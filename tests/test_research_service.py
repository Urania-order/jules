from smos.core.database import SessionLocal
from smos.models.discovery import Hypothesis
from smos.models.models import User
from smos.services.research_service import ResearchService

def test_research_service_basic():
    db = SessionLocal()
    h = Hypothesis(claim="GPU demand increases cooling needs")
    u = User(display_name="Sponsor Corp")
    db.add_all([h, u])
    db.commit()

    svc = ResearchService(db)
    portal = svc.open_portal(h.id)
    assert portal.status == "OPEN"

    svc.sponsor_research(portal.id, u.id, 5000.0)
    assert portal.budget == 5000.0
    assert portal.status == "FUNDED"

    db.close()

def test_research_service_full_portal_management():
    db = SessionLocal()
    h1 = Hypothesis(claim="Quantum computing speeds up optimization")
    h2 = Hypothesis(claim="Neural networks compress data")
    u1 = User(display_name="Research Lab A")
    u2 = User(display_name="Research Lab B")
    db.add_all([h1, h2, u1, u2])
    db.commit()

    svc = ResearchService(db)

    # 1. Open portals
    p1 = svc.open_portal(h1.id, initial_budget=100.0)
    p2 = svc.open_portal(h2.id, initial_budget=0.0)

    # Idempotent check
    p1_again = svc.open_portal(h1.id)
    assert p1_again.id == p1.id

    # 2. Get portal & list portals
    fetched = svc.get_portal(p1.id)
    assert fetched is not None
    assert fetched.hypothesis_id == h1.id

    all_portals = svc.list_portals()
    assert len(all_portals) >= 2

    open_portals = svc.list_portals(status="OPEN")
    assert len(open_portals) >= 2

    # 3. Sponsorship and threshold transition
    sponsorship = svc.sponsor_research(p1.id, u1.id, 950.0, is_transparent=True)
    assert sponsorship is not None
    assert sponsorship.amount == 950.0
    assert p1.budget == 1050.0
    assert p1.status == "FUNDED"

    # 4. Outcomes and closing
    svc.record_outcome(p1.id, "Phase 1 experiment successful")
    assert "Phase 1 experiment successful" in p1.outcomes

    svc.close_portal(p1.id, reason="Research concluded")
    assert p1.status == "COMPLETED"
    assert any("Research concluded" in o for o in p1.outcomes)

    # 5. Lifecycle interface
    state = svc.get_lifecycle_state(p2.id)
    assert state == "OPEN"
    svc.advance_lifecycle(p2.id)
    assert p2.status == "FUNDED"

    # 6. Observable interface
    metrics = svc.get_health_metrics()
    assert "total_portals" in metrics
    assert "open_portals" in metrics
    assert "funded_portals" in metrics
    assert "completed_portals" in metrics
    assert "total_sponsorship_funds" in metrics
    assert metrics["total_sponsorship_funds"] >= 950.0

    summary = svc.get_evolution_summary()
    assert isinstance(summary, list)
    assert len(summary) >= 2

    db.close()

def test_research_portal_api_endpoints():
    from fastapi.testclient import TestClient
    from smos.api.main import app

    client = TestClient(app)
    db = SessionLocal()

    h = Hypothesis(claim="Solar energy efficiency improvement")
    u = User(display_name="Green Energy Fund")
    db.add_all([h, u])
    db.commit()

    # Create portal via API
    resp = client.post(f"/research/portal?hypothesis_id={h.id}&initial_budget=50.0")
    assert resp.status_code == 200
    portal_data = resp.json()
    portal_id = portal_data["id"]

    # List portals
    resp = client.get("/research/portals")
    assert resp.status_code == 200
    assert len(resp.json()) > 0

    # Get portal
    resp = client.get(f"/research/portal/{portal_id}")
    assert resp.status_code == 200
    assert resp.json()["hypothesis_id"] == h.id

    # Sponsor
    resp = client.post(f"/research/sponsor?portal_id={portal_id}&sponsor_id={u.id}&amount=2000.0")
    assert resp.status_code == 200

    # Record outcome
    resp = client.post(f"/research/portal/{portal_id}/outcome?portal_id={portal_id}&outcome=Prototype%20built")
    assert resp.status_code == 200

    # Close portal
    resp = client.post(f"/research/portal/{portal_id}/close?portal_id={portal_id}&reason=Target%20achieved")
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"

    db.close()

if __name__ == "__main__":
    test_research_service_basic()
    test_research_service_full_portal_management()
    test_research_portal_api_endpoints()
