import pytest
from smos.services.commons_service import CommonsService
from smos.models.entities import Cosmonaut, Collaboration


def test_commons_service_find_collaborators(db):
    service = CommonsService(db)

    c1 = Cosmonaut(name="Alice CS Test", type="HUMAN", expertise=["AI", "Ethics"], reputation_score=0.9)
    c2 = Cosmonaut(name="Bob CS Test", type="AGENT", expertise=["AI", "Code"], reputation_score=0.8)
    c3 = Cosmonaut(name="Charlie CS Test", type="LLM", expertise=["Ethics"], reputation_score=0.7)

    db.add_all([c1, c2, c3])
    db.commit()

    try:
        collaborators = service.find_collaborators(c1.id, limit=2)
        assert len(collaborators) == 2
        collaborator_ids = [c.id for c in collaborators]
        assert c2.id in collaborator_ids
        assert c3.id in collaborator_ids
    finally:
        db.delete(c1)
        db.delete(c2)
        db.delete(c3)
        db.commit()


def test_commons_service_collaboration_lifecycle(db):
    service = CommonsService(db)

    c1 = Cosmonaut(name="Alice Lifecycle Test", type="HUMAN")
    c2 = Cosmonaut(name="Bob Lifecycle Test", type="AGENT")
    c3 = Cosmonaut(name="Eve Lifecycle Test", type="AGENT")
    db.add_all([c1, c2, c3])
    db.commit()

    try:
        initial_active = service.get_active_collaborations()

        # 1. Facilitate collaboration
        collab_info = service.facilitate_collaboration(c1.id, c2.id, "Develop eco algorithm")
        assert collab_info["status"] == "active"
        collab_id = collab_info["id"]

        # 2. Get active collaborations
        active_collabs = service.get_active_collaborations()
        assert len(active_collabs) == len(initial_active) + 1
        assert any(c.id == collab_id for c in active_collabs)

        # 3. Record outcome
        recorded = service.record_collaboration_outcome(
            collab_id,
            outcome="SUCCESS",
            metrics={"efficiency": 0.95, "impact": "high"}
        )
        assert recorded is not None
        assert recorded.status == "completed"
        assert recorded.outcome == "SUCCESS"
        assert recorded.metrics["efficiency"] == 0.95

        # Check active collaborations returns to initial length
        active_collabs = service.get_active_collaborations()
        assert len(active_collabs) == len(initial_active)

        # 4. Get collaboration history
        history_c1 = service.get_collaboration_history(c1.id)
        assert len(history_c1) == 1
        assert history_c1[0].id == collab_id

        history_c3 = service.get_collaboration_history(c3.id)
        assert len(history_c3) == 0
    finally:
        collab = db.get(Collaboration, collab_id) if 'collab_id' in locals() else None
        if collab:
            db.delete(collab)
        db.delete(c1)
        db.delete(c2)
        db.delete(c3)
        db.commit()


def test_commons_service_get_health_metrics(db):
    service = CommonsService(db)
    initial_metrics = service.get_health_metrics()

    c1 = Cosmonaut(name="C1 Health Test", type="HUMAN")
    c2 = Cosmonaut(name="C2 Health Test", type="AGENT")
    db.add_all([c1, c2])
    db.commit()

    try:
        collab_info = service.facilitate_collaboration(c1.id, c2.id, "Joint task")
        collab_id = collab_info["id"]

        metrics = service.get_health_metrics()
        assert metrics["cosmonaut_population"] == initial_metrics["cosmonaut_population"] + 2
        assert metrics["active_collaborations"] == initial_metrics["active_collaborations"] + 1
        assert "interaction_density" in metrics
    finally:
        collab = db.get(Collaboration, collab_id) if 'collab_id' in locals() else None
        if collab:
            db.delete(collab)
        db.delete(c1)
        db.delete(c2)
        db.commit()
