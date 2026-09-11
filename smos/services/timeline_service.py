from sqlalchemy.orm import Session
from smos.models.models import Timeline, TimelineType, MemoryNode, Relation
from smos.services.embedding_service import embedding_service
from typing import List

class TimelineService:
    def __init__(self, db: Session):
        self.db = db

    def fork_timeline(self, parent_id: int, description: str, t_type: TimelineType = TimelineType.COUNTERFACTUAL):
        timeline = Timeline(
            parent_timeline_id=parent_id,
            type=t_type,
            description=description
        )
        self.db.add(timeline)
        self.db.commit()
        self.db.refresh(timeline)
        return timeline

    def merge_timeline(self, source_id: int, target_id: int, node_ids: List[int] = None):
        """Transfer knowledge from source to target timeline"""
        query = self.db.query(MemoryNode).filter(MemoryNode.timeline_id == source_id)
        if node_ids:
            query = query.filter(MemoryNode.id.in_(node_ids))

        nodes = query.all()
        transferred = []
        for node in nodes:
            # Create a copy in the target timeline
            new_node = MemoryNode(
                type=node.type,
                content=node.content,
                source=node.source,
                embeddings=node.embeddings,
                owner_id=node.owner_id,
                workspace_id=node.workspace_id,
                timeline_id=target_id,
                reality_level="REAL" if self.db.query(Timeline).get(target_id).type == TimelineType.REAL else "COUNTERFACTUAL"
            )
            self.db.add(new_node)
            transferred.append(new_node)

        self.db.commit()
        return transferred

    def compare_timelines(self, id_a: int, id_b: int):
        nodes_a = self.db.query(MemoryNode).filter(MemoryNode.timeline_id == id_a).all()
        nodes_b = self.db.query(MemoryNode).filter(MemoryNode.timeline_id == id_b).all()

        content_a = {n.content for n in nodes_a}
        content_b = {n.content for n in nodes_b}

        shared = content_a.intersection(content_b)
        diff_a = content_a - content_b
        diff_b = content_b - content_a

        return {
            "shared_count": len(shared),
            "unique_to_a": list(diff_a),
            "unique_to_b": list(diff_b)
        }
