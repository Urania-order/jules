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

        # Write jsonl archive (append if file for current second already exists)
        archive_jsonl_path = self.queue_dir / f"reset-{timestamp_str}.jsonl"
        archive_jsonl_content = "\n".join(archived_lines) + ("\n" if archived_lines else "")
        if archive_jsonl_path.exists():
            existing = archive_jsonl_path.read_text(encoding="utf-8")
            if existing and not existing.endswith("\n"):
                existing += "\n"
            archive_jsonl_content = existing + archive_jsonl_content
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

    def export_archive(self, fmt: str = "jsonl", scope: str = "all") -> tuple[str, str, str]:
        """
        Export merged archive files in CSV, Markdown, or JSONL format.
        
        :param fmt: 'csv' | 'md' | 'jsonl'
        :param scope: 'all' or specific scope string to filter by
        :return: Tuple of (content_string, filename, media_type)
        """
        normalized_fmt = fmt.lower().strip()
        if normalized_fmt not in ("csv", "md", "jsonl"):
            raise ValueError("INVALID_FORMAT")

        normalized_scope = scope.lower().strip()

        # Find all reset-*.jsonl files sorted chronologically
        archive_files = sorted(self.queue_dir.glob("reset-*.jsonl"))
        if not archive_files:
            raise FileNotFoundError("ARCHIVE_EMPTY")

        entries = []
        for path in archive_files:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if normalized_scope != "all":
                            rec_scope = (record.get("scope") or "").lower().strip()
                            rec_status = (record.get("status") or "").lower().strip()
                            matches = (
                                rec_scope == normalized_scope or
                                rec_status == normalized_scope or
                                (normalized_scope in ("ready", "pending") and rec_scope in ("ready", "pending")) or
                                (normalized_scope in ("ready", "pending") and rec_status in ("ready", "pending"))
                            )
                            if not matches:
                                continue
                        entries.append(record)
                    except Exception:
                        pass
            except Exception:
                pass

        if not entries:
            raise FileNotFoundError("ARCHIVE_EMPTY")

        now_utc = datetime.now(timezone.utc)
        ts_filename = now_utc.strftime("%Y%m%d-%H%M%S")

        if normalized_fmt == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["task_id", "status", "request", "priority", "created_at", "reset_at", "scope", "restored"])
            for entry in entries:
                writer.writerow([
                    entry.get("task_id", ""),
                    entry.get("status", ""),
                    entry.get("request", ""),
                    entry.get("priority", 5),
                    entry.get("created_at", ""),
                    entry.get("reset_at", ""),
                    entry.get("scope", ""),
                    entry.get("restored", False)
                ])
            content = output.getvalue()
            filename = f"reset-archive-{ts_filename}.csv"
            media_type = "text/csv"

        elif normalized_fmt == "md":
            md_lines = [
                "# Queue Archive — Export",
                f"Total: {len(entries)} tasks",
                "---"
            ]
            for entry in entries:
                md_lines.append(f"## {entry.get('task_id', 'unknown')}")
                md_lines.append(f"- Status: {str(entry.get('status', '')).upper()}")
                md_lines.append(f"- Request: {entry.get('request', '')}")
                md_lines.append(f"- Priority: {entry.get('priority', 5)}")
                md_lines.append(f"- Created: {entry.get('created_at', '')}")
                md_lines.append(f"- Reset: {entry.get('reset_at', '')}")
                md_lines.append(f"- Scope: {entry.get('scope', '')}")
                
                why = entry.get("why") if isinstance(entry.get("why"), dict) else {}
                md_lines.append("- WHY:")
                md_lines.append(f"  - source_task: {why.get('source_task', 'None') or 'None'}")
                md_lines.append(f"  - proposed_by: {why.get('proposed_by', 'None') or 'None'}")
                md_lines.append("  - history:")
                history = why.get("history_transitions", [])
                if isinstance(history, list) and history:
                    for h in history:
                        if isinstance(h, dict):
                            ts = h.get("timestamp", "")
                            st = str(h.get("status", "")).upper()
                            msg = h.get("message", "")
                            md_lines.append(f"    - [{ts}] {st}: {msg}")
                        else:
                            md_lines.append(f"    - {h}")
                else:
                    md_lines.append("    - None")
            content = "\n".join(md_lines) + "\n"
            filename = f"reset-archive-{ts_filename}.md"
            media_type = "text/markdown"

        else: # jsonl
            jsonl_lines = [json.dumps(e, ensure_ascii=False) for e in entries]
            content = "\n".join(jsonl_lines) + ("\n" if jsonl_lines else "")
            filename = f"reset-archive-{ts_filename}.jsonl"
            media_type = "application/x-jsonlines"

        return content, filename, media_type

    def list_archive_entries(self) -> list[Dict[str, Any]]:
        """
        List all archive entries across all reset-*.jsonl files with unique archive_ids.
        """
        archive_files = sorted(self.queue_dir.glob("reset-*.jsonl"))
        entries = []
        for path in archive_files:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                for idx, line in enumerate(lines, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        archive_id = f"{path.name}:{idx}"
                        entries.append({
                            "archive_id": archive_id,
                            "task_id": record.get("task_id", ""),
                            "status": record.get("status", ""),
                            "request": record.get("request", ""),
                            "priority": record.get("priority", 5),
                            "created_at": record.get("created_at", ""),
                            "reset_at": record.get("reset_at", ""),
                            "scope": record.get("scope", ""),
                            "restored": bool(record.get("restored", False)),
                            "why": record.get("why", {})
                        })
                    except Exception:
                        pass
            except Exception:
                pass
        return entries

    def undo_archive(self, archive_ids: list[str], confirm: str = "") -> Dict[str, Any]:
        """
        Restore specified archived tasks by archive_id.
        """
        if confirm != "UNDO":
            raise ValueError("Confirmation string 'UNDO' is required")

        restored_ids = []
        failed_ids = []

        # Index current files to avoid multiple reads/writes per file
        entries_by_file: Dict[str, list[tuple[int, str]]] = {}
        for aid in archive_ids:
            if ":" not in aid:
                failed_ids.append(aid)
                continue
            fname, lnum_str = aid.split(":", 1)
            try:
                lnum = int(lnum_str)
                entries_by_file.setdefault(fname, []).append((lnum, aid))
            except ValueError:
                failed_ids.append(aid)

        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        import uuid
        for fname, target_lines in entries_by_file.items():
            fpath = self.queue_dir / fname
            if not fpath.exists():
                for _, aid in target_lines:
                    failed_ids.append(aid)
                continue

            try:
                lines = fpath.read_text(encoding="utf-8").splitlines()
                file_modified = False

                for lnum, aid in target_lines:
                    if lnum < 1 or lnum > len(lines):
                        failed_ids.append(aid)
                        continue

                    line_str = lines[lnum - 1].strip()
                    if not line_str:
                        failed_ids.append(aid)
                        continue

                    try:
                        record = json.loads(line_str)
                    except Exception:
                        failed_ids.append(aid)
                        continue

                    if record.get("restored"):
                        # Already restored -> skip
                        continue

                    # Create new Task
                    new_task_id = f"task-{now_utc.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
                    req_str = record.get("request", "Unnamed task")
                    prio = int(record.get("priority", 5))

                    why_data = record.get("why") if isinstance(record.get("why"), dict) else {}
                    existing_transitions = why_data.get("history_transitions", [])
                    if not isinstance(existing_transitions, list):
                        existing_transitions = []

                    new_transition = {
                        "timestamp": now_iso,
                        "status": "PENDING",
                        "message": f"RESTORED from {aid}"
                    }
                    updated_transitions = existing_transitions + [new_transition]

                    updated_why = {
                        "source_task": why_data.get("source_task"),
                        "proposal_origin": why_data.get("proposal_origin"),
                        "proposed_by": why_data.get("proposed_by"),
                        "history_transitions": updated_transitions
                    }

                    from smos.core.task import Task, TaskStatus, TaskHistoryItem

                    # Build history list for Task model
                    task_history = []
                    for h in updated_transitions:
                        if isinstance(h, dict):
                            st_str = str(h.get("status", "PENDING")).upper()
                            try:
                                st_enum = TaskStatus(st_str)
                            except ValueError:
                                st_enum = TaskStatus.PENDING
                            task_history.append(TaskHistoryItem(
                                timestamp=h.get("timestamp", now_iso),
                                status=st_enum,
                                message=h.get("message")
                            ))

                    new_task = Task(
                        id=new_task_id,
                        request=req_str,
                        title=req_str[:50],
                        description=req_str,
                        status=TaskStatus.PENDING,
                        priority=prio,
                        created_at=now_iso,
                        source_task=updated_why.get("source_task"),
                        proposed_by=updated_why.get("proposed_by"),
                        metadata={"why": updated_why},
                        history=task_history
                    )

                    self.queue_mgr.save_task(new_task)

                    # Mark archive line restored: true
                    record["restored"] = True
                    lines[lnum - 1] = json.dumps(record, ensure_ascii=False)
                    file_modified = True
                    restored_ids.append(aid)

                if file_modified:
                    fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")

            except Exception:
                for _, aid in target_lines:
                    if aid not in restored_ids and aid not in failed_ids:
                        failed_ids.append(aid)

        return {
            "status": "success",
            "restored": restored_ids,
            "failed": failed_ids
        }

    def undo_archive_filter(
        self,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        scope: Optional[str] = None,
        search: Optional[str] = None,
        confirm: str = "",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        all_entries = self.list_archive_entries()

        matched_entries = []
        for entry in all_entries:
            if status:
                if (entry.get("status") or "").lower() != status.lower():
                    continue
            if date_from:
                if (entry.get("reset_at") or "") < date_from:
                    continue
            if date_to:
                if (entry.get("reset_at") or "") > date_to:
                    continue
            if scope:
                if (entry.get("scope") or "").lower() != scope.lower():
                    continue
            if search:
                s_lower = search.lower()
                req_text = (entry.get("request") or "").lower()
                tid_text = (entry.get("task_id") or "").lower()
                if s_lower not in req_text and s_lower not in tid_text:
                    continue
            matched_entries.append(entry)

        if dry_run:
            return {
                "status": "success",
                "matched": len(matched_entries),
                "entries": matched_entries
            }

        if confirm != "UNDO":
            raise ValueError("Confirmation string 'UNDO' is required")

        unrestored_ids = [e["archive_id"] for e in matched_entries if not e.get("restored")]
        if not unrestored_ids:
            return {
                "status": "success",
                "matched": len(matched_entries),
                "restored": [],
                "failed": []
            }

        undo_res = self.undo_archive(archive_ids=unrestored_ids, confirm=confirm)
        return {
            "status": "success",
            "matched": len(matched_entries),
            "restored": undo_res["restored"],
            "failed": undo_res["failed"]
        }
