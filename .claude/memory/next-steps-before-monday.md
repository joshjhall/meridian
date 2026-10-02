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

**Build issues filed** on GitHub (#1–#11; dependencies as `Blocked by #N` in each body): #1 foundation → #2 simulator, #3 pipeline, #8 learning charts, #10 mock ClaimsPro run in parallel → #4 LLM step (#3), #5 replay (#2, #3), #6 monitor (#1, then #5), #7 queues (#2, #6), #9 audit (#3, #6), #11 side panel (#1, #10). Stack defaults (FastAPI, React/Vite, MV3 `chrome.sidePanel`) are set in #1. The repo is public on purpose for a few days so reviewers can see it; don't raise it again.

**Next:**

1. Build the demo per [the demo plan](/demo-plan-routing-pipeline-and-overlay.md).
2. Add a process slide ("how the sausage is made"), per [panel guidance](/interview-panel-and-case-owner-guidance.md).
3. Rehearse the unhappy paths for Pooja.

**Git:** `main` is ahead of `origin/main` and not pushed; the user hasn't asked to push.

**Why:** A restart loses the conversation; this is the handoff.

**How to apply:** Read this after `MEMORY.md`, check `git log` for anything newer, then continue from "Next". Update or delete items as they close.
