"""Tests for Temporal Replay Engine (TASK L-05B)."""

from datetime import datetime, timezone, timedelta
import pytest

from smos.models.observation import Observation
from smos.models.experiment_run import ExperimentRun
from smos.models.evaluation import EvaluationRecord, EvaluationStatus
from smos.models.prediction import Prediction
from smos.models.discovery import Hypothesis
from smos.models.phenomenon import Phenomenon
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.models.domain_relation import DomainRelation
from smos.models.models import EpistemicStatus, RelationType
from smos.models.ecology import ProvenanceRecord
from smos.services.temporal_replay_engine import TemporalReplayEngine


def test_replay_empty_database(db):
    engine = TemporalReplayEngine(db)
    as_of = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = engine.replay({"as_of": as_of.isoformat()})

    assert res["completeness"] == "COMPLETE"
    assert res["reconstructed_state"]["observations"] == []
    assert res["reconstructed_state"]["experiment_runs"] == []
    assert res["reconstruction_diagnostics"]["versioning_gap"]["impact"] is not None


def test_knowledge_time_vs_event_time_filtering(db):
    engine = TemporalReplayEngine(db)

    # Cutoff: Monday Oct 12
    t_monday = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    t_tuesday = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
    t_wednesday = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)

    # Obs 1: Occurred Monday, created/ingested Monday -> Available Monday
    obs1 = Observation(
        metric_name="temp",
        metric_value=25.0,
        observed_at=t_monday,
        created_at=t_monday,
    )

    # Obs 2: Occurred Monday, created/ingested Wednesday -> NOT available Monday or Tuesday!
    obs2 = Observation(
        metric_name="pressure",
        metric_value=101.3,
        observed_at=t_monday,
        created_at=t_wednesday,
    )

    db.add_all([obs1, obs2])
    db.commit()

    # Replay as of Tuesday
    res_tuesday = engine.replay({"as_of": t_tuesday.isoformat()})
    reconstructed_obs = res_tuesday["reconstructed_state"]["observations"]

    assert len(reconstructed_obs) == 1
    assert reconstructed_obs[0]["id"] == obs1.id
    assert res_tuesday["reconstruction_diagnostics"]["excluded_counts"]["observation"] == 1


def test_experiment_run_status_reconstruction_from_history(db):
    engine = TemporalReplayEngine(db)

    t1_proposed = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    t2_approved = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t3_completed = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)

    exp = ExperimentRun(
        tool_blueprint_id="sensor_read_v1",
        status="COMPLETED",
        created_at=t1_proposed,
        status_history=[
            {"status": "PROPOSED", "at": t1_proposed.isoformat()},
            {"status": "APPROVED", "at": t2_approved.isoformat()},
            {"status": "COMPLETED", "at": t3_completed.isoformat()},
        ],
    )
    db.add(exp)
    db.commit()

    # Replay at t2_approved + 1 hour (Oct 11 11:00) -> Status MUST be APPROVED, not COMPLETED!
    as_of_mid = datetime(2026, 10, 11, 11, 0, 0, tzinfo=timezone.utc)
    res = engine.replay({"as_of": as_of_mid.isoformat()})

    reconstructed_exps = res["reconstructed_state"]["experiment_runs"]
    assert len(reconstructed_exps) == 1
    assert reconstructed_exps[0]["status_at_as_of"] == "APPROVED"
    assert reconstructed_exps[0]["fidelity"] == "VERIFIED"


def test_domain_relation_and_provenance_time_filtering(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
    as_of = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    rel_early = DomainRelation(
        source_type="phenomenon",
        source_id=1,
        target_type="phenomenon",
        target_id=2,
        relation_type=RelationType.SUPPORTS,
        created_at=t_early,
    )
    rel_late = DomainRelation(
        source_type="phenomenon",
        source_id=1,
        target_type="phenomenon",
        target_id=3,
        relation_type=RelationType.BLOCKS,
        created_at=t_late,
    )

    prov_early = ProvenanceRecord(node_id=1, created_at=t_early)
    prov_late = ProvenanceRecord(node_id=2, created_at=t_late)

    db.add_all([rel_early, rel_late, prov_early, prov_late])
    db.commit()

    res = engine.replay({"as_of": as_of.isoformat()})

    reconstructed_rels = res["reconstructed_state"]["domain_relations"]
    reconstructed_provs = res["reconstructed_state"]["provenance_records"]

    assert len(reconstructed_rels) == 1
    assert reconstructed_rels[0]["id"] == rel_early.id

    assert len(reconstructed_provs) == 1
    assert reconstructed_provs[0]["id"] == prov_early.id


def test_versioning_gap_reporting_and_fidelity_classification(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    as_of = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    phen = Phenomenon(name="Air Flow Pattern", created_at=t_early)
    pred = Prediction(epistemic_status=EpistemicStatus.PREDICTED, created_at=t_early)

    db.add_all([phen, pred])
    db.commit()

    res = engine.replay({"as_of": as_of.isoformat()})

    phens = res["reconstructed_state"]["phenomenon"]
    preds = res["reconstructed_state"]["predictions"]

    assert len(phens) == 1
    assert phens[0]["fidelity"] == "PARTIAL"

    assert len(preds) == 1
    assert preds[0]["fidelity"] == "PARTIAL"

    gap = res["reconstruction_diagnostics"]["versioning_gap"]
    assert "prediction" in gap["entities"]
    assert "phenomenon" in gap["entities"]


def test_replay_read_only_invariant(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    obs = Observation(metric_name="temp", metric_value=10.0, observed_at=t_early, created_at=t_early)
    db.add(obs)
    db.commit()

    initial_obs_count = db.query(Observation).count()
    initial_exp_count = db.query(ExperimentRun).count()

    engine.replay({"as_of": t_early.isoformat()})

    assert db.query(Observation).count() == initial_obs_count
    assert db.query(ExperimentRun).count() == initial_exp_count
