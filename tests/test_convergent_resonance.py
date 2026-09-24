import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.context_exposure import ContextExposure, AgentType
from smos.models.domain_relation import DomainRelation
from smos.models.epistemic import EpistemicStatus, IntellectualCluster
from smos.services.context_exposure_service import ContextExposureService
from smos.services.convergent_resonance_service import (
    ConvergentResonanceService,
    ResonanceCandidate,
)
from smos.services.resonance_service import ResonanceService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_jaccard_disjoint(db_session):
    service = ConvergentResonanceService(db_session)
    assert service.jaccard([1, 2], [3, 4]) == 0.0


def test_jaccard_identical(db_session):
    service = ConvergentResonanceService(db_session)
    assert service.jaccard([1, 2, 3], [1, 2, 3]) == 1.0


def test_jaccard_partial(db_session):
    service = ConvergentResonanceService(db_session)
    # [1, 2] and [2, 3]: intersection = {2} (len 1), union = {1, 2, 3} (len 3) -> 1/3
    assert abs(service.jaccard([1, 2], [2, 3]) - 1 / 3) < 1e-6


def test_conclusions_match_normalized(db_session):
    service = ConvergentResonanceService(db_session)
    c1 = {"claim": "  High Solar Radiation  ", "confidence": 0.8}
    c2 = {"claim": "high solar radiation", "confidence": 0.9}
    assert service.conclusions_match(c1, c2) is True


def test_conclusions_match_key_based(db_session):
    service = ConvergentResonanceService(db_session)
    c1 = {"text": "Volcanic Eruption Imminent"}
    c2 = {"claim": "volcanic eruption imminent"}
    assert service.conclusions_match(c1, c2) is True


def test_conclusions_dont_match(db_session):
    service = ConvergentResonanceService(db_session)
    c1 = {"claim": "Option A"}
    c2 = {"claim": "Option B"}
    assert service.conclusions_match(c1, c2) is False


def test_independent_trajectories_by_role(db_session):
    service = ConvergentResonanceService(db_session)
    e1 = ContextExposure(agent_type=AgentType.HUMAN, role="Analyst", context_ids=[101, 102])
    e2 = ContextExposure(agent_type=AgentType.HUMAN, role="Observer", context_ids=[201, 202])
    assert service.are_independent_trajectories(e1, e2, max_overlap=0.5) is True


def test_independent_trajectories_by_context(db_session):
    service = ConvergentResonanceService(db_session)
    e1 = ContextExposure(agent_type=AgentType.LLM, role="Analyst", context_ids=[1, 2, 3, 4])
    e2 = ContextExposure(agent_type=AgentType.LLM, role="Analyst", context_ids=[1, 2, 3, 4])
    # Same role, same agent type -> NOT independent
    assert service.are_independent_trajectories(e1, e2, max_overlap=0.5) is False

    e3 = ContextExposure(agent_type=AgentType.HUMAN, role="Analyst", context_ids=[1, 2, 3, 4])
    # Different agent_type -> candidate for diff agent, but context overlap = 1.0 > 0.5 -> NOT independent
    assert service.are_independent_trajectories(e1, e3, max_overlap=0.5) is False


# --- Required Scenario 1: test_genuine_convergence ---
def test_genuine_convergence(db_session):
    exp_service = ContextExposureService(db_session)
    # Agent 1
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="Geologist",
        context_ids=[1, 2, 3],
        conclusion={"claim": "Fault line active", "confidence": 0.8},
    )
    # Agent 2
    exp_service.record(
        agent_type=AgentType.LLM,
        role="Seismologist",
        context_ids=[10, 11, 12],
        conclusion={"claim": "fault line active", "confidence": 0.9},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect()

    assert len(results) == 1
    cand = results[0]
    assert cand.kind == "candidate_resonance"
    assert cand.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert "NOT fact" in cand.note
    assert len(cand.supporting_trajectories) == 2


# --- Required Scenario 2: test_identical_context_convergence ---
def test_identical_context_convergence(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1, 2, 3],
        conclusion={"claim": "Identical Context Claim", "confidence": 0.8},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[1, 2, 3],  # Jaccard = 1.0 > 0.5
        conclusion={"claim": "identical context claim", "confidence": 0.8},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect()
    assert len(results) == 0


# --- Required Scenario 3: test_contradiction ---
def test_contradiction(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1, 2],
        conclusion={"claim": "Outcome is X", "confidence": 0.8},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[3, 4],
        conclusion={"claim": "Outcome is Y", "confidence": 0.8},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect()
    assert len(results) == 0


# --- Required Scenario 4: test_insufficient_evidence ---
def test_insufficient_evidence(db_session):
    exp_service = ContextExposureService(db_session)
    # Single exposure
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1, 2],
        conclusion={"claim": "Alone in the dark", "confidence": 0.9},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect()
    assert len(results) == 0


