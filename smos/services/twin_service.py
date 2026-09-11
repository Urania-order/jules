from sqlalchemy.orm import Session
from smos.models.entities import DigitalTwin
from typing import Dict, Any

class TwinService:
    def __init__(self, db: Session):
        self.db = db

    def create_twin(self, owner_id: int, goals: list, preferences: Dict[str, Any]):
        twin = DigitalTwin(
            owner_id=owner_id,
            goals=goals,
            preferences=preferences
        )
        self.db.add(twin)
        self.db.commit()
        self.db.refresh(twin)
        return twin

    def negotiate(self, from_twin_id: int, to_twin_id: int, proposal: Dict[str, Any]):
        """Mock negotiation protocol between twins"""
        print(f"Twin {from_twin_id} proposing to Twin {to_twin_id}: {proposal.get('goal')}")
        # Logic would involve checking preferences and goals
        return {"status": "ACCEPTED", "rationale": "Aligns with owner goals"}
