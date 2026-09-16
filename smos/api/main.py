from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
from smos.services.discovery_system import DiscoverySystem
from smos.services.discovery_service import DiscoveryService
from smos.services.lost_knowledge_service import LostKnowledgeService
from smos.services.coevolution_service import CoevolutionService
from smos.services.impact_service import ImpactService
from smos.services.translator_service import TranslatorService
from smos.services.ecology_engine import EcologyEngine, EcologyEngine as EcologyService
from smos.services.resonance_service import ResonanceService
from smos.services.signal_service import SignalService
from smos.services.causality_service import CausalityService
from smos.services.value_ecology_service import ValueEcologyService, ValueEcologyService as ValueService
from smos.services.research_service import ResearchService
from smos.services.sovereignty_service import SovereigntyService
from smos.services.federation_service import FederationService
from smos.services.economy_service import EconomyService
from smos.services.observatory_service import ObservatoryService
from smos.services.commons_service import CommonsService

# Core & Adapters
from smos.core.state import StateManager
from smos.core.queue import QueueManager
from smos.core.proposals import ProposalManager
from smos.core.events import EventTracker
from smos.core.task import Task, TaskStatus
from smos.adapters.jules_cli import JulesCLIAdapter

import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import os
from pgvector.sqlalchemy import Vector

app = FastAPI(title="Co-SMOS Control Room API", version="0.9")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


frontend_path = Path("frontend")
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

def _get_observatory(db: Session) -> ObservatoryService:
    eco = EcologyEngine(db)
    val = ValueEcologyService(db)
    com = CommonsService(db)
    disc = DiscoverySystem(db)
    res = ResearchService(db)
    return ObservatoryService(db, [eco, val, com, disc, res])

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

def _error_response(code: str, message: str, status_code: int = 400, exit_code: Optional[int] = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "code": code,
            "message": message,
            "exit_code": exit_code
        }
    )

class EventCreate(BaseModel):
    user_id: int
    workspace_id: Optional[int] = None
    stream_id: Optional[int] = None
    type: str
    content: Dict[str, Any]
    application: Optional[str] = None
    window_title: Optional[str] = None

class CreateTaskRequest(BaseModel):
    request: str
    priority: int = 5

class RunQueueRequest(BaseModel):
    mode: str = "once"
    dry_run: bool = False

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None

class ReorderQueueRequest(BaseModel):
    task_ids: List[str]

class ModifyProposalRequest(BaseModel):
    description: Optional[str] = None
    priority: Optional[int] = None

class CreateTwinRequest(BaseModel):
    owner_id: int
    goals: List[str]
    preferences: Dict[str, Any]

class CreateClusterRequest(BaseModel):
    name: str
    domains: List[str]

@app.get("/")
def read_root():
    index_file = Path("frontend/index.html")
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Welcome to Co-SMOS Control Room API"}

# --- CONTROL ROOM ENDPOINTS ---

@app.get("/api/system/status")
def get_system_status():
    sm = StateManager()
    return sm.get_system_status()

@app.get("/api/queue")
def get_queue_tasks():
    qm = QueueManager()
    tasks = qm.list_queue_tasks()
    return [t.model_dump() for t in tasks]

@app.post("/api/queue")
def add_task_to_queue(req: CreateTaskRequest):
    adapter = JulesCLIAdapter()
    res = adapter.add_task(description=req.request, priority=req.priority)
    if not res["success"]:
        return _error_response(
            code="TASK_CREATION_FAILED",
            message=res["error"] or "Failed to add task via CLI adapter",
            status_code=500,
            exit_code=res.get("exit_code")
        )
    qm = QueueManager()
    task_id = None
    if res.get("stdout"):
        for line in res["stdout"].splitlines():
            if "Task ID:" in line:
                task_id = line.split("Task ID:")[-1].strip()
                break
    latest_task = qm.get_task(task_id) if task_id else None
    if not latest_task:
        tasks = qm.list_all_tasks()
        if tasks:
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            latest_task = tasks[0]
    EventTracker.emit("task_created", task_id=latest_task.id if latest_task else None, payload={"request": req.request})
    return {"status": "success", "cli_output": res["stdout"], "task": latest_task.model_dump() if latest_task else None}

