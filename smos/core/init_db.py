from smos.core.database import engine, Base
from smos.models.models import User, Workspace, Timeline, MemoryNode, Relation, Event, Stream
from smos.models.goals import Goal, Task
from smos.models.consensus import Proposal, Vote
from smos.models.discussion import Comment, Reaction
from smos.models.cognitive import CognitiveSession, Thought
from smos.models.entities import DigitalTwin, Cosmonaut, Constellation
from smos.models.experience import Recipe, Reconstruction, CausalRelation, RecipeExecution, Wisdom, AntiRecipe
from smos.models.epistemic import EpistemicLayer, IntellectualCluster, ClusterRelation
from smos.models.discovery import LostKnowledge, Hypothesis, DiscoveryRecovery
from smos.models.coevolution import UnderstandingValidation, ComprehensionTest
from smos.models.entities import BehaviorProfile, LLMProfile
from smos.models.ecology import KnowledgeImpact, KnowledgeActivation, TranslatedMessage
from sqlalchemy import text

def init_db():
    # Ensure vector extension is enabled
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    # Make sure all models are imported before calling create_all
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")

if __name__ == "__main__":
    init_db()
