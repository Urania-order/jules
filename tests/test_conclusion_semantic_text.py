import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.context_exposure import ContextExposure, AgentType
from smos.services.semantic_search_service import (
    SemanticSearchService,
    build_canonical_semantic_text,
)
from smos.services.embedding_fallback import HashFallbackAdapter


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


class MockContextExposureWithConclusion:
    def __init__(self, conclusion):
        self.conclusion = conclusion


# --- Stability tests ---


def test_conclusion_semantic_text_deterministic():
    c = {"claim": "System performance improves", "confidence": 0.85, "detail": "extra info"}
    obj = MockContextExposureWithConclusion(c)
    text1 = build_canonical_semantic_text("conclusion", obj)
    text2 = build_canonical_semantic_text("conclusion", obj)
    assert text1 == text2
    assert text1 == "Conclusion: System performance improves\nConfidence: 0.85"


def test_conclusion_semantic_text_stable_across_calls():
    ce = ContextExposure(
        agent_type=AgentType.HUMAN,
        conclusion={"claim": "Thermal anomaly detected", "confidence": 0.9},
    )
    t1 = build_canonical_semantic_text("context_exposure", ce)
    t2 = build_canonical_semantic_text("context_exposure", ce)
    assert t1 == t2
    assert t1 == "Conclusion: Thermal anomaly detected\nConfidence: 0.9"


def test_conclusion_semantic_text_uses_claim():
    obj = MockContextExposureWithConclusion({"claim": "Primary hypothesis holds"})
    text = build_canonical_semantic_text("conclusion", obj)
    assert "Primary hypothesis holds" in text
    assert text == "Conclusion: Primary hypothesis holds"


def test_conclusion_semantic_text_uses_confidence():
    obj = MockContextExposureWithConclusion({"claim": "Hypothesis holds", "confidence": 0.75})
    text = build_canonical_semantic_text("conclusion", obj)
    assert "Confidence: 0.75" in text


def test_conclusion_semantic_text_does_not_use_raw_json_dump():
    c = {
        "claim": "Clean energy yield increased",
        "confidence": 0.8,
        "detail": {"complex": [1, 2, 3]},
        "provenance": {"internal_key": "unstable_val"},
    }
    obj = MockContextExposureWithConclusion(c)
    text = build_canonical_semantic_text("conclusion", obj)
    assert "unstable_val" not in text
    assert "complex" not in text
    assert text == "Conclusion: Clean energy yield increased\nConfidence: 0.8"


def test_conclusion_semantic_text_no_ids():
    ce = ContextExposure(
        id=999,
        agent_id=123,
        context_ids=[1, 2],
        knowledge_ids=[3, 4],
        conclusion={"claim": "No IDs in representation", "confidence": 0.5},
    )
    text = build_canonical_semantic_text("context_exposure", ce)
    assert "999" not in text
    assert "123" not in text
    assert text == "Conclusion: No IDs in representation\nConfidence: 0.5"


def test_conclusion_semantic_text_no_timestamps():
    ce = ContextExposure(
        conclusion={"claim": "No timestamp test"},
    )
    text = build_canonical_semantic_text("context_exposure", ce)
    assert "created_at" not in text
    assert "updated_at" not in text
    assert text == "Conclusion: No timestamp test"


def test_conclusion_semantic_text_empty_conclusion():
    obj = MockContextExposureWithConclusion({})
    text = build_canonical_semantic_text("conclusion", obj)
    assert text == "Conclusion:"


def test_conclusion_semantic_text_no_claim_fallback():
    # Falls back to 'text' key if 'claim' is missing per conclusion_contract
    obj = MockContextExposureWithConclusion({"text": "Fallback claim text", "confidence": 0.6})
    text = build_canonical_semantic_text("conclusion", obj)
    assert text == "Conclusion: Fallback claim text\nConfidence: 0.6"


# --- Contract integration tests ---


def test_conclusion_semantic_text_uses_conclusion_contract():
    from smos.models.conclusion_contract import get_claim, get_confidence

    c = {"claim": "Contract validated", "confidence": "0.88"}
    obj = MockContextExposureWithConclusion(c)

    expected_claim = get_claim(c)
    expected_conf = get_confidence(c)

    text = build_canonical_semantic_text("conclusion", obj)
    assert expected_claim in text
    assert str(expected_conf) in text
    assert text == f"Conclusion: {expected_claim}\nConfidence: {expected_conf}"


def test_conclusion_semantic_text_round_trip_consistency():
    c = {"claim": "Round trip claim", "confidence": 0.95}
    ce = ContextExposure(
        agent_type=AgentType.HUMAN,
        conclusion=c,
    )

    t1 = build_canonical_semantic_text("conclusion", ce)
    t2 = build_canonical_semantic_text("context_exposure", ce)
    assert t1 == t2 == "Conclusion: Round trip claim\nConfidence: 0.95"


# --- Architecture contract tests ---


def test_generic_search_api_remains_unchanged(db_session):
    adapter = HashFallbackAdapter()
    service = SemanticSearchService(db_session, adapter)

    # Verify generic search API exists and no search_conclusions method was added
    assert hasattr(service, "search")
    assert hasattr(service, "similar")
    assert not hasattr(service, "search_conclusions")

    # Verify indexing and searching context_exposure / conclusion via generic API
    ce = ContextExposure(
        agent_type=AgentType.HUMAN,
        conclusion={"claim": "Generic search API check", "confidence": 0.9},
    )
    db_session.add(ce)
    db_session.commit()

    service.index_canonical("context_exposure", ce.id)
    results = service.search("Generic search API check", k=5, entity_types=["context_exposure"])
    assert len(results) == 1
    assert results[0]["entity_type"] == "context_exposure"
    assert results[0]["entity_id"] == ce.id


def test_no_new_conclusion_model():
    # Verify no new Conclusion model file exists in smos/models
    models_dir = os.path.join(os.path.dirname(__file__), "..", "smos", "models")
    files = os.listdir(models_dir)
    assert "conclusion.py" not in files, "New Conclusion model file must not be created"


def test_conclusion_remains_json_on_context_exposure():
    # Verify ContextExposure.conclusion column remains JSON and is not a foreign key
    column = ContextExposure.conclusion.property.columns[0]
    assert column.type.__class__.__name__ in ("JSON", "JSONB")
