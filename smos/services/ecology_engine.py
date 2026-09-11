from sqlalchemy.orm import Session
from smos.models.epistemic import IntellectualCluster, ClusterRelation
from smos.models.models import MemoryNode
from smos.models.ecology import KnowledgeActivation
from smos.core.interfaces import Observable
from typing import List, Dict, Any
from datetime import datetime, timezone

class EcologyEngine(Observable):
    def __init__(self, db: Session):
        self.db = db

    def propagate_knowledge(self, node_id: int):
        """Propagate knowledge through resonance and cluster interaction"""
        node = self.db.query(MemoryNode).get(node_id)
        if not node:
            return

        for cluster_id in node.cluster_ids:
            cluster = self.db.query(IntellectualCluster).get(cluster_id)
            if cluster:
                cluster.knowledge_inflow += 0.1
                cluster.resonance = min(1.0, cluster.resonance + 0.05)
                cluster.activity = min(1.0, cluster.activity + 0.1)

        self.db.commit()

    def pollinate(self, source_cluster_id: int):
        """Find related clusters and suggest knowledge transfer"""
        relations = self.db.query(ClusterRelation).filter(
            ClusterRelation.source_cluster_id == source_cluster_id
        ).all()

        suggestions = []
        for rel in relations:
            suggestions.append({
                "target_cluster_id": rel.target_cluster_id,
                "action": "TRANSFER_PATTERNS",
                "reason": f"Active link via {rel.interaction_type}"
            })
        return suggestions

    def activate_resonance(self, node_id: int):
        """Increase resonance based on successful application/experiment"""
        activation = self.db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id == node_id).first()
        if activation:
            activation.usage_count += 1
            activation.last_reinforced_at = datetime.now(timezone.utc)
            self.db.commit()

    # Observable interface
    def get_health_metrics(self) -> Dict[str, Any]:
        clusters = self.db.query(IntellectualCluster).all()
        if not clusters:
            return {"health": 1.0, "active_clusters": 0}

        avg_health = sum(c.health for c in clusters) / len(clusters)
        return {
            "health": avg_health,
            "active_clusters": len(clusters),
            "total_resonance": sum(c.resonance for c in clusters)
        }

    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        # Mock summary for now
        return [{"event": "Cluster formation", "timestamp": str(datetime.now(timezone.utc))}]
