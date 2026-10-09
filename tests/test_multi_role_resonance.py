import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.context import Context
from smos.models.context_exposure import ContextExposure, AgentType
from smos.models.domain_relation import DomainRelation
from smos.models.epistemic import EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.services.context_exposure_service import ContextExposureService
from smos.services.convergent_resonance_service import (
    ConvergentResonanceService,
    ResonanceCandidate,
)
from smos.models.conclusion_contract import get_claim, get_confidence


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def multi_role_scenario(db_session):
    """Set up the TASK 23 scenario with 1 Phenomenon, 8 Contexts, and 4 ContextExposures."""
    # 1 Phenomenon
    phenomenon = Phenomenon(
        name="Coastal wetland degradation",
        description="Observed degradation in coastal wetland ecosystems.",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    db_session.add(phenomenon)
    db_session.commit()

    # Dynamic context generation
    ctx_research_1 = Context(name="research_data_1", description="Research data batch 1")
    ctx_research_2 = Context(name="research_data_2", description="Research data batch 2")
    ctx_skeptic_1 = Context(name="critical_review_1", description="Critical review batch 1")
    ctx_skeptic_2 = Context(name="critical_review_2", description="Critical review batch 2")
    ctx_engineer_1 = Context(name="engineering_analysis_1", description="Engineering analysis 1")
    ctx_engineer_2 = Context(name="engineering_analysis_2", description="Engineering analysis 2")
    ctx_ecologist_1 = Context(name="field_observation_1", description="Field observation 1")
    ctx_ecologist_2 = Context(name="field_observation_2", description="Field observation 2")

    contexts = [
        ctx_research_1, ctx_research_2,
        ctx_skeptic_1, ctx_skeptic_2,
        ctx_engineer_1, ctx_engineer_2,
        ctx_ecologist_1, ctx_ecologist_2,
    ]
    db_session.add_all(contexts)
    db_session.commit()

    exp_service = ContextExposureService(db_session)

    claim_text = "Salinity rise correlates with degradation"

    # Researcher -> LLM, role: researcher
    e_researcher = exp_service.record(
        agent_type=AgentType.LLM,
        role="researcher",
        context_ids=[ctx_research_1.id, ctx_research_2.id],
        conclusion={"claim": claim_text, "confidence": 0.7},
        provenance={"phenomenon_id": phenomenon.id},
    )

    # Skeptic -> LLM, role: skeptic
    e_skeptic = exp_service.record(
        agent_type=AgentType.LLM,
        role="skeptic",
        context_ids=[ctx_skeptic_1.id, ctx_skeptic_2.id],
        conclusion={"claim": claim_text, "confidence": 0.5},
        provenance={"phenomenon_id": phenomenon.id},
    )

    # Engineer -> LLM, role: engineer
    e_engineer = exp_service.record(
        agent_type=AgentType.LLM,
        role="engineer",
        context_ids=[ctx_engineer_1.id, ctx_engineer_2.id],
        conclusion={"claim": claim_text, "confidence": 0.6},
        provenance={"phenomenon_id": phenomenon.id},
    )

    # Ecologist -> HUMAN, role: ecologist
    e_ecologist = exp_service.record(
        agent_type=AgentType.HUMAN,
        role="ecologist",
        context_ids=[ctx_ecologist_1.id, ctx_ecologist_2.id],
        conclusion={"claim": claim_text, "confidence": 0.8},
        provenance={"phenomenon_id": phenomenon.id},
    )

    return {
        "phenomenon": phenomenon,
        "contexts": {
            "researcher": [ctx_research_1.id, ctx_research_2.id],
            "skeptic": [ctx_skeptic_1.id, ctx_skeptic_2.id],
            "engineer": [ctx_engineer_1.id, ctx_engineer_2.id],
            "ecologist": [ctx_ecologist_1.id, ctx_ecologist_2.id],
        },
        "exposures": {
            "researcher": e_researcher,
            "skeptic": e_skeptic,
            "engineer": e_engineer,
            "ecologist": e_ecologist,
        },
    }


# ============================================================
# TEST GROUP 1 — PERSPECTIVE IDENTITY
# ============================================================

def test_group_1_perspective_identity(db_session, multi_role_scenario):
    exp_service = ContextExposureService(db_session)
    exposures = exp_service.list()

    # 1. Four ContextExposure records exist
    assert len(exposures) == 4

    # 2. All four records refer to the same Phenomenon
    phen_id = multi_role_scenario["phenomenon"].id
    for e in exposures:
        assert e.provenance.get("phenomenon_id") == phen_id

    # 3. All four roles are distinct: researcher, skeptic, engineer, ecologist
    roles = {e.role for e in exposures}
    assert roles == {"researcher", "skeptic", "engineer", "ecologist"}

    # 4. Context sets remain distinct
    context_sets = [tuple(sorted(e.context_ids)) for e in exposures]
    assert len(set(context_sets)) == 4

    # 5. Each exposure retains its own conclusion
    conclusions = {e.role: e.conclusion for e in exposures}
    assert conclusions["researcher"]["confidence"] == 0.7
    assert conclusions["skeptic"]["confidence"] == 0.5
    assert conclusions["engineer"]["confidence"] == 0.6
    assert conclusions["ecologist"]["confidence"] == 0.8

    # 6. agent_type and role remain separate concepts
    agent_types = {e.role: e.agent_type for e in exposures}
    assert agent_types["researcher"] == AgentType.LLM
    assert agent_types["skeptic"] == AgentType.LLM
    assert agent_types["engineer"] == AgentType.LLM
    assert agent_types["ecologist"] == AgentType.HUMAN


# ============================================================
# TEST GROUP 2 — RESONANCE DETECTION
# ============================================================

def test_group_2_resonance_detection(db_session, multi_role_scenario):
    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect()

    assert isinstance(results, list)
    assert len(results) == 1

    candidate = results[0]

    # Verify canonical ResonanceCandidate fields
    assert candidate.kind == "candidate_resonance"
    assert candidate.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert candidate.epistemic_status == "HYPOTHESIZED"

    # Verify candidate represents multiple source trajectories
    trajectories = candidate.supporting_trajectories
    assert len(trajectories) == 4
    roles = {t["role"] for t in trajectories}
    assert roles == {"researcher", "skeptic", "engineer", "ecologist"}


# ============================================================
# TEST GROUP 3 — NON-COLLAPSE (CRITICAL)
# ============================================================

def test_group_3_non_collapse(db_session, multi_role_scenario):
    res_service = ConvergentResonanceService(db_session)
    _ = res_service.detect()

    # 1. All four ContextExposure records still exist
    exp_service = ContextExposureService(db_session)
    exposures = exp_service.list()
    assert len(exposures) == 4

    # 2. All four roles remain distinct
    roles = {e.role for e in exposures}
    assert roles == {"researcher", "skeptic", "engineer", "ecologist"}

    # 3. All four context sets remain distinct
    context_sets = [tuple(sorted(e.context_ids)) for e in exposures]
    assert len(set(context_sets)) == 4

    # 4. Each original conclusion is UNCHANGED
    conclusions = {e.role: e.conclusion for e in exposures}
    assert conclusions["researcher"] == {"claim": "Salinity rise correlates with degradation", "confidence": 0.7}
    assert conclusions["skeptic"] == {"claim": "Salinity rise correlates with degradation", "confidence": 0.5}
    assert conclusions["engineer"] == {"claim": "Salinity rise correlates with degradation", "confidence": 0.6}
    assert conclusions["ecologist"] == {"claim": "Salinity rise correlates with degradation", "confidence": 0.8}

    # 5. No ContextExposure is deleted (checked in 1)
    # 6. No ContextExposure is merged (checked in 1 & 2)
    # 7. No source trajectory is replaced by the resonance candidate (exposures remain ContextExposure instances)
    for e in exposures:
        assert isinstance(e, ContextExposure)

    # 8. No Phenomenon-level final_conclusion is created
    phenomenon = db_session.get(Phenomenon, multi_role_scenario["phenomenon"].id)
    assert not hasattr(phenomenon, "final_conclusion")

    # 9. No Phenomenon-level resonance aggregation field is introduced
    assert not hasattr(phenomenon, "resonance")

    # 10. epistemic_status of source exposures is UNCHANGED
    for e in exposures:
        assert e.epistemic_status == EpistemicStatus.OBSERVED

    # 11. No automatic epistemic promotion occurs
    assert phenomenon.epistemic_status == EpistemicStatus.OBSERVED


# ============================================================
# TEST GROUP 4 — GRAPH NON-MUTATION
# ============================================================

def test_group_4_graph_non_mutation(db_session, multi_role_scenario):
    # Record DomainRelation state BEFORE calling detect()
    before_relations = db_session.query(DomainRelation).all()
    before_count = len(before_relations)

    res_service = ConvergentResonanceService(db_session)
    _ = res_service.detect()

    # Record state AFTER calling detect()
    after_relations = db_session.query(DomainRelation).all()
    after_count = len(after_relations)

    # Assert graph non-mutation
    assert after_count == before_count == 0
    assert after_relations == before_relations


# ============================================================
# TEST GROUP 5 — RESULT SEMANTICS
# ============================================================

def test_group_5_result_semantics(db_session, multi_role_scenario):
    res_service = ConvergentResonanceService(db_session)
    candidates = res_service.detect()

    # Collection returned
    assert isinstance(candidates, list)
    assert len(candidates) == 1

    candidate = candidates[0]

    # candidate_resonance != final_answer
    assert candidate.kind == "candidate_resonance"
    assert candidate.kind != "final_answer"

    # HYPOTHESIZED != OBSERVED
    assert candidate.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert candidate.epistemic_status != EpistemicStatus.OBSERVED.value

    # Source conclusions remain INTACT
    exposures = ContextExposureService(db_session).list()
    for e in exposures:
        assert get_claim(e.conclusion) == "Salinity rise correlates with degradation"


# ============================================================
# TEST GROUP 6 — EDGE CASES
# ============================================================

def test_group_6_insufficient_agents(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.LLM,
        role="researcher",
        context_ids=[1, 2],
        conclusion={"claim": "Salinity rise correlates with degradation", "confidence": 0.7},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect(min_agents=2)
    assert len(results) == 0


def test_group_6_non_matching_claims(db_session):
    exp_service = ContextExposureService(db_session)
    exp_service.record(
        agent_type=AgentType.LLM,
        role="researcher",
        context_ids=[1, 2],
        conclusion={"claim": "Salinity rise correlates with degradation", "confidence": 0.7},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="skeptic",
        context_ids=[3, 4],
        conclusion={"claim": "Temperature rise causes degradation", "confidence": 0.5},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect()
    assert len(results) == 0


def test_group_6_excessive_context_overlap(db_session):
    exp_service = ContextExposureService(db_session)
    # Context overlap Jaccard index = 1.0 > max_context_overlap (0.5)
    exp_service.record(
        agent_type=AgentType.LLM,
        role="researcher",
        context_ids=[1, 2],
        conclusion={"claim": "Salinity rise correlates with degradation", "confidence": 0.7},
    )
    exp_service.record(
        agent_type=AgentType.LLM,
        role="skeptic",
        context_ids=[1, 2],
        conclusion={"claim": "Salinity rise correlates with degradation", "confidence": 0.5},
    )

    res_service = ConvergentResonanceService(db_session)
    results = res_service.detect(max_context_overlap=0.5)
    assert len(results) == 0


# ============================================================
# TEST GROUP 7 — CONCLUSION CONTRACT
# ============================================================

def test_group_7_conclusion_contract(db_session, multi_role_scenario):
    exp_service = ContextExposureService(db_session)
    exposures = exp_service.list()

    expected_confidences = {
        "researcher": 0.7,
        "skeptic": 0.5,
        "engineer": 0.6,
        "ecologist": 0.8,
    }

    for e in exposures:
        claim = get_claim(e.conclusion)
        confidence = get_confidence(e.conclusion)

        assert claim == "Salinity rise correlates with degradation"
        assert confidence == expected_confidences[e.role]
