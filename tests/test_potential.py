import pytest
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.services.potential_service import PotentialService


def test_create_potential_phenomenon(db):
    service = PotentialService(db)
    potential = service.create(
        phenomenon="Emergent Quantum Coherence in Room-Temp Superconductor",
        status=PotentialStatus.POSSIBLE,
        required_conditions=["High pressure environment", "Impurities under 1ppm"],
        supporting_contexts=[101, 102],
        blocking_constraints=[201],
        dependencies=["Synthetic Crystal Lattice"],
        expected_impacts=[{"target": "Power Grid", "impact_type": "Efficiency", "magnitude": "High"}],
        provenance={"source": "lab_experiment_42"},
    )
    assert potential.id is not None
    assert potential.phenomenon == "Emergent Quantum Coherence in Room-Temp Superconductor"
    assert potential.status == PotentialStatus.POSSIBLE
    assert potential.required_conditions == ["High pressure environment", "Impurities under 1ppm"]
    assert potential.supporting_contexts == [101, 102]
    assert potential.blocking_constraints == [201]
    assert potential.dependencies == ["Synthetic Crystal Lattice"]
    assert potential.expected_impacts == [{"target": "Power Grid", "impact_type": "Efficiency", "magnitude": "High"}]
    assert potential.provenance == {"source": "lab_experiment_42"}


def test_serialize_potential(db):
    service = PotentialService(db)
    potential = service.create(
        phenomenon="Autonomous Network Re-routing",
        status=PotentialStatus.POSSIBLE,
        required_conditions=["Mesh topology"],
        supporting_contexts=[1],
        blocking_constraints=[2],
        dependencies=["Node Discovery"],
        expected_impacts=[{"target": "Latency", "impact_type": "Reduction", "magnitude": "Medium"}],
        provenance={"analyst": "jules"},
    )
    serialized = potential.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["id"] == potential.id
    assert serialized["phenomenon"] == "Autonomous Network Re-routing"
    assert serialized["status"] == "POSSIBLE"
    assert serialized["required_conditions"] == ["Mesh topology"]
    assert serialized["supporting_contexts"] == [1]
    assert serialized["blocking_constraints"] == [2]
    assert serialized["dependencies"] == ["Node Discovery"]
    assert serialized["expected_impacts"] == [{"target": "Latency", "impact_type": "Reduction", "magnitude": "Medium"}]
    assert serialized["provenance"] == {"analyst": "jules"}
    assert "created_at" in serialized
    assert "updated_at" in serialized


def test_persist_potential(db):
    potential = PotentialPhenomenon(
        phenomenon="Direct Persistence Potential",
        status=PotentialStatus.UNLIKELY,
        provenance={"direct_insert": True},
    )
    db.add(potential)
    db.commit()
    db.refresh(potential)

    persisted = db.get(PotentialPhenomenon, potential.id)
    assert persisted is not None
    assert persisted.phenomenon == "Direct Persistence Potential"
    assert persisted.status == PotentialStatus.UNLIKELY
    assert persisted.provenance == {"direct_insert": True}


