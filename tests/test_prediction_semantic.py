import pytest
from smos.models.prediction import Prediction
from smos.models.models import EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.services.prediction_service import PredictionService
from smos.services.phenomenon_service import PhenomenonService
from smos.services.potential_service import PotentialService
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter


def test_prediction_semantic_conditions_returns_candidates(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Heatwave", description="High temperatures")

    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(
        expected_state={"temperature": "extreme"},
        conditions=["high_pressure"],
    )

    # Index both entity types in semantic index
    pred_service.semantic_service.index_canonical("phenomenon", phen.id)
    pred_service.semantic_service.index_canonical("prediction", pred.id)

    candidates = pred_service.semantic_conditions(prediction_id=pred.id)
    assert isinstance(candidates, list)
    matching = [c for c in candidates if c["entity_type"] == "phenomenon" and c["entity_id"] == phen.id]
    assert len(matching) == 1


def test_prediction_semantic_conditions_empty_index_returns_empty(db):
    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"val": 1})

    candidates = pred_service.semantic_conditions(prediction_id=pred.id)
    assert candidates == []


def test_prediction_semantic_conditions_default_entity_types_limited(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Drought")

    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"dry": True})

    pred_service.semantic_service.index_canonical("phenomenon", phen.id)
    pred_service.semantic_service.index_canonical("prediction", pred.id)
    # Index a non-candidate entity type (recipe)
    pred_service.semantic_service.index("recipe", 9999, "Recipe title description")

    candidates = pred_service.semantic_conditions(prediction_id=pred.id)
    entity_types = [c["entity_type"] for c in candidates]
    assert "recipe" not in entity_types
    assert "phenomenon" in entity_types


def test_prediction_semantic_conditions_explicit_entity_types(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Wildfire")

    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"fire": True})

    pred_service.semantic_service.index_canonical("phenomenon", phen.id)
    pred_service.semantic_service.index_canonical("prediction", pred.id)

    candidates = pred_service.semantic_conditions(
        prediction_id=pred.id,
        entity_types=["phenomenon"],
    )
    for c in candidates:
        assert c["entity_type"] == "phenomenon"
    matching = [c for c in candidates if c["entity_id"] == phen.id]
    assert len(matching) == 1


def test_prediction_semantic_search_conditions(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Flood", description="Heavy rainfall causing overflow")

    pred_service = PredictionService(db)
    pred_service.semantic_service.index_canonical("phenomenon", phen.id)

    results = pred_service.semantic_search_conditions(query="Heavy rainfall overflow")
    matching = [r for r in results if r["entity_type"] == "phenomenon" and r["entity_id"] == phen.id]
    assert len(matching) == 1


def test_prediction_semantic_search_conditions_filter(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Storm")

    pred_service = PredictionService(db)
    pred_service.semantic_service.index_canonical("phenomenon", phen.id)

    results = pred_service.semantic_search_conditions(
        query="Storm",
        entity_types=["context"],
    )
    assert results == []


def test_create_prediction_signature_unchanged(db):
    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(
        expected_state={"a": 1},
        source_hypothesis_type="phenomenon",
        source_hypothesis_id=10,
        conditions=["c1"],
        confidence=0.8,
        provenance={"creator": "user"},
    )
    assert pred.id is not None
    assert pred.expected_state == {"a": 1}
    assert pred.conditions == ["c1"]
    assert pred.confidence == 0.8
    assert pred.provenance == {"creator": "user"}


def test_from_potential_phenomenon_without_semantic_conditions(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Solar Flare Potential")

    pred_service = PredictionService(db)
    pred = pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"impact": "moderate"},
        include_semantic_conditions=False,
    )
    assert pred is not None
    assert "semantic_candidates" not in pred.provenance


def test_from_potential_phenomenon_with_semantic_conditions(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Geomagnetic Storm", required_conditions=["high_activity"])

    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Aurora Borealis", description="Polar atmospheric display")

    pred_service = PredictionService(db)
    pred_service.semantic_service.index_canonical("phenomenon", phen.id)

    pred = pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"aurora": True},
        include_semantic_conditions=True,
    )

    assert pred is not None
    assert "semantic_candidates" in pred.provenance
    assert isinstance(pred.provenance["semantic_candidates"], list)
    assert pred.conditions == ["high_activity"]


