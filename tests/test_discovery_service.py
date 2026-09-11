from smos.core.database import SessionLocal
from smos.services.discovery_service import DiscoveryService

def test_discovery_service():
    db = SessionLocal()
    # Import model to ensure registration
    from smos.models.models import User
    from smos.models.epistemic import IntellectualCluster, ClusterRelation

    svc = DiscoveryService(db)

    c1 = svc.create_cluster("Archaeology", ["History", "Science"])
    c2 = svc.create_cluster("Mythology", ["Art", "Religion"])

    svc.link_clusters(c1.id, c2.id, "INSPIRES")
    analogies = svc.find_analogies(c1.id)
    assert "INSPIRES" in analogies

    db.close()

if __name__ == "__main__":
    test_discovery_service()
