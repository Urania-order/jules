import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from smos.core.database import Base
from smos.models.context_exposure import ContextExposure, AgentType
from smos.models.models import EpistemicStatus, User
from smos.models.entities import Cosmonaut, LLMProfile
from smos.models.context import Context
from smos.services.context_exposure_service import ContextExposureService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_agent_type_enum():
    assert AgentType.HUMAN.value == "HUMAN"
    assert AgentType.COSMONAUT.value == "COSMONAUT"
    assert AgentType.LLM.value == "LLM"
    assert AgentType.DIGITAL_TWIN.value == "DIGITAL_TWIN"
    assert AgentType.SYSTEM.value == "SYSTEM"
    assert AgentType.UNKNOWN.value == "UNKNOWN"


def test_agent_type_from_str():
    assert AgentType.from_str("cosmonaut") == AgentType.COSMONAUT
    assert AgentType.from_str("LLM") == AgentType.LLM
    assert AgentType.from_str("invalid_type") == AgentType.UNKNOWN
    assert AgentType.from_str(None) == AgentType.UNKNOWN
    assert AgentType.from_str(AgentType.HUMAN) == AgentType.HUMAN


def test_agent_type_unknown_default():
    assert AgentType._missing_("NonExistent") == AgentType.UNKNOWN


def test_epistemic_status_default_observed(db_session):
    service = ContextExposureService(db_session)
    exposure = service.record(agent_type="SYSTEM")
    assert exposure.epistemic_status == EpistemicStatus.OBSERVED


def test_record_context_exposure(db_session):
    service = ContextExposureService(db_session)
    exposure = service.record(
        agent_type="COSMONAUT",
        agent_id=42,
        role="skeptic",
        context_ids=[101, 102],
        knowledge_ids=[1, 2],
        hidden_context_ids=[201],
        conclusion={"claim": "Hypothesis X holds under condition C", "confidence": 0.85},
        epistemic_status=EpistemicStatus.INFERRED,
        provenance={"source": "test_suite", "run_id": "abc-123"},
    )
    assert exposure.id is not None
    assert exposure.agent_type == AgentType.COSMONAUT
    assert exposure.agent_id == 42
    assert exposure.role == "skeptic"
    assert exposure.context_ids == [101, 102]
    assert exposure.knowledge_ids == [1, 2]
    assert exposure.hidden_context_ids == [201]
    assert exposure.conclusion == {"claim": "Hypothesis X holds under condition C", "confidence": 0.85}
    assert exposure.epistemic_status == EpistemicStatus.INFERRED
    assert exposure.provenance == {"source": "test_suite", "run_id": "abc-123"}


def test_serialize_context_exposure(db_session):
    service = ContextExposureService(db_session)
    exposure = service.record(
        agent_type="LLM",
        agent_id=1,
        role="analyst",
        context_ids=[10],
        conclusion={"claim": "Analysis complete"},
    )
    data = exposure.to_dict()
    assert data["id"] == exposure.id
    assert data["agent_type"] == "LLM"
    assert data["agent_id"] == 1
    assert data["role"] == "analyst"
    assert data["context_ids"] == [10]
    assert data["knowledge_ids"] == []
    assert data["hidden_context_ids"] == []
    assert data["conclusion"] == {"claim": "Analysis complete"}
    assert data["epistemic_status"] == "OBSERVED"
    assert data["provenance"] == {}
    assert "created_at" in data
    assert "updated_at" in data


def test_persist_context_exposure(db_session):
    service = ContextExposureService(db_session)
    created = service.record(
        agent_type="HUMAN",
        agent_id=5,
        role="operator",
        context_ids=[1, 2, 3],
    )
    db_session.expire_all()
    fetched = db_session.query(ContextExposure).filter_by(id=created.id).first()
    assert fetched is not None
    assert fetched.agent_type == AgentType.HUMAN
    assert fetched.context_ids == [1, 2, 3]


