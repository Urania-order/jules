from sqlalchemy.orm import Session
from smos.models.epistemic import EpistemicLayer, IntellectualCluster
from smos.models.models import MemoryNode
from typing import List

class EpistemicService:
    def __init__(self, db: Session):
        self.db = db

    def create_layer(self, name: str, confidence: float, evidence_type: str):
        layer = EpistemicLayer(name=name, confidence_level=confidence, evidence_type=evidence_type)
        self.db.add(layer)
        self.db.commit()
        self.db.refresh(layer)
        return layer

    def assign_to_layer(self, node_id: int, layer_id: int, status: str = None):
        node = self.db.query(MemoryNode).get(node_id)
        if node:
            if not node.layer_ids:
                node.layer_ids = []
            if layer_id not in node.layer_ids:
                # SQLAlchemy JSON mutation tracking
                new_layers = list(node.layer_ids)
                new_layers.append(layer_id)
                node.layer_ids = new_layers

            if status:
                node.epistemic_status = status

            self.db.commit()
        return node

    def get_beyond_consensus_nodes(self):
        return self.db.query(MemoryNode).filter(MemoryNode.epistemic_status == "Beyond All Consensus").all()
