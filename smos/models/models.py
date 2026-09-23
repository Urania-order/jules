from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Enum, Float, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from smos.core.database import Base
import os
if os.getenv("DATABASE_URL", "").startswith("sqlite"):
    import json
    from sqlalchemy import TypeDecorator, Text

    class Vector(TypeDecorator):
        """SQLite-compatible Vector: stores list as JSON text."""
        impl = Text
        cache_ok = True

        def __init__(self, dim=None):
            self.dim = dim
            super().__init__()

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return json.dumps(list(value))

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            return json.loads(value)
else:
    from pgvector.sqlalchemy import Vector

class UserRole(str, enum.Enum):
    OWNER = "Owner"
    ADMIN = "Admin"
    EDITOR = "Editor"
    CONTRIBUTOR = "Contributor"
    READER = "Reader"
    OBSERVER = "Observer"
    AI_AGENT = "AI Agent"

class TimelineType(str, enum.Enum):
    REAL = "REAL"
    SIMULATION = "SIMULATION"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    DREAM = "DREAM"
    FICTION = "FICTION"
    EXPERIMENT = "EXPERIMENT"
    ROLEPLAY = "ROLEPLAY"

class MemoryType(str, enum.Enum):
    MEMORY = "MemoryNode"
    TASK = "TaskNode"
    PROJECT = "ProjectNode"
    GOAL = "GoalNode"
    PERSON = "PersonNode"
    IDEA = "IdeaNode"
    CODE = "CodeNode"

class KnowledgeLifecycleState(str, enum.Enum):
    IDEA = "Idea"
    DISCUSSION = "Discussion"
    RECIPE = "Recipe"
    EXPERIMENT = "Experiment"
    PRACTICE = "Practice"
    BEHAVIOR_CHANGE = "Behavior Change"
    COLLECTIVE_EXPERIENCE = "Collective Experience"
    IMPROVED_KNOWLEDGE = "Improved Knowledge"

