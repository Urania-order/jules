"""Queue Reset Manager for Co-SMOS Control Room v1.1."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from smos.core.queue import QueueManager
from smos.core.task import TaskStatus


class QueueResetManager:
    def __init__(self, queue_dir: Optional[Path] = None, state_file: Optional[Path] = None):
        if queue_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            self.project_root = project_root
            queue_dir = project_root / ".jules" / "queue"
        else:
            self.project_root = queue_dir.parent.parent
        self.queue_dir = Path(queue_dir)
        self.state_file = state_file or (self.project_root / ".co-smos" / "state.json")
        self.pending_dir = self.queue_dir / "pending"
        self.running_dir = self.queue_dir / "running"
        self.completed_dir = self.queue_dir / "completed"
        self.deferred_dir = self.queue_dir / "deferred"
        self.history_dir = self.project_root / ".jules" / "history"

        for d in [self.pending_dir, self.running_dir, self.completed_dir, self.deferred_dir, self.history_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.queue_mgr = QueueManager(queue_dir=self.queue_dir)

    def reset_queue(self, scope: str = "all") -> Dict[str, Any]:
        normalized_scope = scope.lower().strip()
        valid_scopes = {"all", "ready", "pending", "running", "review", "blocked", "completed"}
        if normalized_scope not in valid_scopes:
            raise ValueError(f"Invalid scope: {scope}. Must be one of {valid_scopes}")

        cleared_counts = {
            "ready": 0,
            "pending": 0,
            "running": 0,
            "review": 0,
            "blocked": 0,
            "completed": 0
        }
        total_moved = 0
        archived_lines = []

        now_utc = datetime.now(timezone.utc)
        timestamp_str = now_utc.strftime("%Y%m%d-%H%M%S")
        reset_at_iso = now_utc.isoformat()

        # Gather tasks via QueueManager
        all_tasks = self.queue_mgr.list_all_tasks()

        # Also check state.json directly if present
        state_data = {}
        if self.state_file.exists():
            try:
                state_data = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                state_data = {}

        removed_task_ids = set()
        removed_tasks_info = []

        for task in all_tasks:
            raw_status = (task.status.value if hasattr(task.status, "value") else str(task.status)).lower().strip()

            # Determine whether task matches requested scope
            matches = False
            if normalized_scope == "all":
                matches = True
            elif normalized_scope in ("ready", "pending"):
                matches = raw_status in ("ready", "pending")
            elif normalized_scope == "running":
                matches = raw_status == "running"
            elif normalized_scope == "review":
                matches = raw_status == "review"
            elif normalized_scope == "blocked":
                matches = raw_status == "blocked"
            elif normalized_scope == "completed":
                matches = raw_status in ("completed", "failed", "cancelled", "deferred")

            if not matches:
                continue

            # Extract WHY block preserved from task data (null if missing)
            source_task = getattr(task, "source_task", None)
            proposed_by = getattr(task, "proposed_by", None)
            meta = getattr(task, "metadata", {}) or {}
            proposal_origin = meta.get("proposal_origin")

            existing_why = meta.get("why") if isinstance(meta.get("why"), dict) else {}
            if existing_why:
                source_task = existing_why.get("source_task", source_task)
                proposal_origin = existing_why.get("proposal_origin", proposal_origin)
                proposed_by = existing_why.get("proposed_by", proposed_by)
                history_transitions = existing_why.get("history_transitions", [h.model_dump() for h in task.history] if hasattr(task, "history") and task.history else [])
            else:
                history_transitions = [h.model_dump() for h in task.history] if hasattr(task, "history") and task.history else []

            why_block = {
                "source_task": source_task,
                "proposal_origin": proposal_origin,
                "proposed_by": proposed_by,
                "history_transitions": history_transitions if isinstance(history_transitions, list) else []
            }

            req_str = task.request or task.description or task.title or "Unnamed task"
            created_at_val = task.created_at or reset_at_iso

            archive_entry = {
                "task_id": task.id,
                "status": raw_status,
                "request": req_str,
                "priority": int(task.priority) if task.priority is not None else 5,
                "created_at": created_at_val,
                "reset_at": reset_at_iso,
                "scope": normalized_scope,
                "restored": False,
                "why": why_block
            }
            archived_lines.append(json.dumps(archive_entry, ensure_ascii=False))
            removed_tasks_info.append(archive_entry)
            removed_task_ids.add(task.id)

            if raw_status in cleared_counts:
                cleared_counts[raw_status] += 1
            elif raw_status in ("failed", "cancelled", "deferred"):
                cleared_counts["completed"] += 1
            else:
                cleared_counts["ready"] += 1
            total_moved += 1

        # Update state.json by removing cleared tasks
        if state_data:
            if state_data.get("active_task") and isinstance(state_data["active_task"], dict):
                if state_data["active_task"].get("id") in removed_task_ids:
                    state_data["active_task"] = None
                    if state_data.get("status") in ("running", "busy"):
                        state_data["status"] = "idle"

            if state_data.get("last_task") and isinstance(state_data["last_task"], dict):
                if state_data["last_task"].get("id") in removed_task_ids:
                    state_data["last_task"] = None

            if isinstance(state_data.get("history"), list):
                state_data["history"] = [
                    t for t in state_data["history"]
                    if not (isinstance(t, dict) and t.get("id") in removed_task_ids)
                ]

            if isinstance(state_data.get("tasks"), list):
                state_data["tasks"] = [
                    t for t in state_data["tasks"]
                    if not (isinstance(t, dict) and t.get("id") in removed_task_ids)
                ]

            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Cleanup legacy task files in .jules/queue/ if present
        for folder in [self.pending_dir, self.running_dir, self.completed_dir, self.deferred_dir]:
            for p in list(folder.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    tid = data.get("id") or p.stem
                    if tid in removed_task_ids or normalized_scope == "all":
                        p.unlink(missing_ok=True)
                except Exception:
                    pass

        # Write jsonl archive
        archive_jsonl_path = self.queue_dir / f"reset-{timestamp_str}.jsonl"
        archive_jsonl_content = "\n".join(archived_lines) + ("\n" if archived_lines else "")
        archive_jsonl_path.write_text(archive_jsonl_content, encoding="utf-8")

        # Write history markdown
        history_md_path = self.history_dir / f"reset-{timestamp_str}.md"
        md_content = f"# Queue Reset Report - {timestamp_str}\n\n"
        md_content += f"- **Scope**: `{normalized_scope}`\n"
        md_content += f"- **Reset At**: `{reset_at_iso}`\n"
        md_content += f"- **Total Moved**: `{total_moved}`\n"
        md_content += f"- **Archive JSONL**: `{archive_jsonl_path.name}`\n\n"
        md_content += "## Cleared Tasks\n\n"
        if removed_tasks_info:
            for item in removed_tasks_info:
                md_content += f"- **Task ID**: `{item['task_id']}` | **Status**: `{item['status']}` | **Priority**: `{item['priority']}`\n"
                md_content += f"  - **Request**: {item['request']}\n"
                md_content += f"  - **WHY**: source_task=`{item['why']['source_task']}`, proposed_by=`{item['why']['proposed_by']}`\n"
        else:
            md_content += "No tasks were cleared during this reset operation.\n"

        history_md_path.write_text(md_content, encoding="utf-8")

        return {
            "status": "success",
            "moved": total_moved,
            "cleared": cleared_counts,
            "archive": str(archive_jsonl_path),
            "history": str(history_md_path)
        }
