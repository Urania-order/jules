from sqlalchemy.orm import Session
from smos.models.experience import RecipeExecution, Recipe
from typing import List, Dict, Any

class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def record_execution(self, recipe_id: int, participants: List[int], result: str, duration: float = None, cost: float = 0.0, satisfaction: float = None):
        execution = RecipeExecution(
            recipe_id=recipe_id,
            participants=participants,
            result=result,
            duration=duration,
            cost=cost,
            satisfaction=satisfaction
        )
        self.db.add(execution)

        # Update recipe success rate
        recipe = self.db.query(Recipe).get(recipe_id)
        if recipe:
            total_executions = self.db.query(RecipeExecution).filter(RecipeExecution.recipe_id == recipe_id).count() + 1
            successful_executions = self.db.query(RecipeExecution).filter(
                RecipeExecution.recipe_id == recipe_id,
                RecipeExecution.result == "SUCCESS"
            ).count() + (1 if result == "SUCCESS" else 0)
            recipe.success_rate = successful_executions / total_executions

        self.db.commit()
        self.db.refresh(execution)
        return execution
