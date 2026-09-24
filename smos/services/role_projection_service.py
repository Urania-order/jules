"""RoleProjectionService and entity perspectives (PhenomenonPerspective, ContextPerspective, ConstraintPerspective).

These read-only projections answer domain-relevant questions by querying existing DomainRelation
entries without calculating new truth or modifying models.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from smos.models.domain_relation import DomainRelation
from smos.models.models import RelationType
from smos.services.domain_relation_service import DomainRelationService


class PhenomenonPerspective:
    """Read-only projection answering domain questions from a Phenomenon perspective."""

    def __init__(self, db: Session, domain_service: Optional[DomainRelationService] = None):
        self.db = db
        self.domain_service = domain_service if domain_service is not None else DomainRelationService(db)

    def what_conditions_allow_me_to_emerge(self, phenomenon_id: int) -> List[DomainRelation]:
        """DomainRelation where target=phenomenon, type in (ENABLES, REQUIRES, SUPPORTS)."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.target_type == "phenomenon",
                DomainRelation.target_id == phenomenon_id,
                DomainRelation.relation_type.in_([
                    RelationType.ENABLES,
                    RelationType.REQUIRES,
                    RelationType.SUPPORTS,
                ]),
            )
            .all()
        )

    def what_supports_me(self, phenomenon_id: int) -> List[DomainRelation]:
        """DomainRelation where target=phenomenon, type=SUPPORTS."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.target_type == "phenomenon",
                DomainRelation.target_id == phenomenon_id,
                DomainRelation.relation_type == RelationType.SUPPORTS,
            )
            .all()
        )

    def what_blocks_me(self, phenomenon_id: int) -> List[DomainRelation]:
        """DomainRelation where target=phenomenon, type in (BLOCKS, PREVENTS, SUPPRESSES)."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.target_type == "phenomenon",
                DomainRelation.target_id == phenomenon_id,
                DomainRelation.relation_type.in_([
                    RelationType.BLOCKS,
                    RelationType.PREVENTS,
                    RelationType.SUPPRESSES,
                ]),
            )
            .all()
        )

    def what_changes_after_i_emerge(self, phenomenon_id: int) -> List[DomainRelation]:
        """DomainRelation where source=phenomenon, type in (CHANGES_CONTEXT, TRANSFORMS)."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "phenomenon",
                DomainRelation.source_id == phenomenon_id,
                DomainRelation.relation_type.in_([
                    RelationType.CHANGES_CONTEXT,
                    RelationType.TRANSFORMS,
                ]),
            )
            .all()
        )

    def what_context_could_i_create(self, phenomenon_id: int) -> List[DomainRelation]:
        """DomainRelation where source=phenomenon, type=CREATES_CONTEXT."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "phenomenon",
                DomainRelation.source_id == phenomenon_id,
                DomainRelation.relation_type == RelationType.CREATES_CONTEXT,
            )
            .all()
        )

    def to_dict(self, phenomenon_id: int) -> Dict[str, Any]:
        """Aggregate all phenomenon perspective answers."""
        return {
            "phenomenon_id": phenomenon_id,
            "conditions_allowing_emergence": [
                r.to_dict() for r in self.what_conditions_allow_me_to_emerge(phenomenon_id)
            ],
            "supports": [r.to_dict() for r in self.what_supports_me(phenomenon_id)],
            "blocks": [r.to_dict() for r in self.what_blocks_me(phenomenon_id)],
            "changes_after_emergence": [
                r.to_dict() for r in self.what_changes_after_i_emerge(phenomenon_id)
            ],
            "created_contexts": [
                r.to_dict() for r in self.what_context_could_i_create(phenomenon_id)
            ],
        }


