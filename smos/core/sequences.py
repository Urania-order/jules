"""Sequence Recording and Replay Manager for Co-SMOS Control Room v1.1."""

import json
import os
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from smos.core.task import Task
from smos.core.queue import QueueManager
from smos.core.batch import BatchManager


class CapturedTask(BaseModel):
    id: str
    request: str
    priority: int = 5
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaskSequence(BaseModel):
    id: str
    name: str = "Recorded Sequence"
    tasks: List[CapturedTask] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SequenceManager:
    def __init__(self, sequences_dir: Optional[Path] = None):
        if sequences_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            sequences_dir = project_root / ".jules" / "sequences"
        self.sequences_dir = Path(sequences_dir)
        self.sequences_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.sequences_dir / "recording_state.json"

    def is_recording(self) -> bool:
        if not self._state_file.exists():
            return False
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            return bool(data.get("recording", False))
        except Exception:
            return False

    def start_recording(self) -> Dict[str, Any]:
        state = {
            "recording": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "tasks": []
        }
        self._state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"status": "recording_started", "recording": True}

    def record_task_if_active(self, task: Task) -> None:
        if not self.is_recording():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            captured = {
                "id": task.id,
                "request": task.request or task.title or task.description or "Unnamed task",
                "priority": task.priority,
                "created_at": task.created_at
            }
            data.setdefault("tasks", []).append(captured)
            self._state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

    def stop_recording(self, name: Optional[str] = None) -> Dict[str, Any]:
        captured_tasks = []
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                captured_tasks = [CapturedTask(**t) for t in data.get("tasks", [])]
            except Exception:
                pass
            self._state_file.unlink(missing_ok=True)

        seq_id = f"seq-{int(time.time() * 1000)}"
        seq = TaskSequence(
            id=seq_id,
            name=name or f"Sequence {seq_id}",
            tasks=captured_tasks,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.save_sequence(seq)
        return {"sequence_id": seq.id, "tasks": [t.model_dump() for t in seq.tasks], "sequence": seq.model_dump()}

    def save_sequence(self, sequence: TaskSequence) -> None:
        filepath = self.sequences_dir / f"{sequence.id}.json"
        data = sequence.model_dump()
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def list_sequences(self) -> List[TaskSequence]:
        sequences = []
        for p in sorted(self.sequences_dir.glob("seq-*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                sequences.append(TaskSequence(**data))
            except Exception:
                continue
        sequences.sort(key=lambda x: x.created_at, reverse=True)
        return sequences

    def get_sequence(self, sequence_id: str) -> Optional[TaskSequence]:
        p = self.sequences_dir / f"{sequence_id}.json"
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return TaskSequence(**data)
        except Exception:
            return None

    def replay_sequence(
        self,
        sequence_id: str,
        mode: str = "sequential",
        schedule: str = "now",
        concurrency: int = 3,
        queue_manager: Optional[QueueManager] = None,
        batch_manager: Optional[BatchManager] = None
    ) -> Dict[str, Any]:
        seq = self.get_sequence(sequence_id)
        if not seq:
            raise ValueError(f"Sequence {sequence_id} not found")

        qm = queue_manager or QueueManager()
        bm = batch_manager or BatchManager()

        created_tasks = []
        created_task_ids = []

        for item in seq.tasks:
            task_id = f"task-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
            t = Task(
                id=task_id,
                request=item.request,
                title=item.request[:50],
                priority=item.priority,
                proposed_by="sequence_replay"
            )
            qm.save_task(t)
            created_tasks.append(t.model_dump())
            created_task_ids.append(t.id)

        # Dispatch via batch manager or queue mode
        batch_id = None
        if created_task_ids:
            batch_schedule = schedule
            if mode == "sequential" and schedule == "now":
                batch_schedule = "now-sequential"

            batch = bm.create_batch(
                task_ids=created_task_ids,
                schedule=batch_schedule,
                concurrency=concurrency if mode == "parallel" else 1,
                status="accepted" if schedule in ("now", "now-sequential") else "queued",
                started=created_task_ids if schedule in ("now", "now-sequential") else [],
                queued=[] if schedule in ("now", "now-sequential") else created_task_ids,
                autonomy="AUTO"
            )
            batch_id = batch.id

        return {
            "created_tasks": created_tasks,
            "batch_id": batch_id
        }
