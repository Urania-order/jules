from sqlalchemy.orm import Session
from smos.models.ecology import KnowledgeImpact, KnowledgeActivation
from smos.models.models import MemoryNode
from datetime import datetime, timedelta, timezone

class ImpactService:
    def __init__(self, db: Session):
        self.db = db

    def record_impact(self, node_id: int, domain: str, impact_type: str, confidence: float):
        impact = KnowledgeImpact(
            source_node_id=node_id,
            target_domain=domain,
            influence_type=impact_type,
            confidence=confidence
        )
        self.db.add(impact)
        self.db.commit()
        self.db.refresh(impact)
        return impact

    def activate_knowledge(self, node_id: int, application: str):
        activation = self.db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id == node_id).first()
        if not activation:
            activation = KnowledgeActivation(node_id=node_id, usage_count=0, real_world_application=[])
            self.db.add(activation)
            self.db.flush()

        # Explicitly handle list mutation for SQLAlchemy
        new_apps = list(activation.real_world_application)
        new_apps.append(application)
        activation.real_world_application = new_apps

        activation.usage_count += 1
        activation.last_reinforced_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(activation)
        return activation

    def calculate_decay(self, node_id: int):
        activation = self.db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id == node_id).first()
        if not activation:
            return 1.0 # Max decay

        days_since = (datetime.now(timezone.utc).replace(tzinfo=None) - activation.last_reinforced_at.replace(tzinfo=None)).days
        decay = activation.decay_rate * days_since
        return min(1.0, decay)
