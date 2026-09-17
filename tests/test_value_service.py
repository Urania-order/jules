from smos.core.database import SessionLocal
from smos.models.models import MemoryNode, User, Timeline, TimelineType
from smos.services.value_ecology_service import ValueEcologyService

def test_value_service():
    db = SessionLocal()

    user = User(display_name="Eco User")
    db.add(user)
    tl = Timeline(type=TimelineType.REAL)
    db.add(tl)
    db.commit()
    node = MemoryNode(content="Sustainable Cooling System", owner_id=user.id, timeline_id=tl.id)
    db.add(node)
    db.commit()

    svc = ValueEcologyService(db)
    assessment = svc.assess_knowledge_value(node.id, 0.9, 0.8)
    assert abs(assessment.knowledge_value - 0.72) < 1e-9

    db.close()

if __name__ == "__main__":
    test_value_service()