def test_retrieve_potential(db):
    service = PotentialService(db)
    created = service.create(phenomenon="Retrieval Target")
    retrieved = service.get(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.phenomenon == "Retrieval Target"

    non_existent = service.get(99999)
    assert non_existent is None


def test_list_potentials(db):
    service = PotentialService(db)
    p1 = service.create(phenomenon="Potential Alpha", status=PotentialStatus.POSSIBLE)
    p2 = service.create(phenomenon="Potential Beta", status=PotentialStatus.BLOCKED)
    p3 = service.create(phenomenon="Potential Gamma", status=PotentialStatus.POSSIBLE)

    items = service.list(limit=10, offset=0)
    assert len(items) >= 3
    names = [p.phenomenon for p in items]
    assert "Potential Alpha" in names
    assert "Potential Beta" in names
    assert "Potential Gamma" in names

    possible_items = service.list(status=PotentialStatus.POSSIBLE)
    possible_names = [p.phenomenon for p in possible_items]
    assert "Potential Alpha" in possible_names
    assert "Potential Gamma" in possible_names
    assert "Potential Beta" not in possible_names

    blocked_items = service.list(status="BLOCKED")
    blocked_names = [p.phenomenon for p in blocked_items]
    assert "Potential Beta" in blocked_names
    assert "Potential Alpha" not in blocked_names


def test_update_potential(db):
    service = PotentialService(db)
    created = service.create(phenomenon="Original Potential Name", status=PotentialStatus.UNKNOWN)

    updated = service.update(
        created.id,
        phenomenon="Updated Potential Name",
        status="temporarily_blocked",
        dependencies=["dep1"],
    )
    assert updated is not None
    assert updated.phenomenon == "Updated Potential Name"
    assert updated.status == PotentialStatus.TEMPORARILY_BLOCKED
    assert updated.dependencies == ["dep1"]


def test_delete_potential(db):
    service = PotentialService(db)
    created = service.create(phenomenon="Potential To Delete")
    deleted_ok = service.delete(created.id)
    assert deleted_ok is True

    assert service.get(created.id) is None
    assert service.delete(created.id) is False


def test_potential_status_enum():
    expected_statuses = [
        "POSSIBLE",
        "UNLIKELY",
        "BLOCKED",
        "TEMPORARILY_BLOCKED",
        "STRUCTURALLY_BLOCKED",
        "UNKNOWN",
    ]
    for status_name in expected_statuses:
        enum_val = PotentialStatus[status_name]
        assert enum_val.value == status_name
        assert PotentialStatus.from_str(status_name.lower()) == enum_val


def test_potential_status_unknown_default(db):
    service = PotentialService(db)
    p = service.create(phenomenon="Default Status Potential")
    assert p.status == PotentialStatus.UNKNOWN

    direct_p = PotentialPhenomenon(phenomenon="Direct Default Status Potential")
    db.add(direct_p)
    db.commit()
    db.refresh(direct_p)
    assert direct_p.status == PotentialStatus.UNKNOWN


def test_potential_invalid_status_rejected(db):
    service = PotentialService(db)
    with pytest.raises(ValueError):
        service.create(phenomenon="Invalid Status Potential", status="INVALID_STATUS")

    created = service.create(phenomenon="Valid Status Potential")
    with pytest.raises(ValueError):
        service.update(created.id, status="NON_EXISTENT_STATUS")


def test_attach_condition(db):
    service = PotentialService(db)
    p = service.create(phenomenon="Condition Test Potential")
    updated = service.attach_condition(p.id, "Temp > 100K")
    assert updated is not None
    assert updated.required_conditions == ["Temp > 100K"]

    updated = service.attach_condition(p.id, "Pressure > 50GPa")
    assert updated.required_conditions == ["Temp > 100K", "Pressure > 50GPa"]


def test_attach_constraint(db):
    service = PotentialService(db)
    p = service.create(phenomenon="Constraint Test Potential")
    updated = service.attach_constraint(p.id, 501)
    assert updated is not None
    assert updated.blocking_constraints == [501]

    updated = service.attach_constraint(p.id, 502)
    assert updated.blocking_constraints == [501, 502]


def test_attach_context(db):
    service = PotentialService(db)
    p = service.create(phenomenon="Context Test Potential")
    updated = service.attach_context(p.id, 301)
    assert updated is not None
    assert updated.supporting_contexts == [301]

    updated = service.attach_context(p.id, 302)
    assert updated.supporting_contexts == [301, 302]


def test_required_conditions_json(db):
    service = PotentialService(db)
    conditions = [{"type": "env", "var": "temp", "min": 300}, "Stable power"]
    p = service.create(phenomenon="JSON Conditions Potential", required_conditions=conditions)
    assert p.required_conditions == conditions

    retrieved = service.get(p.id)
    assert retrieved.required_conditions[0]["var"] == "temp"


def test_blocking_constraints_json(db):
    service = PotentialService(db)
    constraints = [10, 20, "constraint:legal_01"]
    p = service.create(phenomenon="JSON Constraints Potential", blocking_constraints=constraints)
    assert p.blocking_constraints == constraints

    retrieved = service.get(p.id)
    assert retrieved.blocking_constraints[2] == "constraint:legal_01"


def test_expected_impacts_json(db):
    service = PotentialService(db)
    impacts = [{"target": "Ecology", "impact_type": "Disruption", "magnitude": "High"}]
    p = service.create(phenomenon="JSON Impacts Potential", expected_impacts=impacts)
    assert p.expected_impacts == impacts

    retrieved = service.get(p.id)
    assert retrieved.expected_impacts[0]["target"] == "Ecology"


def test_potential_provenance_preserved(db):
    service = PotentialService(db)
    provenance_data = {"author": "observer_1", "notes": "initial hypothesis"}
    p = service.create(phenomenon="Provenance Potential", provenance=provenance_data)
    assert p.provenance == provenance_data

    retrieved = service.get(p.id)
    assert retrieved.provenance["author"] == "observer_1"


def test_potential_not_prediction():
    """Assertion test verifying documentation explicitly distinguishes Potential Phenomenon from Prediction.

    Potential Phenomenon ≠ Prediction.
    - Prediction: epistemic claim about what WILL happen (forward-looking).
    - Potential Phenomenon: modal/structural representation of what COULD emerge,
      conditional on conditions/contexts/constraints.
    """
    assert "Potential Phenomenon ≠ Prediction" in (PotentialPhenomenon.__doc__ or "")
    assert "could emerge" in (PotentialPhenomenon.__doc__ or "").lower()
    assert "epistemic claim about what will happen" in (PotentialPhenomenon.__doc__ or "").lower()

    assert "Potential Phenomenon ≠ Prediction" in (PotentialService.__doc__ or "")
