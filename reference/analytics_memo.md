# Claims Extract — Findings Memo
## Meridian Holdings, Insurance Services Analytics

> **Classification:** Confidential | Internal analysis, shared with the Tribe engagement team at kickoff (per Michael Torres, VP Engineering)
> **Basis:** `claims_processing.csv`, a stratified 5,000-claim extract from Snowflake, prepared shortly before engagement kickoff. Masked for sharing: policyholder fields removed, claim IDs renumbered, adjusters pooled into shared codes (see the data dictionary).

This memo presents what the extract supports. It makes no recommendation. The analytics group's read is that where to intervene is an operations and product question, not a data question. Numbers below are computed directly from the extract and are reproducible from it.

## The cycle-time lever is queue wait, not adjuster speed

Average total cycle is 66.8h. Of that, queue wait is 50.7h and actual handling is only 16.1h; wait is 76% of the cycle. Claims spend more than three-quarters of their life waiting to be picked up, so the cycle-time problem is a routing and triage problem, not an adjuster-speed problem. Making adjusters faster barely moves a number that is 76% wait; the lever is how claims are assigned and prioritized before anyone touches them.

## The review flag is where cost hides

The flag over-fires. 46% of all 5,000 claims are flagged for human review, but in the calibration sample (the 500 manually re-reviewed claims whose labels ship with the extract), 237 were flagged and only 58% of those actually needed review, so about 42% of flagged-and-labeled claims were unnecessary human touches. Only 37% of all flagged claims are required to have a human by regulation, so tightening what triggers the flag is a large, addressable chunk of the BU's 45%-to-20% flag-rate target.

## Channel mix explains the cost spread

Cost per claim splits hard by intake channel. E-Portal runs $427.5 and is the largest channel at 42.5% of volume; Phone runs $653.1 (about 1.5x e-portal) at 30.1%; Fax/EDI is close behind at $608.7 (27.4%). The two high-cost channels together are roughly 57% of all claims, so blended cost/claim is dominated by how much volume sits in phone and fax/EDI. Either shifting intake toward e-portal or collapsing the handling cost of the phone/fax path is a direct lever on the -25% cost target. One qualitative note the extract cannot show (it carries no sender field): fax volume is concentrated; a handful of provider networks and repair-shop chains account for a large share of it.

## The 2021 eligibility score is not usable as-is

One caveat on the extract, so nobody builds on it by accident: none of the cuts above use `automation_eligibility_score`. Claims operations has learned to work around it, and the calibration labels back them up. The labels come from a one-time Q4 2025 test in which claims operations manually re-reviewed a 500-claim random sample against the score (a handful of the sampled claims were still open at the time of the test). 131 of the 500 labeled claims score >=70, nominally automation-ready, and 16.8% of those actually needed review. The score also falls as claim amount rises (correlation -0.38); in practice it is an amount proxy that never sees complexity, not a measure of automatability. Treat it as a rebuild candidate (the labels now exist), not as an input.

## Speed alone will not carry satisfaction

CSAT falls only slightly with cycle time: claims resolved in under 24h average 3.24, claims over 72h average 3.14, a 0.1-point spread against a 3.2-to-4.0 goal. Disposition is the stronger driver: denied claims average 2.24 and paid-in-full claims 3.65. And 41% of claims carry no CSAT response at all, so every figure here is a respondents-only read. Pulling wait down should help at the margin, but the satisfaction goal will move on decision quality and communication, not speed alone.

## Known limits of this analysis

- **Trusted labels.** The BU still does not have a trusted set of reviewed claims to test anything against — no ground truth for "should this have been automated / flagged / denied." The 500-claim calibration sample is a start, but it is small, two quarters old, and was not built as an evaluation set. Any validated automation would need one stood up with claims operations.
- **What drives the 50.7h queue.** This analysis has not decomposed whether the wait is staffing, assignment logic, intake batching, or backlog. It is the biggest single number in the extract, and its mechanism is not established here.
- **The regulatory floor.** Which claim types and states must stay in human review by regulation, and where exactly that line sits, is not mapped in this memo. That floor sets a ceiling on how far the flag rate can actually fall.
