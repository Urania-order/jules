"""Events and History tracking for Co-SMOS Control Room v0.9."""

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

    @classmethod
    def emit(cls, event_type: str, task_id: Optional[str] = None, source: str = "system", payload: Optional[Dict[str, Any]] = None) -> Event:
        evt_id = f"evt-{int(datetime.now(timezone.utc).timestamp()*1000)}"
        evt = Event(
            id=evt_id,
            type=event_type,
            task_id=task_id,
            source=source,
            payload=payload or {}
        )
        cls._events.append(evt)
        return evt

    @classmethod
    def list_events(cls, task_id: Optional[str] = None, limit: int = 50) -> List[Event]:
        evts = cls._events
        if task_id:
            evts = [e for e in evts if e.task_id == task_id]
        return sorted(evts, key=lambda x: x.timestamp, reverse=True)[:limit]
