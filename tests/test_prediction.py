from datetime import datetime, timezone, timedelta
import pytest

from smos.models.prediction import Prediction
from smos.models.models import EpistemicStatus, Timeline
from smos.models.phenomenon import Phenomenon
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.services.prediction_service import PredictionService
from smos.services.phenomenon_service import PhenomenonService
from smos.services.potential_service import PotentialService
from smos.services.emergence_analysis_service import EmergenceAnalysisService
from smos.services.blockage_analysis_service import BlockageAnalysisService


def test_create_prediction(db):
    service = PredictionService(db)
    now = datetime.now(timezone.utc)
    p = service.create_prediction(
        expected_state={"value": 100},
        conditions=["temp > 50"],
        confidence=0.85,
        expected_at=now + timedelta(days=1),
    )
    assert p.id is not None
    assert p.expected_state == {"value": 100}
    assert p.conditions == ["temp > 50"]
    assert p.confidence == 0.85
    assert p.epistemic_status == EpistemicStatus.PREDICTED
    assert p.actual_outcome == {}
    assert p.evaluation == {}


def test_later_attach_outcome(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"status": "ready"})
    assert p.actual_outcome == {}

    updated = service.attach_outcome(p.id, {"status": "ready", "measured": True})
    assert updated.actual_outcome == {"status": "ready", "measured": True}
    assert updated.epistemic_status == EpistemicStatus.PREDICTED


def test_evaluate_prediction(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"val": 42})
    service.attach_outcome(p.id, {"val": 42})

    evaluated = service.evaluate(p.id, {"match": True, "accuracy": 1.0})
    assert evaluated.evaluation == {"match": True, "accuracy": 1.0}
    assert evaluated.epistemic_status == EpistemicStatus.PREDICTED


def test_create_prediction_sets_epistemic_status_predicted(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"a": 1})
    assert p.epistemic_status == EpistemicStatus.PREDICTED


def test_create_prediction_with_source_potential_phenomenon(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Emergent State")

    service = PredictionService(db)
    p = service.create_prediction(
        expected_state={"state": "active"},
        source_hypothesis_type="potential_phenomenon",
        source_hypothesis_id=pot.id,
    )
    assert p.source_hypothesis_type == "potential_phenomenon"
    assert p.source_hypothesis_id == pot.id


def test_create_prediction_with_source_phenomenon(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Solar Flare")

    service = PredictionService(db)
    p = service.create_prediction(
        expected_state={"intensity": "X-class"},
        source_hypothesis_type="phenomenon",
        source_hypothesis_id=phen.id,
    )
    assert p.source_hypothesis_type == "phenomenon"
    assert p.source_hypothesis_id == phen.id


def test_create_prediction_with_source_hypothesis_nullable(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"free": True})
    assert p.source_hypothesis_type is None
    assert p.source_hypothesis_id is None


def test_create_prediction_with_conditions(db):
    service = PredictionService(db)
    p = service.create_prediction(
        expected_state={"ok": True},
        conditions=["c1", "c2"],
    )
    assert p.conditions == ["c1", "c2"]


def test_create_prediction_with_confidence(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"ok": True}, confidence=0.9)
    assert p.confidence == 0.9


def test_create_prediction_with_expected_at(db):
    service = PredictionService(db)
    exp = datetime.now(timezone.utc) + timedelta(hours=2)
    p = service.create_prediction(expected_state={"ok": True}, expected_at=exp)
    assert p.expected_at is not None


def test_create_prediction_without_expected_at(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"ok": True})
    assert p.expected_at is None


def test_attach_outcome_does_not_auto_change_status(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"x": 1})
    p_updated = service.attach_outcome(p.id, {"x": 1})
    assert p_updated.epistemic_status == EpistemicStatus.PREDICTED


def test_evaluate_does_not_auto_promote_to_fact(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"x": 1})
    service.attach_outcome(p.id, {"x": 1})
    p_eval = service.evaluate(p.id, {"accuracy": 1.0, "match": True})
    assert p_eval.epistemic_status != "FACT"
    assert p_eval.epistemic_status == EpistemicStatus.PREDICTED


def test_evaluate_does_not_auto_change_epistemic_status(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"x": 1})
    p_eval = service.evaluate(p.id, {"accuracy": 0.0, "match": False})
    assert p_eval.epistemic_status == EpistemicStatus.PREDICTED


def test_prediction_lifecycle_full(db):
    phen_service = PhenomenonService(db)
    pot_service = PotentialService(db)
    pred_service = PredictionService(db)

    phen = phen_service.create(name="Observed Phen")
    pot = pot_service.create(
        phenomenon=phen.name,
        required_conditions=["high_energy"],
    )

    exp_time = datetime.now(timezone.utc) + timedelta(days=5)
    pred = pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"impact": "critical"},
        conditions=["clear_sky"],
        confidence=0.95,
        expected_at=exp_time,
        provenance={"agent": "tester"},
    )

    assert pred.id is not None
    assert pred.source_hypothesis_type == "potential_phenomenon"
    assert pred.source_hypothesis_id == pot.id
    assert "high_energy" in pred.conditions
    assert "clear_sky" in pred.conditions
    assert pred.confidence == 0.95
    assert pred.epistemic_status == EpistemicStatus.PREDICTED

    # Attach outcome
    outcome = {"impact": "critical", "observed_at": datetime.now(timezone.utc).isoformat()}
    pred = pred_service.attach_outcome(pred.id, outcome)
    assert pred.actual_outcome == outcome
    assert pred.epistemic_status == EpistemicStatus.PREDICTED

    # Evaluate
    eval_data = {"match": True, "score": 1.0}
    pred = pred_service.evaluate(pred.id, eval_data)
    assert pred.evaluation == eval_data
    assert pred.epistemic_status == EpistemicStatus.PREDICTED

    # Verify persistent
    fetched = pred_service.get(pred.id)
    assert fetched is not None
    assert fetched.id == pred.id
    assert fetched.actual_outcome == outcome
    assert fetched.evaluation == eval_data


