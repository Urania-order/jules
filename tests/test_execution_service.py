from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut
from smos.services.recipe_service import RecipeService
from smos.services.execution_service import ExecutionService

def test_execution_service():
    db = SessionLocal()

    # Create Cosmonaut
    c = Cosmonaut(name="Executor Bot", type="AGENT")
    db.add(c)
    db.commit()

    recipe_svc = RecipeService(db)
    recipe = recipe_svc.create_recipe("Build OS", c.id, ["Plan", "Code", "Test"], "Dev")

    exec_svc = ExecutionService(db)
    exe = exec_svc.record_execution(recipe.id, [c.id], "SUCCESS", duration=120.5, satisfaction=0.9)

    assert exe.result == "SUCCESS"
    assert recipe.success_rate > 0.0

    db.close()

if __name__ == "__main__":
    test_execution_service()
