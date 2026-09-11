from sqlalchemy.orm import Session
from smos.models.entities import Constellation, Cosmonaut
from smos.models.experience import Recipe
from typing import List

class CommunityService:
    def __init__(self, db: Session):
        self.db = db

    def inherit_experience(self, target_cosmonaut_id: int, topic: str):
        """Find successful recipes on a topic and 'link' them to the cosmonaut"""
        recipes = self.db.query(Recipe).filter(
            Recipe.problem_type == topic,
            Recipe.success_rate >= 0.8
        ).all()

        # Logic to 'inherit' would update the cosmonaut's expertise
        cosmonaut = self.db.query(Cosmonaut).get(target_cosmonaut_id)
        if cosmonaut:
            cosmonaut.expertise.extend([topic])
            self.db.commit()

        return recipes

    def create_constellation(self, mission: str, members: List[int]):
        constellation = Constellation(
            mission=mission,
            members=members
        )
        self.db.add(constellation)
        self.db.commit()
        self.db.refresh(constellation)
        return constellation
