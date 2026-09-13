from scripts.seed_data import seed_database
from smos.models.discovery import Hypothesis
from smos.models.ecology import KnowledgeActivation, ResearchPortal, ValueAssessment
from smos.models.entities import Cosmonaut
from smos.models.epistemic import IntellectualCluster
from smos.models.experience import Recipe
from smos.models.models import MemoryNode, Timeline, TimelineType

SEED_COSMONAUT_NAMES = {
    "Dr. Elena Rostova",
    "Alex Kolar",
    "Sophia Vance",
    "Co-SMOS Core Agent",
    "Athena-7",
    "Hermes-v2",
    "Cybor-1 Project",
    "Nexus-Hybrid",
}

SEED_CLUSTER_NAMES = {
    "AI Architecture",
    "Knowledge Ecology",
    "Value Physics",
    "Human-AI Collaboration",
}

SEED_RECIPE_TITLES = {
    "Cross-Cluster Pollination Recipe",
    "Value Drift Mitigation Recipe",
    "Autonomous Hypothesis Recovery Recipe",
}

SEED_HYPOTHESIS_CLAIMS = {
    "Higher resonance in Intellectual Clusters exponentially decreases memory retrieval latency.",
    "Counterfactual memory pruning prevents hallucinations in multi-agent collaboration streams.",
}


def test_seed_database(db):
    """
    Test that seed_database inserts the expected entities into the database.
    """
    seed_database(db)

    # 1. Cosmonauts (8)
    cosmonauts = db.query(Cosmonaut).filter(Cosmonaut.name.in_(SEED_COSMONAUT_NAMES)).all()
    assert len(cosmonauts) == 8
    human_count = sum(1 for c in cosmonauts if c.type == "HUMAN")
    llm_count = sum(1 for c in cosmonauts if c.type == "LLM")
    hybrid_count = sum(1 for c in cosmonauts if c.type == "HYBRID")
    assert human_count == 3
    assert llm_count == 3
    assert hybrid_count == 2

    # 2. Intellectual Clusters (4) & ambassador_id is None
    clusters = db.query(IntellectualCluster).filter(IntellectualCluster.name.in_(SEED_CLUSTER_NAMES)).all()
    assert len(clusters) == 4
    for cluster in clusters:
        assert cluster.ambassador_id is None

    # 3. Timelines (2: REAL + COUNTERFACTUAL)
    timelines = db.query(Timeline).all()
    assert len(timelines) >= 2
    types = {t.type for t in timelines}
    assert TimelineType.REAL in types
    assert TimelineType.COUNTERFACTUAL in types

    # 4. MemoryNodes (20 tagged with "seed")
    nodes = [n for n in db.query(MemoryNode).all() if n.tags and "seed" in n.tags]
    assert len(nodes) == 20

    # 5. ValueAssessments (20, one for each seeded node)
    seed_node_ids = {n.id for n in nodes}
    assessments = db.query(ValueAssessment).filter(ValueAssessment.node_id.in_(seed_node_ids)).all()
    assert len(assessments) == 20

    # 6. KnowledgeActivations (10 for seeded nodes)
    activations = db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id.in_(seed_node_ids)).all()
    assert len(activations) == 10

    # 7. Recipes (3)
    recipes = db.query(Recipe).filter(Recipe.title.in_(SEED_RECIPE_TITLES)).all()
    assert len(recipes) == 3

    # 8. ResearchPortals (2) & Hypotheses (2)
    hypotheses = db.query(Hypothesis).filter(Hypothesis.claim.in_(SEED_HYPOTHESIS_CLAIMS)).all()
    assert len(hypotheses) == 2
    hypothesis_ids = {h.id for h in hypotheses}
    portals = db.query(ResearchPortal).filter(ResearchPortal.hypothesis_id.in_(hypothesis_ids)).all()
    assert len(portals) == 2


def test_seed_database_idempotency(db):
    """
    Test running seed_database twice does not create duplicate entries.
    """
    seed_database(db)
    seed_database(db)

    cosmonauts = db.query(Cosmonaut).filter(Cosmonaut.name.in_(SEED_COSMONAUT_NAMES)).all()
    assert len(cosmonauts) == 8

    clusters = db.query(IntellectualCluster).filter(IntellectualCluster.name.in_(SEED_CLUSTER_NAMES)).all()
    assert len(clusters) == 4
    for cluster in clusters:
        assert cluster.ambassador_id is None

    nodes = [n for n in db.query(MemoryNode).all() if n.tags and "seed" in n.tags]
    assert len(nodes) == 20

    seed_node_ids = {n.id for n in nodes}
    assessments = db.query(ValueAssessment).filter(ValueAssessment.node_id.in_(seed_node_ids)).all()
    assert len(assessments) == 20

    activations = db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id.in_(seed_node_ids)).all()
    assert len(activations) == 10

    recipes = db.query(Recipe).filter(Recipe.title.in_(SEED_RECIPE_TITLES)).all()
    assert len(recipes) == 3

    hypotheses = db.query(Hypothesis).filter(Hypothesis.claim.in_(SEED_HYPOTHESIS_CLAIMS)).all()
    assert len(hypotheses) == 2

    hypothesis_ids = {h.id for h in hypotheses}
    portals = db.query(ResearchPortal).filter(ResearchPortal.hypothesis_id.in_(hypothesis_ids)).all()
    assert len(portals) == 2
