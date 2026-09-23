from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from smos.models.potential import PotentialPhenomenon, PotentialStatus


class PotentialService:
    """Service layer for managing PotentialPhenomenon entities.

    Potential Phenomenon ≠ Prediction.
    - Prediction: epistemic claim about what WILL happen (forward-looking).
    - Potential Phenomenon: modal/structural representation of what COULD emerge,
      conditional on conditions/contexts/constraints.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        phenomenon: str,
        status: Union[str, PotentialStatus] = PotentialStatus.UNKNOWN,
        required_conditions: Optional[List[Any]] = None,
        supporting_contexts: Optional[List[Any]] = None,
        blocking_constraints: Optional[List[Any]] = None,
        dependencies: Optional[List[Any]] = None,
        expected_impacts: Optional[List[Dict[str, Any]]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> PotentialPhenomenon:
        """Create and persist a new PotentialPhenomenon."""
        if isinstance(status, str):
            status_enum = PotentialStatus.from_str(status)
        else:
            status_enum = status

        if required_conditions is None:
            required_conditions = []
        if supporting_contexts is None:
            supporting_contexts = []
        if blocking_constraints is None:
            blocking_constraints = []
        if dependencies is None:
            dependencies = []
        if expected_impacts is None:
            expected_impacts = []
        if provenance is None:
            provenance = {}

        item = PotentialPhenomenon(
            phenomenon=phenomenon,
            status=status_enum,
            required_conditions=required_conditions,
            supporting_contexts=supporting_contexts,
            blocking_constraints=blocking_constraints,
            dependencies=dependencies,
            expected_impacts=expected_impacts,
            provenance=provenance,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get(self, potential_id: int) -> Optional[PotentialPhenomenon]:
        """Retrieve a PotentialPhenomenon by ID."""
        return self.db.get(PotentialPhenomenon, potential_id)

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[Union[str, PotentialStatus]] = None,
    ) -> List[PotentialPhenomenon]:
        """List potential phenomena with optional status filter and pagination."""
        query = self.db.query(PotentialPhenomenon)

        if status is not None:
            status_enum = PotentialStatus.from_str(status) if isinstance(status, str) else status
            query = query.filter(PotentialPhenomenon.status == status_enum)

        return query.order_by(PotentialPhenomenon.id.asc()).offset(offset).limit(limit).all()

    def update(self, potential_id: int, **fields) -> Optional[PotentialPhenomenon]:
        """Update fields on an existing PotentialPhenomenon."""
        item = self.get(potential_id)
        if not item:
            return None

        if "status" in fields and fields["status"] is not None:
            s = fields["status"]
            fields["status"] = PotentialStatus.from_str(s) if isinstance(s, str) else s

        for key, value in fields.items():
            if hasattr(item, key):
                setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, potential_id: int) -> bool:
        """Delete a PotentialPhenomenon by ID."""
        item = self.get(potential_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def attach_condition(self, potential_id: int, condition: Any) -> Optional[PotentialPhenomenon]:
        """Attach a required condition to a potential phenomenon."""
        item = self.get(potential_id)
        if not item:
            return None
        current = list(item.required_conditions or [])
        current.append(condition)
        item.required_conditions = current
        self.db.commit()
        self.db.refresh(item)
        return item

    def attach_constraint(self, potential_id: int, constraint_id: Any) -> Optional[PotentialPhenomenon]:
        """Attach a blocking constraint ID to a potential phenomenon."""
        item = self.get(potential_id)
        if not item:
            return None
        current = list(item.blocking_constraints or [])
        current.append(constraint_id)
        item.blocking_constraints = current
        self.db.commit()
        self.db.refresh(item)
        return item

    def attach_context(self, potential_id: int, context_id: Any) -> Optional[PotentialPhenomenon]:
        """Attach a supporting context ID to a potential phenomenon."""
        item = self.get(potential_id)
        if not item:
            return None
        current = list(item.supporting_contexts or [])
        current.append(context_id)
        item.supporting_contexts = current
        self.db.commit()
        self.db.refresh(item)
        return item
