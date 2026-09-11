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
    service.process_event(Event(user_id=user.id, content={"text": "The capital of France is Paris"}))
    service.process_event(Event(user_id=user.id, content={"text": "Apple makes iPhones"}))
    service.process_event(Event(user_id=user.id, content={"text": "FastAPI is a modern web framework"}))

    user_id = user.id
    db.close()

    response = client.get(f"/memory/search?q=FastAPI framework&user_id={user_id}")
    assert response.status_code == 200
