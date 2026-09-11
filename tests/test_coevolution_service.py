from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut
from smos.models.models import User
from smos.services.coevolution_service import CoevolutionService

def test_coevolution_service():
    db = SessionLocal()

    agent = Cosmonaut(name="AI Teacher", type="AGENT")
    user = User(display_name="Student")
    db.add_all([agent, user])
    db.commit()

    svc = CoevolutionService(db)
    val = svc.validate_understanding(agent.id, user.id, "History is static", "It is dynamic")
    assert "Revised" in val.revised_interpretation

    test = svc.run_comprehension_test("A", "A")
    assert test.similarity_score > 0.5

    db.close()

if __name__ == "__main__":
    test_coevolution_service()
