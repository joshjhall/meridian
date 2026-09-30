---
type: project
title: Working positions from the user's discovery read
description: The user's solution framing (three legs, no co-pilot) and the positions revised in discussion.
status: draft
---

The user's current framing after reading the repo. Not yet decisions of record; the repo's `memory/decisions.md` is the engagement's (FDPM's) log and should not carry these.

**Three legs, not a co-pilot agent:**

1. **Ingestion:** clean up fax/OCR and phone-transcript intake; flag low-confidence and missing fields. Moving fax senders to the portal is a parallel, ops-owned track.
2. **Prioritization / routing:** replace round-robin with ordering by age and SLA; rebuild the review flag against the 500 calibration labels; route complex and bodily-injury claims to seniors.
3. **Work augmentation / training:** a prepared brief on claim open (summary, injury timeline, suggested questions), delivered via a ClaimsPro note or a browser overlay, not an eighth screen. Precedent search and complex write-ups come in wave two.

Across all three: the five-field audit record, a human-readable rationale, drift monitoring.

**Positions revised in discussion:**

- **Auto-approve dropped** in favor of a **one-click human-confirmed fast lane**. Auto-approval is fully automated adjudication, barred without consent in 8 untracked states and over $10K in 12 states.
- **Assume no consent anywhere.** Consent is untracked and untrustworthy (Michael), so no claim is ever fully automated. No consent does *not* mean the claim needs the extra review tier; keep it out of the review-floor numbers.
- **Skill-based routing raised from P3 to P2.** The floor is not flat (12 seniors, 4 leads), and IS-CLM-2025004222 lost ~4 days in senior review.
- **Moving fax to the portal is a component, not the answer.** It saves ≤8.8% of blended cost even at 100% (extract).
- The AI never recommends a denial. It may surface evidence for a human to judge (pending open question C4).

**Integration path (the user's five-path framing):** 1 (replace the UI, ClaimsPro as backend) and 3 (replace ClaimsPro) are rejected; 2 (vendor extension SDK) is unlikely but being asked. Prototype focus is **4 (write into existing fields: notes, custom fields) + 5 (browser-extension overlay keyed on the claim ID in the URL)**. Deciding questions: I1–I8 in `docs/discovery/open_questions.md`.

**Why:** Future sessions should build on these positions rather than re-derive or contradict them.

**How to apply:** Treat these as the default design direction. The open questions in `docs/discovery/open_questions.md` (C3, C4, M4, M7, T2) can still move them; if an answer lands, update this file.
