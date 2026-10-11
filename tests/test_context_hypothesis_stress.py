"""
Context and Hypothesis Stress Test Suite (TASK 41).

Verifies reasoning behavior under different contexts, blocked potentials,
absent data, competing hypotheses, and post-analysis relation changes for
GUARANTEED/PARTIAL properties identified in Step 0 Audit:

- Property 1: Same H0, different contexts (GUARANTEED)
- Property 2: Blockage != impossibility (GUARANTEED)
- Property 3: Absence of data != evidence of absence (GUARANTEED)
- Property 4a: Competing hypotheses coexistence (GUARANTEED)
- Property 5a: Current-state rerun reflects current state (GUARANTEED)

Unsupported properties (4b, 5b, 5c, 6) are classified as ARCHITECTURAL GAPS per ADR-0009
and are NOT simulated or tested here.
"""

import pytest
from sqlalchemy.orm import Session

from smos.models.models import RelationType, EpistemicStatus
from smos.models.constraint import ConstraintType, ConstraintStatus
from smos.models.potential import PotentialStatus
from smos.models.four_position_contract import FourPosition

from smos.services.phenomenon_service import PhenomenonService
from smos.services.context_service import ContextService
from smos.services.constraint_service import ConstraintService
from smos.services.potential_service import PotentialService
from smos.services.domain_relation_service import DomainRelationService
from smos.services.four_position_service import FourPositionService
from smos.services.emergence_analysis_service import EmergenceAnalysisService
from smos.services.blockage_analysis_service import BlockageAnalysisService
from smos.services.role_projection_service import RoleProjectionService