@app.post("/api/queue/run")
def run_queue(req: RunQueueRequest):
    adapter = JulesCLIAdapter()
    res = adapter.run_queue(mode=req.mode, dry_run=req.dry_run)
    if not res["success"]:
        return _error_response(
            code="QUEUE_RUN_FAILED",
            message=res["error"] or "Queue runner failed",
            status_code=500,
            exit_code=res.get("exit_code")
        )
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/queue/reorder")
def reorder_queue(req: ReorderQueueRequest):
    qm = QueueManager()
    reordered = qm.reorder_queue(req.task_ids)
    EventTracker.emit("queue_reordered", payload={"task_ids": req.task_ids})
    return {"status": "success", "reordered_tasks": [t.model_dump() for t in reordered]}

@app.get("/api/tasks")
def list_tasks():
    qm = QueueManager()
    tasks = qm.list_all_tasks()
    return [t.model_dump() for t in tasks]

@app.get("/api/tasks/{id}")
def get_task_by_id(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)
    return task.model_dump()

@app.patch("/api/tasks/{id}")
def update_task_by_id(id: str, req: UpdateTaskRequest):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    if req.title is not None:
        task.title = req.title
    if req.description is not None:
        task.description = req.description
    if req.priority is not None:
        task.priority = req.priority
    if req.status is not None:
        try:
            new_st = TaskStatus(req.status.upper())
            task.transition_to(new_st, message="Task status updated via API")
        except ValueError:
            return _error_response(code="INVALID_STATUS", message=f"Invalid task status: {req.status}")

    qm.save_task(task)
    EventTracker.emit("task_updated", task_id=id, payload=req.model_dump(exclude_unset=True))
    return task.model_dump()

