"""System State Aggregator for Co-SMOS Control Room v0.9."""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Union
from smos.core.queue import QueueManager
from smos.core.proposals import ProposalManager


def normalize_created_at_state(state_path: Union[str, Path] = ".co-smos/state.json") -> int:
    state_file = Path(state_path)
    if not state_file.exists():
        return 0

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return 0

    if not isinstance(data, dict):
        return 0

    normalized_count = 0

    def _normalize_entry(entry: Any) -> bool:
        if not isinstance(entry, dict):
            return False
        tid = entry.get("id")
        if not tid or not isinstance(tid, str):
            return False
        m = re.match(r"^task-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", tid)
        if not m:
            return False

        iso_from_id = f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:{m.group(6)}+00:00"
        if entry.get("created_at") != iso_from_id:
            entry["created_at"] = iso_from_id
            return True
        return False

    for h in data.get("history", []):
        if _normalize_entry(h):
            normalized_count += 1

    tasks = data.get("tasks", [])
    if isinstance(tasks, list):
        for t in tasks:
            if _normalize_entry(t):
                normalized_count += 1

    if _normalize_entry(data.get("active_task")):
        normalized_count += 1

    if _normalize_entry(data.get("last_task")):
        normalized_count += 1

    if normalized_count > 0:
        state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return normalized_count


class StateManager:
    def __init__(self):
        project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
        self.state_file = project_root / ".co-smos" / "state.json"
        self.queue_mgr = QueueManager()
        self.proposal_mgr = ProposalManager()

    def get_system_status(self) -> Dict[str, Any]:
        co_smos_state = {}
        if self.state_file.exists():
            try:
                co_smos_state = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        tasks = self.queue_mgr.list_all_tasks()
        active_proposals = self.proposal_mgr.list_proposals()
        deferred_proposals = self.proposal_mgr.list_proposals(status="deferred")
        all_proposals = active_proposals + deferred_proposals

        task_counts = {}
        for t in tasks:
            status_str = t.status.value if hasattr(t.status, "value") else str(t.status)
            task_counts[status_str] = task_counts.get(status_str, 0) + 1

        proposal_counts = {
            "proposed": len(active_proposals),
            "deferred": len(deferred_proposals),
            "total": len(all_proposals),
        }

        return {
            "status": "online",
            "co_smos_state": co_smos_state,
            "tasks_summary": {
                "total": len(tasks),
                "by_status": task_counts
            },
            "proposals_summary": proposal_counts,
            "active_task": co_smos_state.get("active_task"),
            "last_task": co_smos_state.get("last_task")
        }
