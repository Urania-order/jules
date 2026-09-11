from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.database import SessionLocal
from smos.models.models import User


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
    db.close()

    event_data = {
        "user_id": user_id,
        "type": "clipboard",
        "content": {"text": "Hello Co-SMOS"},
    }
    response = client.post("/event", json=event_data)
    assert response.status_code == 200
    assert response.json()["type"] == "clipboard"