class EpistemicStatus(str, enum.Enum):
    # Canonical 7 statuses
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    HYPOTHESIZED = "HYPOTHESIZED"
    PREDICTED = "PREDICTED"
    UNVALIDATED = "UNVALIDATED"
    CONTESTED = "CONTESTED"
    REFUTED = "REFUTED"

    # Legacy statuses preserved for backward compatibility
    VERIFIED = "Verified"
    HYPOTHESIS = "Hypothesis"
    COUNTERFACTUAL = "Counterfactual"
    HISTORICAL_RECONSTRUCTION = "Historical Reconstruction"
    SPECULATIVE = "Speculative"
    BEYOND_ALL_CONSENSUS = "Beyond All Consensus"
    UNVERIFIED = "Unverified"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            for member in cls:
                if member.name.upper() == val_upper or member.value.upper() == val_upper:
                    return member
        return None

    @classmethod
    def from_str(cls, value: str) -> "EpistemicStatus":
        """Parse string value into EpistemicStatus (case-insensitive)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid EpistemicStatus: {value}")

    def to_canonical(self) -> "EpistemicStatus":
        """Map legacy statuses to closest canonical equivalent if needed, or return self if already canonical."""
        canonical_map = {
            EpistemicStatus.VERIFIED: EpistemicStatus.OBSERVED,
            EpistemicStatus.HYPOTHESIS: EpistemicStatus.HYPOTHESIZED,
            EpistemicStatus.COUNTERFACTUAL: EpistemicStatus.HYPOTHESIZED,
            EpistemicStatus.HISTORICAL_RECONSTRUCTION: EpistemicStatus.INFERRED,
            EpistemicStatus.SPECULATIVE: EpistemicStatus.HYPOTHESIZED,
            EpistemicStatus.BEYOND_ALL_CONSENSUS: EpistemicStatus.CONTESTED,
            EpistemicStatus.UNVERIFIED: EpistemicStatus.UNVALIDATED,
        }
        return canonical_map.get(self, self)

    @property
    def is_canonical(self) -> bool:
        """Check if this status is one of the 7 canonical statuses."""
        return self in {
            EpistemicStatus.OBSERVED,
            EpistemicStatus.INFERRED,
            EpistemicStatus.HYPOTHESIZED,
            EpistemicStatus.PREDICTED,
            EpistemicStatus.UNVALIDATED,
            EpistemicStatus.CONTESTED,
            EpistemicStatus.REFUTED,
        }

    def serialize(self) -> str:
        """Serialize status for storage/transmission."""
        return self.value

    @classmethod
    def deserialize(cls, value: str) -> "EpistemicStatus":
        """Deserialize status from string representation."""
        return cls.from_str(value)

class RelationType(str, enum.Enum):
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    CREATED_FROM = "CREATED_FROM"
    CAUSES = "CAUSES"
    SOLVES = "SOLVES"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CONTRADICTS = "CONTRADICTS"
    WORKS_ON = "WORKS_ON"
    SHARED_WITH = "SHARED_WITH"
    CREATED_BY = "CREATED_BY"
    MENTIONS = "MENTIONS"
    DEPENDS_ON = "DEPENDS_ON"
    ASSIGNED_TO = "ASSIGNED_TO"
    REVIEWED_BY = "REVIEWED_BY"
    ALTERNATIVE_TO = "ALTERNATIVE_TO"
    BRANCHED_FROM = "BRANCHED_FROM"
    MERGED_INTO = "MERGED_INTO"
    INSPIRED_BY = "INSPIRED_BY"
    SIMULATES = "SIMULATES"
    # New 13 relation types added in TASK 06
    SUPPORTS = "SUPPORTS"
    BLOCKS = "BLOCKS"
    ENABLES = "ENABLES"
    AMPLIFIES = "AMPLIFIES"
    SUPPRESSES = "SUPPRESSES"
    TRANSFORMS = "TRANSFORMS"
    CREATES_CONTEXT = "CREATES_CONTEXT"
    CHANGES_CONTEXT = "CHANGES_CONTEXT"
    EMERGES_FROM = "EMERGES_FROM"
    RESONATES_WITH = "RESONATES_WITH"
    CORRELATES_WITH = "CORRELATES_WITH"
    REQUIRES = "REQUIRES"
    PREVENTS = "PREVENTS"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String)
    avatar = Column(String, nullable=True)
    public_key = Column(String, nullable=True)
    preferences = Column(JSON, default={})
    role = Column(Enum(UserRole), default=UserRole.READER)

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    members = Column(JSON, default=[]) # List of user IDs and roles

class Timeline(Base):
    __tablename__ = "timelines"
    id = Column(Integer, primary_key=True, index=True)
    parent_timeline_id = Column(Integer, ForeignKey("timelines.id"), nullable=True)
    type = Column(Enum(TimelineType), default=TimelineType.REAL)
    description = Column(String, nullable=True)
    probability = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MemoryNode(Base):
    __tablename__ = "memory_nodes"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(MemoryType), default=MemoryType.MEMORY)
    content = Column(String)
    source = Column(JSON, nullable=True)
    embeddings = Column(Vector(1536)) # Assuming OpenAI embeddings size
    importance = Column(Float, default=0.0)
    recurrence = Column(Integer, default=0)
    emotional_weight = Column(Float, default=0.0)
    project_id = Column(Integer, nullable=True)
    tags = Column(JSON, default=[])
    owner_id = Column(Integer, ForeignKey("users.id"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    timeline_id = Column(Integer, ForeignKey("timelines.id"))
    reality_level = Column(String, default="REAL")
    lifecycle_state = Column(Enum(KnowledgeLifecycleState), default=KnowledgeLifecycleState.IDEA)
    epistemic_status = Column(Enum(EpistemicStatus), default=EpistemicStatus.UNVERIFIED)
    layer_ids = Column(JSON, default=[]) # List of EpistemicLayer IDs
    cluster_ids = Column(JSON, default=[]) # List of IntellectualCluster IDs
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Relation(Base):
    """SQLAlchemy model for Relation entities.

    PROVENANCE DECISION (Option B):
    Relation receives provenance = Column(JSON, default=dict) as the canonical
    provenance representation for domain relations, matching the pattern used in
    Phenomenon, Context, Constraint, and PotentialPhenomenon.
    ProvenanceRecord remains unchanged in ecology.py as canonical for memory_nodes/ecology.
    """
    __tablename__ = "relations"
    id = Column(Integer, primary_key=True, index=True)
    from_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    to_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    type = Column(Enum(RelationType))
    provenance = Column(JSON, default=dict)
    epistemic_status = Column(Enum(EpistemicStatus), nullable=True)
    evidence = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)
    observer = Column(String, nullable=True)
    context = Column(String, nullable=True)

class Stream(Base):
    __tablename__ = "streams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    active_goal_id = Column(Integer, nullable=True)
    repository = Column(String, nullable=True)
    tags = Column(JSON, default=[])
    visibility = Column(String, default="Personal") # Personal, Team, Public

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    stream_id = Column(Integer, ForeignKey("streams.id"), nullable=True)
    type = Column(String) # e.g., clipboard, input, browser
    content = Column(JSON)
    application = Column(String, nullable=True)
    window_title = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
