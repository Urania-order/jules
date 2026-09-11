from smos.core.database import SessionLocal
from smos.models.models import Event, User, MemoryNode, Relation
from smos.services.memory_service import MemoryService
import json

def test_memory_service():
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        user = User(display_name="Service Test User")
        db.add(user)
        db.commit()
        db.refresh(user)

    event = Event(user_id=user.id, type="input", content={"text": "Learning about SMOS"})
    db.add(event)
    db.commit()
    db.refresh(event)

    service = MemoryService(db)
    node = service.process_event(event)

    print(f"Created Node: {node.id}, content: {node.content}")
    assert node.owner_id == user.id
    assert "Learning about SMOS" in node.content

    # Create another node and link them
    event2 = Event(user_id=user.id, type="input", content={"text": "Co-SMOS is cool"})
    db.add(event2)
    db.commit()
    node2 = service.process_event(event2)

    rel = service.create_relation(node.id, node2.id, "RELATED_TO")
    print(f"Created Relation: {rel.from_node_id} -> {rel.to_node_id} ({rel.type})")
    assert rel.from_node_id == node.id
    assert rel.to_node_id == node2.id

    db.close()

if __name__ == "__main__":
    test_memory_service()
