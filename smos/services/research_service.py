from sqlalchemy.orm import Session
from smos.models.ecology import ResearchPortal, ResearchSponsorship
from smos.core.interfaces import Evolvable, Observable
from typing import List, Dict, Any, Optional

class ResearchService(Evolvable, Observable):
    FUNDING_THRESHOLD: float = 1000.0

    def __init__(self, db: Session):
        self.db = db

    def open_portal(self, hypothesis_id: int, initial_budget: float = 0.0) -> ResearchPortal:
        """Open a research portal for a hypothesis."""
        portal = self.db.query(ResearchPortal).filter(ResearchPortal.hypothesis_id == hypothesis_id).first()
        if not portal:
            portal = ResearchPortal(hypothesis_id=hypothesis_id, budget=initial_budget, status="OPEN")
            self.db.add(portal)
            self.db.commit()
            self.db.refresh(portal)
        return portal

    def get_portal(self, portal_id: int) -> Optional[ResearchPortal]:
        """Retrieve a research portal by ID."""
        return self.db.get(ResearchPortal, portal_id)

    def list_portals(self, status: Optional[str] = None) -> List[ResearchPortal]:
        """List all research portals, optionally filtered by status."""
        query = self.db.query(ResearchPortal)
        if status:
            query = query.filter(ResearchPortal.status == status)
        return query.all()

    def sponsor_research(
        self,
        portal_id: int,
        sponsor_id: int,
        amount: float,
        is_transparent: bool = True
    ) -> Optional[ResearchSponsorship]:
        """Sponsor a research portal with a financial contribution."""
        portal = self.db.get(ResearchPortal, portal_id)
        if not portal:
            return None

        sponsorship = ResearchSponsorship(
            portal_id=portal_id,
            sponsor_id=sponsor_id,
            amount=amount,
            is_transparent=is_transparent
        )
        self.db.add(sponsorship)

        portal.budget = (portal.budget or 0.0) + amount
        if portal.budget >= self.FUNDING_THRESHOLD and portal.status == "OPEN":
            portal.status = "FUNDED"

        self.db.commit()
        self.db.refresh(sponsorship)
        return sponsorship

    def record_outcome(self, portal_id: int, outcome: str) -> Optional[ResearchPortal]:
        """Record a research outcome or milestone for a portal."""
        portal = self.db.get(ResearchPortal, portal_id)
        if not portal:
            return None

        current_outcomes = list(portal.outcomes or [])
        current_outcomes.append(outcome)
        portal.outcomes = current_outcomes

        self.db.commit()
        self.db.refresh(portal)
        return portal

    def close_portal(self, portal_id: int, reason: Optional[str] = None) -> Optional[ResearchPortal]:
        """Close/complete a research portal."""
        portal = self.db.get(ResearchPortal, portal_id)
        if not portal:
            return None

        portal.status = "COMPLETED"
        if reason:
            self.record_outcome(portal_id, f"Closed: {reason}")
        else:
            self.db.commit()
            self.db.refresh(portal)
        return portal

    # Evolvable interface
    def advance_lifecycle(self, entity_id: int) -> Optional[ResearchPortal]:
        """Advance portal lifecycle: OPEN -> FUNDED -> COMPLETED."""
        portal = self.db.get(ResearchPortal, entity_id)
        if not portal:
            return None

        if portal.status == "OPEN":
            portal.status = "FUNDED"
        elif portal.status == "FUNDED":
            portal.status = "COMPLETED"

        self.db.commit()
        self.db.refresh(portal)
        return portal

    def get_lifecycle_state(self, entity_id: int) -> str:
        """Get lifecycle state of portal."""
        portal = self.db.get(ResearchPortal, entity_id)
        return portal.status if portal else "NON_EXISTENT"

    # Observable interface
    def get_health_metrics(self) -> Dict[str, Any]:
        """Return health metrics for the research portal subsystem."""
        total_portals = self.db.query(ResearchPortal).count()
        open_portals = self.db.query(ResearchPortal).filter(ResearchPortal.status == "OPEN").count()
        funded_portals = self.db.query(ResearchPortal).filter(ResearchPortal.status == "FUNDED").count()
        completed_portals = self.db.query(ResearchPortal).filter(ResearchPortal.status == "COMPLETED").count()

        sponsorships = self.db.query(ResearchSponsorship).all()
        total_funds = sum(s.amount for s in sponsorships if s.amount)
        avg_sponsorship = total_funds / len(sponsorships) if sponsorships else 0.0

        return {
            "total_portals": total_portals,
            "open_portals": open_portals,
            "funded_portals": funded_portals,
            "completed_portals": completed_portals,
            "total_sponsorship_funds": round(total_funds, 2),
            "average_sponsorship_amount": round(avg_sponsorship, 2)
        }

    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        """Return summary of research portal evolution events."""
        portals = self.db.query(ResearchPortal).all()
        summary = []
        for p in portals:
            sponsorship_count = self.db.query(ResearchSponsorship).filter(ResearchSponsorship.portal_id == p.id).count()
            summary.append({
                "portal_id": p.id,
                "hypothesis_id": p.hypothesis_id,
                "status": p.status,
                "budget": p.budget,
                "sponsorship_count": sponsorship_count,
                "outcomes_count": len(p.outcomes or [])
            })
        return summary
