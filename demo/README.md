# Meridian demo

A running demo of the claims pre-processing and routing pipeline, an admin monitor, a mock ClaimsPro screen, and a Chrome side panel. Built from the GitHub issues #1–#11; `docs/presentation/panel_examples.md` is the side-panel spec.

## Run

Prerequisite: [uv](https://docs.astral.sh/uv/). It installs Python 3.14 (pinned in `backend/.python-version`) if needed.

```bash
just dev    # API and pages on http://localhost:8000
just serve  # API and pages without the Tailwind watcher
just test   # pytest: fixtures, roster, API, pages (extra args go to pytest)
just css    # rebuild Tailwind utilities (just dev watches)
just data   # regenerate claim fixtures and roster
just lint   # every linter, no changes (just fmt applies fixes; just lint-py etc. run one)
just clean  # empty the venv and remove caches (just reset also reinstalls and tests)
```

Run from anywhere in the repo; `just` lists every recipe (the justfile is at the repo root).

In the devcontainer, `backend/.venv` is a symlink to `/cache/venvs/<checkout>` on the `meridian-venvs` volume: `meridian` for the main checkout, `meridian--<worktree>` for a git worktree. That keeps venvs off the case-insensitive workspace mount and lets them survive rebuilds. To rebuild every venv, drop the volume (`docker volume rm meridian-venvs`) and run `just install`. Outside the devcontainer (CI included), `.venv` is an ordinary in-tree directory.

### Linting

| Files | Tool | Recipe | Config |
|---|---|---|---|
| Python | ruff (lint + format) | `just lint-py` | `demo/ruff.toml` |
| Python types | pyright | `just lint-types` | `backend/pyproject.toml` |
| Jinja/HTMX templates | djlint | `just lint-templates` | `backend/pyproject.toml` |
| CSS, JS | biome | `just lint-web` | `biome.json` (repo root) |
| Markdown, YAML/JSON, TOML, shell, spelling | rumdl, dprint, taplo, shellcheck/shfmt, typos | `just lint-docs`, `lint-config`, `lint-sh`, `lint-spelling` | repo root |

ruff, pyright, and djlint are pinned dev dependencies in `uv.lock` (add new Python tools with `uv add --dev`); the rest come from the devcontainer. Git hooks (`lefthook.yml`) fix and check staged files on commit and run the type check and full demo lint on push. The vendored Basecoat components in `templates/components/` are excluded.

Then open:

- <http://localhost:8000/admin>: admin monitor (#6, #8, #9)
- <http://localhost:8000/admin/queues>: every adjuster's queue, with drag-to-move and ClaimsPro write status (#7). Like the rest of the demo it is unauthenticated: `?view=admin` only gates the fault toggle for the demo. The move and toggle POSTs need an `X-Meridian-Board` header, which blocks cross-site requests, but that is not authentication, so run it locally only.
- <http://localhost:8000/claimspro/IS-CLM-2025004222>: mock ClaimsPro (#10), deliberately unstyled
- <http://localhost:8000/panel?claim=IS-CLM-2025004222>: side panel (#11)
- <http://localhost:8000/claimspro/IS-CLM-2025004222?panel=docked>: mock ClaimsPro with the panel docked beside it, a safety net for when the extension isn't loaded

### Side panel extension

In Chrome, open `chrome://extensions`, turn on Developer mode, choose **Load unpacked** and pick `demo/extension/`. With `just serve` running, open a claim at `http://localhost:8000/claimspro/{claim_id}` and click the extension's toolbar button. The panel follows the claim in the active tab, and its Contents links scroll the ClaimsPro tab to the matching screen or document. The extension has no content script: it never touches the ClaimsPro page.

## Stack

One language, Python, end to end. The only JavaScript is the extension glue and small browser libraries loaded from a CDN.

| Piece | Tech | Where |
|---|---|---|
| API and pages | Python 3.14, FastAPI, Pydantic, Jinja2; uv | `backend/` |
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
- `backend/app.py`: the JSON API (`/api/health`, `/api/claims`, `/api/claims/{id}`, `/api/roster`, `/api/history`, plus the replay's `/api/events` and `/api/replay`) and the pages (`/admin`, `/admin/queues`, `/claimspro/{id}`, `/panel`).
- `backend/replay/`: the replay runner (#5). It plays the claims extract, in filed-date order, through the real pipeline on the demo clock, and streams the events to `/admin` over SSE at `/api/events`. Speed (simulated hours per second) and pause are set with `POST /api/replay`, a restart (optional seed) with `POST /api/replay/restart`. The sequence is a pure function of the seed, so a rehearsal matches the demo. Each pass writes to one ClaimsPro simulator; `replay.current_sim()` returns the served pass's simulator (its write log and alerts) for audit views. It is replaced on restart, so read it per request.
- `backend/queues.py`: the admin queues board (#7): the board grouped by tier, the review-lane guard (the pipeline's `regulatory_check` and `assign.match` eligibility), and moves sent through `reliable_write`.
- `backend/templates/` and `backend/static/`: Jinja templates and CSS. `templates/components/` holds Basecoat's Jinja macros (MIT; see `BASECOAT_LICENSE.txt`) for its interactive components (tabs, dialog, dropdown, select, popover, toast and others).
- `backend/styles/app.css`: Tailwind input. The built `static/app.css` is committed so a fresh clone runs without a CSS build; run `just css` after changing classes.
- `data/claims/*.json`: the six side-panel claims. Each is a `ClaimFixture`: the `claim` plus an `expected` block (skills, tier, regulated, routing reason, SLA state) from the spec, for the pipeline to test against.
- `data/build_claims.py`: builds the fixtures. Numbers come from `reference/claims_processing.csv`; intake details and stories come from an overlay in the script.
- `data/roster.json` and `data/gen_roster.py`: the seeded roster.
- `data/history.json`: the mocked learning-loop history behind `/admin`'s charts (#8): weekly series from kickoff, release flags, one rollback. Week-0 values carry their sources and `tests/test_history.py` checks them; end points are targets. Illustrative, not measured.
- `backend/panel.py` and `data/panel/*.json`: the side panel's view data. The header and the pipeline's "Needs attention" items are computed; each claim's points, key facts and contents are written in its JSON file, every point linked to its source. "This is wrong", confirm and request clicks go to an in-memory correction log (`GET /api/corrections`); nothing is written to ClaimsPro.
- `extension/`: the MV3 side panel. `panel.html` iframes the backend's `/panel` page; `panel.js` reads the claim ID from the active tab's URL and navigates the tab when the panel asks.

## Contracts and conventions

- Add new shared shapes to `models.py`. Don't define a local claim, event or audit shape anywhere else.
- Skill, Tier and Stage are enums. Iterate them instead of listing members, so a fourth or fifth tier means editing only `models.py`.
- ClaimsPro custom fields (`skills`, `tier`, `routing_reason`, `review_lane`, `brief_status`) are empty in the fixtures; the pipeline (#3) fills them. `sla_due_at` is computed: `received_at` + 24h.
- Pages are server-rendered. Reach for HTMX or a small script before adding a JavaScript framework.
- The mock ClaimsPro page (`/claimspro/{id}`, #10) is plain HTML with no or minimal CSS and does not extend `base.html`, so it reads as a stand-in for Meridian's vendor system. Its custom fields are plain too: in v1 they are ClaimsPro fields, not new UI. Everything that is ours (admin views, side panel) uses Basecoat.
- The mock ClaimsPro page reads the simulator (`claimspro_sim`), not the fixtures, so pipeline writes show in its custom fields ("not yet saved" while a write is pending). `backend/claimspro_page.py` defines its anchors for the side panel's Contents links: one per screen (`#summary`, `#policy`, `#parties`, `#loss`, `#documents`, `#notes`, `#payments`, `#history`) and one per document (`#documents/{slug}`, slug from the file stem, e.g. `#documents/medical-summary`).
- Use Basecoat's classes (`btn`, `card`, `badge`, `alert`, `table` and so on) and its Jinja macros before hand-styling a component, and Tailwind utilities for layout. Load order matters: Basecoat's stylesheet first, then `app.css`. `base.html` already does this.
- Basecoat sets up components inside HTMX swaps by itself. `base.html` forces a reset after an HTMX history restore.

## Assumptions

- **SLA:** 24 hours from receipt. Real claims use the "Received" timestamp in their `status_history.md`; synthetic claims use 09:00 on the filed date.
- **Skills and tier** are assigned in pre-processing and stored as ClaimsPro custom fields.
- **Roster is synthetic:** 95 adjusters. The extract pools them into 50 codes (`ADJ-101`–`ADJ-150`); the demo treats each code as one person and adds `ADJ-151`–`ADJ-195`. 79 work at T1–T2; 16 are T3 (12 seniors and 4 leads), all carrying Bodily Injury. The seed is 2025.
- **Synthetic claims** (0375, 4518, 2043) carry `synthetic: true`. Their numbers are real extract rows; their stories are written for the demo.
- **Claim 4222's medical summary** is hand-transcribed into `details.medical_summary`, because the PDF is a scan with no text layer.
