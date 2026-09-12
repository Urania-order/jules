from typing import List, Optional
from sqlalchemy.orm import Session
from smos.models.models import Event, MemoryNode, Relation, MemoryType, RelationType, Timeline, TimelineType
from smos.services.embedding_service import embedding_service
from smos.core.security import secret_filter
import json


class MemoryService:
    def __init__(self, db: Session):
        self.db = db

    def _get_timeline(self) -> Timeline:
        timeline = self.db.query(Timeline).filter(Timeline.type == TimelineType.REAL).first()
        if not timeline:
            timeline = Timeline(type=TimelineType.REAL, description="Default Reality")
            self.db.add(timeline)
            self.db.commit()
            self.db.refresh(timeline)
        return timeline

    def _prepare_content_and_embedding_text(self, content: Optional[object]) -> tuple[str, str]:
        if content is None:
            content_str = "null"
            embedding_text = ""
        elif isinstance(content, str):
            content_str = secret_filter.filter(content)
            embedding_text = content_str if content_str.strip() else ""
        else:
            content_str = json.dumps(content)
            content_str = secret_filter.filter(content_str)
            embedding_text = content_str if (content_str and content_str != "null") else ""

        return content_str, embedding_text

    def process_event(self, event: Event) -> MemoryNode:
        content_str, embedding_text = self._prepare_content_and_embedding_text(event.content)
        timeline = self._get_timeline()

        embeddings = embedding_service.get_embedding(embedding_text)

        node = MemoryNode(
            type=MemoryType.MEMORY,
            content=content_str,
            source={"event_id": event.id},
            owner_id=event.user_id,
            workspace_id=event.workspace_id,
            timeline_id=timeline.id,
            reality_level="REAL",
            embeddings=embeddings,
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def process_events_batch(self, events: List[Event]) -> List[MemoryNode]:
        if not events:
            return []

        timeline = self._get_timeline()

        contents = []
        texts_for_embedding = []
        for event in events:
            content_str, emb_text = self._prepare_content_and_embedding_text(event.content)
            contents.append(content_str)
            texts_for_embedding.append(emb_text)

        embeddings_list = embedding_service.get_embeddings_batch(texts_for_embedding)

        nodes = []
        for event, content_str, embeddings in zip(events, contents, embeddings_list):
            node = MemoryNode(
                type=MemoryType.MEMORY,
                content=content_str,
                source={"event_id": event.id},
                owner_id=event.user_id,
                workspace_id=event.workspace_id,
                timeline_id=timeline.id,
                reality_level="REAL",
                embeddings=embeddings,
            )
            self.db.add(node)
            nodes.append(node)

        self.db.commit()
        for node in nodes:
            self.db.refresh(node)
        return nodes

    def create_relation(self, from_id: int, to_id: int, rel_type: RelationType):
        relation = Relation(from_node_id=from_id, to_node_id=to_id, type=rel_type)
        self.db.add(relation)
        self.db.commit()
        return relation
