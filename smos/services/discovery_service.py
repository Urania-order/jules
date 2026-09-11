from sqlalchemy.orm import Session
from smos.models.epistemic import IntellectualCluster, ClusterRelation
from typing import List, Dict, Any

class DiscoveryService:
    def __init__(self, db: Session):
        self.db = db

    def create_cluster(self, name: str, domains: List[str]):
        cluster = IntellectualCluster(name=name, domains=domains)
        self.db.add(cluster)
        self.db.commit()
        self.db.refresh(cluster)
        return cluster

    def link_clusters(self, source_id: int, target_id: int, interaction: str):
        relation = ClusterRelation(
            source_cluster_id=source_id,
            target_cluster_id=target_id,
            interaction_type=interaction
        )
        self.db.add(relation)
        self.db.commit()
        return relation

    def find_analogies(self, cluster_id: int):
        # In a real system, this would use semantic similarity of recipes/nodes
        # Mock logic: return neighbors
        relations = self.db.query(ClusterRelation).filter(
            (ClusterRelation.source_cluster_id == cluster_id) |
            (ClusterRelation.target_cluster_id == cluster_id)
        ).all()
        return [r.interaction_type for r in relations]
