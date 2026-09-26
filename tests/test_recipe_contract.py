import inspect
import smos.models
import smos.models.experience
from smos.models.recipe_contract import (
    SOURCE_EXPOSURE_IDS,
    SOURCE_PREDICTION_IDS,
    SOURCE_EVENT_IDS,
    KNOWLEDGE_IDS,
    EVALUATION_SUMMARY,
    CREATED_AT,
    LEARNING_EVIDENCE_SCHEMA_DOC,
    LEARNING_LOOP_DOC,
    normalize_learning_evidence,
    validate_learning_evidence,
    get_sources,
)


def test_knowledge_ids_means_memory_node_ids():
    assert KNOWLEDGE_IDS == "knowledge_ids"
    assert "MemoryNode.id" in LEARNING_EVIDENCE_SCHEMA_DOC
    assert "MemoryNode.id" in smos.models.recipe_contract.__doc__


def test_source_exposure_ids_means_context_exposure_ids():
    assert SOURCE_EXPOSURE_IDS == "source_exposure_ids"
    assert "ContextExposure.id" in LEARNING_EVIDENCE_SCHEMA_DOC
    assert "ContextExposure.id" in smos.models.recipe_contract.__doc__


def test_source_prediction_ids_means_prediction_ids():
    assert SOURCE_PREDICTION_IDS == "source_prediction_ids"
    assert "Prediction.id" in LEARNING_EVIDENCE_SCHEMA_DOC
    assert "Prediction.id" in smos.models.recipe_contract.__doc__


def test_source_event_ids_means_domain_event_ids():
    assert SOURCE_EVENT_IDS == "source_event_ids"
    assert "DomainEvent.id" in LEARNING_EVIDENCE_SCHEMA_DOC
    assert "DomainEvent.id" in smos.models.recipe_contract.__doc__


def test_normalize_learning_evidence_none_returns_defaults():
    norm = normalize_learning_evidence(None)
    assert norm[SOURCE_EXPOSURE_IDS] == []
    assert norm[SOURCE_PREDICTION_IDS] == []
    assert norm[SOURCE_EVENT_IDS] == []
    assert norm[KNOWLEDGE_IDS] == []
    assert norm[EVALUATION_SUMMARY] == {}
    assert norm[CREATED_AT] is None


def test_normalize_learning_evidence_preserves_lists():
    raw = {
        SOURCE_EXPOSURE_IDS: [1, 2],
        SOURCE_PREDICTION_IDS: [3],
        SOURCE_EVENT_IDS: [4, 5],
        KNOWLEDGE_IDS: [6],
    }
    norm = normalize_learning_evidence(raw)
    assert norm[SOURCE_EXPOSURE_IDS] == [1, 2]
    assert norm[SOURCE_PREDICTION_IDS] == [3]
    assert norm[SOURCE_EVENT_IDS] == [4, 5]
    assert norm[KNOWLEDGE_IDS] == [6]


def test_normalize_learning_evidence_preserves_evaluation_summary():
    raw = {EVALUATION_SUMMARY: {"accuracy": 0.95, "notes": "high performance"}}
    norm = normalize_learning_evidence(raw)
    assert norm[EVALUATION_SUMMARY] == {"accuracy": 0.95, "notes": "high performance"}


def test_validate_learning_evidence_accepts_valid():
    raw = {
        SOURCE_EXPOSURE_IDS: [10],
        SOURCE_PREDICTION_IDS: [20],
        SOURCE_EVENT_IDS: [30],
        KNOWLEDGE_IDS: [40],
        EVALUATION_SUMMARY: {"score": 1},
        CREATED_AT: "2026-09-26T22:43:06Z",
    }
    is_valid, errors = validate_learning_evidence(raw)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_learning_evidence_rejects_non_list_ids():
    raw = {SOURCE_EXPOSURE_IDS: "not_a_list"}
    is_valid, errors = validate_learning_evidence(raw)
    assert is_valid is False
    assert any("must be a list of integers" in e for e in errors)


