"""Task Queue Core Manager for Co-SMOS Control Room v0.9."""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from smos.core.task import Task, TaskStatus


class QueueManager:
    def __init__(self, queue_dir: Optional[Path] = None):
        if queue_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            queue_dir = project_root / ".jules" / "queue"
        self.queue_dir = Path(queue_dir)
        self.pending_dir = self.queue_dir / "pending"
        self.running_dir = self.queue_dir / "running"
        self.completed_dir = self.queue_dir / "completed"
        self.proposed_dir = self.queue_dir / "proposed"
        self.deferred_dir = self.queue_dir / "deferred"

        for d in [self.pending_dir, self.running_dir, self.completed_dir, self.proposed_dir, self.deferred_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _task_from_dict(self, data: Dict[str, Any], default_status: TaskStatus) -> Task:
        raw_status = data.get("status")
        status_enum = default_status
        if raw_status:
            try:
                status_enum = TaskStatus(raw_status.upper())
            except ValueError:
                try:
                    status_enum = TaskStatus[raw_status.upper()]
                except KeyError:
                    status_enum = default_status

        req = data.get("request") or data.get("description") or data.get("title") or "Unnamed task"
        return Task(
            id=data.get("id", "unknown-task"),
            request=req,
            title=data.get("title") or req[:50],
            description=data.get("description"),
            status=status_enum,
            priority=int(data.get("priority", 5)),
            created_at=data.get("created_at") or "",
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            proposed_by=data.get("proposed_by"),
            source_task=data.get("source_task"),
            session_id=data.get("session_id"),
            jules_task_id=data.get("jules_task_id"),
            error=data.get("error"),
            exit_code=data.get("exit_code"),
            metadata=data.get("metadata", {}),
            history=data.get("history", [])
        )

    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        data = task.model_dump()
        data["status"] = task.status.value.lower()
        return data

    def list_all_tasks(self) -> List[Task]:
        tasks = []
        directories = [
            (self.pending_dir, TaskStatus.PENDING),
            (self.running_dir, TaskStatus.RUNNING),
            (self.completed_dir, TaskStatus.COMPLETED),
            (self.deferred_dir, TaskStatus.DEFERRED),
        ]
        for folder, default_status in directories:
            for p in folder.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    tasks.append(self._task_from_dict(data, default_status))
                except Exception:
                    continue
        return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        all_tasks = self.list_all_tasks()
        for t in all_tasks:
            if t.id == task_id:
                return t
        return None

    def save_task(self, task: Task) -> None:
        target_dir = self.pending_dir
        if task.status == TaskStatus.RUNNING:
            target_dir = self.running_dir
        elif task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            target_dir = self.completed_dir
        elif task.status == TaskStatus.DEFERRED:
            target_dir = self.deferred_dir

        for d in [self.pending_dir, self.running_dir, self.completed_dir, self.deferred_dir]:
            old_file = d / f"{task.id}.json"
            if old_file.exists():
                old_file.unlink()

        filepath = target_dir / f"{task.id}.json"
        data = self._task_to_dict(task)
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def reorder_queue(self, ordered_task_ids: List[str]) -> List[Task]:
        pending_tasks = {t.id: t for t in self.list_all_tasks() if t.status in (TaskStatus.PENDING, TaskStatus.READY)}
        reordered = []
        base_priority = 10
        for i, tid in enumerate(ordered_task_ids):
            if tid in pending_tasks:
                task = pending_tasks[tid]
                task.priority = max(1, base_priority - i)
                self.save_task(task)
                reordered.append(task)
        return reordered
