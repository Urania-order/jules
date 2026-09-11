from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from smos.core.database import get_db
from smos.models.models import Event as DBEvent, User, Workspace, MemoryNode
from smos.services.embedding_service import embedding_service
from smos.services.orchestrator import AgentOrchestrator
from smos.services.permissions import PermissionService
from smos.services.timeline_service import TimelineService
from smos.services.cognitive_service import CognitiveService
from smos.services.recipe_service import RecipeService
from smos.services.twin_service import TwinService
from smos.services.execution_service import ExecutionService
from smos.services.evolution_service import EvolutionService
from smos.services.community_service import CommunityService
from smos.services.reconstruction_service import ReconstructionService
from smos.services.epistemic_service import EpistemicService
from smos.services.discovery_system import DiscoverySystem as DiscoveryService
from smos.services.lost_knowledge_service import LostKnowledgeService
from smos.services.coevolution_service import CoevolutionService
from smos.services.impact_service import ImpactService
from smos.services.translator_service import TranslatorService
from smos.services.ecology_engine import EcologyEngine as EcologyService
from smos.services.resonance_service import ResonanceService
from smos.services.signal_service import SignalService
from smos.services.causality_service import CausalityService
from smos.services.value_ecology_service import ValueEcologyService as ValueService
from smos.services.research_service import ResearchService
from smos.services.sovereignty_service import SovereigntyService
from smos.services.economy_service import EconomyService
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from pgvector.sqlalchemy import Vector

app = FastAPI(title="Co-SMOS API", version="0.1")

class EventCreate(BaseModel):
    user_id: int
    workspace_id: Optional[int] = None
    stream_id: Optional[int] = None
    type: str
    content: Dict[str, Any]
    application: Optional[str] = None
    window_title: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "Welcome to Co-SMOS API"}

