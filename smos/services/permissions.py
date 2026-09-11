from sqlalchemy.orm import Session
from smos.models.models import MemoryNode, Workspace, User
from fastapi import HTTPException, status

class PermissionService:
    @staticmethod
    def verify_workspace_access(db: Session, user_id: int, workspace_id: int):
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Check if user is a member
        # In our simplified model, workspace.members is a list of user IDs
        if user_id != workspace.owner_id and user_id not in (workspace.members or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this workspace"
            )

    @staticmethod
    def verify_memory_access(db: Session, user_id: int, node_id: int):
        node = db.query(MemoryNode).filter(MemoryNode.id == node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail="Memory node not found")

        if node.workspace_id:
            PermissionService.verify_workspace_access(db, user_id, node.workspace_id)
        elif node.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to private memory denied"
            )
