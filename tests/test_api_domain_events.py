import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from smos.api.main import app
from smos.core.database import SessionLocal
from smos.models.domain_event import DomainEvent, DomainEventType
from smos.services.domain_event_service import DomainEventService

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


@pytest.fixture(autouse=True)
def clean_events():
    db: Session = SessionLocal()
    try:
        db.query(DomainEvent).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def sample_events():
    db: Session = SessionLocal()
    try:
        svc = DomainEventService(db)
        e1 = svc.record(
            entity_type="phenomenon",
            entity_id=1,
            event_type=DomainEventType.CREATED,
            actor_type="user",
            actor_id=10,
            changes={"name": "Atmospheric Resonance"},
        )
        e2 = svc.record(
            entity_type="phenomenon",
            entity_id=1,
            event_type=DomainEventType.UPDATED,
            actor_type="cosmonaut",
            actor_id=42,
            changes={"epistemic_status": {"old": "OBSERVED", "new": "INFERRED"}},
        )
        e3 = svc.record(
            entity_type="context",
            entity_id=2,
            event_type=DomainEventType.CREATED,
            changes={"name": "Ionosphere Layer"},
        )
        return [e1.id, e2.id, e3.id]
    finally:
        db.close()


def test_list_domain_events_endpoint(sample_events):
    resp = client.get("/api/domain-events")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) == 3
    # Recent first ordering in list_recent()
    assert data["events"][0]["entity_type"] == "context"
    assert data["events"][0]["entity_id"] == 2


def test_list_domain_events_with_limit(sample_events):
    resp = client.get("/api/domain-events?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 2


def test_list_for_entity_endpoint(sample_events):
    resp = client.get("/api/domain-events/phenomenon/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "phenomenon"
    assert data["entity_id"] == 1
    assert len(data["events"]) == 2
    # Ascending order in list_for_entity()
    assert data["events"][0]["event_type"] == "CREATED"
    assert data["events"][1]["event_type"] == "UPDATED"


def test_list_for_entity_404_or_empty_for_unknown():
    resp = client.get("/api/domain-events/phenomenon/999999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "phenomenon"
    assert data["entity_id"] == 999999
    assert data["events"] == []


def test_reconstruct_endpoint(sample_events):
    resp = client.post(
        "/api/domain-events/reconstruct/phenomenon/1",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "phenomenon"
    assert data["entity_id"] == 1
    assert data["event_count"] == 2
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert "reconstruction_note" in data
    assert len(data["events"]) == 2


def test_reconstruct_returns_events_in_order(sample_events):
    resp = client.post(
        "/api/domain-events/reconstruct/phenomenon/1",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert events[0]["event_type"] == "CREATED"
    assert events[1]["event_type"] == "UPDATED"


def test_reconstruct_empty_for_unknown_entity():
    resp = client.post(
        "/api/domain-events/reconstruct/unknown_type/999999",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "unknown_type"
    assert data["entity_id"] == 999999
    assert data["event_count"] == 0
    assert data["created_at"] is None
    assert data["updated_at"] is None
    assert data["events"] == []


def test_no_create_domain_event_endpoint():
    resp = client.post("/api/domain-events", json={"entity_type": "phenomenon", "entity_id": 1}, headers=AUTH_HEADERS)
    assert resp.status_code == 405


def test_no_delete_domain_event_endpoint():
    resp = client.delete("/api/domain-events", headers=AUTH_HEADERS)
    assert resp.status_code == 405

    resp2 = client.delete("/api/domain-events/phenomenon/1", headers=AUTH_HEADERS)
    assert resp2.status_code == 405


def test_domain_events_append_only_via_api():
    resp_put = client.put("/api/domain-events/phenomenon/1", json={"actor_type": "hacker"}, headers=AUTH_HEADERS)
    assert resp_put.status_code == 405

    resp_patch = client.patch("/api/domain-events/phenomenon/1", json={"actor_type": "hacker"}, headers=AUTH_HEADERS)
    assert resp_patch.status_code == 405


def test_existing_domain_event_service_unchanged(sample_events):
    db: Session = SessionLocal()
    try:
        svc = DomainEventService(db)
        fetched = svc.get(sample_events[0])
        assert fetched is not None
        assert fetched.entity_type == "phenomenon"
        assert fetched.entity_id == 1

        recent = svc.list_recent()
        assert len(recent) == 3

        reconstruction = svc.reconstruct_entity("phenomenon", 1)
        assert reconstruction["event_count"] == 2
    finally:
        db.close()
