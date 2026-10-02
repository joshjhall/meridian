# Side panel: six example claims

Spec for the demo's side panel: one example per skill, each showing a different situation. The structure stays the same on every claim; what fills each section changes with the claim type and its situation. Claims 0300, 4222 and 2993 use the files in `sample_claims/`. The other three are **synthetic**: the numbers come from a real extract row (`reference/claims_processing.csv`); the details are written for the demo, and the panel labels them that way.

## Shared structure (every claim)

| # | Section | Contents | Behavior |
|---|---|---|---|
| 1 | **Header** | Claim ID; skill chips; tier (T1 standard, T2 involved, T3 senior); time left on the 24h SLA; regulatory status; one-line routing reason | Always visible. SLA turns amber under 6h left and red when breached |
| 2 | **What matters** | 2–4 points, worded for this claim; one of them is what makes it unusual | Each point links to its source |
| 3 | **Key facts** | Fields chosen per claim type (templates below) | Collapsed by default when nothing is unusual |
| 4 | **Needs attention** | Missing items, conflicts between sources, low-confidence spans | Each item shows its sources side by side; one click to confirm or correct |
| 5 | **Contents** | Where each fact lives: ClaimsPro screen, document, page | Clicking navigates the ClaimsPro tab |
| 6 | **Footer** | Who has touched the claim and when; pipeline version; "this is wrong" | The flag goes to the admin view's correction log |

Rules for every panel:

- The panel never recommends approval or denial. It shows evidence for a person to judge.
- Every point links to its source. If a quote can't be matched in the source, it's marked unverified.
- The panel shows less when there's less to say. A clean claim gets a short panel.

## Key-fact templates by skill

| Skill | Key facts |
|---|---|
| Collision | Vehicles involved; point of impact; injuries (y/n); third party (y/n); estimate consistent with photos |
| Bodily Injury | Injured parties; injury timeline (date of loss, symptom onset, first treatment); treatment status; causation documents; liability |
| Comprehensive | Peril (weather, theft, glass, vandalism, fire); date and place; corroboration (police report, weather data); prior losses on the unit |
| Liability | Parties and their carriers; each party's account; fault evidence (police report, witnesses, photos); third-party demand; policy limits |
| Property Damage | Property owner; property type; damage description; estimate or invoice; insured driver's account |

## The six examples

### 1. Collision, the fast lane: IS-CLM-2025000300 (real)

FL, e-portal, $2,825, Simple, T1. Single vehicle into a parking bollard; no injuries, no third party.

- **What matters:** "Complete at intake. Estimate matches the photos. Nothing to chase." Then one-click confirm, the fast lane, never automatic.
- **Needs attention:** none. The section is hidden and the panel is short.
- **SLA:** on track (in the demo, 4h used).
- **Shows:** a clean claim gets a short panel. Over half of volume is Simple.
- Sources: `sample_claims/IS-CLM-2025000300/intake.md`, `adjuster_notes.md`.

### 2. Bodily Injury, the hard call: IS-CLM-2025004222 (real)

NY, phone, $59,534, Complex, T3, regulated (NY, over $10K).

- **What matters:** "Symptom onset reported on the day; first treatment 3 days later (medical summary). Causation documents are partial." "Liability looks clear: rear-ended while stopped; NYSP report on file."
- **Key facts:** an injury timeline (date of loss 9/19, onset the same day per the caller, orthopedic visit about 9/22, MRI requested). The caller says he's out of work and is a commercial driver.
- **Needs attention:** 5 low-confidence transcript spans (`[*]`), each shown with the audio timestamp. The caller corrects "Delford" to "Delaware" himself; the panel shows both and points to the police report to confirm.
- **Routing reason:** "BI over $10K in NY → T3 senior first." This would have saved the 4-day escalation round trip.
- **Shows:** the timeline the second-year adjuster built by hand, ready at open.
- Sources: `sample_claims/IS-CLM-2025004222/call_excerpt.md`, `adjuster_notes.md`; Ops call 61:25.

### 3. Bodily Injury and vehicle damage, a messy intake: IS-CLM-2025002993 (real)

CA, fax/EDI, $48,959, Complex, T3, regulated (CA, over $10K). Skills: Bodily Injury, Collision.

