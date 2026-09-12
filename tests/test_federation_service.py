import pytest
from smos.core.database import SessionLocal
from smos.models.models import User, Timeline, TimelineType, MemoryNode, EpistemicStatus
from smos.models.entities import Cosmonaut
from smos.models.epistemic import IntellectualCluster
from smos.models.ecology import FederatedNode, FederatedSubscription, ProvenanceRecord
from smos.services.federation_service import FederationService
from smos.services.sovereignty_service import SovereigntyService

def test_federation_node_registration_and_listing(db):
    fed_svc = FederationService(db)

    # Register node
    node1 = fed_svc.register_node(
        name="Alpha Node",
        endpoint_url="https://alpha.cosmos.org",
        trust_score=0.9,
        sovereignty_level="HIGH"
    )
    assert node1.id is not None
    assert node1.name == "Alpha Node"
    assert node1.status == "ACTIVE"

    # Re-registering existing endpoint updates node
    node1_updated = fed_svc.register_node(
        name="Alpha Node Updated",
        endpoint_url="https://alpha.cosmos.org",
        trust_score=0.95,
        sovereignty_level="HIGH"
    )
    assert node1_updated.id == node1.id
    assert node1_updated.trust_score == 0.95

    # Register second node
    node2 = fed_svc.register_node(
        name="Beta Node",
        endpoint_url="https://beta.cosmos.org",
        trust_score=0.8
    )

    nodes = fed_svc.list_nodes(active_only=True)
    assert len(nodes) == 2

    status = fed_svc.get_node_status(node1.id)
    assert status["id"] == node1.id
    assert status["name"] == "Alpha Node Updated"
    assert status["active_subscriptions_count"] == 0

def test_federation_subscriptions(db):
    fed_svc = FederationService(db)

    node = fed_svc.register_node("Cluster Node", "https://cluster.node")
    cluster = IntellectualCluster(name="Quantum Physics")
    db.add(cluster)
    db.commit()

    sub = fed_svc.subscribe_cluster(
        node_id=node.id,
        cluster_id=cluster.id,
        consensus_filter="Verified"
    )
    assert sub.id is not None
    assert sub.is_active is True

    status = fed_svc.get_node_status(node.id)
    assert status["active_subscriptions_count"] == 1

    unsub_result = fed_svc.unsubscribe_cluster(sub.id)
    assert unsub_result is True

    status_after = fed_svc.get_node_status(node.id)
    assert status_after["active_subscriptions_count"] == 0

def test_export_and_sync_knowledge_with_provenance_and_sovereignty(db):
    user = User(display_name="Local Scientist")
    cosmo = Cosmonaut(name="AI Observer", type="AGENT")
    tl = Timeline(type=TimelineType.REAL)
    db.add_all([user, cosmo, tl])
    db.commit()

    cluster = IntellectualCluster(name="Ecology Dynamics")
    db.add(cluster)
    db.commit()

    # Create memory node locally
    mnode = MemoryNode(
        content="Resonance principles drive ecosystem stability",
        owner_id=user.id,
        timeline_id=tl.id,
        epistemic_status=EpistemicStatus.VERIFIED,
        cluster_ids=[cluster.id],
        tags=["ecology", "resonance"]
    )
    db.add(mnode)
    db.commit()

    # Create provenance record
    prov = ProvenanceRecord(
        node_id=mnode.id,
        created_by_id=cosmo.id,
        contributors=[cosmo.id],
        evidence_links=["http://evidence.org/doc1"]
    )
    db.add(prov)
    db.commit()

    fed_svc = FederationService(db)

    # Export knowledge
    payload = fed_svc.export_knowledge_payload(
        cluster_id=cluster.id,
        min_epistemic_status="Verified"
    )
    assert payload["count"] == 1
    assert payload["items"][0]["content"] == "Resonance principles drive ecosystem stability"
    assert payload["items"][0]["provenance"]["evidence_links"] == ["http://evidence.org/doc1"]

    # Register foreign remote node and sync knowledge into a target timeline
    remote_node = fed_svc.register_node("Gamma Institute", "https://gamma.inst")
    
    user2 = User(display_name="Remote Recipient")
    tl2 = Timeline(type=TimelineType.REAL)
    db.add_all([user2, tl2])
    db.commit()

    sync_result = fed_svc.sync_knowledge_from_node(
        source_node_id=remote_node.id,
        knowledge_payload=payload,
        target_timeline_id=tl2.id,
        target_owner_id=user2.id
    )

    assert sync_result["status"] == "COMPLETED"
    assert sync_result["synced_items"] == 1

    # Check that synced memory node exists with provenance preserved
    synced_node = db.query(MemoryNode).filter(MemoryNode.owner_id == user2.id).first()
    assert synced_node is not None
    assert "[Federated: Gamma Institute]" in synced_node.content
    assert synced_node.epistemic_status == EpistemicStatus.VERIFIED

    synced_prov = db.query(ProvenanceRecord).filter(ProvenanceRecord.node_id == synced_node.id).first()
    assert synced_prov is not None
    assert "http://evidence.org/doc1" in synced_prov.evidence_links

def test_sovereignty_evaluation_and_principles(db):
    fed_svc = FederationService(db)
    sovereignty_svc = SovereigntyService(db)

    node = fed_svc.register_node("Untrusted Node", "https://untrusted.org", trust_score=0.1)

    eval_result = fed_svc.evaluate_sovereignty_policy(node.id)
    assert eval_result["sovereignty_compliant"] is False

    eval_via_sov = sovereignty_svc.evaluate_sovereignty_policy(node.id)
    assert eval_via_sov["sovereignty_compliant"] is False

    principles = sovereignty_svc.check_sovereignty_principles()
    assert principles["avoid_single_point_of_control"] is True
    assert principles["epistemic_autonomy"] is True
    assert principles["provenance_transparency"] is True

def test_federation_observable_interface(db):
    fed_svc = FederationService(db)
    initial_nodes_count = db.query(FederatedNode).count()

    metrics = fed_svc.get_health_metrics()
    assert "health" in metrics
    assert metrics["total_nodes"] == initial_nodes_count

    fed_svc.register_node("Node A Unique", "https://a-unique-node.com")
    metrics_after = fed_svc.get_health_metrics()
    assert metrics_after["total_nodes"] == initial_nodes_count + 1
    assert metrics_after["health"] == 1.0

    summary = fed_svc.get_evolution_summary()
    assert len(summary) > 0
    assert summary[0]["subsystem"] == "FederationService"