class ContextPerspective:
    """Read-only projection answering domain questions from a Context perspective."""

    def __init__(self, db: Session, domain_service: Optional[DomainRelationService] = None):
        self.db = db
        self.domain_service = domain_service if domain_service is not None else DomainRelationService(db)

    def what_phenomena_do_i_enable(self, context_id: int) -> List[DomainRelation]:
        """DomainRelation where source=context, type=ENABLES, target_type=phenomenon."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "context",
                DomainRelation.source_id == context_id,
                DomainRelation.target_type == "phenomenon",
                DomainRelation.relation_type == RelationType.ENABLES,
            )
            .all()
        )

    def what_do_i_block(self, context_id: int) -> List[DomainRelation]:
        """DomainRelation where source=context, type in (BLOCKS, PREVENTS)."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "context",
                DomainRelation.source_id == context_id,
                DomainRelation.relation_type.in_([
                    RelationType.BLOCKS,
                    RelationType.PREVENTS,
                ]),
            )
            .all()
        )

    def what_do_i_amplify(self, context_id: int) -> List[DomainRelation]:
        """DomainRelation where source=context, type=AMPLIFIES."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "context",
                DomainRelation.source_id == context_id,
                DomainRelation.relation_type == RelationType.AMPLIFIES,
            )
            .all()
        )

    def what_do_i_suppress(self, context_id: int) -> List[DomainRelation]:
        """DomainRelation where source=context, type=SUPPRESSES."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "context",
                DomainRelation.source_id == context_id,
                DomainRelation.relation_type == RelationType.SUPPRESSES,
            )
            .all()
        )

    def what_phenomena_created_or_changed_me(self, context_id: int) -> List[DomainRelation]:
        """DomainRelation where target=context, type in (CREATES_CONTEXT, CHANGES_CONTEXT)."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.target_type == "context",
                DomainRelation.target_id == context_id,
                DomainRelation.relation_type.in_([
                    RelationType.CREATES_CONTEXT,
                    RelationType.CHANGES_CONTEXT,
                ]),
            )
            .all()
        )

    def to_dict(self, context_id: int) -> Dict[str, Any]:
        """Aggregate all context perspective answers."""
        return {
            "context_id": context_id,
            "enabled_phenomena": [
                r.to_dict() for r in self.what_phenomena_do_i_enable(context_id)
            ],
            "blocks": [r.to_dict() for r in self.what_do_i_block(context_id)],
            "amplifies": [r.to_dict() for r in self.what_do_i_amplify(context_id)],
            "suppresses": [r.to_dict() for r in self.what_do_i_suppress(context_id)],
            "created_or_changed_by_phenomena": [
                r.to_dict() for r in self.what_phenomena_created_or_changed_me(context_id)
            ],
        }


class ConstraintPerspective:
    """Read-only projection answering domain questions from a Constraint perspective."""

    def __init__(self, db: Session, domain_service: Optional[DomainRelationService] = None):
        self.db = db
        self.domain_service = domain_service if domain_service is not None else DomainRelationService(db)

    def what_am_i_blocking(self, constraint_id: int) -> List[DomainRelation]:
        """DomainRelation where source=constraint, type in (BLOCKS, PREVENTS, SUPPRESSES)."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "constraint",
                DomainRelation.source_id == constraint_id,
                DomainRelation.relation_type.in_([
                    RelationType.BLOCKS,
                    RelationType.PREVENTS,
                    RelationType.SUPPRESSES,
                ]),
            )
            .all()
        )

    def how_strong_is_evidence(self, constraint_id: int) -> Dict[str, Any]:
        """Aggregate confidence + evidence from DomainRelation where source=constraint."""
        relations = (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "constraint",
                DomainRelation.source_id == constraint_id,
            )
            .all()
        )
        count = len(relations)
        confidences = [r.confidence for r in relations if r.confidence is not None]
        avg_confidence = (sum(confidences) / len(confidences)) if confidences else None
        evidence_count = sum(len(r.evidence) for r in relations if r.evidence)
        return {
            "count": count,
            "avg_confidence": avg_confidence,
            "evidence_count": evidence_count,
        }

    def is_blockage_direct_or_indirect(self, constraint_id: int) -> Dict[str, List[DomainRelation]]:
        """Direct: DomainRelation where source=constraint, type in (BLOCKS, PREVENTS).

        Indirect: DomainRelation where source=X, X is blocked by constraint (transitive - one level only).
        """
        direct = (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "constraint",
                DomainRelation.source_id == constraint_id,
                DomainRelation.relation_type.in_([
                    RelationType.BLOCKS,
                    RelationType.PREVENTS,
                ]),
            )
            .all()
        )
        indirect: List[DomainRelation] = []
        seen_ids = set()

        for rel in direct:
            target_type = rel.target_type
            target_id = rel.target_id
            indirect_rels = (
                self.db.query(DomainRelation)
                .filter(
                    DomainRelation.source_type == target_type,
                    DomainRelation.source_id == target_id,
                    DomainRelation.relation_type.in_([
                        RelationType.BLOCKS,
                        RelationType.PREVENTS,
                    ]),
                )
                .all()
            )
            for r in indirect_rels:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    indirect.append(r)

        return {
            "direct": direct,
            "indirect": indirect,
        }

    def what_other_constraints_depend_on_me(self, constraint_id: int) -> List[DomainRelation]:
        """DomainRelation where target=constraint, type=DEPENDS_ON, source_type=constraint."""
        return (
            self.db.query(DomainRelation)
            .filter(
                DomainRelation.source_type == "constraint",
                DomainRelation.target_type == "constraint",
                DomainRelation.target_id == constraint_id,
                DomainRelation.relation_type == RelationType.DEPENDS_ON,
            )
            .all()
        )

    def to_dict(self, constraint_id: int) -> Dict[str, Any]:
        """Aggregate all constraint perspective answers."""
        blockage = self.is_blockage_direct_or_indirect(constraint_id)
        return {
            "constraint_id": constraint_id,
            "blockages": [r.to_dict() for r in self.what_am_i_blocking(constraint_id)],
            "evidence_strength": self.how_strong_is_evidence(constraint_id),
            "blockage_reach": {
                "direct": [r.to_dict() for r in blockage["direct"]],
                "indirect": [r.to_dict() for r in blockage["indirect"]],
            },
            "dependent_constraints": [
                r.to_dict() for r in self.what_other_constraints_depend_on_me(constraint_id)
            ],
        }


class RoleProjectionService:
    """Aggregator/factory service for role projections."""

    def __init__(self, db: Session, domain_service: Optional[DomainRelationService] = None):
        self.db = db
        self.domain_service = domain_service if domain_service is not None else DomainRelationService(db)
        self._phenomenon_perspective = PhenomenonPerspective(db, self.domain_service)
        self._context_perspective = ContextPerspective(db, self.domain_service)
        self._constraint_perspective = ConstraintPerspective(db, self.domain_service)

    def phenomenon(self, phenomenon_id: int) -> Dict[str, Any]:
        """Get aggregated role projection dict for a phenomenon."""
        return self._phenomenon_perspective.to_dict(phenomenon_id)

    def context(self, context_id: int) -> Dict[str, Any]:
        """Get aggregated role projection dict for a context."""
        return self._context_perspective.to_dict(context_id)

    def constraint(self, constraint_id: int) -> Dict[str, Any]:
        """Get aggregated role projection dict for a constraint."""
        return self._constraint_perspective.to_dict(constraint_id)
