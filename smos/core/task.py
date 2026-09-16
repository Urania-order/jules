"""Task model and status definitions for Co-SMOS Control Room v0.9."""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    REVIEW = "REVIEW"
    ACCEPTED = "ACCEPTED"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEFERRED = "DEFERRED"


class TaskHistoryItem(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: TaskStatus
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class Task(BaseModel):
    id: str
    request: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    proposed_by: Optional[str] = None
    source_task: Optional[str] = None
    session_id: Optional[str] = None
    jules_task_id: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    history: List[TaskHistoryItem] = Field(default_factory=list)

    def transition_to(self, new_status: TaskStatus, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.status = new_status
        now = datetime.now(timezone.utc).isoformat()
        if new_status == TaskStatus.RUNNING and not self.started_at:
            self.started_at = now
        elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED) and not self.finished_at:
            self.finished_at = now

        self.history.append(TaskHistoryItem(
            timestamp=now,
            status=new_status,
            message=message or f"Task state transitioned to {new_status.value}",
            details=details
        ))
