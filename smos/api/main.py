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
from smos.core.state import StateManager, normalize_created_at_state
from smos.core.queue import QueueManager
from smos.core.proposals import ProposalManager, Proposal
from smos.core.events import EventTracker
from smos.core.task import Task, TaskStatus
from smos.core.batch import BatchManager, Batch
from smos.core.scheduler import Scheduler
from smos.core.queue_reset import QueueResetManager, ResetScheduleManager, write_audit_entry, get_audit_entries
from smos.core.templates import TemplateManager
from smos.core.sequences import SequenceManager
from smos.core.batch import BatchManager, Batch, BatchTemplateManager
from smos.adapters.jules_cli import JulesCLIAdapter
from smos.core.consult import consult_settings_manager, consult_audit_logger

import asyncio
import contextlib
import hmac
import json
import logging
import numpy as np
import re
import shlex
import shutil
import subprocess
import threading
import time
import uuid
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
import os
from pgvector.sqlalchemy import Vector

logger = logging.getLogger(__name__)

scheduler_instance = Scheduler()

async def background_scheduler_loop():
    logger.info("Starting background scheduler loop")
    while True:
        try:
            scheduler_instance.check_due_batches()
            rsm = ResetScheduleManager()
            rsm.check_and_run_due_schedules()
        except Exception as e:
            logger.error("Error in background scheduler loop: %s", e)
        await asyncio.sleep(60)

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    log_default_token_warning_once()
    try:
        from smos.core.init_db import init_db
        init_db()
        logger.info("Database tables initialized (idempotent).")
    except Exception as e:
        logger.warning(f"init_db failed: {e}")
    try:
        normalize_created_at_state(".co-smos/state.json")
    except Exception as e:
        logger.warning(f"normalize_created_at failed: {e}")
    scheduler_task = asyncio.create_task(background_scheduler_loop())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Co-SMOS Control Room API", version="0.9", lifespan=lifespan)

CONSULTANT_TOKEN_ENV = "JULES_CONSULTANT_TOKEN"
OPERATOR_TOKEN_ENV = "JULES_OPERATOR_TOKEN"
ADMIN_TOKEN_ENV = "JULES_ADMIN_TOKEN"

DEFAULT_CONSULTANT_TOKEN = "dev-consultant-token"
DEFAULT_OPERATOR_TOKEN = "dev-operator-token"
DEFAULT_ADMIN_TOKEN = "dev-admin-token"

_warning_logged = False

def log_default_token_warning_once():
    global _warning_logged
    if _warning_logged:
        return
    c_tok = os.environ.get(CONSULTANT_TOKEN_ENV, DEFAULT_CONSULTANT_TOKEN)
    o_tok = os.environ.get(OPERATOR_TOKEN_ENV, DEFAULT_OPERATOR_TOKEN)
    a_tok = os.environ.get(ADMIN_TOKEN_ENV, DEFAULT_ADMIN_TOKEN)

    if (c_tok == DEFAULT_CONSULTANT_TOKEN and 
        o_tok == DEFAULT_OPERATOR_TOKEN and 
        a_tok == DEFAULT_ADMIN_TOKEN):
        logger.warning("All Co-SMOS tokens are set to default development values.")
        _warning_logged = True


class AuthException(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code

@app.exception_handler(AuthException)
async def auth_exception_handler(request: Request, exc: AuthException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.code,
            "message": exc.message,
            "exit_code": None
        }
    )

def resolve_role_from_request(request: Request) -> str:
    log_default_token_warning_once()

    # Public health check exception
    if request.url.path == "/api/consult/health" and request.query_params.get("public") == "1":
        return "public"

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthException(
            code="CONSULT_AUTH_REQUIRED",
            message="Authorization header with Bearer token is required",
            status_code=401
        )

    token = auth_header[7:].strip()
    if not token:
        raise AuthException(
            code="CONSULT_AUTH_REQUIRED",
            message="Bearer token cannot be empty",
            status_code=401
        )

    settings = consult_settings_manager.get_settings()
    tokens_cfg = settings.get("tokens", {})

    c_info = tokens_cfg.get("consultant", {})
    o_info = tokens_cfg.get("operator", {})
    a_info = tokens_cfg.get("admin", {})

    c_tok = c_info.get("token") or os.environ.get(CONSULTANT_TOKEN_ENV, DEFAULT_CONSULTANT_TOKEN)
    o_tok = o_info.get("token") or os.environ.get(OPERATOR_TOKEN_ENV, DEFAULT_OPERATOR_TOKEN)
    a_tok = a_info.get("token") or os.environ.get(ADMIN_TOKEN_ENV, DEFAULT_ADMIN_TOKEN)

    token_bytes = token.encode("utf-8")
    matched_role = None

    if hmac.compare_digest(token_bytes, a_tok.encode("utf-8")):
        matched_role = "admin"
    elif hmac.compare_digest(token_bytes, o_tok.encode("utf-8")):
        matched_role = "operator"
    elif hmac.compare_digest(token_bytes, c_tok.encode("utf-8")):
        matched_role = "consultant"

    if matched_role is None:
        raise AuthException(
            code="CONSULT_AUTH_INVALID",
            message="Invalid authorization token",
            status_code=403
        )

    role_cfg = tokens_cfg.get(matched_role, {})
    if role_cfg.get("status") == "disabled":
        raise AuthException(
            code="CONSULT_AUTH_INVALID",
            message=f"Token for role '{matched_role}' is disabled",
            status_code=403
        )

    if request.url.path.startswith("/api/consult"):
        if not consult_settings_manager.check_rate_limit(matched_role):
            raise AuthException(
                code="CONSULT_RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded for role '{matched_role}'",
                status_code=429
            )

    return matched_role

def require_roles(allowed_roles: List[str]):
    def dependency(request: Request) -> str:
        role = resolve_role_from_request(request)
        if role == "public" and "public" in allowed_roles:
            return role
        if role not in allowed_roles:
            raise AuthException(
                code="CONSULT_ROLE_FORBIDDEN",
                message=f"Role '{role}' is forbidden from accessing this resource",
                status_code=403
            )
        return role
    return dependency

require_consultant = require_roles(["consultant", "operator", "admin"])
require_consultant_or_public = require_roles(["public", "consultant", "operator", "admin"])
require_operator = require_roles(["operator", "admin"])
require_admin = require_roles(["admin"])

def check_consult_endpoint_enabled(endpoint_key: str):
    if not consult_settings_manager.is_endpoint_enabled(endpoint_key):
        raise AuthException(
            code="CONSULT_ENDPOINT_DISABLED",
            message=f"Consult endpoint '{endpoint_key}' is disabled",
            status_code=403
        )

