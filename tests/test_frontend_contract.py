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
        ".sequence-template-card",
        ".record-indicator",
        ".batch-template-card",
        ".queue-column-header",
        ".queue-reset-btn",
        ".queue-reset-btn-danger",
        ".export-buttons",
        ".export-btn",
        ".export-toast",
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
    """Verify v1.1 Frontend Contract elements: Per-Column Reset Buttons, Reset Modal, Extended Task Edit modal, Remember Task modal, and Templates UI."""
    content = INDEX_PATH.read_text()

    # 1. Navbar must NOT contain RESET QUEUES topbar button
    assert 'id="btn-reset-queues"' not in content
    assert '⚠ RESET QUEUES' not in content

    # 2. Queue Management view and Reset Center buttons & Modal
    assert 'id="btn-reset-ready"' in content
    assert 'id="btn-reset-running"' in content
    assert 'id="btn-reset-review"' in content
    assert 'id="btn-reset-blocked"' in content
    assert 'id="btn-reset-completed"' in content
    assert 'id="btn-reset-all"' in content
    assert 'id="btn-reset-all-center"' in content
    assert 'id="queue-reset-modal"' in content
    assert 'id="queue-reset-confirm-input"' in content

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


def test_frontend_contract_export_archive_elements():
    """Verify archive export buttons and toast feedback contract elements exist."""
    content = INDEX_PATH.read_text()

    assert 'id="btn-export-csv"' in content
    assert 'id="btn-export-md"' in content
    assert 'id="btn-export-jsonl"' in content
    assert 'id="export-toast"' in content
    assert 'exportArchive' in content
    assert 'showExportToast' in content


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


def test_frontend_contract_sequence_and_batch_template_elements():
    """Verify Sequence recording/replay and Batch template frontend contract elements."""
    content = INDEX_PATH.read_text()

    # Sequence recorder & replay
    assert 'id="view-sequences"' in content
    assert 'data-view="sequences"' in content
    assert 'id="btn-record-start"' in content
    assert 'id="btn-record-stop"' in content
    assert 'sequence-template-card' in content or 'sequence_template_card' in content

    # Batch template
    assert 'id="btn-remember-batch"' in content
    assert 'id="batch-templates-list"' in content
    assert 'batch-template-card' in content or 'batch_template_card' in content


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


def test_frontend_contract_reset_center_elements():
    """Verify Reset Center frontend contract elements and CSS classes."""
    content = INDEX_PATH.read_text()

    # Section view and nav button
    assert 'id="view-reset-center"' in content
    assert 'data-view="reset-center"' in content

    # Tabs
    assert 'id="tab-columns"' in content
    assert 'id="tab-archive"' in content
    assert 'id="tab-undo"' in content

    # Archive list & selectors
    assert 'id="archive-list"' in content
    assert 'archive-row' in content
    assert 'archive-select' in content

    # Undo filters & matched count
    assert 'id="undo-filter-status"' in content
    assert 'id="undo-filter-from"' in content
    assert 'id="undo-filter-to"' in content
    assert 'id="undo-filter-scope"' in content
    assert 'id="undo-filter-search"' in content
    assert 'id="undo-matched-count"' in content

    # Undo buttons & Archive tab undo button
    assert 'id="btn-undo-selected"' not in content
    assert 'id="btn-undo-selected-archive"' in content
    assert 'id="btn-undo-all-matched"' in content
    assert 'Undo Filtered' in content

    # Confirm modal
    assert 'id="undo-confirm-modal"' in content
    assert 'id="undo-confirm-input"' in content

    # Required CSS classes
    css_classes = [
        ".reset-center-tabs",
        ".reset-tab",
        ".archive-list",
        ".archive-row",
        ".archive-select",
        ".undo-filters",
        ".undo-filter-row",
        ".undo-btn",
        ".undo-matched-count",
        ".schedule-card",
        ".schedule-enabled",
        ".schedule-name",
        ".schedule-scope",
        ".schedule-cron",
        ".schedule-save",
        ".schedule-delete"
    ]
    for cls in css_classes:
        assert cls in content, f"CSS class {cls} not found in frontend/index.html"

    # Scheduled tab & buttons
    assert 'id="tab-scheduled"' in content
    assert 'id="btn-add-schedule"' in content
    assert 'id="schedules-list"' in content

    # Audit tab & table elements
    assert 'id="tab-audit"' in content
    assert 'data-tab="audit"' in content
    assert 'id="reset-center-tab-audit"' in content
    assert 'id="audit-list"' in content
    assert 'audit-row' in content
    assert 'id="btn-refresh-audit"' in content


