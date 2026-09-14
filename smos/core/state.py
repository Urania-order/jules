"""System State Aggregator for Co-SMOS Control Room v0.9."""

import json
import os
from pathlib import Path
from typing import Dict, Any
from smos.core.queue import QueueManager
from smos.core.proposals import ProposalManager


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
        proposals = self.proposal_mgr.list_proposals()

        task_counts = {}
        for t in tasks:
            status_str = t.status.value if hasattr(t.status, "value") else str(t.status)
            task_counts[status_str] = task_counts.get(status_str, 0) + 1

        proposal_counts = {
            "proposed": len([p for p in proposals if p.status == "proposed"]),
            "deferred": len([p for p in proposals if p.status == "deferred"]),
            "total": len(proposals),
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
