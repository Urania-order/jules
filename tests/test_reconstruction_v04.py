from smos.core.database import SessionLocal
from smos.services.reconstruction_service import ReconstructionService

def test_reconstruction_v04():
    db = SessionLocal()
    # Import models to ensure they are registered in the metadata for this session
    from smos.models.models import Event
    from smos.models.experience import Reconstruction, AntiRecipe

    svc = ReconstructionService(db)

    rec = svc.reconstruct_experience(
        observations=["Service down"],
        artifacts=["error_log.txt"],
        witnesses=["Admin Agent"],
        level="DEDUCED"
    )
    assert rec.evidence_level == "DEDUCED"

    anti = svc.create_anti_recipe(rec.id, "Pushing to main without tests", ["CI failure", "Manual override"])
    assert anti.reconstruction_id == rec.id
    assert "Avoid this" in anti.description

    db.close()

if __name__ == "__main__":
    test_reconstruction_v04()
