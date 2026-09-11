from smos.core.database import SessionLocal
from smos.services.lost_knowledge_service import LostKnowledgeService

def test_lost_knowledge_service():
    db = SessionLocal()
    # Import
    from smos.models.discovery import LostKnowledge, Hypothesis

    svc = LostKnowledgeService(db)
    lk = svc.record_lost_knowledge(["Scythian Binoculars"], ["Function unknown"])
    assert lk.id is not None

    h = svc.add_hypothesis(lk.id, "Used for astronomical observation", 0.6)
    assert h.lost_knowledge_id == lk.id

    db.close()

if __name__ == "__main__":
    test_lost_knowledge_service()
