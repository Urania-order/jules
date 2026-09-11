from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut
from smos.services.recipe_service import RecipeService

def test_recipe_service():
    db = SessionLocal()

    # Create Cosmonaut
    c = Cosmonaut(name="Expert Bot", type="AGENT")
    db.add(c)
    db.commit()

    svc = RecipeService(db)

    # Recipe
    recipe = svc.create_recipe("How to Deploy", c.id, ["Build", "Push", "Run"], "Deployment")
    assert recipe.author_id == c.id

    # Reputation
    updated = svc.update_reputation(c.id, True)
    assert updated.reputation_score == 10.0
    assert updated.successful_recipes_count == 1

    db.close()

if __name__ == "__main__":
    test_recipe_service()
