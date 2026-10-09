import pytest
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.models.phenomenon import Phenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.semantic_index import SemanticIndexEntry
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


@pytest.fixture(autouse=True)
def cleanup_semantic_index(db):
    yield
    db.query(SemanticIndexEntry).filter(SemanticIndexEntry.entity_id >= 90000).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Auth Tests
# ---------------------------------------------------------------------------

def test_semantic_search_requires_auth():
    resp = client.post("/api/semantic/search", json={"query": "test"})
    assert resp.status_code in (401, 403)


def test_semantic_similar_requires_auth():
    resp = client.get("/api/semantic/similar/phenomenon/1")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/semantic/search Tests
# ---------------------------------------------------------------------------

def test_semantic_search_returns_results(db):
    # Use unique IDs to avoid clashing with other tests in the shared database
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90001, "Quantum Entanglement Resonance")
    svc.index("context", 90002, "Cryogenic Laboratory Context")

    resp = client.post(
        "/api/semantic/search",
        json={"query": "Quantum", "k": 10},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Check that our indexed entities appear in the results
    indexed_pairs = {(r["entity_type"], r["entity_id"]) for r in data}
    assert ("phenomenon", 90001) in indexed_pairs
    assert ("context", 90002) in indexed_pairs
    for item in data:
        assert "entity_type" in item
        assert "entity_id" in item
        assert "similarity" in item
        assert "model_name" in item


def test_semantic_search_empty_index_returns_empty():
    resp = client.post(
        "/api/semantic/search",
        json={"query": "Anything", "entity_types": ["nonexistent_type_x1y2z3"]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_semantic_search_validation_empty_query():
    resp = client.post(
        "/api/semantic/search",
        json={"query": ""},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


def test_semantic_search_validation_k_too_large():
    resp = client.post(
        "/api/semantic/search",
        json={"query": "Test", "k": 101},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


def test_semantic_search_validation_k_zero():
    resp = client.post(
        "/api/semantic/search",
        json={"query": "Test", "k": 0},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


def test_semantic_search_filter_by_entity_types(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90010, "Superconductivity in YBCO")
    svc.index("context", 90020, "High Pressure Cell")

    resp = client.post(
        "/api/semantic/search",
        json={"query": "Superconductivity", "entity_types": ["phenomenon"]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["entity_type"] == "phenomenon" for r in data)
    assert any(r["entity_id"] == 90010 for r in data)


def test_semantic_search_cross_entity_default(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90100, "Thermal Spikes")
    svc.index("constraint", 90200, "Temperature Limit")

    resp = client.post(
        "/api/semantic/search",
        json={"query": "Thermal"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    types = {r["entity_type"] for r in data}
    assert "phenomenon" in types
    assert "constraint" in types


# ---------------------------------------------------------------------------
# GET /api/semantic/similar/{entity_type}/{entity_id} Tests
# ---------------------------------------------------------------------------

def test_semantic_similar_returns_results(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90001, "Source Phenomenon")
    svc.index("phenomenon", 90002, "Neighbor Phenomenon")
    svc.index("context", 90003, "Neighbor Context")

    resp = client.get(
        "/api/semantic/similar/phenomenon/90001",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    indexed_pairs = {(r["entity_type"], r["entity_id"]) for r in data}
    assert ("phenomenon", 90002) in indexed_pairs
    assert ("context", 90003) in indexed_pairs
    assert ("phenomenon", 90001) not in indexed_pairs


def test_semantic_similar_unindexed_entity_returns_empty():
    resp = client.get(
        "/api/semantic/similar/phenomenon/999999",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_semantic_similar_filter_by_entity_types(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90101, "Source Phenomenon")
    svc.index("phenomenon", 90102, "Target Phenomenon")
    svc.index("context", 90103, "Target Context")

    resp = client.get(
        "/api/semantic/similar/phenomenon/90101?entity_types=context",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["entity_type"] == "context" for r in data)
    assert any(r["entity_id"] == 90103 for r in data)


def test_semantic_similar_parses_comma_separated_entity_types(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90201, "Source Entity")
    svc.index("context", 90202, "Context Entity")
    svc.index("constraint", 90203, "Constraint Entity")
    svc.index("recipe", 90204, "Recipe Entity")

    resp = client.get(
        "/api/semantic/similar/phenomenon/90201?entity_types=context,%20constraint",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    types = {r["entity_type"] for r in data}
    assert types.issubset({"context", "constraint"})
    assert "context" in types or "constraint" in types


def test_semantic_similar_empty_entity_types_means_all(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90301, "Source Entity")
    svc.index("context", 90302, "Context Entity")

    resp = client.get(
        "/api/semantic/similar/phenomenon/90301?k=100&entity_types=",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    indexed_pairs = {(r["entity_type"], r["entity_id"]) for r in data}
    assert ("context", 90302) in indexed_pairs


def test_semantic_similar_whitespace_entity_types_means_all(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 90401, "Source Entity")
    svc.index("context", 90402, "Context Entity")

    resp = client.get(
        "/api/semantic/similar/phenomenon/90401?k=100&entity_types=%20%20",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    indexed_pairs = {(r["entity_type"], r["entity_id"]) for r in data}
    assert ("context", 90402) in indexed_pairs


def test_semantic_similar_validation_k_too_large():
    resp = client.get(
        "/api/semantic/similar/phenomenon/1?k=101",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


def test_semantic_similar_validation_k_zero():
    resp = client.get(
        "/api/semantic/similar/phenomenon/1?k=0",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Self-Exclusion Test (Outcome A: service excludes self)
# ---------------------------------------------------------------------------

def test_semantic_similar_excludes_self(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 1, "Target Phenomenon")
    svc.index("phenomenon", 2, "Another Phenomenon")

    resp = client.get(
        "/api/semantic/similar/phenomenon/1",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    results = resp.json()
    # Confirm entity_id 1 with entity_type phenomenon is NOT in results
    phenom_ids = [r["entity_id"] for r in results if r["entity_type"] == "phenomenon"]
    assert 1 not in phenom_ids


# ---------------------------------------------------------------------------
# Read-Only Guarantee Tests
# ---------------------------------------------------------------------------

def test_semantic_search_does_not_create_domain_relation(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 1, "Phenom A")
    svc.index("phenomenon", 2, "Phenom B")

    rel_count_before = db.query(DomainRelation).count()

    client.post(
        "/api/semantic/search",
        json={"query": "Phenom"},
        headers=AUTH_HEADERS,
    )

    assert db.query(DomainRelation).count() == rel_count_before


def test_semantic_search_does_not_modify_canonical_entity(db):
    # Create canonical phenomenon via API
    resp = client.post(
        "/api/phenomena",
        json={"name": "Immutable Phenomenon", "description": "Original Description"},
        headers=AUTH_HEADERS,
    )
    p_id = resp.json()["id"]

    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index_canonical("phenomenon", p_id)

    client.post(
        "/api/semantic/search",
        json={"query": "Immutable"},
        headers=AUTH_HEADERS,
    )

    p = db.query(Phenomenon).filter(Phenomenon.id == p_id).first()
    assert p.name == "Immutable Phenomenon"
    assert p.description == "Original Description"


def test_semantic_search_does_not_auto_index(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 1, "Phenom A")

    index_count_before = db.query(SemanticIndexEntry).count()

    client.post(
        "/api/semantic/search",
        json={"query": "Unindexed Query Text"},
        headers=AUTH_HEADERS,
    )

    assert db.query(SemanticIndexEntry).count() == index_count_before


def test_semantic_similar_does_not_create_domain_relation(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 1, "Phenom A")
    svc.index("phenomenon", 2, "Phenom B")

    rel_count_before = db.query(DomainRelation).count()

    client.get(
        "/api/semantic/similar/phenomenon/1",
        headers=AUTH_HEADERS,
    )

    assert db.query(DomainRelation).count() == rel_count_before


def test_semantic_similar_does_not_auto_index(db):
    svc = SemanticSearchService(db, HashFallbackAdapter())
    svc.index("phenomenon", 1, "Phenom A")
    svc.index("phenomenon", 2, "Phenom B")

    index_count_before = db.query(SemanticIndexEntry).count()

    client.get(
        "/api/semantic/similar/phenomenon/1",
        headers=AUTH_HEADERS,
    )

    assert db.query(SemanticIndexEntry).count() == index_count_before