def test_validate_learning_evidence_rejects_non_int_ids():
    raw = {SOURCE_PREDICTION_IDS: [1, "two", 3]}
    is_valid, errors = validate_learning_evidence(raw)
    assert is_valid is False
    assert any("contains non-integer element" in e for e in errors)

    raw_bool = {KNOWLEDGE_IDS: [True]}
    is_valid_bool, errors_bool = validate_learning_evidence(raw_bool)
    assert is_valid_bool is False
    assert any("contains non-integer element" in e for e in errors_bool)


def test_validate_learning_evidence_rejects_non_dict_evaluation():
    raw = {EVALUATION_SUMMARY: "not_a_dict"}
    is_valid, errors = validate_learning_evidence(raw)
    assert is_valid is False
    assert any("must be a dict" in e for e in errors)


def test_validate_learning_evidence_accepts_empty():
    is_valid, errors = validate_learning_evidence({})
    assert is_valid is True
    assert len(errors) == 0


def test_get_sources_returns_typed_lists():
    raw = {
        SOURCE_EXPOSURE_IDS: [1],
        SOURCE_PREDICTION_IDS: [2, 3],
        SOURCE_EVENT_IDS: [],
        KNOWLEDGE_IDS: [4],
    }
    sources = get_sources(raw)
    assert sources[SOURCE_EXPOSURE_IDS] == [1]
    assert sources[SOURCE_PREDICTION_IDS] == [2, 3]
    assert sources[SOURCE_EVENT_IDS] == []
    assert sources[KNOWLEDGE_IDS] == [4]


def test_learning_evidence_no_conclusion_model_exists():
    # Assert no class named 'Conclusion' in smos.models
    assert not hasattr(smos.models, "Conclusion")


def test_learning_evidence_no_new_recipe_model():
    # Ensure Recipe is the only recipe class in experience module
    classes = [
        obj for name, obj in inspect.getmembers(smos.models.experience, inspect.isclass)
        if obj.__module__ == "smos.models.experience"
    ]
    recipe_classes = [c for c in classes if "Recipe" in c.__name__ and c.__name__ != "AntiRecipe"]
    # Recipe, RecipeExecution
    class_names = [c.__name__ for c in recipe_classes]
    assert "Recipe" in class_names
    assert "LearningRecipe" not in class_names
    assert "RecipeV2" not in class_names
    assert "AnalyticalRecipe" not in class_names


def test_prediction_evaluation_distinct_from_recipe_success_rate():
    # Prediction.evaluation is per-prediction, Recipe.success_rate is aggregate/procedural
    assert "Recipe != Learning Loop" in LEARNING_LOOP_DOC
    assert hasattr(smos.models.Prediction, "evaluation")
    assert hasattr(smos.models.experience.Recipe, "success_rate")


def test_knowledge_lifecycle_state_is_memory_node_only():
    from smos.models.models import MemoryNode, KnowledgeLifecycleState
    # KnowledgeLifecycleState is lifecycle_state on MemoryNode
    assert hasattr(MemoryNode, "lifecycle_state")
    assert getattr(MemoryNode.lifecycle_state.property.columns[0].type, "enum_class", None) == KnowledgeLifecycleState
    assert not hasattr(smos.models.experience.Recipe, "lifecycle_state")


def test_recipe_evolution_uses_evolution_service():
    from smos.services.evolution_service import EvolutionService
    assert hasattr(EvolutionService, "evolve_recipe")


def test_hidden_context_not_in_learning_evidence():
    contract_constants = [
        SOURCE_EXPOSURE_IDS,
        SOURCE_PREDICTION_IDS,
        SOURCE_EVENT_IDS,
        KNOWLEDGE_IDS,
        EVALUATION_SUMMARY,
        CREATED_AT,
    ]
    assert "hidden_context_ids" not in contract_constants


def test_recipe_model_unchanged_in_this_task():
    recipe_fields = [c.name for c in smos.models.experience.Recipe.__table__.columns]
    forbidden_fields = [
        "based_on_predictions",
        "based_on_conclusions",
        "based_on_events",
        "knowledge_ids",
        "evaluation",
    ]
    for field in forbidden_fields:
        assert field not in recipe_fields
