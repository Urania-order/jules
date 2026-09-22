import pytest
from smos.models.models import EpistemicStatus, RelationType
from smos.models.context import Context, ContextRelation
from smos.services.context_service import ContextService


def test_create_context(db):
    service = ContextService(db)
    context = service.create(
        name="Mars Colony Habitat",
        description="Environmental context for Sector 4 habitat",
        components=["life_support", "radiation_shield", "thermal_control"],
        source="Mission Spec v2.1",
        epistemic_status=EpistemicStatus.OBSERVED,
        temporal_scope="2046-2050",
        spatial_scope="Mars Sector 4",
        provenance={"designed_by": "Architect Unit Alpha"},
    )
    assert context.id is not None
    assert context.name == "Mars Colony Habitat"
    assert context.description == "Environmental context for Sector 4 habitat"
    assert context.components == ["life_support", "radiation_shield", "thermal_control"]
    assert context.source == "Mission Spec v2.1"
    assert context.epistemic_status == EpistemicStatus.OBSERVED
    assert context.temporal_scope == "2046-2050"
    assert context.spatial_scope == "Mars Sector 4"
    assert context.provenance == {"designed_by": "Architect Unit Alpha"}


def test_serialize_context(db):
    service = ContextService(db)
    context = service.create(
        name="Orbital Station",
        description="Low Earth Orbit habitat context",
        components=["solar_array", "comm_dish"],
        source="Telemetry",
        epistemic_status=EpistemicStatus.INFERRED,
        temporal_scope="2026+",
        spatial_scope="LEO",
        provenance={"sim_run": 42},
    )
    serialized = context.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["id"] == context.id
    assert serialized["name"] == "Orbital Station"
    assert serialized["description"] == "Low Earth Orbit habitat context"
    assert serialized["components"] == ["solar_array", "comm_dish"]
    assert serialized["source"] == "Telemetry"
    assert serialized["epistemic_status"] == "INFERRED"
    assert serialized["temporal_scope"] == "2026+"
    assert serialized["spatial_scope"] == "LEO"
    assert serialized["provenance"] == {"sim_run": 42}
    assert "created_at" in serialized
    assert "updated_at" in serialized


def test_persist_context(db):
    context = Context(
        name="Direct Persistence Context",
        components=["module_a", "module_b"],
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
        temporal_scope="2030",
        spatial_scope="Moon South Pole",
        provenance={"direct_insert": True},
    )
    db.add(context)
    db.commit()
    db.refresh(context)

    persisted = db.get(Context, context.id)
    assert persisted is not None
    assert persisted.name == "Direct Persistence Context"
    assert persisted.components == ["module_a", "module_b"]
    assert persisted.epistemic_status == EpistemicStatus.HYPOTHESIZED
    assert persisted.provenance == {"direct_insert": True}


