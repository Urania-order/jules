# Architectural Decision Record: ADR-0003
- **Date:** 2026-09-12
- **Task ID:** task-20260912-234853
- **Title:** Export Observatory Reports to JSON and Markdown Formats

## Context
The Observatory subsystem monitors ecosystem health, evolution history, knowledge impact rankings, forecasts, and recommendations. To support automated reporting, documentation generation, and interoperability with external tools and human reviewers, Observatory reports need to be exportable in standard formats (JSON and Markdown).

## Decisions Made
1. **Service Layer Export Methods (`ObservatoryService`)**:
   - Added `export_report_json(report: Optional[Dict[str, Any]] = None, indent: int = 2) -> str` to serialize report structures to formatted JSON strings.
   - Added `export_report_markdown(report: Optional[Dict[str, Any]] = None) -> str` to render report sections into clean Markdown tables, lists, and headings according to Observatory specifications.
   - Supported optional `report` parameter to allow formatting pre-generated reports or defaults to `generate_quarterly_report()`.

2. **FastAPI Export Endpoints (`smos/api/main.py`)**:
   - Added `GET /observatory/export/json` returning `application/json` payload via FastAPI `Response`.
   - Added `GET /observatory/export/markdown` returning `text/markdown` formatted text via FastAPI `Response`.

## Consequences
- Reports can be easily retrieved and rendered by automated agents, command line scripts, and web UI tools.
- Human reviewers can export quarterly reports into Markdown files for persistent documentation.
- Existing Observatory health metrics and quarterly report endpoints remain completely unaffected and backward-compatible.
