"""Queue Reset Manager for Co-SMOS Control Room v1.1."""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


from datetime import datetime, timezone

class QueueResetManager:
    def __init__(self, queue_dir: Optional[Path] = None):
        if queue_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            self.project_root = project_root
            queue_dir = project_root / ".jules" / "queue"
        else:
            self.project_root = queue_dir.parent.parent
        self.queue_dir = Path(queue_dir)
        self.pending_dir = self.queue_dir / "pending"
        self.running_dir = self.queue_dir / "running"
        self.completed_dir = self.queue_dir / "completed"
        self.deferred_dir = self.queue_dir / "deferred"
        self.history_dir = self.project_root / ".jules" / "history"

        for d in [self.pending_dir, self.running_dir, self.completed_dir, self.deferred_dir, self.history_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def reset_queue(self, scope: str = "all") -> Dict[str, Any]:
        normalized_scope = scope.lower().strip()
        valid_scopes = {"all", "ready", "pending", "running", "review", "blocked", "completed"}
        if normalized_scope not in valid_scopes:
            raise ValueError(f"Invalid scope: {scope}. Must be one of {valid_scopes}")

        # Map scopes to target folders & target task statuses
        # "ready" maps to pending folder (or files in pending/running/completed whose status is READY or PENDING)
        # We search across folders for matching status
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

        # Gather files from pending, running, completed
        file_candidates = []
        for folder in [self.pending_dir, self.running_dir, self.completed_dir]:
            for p in list(folder.glob("*.json")):
                file_candidates.append(p)

        # Deduplicate files if any
        file_candidates = list({p.resolve(): p for p in file_candidates}.values())

        removed_tasks_info = []

        for p in file_candidates:
            try:
                content_text = p.read_text(encoding="utf-8")
                data = json.loads(content_text)
            except Exception:
                data = {}

            raw_status = (data.get("status") or "pending").lower().strip()

            # Determine whether this task matches the requested scope
            matches = False
            if normalized_scope == "all":
                matches = True
            elif normalized_scope == "ready":
                matches = raw_status in ("ready", "pending")
            elif normalized_scope == "pending":
                matches = raw_status == "pending"
            elif normalized_scope == "running":
                matches = raw_status == "running"
            elif normalized_scope == "review":
                matches = raw_status == "review"
            elif normalized_scope == "blocked":
                matches = raw_status == "blocked"
            elif normalized_scope == "completed":
                matches = raw_status in ("completed", "failed", "cancelled")

            if not matches:
                continue

            # Task matches scope, let's archive and move to deferred
            task_id = data.get("id") or p.stem
            req_str = data.get("request") or data.get("description") or data.get("title") or "Unnamed task"
            priority_val = int(data.get("priority", 5))
            created_at_val = data.get("created_at") or reset_at_iso

            # Extract WHY object preserved from task data (null if missing)
            source_task = data.get("source_task", None)
            proposed_by = data.get("proposed_by", None)

            # Metadata or nested why or proposal_origin
            meta = data.get("metadata") or {}
            proposal_origin = data.get("proposal_origin") or meta.get("proposal_origin", None)

            # Check if why block is nested in data
            existing_why = data.get("why") if isinstance(data.get("why"), dict) else {}
            if existing_why:
                source_task = existing_why.get("source_task", source_task)
                proposal_origin = existing_why.get("proposal_origin", proposal_origin)
                proposed_by = existing_why.get("proposed_by", proposed_by)
                history_transitions = existing_why.get("history_transitions", data.get("history", []))
            else:
                history_transitions = data.get("history", [])

            why_block = {
                "source_task": source_task,
                "proposal_origin": proposal_origin,
                "proposed_by": proposed_by,
                "history_transitions": history_transitions if isinstance(history_transitions, list) else []
            }

            archive_entry = {
                "task_id": task_id,
                "status": raw_status,
                "request": req_str,
                "priority": priority_val,
                "created_at": created_at_val,
                "reset_at": reset_at_iso,
                "scope": normalized_scope,
                "restored": False,
                "why": why_block
            }
            archived_lines.append(json.dumps(archive_entry, ensure_ascii=False))
            removed_tasks_info.append(archive_entry)

            # Move file to deferred
            dest = self.deferred_dir / p.name
            if dest.exists():
                dest = self.deferred_dir / f"{p.stem}_reset_{os.urandom(4).hex()}.json"

            data["status"] = "deferred"
            data["metadata"] = data.get("metadata", {})
            data["metadata"]["reset_from_scope"] = normalized_scope
            data["metadata"]["reset_at"] = reset_at_iso
            dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            p.unlink()

            # Increment count
            if raw_status in cleared_counts:
                cleared_counts[raw_status] += 1
            else:
                cleared_counts["ready"] += 1
            total_moved += 1

        # Write jsonl archive if any tasks were removed or write even if empty
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
