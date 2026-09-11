from sqlalchemy.orm import Session
from smos.models.models import Timeline, TimelineType, MemoryNode, MemoryType, Relation, RelationType
from smos.services.embedding_service import embedding_service
import json

class CounterfactualEngine:
    def __init__(self, db: Session):
        self.db = db

    def branch_timeline(self, parent_id: int, description: str, timeline_type: TimelineType = TimelineType.COUNTERFACTUAL):
        timeline = Timeline(
            parent_timeline_id=parent_id,
            type=timeline_type,
            description=description,
            probability=0.5 # Default probability for simulations
        )
        self.db.add(timeline)
        self.db.commit()
        self.db.refresh(timeline)
        return timeline

    def create_counterfactual_memory(self, timeline_id: int, content: str, owner_id: int):
        node = MemoryNode(
            type=MemoryType.MEMORY,
            content=content,
            timeline_id=timeline_id,
            reality_level="COUNTERFACTUAL",
            owner_id=owner_id,
            embeddings=embedding_service.get_embedding(content)
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node