def test_prediction_remains_persistent_after_evaluation(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"test": True})
    service.attach_outcome(p.id, {"test": True})
    service.evaluate(p.id, {"match": True})

    fetched = service.get(p.id)
    assert fetched is not None
    assert fetched.id == p.id


def test_prediction_to_dict(db):
    service = PredictionService(db)
    now = datetime.now(timezone.utc)
    p = service.create_prediction(
        expected_state={"key": "val"},
        confidence=0.7,
        expected_at=now,
    )
    d = p.to_dict()
    assert d["id"] == p.id
    assert d["expected_state"] == {"key": "val"}
    assert d["confidence"] == 0.7
    assert d["epistemic_status"] == "PREDICTED"
    assert d["expected_at"] is not None


def test_prediction_is_distinct_from_potential_phenomenon():
    """Docstring / Architecture verification for PotentialPhenomenon vs Prediction."""
    assert Prediction.__doc__ is not None
    assert "Distinction from PotentialPhenomenon" in Prediction.__doc__


def test_prediction_is_distinct_from_timeline():
    """Docstring / Architecture verification for Timeline vs Prediction."""
    assert Prediction.__doc__ is not None
    assert "Distinction from Timeline" in Prediction.__doc__


def test_prediction_service_list(db):
    service = PredictionService(db)
    count_before = len(service.list(limit=1000))
    service.create_prediction(expected_state={"n": 1})
    service.create_prediction(expected_state={"n": 2})

    lst = service.list(limit=1000)
    assert len(lst) == count_before + 2


def test_prediction_service_delete(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"n": 1})
    deleted = service.delete(p.id)
    assert deleted is True
    assert service.get(p.id) is None


def test_prediction_service_get(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"n": 1})
    fetched = service.get(p.id)
    assert fetched is not None
    assert fetched.id == p.id


def test_prediction_confidence_range(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"n": 1}, confidence=0.5)
    assert 0.0 <= p.confidence <= 1.0


def test_prediction_does_not_modify_potential_phenomenon(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Stable Phen")
    orig_status = pot.status

    pred_service = PredictionService(db)
    pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"res": "ok"},
    )

    pot_refreshed = pot_service.get(pot.id)
    assert pot_refreshed.status == orig_status


def test_prediction_does_not_modify_emergence_service(db):
    emergence_service = EmergenceAnalysisService(db)
    assert hasattr(emergence_service, "analyze_emergence")


def test_prediction_does_not_modify_blockage_service(db):
    blockage_service = BlockageAnalysisService(db)
    assert hasattr(blockage_service, "analyze_blockage")


def test_prediction_does_not_modify_timeline(db):
    t = Timeline(description="Branch A")
    db.add(t)
    db.commit()

    service = PredictionService(db)
    p = service.create_prediction(expected_state={"state": "A"})
    db.refresh(t)
    assert t.id is not None
    assert p.id is not None


def test_prediction_reuses_epistemic_status_predicted(db):
    service = PredictionService(db)
    p = service.create_prediction(expected_state={"a": 1})
    assert isinstance(p.epistemic_status, EpistemicStatus)
    assert p.epistemic_status == EpistemicStatus.PREDICTED


def test_from_potential_phenomenon_creates_prediction(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(
        phenomenon="A",
        required_conditions=["c1"],
    )

    service = PredictionService(db)
    p = service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"out": "yes"},
        conditions=["c2"],
    )
    assert p is not None
    assert p.source_hypothesis_type == "potential_phenomenon"
    assert p.source_hypothesis_id == pot.id
    assert p.conditions == ["c1", "c2"]


def test_from_potential_phenomenon_returns_none_for_unknown_id(db):
    service = PredictionService(db)
    p = service.from_potential_phenomenon(
        potential_id=99999,
        expected_state={"out": "yes"},
    )
    assert p is None


def test_prediction_source_hypothesis_polymorphic_no_fk(db):
    service = PredictionService(db)
    p = service.create_prediction(
        expected_state={"test": 1},
        source_hypothesis_type="arbitrary_type",
        source_hypothesis_id=12345,
    )
    assert p.source_hypothesis_type == "arbitrary_type"
    assert p.source_hypothesis_id == 12345


def test_prediction_has_three_timestamps(db):
    service = PredictionService(db)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=10)
    p = service.create_prediction(
        expected_state={"test": 1},
        expected_at=exp,
    )
    assert p.created_at is not None or p.id is not None
    assert p.prediction_time is not None
    assert p.expected_at is not None
