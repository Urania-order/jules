from smos.core.database import SessionLocal
from smos.models.models import User
from smos.services.twin_service import TwinService

def test_twin_service():
    db = SessionLocal()
    user = db.query(User).first()

    svc = TwinService(db)
    twin = svc.create_twin(user.id, ["Build Co-SMOS"], {"privacy": "high"})
    assert twin.owner_id == user.id

    response = svc.negotiate(twin.id, 999, {"goal": "Share memory nodes"})
    assert response["status"] == "ACCEPTED"

    db.close()

if __name__ == "__main__":
    test_twin_service()
