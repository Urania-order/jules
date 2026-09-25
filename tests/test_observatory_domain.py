import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.models.phenomenon import Phenomenon
from smos.models.constraint import Constraint, ConstraintType
from smos.models.context import Context
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.models.prediction import Prediction
from smos.models.domain_relation import DomainRelation
from smos.models.models import EpistemicStatus, RelationType
from smos.models.context_exposure import ContextExposure, AgentType
from smos.services.observatory_service import ObservatoryService

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_domain_tables(db):
    yield
    db.query(DomainRelation).delete()
    db.query(Prediction).delete()
    db.query(PotentialPhenomenon).delete()
    db.query(Constraint).delete()
    db.query(ContextExposure).delete()
    db.query(Phenomenon).delete()
    db.commit()


def test_domain_state_exists_endpoint():
    response = client.get("/observatory/domain-state")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_domain_state_response_shape():
    response = client.get("/observatory/domain-state")
    assert response.status_code == 200
    data = response.json()
    expected_keys = [
        "what_exists",
        "what_is_emerging",
        "what_is_blocked",
        "what_could_emerge",
        "what_changes_context",
        "what_resonates",
        "what_is_predicted",
    ]
    for key in expected_keys:
        assert key in data
        assert isinstance(data[key], list)


def test_domain_state_empty_db(db):
    db.query(DomainRelation).delete()
    db.query(Prediction).delete()
    db.query(PotentialPhenomenon).delete()
    db.query(Constraint).delete()
    db.query(ContextExposure).delete()
    db.query(Phenomenon).delete()
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()
    assert state["what_exists"] == []
    assert state["what_is_emerging"] == []
    assert state["what_is_blocked"] == []
    assert state["what_could_emerge"] == []
    assert state["what_changes_context"] == []
    assert state["what_resonates"] == []
    assert state["what_is_predicted"] == []