def test_retrieve_context_exposure(db_session):
    service = ContextExposureService(db_session)
    created = service.record(agent_type="SYSTEM", role="monitoring")
    retrieved = service.get(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert service.get(9999) is None


def test_list_context_exposures(db_session):
    service = ContextExposureService(db_session)
    e1 = service.record(agent_type="COSMONAUT", agent_id=1)
    e2 = service.record(agent_type="LLM", agent_id=2)
    exposures = service.list()
    assert len(exposures) == 2


def test_list_filter_by_agent_type(db_session):
    service = ContextExposureService(db_session)
    service.record(agent_type="COSMONAUT", agent_id=1)
    service.record(agent_type="LLM", agent_id=2)
    cosmonauts = service.list(agent_type="COSMONAUT")
    assert len(cosmonauts) == 1
    assert cosmonauts[0].agent_type == AgentType.COSMONAUT


def test_list_filter_by_agent_id(db_session):
    service = ContextExposureService(db_session)
    service.record(agent_type="LLM", agent_id=10)
    service.record(agent_type="LLM", agent_id=20)
    filtered = service.list(agent_id=10)
    assert len(filtered) == 1
    assert filtered[0].agent_id == 10


def test_delete_context_exposure(db_session):
    service = ContextExposureService(db_session)
    e = service.record(agent_type="SYSTEM")
    assert service.delete(e.id) is True
    assert service.get(e.id) is None
    assert service.delete(e.id) is False


def test_provenance_survives_persistence(db_session):
    service = ContextExposureService(db_session)
    prov = {"origin": "sensor_net", "batch_id": 999, "nested": {"key": "val"}}
    e = service.record(agent_type="SYSTEM", provenance=prov)
    db_session.expire_all()
    fetched = service.get(e.id)
    assert fetched.provenance == prov


def test_provenance_survives_retrieval(db_session):
    service = ContextExposureService(db_session)
    prov = {"auditor": "agent_x"}
    e = service.record(agent_type="COSMONAUT", provenance=prov)
    fetched = service.get(e.id)
    assert fetched.to_dict()["provenance"] == prov


def test_hidden_context_ids_persist(db_session):
    service = ContextExposureService(db_session)
    e = service.record(agent_type="COSMONAUT", hidden_context_ids=[10, 20, 30])
    db_session.expire_all()
    fetched = service.get(e.id)
    assert fetched.hidden_context_ids == [10, 20, 30]


def test_knowledge_ids_persist(db_session):
    service = ContextExposureService(db_session)
    e = service.record(agent_type="LLM", knowledge_ids=[500, 501])
    db_session.expire_all()
    fetched = service.get(e.id)
    assert fetched.knowledge_ids == [500, 501]


def test_conclusion_json_persists(db_session):
    service = ContextExposureService(db_session)
    conclusion = {"claim": "System is stable", "metrics": {"cpu": 12.5}}
    e = service.record(agent_type="DIGITAL_TWIN", conclusion=conclusion)
    db_session.expire_all()
    fetched = service.get(e.id)
    assert fetched.conclusion == conclusion


def test_convergence_signals_aggregates_by_context(db_session):
    service = ContextExposureService(db_session)
    # Agent 1 and Agent 2 see context [1, 2]
    service.record(agent_type="COSMONAUT", agent_id=1, context_ids=[1, 2], conclusion={"claim": "A"})
    service.record(agent_type="LLM", agent_id=2, context_ids=[1, 2], conclusion={"claim": "A"})
    # Agent 3 sees context [3]
    service.record(agent_type="HUMAN", agent_id=3, context_ids=[3], conclusion={"claim": "B"})

    res = service.convergence_signals()
    assert res["total_exposures"] == 3
    assert len(res["context_fragments"]) == 1
    fragment = res["context_fragments"][0]
    assert fragment["context_ids"] == [1, 2]
    assert fragment["agent_count"] == 2
    assert len(fragment["agents"]) == 2


def test_convergence_signals_returns_signal_note(db_session):
    service = ContextExposureService(db_session)
    res = service.convergence_signals()
    assert res["note"] == "This is a SIGNAL, not evidence of truth."


def test_context_exposure_not_truth():
    # Documentation assertion verifying model docstring explicit design constraint
    doc = ContextExposure.__doc__
    assert "SIGNAL for convergence analysis" in doc
    assert "NOT evidence of truth" in doc


def test_context_exposure_does_not_modify_agent_models(db_session):
    cosmonaut = Cosmonaut(name="Astronaut Alice")
    llm = LLMProfile(role="Analytical")
    db_session.add_all([cosmonaut, llm])
    db_session.commit()

    service = ContextExposureService(db_session)
    service.record(agent_type="COSMONAUT", agent_id=cosmonaut.id)
    service.record(agent_type="LLM", agent_id=llm.id)

    # Verify agent models remain untouched
    c_fetched = db_session.query(Cosmonaut).get(cosmonaut.id)
    l_fetched = db_session.query(LLMProfile).get(llm.id)
    assert c_fetched.name == "Astronaut Alice"
    assert l_fetched.role == "Analytical"


def test_context_exposure_does_not_modify_context_model(db_session):
    ctx = Context(name="Test Context", description="A test context")
    db_session.add(ctx)
    db_session.commit()

    service = ContextExposureService(db_session)
    service.record(agent_type="COSMONAUT", context_ids=[ctx.id], hidden_context_ids=[ctx.id])

    ctx_fetched = db_session.query(Context).get(ctx.id)
    assert ctx_fetched.name == "Test Context"
