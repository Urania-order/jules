from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut
from smos.services.economy_service import EconomyService

def test_economy_service():
    db = SessionLocal()
    # Import
    from smos.models.entities import Cosmonaut

    c = Cosmonaut(name="Valued Agent", type="AGENT")
    db.add(c)
    db.commit()

    svc = EconomyService(db)
    svc.issue_reputation_credits(c.id, 100.0, "Provided valuable recipe")
    svc.issue_reputation_credits(c.id, 50.0, "Verified hypothesis")

    balance = svc.calculate_total_balance(c.id)
    assert balance == 150.0

    db.close()

if __name__ == "__main__":
    test_economy_service()