def test_domain_state_what_exists(db):
    p1 = Phenomenon(name="Observed P1", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Inferred P2", epistemic_status=EpistemicStatus.INFERRED)
    db.add_all([p1, p2])
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    exists_names = [item["name"] for item in state["what_exists"]]
    assert "Observed P1" in exists_names
    assert "Inferred P2" not in exists_names


def test_domain_state_what_emerging(db):
    p1 = Phenomenon(name="Inferred Emergence P1", epistemic_status=EpistemicStatus.INFERRED)
    p2 = Phenomenon(name="Hypothesized Emergence P2", epistemic_status=EpistemicStatus.HYPOTHESIZED)
    p3 = Phenomenon(name="Observed Emergence P3", epistemic_status=EpistemicStatus.OBSERVED)
    db.add_all([p1, p2, p3])
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    emerging_names = [item["name"] for item in state["what_is_emerging"]]
    assert "Inferred Emergence P1" in emerging_names
    assert "Hypothesized Emergence P2" in emerging_names
    assert "Observed Emergence P3" not in emerging_names


def test_domain_state_what_blocked(db):
    p1 = Phenomenon(name="Blocked Phenomenon", epistemic_status=EpistemicStatus.OBSERVED)
    db.add(p1)
    db.commit()
    db.refresh(p1)

    c1 = Constraint(name="Blocking Constraint", type=ConstraintType.TECHNICAL)
    db.add(c1)
    db.commit()
    db.refresh(c1)

    rel = DomainRelation(
        source_type="constraint",
        source_id=c1.id,
        target_type="phenomenon",
        target_id=p1.id,
        relation_type=RelationType.BLOCKS,
    )
    db.add(rel)
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    blocked_ids = [item["phenomenon_id"] for item in state["what_is_blocked"]]
    assert p1.id in blocked_ids
    target_item = [item for item in state["what_is_blocked"] if item["phenomenon_id"] == p1.id][0]
    assert target_item["direct_count"] == 1


def test_domain_state_what_could_emerge(db):
    pot1 = PotentialPhenomenon(phenomenon="Potential P1", status=PotentialStatus.POSSIBLE)
    pot2 = PotentialPhenomenon(phenomenon="Potential P2", status=PotentialStatus.BLOCKED)
    db.add_all([pot1, pot2])
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    possible_names = [item["phenomenon"] for item in state["what_could_emerge"]]
    assert "Potential P1" in possible_names
    assert "Potential P2" not in possible_names


def test_domain_state_what_changes_context(db):
    p1 = Phenomenon(name="P1", epistemic_status=EpistemicStatus.OBSERVED)
    c1 = Context(name="C1")
    db.add_all([p1, c1])
    db.commit()
    db.refresh(p1)
    db.refresh(c1)

    rel1 = DomainRelation(
        source_type="phenomenon",
        source_id=p1.id,
        target_type="context",
        target_id=c1.id,
        relation_type=RelationType.CHANGES_CONTEXT,
    )
    rel2 = DomainRelation(
        source_type="phenomenon",
        source_id=p1.id,
        target_type="context",
        target_id=c1.id,
        relation_type=RelationType.SUPPORTS,
    )
    db.add_all([rel1, rel2])
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    rel_types = [item["relation_type"] for item in state["what_changes_context"]]
    assert "CHANGES_CONTEXT" in rel_types
    assert "SUPPORTS" not in rel_types


def test_domain_state_what_resonates(db):
    exp1 = ContextExposure(
        agent_type=AgentType.HUMAN,
        agent_id=101,
        role="analyst",
        context_ids=[10, 20],
        conclusion={"claim": "Co-SMOS evolution unique", "confidence": 0.8},
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    exp2 = ContextExposure(
        agent_type=AgentType.LLM,
        agent_id=102,
        role="reviewer",
        context_ids=[30, 40],
        conclusion={"claim": "Co-SMOS evolution unique", "confidence": 0.9},
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    db.add_all([exp1, exp2])
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    claims = [item["converging_conclusion"].get("claim") for item in state["what_resonates"]]
    assert "Co-SMOS evolution unique" in claims


def test_domain_state_what_predicted(db):
    pred1 = Prediction(
        expected_state={"value": 100},
        epistemic_status=EpistemicStatus.PREDICTED,
        prediction_time=datetime.now(timezone.utc),
    )
    pred2 = Prediction(
        expected_state={"value": 200},
        epistemic_status=EpistemicStatus.OBSERVED,
        prediction_time=datetime.now(timezone.utc),
    )
    db.add_all([pred1, pred2])
    db.commit()

    obs = ObservatoryService(db, [])
    state = obs.get_domain_state()

    pred_states = [item["expected_state"] for item in state["what_is_predicted"]]
    assert {"value": 100} in pred_states
    assert {"value": 200} not in pred_states


def test_domain_state_does_not_modify_entities(db):
    p1 = Phenomenon(name="Observed P1", epistemic_status=EpistemicStatus.OBSERVED)
    db.add(p1)
    db.commit()
    db.refresh(p1)

    obs = ObservatoryService(db, [])
    obs.get_domain_state()

    fetched = db.query(Phenomenon).filter(Phenomenon.id == p1.id).first()
    assert fetched is not None
    assert fetched.epistemic_status == EpistemicStatus.OBSERVED


def test_observatory_existing_endpoints_unchanged():
    r_health = client.get("/observatory/health")
    assert r_health.status_code == 200
    assert "health_score" in r_health.json()

    r_proposals = client.get("/observatory/proposals")
    assert r_proposals.status_code == 200

    r_report = client.get("/observatory/report")
    assert r_report.status_code == 200

    r_ranking = client.get("/observatory/ranking")
    assert r_ranking.status_code == 200

    r_recs = client.get("/observatory/recommendations")
    assert r_recs.status_code == 200


def test_observatory_health_still_works(db):
    obs = ObservatoryService(db, [])
    report = obs.get_health_report()
    assert "health_score" in report
    assert "timestamp" in report
