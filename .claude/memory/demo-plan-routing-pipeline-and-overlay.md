---
type: project
title: Demo plan: routing pipeline in LangGraph plus a mocked overlay
description: The agreed 2-3 hour demo cut, the one live LLM node, and how it's contained.
status: draft
---

Agreed scope for the demo (full detail in `docs/presentation/slides_draft.md`, "Demo plan"):

- **One claim, one adjuster, end to end:** IS-CLM-2025004222, the second-year adjuster's NY bodily-injury claim ($59.5K, 117h queue wait, 4 days in senior review, injury timeline built by hand).
- **Builds (~2h50 total):**
  - queue view with reason chips (~30 min)
  - routing pipeline (~60 min)
  - mocked ClaimsPro page with the overlay (~45 min)
  - custom-field write-back (~15 min)
  - one correction loop that catches the 84 similar claims (~20 min; cut to a static before/after if short on time)
- **Not building:** a real browser extension, live ClaimsPro API calls, multiple users.
- **Routing pipeline in LangGraph, justified by decomposition:** four dimensions in parallel feed a merge node, then a validate node. The four are regulatory (code), urgency (code), complexity signals (the **only LLM node**; reads notes and transcript, quotes its source) and adjuster fit (code). Validate fails safe to a human queue. The user's framing: production routing is discrete code plus LLM calls for ambiguity. Python or TypeScript is enough at ~1,100 claims/day. Add a rules engine only if Compliance must edit rules themselves.
- **Containing the live call:**
  - schema-validated output only
  - every quote checked against the source
  - no approve/deny field in the schema
  - PII masked
  - recorded fallback on failure or timeout (~20s)
  - one button-triggered call
  - five-field audit record written per run
  - Bifrost as a local gateway only if it takes ≤15 min to set up; otherwise call the provider directly

**Why:** The case owner advised going deep on one journey. Pooja asks about the hardest part and the unhappy paths, and the live node gives engineers something real to inspect.

**How to apply:** Build in this order: pipeline, then overlay, then queue, then fields, then the loop. Keep the LLM confined to the one node. See [next steps](/next-steps-before-monday.md) for open decisions.
