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

**Slide order:** 1 regulatory gap → 2 SOW targets read honestly → 3 five legacy approaches → 5 stakeholders, flows and OKRs → 4 first-pass focus → demo.

**Open decisions:**

- LLM provider for the demo: either approved provider works (decision 5).
- API key: none set; source it from 1Password like the other secrets.
- Whether to add a before/after slide on the second-year adjuster's day, for Nikolina's user-journey questions. Slide 5 partly covers it.

**Next:**

1. Build the demo per [the demo plan](/demo-plan-routing-pipeline-and-overlay.md).
2. Add a process slide ("how the sausage is made"), per [panel guidance](/interview-panel-and-case-owner-guidance.md).
3. Rehearse the unhappy paths for Pooja.

**Git:** `main` is ahead of `origin/main` and not pushed; the user hasn't asked to push.

**Why:** A restart loses the conversation; this is the handoff.

**How to apply:** Read this after `MEMORY.md`, check `git log` for anything newer, then continue from "Next". Update or delete items as they close.
