from mcp.server.fastmcp import FastMCP
from smos.core.database import SessionLocal
from smos.services.integrations import JulesService
from typing import List

mcp = FastMCP("smos")

@mcp.tool()
def search_memory(query: str) -> str:
    """Search semantic memory"""
    db = SessionLocal()
    from smos.models.models import MemoryNode
    from smos.services.embedding_service import embedding_service
    embedding = embedding_service.get_embedding(query)
    results = db.query(MemoryNode).order_by(
        MemoryNode.embeddings.l2_distance(embedding)
    ).limit(3).all()
    db.close()
    return f"Found: {[r.content for r in results]}"

@mcp.tool()
def create_jules_session(task: str, repo: str = None) -> str:
    """Create a new Jules session"""
    jules = JulesService()
    result = jules.create_session(task, repo)
    return f"Jules session created: {result}"

@mcp.tool()
def get_clipboard() -> str:
    """Get current clipboard content (Mock)"""
    return "Clipboard content: 'Sample text from clipboard'"

@mcp.tool()
def set_clipboard(text: str) -> str:
    """Set clipboard content (Mock)"""
    return f"Clipboard set to: {text}"

@mcp.tool()
def create_task(title: str, goal_id: int = None) -> str:
    """Create a new task"""
    db = SessionLocal()
    from smos.models.goals import Task
    task = Task(title=title, goal_id=goal_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.id
    db.close()
    return f"Task created with ID: {task_id}"

@mcp.tool()
def get_active_goals(user_id: int) -> str:
    """Get active goals for a user"""
    db = SessionLocal()
    from smos.services.goal_engine import GoalEngine
    engine = GoalEngine(db)
    goals = engine.identify_active_projects(user_id)
    db.close()
    return f"Active goals: {[g.title for g in goals]}"

@mcp.tool()
def compare_timelines(id_a: int, id_b: int) -> str:
    """Compare two timelines and find differences"""
    db = SessionLocal()
    from smos.services.timeline_service import TimelineService
    svc = TimelineService(db)
    result = svc.compare_timelines(id_a, id_b)
    db.close()
    return f"Timeline Comparison: {result}"

@mcp.tool()
def create_recipe(title: str, author_id: int, steps: List[str], problem_type: str) -> str:
    """Create a new successful recipe for solving a problem"""
    db = SessionLocal()
    from smos.services.recipe_service import RecipeService
    svc = RecipeService(db)
    recipe = svc.create_recipe(title, author_id, steps, problem_type)
    recipe_id = recipe.id
    db.close()
    return f"Recipe created with ID: {recipe_id}"

@mcp.tool()
def start_cognitive_session(topic: str, timeline_id: int, participants: List[int]) -> str:
    """Start a collective thinking session on a specific topic"""
    db = SessionLocal()
    from smos.services.cognitive_service import CognitiveService
    svc = CognitiveService(db)
    session = svc.create_session(None, topic, timeline_id, participants)
    session_id = session.id
    db.close()
    return f"Cognitive Session started with ID: {session_id}"

@mcp.tool()
def execute_recipe(recipe_id: int, participants: List[int], result: str) -> str:
    """Record the outcome of a recipe execution"""
    db = SessionLocal()
    from smos.services.execution_service import ExecutionService
    svc = ExecutionService(db)
    exe = svc.record_execution(recipe_id, participants, result)
    exe_id = exe.id
    db.close()
    return f"Recipe Execution recorded with ID: {exe_id}, Result: {result}"

@mcp.tool()
def inherit_knowledge(cosmonaut_id: int, topic: str) -> str:
    """Download successful experience and recipes from other participants on a topic"""
    db = SessionLocal()
    from smos.services.community_service import CommunityService
    svc = CommunityService(db)
    recipes = svc.inherit_experience(cosmonaut_id, topic)
    db.close()
    return f"Inherited {len(recipes)} recipes on topic: {topic}"

@mcp.tool()
def reconstruct_experience(observations: List[str], artifacts: List[str], witnesses: List[str]) -> str:
    """Infer missing event data or past failures from evidence"""
    db = SessionLocal()
    from smos.services.reconstruction_service import ReconstructionService
    svc = ReconstructionService(db)
    rec = svc.reconstruct_experience(observations, artifacts, witnesses)
    rec_id = rec.id
    db.close()
    return f"Experience Reconstruction created with ID: {rec_id}, Level: {rec.evidence_level}"

@mcp.tool()
def cross_pollinate(cluster_a: int, cluster_b: int) -> str:
    """Link two intellectual clusters and find analogical patterns"""
    db = SessionLocal()
    from smos.services.discovery_service import DiscoveryService
    svc = DiscoveryService(db)
    svc.link_clusters(cluster_a, cluster_b, "SHARES_PATTERNS")
    db.close()
    return f"Clusters {cluster_a} and {cluster_b} cross-pollinated."

@mcp.tool()
def validate_understanding(agent_id: int, human_id: int, interpretation: str) -> str:
    """Start a human-AI understanding validation cycle"""
    db = SessionLocal()
    from smos.services.coevolution_service import CoevolutionService
    svc = CoevolutionService(db)
    val = svc.validate_understanding(agent_id, human_id, interpretation, "Awaiting feedback")
    val_id = val.id
    db.close()
    return f"Understanding Validation initiated with ID: {val_id}"

@mcp.tool()
def recover_knowledge(lk_id: int, hypothesis: str) -> str:
    """Add a new hypothesis to lost knowledge for potential recovery"""
    db = SessionLocal()
    from smos.services.lost_knowledge_service import LostKnowledgeService
    svc = LostKnowledgeService(db)
    h = svc.add_hypothesis(lk_id, hypothesis, 0.5)
    h_id = h.id
    db.close()
    return f"Hypothesis {h_id} added to Lost Knowledge {lk_id}"

@mcp.tool()
def translate_message(source_id: int, target_profile_id: int, content: str) -> str:
    """Translate a message to match a specific cognitive or behavioral profile"""
    db = SessionLocal()
    from smos.services.translator_service import TranslatorService
    svc = TranslatorService(db)
    trans = svc.translate_message(source_id, target_profile_id, content)
    rewrite = trans.suggested_rewrite
    db.close()
    return f"Suggested Rewrite: {rewrite}"

@mcp.tool()
def query_backward_impact(node_id: int, domain: str) -> str:
    """Find hidden influences of a piece of knowledge on other domains"""
    db = SessionLocal()
    from smos.services.impact_service import ImpactService
    svc = ImpactService(db)
    impact = svc.record_impact(node_id, domain, "UNKNOWN_CASCADE_EFFECT", 0.5)
    impact_id = impact.id
    db.close()
    return f"Backward impact recorded with ID: {impact_id}"

@mcp.tool()
def pollinate_knowledge(cluster_id: int) -> str:
    """Find related clusters and suggest knowledge transfer (pollination)"""
    db = SessionLocal()
    from smos.services.ecology_service import EcologyService
    svc = EcologyService(db)
    suggestions = svc.pollinate(cluster_id)
    db.close()
    return f"Pollination suggestions for cluster {cluster_id}: {suggestions}"

@mcp.tool()
def assess_value(node_id: int, benefit: float, impact: float) -> str:
    """Assess the value of knowledge based on human benefit and impact"""
    db = SessionLocal()
    from smos.services.value_service import ValueService
    svc = ValueService(db)
    assessment = svc.assess_knowledge_value(node_id, benefit, impact)
    val_id = assessment.id
    db.close()
    return f"Value Assessment created with ID: {val_id}, Score: {assessment.knowledge_value}"

@mcp.tool()
def fund_research(hypothesis_id: int, amount: float, sponsor_id: int) -> str:
    """Open a funding portal and sponsor a research hypothesis"""
    db = SessionLocal()
    from smos.services.research_service import ResearchService
    svc = ResearchService(db)
    portal = svc.open_portal(hypothesis_id)
    svc.sponsor_research(portal.id, sponsor_id, amount)
    db.close()
    return f"Research funded for hypothesis {hypothesis_id} with amount: {amount}"

@mcp.tool()
def verify_provenance(node_id: int) -> str:
    """Verify the origin and contributors of a piece of knowledge"""
    db = SessionLocal()
    from smos.models.ecology import ProvenanceRecord
    record = db.query(ProvenanceRecord).filter(ProvenanceRecord.node_id == node_id).first()
    db.close()
    return f"Provenance Record: {record.id if record else 'Not found'}"
