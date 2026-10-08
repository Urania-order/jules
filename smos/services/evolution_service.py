import logging
from sqlalchemy.orm import Session
from smos.models.experience import Recipe, Wisdom, RecipeExecution
from smos.models.models import MemoryNode, KnowledgeLifecycleState
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter
from smos.core.interfaces import Evolvable
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class EvolutionService(Evolvable):
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

    def evolve_recipe(
        self,
        parent_id: int,
        mutations: List[Dict[str, Any]],
        include_semantic_neighbors: bool = False,
    ) -> Optional[Recipe]:
        parent = self.db.query(Recipe).get(parent_id)
        if not parent:
            return None

        semantic_neighbors = []
        if include_semantic_neighbors:
            try:
                semantic_neighbors = self.semantic_service.similar(
                    "recipe",
                    parent.id,
                )
            except Exception as e:
                logger.warning(
                    "TASK 32: semantic retrieval for parent recipe %s failed: %s",
                    parent.id,
                    e,
                )
                semantic_neighbors = []

        # Create mutated descendant
        new_recipe = Recipe(
            title=f"{parent.title} (Evolved)",
            description=parent.description,
            author_id=parent.author_id,
            problem_type=parent.problem_type,
            steps=parent.steps, # This would be modified by mutations in a real system
            parent_recipe_id=parent_id,
            mutations=mutations,
        )
        self.db.add(new_recipe)
        self.db.commit()
        self.db.refresh(new_recipe)

        if include_semantic_neighbors and semantic_neighbors:
            prov = dict(new_recipe.provenance or {})
            if "semantic_candidates" not in prov:
                prov["semantic_candidates"] = semantic_neighbors
                new_recipe.provenance = prov
                self.db.commit()
                self.db.refresh(new_recipe)

        return new_recipe

    def distill_wisdom(self, recipe_id: int):
        """Aggregate successful executions into Wisdom"""
        executions = self.db.query(RecipeExecution).filter(
            RecipeExecution.recipe_id == recipe_id,
            RecipeExecution.result == "SUCCESS"
        ).all()

        if len(executions) >= 3: # Criteria for 'Wisdom'
            recipe = self.db.query(Recipe).get(recipe_id)
            wisdom = Wisdom(
                recipe_id=recipe_id,
                domains=[recipe.problem_type],
                confidence=0.9,
                evidence={"execution_count": len(executions)}
            )
            self.db.add(wisdom)
            self.db.commit()
            self.db.refresh(wisdom)
            return wisdom
        return None

    def advance_lifecycle(self, node_id: int, target_state: KnowledgeLifecycleState = None):
        """Advance a knowledge node to the next state in its lifecycle"""
        node = self.db.query(MemoryNode).get(node_id)
        if not node:
            return None

        if target_state:
            node.lifecycle_state = target_state
        else:
            # Automatic progression logic
            states = list(KnowledgeLifecycleState)
            current_idx = states.index(node.lifecycle_state)
            if current_idx < len(states) - 1:
                node.lifecycle_state = states[current_idx + 1]
            else:
                # If at Improved Knowledge, it cycles back to Idea with new insights
                node.lifecycle_state = KnowledgeLifecycleState.IDEA
                node.content = f"REFINED FROM EXPERIENCE: {node.content}"

        self.db.commit()
        self.db.refresh(node)
        return node

    def get_lifecycle_state(self, entity_id: int) -> str:
        node = self.db.query(MemoryNode).get(entity_id)
        return str(node.lifecycle_state) if node else "None"