@app.post("/api/tasks/{id}/start")
def start_task(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    task.transition_to(TaskStatus.RUNNING, message="Task started via API")
    qm.save_task(task)
    EventTracker.emit("task_started", task_id=id)

    # Optionally trigger CLI runner dry-run or process
    adapter = JulesCLIAdapter()
    res = adapter.run_queue(mode="once", dry_run=False)
    return {"status": "success", "task": task.model_dump(), "runner_output": res.get("stdout")}

@app.post("/api/tasks/{id}/cancel")
def cancel_task(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    task.transition_to(TaskStatus.CANCELLED, message="Task cancelled via API")
    qm.save_task(task)
    EventTracker.emit("task_cancelled", task_id=id)
    return {"status": "success", "task": task.model_dump()}

@app.get("/api/proposals")
def list_proposals(status: Optional[str] = None):
    pm = ProposalManager()
    props = pm.list_proposals(status=status)
    return [p.model_dump() for p in props]

@app.get("/api/proposals/{id}")
def get_proposal_by_id(id: str):
    pm = ProposalManager()
    prop = pm.get_proposal(id)
    if not prop:
        return _error_response(code="PROPOSAL_NOT_FOUND", message=f"Proposal with ID {id} not found", status_code=404)
    return prop.model_dump()

@app.post("/api/proposals/{id}/accept")
def accept_proposal(id: str):
    adapter = JulesCLIAdapter()
    res = adapter.accept_proposal(id)
    if not res["success"]:
        return _error_response(code="PROPOSAL_ACCEPT_FAILED", message=res["error"] or "Failed to accept proposal", exit_code=res.get("exit_code"))
    EventTracker.emit("proposal_accepted", payload={"proposal_id": id})
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/proposals/{id}/defer")
def defer_proposal(id: str):
    adapter = JulesCLIAdapter()
    res = adapter.defer_proposal(id)
    if not res["success"]:
        return _error_response(code="PROPOSAL_DEFER_FAILED", message=res["error"] or "Failed to defer proposal", exit_code=res.get("exit_code"))
    EventTracker.emit("proposal_deferred", payload={"proposal_id": id})
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/proposals/{id}/reject")
def reject_proposal(id: str):
    adapter = JulesCLIAdapter()
    res = adapter.reject_proposal(id)
    if not res["success"]:
        return _error_response(code="PROPOSAL_REJECT_FAILED", message=res["error"] or "Failed to reject proposal", exit_code=res.get("exit_code"))
    EventTracker.emit("proposal_rejected", payload={"proposal_id": id})
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/proposals/{id}/modify")
def modify_proposal(id: str, req: ModifyProposalRequest):
    pm = ProposalManager()
    prop = pm.modify_proposal(id, new_description=req.description, new_priority=req.priority)
    if not prop:
        return _error_response(code="PROPOSAL_NOT_FOUND", message=f"Proposal with ID {id} not found", status_code=404)
    EventTracker.emit("proposal_modified", payload={"proposal_id": id})
    return {"status": "success", "proposal": prop.model_dump()}

@app.get("/api/events")
def get_system_events(task_id: Optional[str] = None, limit: int = 50):
    events = EventTracker.list_events(task_id=task_id, limit=limit)
    return [e.model_dump() for e in events]

@app.get("/api/events/{id}")
def get_event_by_id(id: str):
    evt = EventTracker.get_event(id)
    if not evt:
        return _error_response(code="EVENT_NOT_FOUND", message=f"Event with ID {id} not found", status_code=404)
    return evt.model_dump()

@app.get("/api/tasks/{id}/history")
def get_task_history(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)
    return {
        "task_id": id,
        "history": [h.model_dump() for h in task.history],
        "events": [e.model_dump() for e in EventTracker.list_events(task_id=id)]
    }

@app.get("/api/tasks/{id}/dependencies")
def get_task_dependencies(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)
    return {
        "task_id": id,
        "depends_on": [],
        "blocks": []
    }

@app.get("/api/tasks/{id}/replay")
def get_task_replay(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    timeline = []
    for h in task.history:
        st_val = h.status.value if isinstance(h.status, TaskStatus) else str(h.status)
        msg_val = h.message or f"Task state transitioned to {st_val}"
        timeline.append({
            "timestamp": h.timestamp,
            "status": st_val,
            "message": msg_val
        })

    events = EventTracker.list_events(task_id=id, limit=1000)
    for e in events:
        msg = e.payload.get("message") or e.payload.get("request") or f"Event: {e.type}"
        timeline.append({
            "timestamp": e.timestamp,
            "status": e.type.upper(),
            "message": msg
        })

    timeline.sort(key=lambda x: x["timestamp"])

    return {
        "task_id": id,
        "timeline": timeline
    }

@app.post("/api/tasks/{id}/retry")
def retry_task(id: str):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    task_status_str = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
    if task_status_str.upper() not in ("FAILED", "CANCELLED", "BLOCKED"):
        return _error_response(
            code="RETRY_NOT_ALLOWED",
            message=f"Task status '{task_status_str}' does not allow retry. Retry is only allowed for FAILED, CANCELLED, or BLOCKED tasks.",
            status_code=400
        )

    req_text = task.request or task.description or ""
    adapter = JulesCLIAdapter()
    res = adapter.add_task(description=req_text, priority=task.priority)
    if not res["success"]:
        return _error_response(
            code="TASK_CREATION_FAILED",
            message=res["error"] or "Failed to retry task via CLI adapter",
            status_code=500,
            exit_code=res.get("exit_code")
        )

    qm = QueueManager()
    new_task_id = None
    if res.get("stdout"):
        for line in res["stdout"].splitlines():
            if "Task ID:" in line:
                new_task_id = line.split("Task ID:")[-1].strip()
                break

    new_task = qm.get_task(new_task_id) if new_task_id else None
    if not new_task:
        pending_tasks = [t for t in qm.list_all_tasks() if t.status in (TaskStatus.PENDING, TaskStatus.READY)]
        if pending_tasks:
            pending_tasks.sort(key=lambda t: t.created_at, reverse=True)
            new_task = pending_tasks[0]

    if not new_task:
        return _error_response(
            code="TASK_CREATION_FAILED",
            message="Retry task was created but could not be retrieved from queue",
            status_code=500
        )

    if task.title:
        new_task.title = task.title
    if task.description:
        new_task.description = task.description
    new_task.source_task = task.id
    qm.save_task(new_task)

    EventTracker.emit("task_retried", task_id=new_task.id, payload={"original_task_id": id})
    return new_task.model_dump()

@app.get("/api/graph")
def get_task_graph():
    qm = QueueManager()
    tasks = qm.list_all_tasks()
    nodes = []
    for t in tasks:
        st_val = t.status.value if isinstance(t.status, TaskStatus) else str(t.status)
        nodes.append({
            "id": t.id,
            "status": st_val,
            "priority": t.priority,
            "title": t.title or t.request or t.id
        })
    return {
        "nodes": nodes,
        "edges": []
    }

@app.get("/api/search")
def search_control_room(q: str = "", limit: int = 50):
    if not q or not q.strip():
        return {"tasks": [], "proposals": [], "events": []}

    query_str = q.strip().lower()

    qm = QueueManager()
    all_tasks = qm.list_all_tasks()
    matched_tasks = []
    for t in all_tasks:
        text = f"{t.id} {t.request or ''} {t.title or ''} {t.description or ''}".lower()
        if query_str in text:
            matched_tasks.append(t.model_dump())

    pm = ProposalManager()
    all_props = pm.list_proposals()
    matched_props = []
    for p in all_props:
        text = f"{p.id} {p.description or ''} {p.proposed_by or ''}".lower()
        if query_str in text:
            matched_props.append(p.model_dump())

    all_events = EventTracker.list_events(limit=1000)
    matched_events = []
    for e in all_events:
        text = f"{e.id} {e.type or ''} {e.task_id or ''} {e.source or ''} {str(e.payload or '')}".lower()
        if query_str in text:
            matched_events.append(e.model_dump())

    return {
        "tasks": matched_tasks[:limit],
        "proposals": matched_props[:limit],
        "events": matched_events[:limit]
    }

# --- CONSULT ACCESS ENDPOINTS (READ-ONLY) ---

_consult_request_count = 0

def _track_consult_request():
    global _consult_request_count
    _consult_request_count += 1

@app.get("/api/consult/state")
def get_consult_state():
    _track_consult_request()
    sm = StateManager()
    return {
        "read_only": True,
        "request_count": _consult_request_count,
        "system_status": sm.get_system_status()
    }

@app.get("/api/consult/tasks")
def get_consult_tasks():
    _track_consult_request()
    qm = QueueManager()
    tasks = qm.list_all_tasks()
    return [t.model_dump() for t in tasks]

@app.get("/api/consult/task/{id}")
def get_consult_task_by_id(id: str):
    _track_consult_request()
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)
    return task.model_dump()

@app.get("/api/consult/events")
def get_consult_events(limit: int = 100):
    _track_consult_request()
    events = EventTracker.list_events(limit=limit)
    return [e.model_dump() for e in events]

@app.get("/api/consult/errata")
def get_consult_errata():
    _track_consult_request()
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
    errata_dir = project_root / ".jules" / "errata"
    errata_files = {}
    index = []
    if errata_dir.exists() and errata_dir.is_dir():
        for path in sorted(errata_dir.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
                errata_files[path.name] = content
                index.append(path.name)
            except Exception:
                pass
    return {
        "index": index,
        "files": errata_files
    }

@app.get("/api/consult/health")
def get_consult_health():
    _track_consult_request()
    return {
        "status": "ok",
        "read_only": True,
        "service": "consult_access",
        "request_count": _consult_request_count
    }

# --- EXISTING LEGACY ENDPOINTS ---

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
def start_session(topic: str, timeline_id: int, participants: List[int], workspace_id: Optional[int] = None, db: Session = Depends(get_db)):
    svc = CognitiveService(db)
    return svc.create_session(workspace_id, topic, timeline_id, participants)

@app.post("/recipe")
def create_recipe(title: str, author_id: int, steps: List[str], problem_type: str, db: Session = Depends(get_db)):
    svc = RecipeService(db)
    return svc.create_recipe(title, author_id, steps, problem_type)

@app.post("/twin")
def create_twin(req: CreateTwinRequest, db: Session = Depends(get_db)):
    svc = TwinService(db)
    return svc.create_twin(req.owner_id, req.goals, req.preferences)

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
def create_intellectual_cluster(req: CreateClusterRequest, db: Session = Depends(get_db)):
    svc = DiscoveryService(db)
    return svc.create_cluster(req.name, req.domains)

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
def open_research_portal(hypothesis_id: int, initial_budget: float = 0.0, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    return svc.open_portal(hypothesis_id, initial_budget=initial_budget)

@app.get("/research/portals")
def list_research_portals(status: Optional[str] = None, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    return svc.list_portals(status=status)

@app.get("/research/portal/{portal_id}")
def get_research_portal(portal_id: int, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    portal = svc.get_portal(portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="Research portal not found")
    return portal

@app.post("/research/sponsor")
def sponsor_research(portal_id: int, sponsor_id: int, amount: float, is_transparent: bool = True, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    return svc.sponsor_research(portal_id, sponsor_id, amount, is_transparent=is_transparent)

@app.post("/research/portal/{portal_id}/outcome")
def record_portal_outcome(portal_id: int, outcome: str, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    portal = svc.record_outcome(portal_id, outcome)
    if not portal:
        raise HTTPException(status_code=404, detail="Research portal not found")
    return portal

@app.post("/research/portal/{portal_id}/close")
def close_research_portal(portal_id: int, reason: Optional[str] = None, db: Session = Depends(get_db)):
    svc = ResearchService(db)
    portal = svc.close_portal(portal_id, reason=reason)
    if not portal:
        raise HTTPException(status_code=404, detail="Research portal not found")
    return portal

@app.post("/reputation/credit")
def issue_credit(cosmonaut_id: int, amount: float, reason: str, db: Session = Depends(get_db)):
    svc = EconomyService(db)
    return svc.issue_reputation_credits(cosmonaut_id, amount, reason)

@app.post("/federation/node")
def register_federated_node(name: str, endpoint_url: str, trust_score: float = 1.0, sovereignty_level: str = "HIGH", db: Session = Depends(get_db)):
    svc = FederationService(db)
    return svc.register_node(name, endpoint_url, trust_score, sovereignty_level)

@app.get("/federation/nodes")
def list_federated_nodes(db: Session = Depends(get_db)):
    svc = FederationService(db)
    return svc.list_nodes()

@app.post("/federation/sync")
def sync_federated_knowledge(source_node_id: int, payload: Dict[str, Any], target_timeline_id: int, target_owner_id: int, db: Session = Depends(get_db)):
    svc = FederationService(db)
    return svc.sync_knowledge_from_node(source_node_id, payload, target_timeline_id, target_owner_id)

@app.get("/federation/sovereignty/{node_id}")
def evaluate_sovereignty(node_id: int, db: Session = Depends(get_db)):
    svc = FederationService(db)
    return svc.evaluate_sovereignty_policy(node_id)

@app.get("/provenance/{node_id}")
def get_provenance(node_id: int, db: Session = Depends(get_db)):
    from smos.models.ecology import ProvenanceRecord
    return db.query(ProvenanceRecord).filter(ProvenanceRecord.node_id == node_id).first()

@app.get("/observatory/health")
def get_observatory_health(db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    return obs.get_health_report()

@app.get("/observatory/proposals")
def get_observatory_proposals(db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    return obs.get_proposal_metrics()

@app.get("/observatory/report")
def get_observatory_report(db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    return obs.generate_quarterly_report()

@app.get("/observatory/ranking")
def get_observatory_ranking(limit: int = 10, db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    return obs.get_impact_ranking(limit)

@app.get("/observatory/recommendations")
def get_observatory_recommendations(db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    return obs.generate_recommendations()

@app.get("/observatory/export/json")
def export_observatory_json(db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    json_str = obs.export_report_json()
    return Response(content=json_str, media_type="application/json")

@app.get("/observatory/export/markdown")
def export_observatory_markdown(db: Session = Depends(get_db)):
    obs = _get_observatory(db)
    md_str = obs.export_report_markdown()
    return Response(content=md_str, media_type="text/markdown")

@app.get("/memory/search")
def search_memory(q: str, user_id: int, limit: int = 20, db: Session = Depends(get_db)):
    import os
    is_sqlite = os.getenv("DATABASE_URL", "").startswith("sqlite")

    base_query = db.query(MemoryNode).filter(
        (MemoryNode.owner_id == user_id) | (MemoryNode.workspace_id.isnot(None))
    )

    query_embedding = embedding_service.get_embedding(q)

    if is_sqlite:
        nodes = base_query.all()
        scored_nodes = []
        for node in nodes:
            if node.embeddings:
                score = _cosine_similarity(query_embedding, node.embeddings)
            else:
                score = -1.0
            scored_nodes.append((node, score))
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        results = [node for node, _ in scored_nodes[:limit]]
    else:
        results = base_query.order_by(
            MemoryNode.embeddings.l2_distance(query_embedding)
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