@pytest.fixture
def stress_scenario(db: Session):
    """
    Local test scenario for context and hypothesis stress testing:
    - Hypothesis H0: "Geothermal Heat Extraction Network"
    - Context 1: "Volcanic Rift Zone" (High geothermal potential)
    - Context 2: "Urban Residential District" (Strict seismic noise regulations)
    - Constraint: "Subsurface Drilling Depth Limit"
    - Potential: "Regional District Heating Grid" (BLOCKED)
    - Competing Hypotheses: H1 ("Ground Source Heat Pump Fleet"), H2 ("Biomass Cogeneration")
    """
    ps = PhenomenonService(db)
    cs = ContextService(db)
    c_svc = ConstraintService(db)
    pot_svc = PotentialService(db)
    drs = DomainRelationService(db)

    # Core H0 Hypothesis
    h0 = ps.create(
        name="Geothermal Heat Extraction Network",
        description="Deep subsurface hydrothermal extraction array",
        epistemic_status=EpistemicStatus.OBSERVED,
        source="energy_transition_study_2026",
    )

    # Target phenomenon for Position I (H0 ENABLES p_district_heat)
    p_district_heat = ps.create(
        name="District Heating Utility Supply",
        description="Municipal hot water supply network",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    # Target phenomenon for Position IV (H0 PREVENTS p_fossil_boilers)
    p_fossil_boilers = ps.create(
        name="Residential Oil Boiler Heating",
        description="Individual oil-fired home boilers",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    # Distinct Contexts with Concrete Semantic Differences
    ctx_volcanic = cs.create(
        name="Volcanic Rift Zone",
        description="High subsurface thermal gradient with low population density",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    ctx_urban = cs.create(
        name="Urban Residential District",
        description="Dense residential area with strict vibration and surface footprint limits",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    # Relations linking H0 to Contexts and target Phenomena
    rel_volcanic_enables = drs.create(
        source_type="context",
        source_id=ctx_volcanic.id,
        target_type="phenomenon",
        target_id=h0.id,
        relation_type=RelationType.ENABLES,
        confidence=0.95,
        evidence=[2001],
    )

    rel_h0_enables_heat = drs.create(
        source_type="phenomenon",
        source_id=h0.id,
        target_type="phenomenon",
        target_id=p_district_heat.id,
        relation_type=RelationType.ENABLES,
        confidence=0.90,
        evidence=[2002],
    )

    # Constraint & Blocked Potential
    c_drilling = c_svc.create(
        name="Subsurface Drilling Depth Limit",
        description="Environmental cap on drilling depth below 3000 meters",
        type=ConstraintType.TECHNICAL,
        status=ConstraintStatus.ACTIVE,
        confidence=0.9,
    )

    pot_blocked_grid = pot_svc.create(
        phenomenon="Regional District Heating Grid",
        status=PotentialStatus.BLOCKED,
        required_conditions=["Deep drilling approval", "High flow temperature"],
        blocking_constraints=["Subsurface Drilling Depth Limit"],
    )

    # Competing Hypotheses (Coexisting Phenomena)
    h1 = ps.create(
        name="Ground Source Heat Pump Fleet",
        description="Shallow geothermal heat pumps for individual buildings",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    h2 = ps.create(
        name="Biomass Cogeneration Plant",
        description="Wood pellet combustion facility for local heat",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )

    return {
        "h0": h0,
        "ctx_volcanic": ctx_volcanic,
        "ctx_urban": ctx_urban,
        "p_district_heat": p_district_heat,
        "p_fossil_boilers": p_fossil_boilers,
        "rel_volcanic_enables": rel_volcanic_enables,
        "rel_h0_enables_heat": rel_h0_enables_heat,
        "c_drilling": c_drilling,
        "pot_blocked_grid": pot_blocked_grid,
        "h1": h1,
        "h2": h2,
    }


def test_property_1_same_h0_different_contexts(db: Session, stress_scenario: dict):
    """
    Property 1 (Same H0, different contexts):
    Verifies that analyzing H0 or projecting roles under different contexts reflects
    concrete context-dependent differences in relations and perspectives.
    """
    sc = stress_scenario
    h0 = sc["h0"]
    ctx_volcanic = sc["ctx_volcanic"]
    ctx_urban = sc["ctx_urban"]

    role_svc = RoleProjectionService(db)

    # Perspective from Volcanic context
    volcanic_perspective = role_svc.context(ctx_volcanic.id)
    assert len(volcanic_perspective["enabled_phenomena"]) == 1
    assert volcanic_perspective["enabled_phenomena"][0]["target_id"] == h0.id

    # Perspective from Urban context (no ENABLES relation linked to H0)
    urban_perspective = role_svc.context(ctx_urban.id)
    assert len(urban_perspective["enabled_phenomena"]) == 0

    # Four-Position analysis reflects context-linked evidence for Position I
    fps = FourPositionService(db)
    analysis = fps.build_analysis(h0.id)

    pos_i = analysis["positions"][FourPosition.PRESENT_EXISTS.value]
    assert pos_i["status"] == "RESOLVED"
    assert pos_i["claim"] is not None

    # Emergence analysis reflects supporting conditions from volcanic context
    eas = EmergenceAnalysisService(db)
    emergence = eas.analyze_emergence(h0.id)
    supporting_context_ids = [cond.get("source_id") for cond in emergence.supporting_conditions if cond.get("source_type") == "context"]
    assert ctx_volcanic.id in supporting_context_ids
    assert ctx_urban.id not in supporting_context_ids


def test_property_2_blockage_is_not_impossibility(db: Session, stress_scenario: dict):
    """
    Property 2 (Blockage != impossibility):
    Verifies that a blocked potential remains registered as a modal possibility
    (PotentialPhenomenon object with status BLOCKED), rather than being treated
    as non-existent or impossible.
    """
    sc = stress_scenario
    pot_blocked = sc["pot_blocked_grid"]

    pot_svc = PotentialService(db)
    retrieved_pot = pot_svc.get(pot_blocked.id)

    # Blocked potential exists and retains its identity as a PotentialPhenomenon
    assert retrieved_pot is not None
    assert retrieved_pot.status == PotentialStatus.BLOCKED.value
    assert retrieved_pot.phenomenon == "Regional District Heating Grid"
    assert "Subsurface Drilling Depth Limit" in retrieved_pot.blocking_constraints

    # BlockageAnalysisService correctly identifies active constraints without deleting potential
    bas = BlockageAnalysisService(db)
    blockage = bas.analyze_blockage(sc["h0"].id)
    assert blockage.phenomenon_id == sc["h0"].id


def test_property_3_absence_of_data_is_unresolved(db: Session, stress_scenario: dict):
    """
    Property 3 (Absence of data != evidence of absence):
    Verifies that a phenomenon with missing or absent relation data produces UNRESOLVED
    positions, rather than false claims of non-existence.
    """
    ps = PhenomenonService(db)
    unknown_h = ps.create(
        name="Unstudied Subsurface Anomaly",
        description="Phenomenon with zero relations or evidence",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )

    fps = FourPositionService(db)
    analysis = fps.build_analysis(unknown_h.id)

    # All four positions remain UNRESOLVED with null claims
    for pos_key, pos_data in analysis["positions"].items():
        assert pos_data["status"] == "UNRESOLVED"
        assert pos_data["claim"] is None

    # Emergence analysis produces HYPOTHESIZED empty conditions without error or false facts
    eas = EmergenceAnalysisService(db)
    emergence = eas.analyze_emergence(unknown_h.id)
    assert emergence.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert len(emergence.necessary_conditions) == 0
    assert len(emergence.supporting_conditions) == 0


def test_property_4a_competing_hypotheses_coexistence(db: Session, stress_scenario: dict):
    """
    Property 4a (Competing hypotheses - coexistence):
    Verifies that multiple competing phenomenon entities (H0, H1, H2) coexist simultaneously
    in the database without mutual deletion, overwriting, or corruption.
    """
    sc = stress_scenario
    ps = PhenomenonService(db)

    h0 = ps.get(sc["h0"].id)
    h1 = ps.get(sc["h1"].id)
    h2 = ps.get(sc["h2"].id)

    assert h0 is not None and h0.name == "Geothermal Heat Extraction Network"
    assert h1 is not None and h1.name == "Ground Source Heat Pump Fleet"
    assert h2 is not None and h2.name == "Biomass Cogeneration Plant"

    # All three phenomena retain distinct identities and epistemic statuses
    assert h0.epistemic_status == EpistemicStatus.OBSERVED.value
    assert h1.epistemic_status == EpistemicStatus.OBSERVED.value
    assert h2.epistemic_status == EpistemicStatus.HYPOTHESIZED.value


def test_property_5a_current_state_rerun(db: Session, stress_scenario: dict):
    """
    Property 5a (Current-state rerun reflects current state):
    Verifies that re-executing analytical services after modifying DomainRelation
    records reflects the updated live state of the database.
    """
    sc = stress_scenario
    h0 = sc["h0"]
    p_fossil_boilers = sc["p_fossil_boilers"]
    drs = DomainRelationService(db)
    fps = FourPositionService(db)

    # Initial analysis: Position IV (PREVENTS) is UNRESOLVED
    analysis_initial = fps.build_analysis(h0.id)
    pos_iv_initial = analysis_initial["positions"][FourPosition.PRESENT_ABSENT.value]
    assert pos_iv_initial["status"] == "UNRESOLVED"

    # Add new outgoing relation: H0 PREVENTS p_fossil_boilers
    drs.create(
        source_type="phenomenon",
        source_id=h0.id,
        target_type="phenomenon",
        target_id=p_fossil_boilers.id,
        relation_type=RelationType.PREVENTS,
        confidence=0.88,
        evidence=[2003],
    )

    # Current-state rerun: reflects newly added relation
    analysis_rerun = fps.build_analysis(h0.id)
    pos_iv_rerun = analysis_rerun["positions"][FourPosition.PRESENT_ABSENT.value]

    assert pos_iv_rerun["status"] == "RESOLVED"
    assert pos_iv_rerun["claim"] is not None
    assert "displaced/prevented" in pos_iv_rerun["claim"]