# --- Critical Output Checks ---
def test_output_kind_is_candidate_resonance(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1, 2],
        conclusion={"claim": "Target Claim"},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[3, 4],
        conclusion={"claim": "target claim"},
    )

    res_service = ConvergentResonanceService(db_session)
    cand = res_service.detect()[0]
    assert cand.kind == "candidate_resonance"


def test_output_epistemic_status_hypothesized(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1],
        conclusion={"claim": "Target Claim"},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[2],
        conclusion={"claim": "Target Claim"},
    )

    res_service = ConvergentResonanceService(db_session)
    cand = res_service.detect()[0]
    assert cand.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert cand.epistemic_status != EpistemicStatus.OBSERVED.value


def test_output_has_warning_note(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1],
        conclusion={"claim": "Warn Claim"},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[2],
        conclusion={"claim": "Warn Claim"},
    )

    res_service = ConvergentResonanceService(db_session)
    cand = res_service.detect()[0]
    assert "Candidate resonance — NOT fact" in cand.note


def test_resonance_does_not_create_domain_relation(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1],
        conclusion={"claim": "Relation Check"},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[2],
        conclusion={"claim": "Relation Check"},
    )

    initial_relations_count = db_session.query(DomainRelation).count()

    res_service = ConvergentResonanceService(db_session)
    _ = res_service.detect()

    final_relations_count = db_session.query(DomainRelation).count()
    assert initial_relations_count == final_relations_count == 0


def test_resonance_does_not_modify_exposures(db_session):
    exp_service = ContextExposureService(db_session)
    e1 = exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1],
        conclusion={"claim": "Immutable Test"},
    )
    e2 = exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[2],
        conclusion={"claim": "Immutable Test"},
    )

    res_service = ConvergentResonanceService(db_session)
    _ = res_service.detect()

    e1_refreshed = exp_service.get(e1.id)
    e2_refreshed = exp_service.get(e2.id)

    assert e1_refreshed.role == "RoleA"
    assert e2_refreshed.role == "RoleB"


def test_resonance_does_not_touch_knowledge_level(db_session):
    # Verify stub and IntellectualCluster remain untouched
    stub = ResonanceService(db_session)
    res = stub.record_resonance(1, 2, 0.5)
    assert res["status"] == "recorded"

    cluster = IntellectualCluster(name="Test Cluster", resonance=0.5)
    db_session.add(cluster)
    db_session.commit()

    cluster_db = db_session.query(IntellectualCluster).filter(IntellectualCluster.name == "Test Cluster").first()
    assert cluster_db.resonance == 0.5


def test_resonance_service_stub_unchanged():
    import smos.services.resonance_service as resonance_service_mod
    import inspect
    source = inspect.getsource(resonance_service_mod)
    assert "Stub implementation for ECO Co-SMOS v0.9" in source


def test_detect_empty_when_no_exposures(db_session):
    res_service = ConvergentResonanceService(db_session)
    assert res_service.detect() == []


def test_detect_for_conclusion_claim(db_session):
    exp_service = ContextExposureService(db_service := db_session)
    exp_service.record(
        agent_type=AgentType.HUMAN,
        role="RoleA",
        context_ids=[1],
        conclusion={"claim": "Specific Claim"},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="RoleB",
        context_ids=[2],
        conclusion={"claim": "Specific Claim"},
    )

    res_service = ConvergentResonanceService(db_session)
    c1 = res_service.detect_for_conclusion("Specific Claim")
    assert c1 is not None
    assert c1.converging_conclusion.get("claim") == "Specific Claim"

    c2 = res_service.detect_for_conclusion("Nonexistent Claim")
    assert c2 is None


def test_confidence_scales_with_agents(db_session):
    exp_service = ContextExposureService(db_session)
    # 2 agents group
    exp_service.record(agent_type=AgentType.HUMAN, role="A1", context_ids=[1], conclusion={"claim": "Scale Claim", "confidence": 0.5})
    exp_service.record(agent_type=AgentType.LLM, role="A2", context_ids=[2], conclusion={"claim": "Scale Claim", "confidence": 0.5})

    res_service = ConvergentResonanceService(db_session)
    c_2agents = res_service.detect()[0]

    # Add 3rd agent
    exp_service.record(agent_type=AgentType.DIGITAL_TWIN, role="A3", context_ids=[3], conclusion={"claim": "Scale Claim", "confidence": 0.5})
    c_3agents = res_service.detect()[0]

    assert c_3agents.confidence > c_2agents.confidence


def test_shared_context_is_intersection(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(agent_type=AgentType.HUMAN, role="A1", context_ids=[10, 20, 30], conclusion={"claim": "Overlap Claim"})
    exp_service.record(agent_type=AgentType.LLM, role="A2", context_ids=[20, 30, 40], conclusion={"claim": "Overlap Claim"})

    res_service = ConvergentResonanceService(db_session)
    cand = res_service.detect()[0]
    assert cand.shared_context == [20, 30]
