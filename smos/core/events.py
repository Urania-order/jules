"""Events and History tracking for Co-SMOS Control Room v0.9.

Events are persisted to .jules/events/events.jsonl (append-only JSONL).
In-memory list is only a cache.
"""

import json
import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class Event(BaseModel):
    id: str
    type: str
    task_id: Optional[str] = None
    source: str = "system"
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventTracker:
    _events: List[Event] = []
    _events_file: Optional[Path] = None
    _loaded: bool = False

    @classmethod
    def _get_events_file(cls) -> Path:
        if cls._events_file is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            events_dir = project_root / ".jules" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            cls._events_file = events_dir / "events.jsonl"
        return cls._events_file

    @classmethod
    def _load_from_disk(cls) -> None:
        if cls._loaded:
            return
        cls._loaded = True
        path = cls._get_events_file()
        if not path.exists():
            return
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    cls._events.append(Event(**data))
                except Exception:
                    continue
        except Exception:
            pass

    @classmethod
    def emit(
        cls,
        event_type: str,
        task_id: Optional[str] = None,
        source: str = "system",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Event:
        cls._load_from_disk()
        evt_id = f"evt-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{len(cls._events)}"
        evt = Event(
            id=evt_id,
            type=event_type,
            task_id=task_id,
            source=source,
            payload=payload or {},
        )
        cls._events.append(evt)
        try:
            path = cls._get_events_file()
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evt.model_dump(), ensure_ascii=False) + "\n")
        except Exception:
            pass
        return evt

    @classmethod
    def list_events(cls, task_id: Optional[str] = None, limit: int = 50) -> List[Event]:
        cls._load_from_disk()
        evts = cls._events
        if task_id:
            evts = [e for e in evts if e.task_id == task_id]
        return sorted(evts, key=lambda x: x.timestamp, reverse=True)[:limit]

    @classmethod
    def get_event(cls, event_id: str) -> Optional[Event]:
        for evt in cls._events:
            if evt.id == event_id:
                return evt
        return None
