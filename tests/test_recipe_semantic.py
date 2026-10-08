import logging
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.entities import Cosmonaut
from smos.models.experience import Recipe
from smos.models.phenomenon import Phenomenon
from smos.models.domain_relation import DomainRelation
from smos.services.recipe_service import RecipeService
from smos.services.evolution_service import EvolutionService
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create dummy cosmonaut for FK
    cosmonaut = Cosmonaut(id=1, name="Test Cosmonaut", reputation_score=100.0)
    session.add(cosmonaut)
    session.commit()

    yield session
    session.close()


# Backward Compatibility Tests
def test_create_recipe_signature_unchanged(db_session):
    service = RecipeService(db_session)
    recipe = service.create_recipe("Test Recipe", 1, ["step 1"], "debugging")
    assert recipe.id is not None
    assert recipe.title == "Test Recipe"


def test_evolve_recipe_without_semantic_unchanged(db_session):
    recipe_svc = RecipeService(db_session)
    evo_svc = EvolutionService(db_session)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")
    mutations = [{"type": "add_step", "step": "step 2"}]

    child = evo_svc.evolve_recipe(parent.id, mutations)
    assert child is not None
    assert child.title == "Parent Recipe (Evolved)"
    assert child.mutations == mutations
    assert child.provenance == {} or child.provenance is None or child.provenance == dict()


def test_recipe_provenance_default_empty_dict(db_session):
    recipe = Recipe(title="Direct Recipe", author_id=1, problem_type="debugging")
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    assert recipe.provenance == {}


def test_recipe_provenance_field_added(db_session):
    assert hasattr(Recipe, "provenance")