def test_frontend_contract_v1_1_1_sequence_ux():
    """Verify navbar labels, renderSequence date fallback, and prompt truncation logic."""
    content = INDEX_PATH.read_text()

    # Navbar labels and data-view values
    assert '<button class="nav-btn" data-view="sequence">Commands</button>' in content
    assert '<button class="nav-btn" data-view="sequences">Recordings</button>' in content

    # renderSequence truncation logic
    assert 'truncateTask' in content or '.substring(0, 120)' in content
    assert 'title="' in content

    # date fallback logic
    assert 'isNaN(parsed)' in content


def test_frontend_contract_truncate_task():
    """Verify truncateTask helper exists and no raw task.request || task.title displays remain in view rendering."""
    content = INDEX_PATH.read_text()

    # Check truncateTask helper definition and defaults
    assert 'function truncateTask(s, n=120)' in content

    # Ensure all task request/title view code uses truncateTask
    assert '${escapeHTML(truncateTask(task.title || task.request))}' in content

    # Ensure no raw ${escapeHTML(task.request || task.title)} remains in frontend/index.html
    assert '${escapeHTML(task.request || task.title)}' not in content


def test_frontend_contract_safe_date_and_queue_layout():
    """Verify safeDate helper function exists, raw Date calls are replaced, and Queue card layout prevents badge overlap."""
    content = INDEX_PATH.read_text()

    # 1. safeDate helper exists
    assert 'function safeDate(s)' in content
    assert "return 'N/A';" in content or "return 'N/A'" in content
    assert 'isNaN(d)' in content

    # 2. No raw new Date(task.created_at).toLocale* in view code
    assert 'new Date(task.created_at).toLocale' not in content

    # 3. No raw new Date(seq.created_at).toLocale* in view code
    assert 'new Date(seq.created_at).toLocale' not in content

    # 4. safeDate usage in Queue card and Recordings view
    assert '${safeDate(task.created_at)}' in content
    assert '${safeDate(seq.created_at)}' in content

    # 5. COMPLETED card layout (flex-wrap, task-card-actions, no text overlap)
    assert 'task-card-actions' in content
    assert 'flex-wrap: wrap' in content or 'flex-wrap:wrap' in content


def test_frontend_contract_v1_1_7_task_explorer():
    """Verify v1.1.7 Task Explorer helpers, UI controls, localStorage keys, and author badges exist."""
    content = INDEX_PATH.read_text()

    # Shared JS helpers
    assert 'function sortTasksByCreatedAt(tasks, desc = true)' in content
    assert 'function filterTasksByAuthor(tasks, author)' in content
    assert 'function searchTasks(tasks, q)' in content
    assert 'function applyTaskFilters(tasks)' in content

    # UI controls
    assert 'id="task-filter-author"' in content
    assert 'id="task-sort-order"' in content
    assert 'id="task-filter-search"' in content

    # Author dropdown options
    assert 'value="all">All authors' in content
    assert 'value="operator">🧑 operator' in content
    assert 'value="queue">⚙ queue' in content
    assert 'value="consultant">✨ consultant' in content
    assert 'value="unknown">? unknown' in content

    # Sort dropdown options
    assert 'value="desc">↓ Newest' in content
    assert 'value="asc">↑ Oldest' in content

    # LocalStorage keys
    assert 'cosmos_task_author_filter' in content
    assert 'cosmos_task_sort_order' in content
    assert 'cosmos_task_search_q' in content

    # Author badges and rendering
    assert 'formatAuthorBadge' in content
    assert '🧑 operator' in content
    assert '⚙ queue' in content
    assert '✨ consultant' in content
    assert '? unknown' in content
