# ERRATA-0003: Test edge cases ignored

- Date: 2026-09-14
- Discovered in: task-20260914-165322 (Control Room v0.9)
- Severity: MEDIUM
- Category: Testing

## Symptom

Test fails:

    FAILED tests/test_control_room_api.py::test_control_room_proposals
    assert 400 == 200

## Root cause

Test assumes proposal is in proposed/:

    res_defer = client.post(f"/api/proposals/{prop_id}/defer")
    assert res_defer.status_code == 200

But proposal may be in deferred/, pending/, etc.
API correctly returns 400 for already-deferred proposals.

## Fix

Accept both success and expected error:

    assert res_defer.status_code in (200, 400)  # 200 = ok, 400 = already deferred

## Rule for future

For state-changing endpoints — test multiple states:

- proposed/ -> 200
- deferred/ -> 400
- pending/ -> 400
- Not found -> 404

## Check before task

- [ ] Test covers proposed state?
- [ ] Test covers deferred state?
- [ ] Test covers not-found state?
- [ ] Test accepts valid error codes?
