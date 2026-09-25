from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON
from sqlalchemy.sql import func
from smos.core.database import Base
from smos.models.models import EpistemicStatus


class Prediction(Base):
    """Prediction — system expects something to happen under conditions.

    Distinction from PotentialPhenomenon (TASK 05):
    - PotentialPhenomenon: modal ("could happen")
    - Prediction:           declarative ("system expects it to happen
                            under the stated conditions")

    Distinction from Timeline (models.py:195):
    - Timeline: representation of realities / temporal states
      (REAL / COUNTERFACTUAL)
    - Prediction: assertion made BEFORE the expected outcome
    They are conceptually separate. Timeline MUST NOT be reused
    as a Prediction model.

    Lifecycle:
      1. Create prediction (epistemic_status=PREDICTED)
      2. (later) Attach actual_outcome
      3. (later) Evaluate (attach evaluation)

    Rules:
      - attach_outcome() MUST NOT change epistemic_status
      - evaluate() MUST NOT change epistemic_status
      - Prediction MUST remain persistent after evaluation
      - Prediction MUST NOT be auto-promoted to fact

    source_hypothesis is polymorphic:
      - source_hypothesis_type: "potential_phenomenon" | "phenomenon" | None
      - source_hypothesis_id:   int | None
      No FK — one FK cannot reference two tables.
    """

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    # Source (polymorphic — no FK)
    source_hypothesis_type = Column(String, nullable=True)
    source_hypothesis_id = Column(Integer, nullable=True)

    # Timing (MANDATORY — historical reconstructability)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    prediction_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expected_at = Column(
        DateTime(timezone=True),
        nullable=True,   # target time — may be null if unknown
    )

    # Content
    expected_state = Column(JSON, default=dict)
    conditions = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)  # 0.0-1.0

    # Epistemic
    epistemic_status = Column(
        Enum(EpistemicStatus),
        default=EpistemicStatus.PREDICTED,
        nullable=False,
    )

    # Lifecycle (filled later, prediction remains persistent)
    actual_outcome = Column(JSON, default=dict)
    evaluation = Column(JSON, default=dict)

    # Provenance
    provenance = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_hypothesis_type": self.source_hypothesis_type,
            "source_hypothesis_id": self.source_hypothesis_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "prediction_time": self.prediction_time.isoformat() if self.prediction_time else None,
            "expected_at": self.expected_at.isoformat() if self.expected_at else None,
            "expected_state": self.expected_state if self.expected_state is not None else {},
            "conditions": self.conditions if self.conditions is not None else [],
            "confidence": self.confidence,
            "epistemic_status": (
                self.epistemic_status.value
                if isinstance(self.epistemic_status, EpistemicStatus)
                else self.epistemic_status
            ),
            "actual_outcome": self.actual_outcome if self.actual_outcome is not None else {},
            "evaluation": self.evaluation if self.evaluation is not None else {},
            "provenance": self.provenance if self.provenance is not None else {},
        }
