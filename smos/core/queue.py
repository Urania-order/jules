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
            self.project_root = project_root
        else:
            self.project_root = queue_dir.parent.parent
        self.queue_dir = Path(queue_dir)
        self.state_file = self.project_root / ".co-smos" / "state.json"
        self.pending_dir = self.queue_dir / "pending"
        self.running_dir = self.queue_dir / "running"
        self.blocked_dir = self.queue_dir / "blocked"
        self.completed_dir = self.queue_dir / "completed"
        self.proposed_dir = self.queue_dir / "proposed"
        self.deferred_dir = self.queue_dir / "deferred"

        for d in [self.pending_dir, self.running_dir, self.blocked_dir, self.completed_dir, self.proposed_dir, self.deferred_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _iso_from_task_id(self, tid: Optional[str]) -> Optional[str]:
        import re
        from datetime import datetime, timezone
        if not tid or not tid.startswith("task-"):
            return None
        m = re.match(r"^task-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", tid)
        if not m:
            return None
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
                tzinfo=timezone.utc
            ).isoformat()
        except ValueError:
            return None

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

        tid = data.get("id", "unknown-task")
        raw_title = data.get("title")
        raw_req = data.get("request") or data.get("description")

        req = raw_req or raw_title or (tid if tid.startswith("task-") else "Unnamed task")

        if raw_title and raw_title != tid:
            title = raw_title
        elif raw_req and raw_req != tid:
            title = raw_req.split("\n")[0][:80]
        elif raw_title:
            title = raw_title
        else:
            title = req.split("\n")[0][:80] if req else tid

        created_at = data.get("created_at") or self._iso_from_task_id(tid) or ""
        proposed_by = data.get("proposed_by") or "unknown"

        return Task(
            id=tid,
            request=req,
            title=title,
            description=data.get("description"),
            status=status_enum,
            priority=int(data.get("priority", 5)),
            created_at=created_at,
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            proposed_by=proposed_by,
            source_task=data.get("source_task"),
            session_id=data.get("session_id"),
            jules_task_id=data.get("jules_task_id"),
            error=data.get("error"),
            exit_code=data.get("exit_code"),
            notes=data.get("notes"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            history=data.get("history", [])
        )

    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        data = task.model_dump()
        data["status"] = task.status.value.lower()
        return data

    def list_all_tasks(self) -> List[Task]:
        tasks = []
        by_id: Dict[str, Dict[str, Any]] = {}

        # Primary source: state.json
        if self.state_file.exists():
            try:
                state_data = json.loads(self.state_file.read_text(encoding="utf-8"))
                candidates = []
                if isinstance(state_data.get("tasks"), list):
                    candidates.extend(state_data["tasks"])
                if isinstance(state_data.get("history"), list):
                    candidates.extend(state_data["history"])
                if isinstance(state_data.get("active_task"), dict):
                    candidates.append(state_data["active_task"])
                if isinstance(state_data.get("last_task"), dict):
                    candidates.append(state_data["last_task"])

                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    tid = item.get("id")
                    if not tid:
                        continue
                    raw_status = (item.get("status") or "").upper()
                    if raw_status == "CANCELLED":
                        continue
                    by_id[tid] = item  # last wins

                for tid, item in by_id.items():
                    tasks.append(self._task_from_dict(item, TaskStatus.PENDING))
            except Exception:
                pass

        seen_ids = set(by_id.keys())

        # Legacy file source: .jules/queue/*.json
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
                    tid = data.get("id") or p.stem
                    raw_status = (data.get("status") or "").upper()
                    if raw_status == "CANCELLED":
                        continue
                    if tid not in seen_ids:
                        tasks.append(self._task_from_dict(data, default_status))
                        seen_ids.add(tid)
                except Exception:
                    continue

        return tasks

    def list_queue_tasks(self) -> List[Task]:
        """Return only tasks in the active queue (not completed/cancelled/deferred)."""
        queue_statuses = {
            TaskStatus.PENDING,
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.REVIEW,
            TaskStatus.BLOCKED,
        }
        return [t for t in self.list_all_tasks() if t.status in queue_statuses]

    def get_task(self, task_id: str) -> Optional[Task]:
        if self.state_file.exists():
            try:
                state_data = json.loads(self.state_file.read_text(encoding="utf-8"))
                candidates = []
                if isinstance(state_data.get("tasks"), list):
                    candidates.extend(state_data["tasks"])
                if isinstance(state_data.get("history"), list):
                    candidates.extend(state_data["history"])
                if isinstance(state_data.get("active_task"), dict):
                    candidates.append(state_data["active_task"])
                if isinstance(state_data.get("last_task"), dict):
                    candidates.append(state_data["last_task"])

                for item in reversed(candidates):
                    if isinstance(item, dict) and item.get("id") == task_id:
                        return self._task_from_dict(item, TaskStatus.PENDING)
            except Exception:
                pass

        # Legacy file source: .jules/queue/*.json
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
                    tid = data.get("id") or p.stem
                    if tid == task_id:
                        return self._task_from_dict(data, default_status)
                except Exception:
                    continue

        return None

    def save_task(self, task: Task) -> None:
        if self.state_file.exists():
            try:
                state_data = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                state_data = {}
        else:
            state_data = {}
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

        task_dict = self._task_to_dict(task)
        history = state_data.get("history")
        if not isinstance(history, list):
            history = []

        updated = False
        for idx, item in enumerate(history):
            if isinstance(item, dict) and item.get("id") == task.id:
                history[idx] = task_dict
                updated = True
                break
        if not updated:
            history.append(task_dict)

        state_data["history"] = history

        if task.status == TaskStatus.RUNNING:
            state_data["active_task"] = task_dict
            state_data["status"] = "busy"
        elif state_data.get("active_task") and isinstance(state_data["active_task"], dict) and state_data["active_task"].get("id") == task.id:
            state_data["active_task"] = None
            state_data["status"] = "idle"

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            state_data["last_task"] = task_dict

        self.state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Cleanup legacy file if any exists
        for d in [self.pending_dir, self.running_dir, self.completed_dir, self.deferred_dir]:
            old_file = d / f"{task.id}.json"
            if old_file.exists():
                old_file.unlink()

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
