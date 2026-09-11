from sqlalchemy.orm import Session
from smos.models.ecology import ReputationCredit
from typing import List

class EconomyService:
    def __init__(self, db: Session):
        self.db = db

    def issue_reputation_credits(self, cosmonaut_id: int, amount: float, reason: str):
        credit = ReputationCredit(
            cosmonaut_id=cosmonaut_id,
            amount=amount,
            reason=reason
        )
        self.db.add(credit)
        self.db.commit()
        self.db.refresh(credit)
        return credit

    def calculate_total_balance(self, cosmonaut_id: int):
        credits = self.db.query(ReputationCredit).filter(ReputationCredit.cosmonaut_id == cosmonaut_id).all()
        return sum(c.amount for c in credits)
