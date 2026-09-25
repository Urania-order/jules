from sqlalchemy import Column, Integer, String, DateTime, JSON, Enum
from sqlalchemy.sql import func
from smos.core.database import Base
import enum


class DomainEventType(str, enum.Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"
    STATE_CHANGED = "STATE_CHANGED"


class DomainEvent(Base):
    """Domain entity event — supports reconstruction.

    Distinct from:
    - Event (models.py:259): user activity log
    - admin_audit.jsonl: admin command audit
    - ProvenanceRecord (ecology.py:53): memory_node provenance

    Reconstruct:
        who      -> actor_type, actor_id
        what     -> event_type
        when     -> created_at
        context  -> context_ids (JSON)
        evidence -> evidence_ids (JSON)
        changed  -> changes (JSON: {field: {old, new}})

    APPEND-ONLY: never update, never delete.
    """

    __tablename__ = "domain_events"

    id = Column(Integer, primary_key=True, index=True)

    # WHO
    actor_type = Column(String, nullable=True)
    # "user" | "cosmonaut" | "llm" | "system" | None
    actor_id = Column(Integer, nullable=True)

    # WHAT
    entity_type = Column(String, nullable=False, index=True)
    # "phenomenon" | "context" | "constraint" | "potential_phenomenon"
    # | "domain_relation" | "prediction" | "resonance" | ...
    entity_id = Column(Integer, nullable=False, index=True)
    event_type = Column(Enum(DomainEventType), nullable=False)

    # WHEN
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    # WHERE / UNDER WHICH CONTEXT
    context_ids = Column(JSON, default=list)

    # USING WHICH EVIDENCE
    evidence_ids = Column(JSON, default=list)

    # CHANGED WHAT
    changes = Column(JSON, default=dict)

    # Provenance of the event record itself
    provenance = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "event_type": (
                self.event_type.value
                if isinstance(self.event_type, DomainEventType)
                else self.event_type
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "context_ids": self.context_ids if self.context_ids is not None else [],
            "evidence_ids": self.evidence_ids if self.evidence_ids is not None else [],
            "changes": self.changes if self.changes is not None else {},
            "provenance": self.provenance if self.provenance is not None else {},
        }
