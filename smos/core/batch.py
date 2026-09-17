"""Batch core manager and models for Co-SMOS Control Room v0.9."""

import json
import os
import time
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class Batch(BaseModel):
    id: str
    task_ids: List[str]
    concurrency: int
    schedule: str
    status: str  # "accepted" | "queued" | "error"
    started: List[str] = Field(default_factory=list)
    queued: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    autonomy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchTemplateTask(BaseModel):
    request: str
    priority: int = 5


class BatchTemplate(BaseModel):
    id: str
    name: str
    task_ids: List[str] = Field(default_factory=list)
    tasks: List[BatchTemplateTask] = Field(default_factory=list)
    concurrency: int = 3
    schedule: str = "now"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BatchManager:
    def __init__(self, batch_dir: Optional[Path] = None):
        if batch_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            batch_dir = project_root / ".jules" / "batches"
        self.batch_dir = Path(batch_dir)
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def create_batch(
        self,
        task_ids: List[str],
        schedule: str,
        concurrency: int,
        status: str,
        started: List[str],
        queued: List[str],
        autonomy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Batch:
        batch_id = f"batch-{int(time.time() * 1000)}"
        batch = Batch(
            id=batch_id,
            task_ids=task_ids,
            concurrency=concurrency,
            schedule=schedule,
            status=status,
            started=started,
            queued=queued,
            autonomy=autonomy,
            metadata=metadata or {},
        )
        self.save_batch(batch)
        return batch

    def save_batch(self, batch: Batch) -> None:
        filepath = self.batch_dir / f"{batch.id}.json"
        data = batch.model_dump()
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        filepath = self.batch_dir / f"{batch_id}.json"
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return Batch(**data)
        except Exception:
            return None

    def list_batches(self, limit: int = 50) -> List[Batch]:
        batches = []
        for p in self.batch_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                batches.append(Batch(**data))
            except Exception:
                continue
        batches.sort(key=lambda b: b.created_at, reverse=True)
        return batches[:limit]

    def list_queued_batches(self) -> List[Batch]:
        return [b for b in self.list_batches(limit=1000) if b.status == "queued"]

    def run_due_batches(self, scheduler=None, now: Optional[datetime] = None) -> List[str]:
        if scheduler is None:
            from smos.core.scheduler import Scheduler
            scheduler = Scheduler(batch_manager=self)

        from smos.core.queue import QueueManager
        from smos.core.task import TaskStatus
        from smos.core.events import EventTracker

        qm = QueueManager()
        started_batch_ids = []

        # Only touch batches with status == "queued"
        queued_batches = self.list_queued_batches()

        for batch in queued_batches:
            schedule_name = batch.schedule.lower()
            # MUST NOT touch "now" or "now-sequential" batches
            if schedule_name in ("now", "now-sequential"):
                continue

            if scheduler.is_due(schedule_name, now=now):
                # Update status to running
                batch.status = "running"
                
                # Respect concurrency limit
                concurrency = batch.concurrency
                to_start = batch.queued[:concurrency]
                remaining_queued = batch.queued[concurrency:]

                batch.started.extend(to_start)
                batch.queued = remaining_queued

                # Update task statuses
                for tid in to_start:
                    task = qm.get_task(tid)
                    if task:
                        task.transition_to(TaskStatus.RUNNING, message=f"Task started by scheduler batch {batch.id}")
                        qm.save_task(task)
                        EventTracker.emit("task_started", task_id=tid, payload={"execution_mode": "batch_scheduler", "batch_id": batch.id})

                batch.status = "completed"
                self.save_batch(batch)
                started_batch_ids.append(batch.id)

                EventTracker.emit("batch_scheduled_run", payload={"batch_id": batch.id, "started_tasks": to_start})

        return started_batch_ids


class BatchTemplateManager:
    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            templates_dir = project_root / ".jules" / "batch_templates"
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def create_batch_template(
        self,
        name: str,
        task_ids: List[str],
        concurrency: int = 3,
        schedule: str = "now",
        queue_manager = None
    ) -> BatchTemplate:
        template_id = f"btpl-{uuid.uuid4().hex[:8]}"
        
        from smos.core.queue import QueueManager
        qm = queue_manager or QueueManager()

        captured_tasks = []
        for tid in task_ids:
            t = qm.get_task(tid)
            if t:
                captured_tasks.append(BatchTemplateTask(
                    request=t.request or t.title or t.description or "Unnamed task",
                    priority=t.priority
                ))
            else:
                captured_tasks.append(BatchTemplateTask(
                    request=f"Batch task {tid}",
                    priority=3
                ))

        tpl = BatchTemplate(
            id=template_id,
            name=name,
            task_ids=task_ids,
            tasks=captured_tasks,
            concurrency=concurrency,
            schedule=schedule,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.save_template(tpl)
        return tpl

    def save_template(self, template: BatchTemplate) -> None:
        filepath = self.templates_dir / f"{template.id}.json"
        data = template.model_dump()
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def list_templates(self) -> List[BatchTemplate]:
        templates = []
        for p in sorted(self.templates_dir.glob("btpl-*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                templates.append(BatchTemplate(**data))
            except Exception:
                continue
        templates.sort(key=lambda x: x.created_at, reverse=True)
        return templates

    def get_template(self, template_id: str) -> Optional[BatchTemplate]:
        p = self.templates_dir / f"{template_id}.json"
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return BatchTemplate(**data)
        except Exception:
            return None

    def replay_template(
        self,
        template_id: str,
        queue_manager = None,
        batch_manager = None
    ) -> Dict[str, Any]:
        tpl = self.get_template(template_id)
        if not tpl:
            raise ValueError(f"Batch template {template_id} not found")

        from smos.core.queue import QueueManager
        from smos.core.task import Task
        qm = queue_manager or QueueManager()
        bm = batch_manager or BatchManager()

        created_tasks = []
        created_task_ids = []

        if tpl.tasks:
            for item in tpl.tasks:
                task_id = f"task-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
                t = Task(
                    id=task_id,
                    request=item.request,
                    title=item.request[:50],
                    priority=item.priority,
                    proposed_by="batch_template_replay"
                )
                qm.save_task(t)
                created_tasks.append(t.model_dump())
                created_task_ids.append(t.id)
        else:
            # Fallback if tpl.tasks is empty
            for tid in tpl.task_ids:
                old_t = qm.get_task(tid)
                req_str = old_t.request if old_t else f"Task from {tid}"
                prio = old_t.priority if old_t else 3
                task_id = f"task-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
                t = Task(
                    id=task_id,
                    request=req_str,
                    title=req_str[:50],
                    priority=prio,
                    proposed_by="batch_template_replay"
                )
                qm.save_task(t)
                created_tasks.append(t.model_dump())
                created_task_ids.append(t.id)

        schedule = tpl.schedule or "now"
        concurrency = tpl.concurrency or 3

        if created_task_ids:
            if schedule in ("night", "window"):
                status = "queued"
                started_ids = []
                queued_ids = created_task_ids
            elif schedule == "now-sequential":
                status = "accepted"
                started_ids = created_task_ids[:1]
                queued_ids = created_task_ids[1:]
            else:  # "now"
                status = "accepted"
                started_ids = created_task_ids[:concurrency]
                queued_ids = created_task_ids[concurrency:]

            from smos.core.task import TaskStatus
            from smos.core.events import EventTracker
            for tid in started_ids:
                task = qm.get_task(tid)
                if task:
                    task.transition_to(TaskStatus.RUNNING, message="Task started via batch template replay")
                    qm.save_task(task)

            batch = bm.create_batch(
                task_ids=created_task_ids,
                schedule=schedule,
                concurrency=concurrency,
                status=status,
                started=started_ids,
                queued=queued_ids,
                autonomy="AUTO"
            )
            batch_id = batch.id
        else:
            batch_id = None

        return {
            "created_tasks": created_tasks,
            "batch_id": batch_id
        }
