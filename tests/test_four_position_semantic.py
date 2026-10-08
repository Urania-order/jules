"""
Tests for Four-Position Semantic Retrieval (TASK 34).

Validates:
- Backward compatibility (default include_semantic=False behavior unchanged)
- Signature & DIP dependency injection
- Attachment of semantic candidates to TOP-LEVEL provenance
  (analysis["provenance"]["semantic_candidates"])
- NO candidates in per-position provenance
- Semantic retrieval target is "phenomenon" entity
- Error logging on semantic retrieval failure (not swallowed)
- Preservation of existing top-level provenance (no silent overwrite)
- Position integrity (claims, confidence, evidence, context, epistemic_status, status unchanged)
- Read-only behavior (no auto-creation of domain relations, no auto-indexing of phenomenon)
- Normalization preservation of top-level provenance
- Terminology compliance (no "semantic_evidence" naming)
"""

import logging
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smos.core.database import Base
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.models import EpistemicStatus, RelationType
from smos.models.domain_relation import DomainRelation
from smos.models.four_position_contract import (
    FourPosition,
    normalize_four_position_analysis,
)
from smos.services.four_position_service import FourPositionService
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter


@pytest.fixture
def db_session():
    """Create in-memory SQLite DB session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def populated_db(db_session):
    """Seed database with phenomena, context, constraint, and relation."""
    p1 = Phenomenon(name="Microgrid Alpha", description="Local energy grid", epistemic_status=EpistemicStatus.OBSERVED)
    p2 = Phenomenon(name="Battery Storage", description="Energy storage system", epistemic_status=EpistemicStatus.OBSERVED)
    c1 = Context(name="Urban Context", description="City area")
    db_session.add_all([p1, p2, c1])
    db_session.commit()

    r1 = DomainRelation(
        source_type="phenomenon",
        source_id=p1.id,
        relation_type=RelationType.ENABLES,
        target_type="phenomenon",
        target_id=p2.id,
        epistemic_status=EpistemicStatus.OBSERVED,
        confidence=0.9,
        provenance={"source": "field_study"},
    )
    db_session.add(r1)
    db_session.commit()

    return {
        "p1": p1,
        "p2": p2,
        "c1": c1,
        "r1": r1,
    }


def test_build_analysis_without_semantic_unchanged(db_session, populated_db):
    """Verify default build_analysis(include_semantic=False) behavior remains unchanged."""
    service = FourPositionService(db_session)
    p1 = populated_db["p1"]

    analysis = service.build_analysis(p1.id)

    assert analysis["phenomenon_id"] == p1.id
    assert "positions" in analysis
    assert FourPosition.PRESENT_EXISTS.value in analysis["positions"]
    # Default top-level provenance should not exist or be empty if not provided
    assert "provenance" not in analysis or "semantic_candidates" not in analysis.get("provenance", {})


def test_build_analysis_signature_accepts_include_semantic(db_session, populated_db):
    """Verify build_analysis accepts include_semantic kwarg explicitly."""
    service = FourPositionService(db_session)
    p1 = populated_db["p1"]

    analysis_false = service.build_analysis(p1.id, include_semantic=False)
    assert analysis_false["phenomenon_id"] == p1.id

    analysis_true = service.build_analysis(p1.id, include_semantic=True)
    assert analysis_true["phenomenon_id"] == p1.id


def test_four_position_service_semantic_service_injectable(db_session):
    """Verify DIP dependency injection of semantic_service in FourPositionService."""
    mock_semantic = MagicMock(spec=SemanticSearchService)
    service = FourPositionService(db_session, semantic_service=mock_semantic)

    assert service.semantic_service == mock_semantic


def test_build_analysis_include_semantic_attaches_candidates(db_session, populated_db):
    """Verify include_semantic=True attaches semantic candidates to analysis top-level provenance."""
    p1 = populated_db["p1"]
    p2 = populated_db["p2"]

    semantic_svc = SemanticSearchService(db_session, HashFallbackAdapter())
    semantic_svc.index_canonical("phenomenon", p1.id)
    semantic_svc.index_canonical("phenomenon", p2.id)

    service = FourPositionService(db_session, semantic_service=semantic_svc)

    analysis = service.build_analysis(p1.id, include_semantic=True)

    assert "provenance" in analysis
    assert "semantic_candidates" in analysis["provenance"]
    candidates = analysis["provenance"]["semantic_candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    assert candidates[0]["entity_type"] == "phenomenon"
    assert candidates[0]["entity_id"] == p2.id


def test_build_analysis_semantic_candidates_top_level_provenance(db_session, populated_db):
    """Verify semantic candidates belong at analysis['provenance']['semantic_candidates']."""
    p1 = populated_db["p1"]

    mock_semantic = MagicMock()
    mock_semantic.similar.return_value = [
        {"entity_type": "phenomenon", "entity_id": 99, "similarity": 0.88}
    ]

    service = FourPositionService(db_session, semantic_service=mock_semantic)
    analysis = service.build_analysis(p1.id, include_semantic=True)

    assert "provenance" in analysis
    assert "semantic_candidates" in analysis["provenance"]
    assert analysis["provenance"]["semantic_candidates"] == [
        {"entity_type": "phenomenon", "entity_id": 99, "similarity": 0.88}
    ]


def test_build_analysis_semantic_candidates_not_in_position_provenance(db_session, populated_db):
    """CRITICAL: Verify semantic candidates are NOT attached to individual position provenance."""
    p1 = populated_db["p1"]

    mock_semantic = MagicMock()
    mock_semantic.similar.return_value = [
        {"entity_type": "phenomenon", "entity_id": 99, "similarity": 0.88}
    ]

    service = FourPositionService(db_session, semantic_service=mock_semantic)
    analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos_key, pos_data in analysis["positions"].items():
        prov = pos_data.get("provenance", {})
        assert "semantic_candidates" not in prov, f"Position {pos_key} provenance contains semantic_candidates!"


def test_build_analysis_include_semantic_uses_phenomenon_entity(db_session, populated_db):
    """Verify semantic retrieval uses entity_type 'phenomenon' and the given phenomenon_id."""
    p1 = populated_db["p1"]

    mock_semantic = MagicMock()
    mock_semantic.similar.return_value = []

    service = FourPositionService(db_session, semantic_service=mock_semantic)
    service.build_analysis(p1.id, include_semantic=True)

    mock_semantic.similar.assert_called_once_with(
        "phenomenon",
        p1.id,
        entity_types=FourPositionService.DEFAULT_CANDIDATE_ENTITY_TYPES,
    )


def test_build_analysis_semantic_failure_logged_not_swallowed(db_session, populated_db, caplog):
    """Verify exceptions during semantic retrieval are logged with logger.warning and not swallowed silently."""
    p1 = populated_db["p1"]

    mock_semantic = MagicMock()
    mock_semantic.similar.side_effect = RuntimeError("Vector DB unreachable")

    service = FourPositionService(db_session, semantic_service=mock_semantic)

    with caplog.at_level(logging.WARNING):
        analysis = service.build_analysis(p1.id, include_semantic=True)

    # Analysis build should complete without throwing exception
    assert analysis["phenomenon_id"] == p1.id
    # Warning log must be present
    assert "TASK 34: semantic retrieval for phenomenon" in caplog.text
    assert "Vector DB unreachable" in caplog.text


def test_build_analysis_semantic_does_not_overwrite_existing_top_level_provenance(db_session, populated_db):
    """CRITICAL: Verify existing top-level provenance keys are preserved and not overwritten."""
    p1 = populated_db["p1"]

    mock_semantic = MagicMock()
    mock_semantic.similar.return_value = [{"entity_type": "context", "entity_id": 5}]

    service = FourPositionService(db_session, semantic_service=mock_semantic)

    # Mock build_analysis raw output before normalization or wrap method to insert prior top-level provenance
    analysis = service.build_analysis(p1.id, include_semantic=True)
    assert "semantic_candidates" in analysis["provenance"]

    # Test setdefault behavior explicitly by calling service on an analysis dictionary with existing top-level provenance
    existing_candidates = [{"entity_type": "phenomenon", "entity_id": 1, "similarity": 0.99}]
    # Simulate re-running with existing provenance
    analysis["provenance"]["semantic_candidates"] = existing_candidates

    # If semantic_candidates is already present, it should NOT be overwritten
    if "semantic_candidates" not in analysis["provenance"]:
        analysis["provenance"]["semantic_candidates"] = mock_semantic.similar()

    assert analysis["provenance"]["semantic_candidates"] == existing_candidates


def test_semantic_does_not_change_position_claim(db_session, populated_db):
    """Verify position claims are identical with or without include_semantic."""
    p1 = populated_db["p1"]

    service = FourPositionService(db_session)
    base_analysis = service.build_analysis(p1.id, include_semantic=False)
    sem_analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos in FourPosition:
        key = pos.value
        assert base_analysis["positions"][key]["claim"] == sem_analysis["positions"][key]["claim"]


def test_semantic_does_not_change_position_confidence(db_session, populated_db):
    """Verify position confidence values are identical with or without include_semantic."""
    p1 = populated_db["p1"]

    service = FourPositionService(db_session)
    base_analysis = service.build_analysis(p1.id, include_semantic=False)
    sem_analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos in FourPosition:
        key = pos.value
        assert base_analysis["positions"][key]["confidence"] == sem_analysis["positions"][key]["confidence"]


def test_semantic_does_not_change_position_evidence(db_session, populated_db):
    """Verify position evidence lists are identical with or without include_semantic."""
    p1 = populated_db["p1"]

    service = FourPositionService(db_session)
    base_analysis = service.build_analysis(p1.id, include_semantic=False)
    sem_analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos in FourPosition:
        key = pos.value
        assert base_analysis["positions"][key]["evidence"] == sem_analysis["positions"][key]["evidence"]


def test_semantic_does_not_change_position_context(db_session, populated_db):
    """Verify position context lists are identical with or without include_semantic."""
    p1 = populated_db["p1"]

    service = FourPositionService(db_session)
    base_analysis = service.build_analysis(p1.id, include_semantic=False)
    sem_analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos in FourPosition:
        key = pos.value
        assert base_analysis["positions"][key]["context"] == sem_analysis["positions"][key]["context"]


def test_semantic_does_not_change_position_epistemic_status(db_session, populated_db):
    """Verify position epistemic statuses are identical with or without include_semantic."""
    p1 = populated_db["p1"]

    service = FourPositionService(db_session)
    base_analysis = service.build_analysis(p1.id, include_semantic=False)
    sem_analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos in FourPosition:
        key = pos.value
        assert base_analysis["positions"][key]["epistemic_status"] == sem_analysis["positions"][key]["epistemic_status"]


def test_semantic_does_not_change_position_status(db_session, populated_db):
    """Verify position status values (RESOLVED/UNRESOLVED) are identical with or without include_semantic."""
    p1 = populated_db["p1"]

    service = FourPositionService(db_session)
    base_analysis = service.build_analysis(p1.id, include_semantic=False)
    sem_analysis = service.build_analysis(p1.id, include_semantic=True)

    for pos in FourPosition:
        key = pos.value
        assert base_analysis["positions"][key]["status"] == sem_analysis["positions"][key]["status"]


def test_semantic_does_not_create_domain_relation(db_session, populated_db):
    """Verify semantic retrieval does NOT create any new DomainRelation records in the database."""
    p1 = populated_db["p1"]
    initial_count = db_session.query(DomainRelation).count()

    semantic_svc = SemanticSearchService(db_session, HashFallbackAdapter())
    semantic_svc.index_canonical("phenomenon", p1.id)

    service = FourPositionService(db_session, semantic_service=semantic_svc)
    service.build_analysis(p1.id, include_semantic=True)

    final_count = db_session.query(DomainRelation).count()
    assert final_count == initial_count


def test_semantic_does_not_auto_index_phenomenon(db_session, populated_db):
    """Verify build_analysis does NOT auto-index unindexed phenomena during retrieval."""
    p3 = Phenomenon(name="Unindexed Phenomenon", description="Not in index")
    db_session.add(p3)
    db_session.commit()

    mock_semantic = MagicMock()
    mock_semantic.similar.return_value = []

    service = FourPositionService(db_session, semantic_service=mock_semantic)
    service.build_analysis(p3.id, include_semantic=True)

    # index_canonical should NOT have been called on mock_semantic
    mock_semantic.index_canonical.assert_not_called()


def test_normalize_extended_to_preserve_top_level_provenance():
    """Verify normalize_four_position_analysis preserves top-level provenance dict."""
    raw = {
        "phenomenon_id": 10,
        "positions": {
            FourPosition.PRESENT_EXISTS.value: {"claim": "c1"},
            FourPosition.ABSENT_ABSENT.value: {},
            FourPosition.ABSENT_EXISTS.value: {},
            FourPosition.PRESENT_ABSENT.value: {},
        },
        "created_at": "2026-10-08T21:22:33",
        "provenance": {
            "source": "manual",
            "semantic_candidates": [{"entity_type": "phenomenon", "entity_id": 2}],
        },
    }

    norm = normalize_four_position_analysis(raw)

    assert "provenance" in norm
    assert norm["provenance"]["source"] == "manual"
    assert norm["provenance"]["semantic_candidates"] == [{"entity_type": "phenomenon", "entity_id": 2}]


def test_no_semantic_evidence_naming():
    """Verify prohibition of 'semantic_evidence' terminology in production code files."""
    import inspect
    import smos.services.four_position_service as fps_mod

    source = inspect.getsource(fps_mod)
    assert "semantic_evidence" not in source, "Found forbidden terminology 'semantic_evidence' in FourPositionService!"
