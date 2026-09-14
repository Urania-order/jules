"""Proposals Core Manager for Co-SMOS Control Room v0.9."""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from smos.core.task import Task, TaskStatus


class Proposal(BaseModel):
    id: str
    proposed_by: str = "jules"
    source_task: Optional[str] = None
    description: str
    priority: int = 3
    status: str = "proposed"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProposalManager:
    def __init__(self, queue_dir: Optional[Path] = None):
        if queue_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            queue_dir = project_root / ".jules" / "queue"
        self.queue_dir = Path(queue_dir)
        self.proposed_dir = self.queue_dir / "proposed"
        self.deferred_dir = self.queue_dir / "deferred"
        self.pending_dir = self.queue_dir / "pending"

        for d in [self.proposed_dir, self.deferred_dir, self.pending_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def list_proposals(self, status: Optional[str] = None) -> List[Proposal]:
        proposals = []
        directories = [self.proposed_dir, self.deferred_dir]
        for folder in directories:
            for p in folder.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    prop = Proposal(**data)
                    if status is None or prop.status.lower() == status.lower():
                        proposals.append(prop)
                except Exception:
                    continue
        return proposals

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        for p in self.list_proposals():
            if p.id == proposal_id:
                return p
        return None

    def accept_proposal(self, proposal_id: str) -> Optional[Task]:
        prop = self.get_proposal(proposal_id)
        if not prop:
            return None

        # Remove proposal files from proposed and deferred
        for folder in [self.proposed_dir, self.deferred_dir]:
            pf = folder / f"{proposal_id}.json"
            if pf.exists():
                pf.unlink()

        # Convert to pending Task
        task_id = f"task-{proposal_id}" if not proposal_id.startswith("task-") else proposal_id
        task = Task(
            id=task_id,
            request=prop.description,
            title=prop.description[:50],
            description=prop.description,
            status=TaskStatus.PENDING,
            priority=prop.priority,
            proposed_by=prop.proposed_by,
            source_task=prop.source_task,
        )
        task.transition_to(TaskStatus.PENDING, message="Proposal accepted and converted to Task")

        target_file = self.pending_dir / f"{task_id}.json"
        task_data = task.model_dump()
        task_data["status"] = "pending"
        target_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return task

    def defer_proposal(self, proposal_id: str) -> Optional[Proposal]:
        prop = self.get_proposal(proposal_id)
        if not prop:
            return None

        for folder in [self.proposed_dir, self.deferred_dir]:
            pf = folder / f"{proposal_id}.json"
            if pf.exists():
                pf.unlink()

        prop.status = "deferred"
        target_file = self.deferred_dir / f"{proposal_id}.json"
        target_file.write_text(json.dumps(prop.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return prop

    def reject_proposal(self, proposal_id: str) -> bool:
        found = False
        for folder in [self.proposed_dir, self.deferred_dir]:
            pf = folder / f"{proposal_id}.json"
            if pf.exists():
                pf.unlink()
                found = True
        return found

    def modify_proposal(self, proposal_id: str, new_description: Optional[str] = None, new_priority: Optional[int] = None) -> Optional[Proposal]:
        prop = self.get_proposal(proposal_id)
        if not prop:
            return None

        if new_description is not None:
            prop.description = new_description
        if new_priority is not None:
            prop.priority = new_priority

        folder = self.deferred_dir if prop.status == "deferred" else self.proposed_dir
        pf = folder / f"{proposal_id}.json"
        pf.write_text(json.dumps(prop.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return prop
