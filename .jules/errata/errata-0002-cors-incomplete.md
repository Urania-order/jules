# ERRATA-0002: CORS middleware missing

- Date: 2026-09-14
- Discovered in: task-20260914-165322 (Control Room v0.9)
- Severity: HIGH
- Category: Frontend/API integration

## Symptom

Frontend gets CORS error:

    Access to fetch at http://localhost:8080/api/... from origin
    http://localhost:3000 has been blocked by CORS policy

## Root cause

FastAPI had:

    from fastapi.middleware.cors import CORSMiddleware

But NO:

    app.add_middleware(CORSMiddleware, ...)

Import alone does nothing. Middleware MUST be added.

## Fix

    app = FastAPI(title="Co-SMOS Control Room API", version="0.9")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

## Rule for future

CORS = import + add_middleware.
Both are required.
Verify with curl -I -H "Origin: http://localhost:3000" ...

## Check before task

- [ ] CORS import present?
- [ ] app.add_middleware(CORSMiddleware, ...) present?
- [ ] Verified with curl
- [ ] Response has access-control-allow-origin header?
