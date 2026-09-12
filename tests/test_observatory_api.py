from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)

def test_get_observatory_health():
    response = client.get("/observatory/health")
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert "timestamp" in data
    assert "subsystems" in data
    assert "EcologyEngine" in data["subsystems"]
    assert "ValueEcologyService" in data["subsystems"]
    assert "CommonsService" in data["subsystems"]
    assert "DiscoverySystem" in data["subsystems"]

def test_get_observatory_report():
    response = client.get("/observatory/report")
    assert response.status_code == 200
    data = response.json()
    assert "health_report" in data
    assert "evolution_summary" in data
    assert "knowledge_impact_ranking" in data
    assert "forecasts" in data
    assert "recommendations" in data

def test_get_observatory_ranking():
    response = client.get("/observatory/ranking?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

def test_get_observatory_recommendations():
    response = client.get("/observatory/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
