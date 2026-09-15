import re
from pathlib import Path
import pytest

INDEX_PATH = Path("frontend/index.html")

def test_frontend_contract_priority_normalization():
    """Verify task priority input and label are normalized to 1-5 scale."""
    assert INDEX_PATH.exists(), "frontend/index.html missing"
    content = INDEX_PATH.read_text()

    assert 'id="task-priority"' in content
    assert 'min="1"' in content
    assert 'max="5"' in content
    assert 'Priority (1-5)' in content

    # Verify no remaining 1-10 priority scale labels or inputs
    assert 'Priority (1-10)' not in content
    assert 'max="10"' not in content


def test_frontend_contract_sync_button():
    """Verify SYNC button and sync click handler exist."""
    content = INDEX_PATH.read_text()

    assert 'id="btn-sync"' in content
    assert 'SYNC' in content
    assert "btn-sync" in content
    assert "refreshData()" in content


def test_frontend_contract_queue_view_columns():
    """Verify queue presentation has 5 status columns and .queue-columns grid class."""
    content = INDEX_PATH.read_text()

    assert '.queue-columns' in content
    assert '.queue-column' in content

    for status_col in ["READY", "RUNNING", "REVIEW", "BLOCKED", "COMPLETED"]:
        assert status_col in content, f"Column status header {status_col} missing in queue view"

    # Verify PENDING is mapped into READY column
    assert "PENDING" in content
    assert "queue-list-ready" in content


def test_frontend_contract_proposal_modify_ui():
    """Verify Proposal Modify UI modal and handler function exist."""
    content = INDEX_PATH.read_text()

    assert "openModifyModal" in content
    assert "modify-modal-overlay" in content
    assert "modify-proposal-form" in content
    assert "/proposals/" in content
    assert "/modify" in content


def test_frontend_contract_offline_and_retry():
    """Verify offline listener, backend unavailable banner, and retry mechanism exist."""
    content = INDEX_PATH.read_text()

    assert "window.addEventListener('offline'" in content or "addEventListener('offline'" in content
    assert "Co-SMOS backend unavailable" in content
    assert "RETRY" in content
    assert "retryDataRefresh" in content or "refreshData" in content


def test_frontend_contract_css_classes():
    """Verify all required CSS classes exist in frontend/index.html."""
    content = INDEX_PATH.read_text()

    required_classes = [
        ".queue-columns",
        ".queue-column",
        ".error-state",
        ".loading-state",
        ".modal-overlay",
        ".modal",
        ".modal-actions",
        ".btn-sm",
    ]

    for cls in required_classes:
        assert cls in content, f"Required CSS class {cls} not found in frontend/index.html"


def test_frontend_contract_patch_b_elements():
    """Verify Patch B contract elements: history view, autonomy selector, why section, replay button."""
    content = INDEX_PATH.read_text()

    # History view checks
    assert 'data-view="history"' in content
    assert 'id="view-history"' in content
    assert '`${API_BASE}/events`' in content or '/events' in content
    assert 'renderHistory' in content

    # Autonomy selector checks
    assert 'id="autonomy-select"' in content
    assert 'value="MANUAL"' in content
    assert 'value="ASSISTED"' in content
    assert 'value="AUTO"' in content
    assert "localStorage.getItem('cosmos_autonomy')" in content or "localStorage.setItem('cosmos_autonomy'" in content

    # WHY section checks
    assert 'id="why-section"' in content
    assert 'WHY?' in content
    assert 'source_task' in content
    assert 'proposed_by' in content

    # Task detail replay checks
    assert 'id="btn-replay-task"' in content
    assert '▶ REPLAY' in content
    assert '`${API_BASE}/tasks/' in content or '/tasks/' in content
    assert '/replay' in content
    assert 'openReplayModal' in content
