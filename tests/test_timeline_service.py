from smos.core.database import SessionLocal
from smos.models.models import Timeline, TimelineType, User, Event, MemoryNode
from smos.services.timeline_service import TimelineService
from smos.services.memory_service import MemoryService
import json

def test_timeline_service():
    db = SessionLocal()

    user = User(display_name="Timeline User")
    db.add(user)
    db.commit()

    main_tl = Timeline(type=TimelineType.REAL, description="Main")
    db.add(main_tl)
    db.commit()

    svc = TimelineService(db)
    mem_svc = MemoryService(db)

    # Fork
    forked = svc.fork_timeline(main_tl.id, "Simulation A", TimelineType.SIMULATION)

    # Add memory to fork
    mem_svc.process_event(Event(user_id=user.id, type="input", content={"text": "Exclusive to Fork"}))
    node = db.query(MemoryNode).order_by(MemoryNode.id.desc()).first()
    node.timeline_id = forked.id
    db.commit()

    # Compare
    diff = svc.compare_timelines(main_tl.id, forked.id)
    print(f"Diff: {diff}")
    assert any("Exclusive to Fork" in str(u) for u in diff["unique_to_b"])

    # Merge
    merged = svc.merge_timeline(forked.id, main_tl.id)
    print(f"Merged {len(merged)} nodes")
    assert len(merged) > 0

    db.close()

if __name__ == "__main__":
    test_timeline_service()
