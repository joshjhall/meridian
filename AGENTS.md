# Meridian Engagement — Agent Context

## Project

- **Client:** Meridian Holdings — Insurance Services BU. A third-party administrator (TPA) processing ~400K commercial auto claims/year on behalf of carrier clients, with 95 adjusters.
- **Engagement:** $5M, 6-month strategic AI partnership under a signed SOW. Discovery runs weeks 1–2; delivery runs through end of month 6; a formal midpoint checkpoint at end of month 3 shapes continuation.
- **Goal:** deliver Meridian's first production AI capability against four SOW goals:
  - Cost-to-serve: $430–$650 per claim → blended −25%
  - Cycle time: 68h average → <24h for simple claims
  - Review rate: 45% flagged for human review → <20%
  - CSAT: 3.2 → >4.0

## Team

**Meridian**

- Carlos Reyes — GM, Insurance Services (executive sponsor)
- Sandra Okafor — VP Claims Operations (operational lead)
- Michael Torres — VP Engineering (systems, data, and integration; both prior AI attempts were his org's: the 2021 score that shipped and drifted, and a recent RAG effort that never converged; relays and enforces the compliance constraints)

**Tribe**

- Forward Deployed PM — day-to-day engagement lead. The repo is written from her seat: she appears in the transcripts as "You (FDPM)".
- Priya Raman — architect
- Laura Chen — GM, Commercial; engagement lead and executive point of contact; runs weekly CEO/CFO check-ins

## Current priorities

1. **Pick the direction and build the case today** — week-1 discovery is done and it's Friday. One recommendation, the reasoning, and a demo, aligned with the Tribe team at Monday morning's dry run; Tuesday it opens the two-hour client workshop.
2. **Close the remaining discovery questions** — the open items from week 1 that still block a confident scope.
3. **Agree initiative scope by end of week 2** — documented and signed by both parties, per the SOW.

## Systems snapshot

Condensed from Michael Torres's Thursday session; the full conversation is in `memory/calltranscripts/`.

- **ClaimsPro** (vendor: Veritas Systems) is the system of record for intake, triage rules, queues, workflow, and documents. Reads: REST, ~25 endpoints, documented. Writes: SOAP only, ~15 operations (notes, status, documents, workflow); no committed REST write API. Webhook is unreliable (~15-min delay, ~5% of events silently dropped). Nightly batch CSV export feeds Snowflake.
- **No API for claim decisioning.** Approvals/denials enter through the ClaimsPro UI or the batch file interface only. The gap is deliberate and will not be opened for an AI.
- **Data estate is split:** Snowflake holds structured data (claims transactions, policies, payments, reference tables); Databricks holds unstructured data (adjuster notes ~45M records, call transcripts at ~85% ASR accuracy, document OCR output, image metadata). Both key on claim ID; ad-hoc joins are routine, but no productized single-claim view exists.
- **ML/AI infrastructure:** Databricks Model Serving live (one fraud-scoring model; capacity available); MLflow registry in active use; no drift or model-performance monitoring today. LLM providers Anthropic and OpenAI are both security-assessed and approved for production; API calls route US-East; Canadian policyholder data carries residency constraints.
- **Compliance floor (non-negotiable, relayed and enforced by Michael):** AI cannot deny a claim; every denial is a human decision. 12 states (incl. CA, NY, NJ, FL, IL, PA, OH, GA) require human review of any claim decision over $10,000. 8 states prohibit fully automated adjudication without policyholder consent (not cleanly tracked; assume unavailable). Documented appeals process required everywhere; NAIC AI-bulletin commitments (bias testing, human oversight, annual reporting) apply. Every AI-assisted decision needs a five-field audit record (input data, model version, output, confidence score, human-reviewed flag) retained 7 years, with a human-readable rationale on demand. Datadog captures application events only; decision-level audit logging must be built.
- **Known debt:** fax OCR (~78% accuracy, internal 2022 build, no human check before output enters ClaimsPro); EDI parser silently drops ~12% of partner submissions with missing fields; staging runs on 3-month-old data; the 2021 automation-eligibility score is stale and distrusted (see the analytics memo's caveat and the calibration labels in the extract).
- **Capacity:** Michael's platform team (12 engineers, 4 ML/data) provides integration support only (point of contact, PR reviews, architecture guidance); no feature development.

## Repo map

- `docs/project/` — SOW, pre-engagement research notes
- `memory/calltranscripts/` — call summaries, one file per conversation
- `memory/decisions.md` — decisions of record
- `reference/` — material received from Meridian: the claims extract, its data dictionary, and the analytics findings memo
- `sample_claims/` — representative claim inputs to build and test against

## Working agreements

- `memory/` is append-only history. Add to it; do not rewrite what is already there.
- Decisions land in `memory/decisions.md`, one entry per decision, with the reasoning behind it.
- `reference/` is background material received from the client. Consult it as needed; do not exhaustively re-derive it.
- All timeline references are relative to kickoff. No absolute calendar dates.
