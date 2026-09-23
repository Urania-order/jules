import pytest
from smos.models.constraint import Constraint, ConstraintType, ConstraintStatus
from smos.services.constraint_service import ConstraintService


def test_create_constraint(db):
    service = ConstraintService(db)
    constraint = service.create(
        name="Max Thermal Limit",
        description="Maximum continuous operating temperature threshold",
        type=ConstraintType.PHYSICAL,
        strength=0.85,
        status=ConstraintStatus.ACTIVE,
        evidence=["sensor_reading_102", "telemetry_log_45"],
        context="context:habitat_module_1",
        confidence=0.9,
        provenance={"source": "engineering_spec_v3"},
    )
    assert constraint.id is not None
    assert constraint.name == "Max Thermal Limit"
    assert constraint.description == "Maximum continuous operating temperature threshold"
    assert constraint.type == ConstraintType.PHYSICAL
    assert constraint.strength == 0.85
    assert constraint.status == ConstraintStatus.ACTIVE
    assert constraint.evidence == ["sensor_reading_102", "telemetry_log_45"]
    assert constraint.context == "context:habitat_module_1"
    assert constraint.confidence == 0.9
    assert constraint.provenance == {"source": "engineering_spec_v3"}


def test_serialize_constraint(db):
    service = ConstraintService(db)
    constraint = service.create(
        name="Budget Cap",
        description="Quarterly expense limit",
        type=ConstraintType.ECONOMIC,
        strength=1.0,
        status=ConstraintStatus.ACTIVE,
        evidence=["q3_report.pdf"],
        context="finance_dept",
        confidence=0.95,
        provenance={"auditor": "corp_audit"},
    )
    serialized = constraint.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["id"] == constraint.id
    assert serialized["name"] == "Budget Cap"
    assert serialized["description"] == "Quarterly expense limit"
    assert serialized["type"] == "ECONOMIC"
    assert serialized["strength"] == 1.0
    assert serialized["status"] == "ACTIVE"
    assert serialized["evidence"] == ["q3_report.pdf"]
    assert serialized["context"] == "finance_dept"
    assert serialized["confidence"] == 0.95
    assert serialized["provenance"] == {"auditor": "corp_audit"}
    assert "created_at" in serialized
    assert "updated_at" in serialized


def test_persist_constraint(db):
    constraint = Constraint(
        name="Direct Persistence Constraint",
        type=ConstraintType.LEGAL,
        status=ConstraintStatus.ACTIVE,
        confidence=0.8,
        provenance={"direct_insert": True},
    )
    db.add(constraint)
    db.commit()
    db.refresh(constraint)

    persisted = db.get(Constraint, constraint.id)
    assert persisted is not None
    assert persisted.name == "Direct Persistence Constraint"
    assert persisted.type == ConstraintType.LEGAL
    assert persisted.status == ConstraintStatus.ACTIVE
    assert persisted.confidence == 0.8
    assert persisted.provenance == {"direct_insert": True}