def test_retrieve_context(db):
    service = ContextService(db)
    created = service.create(name="Retrieval Context Target")
    retrieved = service.get(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "Retrieval Context Target"

    non_existent = service.get(99999)
    assert non_existent is None


def test_list_contexts(db):
    service = ContextService(db)
    c1 = service.create(name="Context Alpha")
    c2 = service.create(name="Context Beta")
    c3 = service.create(name="Context Gamma")

    items = service.list(limit=10, offset=0)
    assert len(items) >= 3
    names = [c.name for c in items]
    assert "Context Alpha" in names
    assert "Context Beta" in names
    assert "Context Gamma" in names


def test_update_context(db):
    service = ContextService(db)
    created = service.create(name="Original Context Name", epistemic_status=EpistemicStatus.OBSERVED)

    updated = service.update(
        created.id,
        name="Updated Context Name",
        epistemic_status="hypothesized",
        description="Updated description",
        temporal_scope="2050+",
    )
    assert updated is not None
    assert updated.name == "Updated Context Name"
    assert updated.epistemic_status == EpistemicStatus.HYPOTHESIZED
    assert updated.description == "Updated description"
    assert updated.temporal_scope == "2050+"


def test_delete_context(db):
    service = ContextService(db)
    created = service.create(name="Context To Delete")
    deleted_ok = service.delete(created.id)
    assert deleted_ok is True

    assert service.get(created.id) is None
    assert service.delete(created.id) is False


def test_context_components_json(db):
    service = ContextService(db)
    ctx = service.create(
        name="Complex Components Context",
        components=[
            {"id": "c1", "type": "sensor", "active": True},
            {"id": "c2", "type": "actuator", "active": False},
        ],
    )
    assert len(ctx.components) == 2
    assert ctx.components[0]["id"] == "c1"
    assert ctx.components[1]["type"] == "actuator"


def test_context_temporal_scope(db):
    service = ContextService(db)
    ctx = service.create(
        name="Temporal Scope Test Context",
        temporal_scope="2020-01-01 to 2030-12-31 UTC",
    )
    assert ctx.temporal_scope == "2020-01-01 to 2030-12-31 UTC"


def test_context_spatial_scope(db):
    service = ContextService(db)
    ctx = service.create(
        name="Spatial Scope Test Context",
        spatial_scope="Grid Sector 7G (Lat: 45.0, Lon: -90.0)",
    )
    assert ctx.spatial_scope == "Grid Sector 7G (Lat: 45.0, Lon: -90.0)"


def test_context_provenance_preserved(db):
    service = ContextService(db)
    provenance_data = {
        "author": "analyst_1",
        "sources": ["doc_123", "sensor_456"],
        "metadata": {"version": 3, "verified": False},
    }
    ctx = service.create(name="Provenance Context", provenance=provenance_data)
    assert ctx.provenance == provenance_data

    retrieved = service.get(ctx.id)
    assert retrieved.provenance["author"] == "analyst_1"
    assert retrieved.provenance["metadata"]["version"] == 3


def test_invalid_epistemic_state_rejected(db):
    service = ContextService(db)
    with pytest.raises(ValueError):
        service.create(name="Invalid Epistemic Context", epistemic_status="INVALID_STATUS")

    created = service.create(name="Valid Epistemic Context", epistemic_status=EpistemicStatus.OBSERVED)
    with pytest.raises(ValueError):
        service.update(created.id, epistemic_status="NON_EXISTENT_STATUS")


def test_context_default_not_fact(db):
    """Ensure default epistemic status is OBSERVED and not auto-promoted to VERIFIED."""
    service = ContextService(db)
    ctx = service.create(name="Default Context")
    assert ctx.epistemic_status == EpistemicStatus.OBSERVED
    assert ctx.epistemic_status != EpistemicStatus.VERIFIED

    direct_ctx = Context(name="Model Default Context")
    db.add(direct_ctx)
    db.commit()
    db.refresh(direct_ctx)
    assert direct_ctx.epistemic_status == EpistemicStatus.OBSERVED
    assert direct_ctx.epistemic_status != EpistemicStatus.VERIFIED


def test_context_relation_create(db):
    service = ContextService(db)
    c1 = service.create(name="Base Context Environment")
    c2 = service.create(name="Sub Context Environment")

    rel = service.add_relation(
        source_id=c1.id,
        target_id=c2.id,
        relation_type=RelationType.PART_OF,
        provenance={"rule": "structural_hierarchy"},
    )
    assert rel.id is not None
    assert rel.source_context_id == c1.id
    assert rel.target_context_id == c2.id
    assert rel.relation_type == RelationType.PART_OF
    assert rel.provenance == {"rule": "structural_hierarchy"}

    rel_dict = rel.to_dict()
    assert rel_dict["source_context_id"] == c1.id
    assert rel_dict["target_context_id"] == c2.id
    assert rel_dict["relation_type"] == "PART_OF"


def test_context_relation_list(db):
    service = ContextService(db)
    c1 = service.create(name="Root Context")
    c2 = service.create(name="Child Context 1")
    c3 = service.create(name="Child Context 2")

    r1 = service.add_relation(c1.id, c2.id, RelationType.EXTENDS)
    r2 = service.add_relation(c3.id, c1.id, RelationType.DEPENDS_ON)

    rels_c1 = service.list_relations(c1.id)
    assert len(rels_c1) == 2
    rel_ids = [r.id for r in rels_c1]
    assert r1.id in rel_ids
    assert r2.id in rel_ids

    rels_c2 = service.list_relations(c2.id)
    assert len(rels_c2) == 1
    assert rels_c2[0].id == r1.id


def test_context_relation_reuses_relationtype(db):
    service = ContextService(db)
    c1 = service.create(name="Context A")
    c2 = service.create(name="Context B")

    rel_extends = service.add_relation(c1.id, c2.id, RelationType.EXTENDS)
    rel_part_of = service.add_relation(c2.id, c1.id, RelationType.PART_OF)

    assert rel_extends.relation_type == RelationType.EXTENDS
    assert rel_part_of.relation_type == RelationType.PART_OF

    # Pass string representation of RelationType enum
    rel_depends = service.add_relation(c1.id, c2.id, "DEPENDS_ON")
    assert rel_depends.relation_type == RelationType.DEPENDS_ON
