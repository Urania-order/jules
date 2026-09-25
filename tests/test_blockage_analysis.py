import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.models import EpistemicStatus, RelationType
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint, ConstraintType
from smos.models.domain_relation import DomainRelation
from smos.services.phenomenon_service import PhenomenonService
from smos.services.context_service import ContextService
from smos.services.constraint_service import ConstraintService
from smos.services.domain_relation_service import DomainRelationService
from smos.services.role_projection_service import ConstraintPerspective
from smos.services.blockage_analysis_service import (
    BlockageAnalysisService,
    BlockageAnalysis,
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


def test_analyze_blockage_with_direct_constraint(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="Reforestation Project")
    c = c_service.create(
        name="Soil Erosion Limit",
        type=ConstraintType.ECOLOGICAL,
        strength=0.8,
        confidence=0.9,
        evidence=[{"source": "soil_study_2026"}],
    )

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.9,
        evidence=[{"source": "soil_study_2026"}],
    )

    result = ba_service.analyze_blockage(p.id)

    assert result.phenomenon_id == p.id
    assert len(result.direct_constraints) == 1
    d = result.direct_constraints[0]
    assert d["constraint_id"] == c.id
    assert d["relation_type"] == "BLOCKS"
    assert d["confidence"] == 0.9
    assert d["constraint_name"] == "Soil Erosion Limit"
    assert d["constraint_type"] == "ECOLOGICAL"
    assert d["strength"] == 0.8


def test_analyze_blockage_with_indirect_constraint(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Tree Planting")
    p2 = p_service.create(name="Seedling Nursery Supply")
    c = c_service.create(
        name="Water Scarcity",
        type=ConstraintType.PHYSICAL,
        strength=0.9,
        confidence=0.85,
        evidence=[{"doc": "water_report"}],
    )

    # c -> BLOCKS -> p2
    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p2.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.85,
    )
    # p2 -> BLOCKS -> p1
    rel_service.create(
        source_type="phenomenon",
        source_id=p2.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.9,
    )

    result = ba_service.analyze_blockage(p1.id, indirect_max_hops=2)

    assert len(result.indirect_constraints) == 1
    ind = result.indirect_constraints[0]
    assert ind["constraint_id"] == c.id
    assert ind["via"] == {"type": "phenomenon", "id": p2.id}
    assert ind["hops"] == 2
    assert ind["path"] == ["BLOCKS", "BLOCKS"]


def test_analyze_blockage_with_dependency_constraint(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Solar Farm Operation")
    p2 = p_service.create(name="Power Grid Access")
    c = c_service.create(
        name="Regulatory Cap",
        type=ConstraintType.LEGAL,
        confidence=0.8,
        evidence=[{"doc": "law_2026"}],
    )

    # p1 -> REQUIRES -> p2
    rel_service.create(
        source_type="phenomenon",
        source_id=p1.id,
        target_type="phenomenon",
        target_id=p2.id,
        relation_type=RelationType.REQUIRES,
        confidence=0.95,
    )
    # c -> BLOCKS -> p2
    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p2.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.8,
    )

    result = ba_service.analyze_blockage(p1.id)

    assert len(result.dependency_constraints) == 1
    dep = result.dependency_constraints[0]
    assert dep["constraint_id"] == c.id
    assert dep["depends_via"] == {"type": "phenomenon", "id": p2.id}
    assert dep["relation_type"] == "REQUIRES"


def test_analyze_blockage_with_context_constraint(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="Coastal Restoration")
    ctx = ctx_service.create(name="Delta Wetland Region")
    c = c_service.create(
        name="Salinity Threshold",
        type=ConstraintType.ECOLOGICAL,
        context="Delta Wetland Region",
        confidence=0.8,
        evidence=[{"doc": "survey"}],
    )

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.8,
        evidence=[{"doc": "survey"}],
    )

    result = ba_service.analyze_blockage(p.id)

    assert len(result.context_constraints) == 1
    ctx_res = result.context_constraints[0]
    assert ctx_res["context_id"] == ctx.id
    assert ctx_res["context_name"] == "Delta Wetland Region"
    assert ctx_res["reason"] == "hosts_constraint"
    assert c.id in ctx_res["constraint_ids"]


def test_analyze_blockage_with_unknown_constraint(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="Uncertain Project")
    c = c_service.create(
        name="Hypothetical Risk",
        type=ConstraintType.TECHNICAL,
        confidence=0.3,
        evidence=[],
    )

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.3,
        evidence=[],
    )

    result = ba_service.analyze_blockage(p.id)

    assert len(result.unknowns) == 1
    unk = result.unknowns[0]
    assert unk["constraint_id"] == c.id
    assert unk["confidence"] == 0.3
    assert unk["threshold"] == 0.5


