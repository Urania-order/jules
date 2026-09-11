from smos.core.database import SessionLocal
from smos.models.models import MemoryNode, User, Timeline, TimelineType
from smos.services.impact_service import ImpactService

def test_impact_service():
    db = SessionLocal()

    user = User(display_name="Impact User")
    db.add(user)
    db.commit()
    tl = Timeline(type=TimelineType.REAL)
    db.add(tl)
    db.commit()
    node = MemoryNode(content="Herbology knowledge", owner_id=user.id, timeline_id=tl.id)
    db.add(node)
    db.commit()

    svc = ImpactService(db)
    impact = svc.record_impact(node.id, "Health", "HEALTH_IMPACT", 0.8)
    assert impact.target_domain == "Health"

    activation = svc.activate_knowledge(node.id, "Drank chamomile tea")
    assert activation.usage_count == 1

    decay = svc.calculate_decay(node.id)
    assert decay >= 0.0

    db.close()

if __name__ == "__main__":
    test_impact_service()