- **What matters:** "Fax OCR confidence 0.69. 3 fields conflict with the EDI record." "Estimator noted corrosion and old paint edges on the rear quarter, not consistent with a fresh impact." This is shown as evidence with the photo reference, not as a recommendation.
- **Needs attention:**
  - Policy number: OCR reads `CA-CA-88l23-l8`, EDI reads `CA-CA-88123-18`. EDI is suggested; confirm.
  - Bumper line: OCR reads `1,B00.00`. Line items only add up to the recap total if it's `1,800.00`. Confirm.
  - Date of loss: cut off on the fax (`O9/O____`). The EDI accident date (`DTP*439`) is 2025-09-08, the day the fax arrived, three days *after* the estimate was written (2025-09-05). Likely filled with the receipt date; unverified.
  - Claimant contact: blank on the fax and in the EDI address segment. Missing; needs a phone chase.
- **Negation guard:** the estimator's note reads `n0t c0nsistent with a fresh impact` in the raw OCR. The panel shows the raw OCR next to the corrected text with "not" highlighted. Correction may change characters only, never words; code compares the two word by word, and a dropped or added word (a negation above all) goes to a person instead of the record.
- **Shows:** OCR correction by cross-checking sources and arithmetic, with a person confirming. This is the senior adjuster's "fixing what the fax machine ate".
- Sources: `sample_claims/IS-CLM-2025002993/ocr_output.txt`, `edi_record.txt`, `adjuster_notes.md`.

### 4. Comprehensive, the regulatory gap: IS-CLM-2025000375 (synthetic)

GA, e-portal, $13,369, Moderate, T2. **One of the 85:** regulated, not flagged for review. Real: waited 269.7h in queue.

- **Synthetic story:** a hailstorm damaged the insured's box truck while parked overnight at a depot. Shop estimate and 5 photos.
- **What matters:** "Regulated (GA, over $10K): human review required. The review flag was missing and has been added." "Weather data confirms hail at the depot ZIP on the date of loss."
- **Header:** SLA breached, shown in red. Under the old routing, this claim waited 11 days.
- **Footer note:** in the calibration sample, a reviewer marked this claim "review not needed". The review is required by regulation anyway. The panel says so: the rule isn't a judgment call.
- **Shows:** the regulatory gap on a real claim; enrichment from outside data (weather).

### 5. Liability, disputed fault: IS-CLM-2025004518 (synthetic)

PA, phone, $11,271, Moderate, T2, regulated. One of the 85. Skills: Liability, Collision. Real: waited 159.5h in queue; 11 documents.

- **Synthetic story:** a collision at an intersection with a signal; each driver says the other ran the light. The other driver's carrier has sent a third-party demand.
- **What matters:** "Accounts conflict on the signal. Police report: no fault assigned. One independent witness statement on file." "Third-party demand from another carrier: response due" (date).
- **Key facts:** the two accounts side by side, each linking to its source (call transcript, claimant statement).
- **Shows:** a side-by-side layout of conflicting accounts, a different shape from a timeline. The panel lays out the dispute; the adjuster decides fault.

### 6. Property Damage, a thin file: IS-CLM-2025002043 (synthetic)

FL, phone, $14,104, Moderate, T2, regulated. One of the 85. Real: 3 documents; handling 63.8h, high for Moderate.

- **Synthetic story:** the insured's delivery truck backed into a gas station's canopy column. The owner phoned it in; there's no estimate yet.
- **What matters:** "No repair estimate or invoice on file. The amount is the owner's verbal figure." "Owner of the property is a third party: contact on file."
- **Needs attention** leads the panel: estimate missing, photos missing, insured driver's statement missing. Each item has a one-click request.
- **Shows:** when the file is thin, what's missing is the most useful thing to show. It's why handling ran 63.8h.

## Variety at a glance

| # | Claim | Skill | Tier | SLA in demo | Situation | Panel shape |
|---|---|---|---|---|---|---|
| 1 | 0300 | Collision | T1 | On track | Clean | Short; one-click confirm |
| 2 | 4222 | Bodily Injury | T3 | At risk | Hard judgment | Timeline |
| 3 | 2993 | BI and Collision | T3 | At risk | Messy intake | Conflicts to confirm |
| 4 | 0375 | Comprehensive | T2 | Breached | Regulatory gap | Rule banner; outside data |
| 5 | 4518 | Liability | T2 | On track | Disputed fault | Accounts side by side |
| 6 | 2043 | Property Damage | T2 | On track | Thin file | Missing items first |

Cut order if time runs short: drop 6, then 5. Keep 1–4.
