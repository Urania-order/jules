# ERRATA-0001: Frontend API_BASE mismatch

- Date: 2026-09-14
- Discovered in: task-20260914-165322 (Control Room v0.9)
- Severity: HIGH
- Category: Frontend/API integration

## Symptom

Frontend shows `Failed to fetch` in browser console.

## Root cause

Frontend used relative path:

    const API_BASE = '/api';

When frontend on localhost:3000 and API on localhost:8080:

- Request went to http://localhost:3000/api/system/status
- python -m http.server returned HTML 404
- Browser tried to parse HTML as JSON -> Unexpected token

## Fix

Use absolute URL for localhost:

    const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? 'http://localhost:8080/api'
        : '/api';

## Rule for future

When frontend and API on different ports — ALWAYS use absolute URL.
NEVER use relative /api path if ports differ.

## Check before task

- [ ] Frontend port: ______
- [ ] API port: ______
- [ ] If different — API_BASE is absolute URL?
- [ ] Verified in browser (no Failed to fetch)?
