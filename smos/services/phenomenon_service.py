from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from smos.models.phenomenon import Phenomenon
from smos.models.models import EpistemicStatus


class PhenomenonService:
    """Service layer for managing Phenomenon entities.
    
    Note: Phenomenon ≠ Fact. Default epistemic_status is EpistemicStatus.OBSERVED.
    Service methods do not auto-promote phenomena to VERIFIED or facts.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        epistemic_status: Union[str, EpistemicStatus] = EpistemicStatus.OBSERVED,
        source: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Phenomenon:
        """Create and persist a new Phenomenon."""
        if isinstance(epistemic_status, str):
            status_enum = EpistemicStatus.from_str(epistemic_status)
        else:
            status_enum = epistemic_status

        if provenance is None:
            provenance = {}

        phenomenon = Phenomenon(
            name=name,
            description=description,
            epistemic_status=status_enum,
            source=source,
            provenance=provenance,
        )
        self.db.add(phenomenon)
        self.db.commit()
        self.db.refresh(phenomenon)
        return phenomenon

    def get(self, phenomenon_id: int) -> Optional[Phenomenon]:
        """Retrieve a Phenomenon by ID."""
        return self.db.get(Phenomenon, phenomenon_id)

    def list(self, limit: int = 50, offset: int = 0) -> List[Phenomenon]:
        """List phenomena with pagination."""
        return (
            self.db.query(Phenomenon)
            .order_by(Phenomenon.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(self, phenomenon_id: int, **fields) -> Optional[Phenomenon]:
        """Update fields on an existing Phenomenon."""
        phenomenon = self.get(phenomenon_id)
        if not phenomenon:
            return None

        if "epistemic_status" in fields:
            status = fields["epistemic_status"]
            if isinstance(status, str):
                fields["epistemic_status"] = EpistemicStatus.from_str(status)

        for key, value in fields.items():
            if hasattr(phenomenon, key):
                setattr(phenomenon, key, value)

        self.db.commit()
        self.db.refresh(phenomenon)
        return phenomenon

    def delete(self, phenomenon_id: int) -> bool:
        """Delete a Phenomenon by ID."""
        phenomenon = self.get(phenomenon_id)
        if not phenomenon:
            return False
        self.db.delete(phenomenon)
        self.db.commit()
        return True
