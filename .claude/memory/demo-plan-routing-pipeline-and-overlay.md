---
type: project
title: Demo plan: admin/monitor app plus a Chrome side panel on a mock ClaimsPro
description: The agreed demo views, assumptions, and what each shows; supersedes the overlay-centred 2h50 plan.
status: draft
---

Revised after the restructure discussion (supersedes the earlier queue-view/overlay plan). Demo is ~20 min of the 30; slides ~10.

**Release framing:** MVP = legs 1–2 (data quality, routing), surfaced through custom fields with no adjuster UI change. The side panel is shown as the fast follow (days–weeks), built in parallel; rapid echo-back of floor feedback is part of the trust story.

**View 1: Admin / pipeline monitor** (separate full-screen app; managers + Tribe; ACL-differentiated):

- Claims animate through stages (received → validated → enriched → prioritized → assigned) from an emulated live feed; exceptions lane for fail-safes.
- All adjusters' queues; managers can move work manually while routing matures.
- Learning loop front and center: line chart of agreement-with-reviewers over time, flags at each versioned model/prompt/rule release, columns on a second axis (handling time or submit-to-response). Mocked history. No live rule/prompt editing (compliance); changes ship as versioned, auditable releases.
- Second learning-loop chart: intake quality over time, with the same release flags. Fax OCR field accuracy, starting from ~78% today, measured against adjuster-confirmed values. The EDI silent-drop rate (~12% today) can sit alongside it.
- Per-claim expanded audit record: five fields plus temporal data (opened/closed, review intervals by whom, skills/tier assigned).

**View 2: Mock ClaimsPro page + Chrome side panel** (`chrome.sidePanel`, own DOM; never covers legacy content). Navigating between claims updates the panel. Same information architecture across claims; content varies by type. Progressive-disclosure animations.

**Not building:** an adjuster queue (assume ClaimsPro's own queues), a real extension, live ClaimsPro APIs.

**Assumptions:** SLA = 24h from receipt. Each claim gets skills (array; enum = the five claim types) and a tier (enum, 3 levels to start, expandable) in pre-processing, stored as custom fields; adjuster skills/tiers are one-to-many in a small side store keyed on adjuster ID. Claim types limited to the extract's five.

**Why:** User's design decisions in discussion; the panel examples should span every skill.

**How to apply:** Build to these views; see [next steps](/next-steps-before-monday.md). Chat is P2+; if raised, claim-owned history is the user's leaning.

**Decided since:** six panel examples, one per skill (spec in `docs/presentation/panel_examples.md`). Agreement chart: line = agreement with reviewers (up), bars = average submit-to-response time (down), release flags on both. Manual queue moves show the SOAP write-verify-retry cycle (write → delayed REST read → retry N times → error to user + alert to Tribe engineering and client IT). Roster is synthetic.
