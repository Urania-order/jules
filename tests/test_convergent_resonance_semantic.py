import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.context_exposure import ContextExposure, AgentType
from smos.models.models import EpistemicStatus
from smos.services.context_exposure_service import ContextExposureService
from smos.services.convergent_resonance_service import ConvergentResonanceService, ResonanceCandidate
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter
from smos.models.domain_relation import DomainRelation


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_detect_without_semantic_unchanged(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    candidates = crs.detect(include_semantic=False)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.generation_source == "exact_claim_match"
    assert cand.semantic_candidates == []
    assert cand.confidence > 0.0


def test_detect_for_conclusion_without_semantic_unchanged(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    cand = crs.detect_for_conclusion("Co-SMOS scales linearly", include_semantic=False)
    assert cand is not None
    assert cand.generation_source == "exact_claim_match"
    assert cand.semantic_candidates == []


def test_detect_with_semantic_generates_candidates(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.generation_source == "both"
    assert len(cand.semantic_candidates) > 0


def test_detect_semantic_requires_task_10_validation(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Co-SMOS scales linearly", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Completely different claim", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 0


def test_detect_semantic_does_not_introduce_semantic_match(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "AI enhances efficiency", "confidence": 0.9},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Artificial intelligence improves output", "confidence": 0.9},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    # Even if semantically similar, claims are not exact text match under conclusions_match
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 0


def test_detect_semantic_single_pair_does_not_bypass_min_agents(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    candidates = crs.detect(min_agents=2, include_semantic=True)
    assert len(candidates) == 0


def test_detect_semantic_marks_generation_source(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 1
    assert candidates[0].generation_source == "both"


def test_detect_semantic_populates_semantic_candidates(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 1
    sem_cands = candidates[0].semantic_candidates
    assert len(sem_cands) > 0
    ref = sem_cands[0]
    assert "entity_type" in ref
    assert "entity_id" in ref
    assert "similarity" in ref
    assert "model_name" in ref


def test_detect_semantic_candidates_are_references_not_evidence(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101, 102],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201, 202],
        conclusion={"claim": "Linear scaling in cluster", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    cand = crs.detect(include_semantic=True)[0]

    # supporting_trajectories and contexts must only contain original trajectory data
    assert len(cand.supporting_trajectories) == 2
    assert len(cand.independent_contexts) == 2


def test_detect_semantic_does_not_create_semantic_cluster(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Shared claim", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Shared claim", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 1
    # Check that output kind remains candidate_resonance and no cluster entity created
    assert candidates[0].kind == "candidate_resonance"


def test_semantic_similarity_does_not_alter_confidence(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Identical claim", "confidence": 0.7},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Identical claim", "confidence": 0.9},
    )

    crs_no_sem = ConvergentResonanceService(db_session)
    c_no_sem = crs_no_sem.detect(include_semantic=False)[0]

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs_sem = ConvergentResonanceService(db_session, semantic_service=sss)
    c_sem = crs_sem.detect(include_semantic=True)[0]

    assert c_no_sem.confidence == pytest.approx(c_sem.confidence, abs=1e-6)


def test_confidence_uses_task_10_formula_only(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Formula claim", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Formula claim", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    cand = crs.detect(include_semantic=True)[0]
    # base = 0.8, scaled = min(1.0, 0.8 * (2 / 2) ** 0.5) = 0.8
    assert cand.confidence == pytest.approx(0.8, abs=1e-5)


def test_merged_candidate_generation_source_both(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Merged claim", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Merged claim", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 1
    assert candidates[0].generation_source == "both"


def test_merged_candidate_semantic_candidates_union(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Union claim", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Union claim", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    cand = crs.detect(include_semantic=True)[0]
    refs = cand.semantic_candidates
    # Check deduplication
    ref_keys = [(r["entity_type"], r["entity_id"], r["model_name"]) for r in refs]
    assert len(ref_keys) == len(set(ref_keys))


def test_merged_candidate_confidence_is_task_10_original(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Original conf claim", "confidence": 0.6},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Original conf claim", "confidence": 0.6},
    )

    crs = ConvergentResonanceService(db_session)
    c1 = crs.detect(include_semantic=False)[0]
    c2 = crs.detect(include_semantic=True)[0]
    assert c1.confidence == pytest.approx(c2.confidence)


def test_detect_for_conclusion_with_semantic(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Target claim", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Target claim", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    cand = crs.detect_for_conclusion("Target claim", include_semantic=True)
    assert cand is not None
    assert cand.generation_source == "both"


def test_detect_for_conclusion_semantic_does_not_bypass_task_10(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Single agent claim", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    cand = crs.detect_for_conclusion("Single agent claim", min_agents=2, include_semantic=True)
    assert cand is None


def test_detect_for_conclusion_no_second_matching_rule(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Apples are fruit", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Oranges are fruit", "confidence": 0.8},
    )

    sss = SemanticSearchService(db_session, HashFallbackAdapter())
    sss.index_canonical("context_exposure", e1.id)
    sss.index_canonical("context_exposure", e2.id)

    crs = ConvergentResonanceService(db_session, semantic_service=sss)
    cand = crs.detect_for_conclusion("Apples are fruit", include_semantic=True)
    assert cand is None


def test_detect_semantic_read_only(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Read only check", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Read only check", "confidence": 0.8},
    )

    rel_count_before = db_session.query(DomainRelation).count()
    crs = ConvergentResonanceService(db_session)
    crs.detect(include_semantic=True)
    rel_count_after = db_session.query(DomainRelation).count()
    assert rel_count_before == rel_count_after


def test_detect_semantic_does_not_create_domain_relation(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "No rel test", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "No rel test", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    crs.detect(include_semantic=True)
    assert db_session.query(DomainRelation).count() == 0


def test_detect_semantic_does_not_promote_epistemic_status(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Status check", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Status check", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    crs.detect(include_semantic=True)

    db_session.refresh(e1)
    db_session.refresh(e2)
    assert e1.epistemic_status == EpistemicStatus.OBSERVED
    assert e2.epistemic_status == EpistemicStatus.OBSERVED


def test_detect_semantic_candidates_remain_hypothesized(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Hypothesized check", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Hypothesized check", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    cand = crs.detect(include_semantic=True)[0]
    assert cand.epistemic_status == EpistemicStatus.HYPOTHESIZED.value


def test_detect_semantic_kind_still_candidate_resonance(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Kind check", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Kind check", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    cand = crs.detect(include_semantic=True)[0]
    assert cand.kind == "candidate_resonance"


def test_semantic_service_injectable(db_session):
    custom_adapter = HashFallbackAdapter(dimension=128, model_name="custom-test")
    custom_sss = SemanticSearchService(db_session, custom_adapter)
    crs = ConvergentResonanceService(db_session, semantic_service=custom_sss)
    assert crs.semantic_service == custom_sss


def test_semantic_no_auto_index_context_exposure(db_session):
    ces = ContextExposureService(db_session)
    e1 = ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "No auto index check", "confidence": 0.8},
    )
    e2 = ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "No auto index check", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    crs.detect(include_semantic=True)

    # Context Exposures must NOT be auto-indexed into SemanticIndexEntry
    sss = crs.semantic_service
    neighbors = sss.similar("context_exposure", e1.id)
    assert neighbors == []


def test_detect_semantic_skips_if_context_exposure_not_indexed(db_session):
    ces = ContextExposureService(db_session)
    ces.record(
        agent_type="researcher",
        agent_id=1,
        role="researcher",
        context_ids=[101],
        conclusion={"claim": "Unindexed test", "confidence": 0.8},
    )
    ces.record(
        agent_type="skeptic",
        agent_id=2,
        role="skeptic",
        context_ids=[201],
        conclusion={"claim": "Unindexed test", "confidence": 0.8},
    )

    crs = ConvergentResonanceService(db_session)
    # When exposures are not indexed, semantic_service.similar returns [], so generation_source falls back to exact_claim_match
    candidates = crs.detect(include_semantic=True)
    assert len(candidates) == 1
    assert candidates[0].generation_source == "exact_claim_match"
    assert candidates[0].semantic_candidates == []