@app.post("/event")
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    if event.workspace_id:
        PermissionService.verify_workspace_access(db, event.user_id, event.workspace_id)

    db_event = DBEvent(
        user_id=event.user_id,
        workspace_id=event.workspace_id,
        stream_id=event.stream_id,
        type=event.type,
        content=event.content,
        application=event.application,
        window_title=event.window_title
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # Trigger Orchestrator
    orchestrator = AgentOrchestrator(db)
    orchestrator.on_event(db_event)

    return db_event

@app.get("/events")
def get_events(db: Session = Depends(get_db)):
    return db.query(DBEvent).all()

@app.post("/timeline/fork")
def fork_timeline(parent_id: int, description: str, db: Session = Depends(get_db)):
    svc = TimelineService(db)
    return svc.fork_timeline(parent_id, description)

@app.post("/cognitive/session")
def start_session(workspace_id: Optional[int], topic: str, timeline_id: int, participants: List[int], db: Session = Depends(get_db)):
    svc = CognitiveService(db)
    return svc.create_session(workspace_id, topic, timeline_id, participants)

@app.post("/recipe")
def create_recipe(title: str, author_id: int, steps: List[str], problem_type: str, db: Session = Depends(get_db)):
    svc = RecipeService(db)
    return svc.create_recipe(title, author_id, steps, problem_type)

@app.post("/twin")
def create_twin(owner_id: int, goals: List[str], preferences: Dict[str, Any], db: Session = Depends(get_db)):
    svc = TwinService(db)
    return svc.create_twin(owner_id, goals, preferences)

@app.post("/recipe/execute")
def execute_recipe(recipe_id: int, participants: List[int], result: str, db: Session = Depends(get_db)):
    svc = ExecutionService(db)
    return svc.record_execution(recipe_id, participants, result)

@app.post("/recipe/evolve")
def evolve_recipe(parent_id: int, mutations: List[Dict[str, Any]], db: Session = Depends(get_db)):
    svc = EvolutionService(db)
    return svc.evolve_recipe(parent_id, mutations)

@app.post("/community/constellation")
def create_constellation(mission: str, members: List[int], db: Session = Depends(get_db)):
    svc = CommunityService(db)
    return svc.create_constellation(mission, members)

@app.post("/reconstruct")
def reconstruct(observations: List[str], artifacts: List[str], witnesses: List[str], db: Session = Depends(get_db)):
    svc = ReconstructionService(db)
    return svc.reconstruct_experience(observations, artifacts, witnesses)

@app.post("/epistemic/layer")
def create_epistemic_layer(name: str, confidence: float, evidence_type: str, db: Session = Depends(get_db)):
    svc = EpistemicService(db)
    return svc.create_layer(name, confidence, evidence_type)

@app.post("/cluster")
def create_intellectual_cluster(name: str, domains: List[str], db: Session = Depends(get_db)):
    svc = DiscoveryService(db)
    return svc.create_cluster(name, domains)

@app.post("/validate-understanding")
def validate_understanding(agent_id: int, human_id: int, original: str, feedback: str, db: Session = Depends(get_db)):
    svc = CoevolutionService(db)
    return svc.validate_understanding(agent_id, human_id, original, feedback)

@app.post("/impact")
def record_impact(node_id: int, domain: str, impact_type: str, confidence: float, db: Session = Depends(get_db)):
    svc = ImpactService(db)
    return svc.record_impact(node_id, domain, impact_type, confidence)

@app.post("/translate")
def translate(source_id: int, target_profile_id: int, content: str, db: Session = Depends(get_db)):
    svc = TranslatorService(db)
    return svc.translate_message(source_id, target_profile_id, content)

@app.get("/pollinate/{cluster_id}")
def pollinate(cluster_id: int, db: Session = Depends(get_db)):
    svc = EcologyService(db)
    return svc.pollinate(cluster_id)

@app.post("/resonance")
def record_resonance(source_id: int, target_id: int, strength: float, delay: int = 0, db: Session = Depends(get_db)):
    svc = ResonanceService(db)
    return svc.record_resonance(source_id, target_id, strength, delay)

@app.post("/causal-chain")
def discover_chain(origin_node_id: int, events: List[str], confidence: float, db: Session = Depends(get_db)):
    svc = CausalityService(db)
    return svc.discover_causal_chain(origin_node_id, events, confidence)

@app.post("/signal")
def emit_signal(node_id: int, target_cluster_id: Optional[int] = None, strength: float = 0.5, db: Session = Depends(get_db)):
    svc = SignalService(db)
    return svc.emit_signal(node_id, target_cluster_id, strength=strength)

@app.post("/value/assess")
def assess_value(node_id: int, benefit: float, impact: float, db: Session = Depends(get_db)):
    svc = ValueService(db)
    return svc.assess_knowledge_value(node_id, benefit, impact)

@app.post("/research/portal")
def open_research_portal(hypothesis_id: int, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    return svc.open_portal(hypothesis_id)

@app.post("/research/sponsor")
def sponsor_research(portal_id: int, sponsor_id: int, amount: float, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    return svc.sponsor_research(portal_id, sponsor_id, amount)

@app.post("/reputation/credit")
def issue_credit(cosmonaut_id: int, amount: float, reason: str, db: Session = Depends(get_db)):
    svc = EconomyService(db)
    return svc.issue_reputation_credits(cosmonaut_id, amount, reason)

@app.get("/provenance/{node_id}")
def get_provenance(node_id: int, db: Session = Depends(get_db)):
    from smos.models.ecology import ProvenanceRecord
    return db.query(ProvenanceRecord).filter(ProvenanceRecord.node_id == node_id).first()

@app.get("/memory/search")
def search_memory(q: str, user_id: int, limit: int = 20, db: Session = Depends(get_db)):
    import os
    is_sqlite = os.getenv("DATABASE_URL", "").startswith("sqlite")

    base_query = db.query(MemoryNode).filter(
        (MemoryNode.owner_id == user_id) | (MemoryNode.workspace_id.isnot(None))
    )

    if is_sqlite:
        results = base_query.filter(MemoryNode.content.ilike(f"%{q}%")).limit(limit).all()
        if not results:
            results = base_query.limit(limit).all()
    else:
        embedding = embedding_service.get_embedding(q)
        results = base_query.order_by(
            MemoryNode.embeddings.l2_distance(embedding)
        ).limit(limit).all()

    return [
        {
            "id": r.id,
            "content": r.content,
            "type": r.type,
            "reality_level": r.reality_level,
        }
        for r in results
    ]
