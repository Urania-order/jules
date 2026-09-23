"""DomainRelationService providing CRUD operations and scenario helpers for cross-domain relations."""

from typing import List, Optional, Union
from sqlalchemy.orm import Session
from smos.models.domain_relation import DomainRelation
from smos.models.models import EpistemicStatus, RelationType


class DomainRelationService:
    """Service for managing DomainRelation entities and cross-domain scenario relations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        relation_type: Union[RelationType, str],
        provenance: Optional[dict] = None,
        epistemic_status: Optional[Union[EpistemicStatus, str]] = None,
        confidence: Optional[float] = None,
        evidence: Optional[list] = None,
    ) -> DomainRelation:
        """Create a new DomainRelation."""
        if isinstance(relation_type, str):
            relation_type = RelationType(relation_type)

        if epistemic_status is not None and isinstance(epistemic_status, str):
            epistemic_status = EpistemicStatus.deserialize(epistemic_status)
        elif epistemic_status is None:
            epistemic_status = EpistemicStatus.OBSERVED

        relation = DomainRelation(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            epistemic_status=epistemic_status,
            provenance=provenance if provenance is not None else {},
            evidence=evidence if evidence is not None else [],
            confidence=confidence,
        )
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def get(self, relation_id: int) -> Optional[DomainRelation]:
        """Get a DomainRelation by ID."""
        return self.db.query(DomainRelation).filter(DomainRelation.id == relation_id).first()

    def list(
        self,
        source_type: Optional[str] = None,
        target_type: Optional[str] = None,
        relation_type: Optional[Union[RelationType, str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DomainRelation]:
        """List DomainRelation records with optional filters."""
        query = self.db.query(DomainRelation)

        if source_type is not None:
            query = query.filter(DomainRelation.source_type == source_type)
        if target_type is not None:
            query = query.filter(DomainRelation.target_type == target_type)
        if relation_type is not None:
            if isinstance(relation_type, str):
                relation_type = RelationType(relation_type)
            query = query.filter(DomainRelation.relation_type == relation_type)

        return query.offset(offset).limit(limit).all()

    def update(self, relation_id: int, **fields) -> Optional[DomainRelation]:
        """Update fields on an existing DomainRelation."""
        relation = self.get(relation_id)
        if not relation:
            return None

        for key, value in fields.items():
            if hasattr(relation, key):
                if key == "relation_type" and isinstance(value, str):
                    value = RelationType(value)
                elif key == "epistemic_status" and isinstance(value, str):
                    value = EpistemicStatus.deserialize(value)
                setattr(relation, key, value)

        self.db.commit()
        self.db.refresh(relation)
        return relation

    def delete(self, relation_id: int) -> bool:
        """Delete a DomainRelation by ID."""
        relation = self.get(relation_id)
        if not relation:
            return False
        self.db.delete(relation)
        self.db.commit()
        return True

    def list_for(self, source_type: str, source_id: int) -> List[DomainRelation]:
        """List all DomainRelation records originating from a source."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == source_type,
                DomainRelation.source_id == source_id,
            )
            .all()
        )

    def list_into(self, target_type: str, target_id: int) -> List[DomainRelation]:
        """List all DomainRelation records targeting a target."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.target_type == target_type,
                DomainRelation.target_id == target_id,
            )
            .all()
        )

    # Scenario helpers (documented/inferred/hypothesized, not calculating causal truth)

    def context_enables_phenomenon(self, context_id: int, phenomenon_id: int, **kw) -> DomainRelation:
        """Scenario helper: Context ENABLES Phenomenon."""
        return self.create(
            source_type="context",
            source_id=context_id,
            target_type="phenomenon",
            target_id=phenomenon_id,
            relation_type=RelationType.ENABLES,
            **kw,
        )

    def context_blocks_phenomenon(self, context_id: int, phenomenon_id: int, **kw) -> DomainRelation:
        """Scenario helper: Context BLOCKS Phenomenon."""
        return self.create(
            source_type="context",
            source_id=context_id,
            target_type="phenomenon",
            target_id=phenomenon_id,
            relation_type=RelationType.BLOCKS,
            **kw,
        )

    def constraint_blocks_potential(self, constraint_id: int, potential_id: int, **kw) -> DomainRelation:
        """Scenario helper: Constraint BLOCKS Potential Phenomenon."""
        return self.create(
            source_type="constraint",
            source_id=constraint_id,
            target_type="potential",
            target_id=potential_id,
            relation_type=RelationType.BLOCKS,
            **kw,
        )

    def phenomenon_changes_context(self, phenomenon_id: int, context_id: int, **kw) -> DomainRelation:
        """Scenario helper: Phenomenon CHANGES_CONTEXT Context."""
        return self.create(
            source_type="phenomenon",
            source_id=phenomenon_id,
            target_type="context",
            target_id=context_id,
            relation_type=RelationType.CHANGES_CONTEXT,
            **kw,
        )

    def phenomenon_creates_context(self, phenomenon_id: int, context_id: int, **kw) -> DomainRelation:
        """Scenario helper: Phenomenon CREATES_CONTEXT Context."""
        return self.create(
            source_type="phenomenon",
            source_id=phenomenon_id,
            target_type="context",
            target_id=context_id,
            relation_type=RelationType.CREATES_CONTEXT,
            **kw,
        )

    def potential_depends_on_context(self, potential_id: int, context_id: int, **kw) -> DomainRelation:
        """Scenario helper: Potential Phenomenon DEPENDS_ON Context."""
        return self.create(
            source_type="potential",
            source_id=potential_id,
            target_type="context",
            target_id=context_id,
            relation_type=RelationType.DEPENDS_ON,
            **kw,
        )
