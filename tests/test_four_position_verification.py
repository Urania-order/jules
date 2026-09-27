"""
Integration tests for Four-Position Analysis Verification (TASK 26).

Verifies that FourPositionService (TASK 25) preserves the canonical
Four-Position semantics defined by TASK 24.
"""

import pytest
from sqlalchemy.orm import Session

from smos.models.models import RelationType, EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.prediction import Prediction
from smos.models.context_exposure import ContextExposure
from smos.models.domain_event import DomainEvent
from smos.models.four_position_contract import (
    FourPosition,
    normalize_four_position_analysis,
    validate_four_position_analysis,
)
from smos.services.four_position_service import FourPositionService
from smos.services.domain_relation_service import DomainRelationService


@pytest.fixture
def scenario_air_cleaning(db: Session):
    """Fixture providing conceptual scenario: H = Air-Cleaning Facility.

    Sets up observable, independent domain entities for all four positions:
    - H: Air-Cleaning Facility
    - X (Position I): Local Air Purification Capacity
    - Y (Position II): District Clean Air Certification
    - Z (Position III): Existing Industrial Scrubbers
    - W (Position IV): Atmospheric Pollutant Accumulation
    - C (Blockage Constraint): High Power Demand Cap
    """
    h_facility = Phenomenon(
        name="Air-Cleaning Facility",
        description="A facility designed to purify ambient air",
        epistemic_status=EpistemicStatus.OBSERVED,
        source="facility_spec_2026",
    )
    x_capacity = Phenomenon(
        name="Local Air Purification Capacity",
        description="Volumetric air flow filtration throughput",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    y_certification = Phenomenon(
        name="District Clean Air Certification",
        description="Regulatory air quality compliance status",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    z_scrubbers = Phenomenon(
        name="Existing Industrial Scrubbers",
        description="Legacy point-source scrubber units",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    w_pollutants = Phenomenon(
        name="Atmospheric Pollutant Accumulation",
        description="Particulate build-up in local basin",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    c_power_cap = Constraint(
        name="High Power Demand Cap",
        description="Electricity grid intake restriction during peak hours",
    )

    ctx_urban = Context(
        name="Urban Industrial Zone",
        description="Metropolitan area with heavy industrial operations",
    )

    db.add_all([
        h_facility, x_capacity, y_certification,
        z_scrubbers, w_pollutants, c_power_cap, ctx_urban,
    ])
    db.commit()

    for item in [h_facility, x_capacity, y_certification, z_scrubbers, w_pollutants, c_power_cap, ctx_urban]:
        db.refresh(item)

    domain_svc = DomainRelationService(db)

    # Position I: H ENABLES X
    rel_pos_i = domain_svc.create(
        source_type="phenomenon",
        source_id=h_facility.id,
        target_type="phenomenon",
        target_id=x_capacity.id,
        relation_type=RelationType.ENABLES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.9,
        evidence=[101],
        provenance={"source": "air_quality_study"},
    )

    # Position II: Y REQUIRES H (If H absent -> Y will not occur)
    rel_pos_ii = domain_svc.create(
        source_type="phenomenon",
        source_id=y_certification.id,
        target_type="phenomenon",
        target_id=h_facility.id,
        relation_type=RelationType.REQUIRES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.85,
        evidence=[202],
        provenance={"source": "regulatory_compliance_doc"},
    )

    # Position III: H ALTERNATIVE_TO Z (If H absent -> Z exists instead)
    rel_pos_iii = domain_svc.create(
        source_type="phenomenon",
        source_id=h_facility.id,
        target_type="phenomenon",
        target_id=z_scrubbers.id,
        relation_type=RelationType.ALTERNATIVE_TO,
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
        confidence=0.75,
        evidence=[303],
        provenance={"source": "facility_options_analysis"},
    )

    # Position IV: H PREVENTS W (If H exists -> W does not exist / displaced)
    rel_pos_iv = domain_svc.create(
        source_type="phenomenon",
        source_id=h_facility.id,
        target_type="phenomenon",
        target_id=w_pollutants.id,
        relation_type=RelationType.PREVENTS,
        epistemic_status=EpistemicStatus.INFERRED,
        confidence=0.92,
        evidence=[404],
        provenance={"source": "environmental_impact_model"},
    )

    # Separate Blockage relation: Constraint C BLOCKS H
    rel_blockage = domain_svc.create(
        source_type="constraint",
        source_id=c_power_cap.id,
        target_type="phenomenon",
        target_id=h_facility.id,
        relation_type=RelationType.BLOCKS,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.8,
        evidence=[505],
        provenance={"source": "grid_capacity_audit"},
    )

    return {
        "h_facility": h_facility,
        "x_capacity": x_capacity,
        "y_certification": y_certification,
        "z_scrubbers": z_scrubbers,
        "w_pollutants": w_pollutants,
        "c_power_cap": c_power_cap,
        "ctx_urban": ctx_urban,
        "rel_pos_i": rel_pos_i,
        "rel_pos_ii": rel_pos_ii,
        "rel_pos_iii": rel_pos_iii,
        "rel_pos_iv": rel_pos_iv,
        "rel_blockage": rel_blockage,
    }


def test_1_canonical_structure(db: Session, scenario_air_cleaning: dict):
    """TEST 1 — CANONICAL STRUCTURE."""
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    analysis = service.build_analysis(h_id)

    # 1. phenomenon_id identifies requested Phenomenon
    assert analysis["phenomenon_id"] == h_id

    # 2. positions exists
    assert "positions" in analysis
    positions = analysis["positions"]

    # 3. All four canonical positions are present
    expected_positions = {
        FourPosition.PRESENT_EXISTS.value,
        FourPosition.ABSENT_ABSENT.value,
        FourPosition.ABSENT_EXISTS.value,
        FourPosition.PRESENT_ABSENT.value,
    }
    assert set(positions.keys()) == expected_positions

    # 4. No additional replacement position is used
    assert len(positions) == 4

    # 5. Every position conforms to TASK 24 canonical structure
    is_valid, errors = validate_four_position_analysis(analysis)
    assert is_valid, f"Canonical validation failed: {errors}"


def test_2_four_questions_remain_distinct(db: Session, scenario_air_cleaning: dict):
    """TEST 2 — FOUR QUESTIONS REMAIN DISTINCT.

    Verifies semantics using fixture evidence that makes distinctions observable.
    """
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    analysis = service.build_analysis(h_id)
    positions = analysis["positions"]

    pos_i = positions[FourPosition.PRESENT_EXISTS.value]
    pos_ii = positions[FourPosition.ABSENT_ABSENT.value]
    pos_iii = positions[FourPosition.ABSENT_EXISTS.value]
    pos_iv = positions[FourPosition.PRESENT_ABSENT.value]

    # Verify observable domain entities referenced in claims
    assert "Local Air Purification Capacity" in pos_i["claim"]
    assert "District Clean Air Certification" in pos_ii["claim"]
    assert "Existing Industrial Scrubbers" in pos_iii["claim"]
    assert "Atmospheric Pollutant Accumulation" in pos_iv["claim"]

    # Verify observable distinct evidence sources referenced
    assert 101 in pos_i["evidence"]
    assert 202 in pos_ii["evidence"]
    assert 303 in pos_iii["evidence"]
    assert 404 in pos_iv["evidence"]


def test_3_no_mechanical_inversion(db: Session, scenario_air_cleaning: dict):
    """TEST 3 — NO MECHANICAL INVERSION.

    Verifies III is not derived from I by negating claims, and IV is not derived
    from II by negating claims.
    """
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    analysis = service.build_analysis(h_id)
    positions = analysis["positions"]

    pos_i = positions[FourPosition.PRESENT_EXISTS.value]
    pos_ii = positions[FourPosition.ABSENT_ABSENT.value]
    pos_iii = positions[FourPosition.ABSENT_EXISTS.value]
    pos_iv = positions[FourPosition.PRESENT_ABSENT.value]

    # Verify independent domain entities rather than textual negation
    # Position III references target entity Z (Existing Industrial Scrubbers), NOT target entity X (Local Air Purification Capacity)
    assert scenario_air_cleaning["z_scrubbers"].name in pos_iii["claim"]
    assert scenario_air_cleaning["x_capacity"].name not in pos_iii["claim"]

    # Position IV references target entity W (Atmospheric Pollutant Accumulation), NOT source entity Y (District Clean Air Certification)
    assert scenario_air_cleaning["w_pollutants"].name in pos_iv["claim"]
    assert scenario_air_cleaning["y_certification"].name not in pos_iv["claim"]

    # Compare evidence sources
    assert set(pos_i["evidence"]).isdisjoint(set(pos_iii["evidence"]))
    assert set(pos_ii["evidence"]).isdisjoint(set(pos_iv["evidence"]))


def test_4_blockage_is_not_absence_consequence(db: Session, scenario_air_cleaning: dict):
    """TEST 4 — BLOCKAGE IS NOT ABSENCE CONSEQUENCE.

    H is blocked by constraint C ("High Power Demand Cap").
    Verify that this constraint does NOT automatically become Position II ("ABSENT_ABSENT").
    """
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    analysis = service.build_analysis(h_id)
    pos_ii = analysis["positions"][FourPosition.ABSENT_ABSENT.value]

    # Position II must reflect consequence (District Clean Air Certification)
    assert scenario_air_cleaning["y_certification"].name in pos_ii["claim"]

    # Position II must NOT silently re-interpret blockage constraint as a counterfactual consequence
    assert scenario_air_cleaning["c_power_cap"].name not in pos_ii["claim"]
    assert scenario_air_cleaning["rel_blockage"].id not in pos_ii["evidence"]


def test_5_unresolved_is_valid(db: Session):
    """TEST 5 — UNRESOLVED IS VALID.

    Create a Phenomenon with insufficient evidence for Four-Positions.
    Verify positions remain PRESENT, explicitly UNRESOLVED, and without invented claims.
    """
    h_sparse = Phenomenon(
        name="Experimental Nanotech Filter",
        description="Unverified experimental filter",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    db.add(h_sparse)
    db.commit()
    db.refresh(h_sparse)

    service = FourPositionService(db)
    analysis = service.build_analysis(h_sparse.id)

    # 1. Position is still PRESENT
    assert len(analysis["positions"]) == 4

    for pos_key in FourPosition:
        pos_data = analysis["positions"][pos_key.value]
        # 2. Explicitly UNRESOLVED according to TASK 24 / TASK 25 canonical representation
        assert pos_data["status"] == "UNRESOLVED"
        # 3. Does NOT receive an invented claim
        assert pos_data["claim"] is None
        # 4. Does NOT receive fabricated evidence
        assert pos_data["evidence"] == []


def test_6_source_epistemic_status_is_preserved(db: Session, scenario_air_cleaning: dict):
    """TEST 6 — SOURCE EPISTEMIC STATUS IS PRESERVED."""
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    analysis = service.build_analysis(h_id)
    positions = analysis["positions"]

    # Source relation for Position I has OBSERVED
    assert positions[FourPosition.PRESENT_EXISTS.value]["epistemic_status"] == EpistemicStatus.OBSERVED.value

    # Source relation for Position III has HYPOTHESIZED
    assert positions[FourPosition.ABSENT_EXISTS.value]["epistemic_status"] == EpistemicStatus.HYPOTHESIZED.value

    # Source relation for Position IV has INFERRED
    assert positions[FourPosition.PRESENT_ABSENT.value]["epistemic_status"] == EpistemicStatus.INFERRED.value


def test_7_provenance_and_evidence_preservation(db: Session, scenario_air_cleaning: dict):
    """TEST 7 — PROVENANCE / EVIDENCE PRESERVATION.

    Verifies evidence IDs and provenance attached to source material remain traceable.
    """
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    analysis = service.build_analysis(h_id)
    pos_i = analysis["positions"][FourPosition.PRESENT_EXISTS.value]

    # Source relation ID and evidence IDs preserved
    assert scenario_air_cleaning["rel_pos_i"].id in pos_i["evidence"]
    assert 101 in pos_i["evidence"]

    # Source relation provenance dict preserved
    assert pos_i["provenance"].get("source") == "air_quality_study"


def test_8_reproducibility(db: Session, scenario_air_cleaning: dict):
    """TEST 8 — REPRODUCIBILITY.

    Build the same analysis twice without changing canonical input state and compare
    normalized outputs.
    """
    service = FourPositionService(db)
    h_id = scenario_air_cleaning["h_facility"].id

    a1 = service.build_analysis(h_id)
    a2 = service.build_analysis(h_id)

    norm_a1 = normalize_four_position_analysis(a1)
    norm_a2 = normalize_four_position_analysis(a2)

    assert norm_a1 == norm_a2


def test_9_read_only(db: Session, scenario_air_cleaning: dict):
    """TEST 9 — READ-ONLY.

    Takes snapshot of state before and after build_analysis() and confirms no changes.
    """
    def take_snapshot():
        return {
            "phenomena": [(p.id, p.name, p.epistemic_status) for p in db.query(Phenomenon).all()],
            "contexts": [(c.id, c.name) for c in db.query(Context).all()],
            "constraints": [(c.id, c.name) for c in db.query(Constraint).all()],
            "potentials": [(p.id, p.phenomenon) for p in db.query(PotentialPhenomenon).all()],
            "relations": [(r.id, r.source_type, r.source_id, r.target_type, r.target_id, r.relation_type) for r in db.query(DomainRelation).all()],
            "predictions": [(p.id, p.expected_state) for p in db.query(Prediction).all()],
            "exposures": [e.id for e in db.query(ContextExposure).all()],
            "events": [e.id for e in db.query(DomainEvent).all()],
        }

    before = take_snapshot()

    service = FourPositionService(db)
    service.build_analysis(scenario_air_cleaning["h_facility"].id)

    after = take_snapshot()

    assert before == after


def test_10_no_automatic_graph_mutation(db: Session, scenario_air_cleaning: dict):
    """TEST 10 — NO AUTOMATIC GRAPH MUTATION."""
    before_relations = [
        (r.id, r.source_type, r.source_id, r.target_type, r.target_id, r.relation_type)
        for r in db.query(DomainRelation).all()
    ]

    service = FourPositionService(db)
    service.build_analysis(scenario_air_cleaning["h_facility"].id)

    after_relations = [
        (r.id, r.source_type, r.source_id, r.target_type, r.target_id, r.relation_type)
        for r in db.query(DomainRelation).all()
    ]

    assert after_relations == before_relations


def test_11_no_epistemic_promotion(db: Session):
    """TEST 11 — NO EPISTEMIC PROMOTION.

    Source evidence with status HYPOTHESIZED must NOT become OBSERVED or VERIFIED.
    """
    h_hypo = Phenomenon(
        name="Experimental Catalyst",
        description="Hypothetical chemical filter",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    p_target = Phenomenon(
        name="Target Emission Reduction",
        description="Reduced smog",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    db.add_all([h_hypo, p_target])
    db.commit()

    domain_svc = DomainRelationService(db)
    domain_svc.create(
        source_type="phenomenon",
        source_id=h_hypo.id,
        target_type="phenomenon",
        target_id=p_target.id,
        relation_type=RelationType.ENABLES,
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )

    service = FourPositionService(db)
    analysis = service.build_analysis(h_hypo.id)

    pos_i = analysis["positions"][FourPosition.PRESENT_EXISTS.value]
    assert pos_i["epistemic_status"] == EpistemicStatus.HYPOTHESIZED.value
    assert pos_i["epistemic_status"] != EpistemicStatus.OBSERVED.value


def test_12_no_new_conclusion_model(db: Session, scenario_air_cleaning: dict):
    """TEST 12 — NO NEW CONCLUSION MODEL.

    Verify that Four-Position Analysis does NOT silently create persistent conclusions.
    """
    events_before = db.query(DomainEvent).count()

    service = FourPositionService(db)
    service.build_analysis(scenario_air_cleaning["h_facility"].id)

    events_after = db.query(DomainEvent).count()
    assert events_after == events_before


def test_13_position_order_and_identity(db: Session, scenario_air_cleaning: dict):
    """TEST 13 — POSITION ORDER / IDENTITY.

    Verify canonical positions remain identifiable by canonical enum values.
    """
    service = FourPositionService(db)
    analysis = service.build_analysis(scenario_air_cleaning["h_facility"].id)

    positions = analysis["positions"]

    for pos_enum in FourPosition:
        assert pos_enum.value in positions
        assert isinstance(positions[pos_enum.value], dict)


def test_14_no_false_symmetry(db: Session, scenario_air_cleaning: dict):
    """TEST 14 — NO FALSE SYMMETRY.

    Position III is NOT generated by negating Position I.
    Position IV is NOT generated by negating Position II.
    Demonstrated through independently represented evidence/entities.
    """
    service = FourPositionService(db)
    analysis = service.build_analysis(scenario_air_cleaning["h_facility"].id)

    positions = analysis["positions"]

    pos_i = positions[FourPosition.PRESENT_EXISTS.value]
    pos_ii = positions[FourPosition.ABSENT_ABSENT.value]
    pos_iii = positions[FourPosition.ABSENT_EXISTS.value]
    pos_iv = positions[FourPosition.PRESENT_ABSENT.value]

    # Position I entity vs Position III entity
    # Position I points to Local Air Purification Capacity (x_capacity)
    # Position III points to Existing Industrial Scrubbers (z_scrubbers)
    assert scenario_air_cleaning["x_capacity"].name in pos_i["claim"]
    assert scenario_air_cleaning["z_scrubbers"].name in pos_iii["claim"]
    assert pos_i["evidence"] != pos_iii["evidence"]

    # Position II entity vs Position IV entity
    # Position II source is District Clean Air Certification (y_certification)
    # Position IV target is Atmospheric Pollutant Accumulation (w_pollutants)
    assert scenario_air_cleaning["y_certification"].name in pos_ii["claim"]
    assert scenario_air_cleaning["w_pollutants"].name in pos_iv["claim"]
    assert pos_ii["evidence"] != pos_iv["evidence"]
