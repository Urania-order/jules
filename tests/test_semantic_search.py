import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.semantic_index import SemanticIndexEntry
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.prediction import Prediction
from smos.models.experience import Recipe
from smos.models.epistemic import EpistemicStatus
from smos.services.embedding_fallback import HashFallbackAdapter
from smos.services.semantic_search_service import SemanticSearchService, build_canonical_semantic_text


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def adapter():
    return HashFallbackAdapter(dimension=128, model_name="test-hash-128")


def test_index_stores_entry(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Phenomenon: Air Cleaning Facility")

    entry = (
        db_session.query(SemanticIndexEntry)
        .filter_by(entity_type="phenomenon", entity_id=1, model_name=adapter.model_name)
        .first()
    )
    assert entry is not None
    assert entry.dimension == 128
    assert len(entry.vector) == 128


def test_index_same_entity_twice_updates(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Initial text")
    first_hash = db_session.query(SemanticIndexEntry).first().text_hash

    service.index("phenomenon", 1, "Updated text")
    entries = db_session.query(SemanticIndexEntry).all()
    assert len(entries) == 1
    assert entries[0].text_hash != first_hash


def test_index_does_not_create_duplicate(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Identical text")
    service.index("phenomenon", 1, "Identical text")

    count = db_session.query(SemanticIndexEntry).count()
    assert count == 1


def test_index_does_not_modify_canonical_entity(db_session, adapter):
    phenom = Phenomenon(
        name="Solar Panel Dusting",
        description="Dust accumulation reduces efficiency",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    db_session.add(phenom)
    db_session.commit()

    orig_status = phenom.epistemic_status
    orig_updated_at = phenom.updated_at

    service = SemanticSearchService(db_session, adapter)
    service.index_canonical("phenomenon", phenom.id)

    refetched = db_session.query(Phenomenon).filter_by(id=phenom.id).first()
    assert refetched.epistemic_status == orig_status
    assert refetched.updated_at == orig_updated_at


def test_index_does_not_create_domain_relation(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Phenomenon text")
    service.index("phenomenon", 2, "Another phenomenon text")

    relations_count = db_session.query(DomainRelation).count()
    assert relations_count == 0


def test_index_does_not_promote_epistemic_status(db_session, adapter):
    phenom = Phenomenon(
        name="Hypothetical Emergence",
        description="Hypothesized effect",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    db_session.add(phenom)
    db_session.commit()

    service = SemanticSearchService(db_session, adapter)
    service.index_canonical("phenomenon", phenom.id)

    refetched = db_session.query(Phenomenon).filter_by(id=phenom.id).first()
    assert refetched.epistemic_status == EpistemicStatus.HYPOTHESIZED


def test_search_returns_top_k(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Clean Air Filter Unit")
    service.index("phenomenon", 2, "Industrial Chimney Emissions")
    service.index("context", 1, "Urban Environmental Zone")

    results = service.search(query="Clean Air Filter", k=2)
    assert len(results) == 2
    assert "similarity" in results[0]
    assert "entity_type" in results[0]


def test_search_filters_entity_types(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Clean Air Filter Unit")
    service.index("context", 10, "Urban Environmental Zone")
    service.index("constraint", 20, "Filter Flow Constraint")

    results = service.search(query="Filter", k=10, entity_types=["phenomenon", "constraint"])
    types = {r["entity_type"] for r in results}
    assert "context" not in types
    assert types.issubset({"phenomenon", "constraint"})


def test_search_empty_index_returns_empty(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    results = service.search(query="test query")
    assert results == []


def test_similar_returns_neighbors(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Clean Air Filter Unit")
    service.index("phenomenon", 2, "Secondary Dust Exhauster")
    service.index("context", 1, "Zone Cleanliness")

    neighbors = service.similar("phenomenon", 1, k=2)
    assert len(neighbors) == 2
    for n in neighbors:
        # Must exclude self
        assert not (n["entity_type"] == "phenomenon" and n["entity_id"] == 1)


def test_similar_excludes_self(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 10, "Target entity text")
    service.index("phenomenon", 11, "Other entity text")

    neighbors = service.similar("phenomenon", 10, k=10)
    for n in neighbors:
        assert not (n["entity_type"] == "phenomenon" and n["entity_id"] == 10)


def test_search_is_read_only(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 1, "Sample Phenomenon")

    count_before = db_session.query(SemanticIndexEntry).count()
    _ = service.search(query="Sample", k=5)
    _ = service.similar("phenomenon", 1, k=5)
    count_after = db_session.query(SemanticIndexEntry).count()

    assert count_before == count_after


def test_index_canonical_entities(db_session, adapter):
    p = Phenomenon(name="Smog Reduction", description="Reduction in particulate matter")
    c = Context(name="City Center Area", description="Dense urban area")
    cnt = Constraint(name="Filter Pressure Limit", description="Max 50 kPa")
    pot = PotentialPhenomenon(phenomenon="Clean Air Corridor", status="POSSIBLE")
    pred = Prediction(expected_state="Air Quality Index < 50", conditions="Filters active")
    rec = Recipe(title="Filter Cleaning Protocol", description="Standard washing steps")

    db_session.add_all([p, c, cnt, pot, pred, rec])
    db_session.commit()

    service = SemanticSearchService(db_session, adapter)
    service.index_canonical("phenomenon", p.id)
    service.index_canonical("context", c.id)
    service.index_canonical("constraint", cnt.id)
    service.index_canonical("potential", pot.id)
    service.index_canonical("prediction", pred.id)
    service.index_canonical("recipe", rec.id)

    indexed_entries = db_session.query(SemanticIndexEntry).all()
    assert len(indexed_entries) == 6


def test_index_canonical_uses_deterministic_semantic_text(db_session):
    p = Phenomenon(name="Static Test", description="Deterministic test description")

    text1 = build_canonical_semantic_text("phenomenon", p)
    text2 = build_canonical_semantic_text("phenomenon", p)
    assert text1 == text2
    assert "Static Test" in text1
    assert "Deterministic test description" in text1


def test_delete_removes_index_entry(db_session, adapter):
    service = SemanticSearchService(db_session, adapter)
    service.index("phenomenon", 100, "To be deleted")
    assert db_session.query(SemanticIndexEntry).filter_by(entity_type="phenomenon", entity_id=100).count() == 1

    deleted = service.delete("phenomenon", 100)
    assert deleted is True
    assert db_session.query(SemanticIndexEntry).filter_by(entity_type="phenomenon", entity_id=100).count() == 0

    deleted_again = service.delete("phenomenon", 100)
    assert deleted_again is False
