"""Phenomenon model representing observed or postulated occurrences.

Note: Phenomenon ≠ Fact.
A Phenomenon represents an observed or postulated pattern, event, or occurrence.
It possesses an epistemic status (defaulting to OBSERVED), but is NOT automatically
considered a verified fact.
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON
from sqlalchemy.sql import func
from smos.core.database import Base
from smos.models.models import EpistemicStatus


class Phenomenon(Base):
    """SQLAlchemy model for Phenomenon entities.
    
    A phenomenon is an observed or hypothesized domain occurrence.
    Phenomenon ≠ fact: registering a phenomenon does not imply it is verified fact.
    """

    __tablename__ = "phenomena"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    epistemic_status = Column(
        Enum(EpistemicStatus),
        default=EpistemicStatus.OBSERVED,
        nullable=False,
    )
    source = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    provenance = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        """Serialize Phenomenon to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "epistemic_status": self.epistemic_status.value if isinstance(self.epistemic_status, EpistemicStatus) else self.epistemic_status,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "provenance": self.provenance if self.provenance is not None else {},
        }
