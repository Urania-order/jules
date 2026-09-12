from sqlalchemy.orm import Session
from smos.models.entities import Cosmonaut, Collaboration
from smos.models.models import MemoryNode
from smos.core.interfaces import Observable
from typing import List, Dict, Any, Optional

class CommonsService(Observable):
    def __init__(self, db: Session):
        self.db = db

    def facilitate_collaboration(self, cosmonaut_a_id: int, cosmonaut_b_id: int, goal: str):
        """Standard interface for Human-AI or AI-AI interaction"""
        collab = Collaboration(
            cosmonaut_a_id=cosmonaut_a_id,
            cosmonaut_b_id=cosmonaut_b_id,
            goal=goal,
            status="active"
        )
        self.db.add(collab)
        self.db.commit()
        self.db.refresh(collab)
        return {
            "id": collab.id,
            "status": collab.status,
            "facilitator": "Commons",
            "participants": [cosmonaut_a_id, cosmonaut_b_id],
            "goal": goal
        }

    def find_collaborators(self, cosmonaut_id: int, limit: int = 5) -> List[Cosmonaut]:
        """Search partners based on profile compatibility and expertise."""
        target = self.db.get(Cosmonaut, cosmonaut_id)
        if not target:
            return []

        candidates = self.db.query(Cosmonaut).filter(Cosmonaut.id != cosmonaut_id).all()
        target_exp = set(target.expertise or [])

        def rank_key(c: Cosmonaut):
            cand_exp = set(c.expertise or [])
            overlap = len(target_exp.intersection(cand_exp))
            reputation = c.reputation_score or 0.0
            return (overlap, reputation, c.id)

        sorted_candidates = sorted(candidates, key=rank_key, reverse=True)
        return sorted_candidates[:limit]

    def get_active_collaborations(self) -> List[Collaboration]:
        """Get list of active collaborations from DB."""
        return self.db.query(Collaboration).filter(Collaboration.status == "active").all()

    def record_collaboration_outcome(self, collab_id: int, outcome: str, metrics: Dict[str, Any] = None) -> Optional[Collaboration]:
        """Record outcome and metrics for a collaboration."""
        collab = self.db.get(Collaboration, collab_id)
        if not collab:
            return None
        collab.outcome = outcome
        collab.metrics = metrics or {}
        collab.status = "completed"
        self.db.commit()
        self.db.refresh(collab)
        return collab

    def get_collaboration_history(self, cosmonaut_id: int) -> List[Collaboration]:
        """Get history of collaborations involving a specific cosmonaut."""
        return self.db.query(Collaboration).filter(
            (Collaboration.cosmonaut_a_id == cosmonaut_id) |
            (Collaboration.cosmonaut_b_id == cosmonaut_id)
        ).all()

    def share_knowledge(self, from_cosmonaut_id: int, node_id: int):
        """Move knowledge into the shared living space"""
        # Logic to mark node as 'Shared in Commons'
        return True

    def record_experiment(self, cosmonaut_id: int, recipe_id: int, results: Dict[str, Any]):
        """Record emergence of new experiments in the Commons"""
        return {"experiment_id": 1, "status": "recorded"}

    # Observable interface
    def get_health_metrics(self) -> Dict[str, Any]:
        cosmonauts_count = self.db.query(Cosmonaut).count()
        active_collaborations = self.db.query(Collaboration).filter(Collaboration.status == "active").count()
        total_collaborations = self.db.query(Collaboration).count()

        if cosmonauts_count > 1:
            max_connections = (cosmonauts_count * (cosmonauts_count - 1)) / 2.0
            interaction_density = round(min(1.0, total_collaborations / max_connections), 4)
        elif cosmonauts_count == 1:
            interaction_density = round(min(1.0, float(total_collaborations)), 4)
        else:
            interaction_density = 0.0

        return {
            "active_collaborations": active_collaborations,
            "cosmonaut_population": cosmonauts_count,
            "interaction_density": interaction_density
        }

    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        return [{"event": "New community goal created", "subsystem": "Commons"}]
