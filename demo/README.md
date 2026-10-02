# Meridian demo

A running demo of the claims pre-processing and routing pipeline, an admin monitor, a mock ClaimsPro screen, and a Chrome side panel. Built from the GitHub issues #1–#11; `docs/presentation/panel_examples.md` is the side-panel spec.

## Run

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+, and pnpm.

```bash
cd demo
make dev    # backend on :8000, web on :5173 (proxies /api); Ctrl-C stops both
make test   # pytest (fixtures, roster, type parity, API) + tsc
make data   # regenerate claim fixtures and roster
```

Then open:

- <http://localhost:5173/admin>: admin monitor (#6, #7, #8, #9)
- <http://localhost:5173/claimspro/IS-CLM-2025004222>: mock ClaimsPro (#10)
- <http://localhost:5173/panel?claim=IS-CLM-2025004222>: side panel (#11)

## Stack

| Piece | Tech | Where |
|---|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic; uv | `backend/` |
| Web | React, Vite, TypeScript, react-router; pnpm | `web/` |
| Extension | Chrome MV3, `chrome.sidePanel` | `extension/` |
| Streams | Server-sent events | `backend/` (from #5) |

## Layout

- `backend/models.py`: shared contracts and **the source of truth**: `Claim`, `Skill`, `Tier`, `Stage`, `Adjuster`, `PipelineEvent`, `AuditRecord`, `PanelSummary`.
- `web/src/types.ts`: a hand-written TypeScript mirror. `backend/tests/test_types_parity.py` fails if a field or enum value drifts.
- `backend/fixtures.py`: `load_claim_fixtures()` and `load_roster()`, validated through the models.
- `backend/app.py`: API (`/api/health`, `/api/claims`, `/api/claims/{id}`, `/api/roster`).
- `data/claims/*.json`: the six side-panel claims. Each is a `ClaimFixture`: the `claim` plus an `expected` block (skills, tier, regulated, routing reason, SLA state) from the spec for the pipeline to test against.
- `data/build_claims.py`: builds the fixtures. Numbers come from `reference/claims_processing.csv`; intake details and stories come from an overlay in the script.
- `data/roster.json` and `data/gen_roster.py`: the seeded roster.
- `extension/`: MV3 manifest stub.

## Contracts and conventions

- Add new shared shapes to `models.py` first, then mirror them in `types.ts`. Don't invent a local claim, event or audit shape.
- Skill, Tier and Stage are enums. Iterate them instead of listing members, so a fourth or fifth tier means editing only `models.py` and `types.ts`.
- ClaimsPro custom fields (`skills`, `tier`, `routing_reason`, `review_lane`, `brief_status`) are empty in the fixtures; the pipeline (#3) fills them. `sla_due_at` is computed: `received_at` + 24h.

## Assumptions

- **SLA:** 24 hours from receipt. Real claims use the "Received" timestamp in their `status_history.md`; synthetic claims use 09:00 on the filed date.
- **Skills and tier** are assigned in pre-processing and stored as ClaimsPro custom fields.
- **Roster is synthetic:** 95 adjusters. The extract pools them into 50 codes (`ADJ-101`–`ADJ-150`); the demo treats each code as one person and adds `ADJ-151`–`ADJ-195`. 79 work at T1–T2; 16 are T3 (12 seniors and 4 leads), all carrying Bodily Injury. The seed is 2025.
- **Synthetic claims** (0375, 4518, 2043) carry `synthetic: true`. Their numbers are real extract rows; their stories are written for the demo.
- **Claim 4222's medical summary** is hand-transcribed into `details.medical_summary`, because the PDF is a scan with no text layer.
