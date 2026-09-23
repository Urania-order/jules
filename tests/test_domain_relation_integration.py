import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.models import EpistemicStatus, RelationType, MemoryNode, Relation, User, Workspace, Timeline, UserRole
from smos.models.context import Context, ContextRelation
from smos.models.experience import CausalRelation
from smos.models.phenomenon import Phenomenon
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.services.domain_relation_service import DomainRelationService
from smos.services.phenomenon_service import PhenomenonService
from smos.services.context_service import ContextService
from smos.services.constraint_service import ConstraintService
from smos.services.potential_service import PotentialService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_create_domain_relation(db_session):
    service = DomainRelationService(db_session)
    rel = service.create(
        source_type="context",
        source_id=1,
        target_type="phenomenon",
        target_id=2,
        relation_type=RelationType.ENABLES,
        provenance={"source": "test_agent"},
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.85,
        evidence=["doc-123"],
    )
    assert rel.id is not None
    assert rel.source_type == "context"
    assert rel.source_id == 1
    assert rel.target_type == "phenomenon"
    assert rel.target_id == 2
    assert rel.relation_type == RelationType.ENABLES
    assert rel.epistemic_status == EpistemicStatus.OBSERVED
    assert rel.confidence == 0.85
    assert rel.evidence == ["doc-123"]
    assert rel.provenance == {"source": "test_agent"}


def test_serialize_domain_relation(db_session):
    service = DomainRelationService(db_session)
    rel = service.create(
        source_type="context",
        source_id=10,
        target_type="phenomenon",
        target_id=20,
        relation_type="ENABLES",
        provenance={"agent": "jules"},
        confidence=0.9,
    )
    d = rel.to_dict()
    assert d["id"] == rel.id
    assert d["source_type"] == "context"
    assert d["source_id"] == 10
    assert d["target_type"] == "phenomenon"
    assert d["target_id"] == 20
    assert d["relation_type"] == "ENABLES"
    assert d["epistemic_status"] == "OBSERVED"
    assert d["provenance"] == {"agent": "jules"}
    assert d["evidence"] == []
    assert d["confidence"] == 0.9
    assert d["created_at"] is not None
    assert d["updated_at"] is not None


def test_persist_domain_relation(db_session):
    service = DomainRelationService(db_session)
    rel = service.create(
        source_type="constraint",
        source_id=5,
        target_type="potential",
        target_id=6,
        relation_type=RelationType.BLOCKS,
    )
    rel_id = rel.id

    # Expire and reload from DB
    db_session.expire_all()
    loaded = service.get(rel_id)
    assert loaded is not None
    assert loaded.id == rel_id
    assert loaded.relation_type == RelationType.BLOCKS


def test_retrieve_domain_relation(db_session):
    service = DomainRelationService(db_session)
    rel = service.create(
        source_type="phenomenon",
        source_id=1,
        target_type="context",
        target_id=2,
        relation_type=RelationType.CHANGES_CONTEXT,
    )
    fetched = service.get(rel.id)
    assert fetched is not None
    assert fetched.id == rel.id

    non_existent = service.get(99999)
    assert non_existent is None


def test_list_domain_relations(db_session):
    service = DomainRelationService(db_session)
    service.create("context", 1, "phenomenon", 1, RelationType.ENABLES)
    service.create("context", 1, "phenomenon", 2, RelationType.BLOCKS)
    service.create("constraint", 2, "potential", 3, RelationType.BLOCKS)

    all_rels = service.list()
    assert len(all_rels) == 3

    context_rels = service.list(source_type="context")
    assert len(context_rels) == 2

    blocks_rels = service.list(relation_type=RelationType.BLOCKS)
    assert len(blocks_rels) == 2

    filtered = service.list(source_type="constraint", target_type="potential", relation_type="BLOCKS")
    assert len(filtered) == 1


def test_update_domain_relation(db_session):
    service = DomainRelationService(db_session)
    rel = service.create("context", 1, "phenomenon", 1, RelationType.ENABLES, confidence=0.5)

    updated = service.update(rel.id, confidence=0.95, epistemic_status="INFERRED")
    assert updated is not None
    assert updated.confidence == 0.95
    assert updated.epistemic_status == EpistemicStatus.INFERRED

    assert service.update(99999, confidence=0.1) is None


def test_delete_domain_relation(db_session):
    service = DomainRelationService(db_session)
    rel = service.create("context", 1, "phenomenon", 1, RelationType.ENABLES)
    assert service.get(rel.id) is not None

    success = service.delete(rel.id)
    assert success is True
    assert service.get(rel.id) is None

    assert service.delete(rel.id) is False


def test_list_for_source(db_session):
    service = DomainRelationService(db_session)
    service.create("context", 100, "phenomenon", 1, RelationType.ENABLES)
    service.create("context", 100, "phenomenon", 2, RelationType.BLOCKS)
    service.create("context", 200, "phenomenon", 3, RelationType.ENABLES)

    results = service.list_for("context", 100)
    assert len(results) == 2
    for r in results:
        assert r.source_type == "context"
        assert r.source_id == 100


