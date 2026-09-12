import pytest
from datetime import datetime
from smos.services.observatory_service import ObservatoryService
from smos.services.ecology_engine import EcologyEngine
from smos.services.value_ecology_service import ValueEcologyService
from smos.services.commons_service import CommonsService
from smos.services.discovery_system import DiscoverySystem
from smos.models.ecology import ValueAssessment
from smos.models.epistemic import IntellectualCluster
from smos.models.discovery import LostKnowledge

def test_get_health_report(db):
    eco = EcologyEngine(db)
    val = ValueEcologyService(db)
    com = CommonsService(db)
    disc = DiscoverySystem(db)

    obs = ObservatoryService(db, [eco, val, com, disc])
    health_report = obs.get_health_report()

    assert "health_score" in health_report
    assert 0.0 <= health_report["health_score"] <= 1.0
    assert "timestamp" in health_report
    datetime.fromisoformat(health_report["timestamp"])
    assert "subsystems" in health_report
    assert "EcologyEngine" in health_report["subsystems"]
    assert "ValueEcologyService" in health_report["subsystems"]
    assert "CommonsService" in health_report["subsystems"]
    assert "DiscoverySystem" in health_report["subsystems"]

def test_generate_quarterly_report(db):
    eco = EcologyEngine(db)
    val = ValueEcologyService(db)
    com = CommonsService(db)
    disc = DiscoverySystem(db)

    obs = ObservatoryService(db, [eco, val, com, disc])
    report = obs.generate_quarterly_report()

    # Must contain all 5 sections:
    # 1. health_report
    # 2. evolution_summary
    # 3. knowledge_impact_ranking
    # 4. forecasts
    # 5. recommendations
    assert "health_report" in report
    assert "evolution_summary" in report
    assert "knowledge_impact_ranking" in report
    assert "forecasts" in report
    assert "recommendations" in report

    assert isinstance(report["health_report"], dict)
    assert isinstance(report["evolution_summary"], list)
    assert isinstance(report["knowledge_impact_ranking"], list)
    assert isinstance(report["forecasts"], list)
    assert isinstance(report["recommendations"], list)
    assert len(report["forecasts"]) == 8

def test_get_impact_ranking(db):
    val_service = ValueEcologyService(db)
    obs = ObservatoryService(db, [val_service])

    # Test with empty database (fallback mechanism)
    ranking_fallback = obs.get_impact_ranking(limit=2)
    assert len(ranking_fallback) == 2
    for item in ranking_fallback:
        assert "rank" in item
        assert "node_id" in item
        assert "score" in item
        assert "reason" in item

    # Add ValueAssessment items to DB
    v1 = ValueAssessment(node_id=1, knowledge_value=0.9, social_impact=0.8) # score 0.72
    v2 = ValueAssessment(node_id=2, knowledge_value=0.5, social_impact=0.4) # score 0.20
    v3 = ValueAssessment(node_id=3, knowledge_value=1.0, social_impact=0.9) # score 0.90
    db.add_all([v1, v2, v3])
    db.commit()

    ranking = obs.get_impact_ranking(limit=2)
    assert len(ranking) == 2

    # Check order by score descending
    assert ranking[0]["node_id"] == 3
    assert ranking[0]["score"] == 0.90
    assert ranking[0]["rank"] == 1

    assert ranking[1]["node_id"] == 1
    assert ranking[1]["score"] == 0.72
    assert ranking[1]["rank"] == 2

def test_generate_recommendations(db):
    disc = DiscoverySystem(db)
    obs = ObservatoryService(db, [disc])

    recs = obs.generate_recommendations()
    assert isinstance(recs, list)
    assert len(recs) > 0

    # Add dormant topics to a cluster and a low confidence lost knowledge item
    cluster = IntellectualCluster(name="AI Ethics", dormant_topics=["Bias in LLMs", "Safety Guidelines"])
    lost = LostKnowledge(confidence=0.3)
    db.add_all([cluster, lost])
    db.commit()

    recs_updated = obs.generate_recommendations()
    assert isinstance(recs_updated, list)
    assert any("AI Ethics" in r for r in recs_updated)
    assert any("lost knowledge" in r.lower() for r in recs_updated)