@app.middleware("http")
async def consult_audit_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api/consult"):
        return await call_next(request)

    response = await call_next(request)

    role = "unauthenticated"
    try:
        if request.url.path == "/api/consult/health" and request.query_params.get("public") == "1":
            role = "public"
        else:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                tok = auth_header[7:].strip()
                settings = consult_settings_manager.get_settings()
                tokens_cfg = settings.get("tokens", {})
                for r in ["admin", "operator", "consultant"]:
                    r_info = tokens_cfg.get(r, {})
                    r_tok = r_info.get("token") or os.environ.get(f"JULES_{r.upper()}_TOKEN", f"dev-{r}-token")
                    if hmac.compare_digest(tok.encode("utf-8"), r_tok.encode("utf-8")):
                        role = r
                        break
    except Exception:
        pass

    consult_audit_logger.log_request(
        role=role,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code
    )

    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080", "http://127.0.0.1:8080"],
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

class CreateProposalRequest(BaseModel):
    description: str
    priority: int = 3
    source_task: Optional[str] = None
    proposed_by: Optional[str] = "operator"

class RunQueueRequest(BaseModel):
    mode: str = "once"
    dry_run: bool = False

class QueueResetRequest(BaseModel):
    confirm: str
    scope: str = "all"

class QueueResetColumnRequest(BaseModel):
    column: str
    confirm: str

class ResetScheduleCreateRequest(BaseModel):
    name: str
    cron: str
    scope: str
    enabled: bool = True

class ResetScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    scope: Optional[str] = None
    enabled: Optional[bool] = None

class ArchiveUndoRequest(BaseModel):
    archive_ids: List[str]
    confirm: str

class ArchiveUndoFilterRequest(BaseModel):
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    scope: Optional[str] = None
    search: Optional[str] = None
    confirm: str = ""
    dry_run: bool = False

class RememberTaskRequest(BaseModel):
    name: str

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    request: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None

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

class BatchRunRequest(BaseModel):
    task_ids: List[str]
    schedule: str = "now"
    concurrency: int = Field(default=3, ge=1, le=10)
    autonomy: str = "MANUAL"
    confirm: bool = False

class ScheduleRegisterRequest(BaseModel):
    name: str
    config: Dict[str, Any]

class ConsultSettingsPatchRequest(BaseModel):
    rate_limits: Optional[Dict[str, Optional[int]]] = None
    endpoints: Optional[Dict[str, bool]] = None
    tokens: Optional[Dict[str, Dict[str, Any]]] = None

class SequenceRecordStopRequest(BaseModel):
    name: Optional[str] = None

class SequenceReplayRequest(BaseModel):
    mode: str = "sequential"
    schedule: str = "now"
    concurrency: int = 3

class BatchRememberRequest(BaseModel):
    name: str
    task_ids: List[str]
    concurrency: int = 3
    schedule: str = "now"

class AdminRunRequest(BaseModel):
    command: str
    args: str = ""

class AdminQueueAddRequest(BaseModel):
    text: str
    verify_task: Optional[str] = None

RUN_JOBS: Dict[str, Dict[str, Any]] = {}

def _run_job_worker(job_id: str, filename: str, proc: subprocess.Popen, project_root: Path, running_txt: Path, running_meta: Path, meta_filename: str, role: str, t0: float):
    completed_dir = project_root / ".jules" / "queue" / "completed"
    queue_dir = project_root / ".jules" / "queue"

    try:
        stdout, stderr = proc.communicate(timeout=1200)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        exit_code = 124
        stderr = (stderr or "") + "\nrun-task.sh timed out after 1200 seconds."
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = str(e)

    finished_at = datetime.now(timezone.utc).isoformat()
    duration_ms = int((time.time() - t0) * 1000)

    task_id = None
    if stdout:
        match = re.search(r"task-[0-9]{8}-[0-9]{6}", stdout)
        if match:
            task_id = match.group(0)

    if job_id in RUN_JOBS:
        if RUN_JOBS[job_id].get("status") in ("cancelled", "killed"):
            return

    if exit_code == 0:
        completed_txt = completed_dir / filename
        if running_txt.exists():
            shutil.move(str(running_txt), str(completed_txt))
        if running_meta.exists():
            completed_meta = completed_dir / meta_filename
            shutil.move(str(running_meta), str(completed_meta))
        job_status = "completed"
    else:
        runner_log = queue_dir / "runner.log"
        log_entry = f"[{datetime.now(timezone.utc).isoformat()}] Task {filename} failed with exit code {exit_code}:\nSTDOUT: {stdout}\nSTDERR: {stderr}\n"
        with open(runner_log, "a", encoding="utf-8") as f:
            f.write(log_entry)
        job_status = "failed"

    write_admin_audit_entry(
        command="queue/run-next",
        args=filename,
        exit_code=exit_code,
        by=role,
        duration_ms=duration_ms
    )

    if job_id in RUN_JOBS:
        RUN_JOBS[job_id].update({
            "status": job_status,
            "finished_at": finished_at,
            "task_id": task_id,
            "exit_code": exit_code,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "duration_ms": duration_ms
        })

def _move_job_file_to_deferred(project_root: Path, filename: str):
    queue_dir = project_root / ".jules" / "queue"
    deferred_dir = queue_dir / "deferred"
    deferred_dir.mkdir(parents=True, exist_ok=True)

    meta_filename = Path(filename).stem + ".meta.json"

    for src_folder in ["running", "blocked", "pending"]:
        src_dir = queue_dir / src_folder
        txt_path = src_dir / filename
        if txt_path.exists():
            dest_path = deferred_dir / filename
            shutil.move(str(txt_path), str(dest_path))
        meta_path = src_dir / meta_filename
        if meta_path.exists():
            dest_meta = deferred_dir / meta_filename
            shutil.move(str(meta_path), str(dest_meta))

ADMIN_COMMAND_WHITELIST = {
    "test": {
        "exec": "./scripts/test.sh",
        "fixed_args": [],
        "timeout": 300,
    },
    "verify": {
        "exec": "./scripts/verify.sh",
        "fixed_args": ["--all"],
        "timeout": 60,
    },
    "verify-task": {
        "exec": "./scripts/verify.sh",
        "fixed_args": ["--task"],
        "timeout": 60,
    },
    "run-task": {
        "exec": "./scripts/run-task.sh",
        "fixed_args": [],
        "timeout": 1200,
    },
    "task": {
        "exec": "./scripts/jules-task.sh",
        "fixed_args": [],
        "timeout": 60,
    },
    "complete": {
        "exec": "./scripts/jules-complete.sh",
        "fixed_args": ["--task"],
        "timeout": 60,
    },
    "status": {
        "exec": "jules",
        "fixed_args": ["remote", "list", "--session"],
        "timeout": 60,
    },
    "git-log": {
        "exec": "git",
        "fixed_args": ["log", "--oneline", "-10"],
        "timeout": 60,
    },
    "git-status": {
        "exec": "git",
        "fixed_args": ["status", "--short"],
        "timeout": 60,
    },
}

