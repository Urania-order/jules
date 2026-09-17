from smos.core.database import SessionLocal
from smos.services.ecology_engine import EcologyEngine

def test_ecology_service():
    db = SessionLocal()
    from smos.models.epistemic import IntellectualCluster, ClusterRelation

    c1 = IntellectualCluster(name="Source", dormant_topics=["A"])
    c2 = IntellectualCluster(name="Target")
    db.add_all([c1, c2])
    db.commit()

    rel = ClusterRelation(source_cluster_id=c1.id, target_cluster_id=c2.id, interaction_type="INSPIRES")
    db.add(rel)
    db.commit()

    svc = EcologyEngine(db)
    suggestions = svc.pollinate(c1.id)
    assert len(suggestions) > 0
    assert suggestions[0]["target_cluster_id"] == c2.id

    db.close()

if __name__ == "__main__":
    test_ecology_service()
