"""Tests for Replay Contract (TASK L-05B)."""

from datetime import datetime, timezone, timedelta
import pytest

from smos.models.replay_contract import (
    validate_replay_request,
    validate_replay_result,
    normalize_replay_result,
    canonical_replay_json,
    compute_replay_hash,
    FORMAT_VERSION,
)


def test_validate_replay_request_valid():
    req = {
        "as_of": "2026-10-14T12:00:00+00:00",
        "scope": ["observation", "experiment_run"],
        "mode": "computation",
    }
    valid, errors = validate_replay_request(req)
    assert valid is True
    assert errors == []


def test_validate_replay_request_invalid_as_of():
    # Missing as_of
    valid, errors = validate_replay_request({})
    assert valid is False
    assert any("required" in e for e in errors)

    # Naive datetime string
    valid, errors = validate_replay_request({"as_of": "2026-10-14T12:00:00"})
    assert valid is False
    assert any("timezone-aware" in e for e in errors)

    # Malformed datetime string
    valid, errors = validate_replay_request({"as_of": "not-a-date"})
    assert valid is False
    assert any("valid ISO" in e for e in errors)


def test_validate_replay_request_invalid_scope_and_mode():
    req = {
        "as_of": "2026-10-14T12:00:00Z",
        "scope": ["invalid_scope"],
        "mode": "invalid_mode",
    }
    valid, errors = validate_replay_request(req)
    assert valid is False
    assert len(errors) == 2


def test_canonical_replay_json_and_content_hash_excludes_reconstructed_at():
    now = datetime.now(timezone.utc)
    res_a = {
        "as_of": "2026-10-14T12:00:00+00:00",
        "format_version": FORMAT_VERSION,
        "completeness": "COMPLETE",
        "reconstructed_state": {
            "observations": [{"id": 1, "availability_at": "2026-10-14T10:00:00+00:00", "fidelity": "VERIFIED"}],
        },
        "reconstruction_diagnostics": {},
        "provenance": {"provenance_refs": [], "relation_refs": []},
        "uncertainty_notes": [],
        "reconstructed_at": now.isoformat(),
    }

    res_b = {
        "as_of": "2026-10-14T12:00:00+00:00",
        "format_version": FORMAT_VERSION,
        "completeness": "COMPLETE",
        "reconstructed_state": {
            "observations": [{"id": 1, "availability_at": "2026-10-14T10:00:00+00:00", "fidelity": "VERIFIED"}],
        },
        "reconstruction_diagnostics": {},
        "provenance": {"provenance_refs": [], "relation_refs": []},
        "uncertainty_notes": [],
        "reconstructed_at": (now + timedelta(hours=5)).isoformat(),
    }

    hash_a = compute_replay_hash(res_a)
    hash_b = compute_replay_hash(res_b)

    assert hash_a == hash_b
    assert canonical_replay_json(res_a) == canonical_replay_json(res_b)


def test_normalize_replay_result():
    raw = {
        "as_of": "2026-10-14T12:00:00+00:00",
        "completeness": "COMPLETE",
        "reconstructed_state": {
            "phenomenon": [{"id": 10, "availability_at": "2026-10-10T00:00:00+00:00", "fidelity": "PARTIAL"}]
        },
    }
    norm = normalize_replay_result(raw)

    assert norm["as_of"] == "2026-10-14T12:00:00+00:00"
    assert norm["completeness"] == "COMPLETE"
    assert norm["content_hash"] is not None
    assert norm["reconstruction_diagnostics"]["versioning_gap"]["impact"] is not None
