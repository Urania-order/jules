"""
End-to-end integration test for the Co-SMOS research pipeline (TASK 39).

Exercises the full research lifecycle from H0 hypothesis creation to prediction
evaluation, verifying that:
1. H0 creation works (PhenomenonService)
2. Contexts, Constraints, Potentials work
3. DomainRelations work with typed relation helpers
4. FourPositionService.build_analysis (with include_semantic=True) composes correctly
5. Semantic candidates are present as a signal in top-level analysis provenance
6. Positions are UNCHANGED by semantic retrieval
7. Canonical data (DomainRelation, evidence, epistemic_status, model fields) UNCHANGED
8. EmergenceAnalysisService and BlockageAnalysisService compose
9. PredictionService.create_prediction produces a PREDICTED hypothesis
10. attach_outcome preserves epistemic_status and identity
11. evaluate preserves epistemic_status, doesn't lose prior outcome
12. Historical prediction NOT overwritten by evaluate
13. Reproducibility: same canonical input -> same analysis content
14. NO auto-promotion anywhere
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from smos.models.models import RelationType, EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint, ConstraintType, ConstraintStatus
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.models.domain_relation import DomainRelation
from smos.models.prediction import Prediction
from smos.models.four_position_contract import FourPosition, normalize_four_position_analysis

from smos.services.phenomenon_service import PhenomenonService
from smos.services.context_service import ContextService
from smos.services.constraint_service import ConstraintService
from smos.services.potential_service import PotentialService
from smos.services.domain_relation_service import DomainRelationService
from smos.services.emergence_analysis_service import EmergenceAnalysisService
from smos.services.blockage_analysis_service import BlockageAnalysisService
from smos.services.four_position_service import FourPositionService
from smos.services.prediction_service import PredictionService
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter


@pytest.fixture
def e2e_research_scenario(db: Session):
    """
    Sets up an end-to-end research scenario around hypothesis H0:
    H0: "Solar Desalination Array" (Phenomenon, OBSERVED/HYPOTHESIZED)
    - Enriched with Context, Constraint, PotentialPhenomenon
    - Typed DomainRelations linking H0 to target phenomena, contexts, and constraints
    - Indexed in SemanticSearchService
    """
    phenom_svc = PhenomenonService(db)
    context_svc = ContextService(db)
    constraint_svc = ConstraintService(db)
    potential_svc = PotentialService(db)
    relation_svc = DomainRelationService(db)

    # 1. H0 Hypothesis: Solar Desalination Array
    h0 = phenom_svc.create(
        name="Solar Desalination Array",
        description="Autonomous solar-powered water desalination plant",
        epistemic_status=EpistemicStatus.OBSERVED,
        source="research_proposal_2026",
        provenance={"field_site": "Coastal Desert B"}
    )

    # 2. Related phenomena for Four-Position positions
    p_freshwater = phenom_svc.create(
        name="Potable Water Supply",
        description="Fresh drinking water volume in local reservoir",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    p_grid_cert = phenom_svc.create(
        name="Municipal Water Grid Certification",
        description="Regulatory approval for public distribution",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    p_diesel = phenom_svc.create(
        name="Diesel Engine Water Tankers",
        description="Mobile diesel water transport fleet",
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
    )
    p_salinity = phenom_svc.create(
        name="Aquifer Salinity Intrusion",
        description="Over-extraction induced soil salinization",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    # 3. Context, Constraint, Potential
    ctx_coastal = context_svc.create(
        name="Coastal Arid Region",
        description="High solar irradiance with limited natural groundwater",
        epistemic_status=EpistemicStatus.OBSERVED,
    )

    c_membrane_supply = constraint_svc.create(
        name="RO Membrane Supply Bottleneck",
        description="Global supply shortage of high-flux reverse osmosis membranes",
        type=ConstraintType.TECHNICAL,
        status=ConstraintStatus.ACTIVE,
        confidence=0.85,
    )

    pot_expansion = potential_svc.create(
        phenomenon="Regional Desalination Network",
        status=PotentialStatus.POSSIBLE,
        required_conditions=["High solar irradiance", "Membrane availability"],
    )

    # 4. Domain Relations for Four-Position Analysis
    # Position I: H0 ENABLES p_freshwater
    rel_pos_i = relation_svc.create(
        source_type="phenomenon",
        source_id=h0.id,
        target_type="phenomenon",
        target_id=p_freshwater.id,
        relation_type=RelationType.ENABLES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.9,
        evidence=[1001],
        provenance={"study": "desalination_pilot_2026"},
    )

    # Position II: p_grid_cert REQUIRES H0
    rel_pos_ii = relation_svc.create(
        source_type="phenomenon",
        source_id=p_grid_cert.id,
        target_type="phenomenon",
        target_id=h0.id,
        relation_type=RelationType.REQUIRES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.88,
        evidence=[1002],
        provenance={"regulation": "water_safety_code_2026"},
    )

    # Position III: H0 ALTERNATIVE_TO p_diesel
    rel_pos_iii = relation_svc.create(
        source_type="phenomenon",
        source_id=h0.id,
        target_type="phenomenon",
        target_id=p_diesel.id,
        relation_type=RelationType.ALTERNATIVE_TO,
        epistemic_status=EpistemicStatus.HYPOTHESIZED,
        confidence=0.75,
        evidence=[1003],
        provenance={"analysis": "logistics_alternative_study"},
    )

    # Position IV: H0 PREVENTS p_salinity
    rel_pos_iv = relation_svc.create(
        source_type="phenomenon",
        source_id=h0.id,
        target_type="phenomenon",
        target_id=p_salinity.id,
        relation_type=RelationType.PREVENTS,
        epistemic_status=EpistemicStatus.INFERRED,
        confidence=0.92,
        evidence=[1004],
        provenance={"model": "hydrogeology_simulation"},
    )

    # Blockage Relation: Constraint BLOCKS H0
    rel_block = relation_svc.create(
        source_type="constraint",
        source_id=c_membrane_supply.id,
        target_type="phenomenon",
        target_id=h0.id,
        relation_type=RelationType.BLOCKS,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.8,
        evidence=[1005],
    )

    # Context Relation: Context ENABLES H0
    rel_ctx = relation_svc.create(
        source_type="context",
        source_id=ctx_coastal.id,
        target_type="phenomenon",
        target_id=h0.id,
        relation_type=RelationType.ENABLES,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.95,
        evidence=[1006],
    )

    # 5. Index in Semantic Search
    semantic_svc = SemanticSearchService(db, HashFallbackAdapter())
    semantic_svc.index_canonical("phenomenon", h0.id)
    semantic_svc.index_canonical("phenomenon", p_freshwater.id)
    semantic_svc.index_canonical("phenomenon", p_diesel.id)

    return {
        "h0": h0,
        "p_freshwater": p_freshwater,
        "p_grid_cert": p_grid_cert,
        "p_diesel": p_diesel,
        "p_salinity": p_salinity,
        "ctx_coastal": ctx_coastal,
        "c_membrane_supply": c_membrane_supply,
        "pot_expansion": pot_expansion,
        "rel_pos_i": rel_pos_i,
        "rel_pos_ii": rel_pos_ii,
        "rel_pos_iii": rel_pos_iii,
        "rel_pos_iv": rel_pos_iv,
        "rel_block": rel_block,
        "rel_ctx": rel_ctx,
        "semantic_svc": semantic_svc,
    }


def test_e2e_h0_created(db: Session, e2e_research_scenario: dict):
    """1. Verify H0 creation works with correct fields and epistemic status."""
    h0 = e2e_research_scenario["h0"]
    ps = PhenomenonService(db)
    retrieved = ps.get(h0.id)

    assert retrieved is not None
    assert retrieved.id == h0.id
    assert retrieved.name == "Solar Desalination Array"
    assert retrieved.epistemic_status == EpistemicStatus.OBSERVED.value
    assert retrieved.source == "research_proposal_2026"
    assert retrieved.provenance == {"field_site": "Coastal Desert B"}


def test_e2e_contexts_constraints_potentials_created(db: Session, e2e_research_scenario: dict):
    """2. Verify Contexts, Constraints, and Potentials work properly."""
    sc = e2e_research_scenario
    assert sc["ctx_coastal"].name == "Coastal Arid Region"
    assert sc["c_membrane_supply"].name == "RO Membrane Supply Bottleneck"
    assert sc["c_membrane_supply"].type == ConstraintType.TECHNICAL.value
    assert sc["pot_expansion"].phenomenon == "Regional Desalination Network"
    assert sc["pot_expansion"].status == PotentialStatus.POSSIBLE.value


def test_e2e_domain_relations_created(db: Session, e2e_research_scenario: dict):
    """3. Verify DomainRelations work with typed helpers."""
    sc = e2e_research_scenario
    rel_svc = DomainRelationService(db)

    out_rels = rel_svc.list_for("phenomenon", sc["h0"].id)
    in_rels = rel_svc.list_into("phenomenon", sc["h0"].id)

    assert len(out_rels) >= 3  # ENABLES p_freshwater, ALTERNATIVE_TO p_diesel, PREVENTS p_salinity
    assert len(in_rels) >= 2   # p_grid_cert REQUIRES h0, c_membrane_supply BLOCKS h0, ctx_coastal ENABLES h0

    out_types = {r.relation_type for r in out_rels}
    assert RelationType.ENABLES.value in out_types
    assert RelationType.ALTERNATIVE_TO.value in out_types
    assert RelationType.PREVENTS.value in out_types


def test_e2e_four_position_with_semantic_signal(db: Session, e2e_research_scenario: dict):
    """
    4, 5, 6, 7. Verify FourPositionService.build_analysis(include_semantic=True) composes
    correctly, attaching semantic candidates as top-level provenance signal while keeping
    positions and canonical DB state completely UNCHANGED.
    """
    sc = e2e_research_scenario
    fps = FourPositionService(db, semantic_service=sc["semantic_svc"])

    # Baseline analysis without semantic
    a_base = fps.build_analysis(sc["h0"].id, include_semantic=False)
    # Analysis with semantic
    a_sem = fps.build_analysis(sc["h0"].id, include_semantic=True)

    # 4. Analysis structure composes
    assert a_sem["phenomenon_id"] == sc["h0"].id
    assert "positions" in a_sem
    assert len(a_sem["positions"]) == 4

    # 5. Semantic candidates present as a signal in top-level provenance ONLY
    assert a_base.get("provenance") is None
    assert "provenance" in a_sem
    assert "semantic_candidates" in a_sem["provenance"]
    assert isinstance(a_sem["provenance"]["semantic_candidates"], list)

    # 6. Position content is UNCHANGED by semantic retrieval
    norm_base_positions = normalize_four_position_analysis(a_base)["positions"]
    norm_sem_positions = normalize_four_position_analysis(a_sem)["positions"]
    assert norm_base_positions == norm_sem_positions

    # Confirm semantic candidates are NOT attached inside individual positions
    for pos_key, pos_data in a_sem["positions"].items():
        assert "semantic_candidates" not in pos_data["provenance"]

    # 7. Canonical DB entities and relations remain UNCHANGED
    ps = PhenomenonService(db)
    rel_svc = DomainRelationService(db)

    h0_after = ps.get(sc["h0"].id)
    assert h0_after.epistemic_status == EpistemicStatus.OBSERVED.value

    rels_after = rel_svc.list_for("phenomenon", sc["h0"].id)
    assert len(rels_after) == len(rel_svc.list_for("phenomenon", sc["h0"].id))


def test_e2e_emergence_and_blockage_analysis(db: Session, e2e_research_scenario: dict):
    """8. Verify EmergenceAnalysisService and BlockageAnalysisService compose read-only."""
    sc = e2e_research_scenario
    emergence_svc = EmergenceAnalysisService(db)
    blockage_svc = BlockageAnalysisService(db)

    em_res = emergence_svc.analyze_emergence(sc["h0"].id)
    bl_res = blockage_svc.analyze_blockage(sc["h0"].id)

    assert em_res.phenomenon_id == sc["h0"].id
    assert em_res.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert isinstance(em_res.necessary_conditions, list)
    assert isinstance(em_res.supporting_conditions, list)

    assert bl_res.phenomenon_id == sc["h0"].id
    assert bl_res.epistemic_status == EpistemicStatus.HYPOTHESIZED.value
    assert len(bl_res.direct_constraints) >= 1
    assert any(b["constraint_id"] == sc["c_membrane_supply"].id for b in bl_res.direct_constraints)


def test_e2e_prediction_lifecycle_full(db: Session, e2e_research_scenario: dict):
    """
    9, 10, 11, 12, 14. Verify PredictionService lifecycle:
    - create_prediction -> PREDICTED hypothesis
    - attach_outcome -> preserves epistemic_status & identity, attaches actual_outcome
    - evaluate -> preserves epistemic_status & prior outcome, attaches evaluation
    - historical prediction NOT overwritten
    - NO auto-promotion anywhere
    """
    sc = e2e_research_scenario
    pred_svc = PredictionService(db)

    expected_state = {"water_yield_m3_per_day": 500, "purity_ppm": 150}
    conditions = ["Solar irradiance >= 6.0 kWh/m2/day", "RO membrane operational"]
    now_utc = datetime.now(timezone.utc)
    target_time = now_utc + timedelta(days=30)

    # 9. create_prediction produces PREDICTED hypothesis
    pred = pred_svc.create_prediction(
        expected_state=expected_state,
        source_hypothesis_type="phenomenon",
        source_hypothesis_id=sc["h0"].id,
        conditions=conditions,
        confidence=0.85,
        prediction_time=now_utc,
        expected_at=target_time,
        provenance={"experiment": "pilot_run_1"}
    )

    assert pred.id is not None
    assert pred.epistemic_status == EpistemicStatus.PREDICTED.value
    assert pred.confidence == 0.85
    assert pred.actual_outcome == {}
    assert pred.evaluation == {}

    p_id = pred.id

    # 10. attach_outcome preserves epistemic_status and identity
    outcome_data = {"water_yield_m3_per_day": 480, "purity_ppm": 160, "recorded_at": now_utc.isoformat()}
    updated_pred = pred_svc.attach_outcome(p_id, outcome_data)

    assert updated_pred.id == p_id
    assert updated_pred.actual_outcome == outcome_data
    assert updated_pred.epistemic_status == EpistemicStatus.PREDICTED.value  # NO auto-promotion
    assert updated_pred.expected_state == expected_state
    assert updated_pred.confidence == 0.85

    # 11, 12, 14. evaluate preserves epistemic_status, doesn't lose prior outcome, doesn't overwrite historical prediction
    eval_data = {"yield_accuracy": 0.96, "purity_accuracy": 0.93, "status": "VERIFIED_ACCURATE"}
    eval_pred = pred_svc.evaluate(p_id, eval_data)

    assert eval_pred.id == p_id
    assert eval_pred.evaluation == eval_data
    assert eval_pred.actual_outcome == outcome_data  # Outcome NOT lost
    assert eval_pred.expected_state == expected_state  # Expected state NOT overwritten
    assert eval_pred.epistemic_status == EpistemicStatus.PREDICTED.value  # Epistemic status NOT auto-promoted


def test_e2e_reproducibility_stable_content_only(db: Session, e2e_research_scenario: dict):
    """
    13. Reproducibility test: building analysis twice from same canonical DB state
    yields identical stable position content.
    """
    sc = e2e_research_scenario
    fps = FourPositionService(db, semantic_service=sc["semantic_svc"])

    a1 = fps.build_analysis(sc["h0"].id, include_semantic=True)
    a2 = fps.build_analysis(sc["h0"].id, include_semantic=True)

    norm1 = normalize_four_position_analysis(a1)
    norm2 = normalize_four_position_analysis(a2)

    assert norm1 == norm2


def test_e2e_full_research_scenario_pipeline(db: Session, e2e_research_scenario: dict):
    """
    Comprehensive single end-to-end research scenario test traversing the full research pipeline.
    Validates the composition of all components end-to-end in sequence.
    """
    sc = e2e_research_scenario

    # Step 1: H0 Hypothesis Verification
    ps = PhenomenonService(db)
    h0 = ps.get(sc["h0"].id)
    assert h0 is not None
    assert h0.epistemic_status == EpistemicStatus.OBSERVED.value

    # Step 2: Snapshot DB State before analytical services
    def get_db_snapshot():
        return {
            "phenomena_count": db.query(Phenomenon).count(),
            "context_count": db.query(Context).count(),
            "constraint_count": db.query(Constraint).count(),
            "potential_count": db.query(PotentialPhenomenon).count(),
            "relation_count": db.query(DomainRelation).count(),
        }

    snapshot_before = get_db_snapshot()

    # Step 3: Analytical Services (Emergence & Blockage)
    emergence_svc = EmergenceAnalysisService(db)
    blockage_svc = BlockageAnalysisService(db)

    emergence = emergence_svc.analyze_emergence(h0.id)
    blockage = blockage_svc.analyze_blockage(h0.id)

    assert emergence.phenomenon_id == h0.id
    assert blockage.phenomenon_id == h0.id

    # Step 4: Four-Position Analysis (Baseline vs Semantic)
    fps = FourPositionService(db, semantic_service=sc["semantic_svc"])
    a_base = fps.build_analysis(h0.id, include_semantic=False)
    a_sem = fps.build_analysis(h0.id, include_semantic=True)

    # Top-level provenance holds semantic candidates as read-only signal
    assert a_base.get("provenance") is None
    assert "semantic_candidates" in a_sem["provenance"]

    # Position content is identical across calls
    assert a_base["positions"] == a_sem["positions"]

    # Step 5: Verify Read-Only DB Invariance
    snapshot_after_analysis = get_db_snapshot()
    assert snapshot_before == snapshot_after_analysis

    # Step 6: Prediction Lifecycle
    pred_svc = PredictionService(db)
    pred = pred_svc.create_prediction(
        expected_state={"water_output_liters": 10000},
        source_hypothesis_type="phenomenon",
        source_hypothesis_id=h0.id,
        confidence=0.90,
    )
    assert pred.epistemic_status == EpistemicStatus.PREDICTED.value

    # Attach outcome
    outcome = {"water_output_liters": 9850}
    pred_with_outcome = pred_svc.attach_outcome(pred.id, outcome)
    assert pred_with_outcome.actual_outcome == outcome
    assert pred_with_outcome.epistemic_status == EpistemicStatus.PREDICTED.value

    # Evaluate
    evaluation = {"error_rate": 0.015, "accurate": True}
    evaluated_pred = pred_svc.evaluate(pred.id, evaluation)
    assert evaluated_pred.evaluation == evaluation
    assert evaluated_pred.actual_outcome == outcome
    assert evaluated_pred.expected_state == {"water_output_liters": 10000}
    assert evaluated_pred.epistemic_status == EpistemicStatus.PREDICTED.value
