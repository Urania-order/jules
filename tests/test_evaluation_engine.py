"""Engine unit tests for EvaluationEngine (TASK L-05A)."""

from datetime import datetime, timedelta, timezone

import pytest

from smos.models.evaluation import EvaluationRecord, EvaluationStatus
from smos.models.models import EpistemicStatus
from smos.models.observation import Observation
from smos.models.phenomenon import Phenomenon
from smos.models.prediction import Prediction
from smos.services.evaluation_engine import EvaluationEngine
from smos.services.observation_service import ObservationService
from smos.services.prediction_service import PredictionService


@pytest.fixture
def obs_service(db):
    return ObservationService(db)


@pytest.fixture
def pred_service(db):
    return PredictionService(db)


@pytest.fixture
def eval_engine(db):
    return EvaluationEngine(db)


def test_evaluate_missing_target(eval_engine):
    res = eval_engine.evaluate({"target_type": "prediction", "target_id": 9999})
    assert res["status"] == "UNDETERMINED"
    assert "not found" in res["rationale"]


def test_evaluate_prediction_confirmed(db, eval_engine, obs_service):
    pred = Prediction(
        expected_state={"pressure": 100.0},
        epistemic_status=EpistemicStatus.PREDICTED,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    obs_service.ingest({
        "metric_name": "pressure",
        "metric_value": 100.0,
        "prediction_refs": [pred.id],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    })

    res = eval_engine.evaluate({"target_type": "prediction", "target_id": pred.id})
    assert res["status"] == "CONFIRMED"
    assert len(res["observation_refs"]) == 1
    assert pred.epistemic_status == EpistemicStatus.PREDICTED  # INVARIANT: no epistemic mutation


def test_evaluate_prediction_refuted(db, eval_engine, obs_service):
    pred = Prediction(
        expected_state={"pressure": 100.0},
        epistemic_status=EpistemicStatus.PREDICTED,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    obs_service.ingest({
        "metric_name": "pressure",
        "metric_value": 50.0,  # contradicts 100.0
        "prediction_refs": [pred.id],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    })

    res = eval_engine.evaluate({
        "target_type": "prediction",
        "target_id": pred.id,
        "criteria": {"specs": [{"metric_name": "pressure", "expected_value": 100.0, "tolerance": 1.0}]},
    })
    assert res["status"] == "REFUTED"
    assert pred.epistemic_status == EpistemicStatus.PREDICTED  # INVARIANT preserved


def test_evaluate_prediction_inconclusive_conflicting_obs(db, eval_engine, obs_service):
    pred = Prediction(
        expected_state={"temp": 20.0},
        epistemic_status=EpistemicStatus.PREDICTED,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    obs_service.ingest({
        "metric_name": "temp",
        "metric_value": 20.0,  # supports
        "prediction_refs": [pred.id],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    })
    obs_service.ingest({
        "metric_name": "temp",
        "metric_value": 40.0,  # refutes
        "prediction_refs": [pred.id],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    })

    res = eval_engine.evaluate({"target_type": "prediction", "target_id": pred.id})
    assert res["status"] == "INCONCLUSIVE"
    assert any("Conflicting observations" in note for note in res["uncertainty_notes"])


def test_evaluate_temporal_cutoff_excludes_later_observations(db, eval_engine, obs_service):
    pred = Prediction(
        expected_state={"flow": 10.0},
        epistemic_status=EpistemicStatus.PREDICTED,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)

    # Old observation (before cutoff)
    obs1 = obs_service.ingest({
        "metric_name": "flow",
        "metric_value": 10.0,
        "prediction_refs": [pred.id],
        "observed_at": (cutoff - timedelta(minutes=10)).isoformat(),
    })

    # New observation (after cutoff)
    obs2 = obs_service.ingest({
        "metric_name": "flow",
        "metric_value": 999.0,  # refuted if considered
        "prediction_refs": [pred.id],
        "observed_at": (cutoff + timedelta(minutes=10)).isoformat(),
    })

    res = eval_engine.evaluate({
        "target_type": "prediction",
        "target_id": pred.id,
        "as_of": cutoff.isoformat(),
    })

    assert res["status"] == "CONFIRMED"
    assert res["observation_refs"] == [obs1.id]
    assert obs2.id in res["excluded_observation_refs"]


def test_append_only_evaluation_records(db, eval_engine, obs_service):
    pred = Prediction(expected_state={"a": 1.0})
    db.add(pred)
    db.commit()
    db.refresh(pred)

    res1 = eval_engine.evaluate({"target_type": "prediction", "target_id": pred.id})
    res2 = eval_engine.evaluate({"target_type": "prediction", "target_id": pred.id})

    assert res1["id"] != res2["id"]

    records = eval_engine.list_evaluations(target_type="prediction", target_id=pred.id)
    assert len(records) == 2


def test_evaluate_phenomenon_target(db, eval_engine, obs_service):
    phen = Phenomenon(name="Solar Flare", epistemic_status=EpistemicStatus.OBSERVED)
    db.add(phen)
    db.commit()
    db.refresh(phen)

    obs_service.ingest({
        "metric_name": "radiation",
        "metric_value": 500.0,
        "phenomenon_refs": [phen.id],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    })

    res = eval_engine.evaluate({
        "target_type": "phenomenon",
        "target_id": phen.id,
        "criteria": {"specs": [{"metric_name": "radiation", "min": 100.0}]},
    })

    assert res["status"] == "CONFIRMED"
    assert phen.epistemic_status == EpistemicStatus.OBSERVED
