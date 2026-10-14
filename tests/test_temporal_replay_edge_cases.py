"""Additional comprehensive edge case tests for Replay Contract and Temporal Replay Engine (TASK L-05B)."""

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
from smos.models.models import EpistemicStatus, RelationType, Relation
from smos.models.replay_contract import validate_replay_request, validate_replay_result
from smos.services.temporal_replay_engine import TemporalReplayEngine


def test_validate_replay_result_structure():
    invalid_res = {"as_of": "2026-10-14T12:00:00Z", "completeness": "INVALID"}
    valid, errors = validate_replay_result(invalid_res)
    assert valid is False
    assert any("completeness" in e for e in errors)
    assert any("reconstructed_state" in e for e in errors)
    assert any("content_hash" in e for e in errors)


def test_replay_with_scope_filtering(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    obs = Observation(metric_name="temp", metric_value=20.0, observed_at=t_early, created_at=t_early)
    exp = ExperimentRun(tool_blueprint_id="bp1", status="PROPOSED", created_at=t_early)

    db.add_all([obs, exp])
    db.commit()

    # Replay only observation scope
    res = engine.replay({"as_of": t_early.isoformat(), "scope": ["observation"]})

    assert len(res["reconstructed_state"]["observations"]) == 1
    assert len(res["reconstructed_state"]["experiment_runs"]) == 0


def test_experiment_run_missing_status_history_handling(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    exp_no_hist = ExperimentRun(
        tool_blueprint_id="bp1",
        status="EXECUTED",
        created_at=t_early,
        status_history=[],  # Missing/empty history
    )
    db.add(exp_no_hist)
    db.commit()

    res = engine.replay({"as_of": t_early.isoformat()})

    reconstructed_exps = res["reconstructed_state"]["experiment_runs"]
    assert len(reconstructed_exps) == 1
    assert reconstructed_exps[0]["status_at_as_of"] == "UNKNOWN"
    assert reconstructed_exps[0]["fidelity"] == "UNKNOWN"
    assert res["completeness"] == "PARTIAL"
    assert len(res["reconstruction_diagnostics"]["missing_status_history"]) == 1


def test_evaluation_records_time_filtering(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
    as_of = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    eval_early = EvaluationRecord(
        target_type="prediction",
        target_id=1,
        status=EvaluationStatus.CONFIRMED,
        criteria_id="crit_1",
        evaluated_at=t_early,
    )
    eval_late = EvaluationRecord(
        target_type="prediction",
        target_id=2,
        status=EvaluationStatus.REFUTED,
        criteria_id="crit_1",
        evaluated_at=t_late,
    )

    db.add_all([eval_early, eval_late])
    db.commit()

    res = engine.replay({"as_of": as_of.isoformat()})

    reconstructed_evals = res["reconstructed_state"]["evaluations"]
    assert len(reconstructed_evals) == 1
    assert reconstructed_evals[0]["id"] == eval_early.id
    assert res["reconstruction_diagnostics"]["excluded_counts"]["evaluation"] == 1


def test_relation_models_time_filtering(db):
    engine = TemporalReplayEngine(db)

    t_early = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    as_of = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    rel_models = Relation(
        from_node_id=1,
        to_node_id=2,
        type=RelationType.CAUSES,
        provenance={"created_at": t_early.isoformat()},
    )
    db.add(rel_models)
    db.commit()

    res = engine.replay({"as_of": as_of.isoformat()})

    reconstructed_rels = res["reconstructed_state"]["relations"]
    assert len(reconstructed_rels) == 1
    assert reconstructed_rels[0]["id"] == rel_models.id
