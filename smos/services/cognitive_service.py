from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from smos.models.cognitive import CognitiveSession, Thought
from smos.models.consensus import Proposal, Vote

class CognitiveService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, workspace_id: int, topic: str, timeline_id: int, participants: List[int]):
        session = CognitiveSession(
            workspace_id=workspace_id,
            topic=topic,
            active_timeline_id=timeline_id,
            participants=participants
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_thought(self, author_id: int, timeline_id: int, content: str, references: List[int] = None):
        thought = Thought(
            author_id=author_id,
            timeline_id=timeline_id,
            content=content,
            references=references or []
        )
        self.db.add(thought)
        self.db.commit()
        self.db.refresh(thought)
        return thought

    def calculate_consensus(self, proposal_id: int):
        votes = self.db.query(Vote).filter(Vote.proposal_id == proposal_id).all()
        if not votes:
            return 0.0

        approvals = sum(1 for v in votes if v.approve)
        return approvals / len(votes)

    def expire_aged_proposals(self, default_ttl_days: Optional[int] = 7) -> List[Proposal]:
        """Check all pending proposals and transition those past their expires_at or age threshold to EXPIRED."""
        now = datetime.now(timezone.utc)
        pending_proposals = self.db.query(Proposal).filter(Proposal.status == "PENDING").all()
        expired = []

        for p in pending_proposals:
            is_expired = False
            if p.expires_at is not None:
                p_exp = p.expires_at
                if p_exp.tzinfo is None:
                    p_exp = p_exp.replace(tzinfo=timezone.utc)
                if now >= p_exp:
                    is_expired = True
            elif default_ttl_days is not None and p.created_at is not None:
                p_created = p.created_at
                if p_created.tzinfo is None:
                    p_created = p_created.replace(tzinfo=timezone.utc)
                if now >= p_created + timedelta(days=default_ttl_days):
                    is_expired = True

            if is_expired:
                p.status = "EXPIRED"
                expired.append(p)

        if expired:
            self.db.commit()

        return expired
