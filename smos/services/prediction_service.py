from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from smos.models.prediction import Prediction
from smos.models.models import EpistemicStatus
from smos.models.potential import PotentialPhenomenon
from smos.services.semantic_search_service import SemanticSearchService, build_canonical_semantic_text
from smos.services.embedding_fallback import HashFallbackAdapter


class PredictionService:
    """Service for managing Prediction lifecycle.

    Lifecycle (explicit, no auto-promotion):
      1. create_prediction -> epistemic_status=PREDICTED
      2. attach_outcome    -> does NOT change epistemic_status
      3. evaluate          -> does NOT auto-promote to fact
                              does NOT change epistemic_status

    Prediction remains persistent after evaluation (historical record).
    The caller is responsible for explicitly updating epistemic_status
    through an authorized mechanism if desired.
    """

    DEFAULT_CANDIDATE_ENTITY_TYPES = [
        "phenomenon",
        "context",
        "constraint",
        "potential_phenomenon",
    ]

    def __init__(
        self,
        db: Session,
        semantic_service: Optional[SemanticSearchService] = None,
    ):
        self.db = db
        self.semantic_service = (
            semantic_service
            or SemanticSearchService(db, HashFallbackAdapter())
        )

    # --- Create ---
    def create_prediction(
        self,
        expected_state: Dict[str, Any],
        source_hypothesis_type: Optional[str] = None,
        source_hypothesis_id: Optional[int] = None,
        conditions: Optional[List[Any]] = None,
        confidence: Optional[float] = None,
        prediction_time: Optional[datetime] = None,
        expected_at: Optional[datetime] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Prediction:
        prediction = Prediction(
            source_hypothesis_type=source_hypothesis_type,
            source_hypothesis_id=source_hypothesis_id,
            expected_state=dict(expected_state or {}),
            conditions=list(conditions or []),
            confidence=confidence,
            epistemic_status=EpistemicStatus.PREDICTED,
            expected_at=expected_at,
            provenance=dict(provenance or {}),
        )
        if prediction_time is not None:
            prediction.prediction_time = prediction_time
        else:
            prediction.prediction_time = datetime.now(timezone.utc)

        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    # --- Read ---
    def get(self, prediction_id: int) -> Optional[Prediction]:
        return self.db.get(Prediction, prediction_id)

    def list(self, limit: int = 50, offset: int = 0) -> List[Prediction]:
        return (
            self.db.query(Prediction)
            .order_by(Prediction.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete(self, prediction_id: int) -> bool:
        prediction = self.get(prediction_id)
        if not prediction:
            return False
        self.db.delete(prediction)
        self.db.commit()
        return True

    # --- Lifecycle ---
    def attach_outcome(
        self,
        prediction_id: int,
        actual_outcome: Dict[str, Any],
    ) -> Optional[Prediction]:
        """Attach actual outcome. Does NOT change epistemic_status."""
        prediction = self.get(prediction_id)
        if not prediction:
            return None
        prediction.actual_outcome = dict(actual_outcome or {})
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    def evaluate(
        self,
        prediction_id: int,
        evaluation: Dict[str, Any],
    ) -> Optional[Prediction]:
        """Attach evaluation. Does NOT auto-promote to fact.
        Does NOT change epistemic_status.
        """
        prediction = self.get(prediction_id)
        if not prediction:
            return None
        prediction.evaluation = dict(evaluation or {})
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    # --- Semantic Retrieval (TASK 30) ---
    def semantic_conditions(
        self,
        prediction_id: int,
        k: int = 10,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return semantic neighbors of a prediction as CANDIDATE signal.

        IMPORTANT:
        - This is a SIGNAL, not evidence.
        - This is NOT a search for Prediction.conditions.
        - The result is a set of nearby objects that MAY be considered
          as condition candidates by an operator/system in a LATER step.
        - Read-only. Does NOT modify any canonical entity.

        By default, entity_types is limited to canonical candidate types:
            phenomenon, context, constraint, potential_phenomenon

        The prediction MUST already be present in the semantic index
        (indexed by an existing mechanism). If it is not indexed,
        returns [].
        """
        if entity_types is None:
            entity_types = self.DEFAULT_CANDIDATE_ENTITY_TYPES
        return self.semantic_service.similar(
            "prediction",
            prediction_id,
            k=k,
            entity_types=entity_types,
        )

    def semantic_search_conditions(
        self,
        query: str,
        k: int = 10,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search for a candidate query text.

        SIGNAL only. Does NOT modify any canonical entity.
        Default entity_types limited to canonical candidate types.
        """
        if entity_types is None:
            entity_types = self.DEFAULT_CANDIDATE_ENTITY_TYPES
        return self.semantic_service.search(
            query,
            k=k,
            entity_types=entity_types,
        )

    # --- Integration with TASK 05 / TASK 12 ---
    def from_potential_phenomenon(
        self,
        potential_id: int,
        expected_state: Dict[str, Any],
        conditions: Optional[List[Any]] = None,
        confidence: Optional[float] = None,
        expected_at: Optional[datetime] = None,
        provenance: Optional[Dict[str, Any]] = None,
        include_semantic_conditions: bool = False,
    ) -> Optional[Prediction]:
        """Create a Prediction whose source_hypothesis is a
        PotentialPhenomenon (TASK 05).
        """
        potential = self.db.get(PotentialPhenomenon, potential_id)
        if not potential:
            return None

        merged_conditions = list(potential.required_conditions or [])
        if conditions:
            merged_conditions.extend(conditions)

        provenance_dict = dict(provenance or {})

        if include_semantic_conditions:
            query_text = build_canonical_semantic_text("potential_phenomenon", potential)
            semantic_candidates = self.semantic_search_conditions(query_text)
            if "semantic_candidates" not in provenance_dict:
                provenance_dict["semantic_candidates"] = semantic_candidates

        return self.create_prediction(
            expected_state=expected_state,
            source_hypothesis_type="potential_phenomenon",
            source_hypothesis_id=potential.id,
            conditions=merged_conditions,
            confidence=confidence,
            expected_at=expected_at,
            provenance=provenance_dict,
        )
