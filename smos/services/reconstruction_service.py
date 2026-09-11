from sqlalchemy.orm import Session
from smos.models.experience import Reconstruction, CausalRelation, AntiRecipe
from typing import List, Dict, Any

class ReconstructionService:
    def __init__(self, db: Session):
        self.db = db

    def reconstruct_experience(self, observations: List[str], artifacts: List[str], witnesses: List[str], level: str = "RECONSTRUCTED"):
        reconstruction = Reconstruction(
            observations=observations,
            artifacts=artifacts,
            witnesses=witnesses,
            evidence_level=level,
            confidence=0.7,
            inferred_facts={"scenario": "Failure during deployment reconstructed from logs"}
        )
        self.db.add(reconstruction)
        self.db.commit()
        self.db.refresh(reconstruction)
        return reconstruction

    def create_anti_recipe(self, reconstruction_id: int, pattern: str, signs: List[str]):
        anti = AntiRecipe(
            description=f"Avoid this: {pattern}",
            failure_pattern=pattern,
            warning_signs=signs,
            reconstruction_id=reconstruction_id
        )
        self.db.add(anti)
        self.db.commit()
        self.db.refresh(anti)
        return anti
