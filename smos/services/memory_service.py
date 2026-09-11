from sqlalchemy.orm import Session
from smos.models.models import Event, MemoryNode, Relation, MemoryType, RelationType, Timeline, TimelineType
from smos.services.embedding_service import embedding_service
from smos.core.security import secret_filter
import json

class MemoryService:
    def __init__(self, db: Session):
        self.db = db

    def process_event(self, event: Event):
        # Basic logic: transform clipboard/input events into MemoryNodes
        content_str = json.dumps(event.content)

        # Apply secret filtering
        content_str = secret_filter.filter(content_str)

        # Check if we have a default REAL timeline
        timeline = self.db.query(Timeline).filter(Timeline.type == TimelineType.REAL).first()
        if not timeline:
            timeline = Timeline(type=TimelineType.REAL, description="Default Reality")
            self.db.add(timeline)
            self.db.commit()
            self.db.refresh(timeline)

        node = MemoryNode(
            type=MemoryType.MEMORY,
            content=content_str,
            source={"event_id": event.id},
            owner_id=event.user_id,
            workspace_id=event.workspace_id,
            timeline_id=timeline.id,
            reality_level="REAL",
            embeddings=embedding_service.get_embedding(content_str)
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def create_relation(self, from_id: int, to_id: int, rel_type: RelationType):
        relation = Relation(from_node_id=from_id, to_node_id=to_id, type=rel_type)
        self.db.add(relation)
        self.db.commit()
        return relation