def write_admin_audit_entry(command: str, args: str, exit_code: Optional[int], by: str, duration_ms: int):
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
    history_dir = project_root / ".jules" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    audit_file = history_dir / "admin_audit.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "args": args,
        "exit_code": exit_code,
        "by": by,
        "duration_ms": duration_ms
    }
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_admin_audit_entries(limit: int = 50) -> List[Dict[str, Any]]:
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
    audit_file = project_root / ".jules" / "history" / "admin_audit.jsonl"
    if not audit_file.exists():
        return []
    entries = []
    try:
        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception as e:
        logger.error("Error reading admin audit log: %s", e)
    entries.reverse()
    return entries[:limit]

@app.post("/api/admin/run", dependencies=[Depends(require_operator)])
def run_admin_command(req: AdminRunRequest, role: str = Depends(require_operator)):
    if req.command not in ADMIN_COMMAND_WHITELIST:
        write_admin_audit_entry(
            command=req.command,
            args=req.args,
            exit_code=400,
            by=role,
            duration_ms=0
        )
        return _error_response(
            code="UNKNOWN_COMMAND",
            message=f"Command '{req.command}' is not whitelisted",
            status_code=400
        )

    cmd_cfg = ADMIN_COMMAND_WHITELIST[req.command]
    executable = cmd_cfg["exec"]
    fixed_args = cmd_cfg["fixed_args"]
    timeout_sec = cmd_cfg["timeout"]

    parsed_args = []
    if req.args and req.args.strip():
        try:
            parsed_args = shlex.split(req.args.strip())
        except ValueError as e:
            write_admin_audit_entry(
                command=req.command,
                args=req.args,
                exit_code=400,
                by=role,
                duration_ms=0
            )
            return _error_response(
                code="INVALID_ARGS",
                message=f"Failed to parse arguments: {e}",
                status_code=400
            )

    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()

    if executable.startswith("./") or executable.startswith("scripts/"):
        rel_path = executable.lstrip("./")
        target_script = project_root / rel_path
        if target_script.exists():
            full_cmd = [str(target_script)] + fixed_args + parsed_args
        else:
            full_cmd = [executable] + fixed_args + parsed_args
    else:
        full_cmd = [executable] + fixed_args + parsed_args

    t0 = time.time()
    try:
        res = subprocess.run(
            full_cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False
        )
        duration_ms = int((time.time() - t0) * 1000)
        write_admin_audit_entry(
            command=req.command,
            args=req.args,
            exit_code=res.returncode,
            by=role,
            duration_ms=duration_ms
        )
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode,
            "duration_ms": duration_ms
        }
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - t0) * 1000)
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")) + f"\nCommand '{req.command}' timed out after {timeout_sec} seconds."
        exit_code = 124
        write_admin_audit_entry(
            command=req.command,
            args=req.args,
            exit_code=exit_code,
            by=role,
            duration_ms=duration_ms
        )
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "duration_ms": duration_ms
        }
    except FileNotFoundError as e:
        duration_ms = int((time.time() - t0) * 1000)
        write_admin_audit_entry(
            command=req.command,
            args=req.args,
            exit_code=127,
            by=role,
            duration_ms=duration_ms
        )
        return {
            "stdout": "",
            "stderr": f"Executable not found: {e}",
            "exit_code": 127,
            "duration_ms": duration_ms
        }
    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        write_admin_audit_entry(
            command=req.command,
            args=req.args,
            exit_code=1,
            by=role,
            duration_ms=duration_ms
        )
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
            "duration_ms": duration_ms
        }

@app.get("/api/admin/audit", dependencies=[Depends(require_operator)])
def get_admin_audit(limit: int = 50):
    entries = get_admin_audit_entries(limit=limit)
    return {"entries": entries}

@app.post("/api/admin/queue/add", dependencies=[Depends(require_operator)])
def admin_queue_add(req: AdminQueueAddRequest, role: str = Depends(require_operator)):
    t0 = time.time()
    text_content = req.text if req.text is not None else ""
    if not text_content.strip():
        write_admin_audit_entry(
            command="queue/add",
            args="",
            exit_code=400,
            by=role,
            duration_ms=0
        )
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "code": "MISSING_TEXT",
                "error": "MISSING_TEXT",
                "message": "Prompt text is required",
                "exit_code": None
            }
        )

    uid = uuid.uuid4().hex[:8]
    filename = f"admin-{uid}.txt"
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    pending_dir = project_root / ".jules" / "queue" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    txt_file = pending_dir / filename
    txt_file.write_text(text_content, encoding="utf-8")

    if req.verify_task:
        meta_file = pending_dir / f"admin-{uid}.meta.json"
        meta_data = {
            "verify_task": str(req.verify_task),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "by": role
        }
        meta_file.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")

    duration_ms = int((time.time() - t0) * 1000)
    write_admin_audit_entry(
        command="queue/add",
        args=filename,
        exit_code=0,
        by=role,
        duration_ms=duration_ms
    )

    return {"queued": True, "filename": filename}

@app.post("/api/admin/queue/run-next", dependencies=[Depends(require_operator)])
def admin_queue_run_next(role: str = Depends(require_operator)):
    t0 = time.time()
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    queue_dir = project_root / ".jules" / "queue"
    pending_dir = queue_dir / "pending"
    running_dir = queue_dir / "running"
    completed_dir = queue_dir / "completed"

    pending_dir.mkdir(parents=True, exist_ok=True)
    running_dir.mkdir(parents=True, exist_ok=True)
    completed_dir.mkdir(parents=True, exist_ok=True)

    pending_files = [f for f in pending_dir.glob("*.txt") if f.is_file()]
    if not pending_files:
        write_admin_audit_entry(
            command="queue/run-next",
            args="",
            exit_code=400,
            by=role,
            duration_ms=0
        )
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "code": "next_task_not_formed",
                "error": "next_task_not_formed",
                "message": "No pending task files",
                "exit_code": None
            }
        )

    def _ctime(f: Path):
        st = f.stat()
        return getattr(st, "st_birthtime", st.st_mtime)

    pending_files.sort(key=_ctime)
    oldest_txt = pending_files[0]
    filename = oldest_txt.name

    running_txt = running_dir / filename
    shutil.move(str(oldest_txt), str(running_txt))

    meta_filename = oldest_txt.stem + ".meta.json"
    oldest_meta = pending_dir / meta_filename
    running_meta = running_dir / meta_filename
    verify_task = None

    if oldest_meta.exists():
        try:
            meta_data = json.loads(oldest_meta.read_text(encoding="utf-8"))
            verify_task = meta_data.get("verify_task")
        except Exception:
            pass
        shutil.move(str(oldest_meta), str(running_meta))

    run_task_script = project_root / "scripts" / "run-task.sh"
    cmd = [str(run_task_script), str(running_txt)]
    if verify_task:
        cmd.extend(["--verify", str(verify_task)])

    job_id = uuid.uuid4().hex[:8]
    started_at = datetime.now(timezone.utc).isoformat()

    proc = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    job_record = {
        "job_id": job_id,
        "status": "running",
        "filename": filename,
        "started_at": started_at,
        "finished_at": None,
        "task_id": None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "duration_ms": None,
        "proc": proc
    }
    RUN_JOBS[job_id] = job_record

    thread = threading.Thread(
        target=_run_job_worker,
        args=(job_id, filename, proc, project_root, running_txt, running_meta, meta_filename, role, t0),
        daemon=True
    )
    thread.start()

    return {
        "started": True,
        "job_id": job_id,
        "filename": filename
    }

