from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.database import SessionLocal
from smos.models.models import User, MemoryNode


client = TestClient(app)


def test_api():
    response = client.get("/")
    assert response.status_code == 200

    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        user = User(display_name="Test User")
        db.add(user)
        db.commit()
        db.refresh(user)
    user_id = user.id

    event_data = {
        "user_id": user_id,
        "type": "clipboard",
        "content": {"text": "Hello Co-SMOS"},
    }
    response = client.post("/event", json=event_data)
    assert response.status_code == 200
    event_json = response.json()
    assert event_json["type"] == "clipboard"
    event_id = event_json["id"]

    # Verify that MemoryNode is created with 1536-dimensional embeddings
    memory_node = db.query(MemoryNode).filter(MemoryNode.source["event_id"] == event_id).first()
    if not memory_node:
        nodes = db.query(MemoryNode).all()
        memory_node = next((n for n in nodes if n.source and n.source.get("event_id") == event_id), None)

    assert memory_node is not None
    assert memory_node.embeddings is not None
    assert len(memory_node.embeddings) == 1536
    db.close()
