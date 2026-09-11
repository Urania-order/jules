from smos.core.database import SessionLocal
from smos.services.ecology_service import EcologyService

def test_ecology_service():
    db = SessionLocal()
    # Import
    from smos.models.models import User
    from smos.models.entities import Cosmonaut
    from smos.models.epistemic import IntellectualCluster, ClusterRelation

    c1 = IntellectualCluster(name="Source", dormant_topics=["A"])
    c2 = IntellectualCluster(name="Target")
    db.add_all([c1, c2])
    db.commit()

    rel = ClusterRelation(source_cluster_id=c1.id, target_cluster_id=c2.id, interaction_type="INSPIRES")
    db.add(rel)
    db.commit()

    svc = EcologyService(db)
    suggestions = svc.pollinate(c1.id)
    assert len(suggestions) > 0
    assert suggestions[0]["target_cluster_id"] == c2.id

    is_active = svc.check_activation(c1.id)
    assert is_active is True

    db.close()

if __name__ == "__main__":
    test_ecology_service()