@app.get("/api/admin/queue/jobs/{job_id}", dependencies=[Depends(require_operator)])
def get_admin_queue_job(job_id: str):
    if job_id not in RUN_JOBS:
        return _error_response(code="JOB_NOT_FOUND", message=f"Job '{job_id}' not found", status_code=404)
    rec = dict(RUN_JOBS[job_id])
    rec.pop("proc", None)
    return rec

@app.get("/api/admin/queue/jobs", dependencies=[Depends(require_operator)])
def list_admin_queue_jobs():
    jobs_list = []
    for j in RUN_JOBS.values():
        rec = dict(j)
        rec.pop("proc", None)
        jobs_list.append(rec)
    jobs_list.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return {"jobs": jobs_list[:20]}

@app.post("/api/admin/queue/cancel/{job_id}", dependencies=[Depends(require_operator)])
def admin_queue_cancel_job(job_id: str, role: str = Depends(require_operator)):
    if job_id not in RUN_JOBS:
        return _error_response(code="JOB_NOT_FOUND", message=f"Job '{job_id}' not found", status_code=404)

    job = RUN_JOBS[job_id]
    proc: Optional[subprocess.Popen] = job.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except Exception as e:
            logger.error("Error terminating process for job %s: %s", job_id, e)

    job["status"] = "cancelled"
    job["finished_at"] = datetime.now(timezone.utc).isoformat()

    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    filename = job.get("filename")
    if filename:
        _move_job_file_to_deferred(project_root, filename)

    write_admin_audit_entry(
        command="queue/cancel",
        args=job_id,
        exit_code=0,
        by=role,
        duration_ms=0
    )

    rec = dict(job)
    rec.pop("proc", None)
    return rec

@app.post("/api/admin/queue/kill/{job_id}", dependencies=[Depends(require_operator)])
def admin_queue_kill_job(job_id: str, role: str = Depends(require_operator)):
    if job_id not in RUN_JOBS:
        return _error_response(code="JOB_NOT_FOUND", message=f"Job '{job_id}' not found", status_code=404)

    job = RUN_JOBS[job_id]
    proc: Optional[subprocess.Popen] = job.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.kill()
            proc.wait()
        except Exception as e:
            logger.error("Error killing process for job %s: %s", job_id, e)

    job["status"] = "killed"
    job["finished_at"] = datetime.now(timezone.utc).isoformat()

    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    filename = job.get("filename")
    if filename:
        _move_job_file_to_deferred(project_root, filename)

    write_admin_audit_entry(
        command="queue/kill",
        args=job_id,
        exit_code=0,
        by=role,
        duration_ms=0
    )

    rec = dict(job)
    rec.pop("proc", None)
    return rec

@app.get("/api/queue/status", dependencies=[Depends(require_operator)])
def get_queue_status():
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    queue_dir = project_root / ".jules" / "queue"

    def _count_txt(folder_name: str) -> int:
        folder = queue_dir / folder_name
        if not folder.exists():
            return 0
        return len([f for f in folder.glob("*.txt") if f.is_file()])

    qm = QueueManager()
    tasks = qm.list_all_tasks()
    running_tasks = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)

    running_files = _count_txt("running")
    return {
        "pending": _count_txt("pending"),
        "running": running_files + running_tasks,
        "running_files": running_files,
        "running_tasks": running_tasks,
        "blocked": _count_txt("blocked"),
        "deferred": _count_txt("deferred"),
    }

@app.get("/api/queue/files", dependencies=[Depends(require_operator)])
def list_queue_files():
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    queue_dir = project_root / ".jules" / "queue"

    active_jobs_by_file = {}
    for jid, job in RUN_JOBS.items():
        fname = job.get("filename")
        if fname and job.get("status") == "running":
            active_jobs_by_file[fname] = job

    def _get_file_cards(directory: Path):
        if not directory.exists():
            return []
        res = []

        def _ctime(f: Path):
            st = f.stat()
            return getattr(st, "st_birthtime", st.st_mtime)

        files = [f for f in directory.glob("*.txt") if f.is_file()]
        files.sort(key=_ctime)

        for f in files:
            stat = f.stat()
            ctime_val = getattr(stat, "st_birthtime", stat.st_mtime)
            ctime_iso = datetime.fromtimestamp(ctime_val, tz=timezone.utc).isoformat()

            try:
                content = f.read_text(encoding="utf-8")
                header = content.strip().split("\n")[0][:80]
            except Exception:
                header = f.name

            item = {
                "filename": f.name,
                "size": stat.st_size,
                "header": header,
                "ctime": ctime_iso
            }

            if f.name in active_jobs_by_file:
                job = active_jobs_by_file[f.name]
                item["job_id"] = job["job_id"]
                st_time = job.get("started_at")
                if st_time:
                    try:
                        st_dt = datetime.fromisoformat(st_time)
                        now_dt = datetime.now(timezone.utc)
                        item["elapsed_sec"] = max(0, int((now_dt - st_dt).total_seconds()))
                    except Exception:
                        pass
                proc = job.get("proc")
                if proc and hasattr(proc, "pid"):
                    item["pid"] = proc.pid

            res.append(item)
        return res

    return {
        "pending": _get_file_cards(queue_dir / "pending"),
        "running": _get_file_cards(queue_dir / "running"),
        "blocked": _get_file_cards(queue_dir / "blocked"),
        "completed": _get_file_cards(queue_dir / "completed"),
        "deferred": _get_file_cards(queue_dir / "deferred"),
    }

