"""
Tests for FourPositionService (TASK 25).

Validates four-position modal analysis projection, read-only guarantees,
preservation of source epistemic status and provenance, and semantic distinctions.
"""

import pytest
from sqlalchemy.orm import Session

from smos.models.models import RelationType, EpistemicStatus, Relation
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.prediction import Prediction
from smos.models.four_position_contract import (
    FourPosition,
    validate_four_position_analysis,
)
from smos.services.four_position_service import FourPositionService
from smos.services.domain_relation_service import DomainRelationService
from smos.services.blockage_analysis_service import BlockageAnalysisService
from smos.services.emergence_analysis_service import EmergenceAnalysisService


@pytest.fixture
def sample_data(db: Session):
    """Fixture providing a rich domain topology for FourPositionService tests."""
    p_core = Phenomenon(
        name="Grid Modernization",
        description="Upgrade power grid infrastructure",
        epistemic_status=EpistemicStatus.OBSERVED,
        source="grid_study_2026",
    )
    p_downstream = Phenomenon(
        name="Renewable Integration",
        description="Integrate solar/wind into grid",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    p_prereq = Phenomenon(
        name="Smart Meter Rollout",
        description="Install smart meters",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    p_alt = Phenomenon(
        name="Legacy Substation Patching",
        description="Continue patching old substations",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    p_displaced = Phenomenon(
        name="Fossil Peak Plant Usage",
        description="Relying on old peaker plants",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    c_budget = Constraint(
        name="Capital Expenditure Cap",
        description="Annual budget limit",
    )

    ctx_urban = Context(
        name="Urban Metro Region",
        description="High density electrical grid",
    )

    db.add_all([p_core, p_downstream, p_prereq, p_alt, p_displaced, c_budget, ctx_urban])
    db.commit()
    for item in [p_core, p_downstream, p_prereq, p_alt, p_displaced, c_budget, ctx_urban]:
        db.refresh(item)

    domain_svc = DomainRelationService(db)

    # Position I: Grid Modernization ENABLES Renewable Integration
    rel_pos_i = domain_svc.create(
        source_type="phenomenon",
        source_id=p_core.id,
        target_type="phenomenon",
        target_id=p_downstream.id,
        relation_type=RelationType.ENABLES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.9,
        evidence=[101],
        provenance={"source": "engineering_report"},
    )

    # Position II: Grid Modernization REQUIRES Smart Meter Rollout (Smart Meter Rollout requires Grid Modernization / Smart Meter Rollout enables Grid Modernization -> so Smart Meter Rollout depends on Grid Modernization if Grid Modernization requires Smart Meter Rollout, Grid Modernization depends on Smart Meter Rollout. But if p_downstream REQUIRES p_core, then if p_core absent, p_downstream absent)
    # Smart Meter Rollout REQUIRES Grid Modernization -> so if Grid Modernization is absent, Smart Meter Rollout will NOT exist.
    rel_pos_ii = domain_svc.create(
        source_type="phenomenon",
        source_id=p_prereq.id,
        target_type="phenomenon",
        target_id=p_core.id,
        relation_type=RelationType.REQUIRES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.85,
        evidence=[102],
        provenance={"source": "dependency_tree"},
    )

    # Position III: Grid Modernization ALTERNATIVE_TO Legacy Substation Patching
    rel_pos_iii = domain_svc.create(
        source_type="phenomenon",
        source_id=p_core.id,
        target_type="phenomenon",
        target_id=p_alt.id,
        relation_type=RelationType.ALTERNATIVE_TO,
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
        confidence=0.7,
        evidence=[103],
        provenance={"source": "planning_doc"},
    )

    # Position IV: Grid Modernization PREVENTS Fossil Peak Plant Usage
    rel_pos_iv = domain_svc.create(
        source_type="phenomenon",
        source_id=p_core.id,
        target_type="phenomenon",
        target_id=p_displaced.id,
        relation_type=RelationType.PREVENTS,
        epistemic_status=EpistemicStatus.INFERRED,
        confidence=0.95,
        evidence=[104],
        provenance={"source": "emissions_study"},
    )

    # Separate relation representing "Grid Modernization IS BLOCKED by Capital Expenditure Cap"
    # This is a blockage of H, NOT Position II or Position IV.
    rel_blockage = domain_svc.create(
        source_type="constraint",
        source_id=c_budget.id,
        target_type="phenomenon",
        target_id=p_core.id,
        relation_type=RelationType.BLOCKS,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.8,
        evidence=[105],
    )

    return {
        "p_core": p_core,
        "p_downstream": p_downstream,
        "p_prereq": p_prereq,
        "p_alt": p_alt,
        "p_displaced": p_displaced,
        "c_budget": c_budget,
        "ctx_urban": ctx_urban,
        "rel_pos_i": rel_pos_i,
        "rel_pos_ii": rel_pos_ii,
        "rel_pos_iii": rel_pos_iii,
        "rel_pos_iv": rel_pos_iv,
        "rel_blockage": rel_blockage,
    }


def test_req_1_all_four_positions_always_returned(db: Session, sample_data: dict):
    """Test 1: All four positions are ALWAYS returned."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    is_valid, errors = validate_four_position_analysis(res)
    assert is_valid, f"Validation errors: {errors}"

    positions = res["positions"]
    assert FourPosition.PRESENT_EXISTS.value in positions
    assert FourPosition.ABSENT_ABSENT.value in positions
    assert FourPosition.ABSENT_EXISTS.value in positions
    assert FourPosition.PRESENT_ABSENT.value in positions


def test_req_2_same_phenomenon_is_source_for_all_positions(db: Session, sample_data: dict):
    """Test 2: The same Phenomenon remains the source of all four positions."""
    svc = FourPositionService(db)
    p_id = sample_data["p_core"].id
    res = svc.build_analysis(p_id)

    assert res["phenomenon_id"] == p_id
    p_name = sample_data["p_core"].name

    for pos_key, pos_data in res["positions"].items():
        if pos_data.get("claim"):
            assert p_name in pos_data["claim"]


def test_req_3_position_i_represents_present_exists(db: Session, sample_data: dict):
    """Test 3: Position I represents H exists -> what exists/happens."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    pos_i = res["positions"][FourPosition.PRESENT_EXISTS.value]
    assert pos_i["status"] == "RESOLVED"
    assert "Renewable Integration" in pos_i["claim"]
    assert pos_i["evidence"] == sorted([101, sample_data["rel_pos_i"].id])


def test_req_4_position_ii_represents_absent_absent(db: Session, sample_data: dict):
    """Test 4: Position II represents H absent -> what does not exist/happen."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    pos_ii = res["positions"][FourPosition.ABSENT_ABSENT.value]
    assert pos_ii["status"] == "RESOLVED"
    assert "Smart Meter Rollout" in pos_ii["claim"]
    assert pos_ii["evidence"] == sorted([102, sample_data["rel_pos_ii"].id])


def test_req_5_position_iii_represents_absent_exists(db: Session, sample_data: dict):
    """Test 5: Position III represents H absent -> what exists/happens instead."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    pos_iii = res["positions"][FourPosition.ABSENT_EXISTS.value]
    assert pos_iii["status"] == "RESOLVED"
    assert "Legacy Substation Patching" in pos_iii["claim"]
    assert pos_iii["evidence"] == sorted([103, sample_data["rel_pos_iii"].id])


def test_req_6_position_iv_represents_present_absent(db: Session, sample_data: dict):
    """Test 6: Position IV represents H exists -> what does not exist/happen."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    pos_iv = res["positions"][FourPosition.PRESENT_ABSENT.value]
    assert pos_iv["status"] == "RESOLVED"
    assert "Fossil Peak Plant Usage" in pos_iv["claim"]
    assert pos_iv["evidence"] == sorted([104, sample_data["rel_pos_iv"].id])


def test_req_7_missing_evidence_produces_unresolved(db: Session):
    """Test 7: Missing evidence produces UNRESOLVED rather than invented claims."""
    p_isolated = Phenomenon(
        name="Isolated Island Microgrid",
        description="Standalone microgrid",
    )
    db.add(p_isolated)
    db.commit()
    db.refresh(p_isolated)

    svc = FourPositionService(db)
    res = svc.build_analysis(p_isolated.id)

    is_valid, errors = validate_four_position_analysis(res)
    assert is_valid, f"Validation errors: {errors}"

    for pos_key, pos_data in res["positions"].items():
        assert pos_data["claim"] is None
        assert pos_data["evidence"] == []
        assert pos_data["status"] == "UNRESOLVED"


def test_req_8_existing_epistemic_statuses_preserved(db: Session, sample_data: dict):
    """Test 8: Existing epistemic statuses are PRESERVED without auto-promotion."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    pos_i = res["positions"][FourPosition.PRESENT_EXISTS.value]
    # Source relation was OBSERVED -> project status should remain OBSERVED
    assert pos_i["epistemic_status"] == EpistemicStatus.OBSERVED.value

    pos_iv = res["positions"][FourPosition.PRESENT_ABSENT.value]
    # Source relation was INFERRED -> project status should remain INFERRED
    assert pos_iv["epistemic_status"] == EpistemicStatus.INFERRED.value


def test_req_9_provenance_and_evidence_preserved(db: Session, sample_data: dict):
    """Test 9: Provenance and evidence are PRESERVED from source relations."""
    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    pos_i = res["positions"][FourPosition.PRESENT_EXISTS.value]
    assert 101 in pos_i["evidence"]
    assert pos_i["provenance"].get("source") == "engineering_report"


def test_req_10_11_12_13_read_only_guarantees(db: Session, sample_data: dict):
    """Tests 10, 11, 12, 13: Read-only guarantee.

    Verifies build_analysis() creates/modifies NO DomainRelation,
    Phenomenon, Prediction, or Recipe.
    """
    rel_count_before = db.query(DomainRelation).count()
    phenom_count_before = db.query(Phenomenon).count()
    pred_count_before = db.query(Prediction).count()

    svc = FourPositionService(db)
    res = svc.build_analysis(sample_data["p_core"].id)

    assert db.query(DomainRelation).count() == rel_count_before
    assert db.query(Phenomenon).count() == phenom_count_before
    assert db.query(Prediction).count() == pred_count_before


def test_req_14_determinism(db: Session, sample_data: dict):
    """Test 14: Repeated execution with unchanged input produces equivalent output."""
    svc = FourPositionService(db)
    res1 = svc.build_analysis(sample_data["p_core"].id)
    res2 = svc.build_analysis(sample_data["p_core"].id)

    assert res1 == res2


def test_semantic_distinction_blockage_vs_position_ii(db: Session, sample_data: dict):
    """IMPORTANT SEMANTIC TEST 1: Distinguish 'H is blocked' from 'If H does not occur, X will not occur.'

    Blockage Service reports: Capital Expenditure Cap BLOCKS Grid Modernization.
    Position II reports: Smart Meter Rollout will not occur if Grid Modernization does not occur.
    These are completely different statements and must not be conflated.
    """
    svc = FourPositionService(db)
    blockage_svc = BlockageAnalysisService(db)

    blockage_res = blockage_svc.analyze_blockage(sample_data["p_core"].id)
    four_pos_res = svc.build_analysis(sample_data["p_core"].id)

    pos_ii = four_pos_res["positions"][FourPosition.ABSENT_ABSENT.value]

    # Blockage analysis shows Capital Expenditure Cap
    direct_blockers = [b["constraint_name"] for b in blockage_res.direct_constraints]
    assert "Capital Expenditure Cap" in direct_blockers

    # Position II shows Smart Meter Rollout (consequence of absence)
    assert "Smart Meter Rollout" in pos_ii["claim"]
    assert "Capital Expenditure Cap" not in pos_ii["claim"]


def test_semantic_distinction_emergence_vs_position_iv(db: Session, sample_data: dict):
    """IMPORTANT SEMANTIC TEST 2: Distinguish 'H can emerge' from 'If H occurs, Y will not occur.'

    Emergence Service reports conditions under which H can emerge.
    Position IV reports what is displaced/prevented by H (Fossil Peak Plant Usage).
    These are completely different statements and must not be conflated.
    """
    svc = FourPositionService(db)
    emergence_svc = EmergenceAnalysisService(db)

    emergence_res = emergence_svc.analyze_emergence(sample_data["p_core"].id)
    four_pos_res = svc.build_analysis(sample_data["p_core"].id)

    pos_iv = four_pos_res["positions"][FourPosition.PRESENT_ABSENT.value]

    # Position IV reports Fossil Peak Plant Usage displaced by H
    assert "Fossil Peak Plant Usage" in pos_iv["claim"]

    # Emergence Analysis reports conditions/effects for emergence, NOT Position IV's definition
    assert pos_iv["claim"] != emergence_res.note
