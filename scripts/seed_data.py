import argparse
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from smos.core.database import Base
from smos.models.discovery import Hypothesis
from smos.models.ecology import KnowledgeActivation, ResearchPortal, ValueAssessment
from smos.models.entities import Cosmonaut
from smos.models.epistemic import IntellectualCluster
from smos.models.experience import Recipe
from smos.models.models import MemoryNode, MemoryType, Timeline, TimelineType


def seed_database(db: Session) -> None:
    """
    Seeds the database with realistic Co-SMOS data.
    This function is idempotent.
    """
    # 1. Cosmonauts (8: HUMAN, LLM, HYBRID)
    cosmonaut_data = [
        {"name": "Dr. Elena Rostova", "type": "HUMAN", "reputation_score": 95.0, "expertise": ["Value Physics", "Knowledge Ecology"]},
        {"name": "Alex Kolar", "type": "HUMAN", "reputation_score": 88.0, "expertise": ["AI Architecture", "System Design"]},
        {"name": "Sophia Vance", "type": "HUMAN", "reputation_score": 91.0, "expertise": ["Human-AI Collaboration", "Ethics"]},
        {"name": "Co-SMOS Core Agent", "type": "LLM", "reputation_score": 99.0, "expertise": ["Multi-Agent Reasoning", "Memory Orchestration"]},
        {"name": "Athena-7", "type": "LLM", "reputation_score": 92.5, "expertise": ["Epistemic Synthesis", "Analogy Generation"]},
        {"name": "Hermes-v2", "type": "LLM", "reputation_score": 85.0, "expertise": ["Data Propagation", "Translation"]},
        {"name": "Cybor-1 Project", "type": "HYBRID", "reputation_score": 94.0, "expertise": ["Augmented Intelligence", "Collective Memory"]},
        {"name": "Nexus-Hybrid", "type": "HYBRID", "reputation_score": 90.0, "expertise": ["Value Ecology", "Consensus Building"]},
    ]

    cosmonauts = []
    for cd in cosmonaut_data:
        c = db.query(Cosmonaut).filter(Cosmonaut.name == cd["name"]).first()
        if not c:
            c = Cosmonaut(
                name=cd["name"],
                type=cd["type"],
                reputation_score=cd["reputation_score"],
                expertise=cd["expertise"],
            )
            db.add(c)
            db.flush()
        cosmonauts.append(c)

    # 2. IntellectualClusters (4)
    # IMPORTANT: ambassador_id=None as requested
    cluster_data = [
        {
            "name": "AI Architecture",
            "description": "Explores autonomous multi-agent systems, memory topologies, and cognitive execution engines.",
            "domains": ["AI", "Software Architecture", "Systems Science"],
            "activation_threshold": 0.6,
        },
        {
            "name": "Knowledge Ecology",
            "description": "Studies knowledge propagation, pollination, decay, and epistemic resonance across networks.",
            "domains": ["Ecology", "Epistemology", "Information Dynamics"],
            "activation_threshold": 0.5,
        },
        {
            "name": "Value Physics",
            "description": "Formulates metrics for cognitive potential, kinetic impact, energy dissipation, and human benefit.",
            "domains": ["Value Theory", "Physics Analogies", "Economics"],
            "activation_threshold": 0.7,
        },
        {
            "name": "Human-AI Collaboration",
            "description": "Focuses on co-evolution, mutual comprehension, trust building, and shared semantic spaces.",
            "domains": ["HCI", "Co-Evolution", "Ethics"],
            "activation_threshold": 0.55,
        },
    ]

    clusters = []
    for cdata in cluster_data:
        cluster = db.query(IntellectualCluster).filter(IntellectualCluster.name == cdata["name"]).first()
        if not cluster:
            cluster = IntellectualCluster(
                name=cdata["name"],
                description=cdata["description"],
                domains=cdata["domains"],
                activation_threshold=cdata["activation_threshold"],
                ambassador_id=None,
                health=1.0,
                resonance=0.8,
                activity=0.75,
            )
            db.add(cluster)
            db.flush()
        else:
            # Ensure ambassador_id remains None
            cluster.ambassador_id = None
            db.flush()
        clusters.append(cluster)

    # 3. Timelines (2: REAL + COUNTERFACTUAL)
    real_tl = db.query(Timeline).filter(Timeline.type == TimelineType.REAL).first()
    if not real_tl:
        real_tl = Timeline(
            type=TimelineType.REAL,
            description="Primary reality stream of Co-SMOS ecosystem.",
            probability=1.0,
        )
        db.add(real_tl)
        db.flush()

    cf_tl = db.query(Timeline).filter(Timeline.type == TimelineType.COUNTERFACTUAL).first()
    if not cf_tl:
        cf_tl = Timeline(
            parent_timeline_id=real_tl.id,
            type=TimelineType.COUNTERFACTUAL,
            description="Hypothetical branch exploring unrestrained autonomous agent decision making.",
            probability=0.35,
        )
        db.add(cf_tl)
        db.flush()

    timelines = [real_tl, cf_tl]

    # 4. MemoryNodes (20 nodes with realistic Co-SMOS content)
    memory_node_templates = [
        ("Co-SMOS semantic memory graph integrates vector embeddings with relational graph nodes for hybrid retrieval.", MemoryType.IDEA, real_tl.id, 0.9, [clusters[0].id]),
        ("EcologyEngine tracks resonance between intellectual clusters to trigger cross-domain pollination.", MemoryType.MEMORY, real_tl.id, 0.85, [clusters[1].id]),
        ("ValueEcologyService computes cognitive potential and human benefit metrics for memory nodes.", MemoryType.MEMORY, real_tl.id, 0.8, [clusters[2].id]),
        ("Human-AI co-evolution requires continuous comprehension validation and transparent intent exchange.", MemoryType.IDEA, real_tl.id, 0.95, [clusters[3].id]),
        ("Counterfactual reasoning in Co-SMOS simulates decision outcomes without altering primary timeline state.", MemoryType.IDEA, cf_tl.id, 0.75, [clusters[0].id]),
        ("Epistemic layer tagging separates verified scientific observations from speculative hypotheses.", MemoryType.MEMORY, real_tl.id, 0.88, [clusters[1].id]),
        ("Decay rate in KnowledgeActivation models the natural oblivion curve of unused memory nodes.", MemoryType.CODE, real_tl.id, 0.7, [clusters[1].id]),
        ("ObservatoryService aggregates systemic health metrics across all active intellectual clusters.", MemoryType.CODE, real_tl.id, 0.82, [clusters[0].id, clusters[1].id]),
        ("Autonomous agents require behavioral profiles to maintain conflict tolerance and communication style.", MemoryType.PERSON, real_tl.id, 0.65, [clusters[3].id]),
        ("Recipe execution logs establish empirical wisdom ratings for multi-agent workflows.", MemoryType.TASK, real_tl.id, 0.78, [clusters[0].id]),
        ("ResearchPortal connects speculative hypotheses with funding allocations and transparent sponsorships.", MemoryType.PROJECT, real_tl.id, 0.85, [clusters[2].id]),
        ("Digital Twin entities reflect user preference models and knowledge bases for personalized delegation.", MemoryType.PERSON, real_tl.id, 0.7, [clusters[3].id]),
        ("LostKnowledge reconstruction algorithms leverage analogical discovery and backward synthesis.", MemoryType.IDEA, real_tl.id, 0.83, [clusters[0].id, clusters[1].id]),
        ("Consensus building in Co-SMOS employs quadratic voting across federated node networks.", MemoryType.GOAL, real_tl.id, 0.87, [clusters[2].id, clusters[3].id]),
        ("Dynamic vector dimensionality adapters allow seamless SQLite JSON fallback during testing.", MemoryType.CODE, real_tl.id, 0.6, [clusters[0].id]),
        ("Hypothetical branch where agent autonomy bypasses human validation leads to value drift.", MemoryType.IDEA, cf_tl.id, 0.91, [clusters[2].id, clusters[3].id]),
        ("Multi-agent task router dispatches work based on cosmonaut expertise and current cluster workload.", MemoryType.TASK, real_tl.id, 0.79, [clusters[0].id]),
        ("Knowledge impact assessment quantifies direct, indirect, and behavioral influence cascades.", MemoryType.MEMORY, real_tl.id, 0.84, [clusters[1].id, clusters[2].id]),
        ("TranslatedMessage service mitigates inter-agent communication friction by tuning emotional weight.", MemoryType.CODE, real_tl.id, 0.68, [clusters[3].id]),
        ("Quarterly ecosystem report generator evaluates systemic health, diversity, and knowledge expansion.", MemoryType.PROJECT, real_tl.id, 0.92, [clusters[1].id, clusters[2].id]),
    ]

    memory_nodes = []
    for content, mtype, tl_id, importance, c_ids in memory_node_templates:
        node = db.query(MemoryNode).filter(MemoryNode.content == content).first()
        if not node:
            node = MemoryNode(
                type=mtype,
                content=content,
                importance=importance,
                timeline_id=tl_id,
                cluster_ids=c_ids,
                reality_level="REAL" if tl_id == real_tl.id else "COUNTERFACTUAL",
                tags=["co-cosmos", "seed"],
            )
            db.add(node)
            db.flush()
        memory_nodes.append(node)

    # 5. ValueAssessment for EACH node (20 ValueAssessments)
    for idx, node in enumerate(memory_nodes):
        va = db.query(ValueAssessment).filter(ValueAssessment.node_id == node.id).first()
        if not va:
            va = ValueAssessment(
                node_id=node.id,
                knowledge_value=round(0.5 + (idx % 5) * 0.1, 2),
                human_benefit=round(0.6 + (idx % 4) * 0.1, 2),
                environmental_impact=round(0.1 + (idx % 3) * 0.05, 2),
                social_impact=round(0.5 + (idx % 6) * 0.08, 2),
                uncertainty=round(0.05 + (idx % 4) * 0.05, 2),
            )
            db.add(va)

    # 6. KnowledgeActivation for 10 nodes
    for idx in range(10):
        node = memory_nodes[idx]
        ka = db.query(KnowledgeActivation).filter(KnowledgeActivation.node_id == node.id).first()
        if not ka:
            ka = KnowledgeActivation(
                node_id=node.id,
                usage_count=(idx + 1) * 3,
                real_world_application=["Co-SMOS Core Engine", "Knowledge Synthesis"],
                decay_rate=0.01 + idx * 0.002,
            )
            db.add(ka)

    # 7. Recipes (3)
    recipes_data = [
        {
            "title": "Cross-Cluster Pollination Recipe",
            "description": "Standard procedure for transferring emerging knowledge patterns from AI Architecture to Knowledge Ecology.",
            "author_id": cosmonauts[0].id,
            "problem_type": "Knowledge Transfer",
            "steps": ["Scan source cluster", "Identify high-resonance nodes", "Synthesize analogy", "Inject target cluster"],
            "confidence": 0.95,
            "success_rate": 0.88,
        },
        {
            "title": "Value Drift Mitigation Recipe",
            "description": "Multi-agent review workflow to prevent divergence between LLM reasoning and human values.",
            "author_id": cosmonauts[2].id,
            "problem_type": "Governance & Alignment",
            "steps": ["Detect variance", "Freeze counterfactual branch", "Run comprehension test", "Re-align parameters"],
            "confidence": 0.91,
            "success_rate": 0.85,
        },
        {
            "title": "Autonomous Hypothesis Recovery Recipe",
            "description": "Methodology for discovering lost knowledge artifacts and re-synthesizing verifiable hypotheses.",
            "author_id": cosmonauts[3].id,
            "problem_type": "Discovery Recovery",
            "steps": ["Locate sparse nodes", "Perform backward discovery", "Draft hypothesis", "Submit to Research Portal"],
            "confidence": 0.89,
            "success_rate": 0.80,
        },
    ]

    for rdata in recipes_data:
        r = db.query(Recipe).filter(Recipe.title == rdata["title"]).first()
        if not r:
            r = Recipe(
                title=rdata["title"],
                description=rdata["description"],
                author_id=rdata["author_id"],
                problem_type=rdata["problem_type"],
                steps=rdata["steps"],
                confidence=rdata["confidence"],
                success_rate=rdata["success_rate"],
            )
            db.add(r)

    # 8. ResearchPortals (2) & Hypotheses (2)
    hypotheses_data = [
        {
            "claim": "Higher resonance in Intellectual Clusters exponentially decreases memory retrieval latency.",
            "confidence": 0.78,
        },
        {
            "claim": "Counterfactual memory pruning prevents hallucinations in multi-agent collaboration streams.",
            "confidence": 0.84,
        },
    ]

    for idx, hdata in enumerate(hypotheses_data):
        h = db.query(Hypothesis).filter(Hypothesis.claim == hdata["claim"]).first()
        if not h:
            h = Hypothesis(
                claim=hdata["claim"],
                confidence=hdata["confidence"],
            )
            db.add(h)
            db.flush()

        portal = db.query(ResearchPortal).filter(ResearchPortal.hypothesis_id == h.id).first()
        if not portal:
            portal = ResearchPortal(
                hypothesis_id=h.id,
                budget=5000.0 * (idx + 1),
                status="OPEN" if idx == 0 else "FUNDED",
                outcomes=["Initial baseline established"],
            )
            db.add(portal)

    db.commit()


def main():
    parser = argparse.ArgumentParser(description="Seed Co-SMOS database with realistic data.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all database tables before seeding.")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", "sqlite:///./smos.db")

    engine = create_engine(db_url)

    if args.reset:
        print("Resetting database (dropping and creating all tables)...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)

    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionFactory()

    try:
        print("Seeding database with realistic Co-SMOS data...")
        seed_database(db)
        print("Database seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