def test_direct_constraint_uses_BLOCKS(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev1"])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS)
    res = ba_service.analyze_blockage(p.id)
    assert len(res.direct_constraints) == 1
    assert res.direct_constraints[0]["relation_type"] == "BLOCKS"


def test_direct_constraint_uses_PREVENTS(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev1"])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.PREVENTS)
    res = ba_service.analyze_blockage(p.id)
    assert len(res.direct_constraints) == 1
    assert res.direct_constraints[0]["relation_type"] == "PREVENTS"


def test_direct_constraint_uses_SUPPRESSES(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev1"])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.SUPPRESSES)
    res = ba_service.analyze_blockage(p.id)
    assert len(res.direct_constraints) == 1
    assert res.direct_constraints[0]["relation_type"] == "SUPPRESSES"


def test_indirect_constraint_bounded_by_max_hops(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="Target P")
    p2 = p_service.create(name="Intermediate P1")
    p3 = p_service.create(name="Intermediate P2")
    c = c_service.create(name="Deep Constraint", confidence=0.8, evidence=["ev"])

    # c -> BLOCKS -> p3 -> BLOCKS -> p2 -> BLOCKS -> p1
    rel_service.create("constraint", c.id, "phenomenon", p3.id, RelationType.BLOCKS)
    rel_service.create("phenomenon", p3.id, "phenomenon", p2.id, RelationType.BLOCKS)
    rel_service.create("phenomenon", p2.id, "phenomenon", p1.id, RelationType.BLOCKS)

    # Max hops 2 should not find c (hop 3)
    res2 = ba_service.analyze_blockage(p1.id, indirect_max_hops=2)
    assert len(res2.indirect_constraints) == 0

    # Max hops 3 should find c
    res3 = ba_service.analyze_blockage(p1.id, indirect_max_hops=3)
    assert len(res3.indirect_constraints) == 1
    assert res3.indirect_constraints[0]["hops"] == 3


def test_indirect_constraint_path_documented(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="P1")
    p2 = p_service.create(name="P2")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])

    rel_service.create("constraint", c.id, "phenomenon", p2.id, RelationType.PREVENTS)
    rel_service.create("phenomenon", p2.id, "phenomenon", p1.id, RelationType.BLOCKS)

    res = ba_service.analyze_blockage(p1.id, indirect_max_hops=2)
    assert len(res.indirect_constraints) == 1
    assert res.indirect_constraints[0]["path"] == ["PREVENTS", "BLOCKS"]


def test_dependency_constraint_via_REQUIRES(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="P1")
    p2 = p_service.create(name="P2")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])

    rel_service.create("phenomenon", p1.id, "phenomenon", p2.id, RelationType.REQUIRES)
    rel_service.create("constraint", c.id, "phenomenon", p2.id, RelationType.BLOCKS)

    res = ba_service.analyze_blockage(p1.id)
    assert len(res.dependency_constraints) == 1
    assert res.dependency_constraints[0]["relation_type"] == "REQUIRES"


def test_dependency_constraint_via_DEPENDS_ON(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p1 = p_service.create(name="P1")
    p2 = p_service.create(name="P2")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])

    rel_service.create("phenomenon", p1.id, "phenomenon", p2.id, RelationType.DEPENDS_ON)
    rel_service.create("constraint", c.id, "phenomenon", p2.id, RelationType.BLOCKS)

    res = ba_service.analyze_blockage(p1.id)
    assert len(res.dependency_constraints) == 1
    assert res.dependency_constraints[0]["relation_type"] == "DEPENDS_ON"


def test_context_constraint_includes_linked_contexts(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    ctx = ctx_service.create(name="Context A")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS)
    rel_service.create("constraint", c.id, "context", ctx.id, RelationType.DEPENDS_ON)

    res = ba_service.analyze_blockage(p.id)
    assert len(res.context_constraints) == 1
    assert res.context_constraints[0]["context_id"] == ctx.id


def test_context_constraint_matches_string_field(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    ctx = ctx_service.create(name="Urban Area")
    c = c_service.create(name="C1", context="Urban Area", confidence=0.8, evidence=["ev"])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS)

    res = ba_service.analyze_blockage(p.id)
    assert len(res.context_constraints) == 1
    assert res.context_constraints[0]["context_name"] == "Urban Area"


