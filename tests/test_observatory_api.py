from fastapi.testclient import TestClient
from smos.api.main import app

client = TestClient(app)

def test_get_observatory_health():
    response = client.get("/observatory/health")
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert "timestamp" in data
    assert "proposal_metrics" in data
    assert "subsystems" in data
    assert "EcologyEngine" in data["subsystems"]
    assert "ValueEcologyService" in data["subsystems"]
    assert "CommonsService" in data["subsystems"]
    assert "DiscoverySystem" in data["subsystems"]

def test_get_observatory_proposals():
    response = client.get("/observatory/proposals")
    assert response.status_code == 200
    data = response.json()
    assert "total_proposals" in data
    assert "status_counts" in data
    assert "approval_rate" in data

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

def test_export_observatory_json():
    response = client.get("/observatory/export/json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "health_report" in data
    assert "knowledge_impact_ranking" in data

def test_export_observatory_markdown():
    response = client.get("/observatory/export/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    text = response.text
    assert "# Co-SMOS Observatory Quarterly Report" in text
    assert "## 1. Ecosystem Health Report" in text

def test_get_observatory_recommendations():
    response = client.get("/observatory/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
