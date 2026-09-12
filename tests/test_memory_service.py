from smos.core.database import SessionLocal
from smos.models.models import Event, User, MemoryNode, Relation
from smos.services.memory_service import MemoryService
from smos.services.embedding_service import embedding_service
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
    assert node.embeddings is not None
    assert isinstance(node.embeddings, list)
    assert len(node.embeddings) == 1536

    # Create another node and link them
    event2 = Event(user_id=user.id, type="input", content={"text": "Co-SMOS is cool"})
    db.add(event2)
    db.commit()
    node2 = service.process_event(event2)

    assert node2.embeddings is not None
    assert isinstance(node2.embeddings, list)
    assert len(node2.embeddings) == 1536

    rel = service.create_relation(node.id, node2.id, "RELATED_TO")
    print(f"Created Relation: {rel.from_node_id} -> {rel.to_node_id} ({rel.type})")
    assert rel.from_node_id == node.id
    assert rel.to_node_id == node2.id

    db.close()


def test_different_events_different_embeddings():
    db = SessionLocal()
    user = User(display_name="Embedding Test User")
    db.add(user)
    db.commit()
    db.refresh(user)

    event1 = Event(user_id=user.id, type="input", content={"text": "First unique memory topic"})
    event2 = Event(user_id=user.id, type="input", content={"text": "Second completely distinct topic"})
    db.add_all([event1, event2])
    db.commit()

    service = MemoryService(db)
    node1 = service.process_event(event1)
    node2 = service.process_event(event2)

    assert node1.embeddings is not None
    assert node2.embeddings is not None
    assert len(node1.embeddings) == 1536
    assert len(node2.embeddings) == 1536
    assert node1.embeddings != node2.embeddings

    db.close()


def test_empty_or_none_content_fallback():
    db = SessionLocal()
    user = User(display_name="Fallback Test User")
    db.add(user)
    db.commit()
    db.refresh(user)

    event_none = Event(user_id=user.id, type="input", content=None)
    event_empty = Event(user_id=user.id, type="input", content="")
    db.add_all([event_none, event_empty])
    db.commit()

    service = MemoryService(db)
    node_none = service.process_event(event_none)
    node_empty = service.process_event(event_empty)

    expected_fallback_embedding = embedding_service.get_embedding("")

    assert len(node_none.embeddings) == 1536
    assert len(node_empty.embeddings) == 1536
    assert node_none.embeddings == expected_fallback_embedding
    assert node_empty.embeddings == expected_fallback_embedding

    db.close()


def test_process_events_batch():
    db = SessionLocal()
    user = User(display_name="Batch Test User")
    db.add(user)
    db.commit()
    db.refresh(user)

    event1 = Event(user_id=user.id, type="input", content={"text": "Batch Event 1"})
    event2 = Event(user_id=user.id, type="input", content={"text": "Batch Event 2"})
    db.add_all([event1, event2])
    db.commit()

    service = MemoryService(db)
    nodes = service.process_events_batch([event1, event2])

    assert len(nodes) == 2
    assert len(nodes[0].embeddings) == 1536
    assert len(nodes[1].embeddings) == 1536
    assert nodes[0].embeddings != nodes[1].embeddings

    # Empty batch test
    assert service.process_events_batch([]) == []

    db.close()


if __name__ == "__main__":
    test_memory_service()
    test_different_events_different_embeddings()
    test_empty_or_none_content_fallback()
    test_process_events_batch()
