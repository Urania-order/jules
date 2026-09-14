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


def test_expire_aged_proposals(db):
    from datetime import datetime, timezone, timedelta
    from smos.models.consensus import Proposal
    from smos.services.cognitive_service import CognitiveService

    svc = CognitiveService(db)

    now = datetime.now(timezone.utc)

    # 1. Unexpired proposal (created 1 day ago, 7 day default TTL)
    p_fresh = Proposal(title="Fresh", description="Recent", status="PENDING", created_at=now - timedelta(days=1))
    # 2. Aged proposal without explicit expires_at (created 10 days ago, default 7 day TTL)
    p_aged = Proposal(title="Aged", description="Old", status="PENDING", created_at=now - timedelta(days=10))
    # 3. Explicitly expired proposal by expires_at (expires_at set in the past)
    p_exp_past = Proposal(title="Past Exp", description="Exp", status="PENDING", created_at=now - timedelta(days=1), expires_at=now - timedelta(hours=1))
    # 4. Explicitly non-expired proposal by expires_at (expires_at in the future)
    p_exp_future = Proposal(title="Future Exp", description="Exp", status="PENDING", created_at=now - timedelta(days=10), expires_at=now + timedelta(days=5))

    db.add_all([p_fresh, p_aged, p_exp_past, p_exp_future])
    db.commit()

    expired = svc.expire_aged_proposals(default_ttl_days=7)
    expired_ids = {p.id for p in expired}

    assert p_aged.id in expired_ids
    assert p_exp_past.id in expired_ids
    assert p_fresh.id not in expired_ids
    assert p_exp_future.id not in expired_ids

    db.refresh(p_aged)
    db.refresh(p_exp_past)
    db.refresh(p_fresh)
    db.refresh(p_exp_future)

    assert p_aged.status == "EXPIRED"
    assert p_exp_past.status == "EXPIRED"
    assert p_fresh.status == "PENDING"
    assert p_exp_future.status == "PENDING"


if __name__ == "__main__":
    test_cognitive_service()
