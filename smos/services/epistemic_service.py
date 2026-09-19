from sqlalchemy.orm import Session
from smos.models.epistemic import EpistemicLayer, IntellectualCluster
from smos.models.models import MemoryNode, EpistemicStatus
from typing import List, Optional, Union

class EpistemicService:
    def __init__(self, db: Session):
        self.db = db

    def create_layer(self, name: str, confidence: float, evidence_type: str):
        layer = EpistemicLayer(name=name, confidence_level=confidence, evidence_type=evidence_type)
        self.db.add(layer)
        self.db.commit()
        self.db.refresh(layer)
        return layer

    def assign_to_layer(self, node_id: int, layer_id: int, status: Optional[Union[str, EpistemicStatus]] = None):
        node = self.db.get(MemoryNode, node_id)
        if node:
            if not node.layer_ids:
                node.layer_ids = []
            if layer_id not in node.layer_ids:
                # SQLAlchemy JSON mutation tracking
                new_layers = list(node.layer_ids)
                new_layers.append(layer_id)
                node.layer_ids = new_layers

            if status:
                if isinstance(status, EpistemicStatus):
                    node.epistemic_status = status
                else:
                    try:
                        node.epistemic_status = EpistemicStatus.from_str(status)
                    except ValueError:
                        node.epistemic_status = status

            self.db.commit()
        return node

    def update_node_status(self, node_id: int, status: Union[str, EpistemicStatus]) -> Optional[MemoryNode]:
        """Update the epistemic status of a MemoryNode."""
        node = self.db.get(MemoryNode, node_id)
        if not node:
            return None
        if isinstance(status, EpistemicStatus):
            node.epistemic_status = status
        else:
            try:
                node.epistemic_status = EpistemicStatus.from_str(status)
            except ValueError:
                node.epistemic_status = status
        self.db.commit()
        self.db.refresh(node)
        return node

    def get_nodes_by_status(self, status: Union[str, EpistemicStatus]) -> List[MemoryNode]:
        """Retrieve memory nodes by epistemic status."""
        parsed_status = EpistemicStatus.from_str(status) if isinstance(status, str) else status
        return self.db.query(MemoryNode).filter(MemoryNode.epistemic_status == parsed_status).all()

    def get_beyond_consensus_nodes(self):
        return self.get_nodes_by_status(EpistemicStatus.BEYOND_ALL_CONSENSUS)
