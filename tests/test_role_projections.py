"""Tests for Role Projection Service and Phenomenon/Context/Constraint Perspectives."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from smos.core.database import Base
from smos.models.domain_relation import DomainRelation
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.models import RelationType, EpistemicStatus
from smos.services.domain_relation_service import DomainRelationService
from smos.services.role_projection_service import (
    RoleProjectionService,
    PhenomenonPerspective,
    ContextPerspective,
    ConstraintPerspective,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def domain_service(db_session):
    return DomainRelationService(db_session)


@pytest.fixture
def role_service(db_session):
    return RoleProjectionService(db_session)


# Phenomenon perspective tests
def test_phenomenon_what_conditions_allow_me_to_emerge(db_session, domain_service):
    p_perspective = PhenomenonPerspective(db_session, domain_service)

    rel_enables = domain_service.create("context", 1, "phenomenon", 10, RelationType.ENABLES)
    rel_requires = domain_service.create("constraint", 2, "phenomenon", 10, RelationType.REQUIRES)
    rel_supports = domain_service.create("phenomenon", 3, "phenomenon", 10, RelationType.SUPPORTS)
    rel_blocks = domain_service.create("context", 4, "phenomenon", 10, RelationType.BLOCKS)

    res = p_perspective.what_conditions_allow_me_to_emerge(10)
    res_ids = [r.id for r in res]

    assert rel_enables.id in res_ids
    assert rel_requires.id in res_ids
    assert rel_supports.id in res_ids
    assert rel_blocks.id not in res_ids


def test_phenomenon_what_supports_me(db_session, domain_service):
    p_perspective = PhenomenonPerspective(db_session, domain_service)

    rel_supports = domain_service.create("phenomenon", 1, "phenomenon", 20, RelationType.SUPPORTS)
    rel_enables = domain_service.create("context", 2, "phenomenon", 20, RelationType.ENABLES)

    res = p_perspective.what_supports_me(20)
    assert len(res) == 1
    assert res[0].id == rel_supports.id


def test_phenomenon_what_blocks_me(db_session, domain_service):
    p_perspective = PhenomenonPerspective(db_session, domain_service)

    rel_blocks = domain_service.create("constraint", 1, "phenomenon", 30, RelationType.BLOCKS)
    rel_prevents = domain_service.create("context", 2, "phenomenon", 30, RelationType.PREVENTS)
    rel_suppresses = domain_service.create("constraint", 3, "phenomenon", 30, RelationType.SUPPRESSES)
    rel_enables = domain_service.create("context", 4, "phenomenon", 30, RelationType.ENABLES)

    res = p_perspective.what_blocks_me(30)
    res_ids = [r.id for r in res]

    assert rel_blocks.id in res_ids
    assert rel_prevents.id in res_ids
    assert rel_suppresses.id in res_ids
    assert rel_enables.id not in res_ids


def test_phenomenon_what_changes_after_i_emerge(db_session, domain_service):
    p_perspective = PhenomenonPerspective(db_session, domain_service)

    rel_changes = domain_service.create("phenomenon", 40, "context", 1, RelationType.CHANGES_CONTEXT)
    rel_transforms = domain_service.create("phenomenon", 40, "phenomenon", 2, RelationType.TRANSFORMS)
    rel_creates = domain_service.create("phenomenon", 40, "context", 3, RelationType.CREATES_CONTEXT)

    res = p_perspective.what_changes_after_i_emerge(40)
    res_ids = [r.id for r in res]

    assert rel_changes.id in res_ids
    assert rel_transforms.id in res_ids
    assert rel_creates.id not in res_ids


def test_phenomenon_what_context_could_i_create(db_session, domain_service):
    p_perspective = PhenomenonPerspective(db_session, domain_service)

    rel_creates = domain_service.create("phenomenon", 50, "context", 1, RelationType.CREATES_CONTEXT)
    rel_changes = domain_service.create("phenomenon", 50, "context", 2, RelationType.CHANGES_CONTEXT)

    res = p_perspective.what_context_could_i_create(50)
    assert len(res) == 1
    assert res[0].id == rel_creates.id


def test_phenomenon_to_dict(db_session, domain_service):
    p_perspective = PhenomenonPerspective(db_session, domain_service)

    domain_service.create("context", 1, "phenomenon", 60, RelationType.ENABLES)
    domain_service.create("phenomenon", 2, "phenomenon", 60, RelationType.SUPPORTS)
    domain_service.create("constraint", 3, "phenomenon", 60, RelationType.BLOCKS)
    domain_service.create("phenomenon", 60, "context", 4, RelationType.CHANGES_CONTEXT)
    domain_service.create("phenomenon", 60, "context", 5, RelationType.CREATES_CONTEXT)

    d = p_perspective.to_dict(60)
    assert d["phenomenon_id"] == 60
    assert len(d["conditions_allowing_emergence"]) == 2
    assert len(d["supports"]) == 1
    assert len(d["blocks"]) == 1
    assert len(d["changes_after_emergence"]) == 1
    assert len(d["created_contexts"]) == 1


# Context perspective tests
def test_context_what_phenomena_do_i_enable(db_session, domain_service):
    c_perspective = ContextPerspective(db_session, domain_service)

    rel_enables_p = domain_service.create("context", 100, "phenomenon", 1, RelationType.ENABLES)
    rel_enables_c = domain_service.create("context", 100, "context", 2, RelationType.ENABLES)

    res = c_perspective.what_phenomena_do_i_enable(100)
    assert len(res) == 1
    assert res[0].id == rel_enables_p.id


def test_context_what_do_i_block(db_session, domain_service):
    c_perspective = ContextPerspective(db_session, domain_service)

    rel_blocks = domain_service.create("context", 101, "phenomenon", 1, RelationType.BLOCKS)
    rel_prevents = domain_service.create("context", 101, "potential", 2, RelationType.PREVENTS)
    rel_suppresses = domain_service.create("context", 101, "phenomenon", 3, RelationType.SUPPRESSES)

    res = c_perspective.what_do_i_block(101)
    res_ids = [r.id for r in res]

    assert rel_blocks.id in res_ids
    assert rel_prevents.id in res_ids
    assert rel_suppresses.id not in res_ids


def test_context_what_do_i_amplify(db_session, domain_service):
    c_perspective = ContextPerspective(db_session, domain_service)

    rel_amplifies = domain_service.create("context", 102, "phenomenon", 1, RelationType.AMPLIFIES)
    rel_suppresses = domain_service.create("context", 102, "phenomenon", 2, RelationType.SUPPRESSES)

    res = c_perspective.what_do_i_amplify(102)
    assert len(res) == 1
    assert res[0].id == rel_amplifies.id


def test_context_what_do_i_suppress(db_session, domain_service):
    c_perspective = ContextPerspective(db_session, domain_service)

    rel_suppresses = domain_service.create("context", 103, "phenomenon", 1, RelationType.SUPPRESSES)
    rel_amplifies = domain_service.create("context", 103, "phenomenon", 2, RelationType.AMPLIFIES)

    res = c_perspective.what_do_i_suppress(103)
    assert len(res) == 1
    assert res[0].id == rel_suppresses.id


def test_context_what_phenomena_created_or_changed_me(db_session, domain_service):
    c_perspective = ContextPerspective(db_session, domain_service)

    rel_creates = domain_service.create("phenomenon", 1, "context", 104, RelationType.CREATES_CONTEXT)
    rel_changes = domain_service.create("phenomenon", 2, "context", 104, RelationType.CHANGES_CONTEXT)
    rel_enables = domain_service.create("context", 3, "context", 104, RelationType.ENABLES)

    res = c_perspective.what_phenomena_created_or_changed_me(104)
    res_ids = [r.id for r in res]

    assert rel_creates.id in res_ids
    assert rel_changes.id in res_ids
    assert rel_enables.id not in res_ids


def test_context_to_dict(db_session, domain_service):
    c_perspective = ContextPerspective(db_session, domain_service)

    domain_service.create("context", 105, "phenomenon", 1, RelationType.ENABLES)
    domain_service.create("context", 105, "phenomenon", 2, RelationType.BLOCKS)
    domain_service.create("context", 105, "phenomenon", 3, RelationType.AMPLIFIES)
    domain_service.create("context", 105, "phenomenon", 4, RelationType.SUPPRESSES)
    domain_service.create("phenomenon", 5, "context", 105, RelationType.CREATES_CONTEXT)

    d = c_perspective.to_dict(105)
    assert d["context_id"] == 105
    assert len(d["enabled_phenomena"]) == 1
    assert len(d["blocks"]) == 1
    assert len(d["amplifies"]) == 1
    assert len(d["suppresses"]) == 1
    assert len(d["created_or_changed_by_phenomena"]) == 1


# Constraint perspective tests
def test_constraint_what_am_i_blocking(db_session, domain_service):
    cn_perspective = ConstraintPerspective(db_session, domain_service)

    rel_blocks = domain_service.create("constraint", 200, "phenomenon", 1, RelationType.BLOCKS)
    rel_prevents = domain_service.create("constraint", 200, "potential", 2, RelationType.PREVENTS)
    rel_suppresses = domain_service.create("constraint", 200, "phenomenon", 3, RelationType.SUPPRESSES)
    rel_requires = domain_service.create("constraint", 200, "phenomenon", 4, RelationType.REQUIRES)

    res = cn_perspective.what_am_i_blocking(200)
    res_ids = [r.id for r in res]

    assert rel_blocks.id in res_ids
    assert rel_prevents.id in res_ids
    assert rel_suppresses.id in res_ids
    assert rel_requires.id not in res_ids


def test_constraint_how_strong_is_evidence(db_session, domain_service):
    cn_perspective = ConstraintPerspective(db_session, domain_service)

    domain_service.create(
        "constraint", 201, "phenomenon", 1, RelationType.BLOCKS,
        confidence=0.8, evidence=["ev1", "ev2"]
    )
    domain_service.create(
        "constraint", 201, "potential", 2, RelationType.PREVENTS,
        confidence=0.6, evidence=["ev3"]
    )

    ev = cn_perspective.how_strong_is_evidence(201)
    assert ev["count"] == 2
    assert abs(ev["avg_confidence"] - 0.7) < 1e-6
    assert ev["evidence_count"] == 3


def test_constraint_is_blockage_direct_or_indirect(db_session, domain_service):
    cn_perspective = ConstraintPerspective(db_session, domain_service)

    # Constraint 202 direct blocks Phenomenon 1
    rel_direct = domain_service.create("constraint", 202, "phenomenon", 1, RelationType.BLOCKS)
    # Phenomenon 1 direct blocks Potential 2 (indirect for Constraint 202)
    rel_indirect = domain_service.create("phenomenon", 1, "potential", 2, RelationType.BLOCKS)

    res = cn_perspective.is_blockage_direct_or_indirect(202)
    assert len(res["direct"]) == 1
    assert res["direct"][0].id == rel_direct.id
    assert len(res["indirect"]) == 1
    assert res["indirect"][0].id == rel_indirect.id


def test_constraint_what_other_constraints_depend_on_me(db_session, domain_service):
    cn_perspective = ConstraintPerspective(db_session, domain_service)

    rel_dep = domain_service.create("constraint", 203, "constraint", 204, RelationType.DEPENDS_ON)
    domain_service.create("phenomenon", 1, "constraint", 204, RelationType.DEPENDS_ON)

    res = cn_perspective.what_other_constraints_depend_on_me(204)
    assert len(res) == 1
    assert res[0].id == rel_dep.id


def test_constraint_to_dict(db_session, domain_service):
    cn_perspective = ConstraintPerspective(db_session, domain_service)

    domain_service.create(
        "constraint", 205, "phenomenon", 1, RelationType.BLOCKS,
        confidence=0.9, evidence=["doc"]
    )
    domain_service.create("constraint", 206, "constraint", 205, RelationType.DEPENDS_ON)

    d = cn_perspective.to_dict(205)
    assert d["constraint_id"] == 205
    assert len(d["blockages"]) == 1
    assert d["evidence_strength"]["count"] == 1
    assert d["evidence_strength"]["avg_confidence"] == 0.9
    assert len(d["blockage_reach"]["direct"]) == 1
    assert len(d["dependent_constraints"]) == 1


# General & Service Tests
def test_role_projection_service_factory(db_session, domain_service):
    service = RoleProjectionService(db_session, domain_service)

    domain_service.create("context", 1, "phenomenon", 10, RelationType.ENABLES)
    domain_service.create("context", 20, "phenomenon", 2, RelationType.BLOCKS)
    domain_service.create("constraint", 30, "phenomenon", 3, RelationType.PREVENTS)

    p_dict = service.phenomenon(10)
    c_dict = service.context(20)
    cn_dict = service.constraint(30)

    assert p_dict["phenomenon_id"] == 10
    assert c_dict["context_id"] == 20
    assert cn_dict["constraint_id"] == 30


def test_projection_reuses_domain_relation(db_session, domain_service):
    count_before = db_session.query(DomainRelation).count()
    service = RoleProjectionService(db_session, domain_service)
    service.phenomenon(999)
    service.context(999)
    service.constraint(999)
    count_after = db_session.query(DomainRelation).count()

    assert count_before == count_after


def test_projection_does_not_calculate_new_truth(db_session):
    """Assertion test documenting that projections only read existing DomainRelations."""
    service = RoleProjectionService(db_session)
    res = service.phenomenon(123)
    assert res["conditions_allowing_emergence"] == []


def test_projection_returns_empty_for_unknown_id(db_session):
    service = RoleProjectionService(db_session)

    p_res = service.phenomenon(99999)
    assert p_res["conditions_allowing_emergence"] == []
    assert p_res["supports"] == []
    assert p_res["blocks"] == []

    c_res = service.context(99999)
    assert c_res["enabled_phenomena"] == []
    assert c_res["blocks"] == []

    cn_res = service.constraint(99999)
    assert cn_res["blockages"] == []
    assert cn_res["evidence_strength"]["count"] == 0


def test_phenomenon_perspective_does_not_modify_models(db_session):
    initial_rels = db_session.query(DomainRelation).all()
    perspective = PhenomenonPerspective(db_session)
    perspective.to_dict(1)
    final_rels = db_session.query(DomainRelation).all()
    assert len(initial_rels) == len(final_rels)


def test_context_perspective_does_not_modify_models(db_session):
    initial_rels = db_session.query(DomainRelation).all()
    perspective = ContextPerspective(db_session)
    perspective.to_dict(1)
    final_rels = db_session.query(DomainRelation).all()
    assert len(initial_rels) == len(final_rels)


def test_constraint_perspective_does_not_modify_models(db_session):
    initial_rels = db_session.query(DomainRelation).all()
    perspective = ConstraintPerspective(db_session)
    perspective.to_dict(1)
    final_rels = db_session.query(DomainRelation).all()
    assert len(initial_rels) == len(final_rels)
