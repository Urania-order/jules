from sqlalchemy.orm import Session
from smos.models.ecology import ResearchPortal, ResearchSponsorship
from typing import List, Dict, Any

class ResearchService:
    def __init__(self, db: Session):
        self.db = db

    def open_portal(self, hypothesis_id: int):
        portal = ResearchPortal(hypothesis_id=hypothesis_id)
        self.db.add(portal)
        self.db.commit()
        self.db.refresh(portal)
        return portal

    def sponsor_research(self, portal_id: int, sponsor_id: int, amount: float):
        sponsorship = ResearchSponsorship(portal_id=portal_id, sponsor_id=sponsor_id, amount=amount)
        self.db.add(sponsorship)

        portal = self.db.query(ResearchPortal).get(portal_id)
        if portal:
            portal.budget += amount
            if portal.budget > 1000: # Mock funding threshold
                portal.status = "FUNDED"

        self.db.commit()
        self.db.refresh(sponsorship)
        return sponsorship
