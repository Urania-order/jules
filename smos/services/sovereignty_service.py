from sqlalchemy.orm import Session
from smos.models.ecology import ProvenanceRecord
from typing import List, Dict, Any

from smos.services.federation_service import FederationService

class SovereigntyService:
    """
    SovereigntyService delegates and wraps sovereignty policies and provenance tracking,
    integrating with FederationService.
    """
    def __init__(self, db: Session):
        self.db = db
        self.federation = FederationService(db)

    def record_provenance(self, node_id: int, cosmonaut_id: int, evidence: List[str]):
        record = ProvenanceRecord(
            node_id=node_id,
            created_by_id=cosmonaut_id,
            evidence_links=evidence
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def check_sovereignty_principles(self):
        return self.federation.check_sovereignty_principles()

    def evaluate_sovereignty_policy(self, node_id: int):
        return self.federation.evaluate_sovereignty_policy(node_id)
