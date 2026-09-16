"""Batch core manager and models for Co-SMOS Control Room v0.9."""

import json
import os
import time
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
