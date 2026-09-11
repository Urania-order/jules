from smos.core.database import SessionLocal
from smos.models.models import MemoryNode, User, Timeline, TimelineType
from smos.services.value_service import ValueService

def test_value_service():
    db = SessionLocal()
    # Import
    from smos.models.models import User, MemoryNode

    user = User(display_name="Eco User")
    db.add(user)
    tl = Timeline(type=TimelineType.REAL)
    db.add(tl)
    db.commit()
    node = MemoryNode(content="Sustainable Cooling System", owner_id=user.id, timeline_id=tl.id)
    db.add(node)
    db.commit()

    svc = ValueService(db)
    assessment = svc.assess_knowledge_value(node.id, 0.9, 0.1)
    assert assessment.knowledge_value > 0.5

    is_meaningful = svc.verify_human_meaning_principle(assessment.id)
    assert is_meaningful is True

    db.close()

if __name__ == "__main__":
    test_value_service()
