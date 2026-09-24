import enum
from sqlalchemy import Column, Integer, String, Enum, JSON, DateTime, func
from smos.core.database import Base
from smos.models.models import EpistemicStatus

class AgentType(str, enum.Enum):
    HUMAN = "HUMAN"           # User / human operator
    COSMONAUT = "COSMONAUT"   # Cosmonaut actor
    LLM = "LLM"               # LLMProfile agent
    DIGITAL_TWIN = "DIGITAL_TWIN"
    SYSTEM = "SYSTEM"         # automated/system
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            upper = value.upper()
            for member in cls:
                if member.value == upper:
                    return member
        return cls.UNKNOWN

    @classmethod
    def from_str(cls, value):
        if value is None:
            return cls.UNKNOWN
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).upper())
        except (ValueError, KeyError):
            return cls.UNKNOWN

class ContextExposure(Base):
    """Context exposure record.

    Records which context was visible to an agent when it generated
    a conclusion.

    IMPORTANT: this is a SIGNAL for convergence analysis,
    NOT evidence of truth.

    Visibility belongs to the exposure/run, not to Context itself.
    The same Context may be:
    - visible to Agent A (context_ids)
    - hidden from Agent B (hidden_context_ids)
    """
    __tablename__ = "context_exposures"

    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(
        Enum(AgentType),
        default=AgentType.UNKNOWN,
        nullable=False,
    )
    agent_id = Column(Integer, nullable=True)   # polymorphic (see AgentType)
    role = Column(String, nullable=True)         # analytical role in this run
    context_ids = Column(JSON, default=list)     # visible contexts.id
    knowledge_ids = Column(JSON, default=list)   # visible memory_nodes.id
    hidden_context_ids = Column(JSON, default=list)  # hidden contexts.id
    conclusion = Column(JSON, default=dict)      # {text, claim, confidence, ...}
    epistemic_status = Column(
        Enum(EpistemicStatus),
        default=EpistemicStatus.OBSERVED,
        nullable=True,
    )
    provenance = Column(JSON, default=dict)      # origin of THIS exposure record
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> dict:
        """Serialize ContextExposure to a dictionary."""
        return {
            "id": self.id,
            "agent_type": self.agent_type.value if isinstance(self.agent_type, AgentType) else self.agent_type,
            "agent_id": self.agent_id,
            "role": self.role,
            "context_ids": self.context_ids if self.context_ids is not None else [],
            "knowledge_ids": self.knowledge_ids if self.knowledge_ids is not None else [],
            "hidden_context_ids": self.hidden_context_ids if self.hidden_context_ids is not None else [],
            "conclusion": self.conclusion if self.conclusion is not None else {},
            "epistemic_status": self.epistemic_status.value if isinstance(self.epistemic_status, EpistemicStatus) else self.epistemic_status,
            "provenance": self.provenance if self.provenance is not None else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
