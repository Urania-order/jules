from smos.core.database import SessionLocal
from smos.models.models import User, Timeline, TimelineType
from smos.services.cognitive_service import CognitiveService


def test_cognitive_service():
    db = SessionLocal()

    user = db.query(User).first()
    if not user:
        user = User(display_name="Test User")
        db.add(user)
        db.commit()
        db.refresh(user)

    timeline = db.query(Timeline).first()
    if not timeline:
        timeline = Timeline(type=TimelineType.REAL, description="Main Timeline")
        db.add(timeline)
        db.commit()
        db.refresh(timeline)

    svc = CognitiveService(db)

    session = svc.create_session(
        workspace_id=None,
        topic="AI Architecture",
        timeline_id=timeline.id,
        participants=[user.id],
    )
    assert session.topic == "AI Architecture"

    thought = svc.add_thought(
        user.id, timeline.id, "We should use a graph database."
    )
    assert thought.author_id == user.id
    assert "graph" in thought.content

    db.close()


if __name__ == "__main__":
    test_cognitive_service()
