from smos.core.database import SessionLocal
from smos.models.models import User, Timeline, TimelineType
from smos.services.counterfactual_engine import CounterfactualEngine


def test_counterfactual():
    db = SessionLocal()

    user = db.query(User).first()
    if not user:
        user = User(display_name="Test User")
        db.add(user)
        db.commit()
        db.refresh(user)

    main_timeline = db.query(Timeline).filter(Timeline.type == TimelineType.REAL).first()
    if not main_timeline:
        main_timeline = Timeline(type=TimelineType.REAL, description="Main Timeline")
        db.add(main_timeline)
        db.commit()
        db.refresh(main_timeline)

    engine = CounterfactualEngine(db)

    alt_timeline = engine.branch_timeline(
        parent_id=main_timeline.id,
        description="What if we used Neo4j?",
    )
    assert alt_timeline.parent_timeline_id == main_timeline.id

    cf_memory = engine.create_counterfactual_memory(
        timeline_id=alt_timeline.id,
        content="Neo4j provides better graph traversal for semantic memory.",
        owner_id=user.id,
    )
    assert cf_memory.timeline_id == alt_timeline.id
    assert cf_memory.reality_level == "COUNTERFACTUAL"

    db.close()


if __name__ == "__main__":
    test_counterfactual()