@app.delete("/api/queue/files/{folder}/{filename}", dependencies=[Depends(require_operator)])
def delete_queue_file(folder: str, filename: str, role: str = Depends(require_operator)):
    if folder not in ("pending", "running", "blocked", "completed"):
        return _error_response(code="INVALID_FOLDER", message=f"Invalid folder '{folder}'", status_code=400)

    if ".." in filename or "/" in filename or "\\" in filename:
        return _error_response(code="INVALID_FILENAME", message="Path traversal characters not allowed", status_code=400)

    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    queue_dir = project_root / ".jules" / "queue"
    src_dir = (queue_dir / folder).resolve()
    deferred_dir = (queue_dir / "deferred").resolve()
    deferred_dir.mkdir(parents=True, exist_ok=True)

    file_path = (src_dir / filename).resolve()
    if not str(file_path).startswith(str(src_dir)):
        return _error_response(code="INVALID_FILENAME", message="Path traversal prohibited", status_code=400)

    if not file_path.exists() or not file_path.is_file():
        return _error_response(code="FILE_NOT_FOUND", message=f"File '{filename}' not found in folder '{folder}'", status_code=404)

    target_txt = deferred_dir / filename
    shutil.move(str(file_path), str(target_txt))

    meta_filename = file_path.stem + ".meta.json"
    meta_path = src_dir / meta_filename
    if meta_path.exists() and meta_path.is_file():
        target_meta = deferred_dir / meta_filename
        shutil.move(str(meta_path), str(target_meta))

    write_admin_audit_entry(
        command="queue/file-delete",
        args=f"{folder}/{filename}",
        exit_code=0,
        by=role,
        duration_ms=0
    )

    return {"deleted": True, "filename": filename, "folder": folder, "moved_to": "deferred"}

@app.get("/api/admin/queue/list", dependencies=[Depends(require_operator)])
def admin_queue_list():
    project_root = Path(os.environ.get("JULES_PROJECT_ROOT", ".")).resolve()
    queue_dir = project_root / ".jules" / "queue"

    def _get_file_info(directory: Path):
        if not directory.exists():
            return []
        res = []
        for f in sorted(directory.glob("*.txt")):
            if f.is_file():
                stat = f.stat()
                created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                res.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "created_at": created_at
                })
        return res

    return {
        "pending": _get_file_info(queue_dir / "pending"),
        "running": _get_file_info(queue_dir / "running"),
        "completed": _get_file_info(queue_dir / "completed"),
    }

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

@app.post("/api/queue", dependencies=[Depends(require_operator)])
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
    if latest_task:
        seq_mgr = SequenceManager()
        seq_mgr.record_task_if_active(latest_task)
    EventTracker.emit("task_created", task_id=latest_task.id if latest_task else None, payload={"request": req.request})
    return {"status": "success", "cli_output": res["stdout"], "task": latest_task.model_dump() if latest_task else None}

@app.post("/api/tasks", dependencies=[Depends(require_operator)])
def create_task_endpoint(req: CreateTaskRequest):
    return add_task_to_queue(req)

@app.post("/api/queue/run", dependencies=[Depends(require_operator)])
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

@app.post("/api/queue/reorder", dependencies=[Depends(require_operator)])
def reorder_queue(req: ReorderQueueRequest):
    qm = QueueManager()
    reordered = qm.reorder_queue(req.task_ids)
    EventTracker.emit("queue_reordered", payload={"task_ids": req.task_ids})
    return {"status": "success", "reordered_tasks": [t.model_dump() for t in reordered]}

@app.post("/api/queue/reset", dependencies=[Depends(require_operator)])
def reset_queue_endpoint(req: QueueResetRequest, role: str = Depends(require_operator)):
    if req.confirm != "RESET":
        return _error_response(
            code="INVALID_CONFIRMATION",
            message="Queue reset requires confirmation string 'RESET'",
            status_code=400
        )
    qrm = QueueResetManager()
    try:
        res = qrm.reset_queue(scope=req.scope)
        EventTracker.emit("queue_reset", payload={"scope": req.scope, "cleared": res["cleared"]})
        write_audit_entry(
            action="reset-column",
            scope=req.scope,
            moved=res.get("moved", 0),
            restored=0,
            by=role,
            schedule_id=None,
            archive_file=res.get("archive")
        )
        return res
    except ValueError as e:
        return _error_response(code="INVALID_SCOPE", message=str(e), status_code=400)


@app.get("/api/queue/reset/audit", dependencies=[Depends(require_operator)])
def get_queue_reset_audit(limit: int = 50):
    entries = get_audit_entries(limit=limit)
    return {"entries": entries}

@app.get("/api/queue/reset/schedules", dependencies=[Depends(require_operator)])
def list_queue_reset_schedules():
    rsm = ResetScheduleManager()
    return rsm.list_schedules()

@app.post("/api/queue/reset/schedules", dependencies=[Depends(require_operator)])
def create_queue_reset_schedule(req: ResetScheduleCreateRequest):
    rsm = ResetScheduleManager()
    try:
        sched = rsm.create_schedule(
            name=req.name,
            cron=req.cron,
            scope=req.scope,
            enabled=req.enabled
        )
        EventTracker.emit("queue_reset_schedule_created", payload={"schedule_id": sched["id"], "name": sched["name"]})
        return sched
    except ValueError as e:
        return _error_response(code="INVALID_SCHEDULE", message=str(e), status_code=400)

@app.patch("/api/queue/reset/schedules/{id}", dependencies=[Depends(require_operator)])
def update_queue_reset_schedule(id: str, req: ResetScheduleUpdateRequest):
    rsm = ResetScheduleManager()
    try:
        sched = rsm.update_schedule(
            schedule_id=id,
            name=req.name,
            cron=req.cron,
            scope=req.scope,
            enabled=req.enabled
        )
        EventTracker.emit("queue_reset_schedule_updated", payload={"schedule_id": id})
        return sched
    except KeyError as e:
        return _error_response(code="SCHEDULE_NOT_FOUND", message=str(e), status_code=404)
    except ValueError as e:
        return _error_response(code="INVALID_SCHEDULE", message=str(e), status_code=400)

@app.delete("/api/queue/reset/schedules/{id}", dependencies=[Depends(require_operator)])
def delete_queue_reset_schedule(id: str):
    rsm = ResetScheduleManager()
    deleted = rsm.delete_schedule(id)
    if not deleted:
        return _error_response(code="SCHEDULE_NOT_FOUND", message=f"Schedule '{id}' not found", status_code=404)
    EventTracker.emit("queue_reset_schedule_deleted", payload={"schedule_id": id})
    return {"status": "success", "message": f"Schedule '{id}' deleted"}

@app.get("/api/queue/archive", dependencies=[Depends(require_operator)])
def get_queue_archive():
    qrm = QueueResetManager()
    entries = qrm.list_archive_entries()
    return {"entries": entries}

