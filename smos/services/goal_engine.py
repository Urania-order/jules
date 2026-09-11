from sqlalchemy.orm import Session
from smos.models.models import MemoryNode, Workspace
from smos.models.goals import Goal, GoalStatus
from smos.services.embedding_service import embedding_service

class GoalEngine:
    def __init__(self, db: Session):
        self.db = db

    def identify_active_projects(self, user_id: int):
        # In a real system, this would analyze recurrence and keywords in MemoryNodes
        # For now, return goals explicitly marked as ACTIVE
        return self.db.query(Goal).filter(
            Goal.owner_id == user_id,
            Goal.status == GoalStatus.ACTIVE
        ).all()

    def detect_hyperfixations(self, user_id: int):
        # Mock logic: find keywords that appear in many recent memory nodes
        # This would use semantic clustering in a full implementation
        return ["Co-SMOS", "FastAPI", "PostgreSQL"]

    def find_incomplete_tasks(self, user_id: int):
        from smos.models.goals import Task, TaskStatus
        return self.db.query(Task).filter(
            Task.assigned_to_id == user_id,
            Task.status != TaskStatus.DONE
        ).all()
