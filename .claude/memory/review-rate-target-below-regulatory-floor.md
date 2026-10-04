---
type: project
title: The <20% review-rate target depends on which regulation data you trust
description: Reachable under the stated $10K-and-state rule (floor 12.9%), not as the extract labels it (25.4%).
stale_check: "re-run python3 analysis/review_floor.py; sections 1-4 use the labels, section 9 the stated rule"
---

The SOW's review-rate target (45% → <20%, `docs/project/sow.md:18`) has two answers, depending on the regulation data:

- **Stated rule** (case owner, clarification call): `requires_human_by_regulation` = over $10K in one of 12 states. Floor **12.9%**, so <20% is reachable only by cutting the *need* for second opinions. A perfect second-opinion flag still puts total review at ~39%.
- **As labeled in the extract:** floor **25.4%**. It matches the rule in the 12 states but adds 628 unexplained regulated claims (~30%) in the other 8. Likely planted or an artifact; present it as a finding.
- **85 claims** meet the stated rule and have the regulation flag set, but not the review flag. If routing uses only the review flag, they skipped a required review. The case owner called this "an error".
- **Quick win to open with:** route on either flag. It closes a regulatory gap before any AI is built, but it *raises* the flag rate. It's Meridian's change to make (legacy SaaS, CAB); take it to Michael privately first. Engineering must confirm how routing filters (M14).
- **The 628 unexplained labels:** readings ranked by fit are legacy rules still running, then one shared unstated rule, then conflicting rules. The ~30% is uniform across all 8 states.

Full argument and caveats: "Review floor, revised" in `docs/discovery/open_questions.md`.

**Why:** The panel expects the candidate to say whether the goals are realistic, unprompted. The honest answer is "possible under the rule you gave us, but not by removing false alarms alone, and your data disagrees with your rule."

**How to apply:** Raise it early in the presentation, unprompted: open on the quick win, then realism. The user's view: <20% was set to be near-impossible, with a narrow theoretical path that isn't realistic in six months on a legacy system. Lead with reading A (the stated rule) and show the data gap as a finding. Frame the design goal as fewer *needed* second opinions: better-prepared claims plus right-first-time routing. Quote the script's output rather than restating numbers from memory.

**Proposed alternative target, spoken only (2026-10-03):** the user proposes a <20% *second-opinion* rate as the alternative SOW target: "not 100% certain it's realistic, but more realistic than any of the current SOW targets". The demo's learning-loop routing box charts it, going from 34.8% to 19.4% (`demo/data/history.json`, routing `tertiary`). 34.8% is an illustrative midpoint the user will explain live. The extract measures the bounds: at least 28.9% (flagged, not regulation-required) and at most 45.6% (all flagged). The true union also counts regulated claims with 2+ reviewers, and the extract has no reviewer count. The user chose to say this out loud rather than put it on a slide, so the deck's 26% / 34% second-opinion figures are deliberately left as they are. Don't "fix" the deck to match the chart.
