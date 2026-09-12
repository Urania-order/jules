from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.database import SessionLocal
from smos.models.models import User, Event
from smos.services.memory_service import MemoryService


client = TestClient(app)


def test_search():
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        user = User(display_name="Search Test User")
        db.add(user)
        db.commit()
        db.refresh(user)

    service = MemoryService(db)
    import json
    service.process_event(Event(user_id=user.id, content={"text": "The capital of France is Paris"}))
    service.process_event(Event(user_id=user.id, content={"text": "Apple makes iPhones"}))
    service.process_event(Event(user_id=user.id, content={"text": "FastAPI is a modern web framework"}))

    user_id = user.id
    db.close()

    query_str = json.dumps({"text": "FastAPI is a modern web framework"})
    response = client.get(f"/memory/search?q={query_str}&user_id={user_id}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    # Top result should be the FastAPI memory node due to vector similarity of exact text matching query text
    assert "FastAPI" in results[0]["content"]


def test_cosine_similarity_helper():
    from smos.api.main import _cosine_similarity
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert _cosine_similarity([], [1.0, 0.0]) == 0.0
