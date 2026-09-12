import pytest
from smos.services.ecology_engine import EcologyEngine
from smos.services.value_ecology_service import ValueEcologyService
from smos.services.commons_service import CommonsService
from smos.services.discovery_system import DiscoverySystem
from smos.services.observatory_service import ObservatoryService
from smos.models.epistemic import IntellectualCluster, ClusterRelation
from smos.models.ecology import ValueAssessment
from smos.models.entities import Cosmonaut, Collaboration
from smos.models.discovery import Hypothesis


def test_ecology_engine_health_metrics(db):
    engine = EcologyEngine(db)
    initial_metrics = engine.get_health_metrics()
    assert isinstance(initial_metrics, dict)
    assert "health" in initial_metrics
    assert "active_clusters" in initial_metrics
    assert "total_resonance" in initial_metrics

    # Add a cluster and check real DB metrics
    cluster = IntellectualCluster(name="AI Safety Ecology Engine Test", health=0.9, resonance=0.5)
    db.add(cluster)
    db.commit()

    try:
        metrics = engine.get_health_metrics()
        assert metrics["active_clusters"] == initial_metrics["active_clusters"] + 1
        assert "total_resonance" in metrics
    finally:
        db.delete(cluster)
        db.commit()


def test_value_ecology_service_health_metrics(db):
    service = ValueEcologyService(db)
    initial_metrics = service.get_health_metrics()
    assert isinstance(initial_metrics, dict)
    assert "avg_value" in initial_metrics
    assert "total_social_impact" in initial_metrics

    # Add ValueAssessment and verify real DB metrics
    va = ValueAssessment(node_id=9999, knowledge_value=0.8, social_impact=0.6)
    db.add(va)
    db.commit()

    try:
        metrics = service.get_health_metrics()
        assert "avg_value" in metrics
        assert "total_social_impact" in metrics
    finally:
        db.delete(va)
        db.commit()


def test_commons_service_health_metrics(db):
    service = CommonsService(db)
    initial_metrics = service.get_health_metrics()
    assert isinstance(initial_metrics, dict)
    assert "active_collaborations" in initial_metrics
    assert "cosmonaut_population" in initial_metrics
    assert "interaction_density" in initial_metrics

    c1 = Cosmonaut(name="Cosmo1 Metrics Test", type="HUMAN")
    c2 = Cosmonaut(name="Cosmo2 Metrics Test", type="AGENT")
    db.add_all([c1, c2])
    db.commit()

    try:
        res = service.facilitate_collaboration(c1.id, c2.id, "Research AI Ecology")
        collab_id = res["id"]

        metrics = service.get_health_metrics()
        assert metrics["cosmonaut_population"] == initial_metrics["cosmonaut_population"] + 2
        assert metrics["active_collaborations"] == initial_metrics["active_collaborations"] + 1
        assert "interaction_density" in metrics
    finally:
        collab = db.get(Collaboration, collab_id)
        if collab:
            db.delete(collab)
        db.delete(c1)
        db.delete(c2)
        db.commit()


def test_discovery_system_health_metrics(db):
    system = DiscoverySystem(db)
    initial_metrics = system.get_health_metrics()
    assert isinstance(initial_metrics, dict)
    assert "active_hypotheses" in initial_metrics
    assert "analogies_found" in initial_metrics

    hypo = Hypothesis(claim="Ecosystems exhibit self-repair Health Test", confidence=0.85)
    c1 = IntellectualCluster(name="Cluster A Discovery Health Test")
    c2 = IntellectualCluster(name="Cluster B Discovery Health Test")
    db.add_all([hypo, c1, c2])
    db.commit()

    rel = ClusterRelation(source_cluster_id=c1.id, target_cluster_id=c2.id, interaction_type="INSPIRES")
    db.add(rel)
    db.commit()

    try:
        metrics = system.get_health_metrics()
        assert metrics["active_hypotheses"] == initial_metrics["active_hypotheses"] + 1
        assert metrics["analogies_found"] == initial_metrics["analogies_found"] + 1
    finally:
        db.delete(rel)
        db.delete(hypo)
        db.delete(c1)
        db.delete(c2)
        db.commit()


def test_observatory_service_health_report(db):
    eco = EcologyEngine(db)
    val = ValueEcologyService(db)
    com = CommonsService(db)
    disc = DiscoverySystem(db)

    observatory = ObservatoryService(db, subsystems=[eco, val, com, disc])
    report = observatory.get_health_report()

    assert "health_score" in report
    assert "subsystems" in report
    assert "EcologyEngine" in report["subsystems"]
    assert "ValueEcologyService" in report["subsystems"]
    assert "CommonsService" in report["subsystems"]
    assert "DiscoverySystem" in report["subsystems"]
