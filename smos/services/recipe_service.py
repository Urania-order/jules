from sqlalchemy.orm import Session
from smos.models.experience import Recipe
from smos.models.entities import Cosmonaut
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter
from typing import List, Dict, Any, Optional

class RecipeService:
    DEFAULT_CANDIDATE_ENTITY_TYPES = [
        "recipe",
        "phenomenon",
        "context",
        "constraint",
    ]

    def __init__(
        self,
        db: Session,
        semantic_service: Optional[SemanticSearchService] = None,
    ):
        self.db = db
        self.semantic_service = (
            semantic_service
            or SemanticSearchService(db, HashFallbackAdapter())
        )

    def semantic_neighbors(
        self,
        recipe_id: int,
        k: int = 10,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return semantic neighbors of a recipe as a cross-pollination signal.

        Read-only signal. Not evidence, not a mutation, does not alter epistemic status.
        """
        if entity_types is None:
            entity_types = self.DEFAULT_CANDIDATE_ENTITY_TYPES
        return self.semantic_service.similar(
            "recipe", recipe_id, k=k, entity_types=entity_types
        )

    def semantic_search(
        self,
        query: str,
        k: int = 10,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search semantic index for cross-pollination candidates as a read-only signal."""
        if entity_types is None:
            entity_types = self.DEFAULT_CANDIDATE_ENTITY_TYPES
        return self.semantic_service.search(
            query, k=k, entity_types=entity_types
        )

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
        cosmonaut = self.db.get(Cosmonaut, cosmonaut_id)
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
        cosmonaut = self.db.get(Cosmonaut, cosmonaut_id)
        if not cosmonaut:
            return 0.0
        return cosmonaut.reputation_score
