from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from smos.models.constraint import Constraint, ConstraintType, ConstraintStatus


class ConstraintService:
    """Service layer for managing Constraint entities.

    Note: Constraint ≠ Cause.
    A Constraint represents a limiting condition or bounding envelope, NOT a causal agent.
    Service methods manage limiting conditions and do not generate causal relations.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        type: Union[str, ConstraintType] = ConstraintType.UNKNOWN,
        strength: Optional[float] = None,
        status: Union[str, ConstraintStatus] = ConstraintStatus.UNKNOWN,
        evidence: Optional[List[Any]] = None,
        context: Optional[str] = None,
        confidence: float = 0.5,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Constraint:
        """Create and persist a new Constraint."""
        if isinstance(type, str):
            type_enum = ConstraintType.from_str(type)
        else:
            type_enum = type

        if isinstance(status, str):
            status_enum = ConstraintStatus.from_str(status)
        else:
            status_enum = status

        if evidence is None:
            evidence = []

        if provenance is None:
            provenance = {}

        constraint = Constraint(
            name=name,
            description=description,
            type=type_enum,
            strength=strength,
            status=status_enum,
            evidence=evidence,
            context=context,
            confidence=confidence,
            provenance=provenance,
        )
        self.db.add(constraint)
        self.db.commit()
        self.db.refresh(constraint)
        return constraint

    def get(self, constraint_id: int) -> Optional[Constraint]:
        """Retrieve a Constraint by ID."""
        return self.db.get(Constraint, constraint_id)

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        type: Optional[Union[str, ConstraintType]] = None,
        status: Optional[Union[str, ConstraintStatus]] = None,
    ) -> List[Constraint]:
        """List constraints with optional filtering and pagination."""
        query = self.db.query(Constraint)

        if type is not None:
            type_enum = ConstraintType.from_str(type) if isinstance(type, str) else type
            query = query.filter(Constraint.type == type_enum)

        if status is not None:
            status_enum = ConstraintStatus.from_str(status) if isinstance(status, str) else status
            query = query.filter(Constraint.status == status_enum)

        return query.order_by(Constraint.id.asc()).offset(offset).limit(limit).all()

    def update(self, constraint_id: int, **fields) -> Optional[Constraint]:
        """Update fields on an existing Constraint."""
        constraint = self.get(constraint_id)
        if not constraint:
            return None

        if "type" in fields and fields["type"] is not None:
            t = fields["type"]
            fields["type"] = ConstraintType.from_str(t) if isinstance(t, str) else t

        if "status" in fields and fields["status"] is not None:
            s = fields["status"]
            fields["status"] = ConstraintStatus.from_str(s) if isinstance(s, str) else s

        for key, value in fields.items():
            if hasattr(constraint, key):
                setattr(constraint, key, value)

        self.db.commit()
        self.db.refresh(constraint)
        return constraint

    def delete(self, constraint_id: int) -> bool:
        """Delete a Constraint by ID."""
        constraint = self.get(constraint_id)
        if not constraint:
            return False
        self.db.delete(constraint)
        self.db.commit()
        return True