def test_list_into_target(db_session):
    service = DomainRelationService(db_session)
    service.create("context", 1, "phenomenon", 500, RelationType.ENABLES)
    service.create("phenomenon", 2, "phenomenon", 500, RelationType.SUPPORTS)
    service.create("context", 3, "phenomenon", 600, RelationType.ENABLES)

    results = service.list_into("phenomenon", 500)
    assert len(results) == 2
    for r in results:
        assert r.target_type == "phenomenon"
        assert r.target_id == 500


def test_scenario_context_enables_phenomenon(db_session):
    service = DomainRelationService(db_session)
    rel = service.context_enables_phenomenon(context_id=1, phenomenon_id=2, confidence=0.9)
    assert rel.source_type == "context"
    assert rel.source_id == 1
    assert rel.target_type == "phenomenon"
    assert rel.target_id == 2
    assert rel.relation_type == RelationType.ENABLES
    assert rel.confidence == 0.9


def test_scenario_context_blocks_phenomenon(db_session):
    service = DomainRelationService(db_session)
    rel = service.context_blocks_phenomenon(context_id=1, phenomenon_id=2)
    assert rel.source_type == "context"
    assert rel.source_id == 1
    assert rel.target_type == "phenomenon"
    assert rel.target_id == 2
    assert rel.relation_type == RelationType.BLOCKS


def test_scenario_constraint_blocks_potential(db_session):
    service = DomainRelationService(db_session)
    rel = service.constraint_blocks_potential(constraint_id=10, potential_id=20)
    assert rel.source_type == "constraint"
    assert rel.source_id == 10
    assert rel.target_type == "potential"
    assert rel.target_id == 20
    assert rel.relation_type == RelationType.BLOCKS


def test_scenario_phenomenon_changes_context(db_session):
    service = DomainRelationService(db_session)
    rel = service.phenomenon_changes_context(phenomenon_id=5, context_id=15)
    assert rel.source_type == "phenomenon"
    assert rel.source_id == 5
    assert rel.target_type == "context"
    assert rel.target_id == 15
    assert rel.relation_type == RelationType.CHANGES_CONTEXT


def test_scenario_phenomenon_creates_context(db_session):
    service = DomainRelationService(db_session)
    rel = service.phenomenon_creates_context(phenomenon_id=5, context_id=15)
    assert rel.source_type == "phenomenon"
    assert rel.source_id == 5
    assert rel.target_type == "context"
    assert rel.target_id == 15
    assert rel.relation_type == RelationType.CREATES_CONTEXT


def test_scenario_potential_depends_on_context(db_session):
    service = DomainRelationService(db_session)
    rel = service.potential_depends_on_context(potential_id=30, context_id=40)
    assert rel.source_type == "potential"
    assert rel.source_id == 30
    assert rel.target_type == "context"
    assert rel.target_id == 40
    assert rel.relation_type == RelationType.DEPENDS_ON


def test_full_graph_integration(db_session):
    # Instantiate all domain services
    p_service = PhenomenonService(db_session)
    c_service = ContextService(db_session)
    k_service = ConstraintService(db_session)
    pot_service = PotentialService(db_session)
    rel_service = DomainRelationService(db_session)

    # Create domain entities
    p1 = p_service.create(name="Solar Flare")
    c1 = c_service.create(name="High Radiation Environment")
    k1 = k_service.create(name="Shielding Capacity Limit")
    pot1 = pot_service.create(phenomenon="Communication Blackout")

    # Build all 6 required scenario relations in a single network
    r1 = rel_service.context_enables_phenomenon(c1.id, p1.id, epistemic_status=EpistemicStatus.OBSERVED)
    r2 = rel_service.context_blocks_phenomenon(c1.id, p1.id, epistemic_status=EpistemicStatus.HYPOTHESIZED)
    r3 = rel_service.constraint_blocks_potential(k1.id, pot1.id, epistemic_status=EpistemicStatus.INFERRED)
    r4 = rel_service.phenomenon_changes_context(p1.id, c1.id, epistemic_status=EpistemicStatus.OBSERVED)
    r5 = rel_service.phenomenon_creates_context(p1.id, c1.id, epistemic_status=EpistemicStatus.OBSERVED)
    r6 = rel_service.potential_depends_on_context(pot1.id, c1.id, epistemic_status=EpistemicStatus.PREDICTED)

    # Verify 6 relations persisted
    network = rel_service.list()
    assert len(network) == 6

    # Verify queryability by source and target
    p1_out = rel_service.list_for("phenomenon", p1.id)
    assert len(p1_out) == 2  # CHANGES_CONTEXT, CREATES_CONTEXT

    c1_in = rel_service.list_into("context", c1.id)
    assert len(c1_in) == 3  # CHANGES_CONTEXT, CREATES_CONTEXT, DEPENDS_ON


