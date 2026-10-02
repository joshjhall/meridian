---
type: project
title: Where the work stands, and next steps before the Monday session
description: What's done, what's open, and what to do next; update as items close.
stale_check: "check git log and docs/presentation/ for progress since this was written"
---

**Done:**

- Questions doc with the clarification-call answers: `docs/discovery/open_questions.md`
- Analysis script, sections 1-9: `analysis/review_floor.py`
- Slides draft (5 slides plus demo plan): `docs/presentation/slides_draft.md`

The user will move the slides into Keynote.

**Slide order (revised):** 1 POV → 2 regulatory gap (437 = 85 + 352) → 3 SOW targets → 4 five approaches (the box) → 5 what we're not building yet → 6 stakeholders and flows → 7 first pass → 8 process → demo. The demo plan section in the slides draft is marked pending until the monitor paradigm is settled.

**Open decisions:**

- LLM provider for the demo: either approved provider works (decision 5).
- API key: none set; source it from 1Password like the other secrets.
- Whether to add a before/after slide on the second-year adjuster's day, for Nikolina's user-journey questions. Slide 5 partly covers it.

**Build issues filed** on GitHub (#1–#11; dependencies as `Blocked by #N` in each body): #1 foundation → #2 simulator, #3 pipeline, #8 learning charts, #10 mock ClaimsPro run in parallel → #4 LLM step (#3), #5 replay (#2, #3), #6 monitor (#1, then #5), #7 queues (#2, #6), #9 audit (#3, #6), #11 side panel (#1, #10). Stack is all Python (decisions 7 and 8): FastAPI + Jinja/HTMX pages, Basecoat + Tailwind, LangGraph, D3, a thin MV3 extension; the mock ClaimsPro page is plain unstyled HTML. #1 merged as PR #12; follow-ups filed: #13 (demo clock), #14 (CI, none exists yet). The repo is public on purpose for a few days so reviewers can see it; don't raise it again.

**Devcontainer:** the demo is pinned to Python 3.14 (`demo/backend/.python-version`, `requires-python >=3.14`); the old `.venv` was built on Debian's /usr/bin 3.13. Upstream issues filed on joshjhall/containers: #1000 (pyright downloads its own Node at runtime; the fix should make Node an implicit dependency of python-dev) and #1001 (the `test-python-dev` script is missing). Once a fix lands, bump the `containers` submodule.

**Next:**

1. Build the demo per [the demo plan](/demo-plan-routing-pipeline-and-overlay.md).
2. Add a process slide ("how the sausage is made"), per [panel guidance](/interview-panel-and-case-owner-guidance.md).
3. Rehearse the unhappy paths for Pooja.

**Git:** `main` is in sync with `origin/main`.

**Why:** A restart loses the conversation; this is the handoff.

**How to apply:** Read this after `MEMORY.md`, check `git log` for anything newer, then continue from "Next". Update or delete items as they close.
