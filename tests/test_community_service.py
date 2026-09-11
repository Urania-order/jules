from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut
from smos.services.community_service import CommunityService

def test_community_service():
    db = SessionLocal()

    c1 = Cosmonaut(name="C1", type="HUMAN")
    c2 = Cosmonaut(name="C2", type="AGENT")
    db.add_all([c1, c2])
    db.commit()

    svc = CommunityService(db)
    con = svc.create_constellation("Explore Co-SMOS", [c1.id, c2.id])
    assert con.mission == "Explore Co-SMOS"
    assert c1.id in con.members

    db.close()

if __name__ == "__main__":
    test_community_service()
