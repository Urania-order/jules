from smos.models.models import Event, MemoryNode
from smos.services.memory_service import MemoryService
from sqlalchemy.orm import Session

class AgentOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.memory_service = MemoryService(db)

    def on_event(self, event: Event):
        # Librarian Agent logic: store in memory
        node = self.memory_service.process_event(event)
        print(f"Librarian Agent: Stored event {event.id} as node {node.id}")

        # Trigger other agents based on content
        if "Fix" in node.content or "bug" in node.content.lower():
            self.trigger_coder_agent(node)

    def trigger_coder_agent(self, node: MemoryNode):
        print(f"Coder Agent: Detected potential task in node {node.id}")
        # In a real system, this would create a TaskNode or trigger Jules
