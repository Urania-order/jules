from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from smos.models.context_exposure import ContextExposure, AgentType
from smos.models.models import EpistemicStatus

class ContextExposureService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        agent_type,
        agent_id: Optional[int] = None,
        role: Optional[str] = None,
        context_ids: Optional[List[int]] = None,
        knowledge_ids: Optional[List[int]] = None,
        conclusion: Optional[Dict[str, Any]] = None,
        hidden_context_ids: Optional[List[int]] = None,
        epistemic_status=None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> ContextExposure:
        exposure = ContextExposure(
            agent_type=AgentType.from_str(agent_type),
            agent_id=agent_id,
            role=role,
            context_ids=list(context_ids or []),
            knowledge_ids=list(knowledge_ids or []),
            hidden_context_ids=list(hidden_context_ids or []),
            conclusion=dict(conclusion or {}),
            epistemic_status=epistemic_status or EpistemicStatus.OBSERVED,
            provenance=dict(provenance or {}),
        )
        self.db.add(exposure)
        self.db.commit()
        self.db.refresh(exposure)
        return exposure

    def get(self, exposure_id: int) -> Optional[ContextExposure]:
        return self.db.query(ContextExposure).filter(ContextExposure.id == exposure_id).first()

    def list(
        self,
        agent_type=None,
        agent_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ContextExposure]:
        q = self.db.query(ContextExposure)
        if agent_type is not None:
            q = q.filter(ContextExposure.agent_type == AgentType.from_str(agent_type))
        if agent_id is not None:
            q = q.filter(ContextExposure.agent_id == agent_id)
        return q.order_by(ContextExposure.created_at.desc()).offset(offset).limit(limit).all()

    def delete(self, exposure_id: int) -> bool:
        e = self.get(exposure_id)
        if not e:
            return False
        self.db.delete(e)
        self.db.commit()
        return True

    def convergence_signals(
        self,
        conclusion_filter: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Aggregate exposures by shared context fragments.

        Returns a SIGNAL, not evidence of truth.
        """
        exposures = self.list(limit=limit)
        # Group by frozenset(context_ids) for shared fragment detection
        groups: Dict[frozenset, List[ContextExposure]] = {}
        for e in exposures:
            key = frozenset(e.context_ids or [])
            groups.setdefault(key, []).append(e)

        fragments = []
        for key, items in groups.items():
            if len(items) < 2:
                continue
            fragments.append({
                "context_ids": sorted(list(key)),
                "agent_count": len(items),
                "agents": [
                    {
                        "agent_type": (i.agent_type.value if isinstance(i.agent_type, AgentType) else i.agent_type),
                        "agent_id": i.agent_id,
                        "role": i.role,
                        "conclusion": i.conclusion,
                    }
                    for i in items
                ],
            })
        fragments.sort(key=lambda f: f["agent_count"], reverse=True)
        return {
            "total_exposures": len(exposures),
            "context_fragments": fragments,
            "note": "This is a SIGNAL, not evidence of truth.",
        }
