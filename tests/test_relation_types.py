"""Tests for RelationType enum expansion, Relation provenance fields, and Provenance decision (TASK 06)."""

import pytest
from sqlalchemy.orm import Session
from smos.models.models import RelationType, Relation, EpistemicStatus, MemoryNode, User, Workspace, Timeline
from smos.models.context import ContextRelation
from smos.models.experience import CausalRelation
from smos.models.ecology import ProvenanceRecord


def test_relation_type_supports():
    assert RelationType.SUPPORTS.value == "SUPPORTS"


def test_relation_type_blocks():
    assert RelationType.BLOCKS.value == "BLOCKS"


def test_relation_type_enables():
    assert RelationType.ENABLES.value == "ENABLES"


def test_relation_type_correlates_with():
    assert RelationType.CORRELATES_WITH.value == "CORRELATES_WITH"


def test_relation_type_contradicts():
    assert RelationType.CONTRADICTS.value == "CONTRADICTS"


def test_relation_type_requires():
    assert RelationType.REQUIRES.value == "REQUIRES"


def test_relation_type_prevents():
    assert RelationType.PREVENTS.value == "PREVENTS"


def test_new_relations_count():
    assert len(RelationType) == 33


def test_no_duplicate_relations():
    values = [e.value for e in RelationType]
    names = [e.name for e in RelationType]
    assert len(values) == len(set(values))
    assert len(names) == len(set(names))


def test_relation_provenance_field_exists(db: Session):
    user = User(display_name="Test User")
    workspace = Workspace(name="Test Workspace")
    timeline = Timeline(description="Test Timeline")
    db.add_all([user, workspace, timeline])
    db.commit()

    n1 = MemoryNode(content="Node 1", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    n2 = MemoryNode(content="Node 2", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    db.add_all([n1, n2])
    db.commit()

    rel = Relation(
        from_node_id=n1.id,
        to_node_id=n2.id,
        type=RelationType.SUPPORTS,
        provenance={"source_case": "case_1", "observer": "agent_alpha"}
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)

    assert hasattr(rel, "provenance")
    assert rel.provenance == {"source_case": "case_1", "observer": "agent_alpha"}


def test_relation_provenance_default_empty_dict(db: Session):
    user = User(display_name="Test User 2")
    workspace = Workspace(name="Test Workspace 2")
    timeline = Timeline(description="Test Timeline 2")
    db.add_all([user, workspace, timeline])
    db.commit()

    n1 = MemoryNode(content="Node 1", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    n2 = MemoryNode(content="Node 2", owner_id=user.id, workspace_id=workspace.id, timeline_id=timeline.id)
    db.add_all([n1, n2])
    db.commit()

    rel = Relation(
        from_node_id=n1.id,
        to_node_id=n2.id,
        type=RelationType.BLOCKS
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)

    assert rel.provenance == {}


def test_relation_epistemic_status_nullable(db: Session):
    rel1 = Relation(type=RelationType.ENABLES, epistemic_status=None)
    rel2 = Relation(type=RelationType.AMPLIFIES, epistemic_status=EpistemicStatus.OBSERVED)
    db.add_all([rel1, rel2])
    db.commit()
    db.refresh(rel1)
    db.refresh(rel2)

    assert rel1.epistemic_status is None
    assert rel2.epistemic_status == EpistemicStatus.OBSERVED


def test_relation_evidence_field(db: Session):
    rel = Relation(type=RelationType.SUPPRESSES, evidence=["doc:123", "event:456"])
    db.add(rel)
    db.commit()
    db.refresh(rel)

    assert rel.evidence == ["doc:123", "event:456"]


def test_relation_confidence_field(db: Session):
    rel = Relation(type=RelationType.TRANSFORMS, confidence=0.85)
    db.add(rel)
    db.commit()
    db.refresh(rel)

    assert rel.confidence == 0.85


def test_context_relation_has_no_new_provenance_field():
    # ContextRelation already has provenance JSON column from prior implementation.
    # TASK 06 constraint: MUST NOT introduce separate / new provenance fields or mechanisms.
    cols = [c.name for c in ContextRelation.__table__.columns]
    assert "provenance" in cols
    assert "provenance_record_id" not in cols
    assert "subject_type" not in cols


def test_causal_relation_has_no_new_provenance_field():
    # CausalRelation has confidence and evidence, but no provenance field.
    cols = [c.name for c in CausalRelation.__table__.columns]
    assert "provenance" not in cols
    assert "provenance_record_id" not in cols


def test_existing_relation_usage_still_works(db: Session):
    # Verify backward compatibility for existing relations
    rel = Relation(from_node_id=1, to_node_id=2, type=RelationType.DEPENDS_ON)
    db.add(rel)
    db.commit()
    db.refresh(rel)

    assert rel.id is not None
    assert rel.type == RelationType.DEPENDS_ON
    assert rel.from_node_id == 1
    assert rel.to_node_id == 2


def test_provenance_record_unchanged():
    # Verify ProvenanceRecord in ecology.py remains unchanged (coupled to memory_nodes with node_id FK)
    cols = [c.name for c in ProvenanceRecord.__table__.columns]
    assert "node_id" in cols
    assert "created_by_id" in cols
    assert "contributors" in cols
    assert "evidence_links" in cols
    assert "revision_history" in cols
    assert "created_at" in cols
    # Confirm it was NOT modified to polymorphic
    assert "subject_id" not in cols
    assert "subject_type" not in cols


def test_step0_documented():
    # Verify Step 0 docstring decision in Relation model docstring
    assert "PROVENANCE DECISION (Option B)" in Relation.__doc__
