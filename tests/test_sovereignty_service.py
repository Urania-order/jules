from smos.core.database import SessionLocal
from smos.models.models import MemoryNode, User, Timeline, TimelineType
from smos.models.entities import Cosmonaut
from smos.services.sovereignty_service import SovereigntyService

def test_sovereignty_service():
    db = SessionLocal()
    # Import
    from smos.models.models import User, MemoryNode
    from smos.models.entities import Cosmonaut

    u = User(display_name="Creator")
    c = Cosmonaut(name="AI Helper", type="AGENT")
    db.add_all([u, c])
    tl = Timeline(type=TimelineType.REAL)
    db.add(tl)
    db.commit()
    node = MemoryNode(content="Original Idea", owner_id=u.id, timeline_id=tl.id)
    db.add(node)
    db.commit()

    svc = SovereigntyService(db)
    rec = svc.record_provenance(node.id, c.id, ["observation_log_1"])
    assert rec.created_by_id == c.id

    principles = svc.check_sovereignty_principles()
    assert principles["preserve_plurality"] is True

    db.close()

if __name__ == "__main__":
    test_sovereignty_service()
