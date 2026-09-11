from sqlalchemy.orm import Session
from smos.models.ecology import ValueAssessment, KnowledgeActivation, KnowledgeImpact
from smos.models.models import MemoryNode
from smos.core.interfaces import Observable
from typing import Dict, Any, List
from datetime import datetime, timezone

class ValueEcologyService(Observable):
    def __init__(self, db: Session):
        self.db = db

    def calculate_metrics(self, node_id: int) -> Dict[str, float]:
        activations = self.db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id == node_id).first()
        impacts = self.db.query(KnowledgeImpact).filter(KnowledgeImpact.source_node_id == node_id).all()

        usage_count = activations.usage_count if activations else 0
        impact_count = len(impacts)

        energy = min(1.0, (usage_count * 0.1) + (impact_count * 0.2))
        resonance = sum(i.confidence for i in impacts) / impact_count if impact_count > 0 else 0.1
        node = self.db.query(MemoryNode).get(node_id)
        potential = node.importance if node else 0.5

        return {
            "energy": energy,
            "potential": potential,
            "resonance": resonance,
            "diffusion": min(1.0, impact_count * 0.25)
        }

    def update_node_physics(self, node_id: int):
        metrics = self.calculate_metrics(node_id)
        assessment = self.db.query(ValueAssessment).filter(ValueAssessment.node_id == node_id).first()
        if not assessment:
            assessment = ValueAssessment(node_id=node_id)
            self.db.add(assessment)

        # Principle: Knowledge value emerges through implementation and human benefit
        assessment.knowledge_value = metrics["energy"] * metrics["resonance"]
        assessment.social_impact = metrics["diffusion"]

        # New ecosystem-oriented metrics
        assessment.environmental_impact = 0.9 # Mock: high environmental benefit
        assessment.human_benefit = 0.85 # High societal benefit

        self.db.commit()
        return metrics

    # Observable interface
    def get_health_metrics(self) -> Dict[str, Any]:
        assessments = self.db.query(ValueAssessment).all()
        if not assessments:
            return {"avg_value": 0.0}
        return {
            "avg_value": sum(a.knowledge_value for a in assessments) / len(assessments),
            "total_social_impact": sum(a.social_impact for a in assessments)
        }

    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        return []