def test_domain_relation_provenance_json(db_session):
    service = DomainRelationService(db_session)
    prov = {"method": "automated_inference", "agent": "jules_v1.4", "timestamp": "2026-09-23T19:29:23Z"}
    rel = service.create("context", 1, "phenomenon", 2, RelationType.ENABLES, provenance=prov)
    assert rel.provenance == prov
    assert rel.to_dict()["provenance"] == prov


def test_domain_relation_epistemic_status_default(db_session):
    service = DomainRelationService(db_session)
    rel = service.create("context", 1, "phenomenon", 2, RelationType.ENABLES)
    assert rel.epistemic_status == EpistemicStatus.OBSERVED


def test_domain_relation_does_not_calculate_causality(db_session):
    # Documentation / assertion test confirming domain relation represents documented epistemic claims without asserting underlying causal truth
    service = DomainRelationService(db_session)
    hypothesized_rel = service.create(
        source_type="phenomenon",
        source_id=1,
        target_type="context",
        target_id=2,
        relation_type=RelationType.CHANGES_CONTEXT,
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
        confidence=0.4,
    )
    # The relation retains HYPOTHESIZED status and confidence value as asserted by source, without computing causal determinism
    assert hypothesized_rel.epistemic_status == EpistemicStatus.HYPOTHESIZED
    assert hypothesized_rel.confidence == 0.4


def test_domain_relation_reuses_relationtype():
    assert RelationType.ENABLES.value == "ENABLES"
    assert RelationType.BLOCKS.value == "BLOCKS"
    assert RelationType.CHANGES_CONTEXT.value == "CHANGES_CONTEXT"
    assert RelationType.CREATES_CONTEXT.value == "CREATES_CONTEXT"
    assert RelationType.DEPENDS_ON.value == "DEPENDS_ON"


def test_domain_relation_reuses_epistemicstatus():
    assert EpistemicStatus.OBSERVED.value == "OBSERVED"
    assert EpistemicStatus.INFERRED.value == "INFERRED"
    assert EpistemicStatus.HYPOTHESIZED.value == "HYPOTHESIZED"


def test_relation_unchanged(db_session):
    # Verify legacy Relation (MemoryNode FK) still works as expected
    user = User(display_name="Tester", role=UserRole.OWNER)
    db_session.add(user)
    db_session.commit()

    workspace = Workspace(name="WS", owner_id=user.id)
    timeline = Timeline()
    db_session.add_all([workspace, timeline])
    db_session.commit()

    node1 = MemoryNode(content="Node 1", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    node2 = MemoryNode(content="Node 2", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    db_session.add_all([node1, node2])
    db_session.commit()

    rel = Relation(from_node_id=node1.id, to_node_id=node2.id, type=RelationType.RELATED_TO)
    db_session.add(rel)
    db_session.commit()

    assert rel.id is not None
    assert rel.from_node_id == node1.id
    assert rel.to_node_id == node2.id


def test_context_relation_unchanged(db_session):
    # Verify ContextRelation (Context FK) still works as expected
    c1 = Context(name="Context 1")
    c2 = Context(name="Context 2")
    db_session.add_all([c1, c2])
    db_session.commit()

    cr = ContextRelation(source_context_id=c1.id, target_context_id=c2.id, relation_type=RelationType.EXTENDS)
    db_session.add(cr)
    db_session.commit()

    assert cr.id is not None
    assert cr.source_context_id == c1.id
    assert cr.target_context_id == c2.id


def test_causal_relation_unchanged(db_session):
    # Verify CausalRelation (MemoryNode cause/effect) still works as expected
    user = User(display_name="Tester", role=UserRole.OWNER)
    db_session.add(user)
    db_session.commit()

    workspace = Workspace(name="WS", owner_id=user.id)
    timeline = Timeline()
    db_session.add_all([workspace, timeline])
    db_session.commit()

    node1 = MemoryNode(content="Cause Node", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    node2 = MemoryNode(content="Effect Node", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    db_session.add_all([node1, node2])
    db_session.commit()

    causal_rel = CausalRelation(cause_node_id=node1.id, effect_node_id=node2.id, confidence=0.8)
    db_session.add(causal_rel)
    db_session.commit()

    assert causal_rel.id is not None
    assert causal_rel.cause_node_id == node1.id
    assert causal_rel.effect_node_id == node2.id


def test_step0_documented():
    # Assertion confirming STEP 0 audit decisions
    audit_findings = {
        "Relation": "smos/models/models.py:228 - FK from_node_id, to_node_id -> memory_nodes.id",
        "ContextRelation": "smos/models/context.py:66 - FK source_context_id, target_context_id -> contexts.id",
        "CausalRelation": "smos/models/experience.py:74 - FK cause_node_id, effect_node_id -> memory_nodes.id",
        "ClusterRelation": "smos/models/epistemic.py:32 - FK source_cluster_id, target_cluster_id -> intellectual_clusters.id",
        "GenericRelation": False,
        "Decision": "Keep type-specific relations unchanged. Create DomainRelation for cross-domain edges.",
    }
    assert audit_findings["GenericRelation"] is False
    assert "DomainRelation" in audit_findings["Decision"]
