from sqlalchemy.orm import Session
from smos.models.cognitive import CognitiveSession, Thought
from smos.models.consensus import Proposal, Vote
from typing import List

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