def test_retrieve_constraint(db):
    service = ConstraintService(db)
    created = service.create(name="Retrieval Constraint Target")
    retrieved = service.get(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "Retrieval Constraint Target"

    non_existent = service.get(99999)
    assert non_existent is None


def test_list_constraints(db):
    service = ConstraintService(db)
    c1 = service.create(name="Constraint Alpha", type=ConstraintType.TECHNICAL, status=ConstraintStatus.ACTIVE)
    c2 = service.create(name="Constraint Beta", type=ConstraintType.SOCIAL, status=ConstraintStatus.RESOLVED)
    c3 = service.create(name="Constraint Gamma", type=ConstraintType.TECHNICAL, status=ConstraintStatus.VIOLATED)

    items = service.list(limit=10, offset=0)
    assert len(items) >= 3
    names = [c.name for c in items]
    assert "Constraint Alpha" in names
    assert "Constraint Beta" in names
    assert "Constraint Gamma" in names

    tech_items = service.list(type=ConstraintType.TECHNICAL)
    tech_names = [c.name for c in tech_items]
    assert "Constraint Alpha" in tech_names
    assert "Constraint Gamma" in tech_names
    assert "Constraint Beta" not in tech_names

    active_items = service.list(status="ACTIVE")
    active_names = [c.name for c in active_items]
    assert "Constraint Alpha" in active_names
    assert "Constraint Beta" not in active_names


def test_update_constraint(db):
    service = ConstraintService(db)
    created = service.create(name="Original Constraint Name", type=ConstraintType.UNKNOWN, status=ConstraintStatus.UNKNOWN)

    updated = service.update(
        created.id,
        name="Updated Constraint Name",
        type="security",
        status="active",
        strength=0.75,
        confidence=0.85,
    )
    assert updated is not None
    assert updated.name == "Updated Constraint Name"
    assert updated.type == ConstraintType.SECURITY
    assert updated.status == ConstraintStatus.ACTIVE
    assert updated.strength == 0.75
    assert updated.confidence == 0.85


def test_delete_constraint(db):
    service = ConstraintService(db)
    created = service.create(name="Constraint To Delete")
    deleted_ok = service.delete(created.id)
    assert deleted_ok is True

    assert service.get(created.id) is None
    assert service.delete(created.id) is False


def test_constraint_type_enum():
    expected_types = [
        "PHYSICAL",
        "ECONOMIC",
        "LEGAL",
        "SOCIAL",
        "TECHNICAL",
        "ECOLOGICAL",
        "INFORMATIONAL",
        "ORGANIZATIONAL",
        "SECURITY",
        "INFRASTRUCTURAL",
        "TEMPORAL",
        "UNKNOWN",
    ]
    for type_name in expected_types:
        enum_val = ConstraintType[type_name]
        assert enum_val.value == type_name
        assert ConstraintType.from_str(type_name.lower()) == enum_val


def test_constraint_status_enum():
    expected_statuses = ["ACTIVE", "RESOLVED", "VIOLATED", "UNKNOWN"]
    for status_name in expected_statuses:
        enum_val = ConstraintStatus[status_name]
        assert enum_val.value == status_name
        assert ConstraintStatus.from_str(status_name.lower()) == enum_val


def test_constraint_type_unknown_default(db):
    service = ConstraintService(db)
    c = service.create(name="Default Type Constraint")
    assert c.type == ConstraintType.UNKNOWN

    direct_c = Constraint(name="Direct Default Type Constraint")
    db.add(direct_c)
    db.commit()
    db.refresh(direct_c)
    assert direct_c.type == ConstraintType.UNKNOWN


def test_constraint_status_unknown_default(db):
    service = ConstraintService(db)
    c = service.create(name="Default Status Constraint")
    assert c.status == ConstraintStatus.UNKNOWN

    direct_c = Constraint(name="Direct Default Status Constraint")
    db.add(direct_c)
    db.commit()
    db.refresh(direct_c)
    assert direct_c.status == ConstraintStatus.UNKNOWN


def test_constraint_strength_optional(db):
    service = ConstraintService(db)
    c1 = service.create(name="No Strength Constraint")
    assert c1.strength is None

    c2 = service.create(name="With Strength Constraint", strength=0.42)
    assert c2.strength == 0.42


def test_constraint_confidence_range(db):
    service = ConstraintService(db)
    c_default = service.create(name="Default Confidence Constraint")
    assert c_default.confidence == 0.5

    c_custom = service.create(name="Custom Confidence Constraint", confidence=0.99)
    assert c_custom.confidence == 0.99


def test_constraint_evidence_json(db):
    service = ConstraintService(db)
    evidence_items = [
        {"type": "document", "uri": "doc://123"},
        {"type": "observation", "id": "obs_456"},
    ]
    c = service.create(name="Evidence Constraint", evidence=evidence_items)
    assert c.evidence == evidence_items

    retrieved = service.get(c.id)
    assert retrieved.evidence[0]["type"] == "document"
    assert retrieved.evidence[1]["id"] == "obs_456"


def test_constraint_provenance_preserved(db):
    service = ConstraintService(db)
    provenance_data = {
        "author": "system_admin",
        "rule_id": "rule_99",
        "meta": {"version": 1},
    }
    c = service.create(name="Provenance Constraint", provenance=provenance_data)
    assert c.provenance == provenance_data

    retrieved = service.get(c.id)
    assert retrieved.provenance["author"] == "system_admin"
    assert retrieved.provenance["meta"]["version"] == 1


def test_constraint_invalid_type_rejected(db):
    service = ConstraintService(db)
    with pytest.raises(ValueError):
        service.create(name="Invalid Type Constraint", type="INVALID_TYPE")

    created = service.create(name="Valid Type Constraint")
    with pytest.raises(ValueError):
        service.update(created.id, type="NON_EXISTENT_TYPE")


def test_constraint_invalid_status_rejected(db):
    service = ConstraintService(db)
    with pytest.raises(ValueError):
        service.create(name="Invalid Status Constraint", status="INVALID_STATUS")

    created = service.create(name="Valid Status Constraint")
    with pytest.raises(ValueError):
        service.update(created.id, status="NON_EXISTENT_STATUS")


def test_constraint_not_causality():
    """Assertion test verifying documentation explicitly states Constraint ≠ Cause.

    A constraint is a limiting condition or bounding envelope, NOT a causal agent.
    Constraint entities restrict state spaces rather than asserting or driving causal links.
    """
    assert "Constraint ≠ Cause" in (Constraint.__doc__ or "")
    assert "limiting condition" in (Constraint.__doc__ or "").lower()
    assert "not a causal agent" in (Constraint.__doc__ or "").lower()

    assert "Constraint ≠ Cause" in (ConstraintService.__doc__ or "")
