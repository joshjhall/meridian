# Meridian demo

A running demo of the claims pre-processing and routing pipeline, an admin monitor, a mock ClaimsPro screen, and a Chrome side panel. Built from the GitHub issues #1–#11; `docs/presentation/panel_examples.md` is the side-panel spec.

## Run

Prerequisite: [uv](https://docs.astral.sh/uv/). It installs Python 3.12+ if needed.

```bash
cd demo
make dev    # API and pages on http://localhost:8000
make test   # pytest: fixtures, roster, API, pages
make css    # rebuild Tailwind utilities (make dev watches)
make data   # regenerate claim fixtures and roster
```

Then open:

- <http://localhost:8000/admin>: admin monitor (#6, #7, #8, #9)
- <http://localhost:8000/claimspro/IS-CLM-2025004222>: mock ClaimsPro (#10)
- <http://localhost:8000/panel?claim=IS-CLM-2025004222>: side panel (#11)

## Stack

One language, Python, end to end. The only JavaScript is the extension glue and small browser libraries loaded from a CDN.

| Piece | Tech | Where |
|---|---|---|
| API and pages | Python 3.12+, FastAPI, Pydantic, Jinja2; uv | `backend/` |
| Components | [Basecoat](https://basecoatui.com) 1.0.2: shadcn/ui as plain HTML + Tailwind, from a CDN | `backend/templates/components/` (Jinja macros) |
| Styling | Tailwind CSS v4 utilities, built by the standalone CLI (`pytailwindcss`, no Node) | `backend/styles/app.css` → `backend/static/app.css` |
| Interactivity | HTMX, server-sent events, CSS transitions | `backend/templates/`, `backend/static/` |
| Charts | D3, from a CDN, fed JSON by the API | `backend/static/` (from #8) |
| Pipeline | LangGraph: one node per stage, each emitting a `PipelineEvent` | `backend/` (from #3) |
| Extension | Chrome MV3, `chrome.sidePanel`; embeds `/panel` | `extension/` |

Why Python: Meridian's ML platform is Databricks with MLflow, which can trace LangGraph runs and log a graph as a model, so the demo pipeline is the shape a production one would take. LangGraph's Python library is its primary implementation. One language also means one schema: the Pydantic models are used directly by the API, the templates and the pipeline.

## Layout

- `backend/models.py`: the shared contracts and **the only schema**: `Claim`, `Skill`, `Tier`, `Stage`, `Adjuster`, `PipelineEvent`, `AuditRecord`, `PanelSummary`.
- `backend/fixtures.py`: `load_claim_fixtures()` and `load_roster()`, validated through the models.
- `backend/app.py`: the JSON API (`/api/health`, `/api/claims`, `/api/claims/{id}`, `/api/roster`) and the pages (`/admin`, `/claimspro/{id}`, `/panel`).
- `backend/templates/` and `backend/static/`: Jinja templates and CSS. `templates/components/` holds Basecoat's Jinja macros (MIT; see `BASECOAT_LICENSE.txt`) for its interactive components (tabs, dialog, dropdown, select, popover, toast and others).
- `backend/styles/app.css`: Tailwind input. The built `static/app.css` is committed so a fresh clone runs without a CSS build; run `make css` after changing classes.
- `data/claims/*.json`: the six side-panel claims. Each is a `ClaimFixture`: the `claim` plus an `expected` block (skills, tier, regulated, routing reason, SLA state) from the spec, for the pipeline to test against.
- `data/build_claims.py`: builds the fixtures. Numbers come from `reference/claims_processing.csv`; intake details and stories come from an overlay in the script.
- `data/roster.json` and `data/gen_roster.py`: the seeded roster.
- `extension/`: the MV3 side panel. It embeds the backend's `/panel` page.

## Contracts and conventions

- Add new shared shapes to `models.py`. Don't define a local claim, event or audit shape anywhere else.
- Skill, Tier and Stage are enums. Iterate them instead of listing members, so a fourth or fifth tier means editing only `models.py`.
- ClaimsPro custom fields (`skills`, `tier`, `routing_reason`, `review_lane`, `brief_status`) are empty in the fixtures; the pipeline (#3) fills them. `sla_due_at` is computed: `received_at` + 24h.
- Pages are server-rendered. Reach for HTMX or a small script before adding a JavaScript framework.
- Use Basecoat's classes (`btn`, `card`, `badge`, `alert`, `table` and so on) and its Jinja macros before hand-styling a component, and Tailwind utilities for layout. Load order matters: Basecoat's stylesheet first, then `app.css`. `base.html` already does this.
- Basecoat sets up components inside HTMX swaps by itself. `base.html` forces a reset after an HTMX history restore.

## Assumptions

- **SLA:** 24 hours from receipt. Real claims use the "Received" timestamp in their `status_history.md`; synthetic claims use 09:00 on the filed date.
- **Skills and tier** are assigned in pre-processing and stored as ClaimsPro custom fields.
- **Roster is synthetic:** 95 adjusters. The extract pools them into 50 codes (`ADJ-101`–`ADJ-150`); the demo treats each code as one person and adds `ADJ-151`–`ADJ-195`. 79 work at T1–T2; 16 are T3 (12 seniors and 4 leads), all carrying Bodily Injury. The seed is 2025.
- **Synthetic claims** (0375, 4518, 2043) carry `synthetic: true`. Their numbers are real extract rows; their stories are written for the demo.
- **Claim 4222's medical summary** is hand-transcribed into `details.medical_summary`, because the PDF is a scan with no text layer.
