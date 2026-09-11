from sqlalchemy.orm import Session
from smos.models.models import MemoryNode
from smos.models.ecology import ValueAssessment
from typing import List

class AttentionEcologyService:
    def __init__(self, db: Session):
        self.db = db

    def recommend_under_discovered(self, limit: int = 5) -> List[MemoryNode]:
        """
        Recommend knowledge that has high Potential but low current Energy/Popularity.
        The goal is to maximize collective learning rather than engagement.
        """
        # Join MemoryNode with ValueAssessment to find high potential nodes with low energy
        assessments = self.db.query(ValueAssessment).filter(
            ValueAssessment.knowledge_value < 0.3 # Low energy
        ).order_by(ValueAssessment.social_impact.desc()).limit(limit).all()

        node_ids = [a.node_id for a in assessments]
        return self.db.query(MemoryNode).filter(MemoryNode.id.in_(node_ids)).all()

    def redirect_attention(self, profile_id: int):
        """Redirect cosmonaut attention toward overlooked knowledge or forgotten recipes"""
        return {
            "action": "REDIRECT_ATTENTION",
            "targets": ["forgotten recipe #12", "dormant cluster 'Bio-Resonance'"],
            "reason": "Maximize collective learning potential"
        }

    def highlight_successful_recipes(self) -> List[MemoryNode]:
        """Identify recipes that have led to verified collective outcomes"""
        from smos.models.models import KnowledgeLifecycleState
        return self.db.query(MemoryNode).filter(
            MemoryNode.lifecycle_state == KnowledgeLifecycleState.COLLECTIVE_EXPERIENCE
        ).all()
