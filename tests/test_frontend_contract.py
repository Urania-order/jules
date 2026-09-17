import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from smos.api.main import app

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
        ".stage-card",
        ".stage-list",
        ".stage",
        ".stage-active",
        ".stage-done",
        ".stage-failed",
        ".stage-unknown",
        ".sequence-item",
        ".seq-time",
        ".seq-id",
        ".seq-state",
        ".seq-priority",
        ".lever",
        ".lever-name",
        ".lever-state",
        ".lever-cycle",
        ".led",
        ".led-green",
        ".led-yellow",
        ".led-red",
        ".led-off",
        ".task-card",
        ".task-card-hover",
        ".task-priority-badge",
        ".why-preview",
        ".why-preview-visible",
        ".task-edit-modal",
        ".task-edit-input",
        ".batch-select",
        ".batch-status",
        ".consult-endpoint",
        ".consult-led",
        ".reset-confirm",
        ".template-card",
        ".template-list",
        ".consult-tab",
        ".consult-settings",
        ".consult-audit-row",
        ".token-status",
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


def test_frontend_contract_control_panel_elements():
    """Verify Control Panel & UX contract elements added in v0.9 patch."""
    content = INDEX_PATH.read_text()

    # 1. Command Intake
    assert 'id="view-command-intake"' in content
    assert 'data-view="command-intake"' in content
    assert 'id="command-input"' in content
    assert 'id="command-priority"' in content
    assert 'id="command-submit"' in content

    # 2. Stages
    assert 'id="view-stages"' in content
    assert 'data-view="stages"' in content
    assert 'stage-card' in content
    assert 'stage-list' in content
    assert 'stage-active' in content
    assert 'stage-done' in content
    assert 'stage-failed' in content

    # 3. Sequence
    assert 'id="view-sequence"' in content
    assert 'data-view="sequence"' in content
    assert 'sequence-list' in content
    assert 'sequence-item' in content

    # 4. Cycles
    assert 'id="view-cycles"' in content
    assert 'data-view="cycles"' in content
    assert 'data-lever=' in content or 'lever' in content

    # 5. LEDs
    assert 'led-green' in content
    assert 'led-yellow' in content
    assert 'led-red' in content
    assert 'led-off' in content

    # 6. Task Card UX & Edit Modal
    assert 'task-card' in content
    assert 'task-priority-badge' in content
    assert 'why-preview' in content
    assert 'why-preview-visible' in content
    assert 'task-edit-modal' in content or 'task-edit-modal-overlay' in content
    assert 'id="task-edit-request"' in content
    assert 'id="task-edit-priority"' in content
    assert 'id="task-edit-save"' in content
    assert 'id="task-edit-cancel"' in content
    assert 'card.draggable = true' in content or 'draggable' in content
    assert 'contextmenu' in content
    assert 'Control' in content or 'isCtrlPressed' in content or 'Control' in content

    # 7. Parallel Batch
    assert 'id="view-batch"' in content
    assert 'data-view="batch"' in content
    assert 'id="batch-schedule"' in content
    assert 'id="batch-concurrency"' in content
    assert 'id="batch-run"' in content
    assert 'id="batch-status"' in content
    assert 'batch-select' in content

    # 8. Consult View
    assert 'id="view-consult"' in content
    assert 'data-view="consult"' in content
    assert 'consult-endpoint' in content
    assert 'consult-led' in content


def test_frontend_contract_v1_1_elements():
    """Verify v1.1 Frontend Contract elements: Reset Queues button, Extended Task Edit modal, Remember Task modal, and Templates UI."""
    content = INDEX_PATH.read_text()

    # 1. Reset Queues Button & Modal
    assert 'id="btn-reset-queues"' in content
    assert 'id="reset-confirm-input"' in content or 'RESET' in content

    # 2. Extended Task Edit Modal Fields
    assert 'id="task-edit-request"' in content
    assert 'id="task-edit-priority"' in content
    assert 'id="task-edit-status"' in content
    assert 'id="task-edit-notes"' in content
    assert 'id="task-edit-tags"' in content

    # 3. Remember Task Modal & Inputs
    assert 'id="task-remember-modal"' in content
    assert 'id="task-remember-name"' in content

    # 4. Templates View & Cards
    assert 'id="view-templates"' in content
    assert 'data-view="templates"' in content
    assert 'template-card' in content
    assert 'template-list' in content
    assert 'id="template-list"' in content


def test_frontend_contract_consult_tuning_elements():
    """Verify Consult Tuning contract elements: consult tabs, settings panel, tokens UI, rate limits UI, endpoint toggles UI, and audit log list."""
    content = INDEX_PATH.read_text()

    # CSS classes
    assert '.consult-tab' in content
    assert '.consult-settings' in content
    assert '.consult-audit-row' in content
    assert '.token-status' in content

    # Tabs
    assert 'switchConsultTab' in content
    assert 'data-tab="endpoints"' in content
    assert 'data-tab="settings"' in content
    assert 'data-tab="audit"' in content

    # Settings panel elements
    assert 'view-consult-settings' in content
    assert 'id="consult-tokens-list"' in content
    assert 'id="rate-limit-consultant"' in content
    assert 'id="rate-limit-operator"' in content
    assert 'id="consult-toggles-list"' in content

    # Audit elements
    assert 'id="consult-audit-list"' in content


def test_consult_endpoints_read_only():
    """Verify backend consult endpoints exist and strictly reject state-modifying HTTP methods."""
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-consultant-token"}

    consult_routes = [
        "/api/consult/state",
        "/api/consult/tasks",
        "/api/consult/events",
        "/api/consult/errata",
        "/api/consult/health",
    ]

    for route in consult_routes:
        res = client.get(route, headers=headers)
        assert res.status_code == 200, f"GET {route} failed with {res.status_code}"

        # Assert POST / PATCH / DELETE / PUT are not allowed or rejected (405 Method Not Allowed or 403 Role Forbidden)
        post_res = client.post(route, json={"test": "data"}, headers=headers)
        assert post_res.status_code in (405, 404, 403), f"POST {route} did not reject with 405/404/403"

        patch_res = client.patch(route, json={"test": "data"}, headers=headers)
        assert patch_res.status_code in (405, 404, 403), f"PATCH {route} did not reject with 405/404/403"

        delete_res = client.delete(route, headers=headers)
        assert delete_res.status_code in (405, 404, 403), f"DELETE {route} did not reject with 405/404/403"
