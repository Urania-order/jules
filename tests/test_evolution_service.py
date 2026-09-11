from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut
from smos.services.recipe_service import RecipeService
from smos.services.evolution_service import EvolutionService

def test_evolution_service():
    db = SessionLocal()

    c = Cosmonaut(name="Evolver", type="AGENT")
    db.add(c)
    db.commit()

    recipe_svc = RecipeService(db)
    parent = recipe_svc.create_recipe("Base Recipe", c.id, ["A"], "Test")

    evo_svc = EvolutionService(db)
    descendant = evo_svc.evolve_recipe(parent.id, [{"type": "add_step", "step": "B"}])

    assert descendant.parent_recipe_id == parent.id
    assert "Evolved" in descendant.title

    db.close()

if __name__ == "__main__":
    test_evolution_service()