def test_unknowns_low_confidence(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.2, evidence=["ev1"])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS, confidence=0.2)

    res = ba_service.analyze_blockage(p.id)
    assert len(res.unknowns) == 1
    assert res.unknowns[0]["reason"] == "low_confidence"


def test_unknowns_missing_evidence(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.9, evidence=[])

    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS, confidence=0.9, evidence=[])

    res = ba_service.analyze_blockage(p.id)
    assert len(res.unknowns) == 1
    assert res.unknowns[0]["reason"] == "missing_evidence"


def test_output_kind_is_blockage_analysis(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ba_service = BlockageAnalysisService(db_session)

    res = ba_service.analyze_blockage(p.id)
    assert res.kind == "blockage_analysis"


def test_output_epistemic_status_hypothesized(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ba_service = BlockageAnalysisService(db_session)

    res = ba_service.analyze_blockage(p.id)
    assert res.epistemic_status == EpistemicStatus.HYPOTHESIZED.value


def test_output_note_says_not_prescription(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ba_service = BlockageAnalysisService(db_session)

    res = ba_service.analyze_blockage(p.id)
    assert "NOT prescription" in res.note
    assert "Human review required" in res.note


def test_output_has_no_recommendation_fields(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ba_service = BlockageAnalysisService(db_session)

    res = ba_service.analyze_blockage(p.id)
    assert not hasattr(res, "suggested_action")
    assert not hasattr(res, "recommended_fix")
    assert not hasattr(res, "priority_score")
    assert "recommend" not in res.note.lower()


def test_blockage_analysis_is_read_only(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])
    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS)

    count_before = len(rel_service.list())
    ba_service.analyze_blockage(p.id)
    count_after = len(rel_service.list())

    assert count_before == count_after


def test_blockage_analysis_does_not_modify_constraint_perspective(db_session):
    p_service = PhenomenonService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)
    cp = ConstraintPerspective(db_session, rel_service)

    p = p_service.create(name="P1")
    c = c_service.create(name="C1", confidence=0.8, evidence=["ev"])
    rel_service.create("constraint", c.id, "phenomenon", p.id, RelationType.BLOCKS)

    perspective_before = cp.to_dict(c.id)
    ba_service.analyze_blockage(p.id)
    perspective_after = cp.to_dict(c.id)

    assert perspective_before == perspective_after


def test_blockage_analysis_returns_empty_for_unknown_phenomenon(db_session):
    ba_service = BlockageAnalysisService(db_session)
    res = ba_service.analyze_blockage(99999)

    assert res.phenomenon_id == 99999
    assert res.direct_constraints == []
    assert res.indirect_constraints == []
    assert res.dependency_constraints == []
    assert res.context_constraints == []
    assert res.unknowns == []


def test_blockage_analysis_to_dict(db_session):
    p_service = PhenomenonService(db_session)
    p = p_service.create(name="P1")
    ba_service = BlockageAnalysisService(db_session)

    res = ba_service.analyze_blockage(p.id)
    d = res.to_dict()

    assert isinstance(d, dict)
    assert d["kind"] == "blockage_analysis"
    assert d["phenomenon_id"] == p.id
    assert "direct_constraints" in d
    assert "note" in d


def test_blockage_analysis_ecological_example(db_session):
    p_service = PhenomenonService(db_session)
    ctx_service = ContextService(db_session)
    c_service = ConstraintService(db_session)
    rel_service = DomainRelationService(db_session)
    ba_service = BlockageAnalysisService(db_session, rel_service)

    p = p_service.create(name="Coastal wetland restoration")
    ctx = ctx_service.create(
        name="Delta region",
        components=[{"type": "hydrology"}],
    )
    c = c_service.create(
        name="Salinity threshold",
        type=ConstraintType.ECOLOGICAL,
        strength=0.7,
        confidence=0.8,
        evidence=[{"source": "survey-2026"}],
        context="Delta region",
    )

    rel_service.create(
        source_type="constraint",
        source_id=c.id,
        target_type="phenomenon",
        target_id=p.id,
        relation_type=RelationType.BLOCKS,
        confidence=0.8,
        evidence=[{"source": "survey-2026"}],
    )

    res = ba_service.analyze_blockage(p.id)

    assert len(res.direct_constraints) == 1
    assert res.direct_constraints[0]["constraint_name"] == "Salinity threshold"
    assert res.direct_constraints[0]["constraint_type"] == "ECOLOGICAL"
    assert len(res.context_constraints) == 1
    assert res.context_constraints[0]["context_name"] == "Delta region"