@app.post("/api/queue/archive/undo", dependencies=[Depends(require_operator)])
def undo_queue_archive(req: ArchiveUndoRequest, role: str = Depends(require_operator)):
    if req.confirm != "UNDO":
        return _error_response(
            code="INVALID_CONFIRMATION",
            message="Archive undo requires confirmation string 'UNDO'",
            status_code=400
        )
    qrm = QueueResetManager()
    try:
        res = qrm.undo_archive(archive_ids=req.archive_ids, confirm=req.confirm)
        EventTracker.emit("archive_undo", payload={"restored": res["restored"]})
        write_audit_entry(
            action="undo-selected",
            scope=None,
            moved=0,
            restored=len(res.get("restored", [])),
            by=role,
            schedule_id=None,
            archive_file=None
        )
        return res
    except ValueError as e:
        return _error_response(code="INVALID_REQUEST", message=str(e), status_code=400)

@app.post("/api/queue/archive/undo-filter", dependencies=[Depends(require_operator)])
def undo_filter_queue_archive(req: ArchiveUndoFilterRequest, role: str = Depends(require_operator)):
    if not req.dry_run and req.confirm != "UNDO":
        return _error_response(
            code="INVALID_CONFIRMATION",
            message="Archive undo filter requires confirmation string 'UNDO'",
            status_code=400
        )
    qrm = QueueResetManager()
    try:
        res = qrm.undo_archive_filter(
            status=req.status,
            date_from=req.date_from,
            date_to=req.date_to,
            scope=req.scope,
            search=req.search,
            confirm=req.confirm,
            dry_run=req.dry_run
        )
        if not req.dry_run:
            EventTracker.emit("archive_undo_filter", payload={"matched": res["matched"], "restored": res["restored"]})
            write_audit_entry(
                action="undo-filter",
                scope=req.scope,
                moved=0,
                restored=len(res.get("restored", [])),
                by=role,
                schedule_id=None,
                archive_file=None
            )
        return res
    except ValueError as e:
        return _error_response(code="INVALID_REQUEST", message=str(e), status_code=400)

@app.get("/api/queue/archive/export", dependencies=[Depends(require_operator)])
def export_queue_archive(format: str, scope: str = "all"):
    qrm = QueueResetManager()
    try:
        content, filename, media_type = qrm.export_archive(fmt=format, scope=scope)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        return Response(content=content, media_type=media_type, headers=headers)
    except ValueError as e:
        if str(e) == "INVALID_FORMAT":
            return _error_response(code="INVALID_FORMAT", message=f"Invalid format '{format}'. Must be one of: csv, md, jsonl", status_code=400)
        return _error_response(code="INVALID_REQUEST", message=str(e), status_code=400)
    except FileNotFoundError as e:
        if str(e) == "ARCHIVE_EMPTY":
            return _error_response(code="ARCHIVE_EMPTY", message="No archive files or matching entries found", status_code=404)
        return _error_response(code="NOT_FOUND", message=str(e), status_code=404)

@app.post("/api/queue/reset-column", dependencies=[Depends(require_operator)])
def reset_queue_column_endpoint(req: QueueResetColumnRequest, role: str = Depends(require_operator)):
    if req.confirm != "RESET":
        return _error_response(
            code="INVALID_CONFIRMATION",
            message="Column reset requires confirmation string 'RESET'",
            status_code=400
        )
    qrm = QueueResetManager()
    try:
        res = qrm.reset_queue(scope=req.column)
        EventTracker.emit("queue_column_reset", payload={"column": req.column, "cleared": res["cleared"]})
        write_audit_entry(
            action="reset-column",
            scope=req.column,
            moved=res.get("moved", 0),
            restored=0,
            by=role,
            schedule_id=None,
            archive_file=res.get("archive")
        )
        return res
    except ValueError as e:
        return _error_response(code="INVALID_SCOPE", message=str(e), status_code=400)

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

@app.patch("/api/tasks/{id}", dependencies=[Depends(require_operator)])
def update_task_by_id(id: str, req: UpdateTaskRequest):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    if req.title is not None:
        task.title = req.title
    if req.description is not None:
        task.description = req.description
    if req.request is not None:
        task.request = req.request
    if req.priority is not None:
        task.priority = req.priority
    if req.notes is not None:
        task.notes = req.notes
    if req.tags is not None:
        task.tags = req.tags
    if req.status is not None:
        try:
            new_st = TaskStatus(req.status.upper())
            task.transition_to(new_st, message="Task status updated via API")
        except ValueError:
            return _error_response(code="INVALID_STATUS", message=f"Invalid task status: {req.status}")

    qm.save_task(task)
    EventTracker.emit("task_updated", task_id=id, payload=req.model_dump(exclude_unset=True))
    return task.model_dump()

@app.post("/api/tasks/{id}/remember", dependencies=[Depends(require_operator)])
def remember_task_as_template(id: str, req: RememberTaskRequest):
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)

    tm = TemplateManager()
    tpl = tm.create_template_from_task(name=req.name, task=task)
    EventTracker.emit("template_created", payload={"template_id": tpl.id, "source_task_id": id, "name": req.name})
    return {"template_id": tpl.id, "template": tpl.model_dump()}

@app.get("/api/templates")
def list_templates():
    tm = TemplateManager()
    templates = tm.list_templates()
    return [t.model_dump() for t in templates]

@app.delete("/api/templates/{id}", dependencies=[Depends(require_operator)])
def delete_template(id: str):
    tm = TemplateManager()
    deleted = tm.delete_template(id)
    if not deleted:
        return _error_response(code="TEMPLATE_NOT_FOUND", message=f"Template with ID {id} not found", status_code=404)
    EventTracker.emit("template_deleted", payload={"template_id": id})
    return {"status": "success", "message": f"Template {id} deleted"}

@app.post("/api/templates/{id}/use", dependencies=[Depends(require_operator)])
def use_template(id: str):
    tm = TemplateManager()
    qm = QueueManager()
    task = tm.use_template(id, queue_manager=qm)
    if not task:
        return _error_response(code="TEMPLATE_NOT_FOUND", message=f"Template with ID {id} not found", status_code=404)
    EventTracker.emit("task_created_from_template", task_id=task.id, payload={"template_id": id})
    return task.model_dump()

@app.post("/api/tasks/{id}/start", dependencies=[Depends(require_operator)])
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

@app.post("/api/tasks/{id}/cancel", dependencies=[Depends(require_operator)])
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

