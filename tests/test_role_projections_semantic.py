"""Unit tests for semantic-enhanced role projections (TASK 29).

Validates PhenomenonPerspective, ContextPerspective, ConstraintPerspective, and
RoleProjectionService semantic retrieval capabilities, preserving read-only and
backward compatibility contracts.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from smos.core.database import Base
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.domain_relation import DomainRelation
from smos.models.models import EpistemicStatus, RelationType
from smos.services.embedding_fallback import HashFallbackAdapter
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.role_projection_service import (
    RoleProjectionService,
    PhenomenonPerspective,
    ContextPerspective,
    ConstraintPerspective,
)


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_phenomenon_perspective_semantic_neighbors(db_session: Session):
    p1 = Phenomenon(name="Desertification", description="Expansion of arid lands", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Soil Erosion", description="Loss of topsoil layer", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    neighbors = perspective.semantic_neighbors(p1.id)

    assert len(neighbors) == 1
    assert neighbors[0]["entity_type"] == "phenomenon"
    assert neighbors[0]["entity_id"] == p2.id
    assert "similarity" in neighbors[0]
    assert "model_name" in neighbors[0]


def test_phenomenon_perspective_semantic_neighbors_empty_index(db_session: Session):
    p1 = Phenomenon(name="Desertification", description="Expansion of arid lands", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add(p1)
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    neighbors = perspective.semantic_neighbors(p1.id)

    assert neighbors == []


def test_phenomenon_perspective_semantic_search(db_session: Session):
    p1 = Phenomenon(name="Solar Flare", description="Electromagnetic burst from Sun", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add(p1)
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    results = perspective.semantic_search("Sun burst")

    assert len(results) == 1
    assert results[0]["entity_type"] == "phenomenon"
    assert results[0]["entity_id"] == p1.id


def test_phenomenon_perspective_semantic_search_filter(db_session: Session):
    p1 = Phenomenon(name="Drought", description="Water shortage", epistemic_status=EpistemicStatus.OBSERVED)
    c1 = Context(name="Arid Climate", description="Low rainfall region")
    db_session.add_all([p1, c1])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("context", c1.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    results = perspective.semantic_search("Water shortage", entity_types=["context"])

    assert len(results) == 1
    assert results[0]["entity_type"] == "context"
    assert results[0]["entity_id"] == c1.id


def test_context_perspective_semantic_neighbors(db_session: Session):
    c1 = Context(name="Alpine Zone", description="High altitude ecosystems")
    c2 = Context(name="Subalpine Zone", description="Transitional high forest")
    db_session.add_all([c1, c2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("context", c1.id)
    search_service.index_canonical("context", c2.id)

    perspective = ContextPerspective(db_session, semantic_service=search_service)
    neighbors = perspective.semantic_neighbors(c1.id)

    assert len(neighbors) == 1
    assert neighbors[0]["entity_type"] == "context"
    assert neighbors[0]["entity_id"] == c2.id


def test_constraint_perspective_semantic_neighbors(db_session: Session):
    k1 = Constraint(name="Water Quota", description="Restricted allocation per hectare")
    k2 = Constraint(name="Pesticide Cap", description="Maximum chemical usage per season")
    db_session.add_all([k1, k2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("constraint", k1.id)
    search_service.index_canonical("constraint", k2.id)

    perspective = ConstraintPerspective(db_session, semantic_service=search_service)
    neighbors = perspective.semantic_neighbors(k1.id)

    assert len(neighbors) == 1
    assert neighbors[0]["entity_type"] == "constraint"
    assert neighbors[0]["entity_id"] == k2.id


def test_to_dict_without_semantics_unchanged(db_session: Session):
    p1 = Phenomenon(name="Rainfall", description="Precipitation", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add(p1)
    db_session.commit()

    service = RoleProjectionService(db_session)
    res = service.phenomenon(p1.id, include_semantics=False)

    assert "semantic_neighbors" not in res
    assert res == {
        "phenomenon_id": p1.id,
        "conditions_allowing_emergence": [],
        "supports": [],
        "blocks": [],
        "changes_after_emergence": [],
        "created_contexts": [],
    }


def test_to_dict_with_semantics_includes_neighbors(db_session: Session):
    p1 = Phenomenon(name="Rainfall", description="Precipitation", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Flood", description="Overflow of water", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    service = RoleProjectionService(db_session, semantic_service=search_service)
    res = service.phenomenon(p1.id, include_semantics=True)

    assert "semantic_neighbors" in res
    assert len(res["semantic_neighbors"]) == 1
    assert res["semantic_neighbors"][0]["entity_id"] == p2.id


def test_to_dict_with_semantics_has_canonical_keys(db_session: Session):
    p1 = Phenomenon(name="Snowfall", description="Solid precipitation", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add(p1)
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)

    service = RoleProjectionService(db_session, semantic_service=search_service)
    res = service.phenomenon(p1.id, include_semantics=True)

    expected_keys = {
        "phenomenon_id",
        "conditions_allowing_emergence",
        "supports",
        "blocks",
        "changes_after_emergence",
        "created_contexts",
        "semantic_neighbors",
    }
    assert set(res.keys()) == expected_keys


def test_semantic_neighbors_read_only(db_session: Session):
    p1 = Phenomenon(name="Heatwave", description="Extreme temperature event", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Wildfire", description="Uncontrolled fire", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    rel_count_before = db_session.query(DomainRelation).count()

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    _ = perspective.semantic_neighbors(p1.id)

    rel_count_after = db_session.query(DomainRelation).count()
    assert rel_count_before == rel_count_after == 0


def test_semantic_neighbors_do_not_create_domain_relation(db_session: Session):
    p1 = Phenomenon(name="Ocean Acidification", description="pH drop", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Coral Bleaching", description="Loss of endosymbionts", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    _ = perspective.semantic_neighbors(p1.id)

    relations = db_session.query(DomainRelation).all()
    assert len(relations) == 0


def test_semantic_neighbors_do_not_modify_canonical(db_session: Session):
    p1 = Phenomenon(name="Glacial Retreat", description="Melting ice sheets", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add(p1)
    db_session.commit()

    initial_updated_at = p1.updated_at

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    _ = perspective.semantic_neighbors(p1.id)

    db_session.refresh(p1)
    assert p1.name == "Glacial Retreat"
    assert p1.epistemic_status == EpistemicStatus.OBSERVED
    assert p1.updated_at == initial_updated_at


def test_semantic_neighbors_do_not_promote_epistemic_status(db_session: Session):
    p1 = Phenomenon(name="Dark Matter Cloud", description="Unseen mass concentration", epistemic_status=EpistemicStatus.HYPOTHESIZED)
    p2 = Phenomenon(name="Gravitational Lensing", description="Bending of light", epistemic_status=EpistemicStatus.HYPOTHESIZED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    _ = perspective.semantic_neighbors(p1.id)

    db_session.refresh(p1)
    db_session.refresh(p2)
    assert p1.epistemic_status == EpistemicStatus.HYPOTHESIZED
    assert p2.epistemic_status == EpistemicStatus.HYPOTHESIZED


def test_semantic_neighbors_are_signal_not_evidence(db_session: Session):
    p1 = Phenomenon(name="Signal A", description="Description A", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Signal B", description="Description B", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service = SemanticSearchService(db_session, HashFallbackAdapter())
    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    neighbors = perspective.semantic_neighbors(p1.id)

    # Neighbors output contains similarity score and entity info, no evidence fields or relations
    for item in neighbors:
        assert "evidence" not in item
        assert "confidence" not in item
        assert "relation_type" not in item


def test_semantic_service_injectable(db_session: Session):
    class CustomAdapter(HashFallbackAdapter):
        def __init__(self):
            super().__init__(dimension=128, model_name="custom-test-v1")

    adapter = CustomAdapter()
    search_service = SemanticSearchService(db_session, adapter)

    p1 = Phenomenon(name="Alpha", description="Alpha description", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Beta", description="Beta description", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    search_service.index_canonical("phenomenon", p1.id)
    search_service.index_canonical("phenomenon", p2.id)

    perspective = PhenomenonPerspective(db_session, semantic_service=search_service)
    neighbors = perspective.semantic_neighbors(p1.id)

    assert len(neighbors) == 1
    assert neighbors[0]["model_name"] == "custom-test-v1"


def test_role_projection_service_unchanged_existing_fields(db_session: Session):
    p1 = Phenomenon(name="A", description="A", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="B", description="B", epistemic_status=EpistemicStatus.OBSERVED)
    db_session.add_all([p1, p2])
    db_session.commit()

    rel = DomainRelation(
        source_type="phenomenon",
        source_id=p1.id,
        relation_type=RelationType.ENABLES,
        target_type="phenomenon",
        target_id=p2.id,
    )
    db_session.add(rel)
    db_session.commit()

    service = RoleProjectionService(db_session)
    res_default = service.phenomenon(p2.id)
    res_semantics = service.phenomenon(p2.id, include_semantics=True)

    assert len(res_default["conditions_allowing_emergence"]) == 1
    assert len(res_semantics["conditions_allowing_emergence"]) == 1
    assert res_default["conditions_allowing_emergence"][0]["id"] == rel.id
