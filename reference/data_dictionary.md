# Meridian Insurance Services — Claims Data Dictionary
## File: claims_processing.csv (5,000 rows)

Field definitions for the historical claims extract from the Insurance Services BU. Fields
are listed in column order.

---

### claim_id
Unique claim identifier. Format: `IS-CLM-YYYYXXXXXX`. The extract's masking step renumbered
identifiers into a contiguous range (the same mapping is applied across all engagement
materials), so numeric order carries no information; do not treat ID order as filing order.

---

### filed_date
Date the claim was submitted. Format: YYYY-MM-DD. All records in this extract fall in 2025.

---

### claim_type
Type of insurance claim.
Values: Collision, Comprehensive, Bodily Injury, Property Damage, Liability.

---

### state
US state where the claim was filed. 20 states represented. State affects regulatory
handling of a claim; see the compliance floor in the engagement context file (AGENTS.md).

---

### intake_channel
How the claim entered the system.
Values:
- E-Portal — policyholder/agent web submission (~$430 fully loaded cost)
- Phone — call center agent entry (~$650 fully loaded cost)
- Fax/EDI — partner provider submissions (~$610 fully loaded cost)

Fax/EDI records carry known data-quality issues: ~8% inconsistent EDI coding, ~12% missing
fields, and ~78% OCR accuracy on faxed documents.

---

### cost_per_claim_usd
Fully loaded cost to process this claim, in USD, including labor, system costs, and overhead.
Reflects actual handling complexity rather than a fixed per-channel rate: a simple and a
complex claim in the same channel can carry very different costs. Range: $140–$1,491.

---

### claim_amount_usd
Dollar value of the claim submitted by the policyholder. This is what is claimed, not what
was paid out. Range: $250–$85,000.

---

### complexity
Adjuster-assigned complexity classification, recorded at time of review.
Values: Simple, Moderate, Complex.

---

### automation_eligibility_score
Rules-based score (0–100) produced by the triage engine, deployed 2021. Higher = more
eligible for auto-adjudication. Observed range: 5–99. Known calibration issues: never
recalibrated since deployment; the Q4 2025 calibration sample (`review_actually_needed`)
measures its divergence from reviewer judgment. See the caveat in `analytics_memo.md`.

---

### flagged_for_human_review
Whether the current rules engine routed this claim to a human adjuster for review.
Values: Yes / No. Approximately 45% of records are flagged.

---

### requires_human_by_regulation
Whether the claim requires human review under state insurance regulations, regardless of
system recommendation. Values: Yes / No. About 25% of records in this extract are so
regulated.

---

### queue_wait_hours
Time the claim spent waiting in queue before an adjuster picked it up, in hours. A component
of total_cycle_time_hours. Range: 3–465 hours.

---

### handling_hours
Elapsed wall-clock time the claim spent in active-handling statuses, in hours; excludes
queue wait. This measures how long the claim was open with an adjuster, not continuous
adjuster effort; a claim can sit in an active status between touches. Range: 0.8–142 hours.

---

### total_cycle_time_hours
Total tracked cycle time: queue_wait_hours + handling_hours, in hours. For claims still
pending at extract time, this is the time accrued so far; time spent suspended (e.g.,
awaiting documentation from a claimant) is not tracked. Totals may differ from the sum of
the components by up to 0.1h due to rounding. Range: 4–507 hours.

---

### disposition
Final outcome of the claim.
Values: Paid in Full (46%), Partial Payment (21%), Denied (17%), Settled (12%),
Pending Review (3%).

---

### denial_reason
Reason for denial. Populated only when disposition = Denied; blank for all other claims.
Values: Insufficient documentation, Fraud suspected, Filing deadline missed, Policy lapsed,
Pre-existing damage, Exceeded policy limit, Coverage exclusion.

---

### adjuster_id
Anonymized adjuster identifier. Format: `ADJ-XXX`. The masking step pools the BU's 95
adjusters into 50 shared codes (each adjuster maps to exactly one code, but most codes
cover more than one adjuster), so per-adjuster workload cannot be read from this field.

---

### document_count
Number of documents attached to the claim. Range: 1–18.

---

### customer_satisfaction_1to5
Post-resolution CSAT score provided by the policyholder. Scale: 1–5. Approximately 41% of
records have no CSAT score (likely non-respondents), so aggregate figures may not represent
the full population.

---

### review_actually_needed
Outcome of manual re-review: whether a human review was actually necessary. Values: Yes / No.
Populated only for the 500 claims in the Q4 2025 calibration exercise; blank for all other
records. This is the last column in the file.