def test_from_potential_phenomenon_preserves_existing_provenance_semantic_candidates(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Supernova")

    pred_service = PredictionService(db)
    existing_candidates = [{"entity_type": "phenomenon", "entity_id": 999, "similarity": 0.99}]

    pred = pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"radiation": "high"},
        provenance={"semantic_candidates": existing_candidates},
        include_semantic_conditions=True,
    )

    assert pred is not None
    assert pred.provenance["semantic_candidates"] == existing_candidates


def test_from_potential_phenomenon_conditions_field_unchanged(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Volcanic Eruption", required_conditions=["magma_buildup"])

    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Ash Cloud")

    pred_service = PredictionService(db)
    pred_service.semantic_service.index_canonical("phenomenon", phen.id)

    pred = pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"eruption": True},
        conditions=["seismic_tremors"],
        include_semantic_conditions=True,
    )

    assert pred.conditions == ["magma_buildup", "seismic_tremors"]


def test_from_potential_phenomenon_does_not_auto_index_prediction(db):
    pot_service = PotentialService(db)
    pot = pot_service.create(phenomenon="Landslide")

    pred_service = PredictionService(db)
    pred = pred_service.from_potential_phenomenon(
        potential_id=pot.id,
        expected_state={"slide": True},
        include_semantic_conditions=True,
    )

    # Check that prediction is not auto-indexed
    candidates = pred_service.semantic_conditions(prediction_id=pred.id)
    assert candidates == []


def test_semantic_conditions_read_only(db):
    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"test": 1})

    count_before = len(pred_service.list(limit=100))
    _ = pred_service.semantic_conditions(prediction_id=pred.id)
    count_after = len(pred_service.list(limit=100))

    assert count_before == count_after


def test_semantic_conditions_do_not_create_domain_relation(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Tsunami")

    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"wave": "large"})

    pred_service.semantic_service.index_canonical("phenomenon", phen.id)
    pred_service.semantic_service.index_canonical("prediction", pred.id)

    relations_before = db.query(DomainRelation).count()
    _ = pred_service.semantic_conditions(prediction_id=pred.id)
    relations_after = db.query(DomainRelation).count()

    assert relations_before == relations_after == 0


def test_semantic_conditions_do_not_modify_prediction(db):
    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(
        expected_state={"value": 50},
        conditions=["initial_cond"],
        confidence=0.7,
    )

    pred_service.semantic_service.index_canonical("prediction", pred.id)
    _ = pred_service.semantic_conditions(prediction_id=pred.id)

    fetched = pred_service.get(pred.id)
    assert fetched.expected_state == {"value": 50}
    assert fetched.conditions == ["initial_cond"]
    assert fetched.confidence == 0.7


def test_semantic_conditions_do_not_promote_epistemic_status(db):
    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"status": "pending"})

    pred_service.semantic_service.index_canonical("prediction", pred.id)
    _ = pred_service.semantic_conditions(prediction_id=pred.id)

    fetched = pred_service.get(pred.id)
    assert fetched.epistemic_status == EpistemicStatus.PREDICTED


def test_semantic_conditions_are_signal_not_evidence(db):
    phen_service = PhenomenonService(db)
    phen = phen_service.create(name="Earthquake")

    pred_service = PredictionService(db)
    pred = pred_service.create_prediction(expected_state={"magnitude": 7.0})

    pred_service.semantic_service.index_canonical("phenomenon", phen.id)
    pred_service.semantic_service.index_canonical("prediction", pred.id)

    candidates = pred_service.semantic_conditions(prediction_id=pred.id)
    assert isinstance(candidates, list)
    # The output is list of candidate dicts with similarity scores, not evidence objects
    for cand in candidates:
        assert "entity_type" in cand
        assert "entity_id" in cand
        assert "similarity" in cand
        assert "model_name" in cand


def test_semantic_service_injectable(db):
    custom_adapter = HashFallbackAdapter(dimension=128, model_name="custom-hash-128")
    custom_semantic_svc = SemanticSearchService(db, custom_adapter)

    pred_service = PredictionService(db, semantic_service=custom_semantic_svc)
    assert pred_service.semantic_service is custom_semantic_svc
    assert pred_service.semantic_service.adapter.model_name == "custom-hash-128"
