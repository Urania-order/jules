import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.models import EpistemicStatus, RelationType
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint, ConstraintType
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.services.phenomenon_service import PhenomenonService
from smos.services.context_service import ContextService
from smos.services.constraint_service import ConstraintService
from smos.services.potential_service import PotentialService
from smos.services.domain_relation_service import DomainRelationService
from smos.services.role_projection_service import PhenomenonPerspective
from smos.services.blockage_analysis_service import BlockageAnalysisService
from smos.services.emergence_analysis_service import (
    EmergenceAnalysisService,
    EmergenceAnalysis,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_analyze_emergence_with_two_required_conditions(db_session):
    p_service = PhenomenonService(db_session)
    pot_service = PotentialService(db_session)
    ea_service = EmergenceAnalysisService(db_session)

    p = p_service.create(name="P1")
    pot_service.create(
        phenomenon="P1",
        required_conditions=["cond-A", "cond-B"],
        supporting_contexts=["ctx-1"],
        blocking_constraints=["bc-1", "bc-2"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.necessary_conditions) == 2
    cond_names = [c["condition"] for c in result.necessary_conditions]
    assert "cond-A" in cond_names
    assert "cond-B" in cond_names


def test_analyze_emergence_with_one_supporting_context(db_session):
    p_service = PhenomenonService(db_session)
    pot_service = PotentialService(db_session)
    ea_service = EmergenceAnalysisService(db_session)

    p = p_service.create(name="P1")
    pot_service.create(
        phenomenon="P1",
        required_conditions=["cond-A", "cond-B"],
        supporting_contexts=["ctx-1"],
        blocking_constraints=["bc-1", "bc-2"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.supporting_conditions) == 1
    assert result.supporting_conditions[0]["context"] == "ctx-1"


def test_analyze_emergence_with_two_blocking_constraints(db_session):
    p_service = PhenomenonService(db_session)
    pot_service = PotentialService(db_session)
    ea_service = EmergenceAnalysisService(db_session)

    p = p_service.create(name="P1")
    pot_service.create(
        phenomenon="P1",
        required_conditions=["cond-A", "cond-B"],
        supporting_contexts=["ctx-1"],
        blocking_constraints=["bc-1", "bc-2"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.blocking_conditions) == 2
    b_names = [b["constraint"] for b in result.blocking_conditions]
    assert "bc-1" in b_names
    assert "bc-2" in b_names


def test_emergence_necessary_conditions_via_REQUIRES(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Target P")
    p2 = p_service.create(name="Prerequisite P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p2.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.REQUIRES,
        confidence=0.9,
        evidence=["req_doc"],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.necessary_conditions) == 1
    item = result.necessary_conditions[0]
    assert item["relation_type"] == "REQUIRES"
    assert item["source_type"] == "phenomenon"
    assert item["source_id"] == p2.id


def test_emergence_supporting_conditions_via_ENABLES(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Emergent Phenomenon")
    ctx = ctx_service.create(name="Favorable Context")

    rel_service.create(
        source_type="context",
        source_id=ctx.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.ENABLES,
        confidence=0.85,
        evidence=["enables_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.supporting_conditions) == 1
    assert result.supporting_conditions[0]["relation_type"] == "ENABLES"


def test_emergence_supporting_conditions_via_SUPPORTS(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Target P")
    p2 = p_service.create(name="Supporting P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p2.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.SUPPORTS,
        confidence=0.8,
        evidence=["supports_doc"],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.supporting_conditions) == 1
    assert result.supporting_conditions[0]["relation_type"] == "SUPPORTS"


def test_emergence_supporting_conditions_via_AMPLIFIES(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Target P")
    p2 = p_service.create(name="Amplifying P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p2.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.AMPLIFIES,
        confidence=0.75,
        evidence=["amplifies_doc"],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.supporting_conditions) == 1
    assert result.supporting_conditions[0]["relation_type"] == "AMPLIFIES"


def test_emergence_blocking_conditions_via_BLOCKS(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Target P")
    c = c_service.create(name="Blocking Constraint")

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.9,
        evidence=["blocks_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.blocking_conditions) == 1
    assert result.blocking_conditions[0]["relation_type"] == "BLOCKS"


def test_emergence_blocking_conditions_via_PREVENTS(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Target P")
    c = c_service.create(name="Preventing Constraint")

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.PREVENTS,
        confidence=0.9,
        evidence=["prevents_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.blocking_conditions) == 1
    assert result.blocking_conditions[0]["relation_type"] == "PREVENTS"


def test_emergence_blocking_conditions_via_SUPPRESSES(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Target P")
    c = c_service.create(name="Suppressing Constraint")

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.SUPPRESSES,
        confidence=0.9,
        evidence=["suppresses_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.blocking_conditions) == 1
    assert result.blocking_conditions[0]["relation_type"] == "SUPPRESSES"


def test_emergence_dependencies_via_DEPENDS_ON(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Dependent P")
    p2 = p_service.create(name="Base P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p1.id,
        target_type="phenomenon",
        target_id=p2.id,
        relation_type=RelationType.DEPENDS_ON,
        confidence=0.85,
        evidence=["depends_doc"],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.dependencies) == 1
    assert result.dependencies[0]["relation_type"] == "DEPENDS_ON"


def test_emergence_context_transitions_via_CHANGES_CONTEXT(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Changing P")
    ctx = ctx_service.create(name="Target Context")

    rel_service.create(
        source_type="phenomenon",
        source_id=p.id,
        target_type="context",
        target_id=ctx.id,
        relation_type=RelationType.CHANGES_CONTEXT,
        confidence=0.8,
        evidence=["changes_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.context_transitions) == 1
    assert result.context_transitions[0]["relation_type"] == "CHANGES_CONTEXT"


def test_emergence_context_transitions_via_CREATES_CONTEXT(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Creating P")
    ctx = ctx_service.create(name="New Context")

    rel_service.create(
        source_type="phenomenon",
        source_id=p.id,
        target_type="context",
        target_id=ctx.id,
        relation_type=RelationType.CREATES_CONTEXT,
        confidence=0.9,
        evidence=["creates_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.context_transitions) == 1
    assert result.context_transitions[0]["relation_type"] == "CREATES_CONTEXT"


def test_emergence_possible_downstream_effects_via_CREATES_CONTEXT(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Creating P")
    ctx = ctx_service.create(name="New Context")

    rel_service.create(
        source_type="phenomenon",
        source_id=p.id,
        target_type="context",
        target_id=ctx.id,
        relation_type=RelationType.CREATES_CONTEXT,
        confidence=0.9,
        evidence=["creates_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.possible_downstream_effects) == 1
    assert result.possible_downstream_effects[0]["relation_type"] == "CREATES_CONTEXT"


def test_emergence_possible_downstream_effects_via_CHANGES_CONTEXT(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p = p_service.create(name="Changing P")
    ctx = ctx_service.create(name="Target Context")

    rel_service.create(
        source_type="phenomenon",
        source_id=p.id,
        target_type="context",
        target_id=ctx.id,
        relation_type=RelationType.CHANGES_CONTEXT,
        confidence=0.8,
        evidence=["changes_doc"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.possible_downstream_effects) == 1
    assert result.possible_downstream_effects[0]["relation_type"] == "CHANGES_CONTEXT"


def test_emergence_possible_downstream_effects_via_TRANSFORMS(db_session):
    p_service = PhenomenonService(db_session)
    p2 = p_service.create(name="Target P")
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Transforming P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p1.id,
        target_type="phenomenon",
        target_id=p2.id,
        relation_type=RelationType.TRANSFORMS,
        confidence=0.85,
        evidence=["transforms_doc"],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.possible_downstream_effects) == 1
    assert result.possible_downstream_effects[0]["relation_type"] == "TRANSFORMS"


def test_emergence_unknowns_low_confidence(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Target P")
    p2 = p_service.create(name="Req P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p2.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.REQUIRES,
        confidence=0.3,
        evidence=["doc"],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.unknowns) == 1
    assert result.unknowns[0]["reason"] == "low_confidence"


def test_emergence_unknowns_missing_evidence(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Target P")
    p2 = p_service.create(name="Req P")

    rel_service.create(
        source_type="phenomenon",
        source_id=p2.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.REQUIRES,
        confidence=0.9,
        evidence=[],
    )

    result = ea_service.analyze_emergence(p1.id)

    assert len(result.unknowns) == 1
    assert result.unknowns[0]["reason"] == "missing_evidence"


def test_output_kind_is_emergence_analysis(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ea_service = EmergenceAnalysisService(db_session)

    result = ea_service.analyze_emergence(p.id)

    assert result.kind == "emergence_analysis"


def test_output_epistemic_status_hypothesized(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ea_service = EmergenceAnalysisService(db_session)

    result = ea_service.analyze_emergence(p.id)

    assert result.epistemic_status == EpistemicStatus.HYPOTHESIZED.value


def test_output_note_says_not_prediction(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ea_service = EmergenceAnalysisService(db_session)

    result = ea_service.analyze_emergence(p.id)

    assert "Possibility analysis — NOT prediction" in result.note
    assert "No forecast provided" in result.note
    assert "Human review required" in result.note


def test_output_has_no_prediction_fields(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ea_service = EmergenceAnalysisService(db_session)

    result = ea_service.analyze_emergence(p.id)

    assert not hasattr(result, "predicted_outcome")
    assert not hasattr(result, "forecast")
    assert not hasattr(result, "probability")
    assert not hasattr(result, "expected_date")


def test_emergence_analysis_is_read_only(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="P1")
    p2 = p_service.create(name="P2")
    rel_service.create("phenomenon", p2.id, "phenomenon", p1.id, RelationType.REQUIRES)

    count_before = len(rel_service.list())
    ea_service.analyze_emergence(p1.id)
    count_after = len(rel_service.list())

    assert count_before == count_after


def test_emergence_analysis_does_not_modify_phenomenon_perspective(db_session):
    p_service = PhenomenonService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)
    pp = PhenomenonPerspective(db_session, rel_service)

    p1 = p_service.create(name="P1")
    p2 = p_service.create(name="P2")
    rel_service.create("phenomenon", p2.id, "phenomenon", p1.id, RelationType.REQUIRES)

    perspective_before = pp.to_dict(p1.id)
    ea_service.analyze_emergence(p1.id)
    perspective_after = pp.to_dict(p1.id)

    assert perspective_before == perspective_after


def test_emergence_analysis_does_not_modify_blockage_service(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ea_service = EmergenceAnalysisService(db_session, rel_service)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])
    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS)

    blockage_before = ba_service.analyze_blockage(p.id).to_dict()
    ea_service.analyze_emergence(p.id)
    blockage_after = ba_service.analyze_blockage(p.id).to_dict()

    assert blockage_before == blockage_after


def test_emergence_analysis_returns_empty_for_unknown_phenomenon(db_session):
    ea_service = EmergenceAnalysisService(db_session)

    result = ea_service.analyze_emergence(99999)

    assert result.phenomenon_id == 99999
    assert result.necessary_conditions == []
    assert result.supporting_conditions == []
    assert result.blocking_conditions == []
    assert result.dependencies == []
    assert result.context_transitions == []
    assert result.possible_downstream_effects == []
    assert result.unknowns == []


def test_emergence_analysis_to_dict(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ea_service = EmergenceAnalysisService(db_session)

    result = ea_service.analyze_emergence(p.id)
    d = result.to_dict()

    assert isinstance(d, dict)
    assert d["kind"] == "emergence_analysis"
    assert d["phenomenon_id"] == p.id
    assert "necessary_conditions" in d
    assert "note" in d


def test_emergence_integrates_potential_phenomenon_by_name(db_session):
    p_service = PhenomenonService(db_session)
    pot_service = PotentialService(db_session)
    ea_service = EmergenceAnalysisService(db_session)

    p = p_service.create(name="Emergent Concept")
    pot = pot_service.create(
        phenomenon="Emergent Concept",
        required_conditions=["Resource A"],
        supporting_contexts=["Context B"],
        blocking_constraints=["Constraint C"],
        dependencies=["Dep D"],
        expected_impacts=["Impact E"],
    )

    result = ea_service.analyze_emergence(p.id)

    assert len(result.necessary_conditions) == 1
    assert result.necessary_conditions[0]["condition"] == "Resource A"
    assert result.necessary_conditions[0]["potential_id"] == pot.id

    assert len(result.supporting_conditions) == 1
    assert result.supporting_conditions[0]["context"] == "Context B"

    assert len(result.blocking_conditions) == 1
    assert result.blocking_conditions[0]["constraint"] == "Constraint C"

    assert len(result.dependencies) == 1
    assert result.dependencies[0]["dependency"] == "Dep D"

    assert len(result.possible_downstream_effects) == 1
    assert result.possible_downstream_effects[0]["impact"] == "Impact E"