@app.post("/api/proposals", dependencies=[Depends(require_operator)])
def create_proposal(req: CreateProposalRequest):
    pm = ProposalManager()
    prop_id = f"prop-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    prop = Proposal(
        id=prop_id,
        description=req.description,
        priority=req.priority,
        source_task=req.source_task,
        proposed_by=req.proposed_by or "operator",
    )
    target_file = pm.proposed_dir / f"{prop_id}.json"
    target_file.write_text(json.dumps(prop.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    EventTracker.emit("proposal_created", payload={"proposal_id": prop_id, "description": req.description})
    return {"status": "success", "proposal": prop.model_dump()}

@app.get("/api/proposals/{id}")
def get_proposal_by_id(id: str):
    pm = ProposalManager()
    prop = pm.get_proposal(id)
    if not prop:
        return _error_response(code="PROPOSAL_NOT_FOUND", message=f"Proposal with ID {id} not found", status_code=404)
    return prop.model_dump()

@app.post("/api/proposals/{id}/accept", dependencies=[Depends(require_operator)])
def accept_proposal(id: str):
    adapter = JulesCLIAdapter()
    res = adapter.accept_proposal(id)
    if not res["success"]:
        return _error_response(code="PROPOSAL_ACCEPT_FAILED", message=res["error"] or "Failed to accept proposal", exit_code=res.get("exit_code"))
    EventTracker.emit("proposal_accepted", payload={"proposal_id": id})
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/proposals/{id}/defer", dependencies=[Depends(require_operator)])
def defer_proposal(id: str):
    adapter = JulesCLIAdapter()
    res = adapter.defer_proposal(id)
    if not res["success"]:
        return _error_response(code="PROPOSAL_DEFER_FAILED", message=res["error"] or "Failed to defer proposal", exit_code=res.get("exit_code"))
    EventTracker.emit("proposal_deferred", payload={"proposal_id": id})
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/proposals/{id}/reject", dependencies=[Depends(require_operator)])
def reject_proposal(id: str):
    adapter = JulesCLIAdapter()
    res = adapter.reject_proposal(id)
    if not res["success"]:
        return _error_response(code="PROPOSAL_REJECT_FAILED", message=res["error"] or "Failed to reject proposal", exit_code=res.get("exit_code"))
    EventTracker.emit("proposal_rejected", payload={"proposal_id": id})
    return {"status": "success", "cli_output": res["stdout"]}

@app.post("/api/proposals/{id}/modify", dependencies=[Depends(require_operator)])
def modify_proposal(id: str, req: ModifyProposalRequest):
    pm = ProposalManager()
    prop = pm.modify_proposal(id, new_description=req.description, new_priority=req.priority)
    if not prop:
        return _error_response(code="PROPOSAL_NOT_FOUND", message=f"Proposal with ID {id} not found", status_code=404)
    EventTracker.emit("proposal_modified", payload={"proposal_id": id})
    return {"status": "success", "proposal": prop.model_dump()}

# --- SEQUENCE ENDPOINTS ---

@app.post("/api/sequences/record/start", dependencies=[Depends(require_operator)])
def start_sequence_record():
    sm = SequenceManager()
    res = sm.start_recording()
    EventTracker.emit("sequence_recording_started")
    return res

@app.post("/api/sequences/record/stop", dependencies=[Depends(require_operator)])
def stop_sequence_record(req: Optional[SequenceRecordStopRequest] = None):
    sm = SequenceManager()
    name = req.name if req else None
    res = sm.stop_recording(name=name)
    EventTracker.emit("sequence_recording_stopped", payload={"sequence_id": res["sequence_id"]})
    return res

@app.get("/api/sequences")
def list_sequences():
    sm = SequenceManager()
    seqs = sm.list_sequences()
    return [s.model_dump() for s in seqs]

@app.get("/api/sequences/{id}")
def get_sequence_by_id(id: str):
    sm = SequenceManager()
    seq = sm.get_sequence(id)
    if not seq:
        return _error_response(code="SEQUENCE_NOT_FOUND", message=f"Sequence {id} not found", status_code=404)
    return seq.model_dump()

@app.post("/api/sequences/{id}/replay", dependencies=[Depends(require_operator)])
def replay_sequence(id: str, req: SequenceReplayRequest):
    sm = SequenceManager()
    try:
        res = sm.replay_sequence(
            sequence_id=id,
            mode=req.mode,
            schedule=req.schedule,
            concurrency=req.concurrency
        )
        EventTracker.emit("sequence_replayed", payload={"sequence_id": id, "batch_id": res.get("batch_id")})
        return res
    except ValueError as e:
        return _error_response(code="SEQUENCE_NOT_FOUND", message=str(e), status_code=404)

# --- BATCH ENDPOINTS ---

@app.post("/api/batch/run", dependencies=[Depends(require_operator)])
def run_batch(req: BatchRunRequest):
    schedule = req.schedule.lower()
    autonomy = req.autonomy.upper()

    if schedule not in ("now", "now-sequential", "night", "window"):
        return _error_response(
            code="INVALID_SCHEDULE",
            message=f"Unsupported schedule: {req.schedule}",
            status_code=400
        )

    if autonomy == "MANUAL" and not req.confirm:
        return _error_response(
            code="CONFIRMATION_REQUIRED",
            message="Manual execution requires explicit confirmation (confirm=true)",
            status_code=400
        )

    bm = BatchManager()
    qm = QueueManager()

    if schedule in ("night", "window"):
        status = "queued"
        started_ids = []
        queued_ids = req.task_ids
    elif schedule == "now-sequential":
        status = "accepted"
        started_ids = req.task_ids[:1]
        queued_ids = req.task_ids[1:]
    else:  # "now"
        status = "accepted"
        limit = req.concurrency
        started_ids = req.task_ids[:limit]
        queued_ids = req.task_ids[limit:]

    # Transition started tasks
    for tid in started_ids:
        task = qm.get_task(tid)
        if task:
            task.transition_to(TaskStatus.RUNNING, message="Task started via batch execution")
            qm.save_task(task)
            EventTracker.emit("task_started", task_id=tid, payload={"execution_mode": "batch"})

    batch = bm.create_batch(
        task_ids=req.task_ids,
        schedule=req.schedule,
        concurrency=req.concurrency,
        status=status,
        started=started_ids,
        queued=queued_ids,
        autonomy=req.autonomy,
    )

    EventTracker.emit("batch_created", payload={"batch_id": batch.id, "schedule": schedule, "task_count": len(req.task_ids)})

    return {
        "status": batch.status,
        "batch_id": batch.id,
        "task_ids": batch.task_ids,
        "concurrency": batch.concurrency,
        "schedule": batch.schedule,
        "started": batch.started,
        "queued": batch.queued,
    }

@app.get("/api/batch/queue")
def list_queued_batches():
    bm = BatchManager()
    batches = bm.list_queued_batches()
    return [b.model_dump() for b in batches]

@app.get("/api/batch")
def list_recent_batches(limit: int = 50):
    bm = BatchManager()
    batches = bm.list_batches(limit=limit)
    return [b.model_dump() for b in batches]

# --- BATCH TEMPLATE ENDPOINTS ---

@app.post("/api/batch/remember", dependencies=[Depends(require_operator)])
def remember_batch_template(req: BatchRememberRequest):
    btm = BatchTemplateManager()
    tpl = btm.create_batch_template(
        name=req.name,
        task_ids=req.task_ids,
        concurrency=req.concurrency,
        schedule=req.schedule
    )
    EventTracker.emit("batch_template_created", payload={"template_id": tpl.id, "name": req.name})
    return tpl.model_dump()

@app.get("/api/batch/templates")
def list_batch_templates():
    btm = BatchTemplateManager()
    templates = btm.list_templates()
    return [t.model_dump() for t in templates]

@app.get("/api/batch/templates/{id}")
def get_batch_template_by_id(id: str):
    btm = BatchTemplateManager()
    tpl = btm.get_template(id)
    if not tpl:
        return _error_response(code="BATCH_TEMPLATE_NOT_FOUND", message=f"Batch template {id} not found", status_code=404)
    return tpl.model_dump()

@app.post("/api/batch/templates/{id}/replay", dependencies=[Depends(require_operator)])
def replay_batch_template(id: str):
    btm = BatchTemplateManager()
    try:
        res = btm.replay_template(template_id=id)
        EventTracker.emit("batch_template_replayed", payload={"template_id": id, "batch_id": res.get("batch_id")})
        return res
    except ValueError as e:
        return _error_response(code="BATCH_TEMPLATE_NOT_FOUND", message=str(e), status_code=404)

@app.get("/api/batch/{id}")
def get_batch_by_id(id: str):
    bm = BatchManager()
    batch = bm.get_batch(id)
    if not batch:
        return _error_response(code="BATCH_NOT_FOUND", message=f"Batch with ID {id} not found", status_code=404)
    return batch.model_dump()

# --- SCHEDULER ENDPOINTS ---

@app.get("/api/scheduler/schedules")
def list_schedules():
    return scheduler_instance.get_schedules()

@app.post("/api/scheduler/schedules", dependencies=[Depends(require_operator)])
def register_schedule_endpoint(req: ScheduleRegisterRequest):
    try:
        scheduler_instance.register_schedule(req.name, req.config)
        return {"status": "success", "schedule": req.name, "config": scheduler_instance.schedules.get(req.name.lower())}
    except ValueError as e:
        return _error_response(code="INVALID_SCHEDULE_CONFIG", message=str(e), status_code=400)

@app.get("/api/scheduler/status")
def get_scheduler_status():
    return scheduler_instance.get_status()

@app.post("/api/scheduler/trigger", dependencies=[Depends(require_operator)])
def trigger_scheduler():
    bm = BatchManager()
    started_batch_ids = scheduler_instance.check_due_batches()
    return {"status": "success", "started_batches": started_batch_ids}

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

@app.post("/api/tasks/{id}/retry", dependencies=[Depends(require_operator)])
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

# --- CONSULT ACCESS ENDPOINTS (READ-ONLY & SETTINGS) ---

_consult_request_count = 0

def _track_consult_request():
    global _consult_request_count
    _consult_request_count += 1

@app.get("/api/consult/settings", dependencies=[Depends(require_admin)])
def get_consult_settings():
    return consult_settings_manager.get_settings()

@app.patch("/api/consult/settings", dependencies=[Depends(require_admin)])
def patch_consult_settings(req: ConsultSettingsPatchRequest):
    updated = consult_settings_manager.update_settings(req.model_dump(exclude_unset=True))
    return updated

@app.post("/api/consult/tokens/{role}/regenerate", dependencies=[Depends(require_admin)])
def regenerate_consult_token(role: str):
    if role not in ("consultant", "operator", "admin"):
        return _error_response(code="INVALID_ROLE", message=f"Invalid role '{role}'", status_code=400)
    new_token = consult_settings_manager.regenerate_token(role)
    return {"status": "success", "role": role, "token": new_token}

@app.post("/api/consult/tokens/{role}/disable", dependencies=[Depends(require_admin)])
def disable_consult_token(role: str):
    if role not in ("consultant", "operator", "admin"):
        return _error_response(code="INVALID_ROLE", message=f"Invalid role '{role}'", status_code=400)
    consult_settings_manager.disable_token(role)
    return {"status": "success", "role": role, "disabled": True}

@app.get("/api/consult/audit", dependencies=[Depends(require_consultant)])
def get_consult_audit(limit: int = 50):
    return consult_audit_logger.get_logs(limit=limit)

@app.get("/api/consult/state", dependencies=[Depends(require_consultant)])
def get_consult_state():
    check_consult_endpoint_enabled("/api/consult/state")
    _track_consult_request()
    sm = StateManager()
    return {
        "read_only": True,
        "request_count": _consult_request_count,
        "system_status": sm.get_system_status()
    }

@app.get("/api/consult/tasks", dependencies=[Depends(require_consultant)])
def get_consult_tasks():
    check_consult_endpoint_enabled("/api/consult/tasks")
    _track_consult_request()
    qm = QueueManager()
    tasks = qm.list_all_tasks()
    return [t.model_dump() for t in tasks]

@app.get("/api/consult/task/{id}", dependencies=[Depends(require_consultant)])
def get_consult_task_by_id(id: str):
    check_consult_endpoint_enabled("/api/consult/task/{id}")
    _track_consult_request()
    qm = QueueManager()
    task = qm.get_task(id)
    if not task:
        return _error_response(code="TASK_NOT_FOUND", message=f"Task with ID {id} not found", status_code=404)
    return task.model_dump()

@app.get("/api/consult/events", dependencies=[Depends(require_consultant)])
def get_consult_events(limit: int = 100):
    check_consult_endpoint_enabled("/api/consult/events")
    _track_consult_request()
    events = EventTracker.list_events(limit=limit)
    return [e.model_dump() for e in events]

@app.get("/api/consult/errata", dependencies=[Depends(require_consultant)])
def get_consult_errata():
    check_consult_endpoint_enabled("/api/consult/errata")
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

@app.get("/api/consult/health", dependencies=[Depends(require_consultant_or_public)])
def get_consult_health():
    check_consult_endpoint_enabled("/api/consult/health")
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

@app.get("/epistemic/statuses")
def list_epistemic_statuses():
    """Returns available epistemic statuses including canonical and legacy statuses."""
    from smos.models.models import EpistemicStatus
    canonical = [s.value for s in EpistemicStatus if s.is_canonical]
    legacy = [s.value for s in EpistemicStatus if not s.is_canonical]
    return {
        "status": "success",
        "canonical": canonical,
        "legacy": legacy,
        "all": [s.value for s in EpistemicStatus]
    }

@app.post("/epistemic/node/{node_id}/status")
def update_node_epistemic_status(node_id: int, status: str, db: Session = Depends(get_db)):
    """Updates the epistemic status of a node."""
    from smos.models.models import EpistemicStatus
    svc = EpistemicService(db)
    try:
        ep_status = EpistemicStatus.from_str(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid epistemic status: {status}")
    node = svc.update_node_status(node_id, ep_status)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "status": "success",
        "node_id": node.id,
        "epistemic_status": node.epistemic_status.value
    }

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