from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from smos.models.phenomenon import Phenomenon
from smos.models.models import EpistemicStatus
from smos.models.domain_event import DomainEventType
from smos.services.domain_event_service import DomainEventService


class PhenomenonService:
    """Service layer for managing Phenomenon entities.
    
    Note: Phenomenon ≠ Fact. Default epistemic_status is EpistemicStatus.OBSERVED.
    Service methods do not auto-promote phenomena to VERIFIED or facts.
    """

    def __init__(self, db: Session, event_service: Optional[DomainEventService] = None):
        self.db = db
        self.event_service = event_service

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        epistemic_status: Union[str, EpistemicStatus] = EpistemicStatus.OBSERVED,
        source: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[int] = None,
        context_ids: Optional[List[int]] = None,
        evidence_ids: Optional[List[int]] = None,
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

        if self.event_service:
            self.event_service.record(
                entity_type="phenomenon",
                entity_id=phenomenon.id,
                event_type=DomainEventType.CREATED,
                actor_type=actor_type,
                actor_id=actor_id,
                context_ids=context_ids,
                evidence_ids=evidence_ids,
                changes={"created": phenomenon.to_dict()},
            )

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

    def update(
        self,
        phenomenon_id: int,
        actor_type: Optional[str] = None,
        actor_id: Optional[int] = None,
        context_ids: Optional[List[int]] = None,
        evidence_ids: Optional[List[int]] = None,
        event_type: Optional[Union[str, DomainEventType]] = None,
        **fields,
    ) -> Optional[Phenomenon]:
        """Update fields on an existing Phenomenon."""
        phenomenon = self.get(phenomenon_id)
        if not phenomenon:
            return None

        changes: Dict[str, Dict[str, Any]] = {}
        status_changed = False

        if "epistemic_status" in fields:
            status = fields["epistemic_status"]
            if isinstance(status, str):
                fields["epistemic_status"] = EpistemicStatus.from_str(status)

        for key, value in fields.items():
            if hasattr(phenomenon, key):
                old_val = getattr(phenomenon, key)
                old_val_ser = (
                    old_val.value if isinstance(old_val, EpistemicStatus) else old_val
                )
                setattr(phenomenon, key, value)
                new_val_ser = (
                    value.value if isinstance(value, EpistemicStatus) else value
                )

                if key == "epistemic_status" and old_val_ser != new_val_ser:
                    status_changed = True

                changes[key] = {"old": old_val_ser, "new": new_val_ser}

        self.db.commit()
        self.db.refresh(phenomenon)

        if self.event_service:
            if event_type is None:
                evt_type = (
                    DomainEventType.STATE_CHANGED
                    if status_changed
                    else DomainEventType.UPDATED
                )
            else:
                evt_type = event_type

            self.event_service.record(
                entity_type="phenomenon",
                entity_id=phenomenon.id,
                event_type=evt_type,
                actor_type=actor_type,
                actor_id=actor_id,
                context_ids=context_ids,
                evidence_ids=evidence_ids,
                changes=changes,
            )

        return phenomenon

    def link_context(
        self,
        phenomenon_id: int,
        context_id: int,
        actor_type: Optional[str] = None,
        actor_id: Optional[int] = None,
        evidence_ids: Optional[List[int]] = None,
    ) -> Optional[Phenomenon]:
        """Link a context to a phenomenon (record LINKED domain event)."""
        phenomenon = self.get(phenomenon_id)
        if not phenomenon:
            return None
        if self.event_service:
            self.event_service.record(
                entity_type="phenomenon",
                entity_id=phenomenon_id,
                event_type=DomainEventType.LINKED,
                actor_type=actor_type,
                actor_id=actor_id,
                context_ids=[context_id],
                evidence_ids=evidence_ids,
                changes={"linked_context_id": context_id},
            )
        return phenomenon

    def delete(
        self,
        phenomenon_id: int,
        actor_type: Optional[str] = None,
        actor_id: Optional[int] = None,
        context_ids: Optional[List[int]] = None,
        evidence_ids: Optional[List[int]] = None,
    ) -> bool:
        """Delete a Phenomenon by ID."""
        phenomenon = self.get(phenomenon_id)
        if not phenomenon:
            return False

        old_data = phenomenon.to_dict()
        self.db.delete(phenomenon)
        self.db.commit()

        if self.event_service:
            self.event_service.record(
                entity_type="phenomenon",
                entity_id=phenomenon_id,
                event_type=DomainEventType.DELETED,
                actor_type=actor_type,
                actor_id=actor_id,
                context_ids=context_ids,
                evidence_ids=evidence_ids,
                changes={"deleted": old_data},
            )

        return True
