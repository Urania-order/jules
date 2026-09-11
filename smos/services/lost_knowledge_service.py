from sqlalchemy.orm import Session
from smos.models.discovery import LostKnowledge, Hypothesis, DiscoveryRecovery
from typing import List, Dict, Any

class LostKnowledgeService:
    def __init__(self, db: Session):
        self.db = db

    def record_lost_knowledge(self, artifacts: List[str], unknowns: List[str]):
        lk = LostKnowledge(artifacts=artifacts, unknowns=unknowns)
        self.db.add(lk)
        self.db.commit()
        self.db.refresh(lk)
        return lk

    def add_hypothesis(self, lk_id: int, claim: str, confidence: float):
        h = Hypothesis(lost_knowledge_id=lk_id, claim=claim, confidence=confidence)
        self.db.add(h)
        self.db.commit()
        self.db.refresh(h)
        return h

    def recover_recipe(self, hypothesis_id: int, recipe_id: int):
        recovery = DiscoveryRecovery(recipe_id=recipe_id, hypotheses=[hypothesis_id], confidence=0.5)
        self.db.add(recovery)
        self.db.commit()
        return recovery
