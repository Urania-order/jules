import pytest
from smos.core.task import Task, TaskStatus

def test_task_model_initialization():
    t = Task(
        id="task-001",
        request="Test task request",
        priority=5
    )
    assert t.id == "task-001"
    assert t.status == TaskStatus.PENDING
    assert t.priority == 5
    assert len(t.history) == 0

def test_task_status_transition():
    t = Task(
        id="task-002",
        request="Task for status testing"
    )
    t.transition_to(TaskStatus.RUNNING, message="Starting task execution")
    assert t.status == TaskStatus.RUNNING
    assert t.started_at is not None
    assert len(t.history) == 1
    assert t.history[0].status == TaskStatus.RUNNING

    t.transition_to(TaskStatus.COMPLETED, message="Task completed successfully")
    assert t.status == TaskStatus.COMPLETED
    assert t.finished_at is not None
    assert len(t.history) == 2