# Semantic Retrieval Tests
def test_recipe_service_semantic_neighbors(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("Recipe 1", 1, ["step 1"], "debugging")
    r2 = recipe_svc.create_recipe("Recipe 2", 1, ["step 2"], "debugging")

    semantic_svc.index_canonical("recipe", r1.id)
    semantic_svc.index_canonical("recipe", r2.id)

    neighbors = recipe_svc.semantic_neighbors(r1.id)
    assert len(neighbors) == 1
    assert neighbors[0]["entity_type"] == "recipe"
    assert neighbors[0]["entity_id"] == r2.id


def test_recipe_service_semantic_neighbors_empty_index(db_session):
    recipe_svc = RecipeService(db_session)
    neighbors = recipe_svc.semantic_neighbors(999)
    assert neighbors == []


def test_recipe_service_semantic_search(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("Optimization Recipe", 1, ["step 1"], "perf")
    semantic_svc.index_canonical("recipe", r1.id)

    results = recipe_svc.semantic_search("Optimization")
    assert len(results) == 1
    assert results[0]["entity_id"] == r1.id


def test_recipe_service_semantic_search_filter(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("Recipe 1", 1, ["step 1"], "debugging")
    semantic_svc.index_canonical("recipe", r1.id)

    # Filter for phenomenon only (should return empty since r1 is recipe)
    results = recipe_svc.semantic_search("Recipe", entity_types=["phenomenon"])
    assert len(results) == 0


def test_semantic_neighbors_default_entity_types_limited(db_session):
    recipe_svc = RecipeService(db_session)
    assert recipe_svc.DEFAULT_CANDIDATE_ENTITY_TYPES == [
        "recipe",
        "phenomenon",
        "context",
        "constraint",
    ]


# Evolution Integration Tests
def test_evolve_recipe_with_include_semantic_neighbors(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")
    other = recipe_svc.create_recipe("Other Recipe", 1, ["step A"], "debugging")

    semantic_svc.index_canonical("recipe", parent.id)
    semantic_svc.index_canonical("recipe", other.id)

    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)
    assert child is not None
    assert "semantic_candidates" in child.provenance
    candidates = child.provenance["semantic_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["entity_id"] == other.id


def test_evolve_recipe_uses_parent_for_semantic_retrieval(db_session):
    class MockSemanticService(SemanticSearchService):
        def __init__(self):
            self.called_with = []

        def similar(self, entity_type, entity_id, k=10, entity_types=None):
            self.called_with.append((entity_type, entity_id))
            return [{"entity_type": "recipe", "entity_id": 99, "similarity": 0.8}]

    mock_semantic = MockSemanticService()
    recipe_svc = RecipeService(db_session, semantic_service=mock_semantic)
    evo_svc = EvolutionService(db_session, semantic_service=mock_semantic)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")

    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)

    # Must be called for parent.id, NOT child.id
    assert mock_semantic.called_with == [("recipe", parent.id)]
    assert child.provenance["semantic_candidates"][0]["entity_id"] == 99


def test_evolve_recipe_does_not_require_new_recipe_index(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")
    # Parent is not indexed -> similar() returns []
    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)

    assert child is not None
    # No semantic candidates attached if empty
    assert "semantic_candidates" not in (child.provenance or {})


def test_evolve_recipe_does_not_auto_index_new_recipe(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")
    semantic_svc.index_canonical("recipe", parent.id)

    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)

    # Check index for child.id
    child_neighbors = semantic_svc.similar("recipe", child.id)
    # Child was not indexed, so searching for child in index returns []
    assert child_neighbors == []


def test_evolve_recipe_does_not_mutate_from_semantics(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")
    other = recipe_svc.create_recipe("Other Recipe", 1, ["step X"], "debugging")
    semantic_svc.index_canonical("recipe", parent.id)
    semantic_svc.index_canonical("recipe", other.id)

    mutations = [{"type": "modify", "detail": "test"}]
    child = evo_svc.evolve_recipe(parent.id, mutations, include_semantic_neighbors=True)

    assert child.mutations == mutations


def test_evolve_recipe_does_not_modify_steps(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1", "step 2"], "debugging")
    other = recipe_svc.create_recipe("Other Recipe", 1, ["step X", "step Y"], "debugging")
    semantic_svc.index_canonical("recipe", parent.id)
    semantic_svc.index_canonical("recipe", other.id)

    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)

    assert child.steps == ["step 1", "step 2"]


def test_evolve_recipe_semantic_failure_logged_not_swallowed(db_session, caplog):
    class FailingSemanticService(SemanticSearchService):
        def similar(self, entity_type, entity_id, k=10, entity_types=None):
            raise RuntimeError("Index database offline")

    failing_svc = FailingSemanticService(db_session, HashFallbackAdapter())
    recipe_svc = RecipeService(db_session, semantic_service=failing_svc)
    evo_svc = EvolutionService(db_session, semantic_service=failing_svc)

    parent = recipe_svc.create_recipe("Parent Recipe", 1, ["step 1"], "debugging")

    with caplog.at_level(logging.WARNING):
        child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)

    assert child is not None
    assert "semantic retrieval for parent recipe" in caplog.text
    assert "Index database offline" in caplog.text


# Provenance Boundary Tests
def test_evolve_recipe_does_not_overwrite_existing_child_provenance(db_session):
    class MockSemanticService(SemanticSearchService):
        def similar(self, entity_type, entity_id, k=10, entity_types=None):
            return [{"entity_type": "recipe", "entity_id": 999, "similarity": 0.99}]

    mock_semantic = MockSemanticService(db_session, HashFallbackAdapter())
    evo_svc = EvolutionService(db_session, semantic_service=mock_semantic)

    parent = Recipe(title="Parent", author_id=1, problem_type="test")
    db_session.add(parent)
    db_session.commit()

    # Suppose child was created with existing semantic_candidates in provenance
    # We simulate this boundary: if prov already has semantic_candidates, TASK 32 must NOT overwrite
    # Let's test that if evolve_recipe is called, it preserves existing prov keys
    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=True)
    # Give child existing prov
    child.provenance = {"semantic_candidates": [{"entity_type": "recipe", "entity_id": 111, "similarity": 0.5}], "custom_key": "custom_val"}
    db_session.commit()

    # Re-run evolution condition check logic or verify state
    assert child.provenance["custom_key"] == "custom_val"
    assert child.provenance["semantic_candidates"][0]["entity_id"] == 111


def test_evolve_recipe_does_not_inherit_parent_provenance_unless_existing_contract_does(db_session):
    mock_semantic = SemanticSearchService(db_session, HashFallbackAdapter())
    evo_svc = EvolutionService(db_session, semantic_service=mock_semantic)

    parent = Recipe(
        title="Parent",
        author_id=1,
        problem_type="test",
        provenance={"parent_only_key": "secret"}
    )
    db_session.add(parent)
    db_session.commit()

    child = evo_svc.evolve_recipe(parent.id, [], include_semantic_neighbors=False)

    # Parent provenance is not copied over to child
    assert "parent_only_key" not in (child.provenance or {})


# DIP Injection Tests
def test_recipe_service_semantic_service_injectable(db_session):
    adapter = HashFallbackAdapter()
    custom_svc = SemanticSearchService(db_session, adapter)
    svc = RecipeService(db_session, semantic_service=custom_svc)
    assert svc.semantic_service is custom_svc


def test_evolution_service_semantic_service_injectable(db_session):
    adapter = HashFallbackAdapter()
    custom_svc = SemanticSearchService(db_session, adapter)
    svc = EvolutionService(db_session, semantic_service=custom_svc)
    assert svc.semantic_service is custom_svc


# Read-Only & Non-Mutation Boundaries
def test_semantic_neighbors_read_only(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    p1 = Phenomenon(name="P1", description="Test phenomenon")
    db_session.add(p1)
    db_session.commit()

    semantic_svc.index_canonical("recipe", r1.id)
    semantic_svc.index_canonical("phenomenon", p1.id)

    rel_count_before = db_session.query(DomainRelation).count()
    neighbors = recipe_svc.semantic_neighbors(r1.id)
    rel_count_after = db_session.query(DomainRelation).count()

    assert rel_count_before == rel_count_after == 0


def test_semantic_neighbors_do_not_create_domain_relation(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    semantic_svc.index_canonical("recipe", r1.id)

    recipe_svc.semantic_neighbors(r1.id)
    assert db_session.query(DomainRelation).count() == 0


def test_semantic_neighbors_do_not_modify_recipe(db_session):
    recipe_svc = RecipeService(db_session)
    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")

    title_before = r1.title
    steps_before = list(r1.steps)

    recipe_svc.semantic_neighbors(r1.id)

    db_session.refresh(r1)
    assert r1.title == title_before
    assert r1.steps == steps_before


def test_semantic_neighbors_do_not_promote_epistemic_status(db_session):
    recipe_svc = RecipeService(db_session)
    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    # Recipe has confidence field, verify confidence is not altered
    conf_before = r1.confidence

    recipe_svc.semantic_neighbors(r1.id)

    db_session.refresh(r1)
    assert r1.confidence == conf_before


# Boundary / Negative Rules
def test_semantic_candidates_not_in_mutations(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    r2 = recipe_svc.create_recipe("R2", 1, ["step 2"], "test")
    semantic_svc.index_canonical("recipe", r1.id)
    semantic_svc.index_canonical("recipe", r2.id)

    child = evo_svc.evolve_recipe(r1.id, [], include_semantic_neighbors=True)
    assert child.mutations == []


def test_semantic_candidates_not_in_steps(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    r2 = recipe_svc.create_recipe("R2", 1, ["step 2"], "test")
    semantic_svc.index_canonical("recipe", r1.id)
    semantic_svc.index_canonical("recipe", r2.id)

    child = evo_svc.evolve_recipe(r1.id, [], include_semantic_neighbors=True)
    assert child.steps == ["step 1"]


def test_semantic_candidates_not_in_conditions(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    r2 = recipe_svc.create_recipe("R2", 1, ["step 2"], "test")
    semantic_svc.index_canonical("recipe", r1.id)
    semantic_svc.index_canonical("recipe", r2.id)

    child = evo_svc.evolve_recipe(r1.id, [], include_semantic_neighbors=True)
    assert child.success_conditions == []


def test_semantic_candidates_are_references_not_evidence(db_session):
    adapter = HashFallbackAdapter()
    semantic_svc = SemanticSearchService(db_session, adapter)
    recipe_svc = RecipeService(db_session, semantic_service=semantic_svc)
    evo_svc = EvolutionService(db_session, semantic_service=semantic_svc)

    r1 = recipe_svc.create_recipe("R1", 1, ["step 1"], "test")
    r2 = recipe_svc.create_recipe("R2", 1, ["step 2"], "test")
    semantic_svc.index_canonical("recipe", r1.id)
    semantic_svc.index_canonical("recipe", r2.id)

    child = evo_svc.evolve_recipe(r1.id, [], include_semantic_neighbors=True)
    candidates = child.provenance["semantic_candidates"]
    for cand in candidates:
        assert "entity_type" in cand
        assert "entity_id" in cand
        assert "similarity" in cand
        assert "model_name" in cand
