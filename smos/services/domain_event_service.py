from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from smos.models.domain_event import DomainEvent, DomainEventType


class DomainEventService:
    """Append-only domain event service.

    This is THE canonical domain entity audit mechanism.
    Do NOT create parallel audit systems.
    """

    def __init__(self, db: Session):
        self.db = db

    # --- Record (append-only) ---
    def record(
        self,
        entity_type: str,
        entity_id: int,
        event_type: Any,
        actor_type: Optional[str] = None,
        actor_id: Optional[int] = None,
        context_ids: Optional[List[int]] = None,
        evidence_ids: Optional[List[int]] = None,
        changes: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> DomainEvent:
        if isinstance(event_type, str):
            event_type = DomainEventType(event_type)
        event = DomainEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            context_ids=list(context_ids or []),
            evidence_ids=list(evidence_ids or []),
            changes=dict(changes or {}),
            provenance=dict(provenance or {}),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    # --- Query ---
    def get(self, event_id: int) -> Optional[DomainEvent]:
        return self.db.query(DomainEvent).filter(DomainEvent.id == event_id).first()

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DomainEvent]:
        return (
            self.db.query(DomainEvent)
            .filter(
                DomainEvent.entity_type == entity_type,
                DomainEvent.entity_id == entity_id,
            )
            .order_by(DomainEvent.created_at.asc(), DomainEvent.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_recent(self, limit: int = 50) -> List[DomainEvent]:
        return (
            self.db.query(DomainEvent)
            .order_by(DomainEvent.created_at.desc(), DomainEvent.id.desc())
            .limit(limit)
            .all()
        )

    # --- Reconstruction (READ-ONLY) ---
    def reconstruct_entity(
        self,
        entity_type: str,
        entity_id: int,
    ) -> Dict[str, Any]:
        """Reconstruct the entity's change history (READ-ONLY)."""
        events = self.list_for_entity(entity_type, entity_id)
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_count": len(events),
            "created_at": events[0].created_at.isoformat() if (events and events[0].created_at) else None,
            "updated_at": events[-1].created_at.isoformat() if (events and events[-1].created_at) else None,
            "events": [e.to_dict() for e in events],
            "reconstruction_note": (
                "Reconstructed from DomainEvent records. READ-ONLY. "
                "Events are append-only."
            ),
        }

    def reconstruct_lifecycle(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[Dict[str, Any]]:
        """Return lifecycle events in chronological order."""
        events = self.list_for_entity(entity_type, entity_id)
        return [e.to_dict() for e in events]
