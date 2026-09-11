from smos.core.database import SessionLocal
from smos.models.discovery import Hypothesis
from smos.models.models import User
from smos.services.research_service import ResearchService

def test_research_service():
    db = SessionLocal()
    # Import
    from smos.models.discovery import Hypothesis
    from smos.models.models import User

    h = Hypothesis(claim="GPU demand increases cooling needs")
    u = User(display_name="Sponsor Corp")
    db.add_all([h, u])
    db.commit()

    svc = ResearchService(db)
    portal = svc.open_portal(h.id)
    assert portal.status == "OPEN"

    svc.sponsor_research(portal.id, u.id, 5000.0)
    assert portal.budget == 5000.0
    assert portal.status == "FUNDED"

    db.close()

if __name__ == "__main__":
    test_research_service()
