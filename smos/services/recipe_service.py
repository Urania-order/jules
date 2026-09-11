from sqlalchemy.orm import Session
from smos.models.experience import Recipe
from smos.models.entities import Cosmonaut
from typing import List, Dict, Any

class RecipeService:
    def __init__(self, db: Session):
        self.db = db

    def create_recipe(self, title: str, author_id: int, steps: List[str], problem_type: str):
        recipe = Recipe(
            title=title,
            author_id=author_id,
            steps=steps,
            problem_type=problem_type
        )
        self.db.add(recipe)
        self.db.commit()
        self.db.refresh(recipe)
        return recipe

    def update_reputation(self, cosmonaut_id: int, success: bool):
        cosmonaut = self.db.query(Cosmonaut).get(cosmonaut_id)
        if not cosmonaut:
            return

        if success:
            cosmonaut.successful_recipes_count += 1
            cosmonaut.reputation_score += 10.0
        else:
            cosmonaut.failed_recipes_count += 1
            cosmonaut.reputation_score -= 5.0

        self.db.commit()
        return cosmonaut

    def get_trust_score(self, cosmonaut_id: int):
        cosmonaut = self.db.query(Cosmonaut).get(cosmonaut_id)
        if not cosmonaut:
            return 0.0
        return cosmonaut.reputation_score
