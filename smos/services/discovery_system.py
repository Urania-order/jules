from sqlalchemy.orm import Session
from smos.models.epistemic import IntellectualCluster, ClusterRelation
from smos.models.discovery import LostKnowledge, Hypothesis
from smos.core.interfaces import Observable
from typing import List, Dict, Any

class DiscoverySystem(Observable):
    def __init__(self, db: Session):
        self.db = db

    def backward_discovery(self, outcome_node_id: int) -> List[Dict[str, Any]]:
        """Reverse causal search"""
        return [
            {"node_id": 101, "type": "Recipe", "confidence": 0.85, "reason": "Structural similarity"}
        ]

    def find_analogies(self, cluster_id: int):
        relations = self.db.query(ClusterRelation).filter(
            (ClusterRelation.source_cluster_id == cluster_id) |
            (ClusterRelation.target_cluster_id == cluster_id)
        ).all()
        return [r.interaction_type for r in relations]

    # Observable interface
    def get_health_metrics(self) -> Dict[str, Any]:
        hypotheses_count = self.db.query(Hypothesis).count()
        return {"active_hypotheses": hypotheses_count}

    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        return []
