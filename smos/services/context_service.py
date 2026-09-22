from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from smos.models.context import Context, ContextRelation
from smos.models.models import EpistemicStatus, RelationType


class ContextService:
    """Service layer for managing Context and ContextRelation entities.

    Note: Context ≠ Fact. Default epistemic_status is EpistemicStatus.OBSERVED.
    Service methods do not auto-promote contexts to VERIFIED or facts.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        components: Optional[List[Any]] = None,
        source: Optional[str] = None,
        epistemic_status: Union[str, EpistemicStatus] = EpistemicStatus.OBSERVED,
        temporal_scope: Optional[str] = None,
        spatial_scope: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Context:
        """Create and persist a new Context."""
        if isinstance(epistemic_status, str):
            status_enum = EpistemicStatus.from_str(epistemic_status)
        else:
            status_enum = epistemic_status

        if components is None:
            components = []

        if provenance is None:
            provenance = {}

        context = Context(
            name=name,
            description=description,
            components=components,
            source=source,
            epistemic_status=status_enum,
            temporal_scope=temporal_scope,
            spatial_scope=spatial_scope,
            provenance=provenance,
        )
        self.db.add(context)
        self.db.commit()
        self.db.refresh(context)
        return context

    def get(self, context_id: int) -> Optional[Context]:
        """Retrieve a Context by ID."""
        return self.db.get(Context, context_id)

    def list(self, limit: int = 50, offset: int = 0) -> List[Context]:
        """List contexts with pagination."""
        return (
            self.db.query(Context)
            .order_by(Context.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(self, context_id: int, **fields) -> Optional[Context]:
        """Update fields on an existing Context."""
        context = self.get(context_id)
        if not context:
            return None

        if "epistemic_status" in fields:
            status = fields["epistemic_status"]
            if isinstance(status, str):
                fields["epistemic_status"] = EpistemicStatus.from_str(status)

        for key, value in fields.items():
            if hasattr(context, key):
                setattr(context, key, value)

        self.db.commit()
        self.db.refresh(context)
        return context

    def delete(self, context_id: int) -> bool:
        """Delete a Context by ID."""
        context = self.get(context_id)
        if not context:
            return False
        self.db.delete(context)
        self.db.commit()
        return True

    def add_relation(
        self,
        source_id: int,
        target_id: int,
        relation_type: Union[str, RelationType],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> ContextRelation:
        """Add a relationship between two Context entities."""
        if isinstance(relation_type, str):
            rel_type_enum = RelationType(relation_type)
        else:
            rel_type_enum = relation_type

        if provenance is None:
            provenance = {}

        relation = ContextRelation(
            source_context_id=source_id,
            target_context_id=target_id,
            relation_type=rel_type_enum,
            provenance=provenance,
        )
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def list_relations(self, context_id: int) -> List[ContextRelation]:
        """List all ContextRelation entities where context_id is source or target."""
        return (
            self.db.query(ContextRelation)
            .filter(
                or_(
                    ContextRelation.source_context_id == context_id,
                    ContextRelation.target_context_id == context_id,
                )
            )
            .order_by(ContextRelation.id.asc())
            .all()
        )
