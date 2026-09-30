# Open discovery questions

Questions to close with Meridian (and a few inside Tribe) before initiative scope is signed at the end of week 2. Each question lists **Why** it is being asked and **Sources** in this repo to read first. Figures marked _(extract)_ are our own cuts of `reference/claims_processing.csv`; the review-rate figures are reproducible with `python3 analysis/review_floor.py`.

**Timing tags:** **[pre-workshop]** needed before the week-2 Tuesday workshop (ideally before Monday's dry run); **[pre-scope]** needed before scope is signed; **[delivery]** can wait, but should be raised now given lead times.

IDs are stable so answers can be referenced from `memory/decisions.md`.

Transcript shorthand: **Kickoff** = `memory/calltranscripts/w1-mon-meridian-kickoff.md`, **Ops** = `memory/calltranscripts/w1-tue-sandra-ops-walkthrough.md`, **Systems** = `memory/calltranscripts/w1-thu-michael-systems.md`. Timestamps are the speaker markers in the transcript.

## Tomorrow morning: the short list

The questions that decide the demo's direction, in asking order. Full context for each is below.

0. **What do the two review flags (`flagged_for_human_review` and `requires_human_by_regulation`.) mean, who sets them, and what do they do to routing?** Everything about the review-rate target depends on this. (F1)
1. **Where does ClaimsPro run, and in what?** SaaS or installed? Web app, desktop, or Citrix? (I1)
2. **Can we build inside it?** Any extension or plugin SDK, embeddable panels, custom fields? (I2, I3)
3. **Can an overlay know what the adjuster is looking at?** Is the claim ID in the URL; is the user identifiable? (I5)
4. **What browser, what version, centrally managed?** Can IT force-install an extension? (I6)
5. **Is our reading of the review floor right?** Confirm the 12 states, what drives the other 8, and how the two review fields relate. (M1, M2, V3)
6. **What's the real state mix?** The floor is ~22–30% depending on it. (V1)
7. **Is the extract a fair sample?** What was excluded, and how was the calibration sample chosen? (V4, V5)
8. **Privately to Michael:** where did the 437 regulated-but-unflagged claims get their required review? Framed as "help us read the fields", not "we found a gap". (M3)

## F1: What the two review flags mean (ask first)

- **F1 [pre-workshop] — For `flagged_for_human_review` and `requires_human_by_regulation`: what does each mean, who or what sets it and when, and what does it do to the claim's routing?** Walk both through ClaimsPro with Michael's team and one of Sandra's adjusters.
  - **Meaning:** In plain terms, what is each flag asserting? What does "human review" mean here, given every claim is already worked by an adjuster?
  - **Who sets it, and when:** A rule at intake? Recalculated later? Can an adjuster set or clear it by hand, for example to ask for a second opinion? Is there an audit trail of who set it?
  - **Routing:** Where does a flagged claim go that an unflagged one doesn't: a different queue, a senior or supervisor, a QA step, a sign-off before payment? Does `requires_human_by_regulation` route anything on its own, or does it only record the requirement?
  - **Interaction:** Does the review flag include regulation-driven reviews, or are they separate paths? (This is V3 and M3.)
  - _Why:_ Whether <20% is reachable depends entirely on the answers. One reading makes it achievable through better routing; another makes it impossible. See "What the <20% target is for" below.
  - _Sources:_ `reference/data_dictionary.md:72`–`81`; `sample_claims/*/status_history.md` (no status step corresponds to the flag in any of the three samples); `analysis/review_floor.py` sections 4, 6, and 8.

## What the <20% target is for, and when it's reachable

The SOW lists "Review rate: 45% of claims flagged for human review → <20%" (`docs/project/sow.md:18`) without saying what it achieves. Unlike the other three goals, it measures a process, not an outcome anyone experiences, so its purpose has to be inferred.

**A flag doesn't change a claim's cost or speed.** Holding complexity fixed, flagged and unflagged claims cost the same and take as long (`analysis/review_floor.py` section 8):

| Complexity | Cost, not flagged / flagged | Cycle, not flagged / flagged |
| ---------- | --------------------------- | ---------------------------- |
| Simple     | $381 / $380                 | 48.2h / 46.1h                |
| Moderate   | $619 / $615                 | 73.1h / 73.4h                |
| Complex    | $920 / $904                 | 107.9h / 111.1h              |

Flagged claims look expensive only because the flag fires mostly on complex claims (94% of complex, 19% of simple). So in this data, cutting flags wouldn't by itself move cost or cycle time. Caveats: this is observational, and the fully loaded cost might not capture a separate reviewer's time (D6).

**Three things <20% might be for:**

1. **Less human effort per claim.** The flag rate stood in for "how much extra human work the operation does." The goal is right, the metric may be wrong; human minutes per claim would measure it directly (C1).
2. **Flags adjusters can trust.** 42% of today's flags are unnecessary against reviewer judgment, so adjusters learn to ignore them. A flag that fires less but is right when it does is a precision goal.
3. **Automation readiness.** Unflagged claims are the ones a system could fast-track. The no-consent assumption (M4) rules out full automation, so this reading doesn't hold.

**When it's reachable, depending on F1.** Everything in "Why <20% is not reachable as written" below assumes the review flag must cover regulation-required claims. That assumption may be wrong:

| If F1 finds...                                                                                          | Then <20% is...                                           | Because...                                                      |
| ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------- |
| The review flag must include every regulation-required claim                                            | **Not reachable** as written                              | The floor is ~22–30% (findings 1–4 below)                       |
| Regulation is routed on its own, and the review flag is **only** a human's request for a second opinion | **Potentially reachable**, through better initial routing | Fewer claims would reach the wrong adjuster and need escalating |

Under the second reading, one scenario: if complex claims go straight to seniors and need no second opinion, and only the calibration-sample-justified share of other flags remains, the rate falls to about **12.8%** (section 8). Two cautions:

- **The data doesn't look like a manual flag.** It tracks rule inputs closely: flag rates rise from 25% to 94% with claim amount, fall from 76% to 24% as the 2021 score rises, and are flat across intake channels. A second-opinion request should depend on the adjuster and the claim's difficulty, not on its dollar amount. It looks like a rules-engine output (as the data dictionary says), possibly with manual additions. F1 is still worth asking, since the data can't rule out a mix.
- **The scenario has a capacity cost.** Complex claims are 18.9% of volume, about 75,600 a year for 12 seniors and 4 leads, or roughly 19 each per working day. That's above the 15–18 claims a day adjusters handle now, and complex claims are the slow ones. Routing all of them to seniors would overload the tier. A realistic design routes the hardest subset (S3, S4).

## Why <20% review rate is not reachable as written

This section supports C1, M1, M2, and M3. It assumes the review flag must include regulation-required claims; F1 tests that assumption. The SOW targets moving the review rate from 45% of claims flagged to <20% (`docs/project/sow.md:18`).

**The SOW expects targets to be refined in discovery.** Targets are "directional" (`docs/project/sow.md:12`); "measurement plans will be defined during the Discovery Period and agreed in writing at its conclusion" (`docs/project/sow.md:21`). Proposing a redefinition is the process the SOW describes, not a renegotiation.

**1. The regulatory floor alone is above 20%.** 1,272 of 5,000 claims (25.4%, 95% CI ±1.2 pts) are `requires_human_by_regulation = Yes` _(extract)_. The data dictionary states "about 25%" (`reference/data_dictionary.md:80`); the analytics memo flags that it did not map the floor and that "that floor sets a ceiling on how far the flag rate can actually fall" (`reference/analytics_memo.md:33`). The extract is stratified and its regulated share matches the calibration sample's (26.8%), so this is not a sampling artifact.

**2. The floor follows state rules we were told about, plus one we weren't.** Michael named 8 of the 12 states that require human review over $10K (Systems, 20:05, line 121). In the extract, exactly 12 states behave that way (0% regulated at or under $10K, 100% over): the 8 named plus MA, MD, MI, VA. In the remaining 8 states (AZ, IN, MO, NC, TN, TX, WA, WI) about 30% of claims are regulated regardless of amount, which no rule we've been given explains. Nothing else in the extract explains it either (M2). Together: 12.9% + 12.6% = 25.4%. Applying the $10K rule in every state would raise the floor to 31.9%. It isn't necessary, since the flag is recorded per claim.

**3. Even a perfect flag would flag ~44% of claims.** In the 500-claim calibration sample (labels described at `reference/data_dictionary.md:141` and `reference/analytics_memo.md:15`), a claim must be reviewed if a reviewer judged review needed _or_ regulation requires it. That is 222 of 500 claims (44.4%, ±4.4 pts). Among claims regulation doesn't cover, reviewers judged 24.0% still needed review. The current flag fires on 47.4% of the sample, so a perfect rebuild of the _same_ flag moves the rate only about 3 points. The memo's "42% of flagged were unnecessary" (`reference/analytics_memo.md:15`) is true against reviewer judgment alone, but many of those claims are regulation-required anyway; only 36.6% of flagged claims are regulated (the memo's "37%").

**4. The floor depends on the real state mix, and the extract may not reflect it.** The extract is close to evenly spread across 20 states (222–292 claims each), which looks like stratified sampling, not Meridian's real volume. Holding each state group's rate fixed, the floor is 22.1% if all volume were in the 12 threshold states and 30.1% if all were in the other 8 (`analysis/review_floor.py` section 5). A realistic range is **~22–30%**, and every point in it is above 20%. The low end is the one to confirm (V1), because it leaves the thinnest margin.

**Caveats, stated up front:** the calibration sample is 500 claims, two quarters old, and "was not built as an evaluation set" (`reference/analytics_memo.md:31`). We don't know how reviewers defined "needed" (D5). If "needed" meant "needed under today's process", a prepared claim brief could lower it; that is the one lever that moves finding 3.

**What this means for the target.** The rate of claims _touched_ by a human cannot fall far. What can fall is the cost and depth of each touch: a one-click confirmation of a prepared recommendation instead of a full review (C3). Candidate redefinitions for C1:

- **Discretionary flag rate:** claims flagged but not regulation-required, 28.9% of claims today _(extract)_, with a target set against the calibration labels.
- **Full-review rate:** claims needing a full adjuster review rather than a fast-lane confirmation.
- **Human minutes per claim:** closer to what the cost target actually needs.

**Also found:** 437 regulation-required claims were _not_ flagged for review _(extract)_. The flag is set by the rules engine (`reference/data_dictionary.md:72`–`73`), so the question is whether the engine is the only route to the required review. Every one of the 437 was worked by an adjuster (all have an `adjuster_id` and ≥1.0h handling), and 66 were denied, which is always a human decision. So "review" here likely means an extra tier (e.g. senior review, as on IS-CLM-2025004222), not the first human touch. Only Meridian can say whether these claims got the tier the regulation requires (V3, M3). Handle with care: this is about Michael's current system.

## Integration path: how anything reaches the adjuster (Michael Torres)

There are five generic ways to put new capability in front of users of a legacy system of record. Our read on each, and the questions that confirm or kill it:

| #   | Path                                                                                                                                  | Our read                                                                                                                      | Deciding questions                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| 1   | Replace the UI; use ClaimsPro as a headless backend                                                                                   | **Rejected.** Claim decisions can only be entered through the ClaimsPro UI or batch files, and Michael won't open that for AI | none; confirmed (Systems, 5:45, line 70) |
| 2   | Build inside ClaimsPro with a vendor extension or plugin SDK                                                                          | **Unlikely.** No SDK was mentioned; this class of vendor system rarely has one                                                | I2                                       |
| 3   | Replace ClaimsPro with a more flexible system                                                                                         | **Rejected.** A system-of-record migration doesn't fit 6 months and $5M, and it's not what the SOW buys                       | none                                     |
| 4   | Write into ClaimsPro's existing fields: notes, documents, workflow status, custom fields if they exist                                | **Likely.** Notes, documents, and workflow writes exist via SOAP; the brief can land as a note or attached document           | I3, I4                                   |
| 5   | Overlay: a browser extension that reads which claim is open and shows our panel beside ClaimsPro, fed by our backend via the REST API | **Likely.** It needs the claim ID and user identity readable from the page, and a managed browser we can deploy to            | I1, I5, I6, I7, I8                       |

Paths 4 and 5 combine well. The note (4) is the durable, auditable record that survives if the extension breaks; the overlay (5) is the richer, interactive experience. Two further paths are worth naming:

- **Upstream interception:** fix fax OCR and EDI output _before_ it enters ClaimsPro. Today it lands with no human check (Systems, 28:15, line 142). This path needs no UI in ClaimsPro at all.
- **Native configuration:** ClaimsPro's own triage rules and queue setup. This is the likely route for routing changes (M5).

UI automation (bots driving the ClaimsPro screens) is rejected: it breaks on every vendor UI change, and it would be a way around the deliberate decisioning gap.

- **I1 [pre-workshop] — Is ClaimsPro SaaS (hosted by Veritas) or installed by Meridian, and is the adjuster client a web app?**
  - _Why:_ Everything in path 5 assumes a browser-based UI. If it's a desktop or Citrix-delivered client, a browser extension can't reach it, and path 4 becomes the only way in. Hosting also decides who controls upgrades and how often the UI changes under us.
  - _Sources:_ Systems, 2:40 (line 53, "Third-party, licensed from Veritas"); `AGENTS.md:37`. The repo never says whether it's hosted or browser-based.
- **I2 [pre-workshop] — Beyond the REST and SOAP APIs, does ClaimsPro offer any extension or plugin SDK, embeddable panels or widgets, UI customization, or a vendor app marketplace?**
  - _Why:_ It's the only way to put our UI _inside_ ClaimsPro (path 2). We expect "no", but it's cheap to ask and changes everything if the answer is yes.
  - _Sources:_ Systems, 4:40 (line 64); Ops, 86:20 (line 241, "Don't build us an eighth screen").
- **I3 [pre-scope] — Does ClaimsPro support custom fields, and can they be read and written through the APIs and shown on the adjuster's screens?**
  - _Why:_ Custom fields would let structured outputs sit in the adjuster's normal view, such as a review-lane indicator, extraction confidence, or brief status. Without them, the notes field carries everything.
  - _Sources:_ Systems, 4:40 (line 64, SOAP writes: notes, status, documents, workflow).
- **I4 [pre-scope] — What are the notes field's limits: length, formatting (plain text or rich), visibility to adjusters and in correspondence, and can notes be edited or superseded?**
  - _Why:_ If the prepared brief is written as a note, its size and format limit how useful it is. Notes that are visible externally or can't be edited would change what goes in them.
  - _Sources:_ `sample_claims/*/adjuster_notes.md` (note style today); Systems, 4:40 (line 64).
- **I5 [pre-workshop] — Does the ClaimsPro URL for an open claim include the claim ID (as a path segment or query parameter)? Is the signed-in user identifiable from the page?**
  - _Why:_ Path 5 depends on the extension knowing which claim is open and who is looking at it. A URL is the most robust source; reading the page contents is fragile. If it's a single-page app, we also need to know whether the URL changes as the adjuster moves between claims and screens.
  - _Sources:_ Ops, 42:05 (line 169, seven screens per claim, all of which need to resolve to the same claim).
- **I6 [pre-workshop] — Which browsers, and which versions, do adjusters use? Is the browser centrally managed, and can IT force-install an extension?**
  - _Why:_ An extension ships per browser engine. Chromium-based browsers (Chrome, Edge) share one build; Firefox needs a separate one; Safari is out. Central management decides whether deployment is a policy push or a per-seat install, and whether security allows extensions at all.
  - _Sources:_ no repo source; not covered in week 1.
- **I7 [pre-scope] — How do adjusters sign in to ClaimsPro (SSO provider)? Can our overlay's backend use the same identity?**
  - _Why:_ The overlay has to call our backend as the signed-in adjuster, so the audit record's human-reviewed flag names a real person. Sharing SSO avoids a second login and ties the record to the same identity as ClaimsPro.
  - _Sources:_ Systems, 12:45 (line 94, five-field audit record).
- **I8 [delivery] — How often does Veritas change the ClaimsPro UI, and with how much notice?**
  - _Why:_ Any overlay that depends on page structure breaks on UI releases. The claim-ID-in-URL approach (I5) limits that risk; this tells us how much maintenance to plan for.
  - _Sources:_ Systems, 4:40 (line 64, REST write API "on the roadmap" for two years, a hint about the vendor's pace).

## Data validation: are we reading the extract correctly? (Michael's analytics team)

Our analysis rests on the 5,000-claim extract. Before the workshop quotes numbers from it, confirm we're reading it the way Meridian's team built it. The extract is internally consistent: cycle time always equals wait plus handling, denial reasons appear only on denials, and there are no duplicate IDs (`analysis/review_floor.py` section 5). The open questions are about how it was sampled and what it leaves out.

- **V1 [pre-workshop] — How was the extract stratified, and what is the real volume split by state?**
  - _Why:_ The extract has 222–292 claims in each of 20 states, far more even than real volume usually is. The regulatory floor ranges from ~22% to ~30% depending on the state mix (finding 4), so the real split sets the number we quote.
  - _Sources:_ `reference/analytics_memo.md` header ("a stratified 5,000-claim extract"); `reference/data_dictionary.md` (`state`, "20 states represented"); `analysis/review_floor.py` section 5.
- **V2 [pre-workshop] — Does Meridian operate in states beyond these 20?**
  - _Why:_ If so, their regulation rules are unknown and the floor could move either way.
  - _Sources:_ `reference/data_dictionary.md` (`state`).
- **V3 [pre-workshop] — Is our reading of the regulation and review fields right?**
  - What does `flagged_for_human_review` route a claim _to_? Every claim in the extract has an adjuster, so it can't mean "gets a human". Is it a second review tier (senior, supervisor, QA)?
  - Is `requires_human_by_regulation` computed from rules or entered by people, and when is it set?
  - What does "human review" mean _in the regulation_? Is a single adjuster working the claim enough, or does the rule require a second-level review?
  - _Why:_ The headline finding (the <20% target is below the floor) and the 437 unflagged regulated claims (M3) both depend on how these fields relate. If one adjuster working the claim satisfies the regulation, the 437 are compliant and the review-rate target should be measured against the extra tier, not the first touch.
  - _Sources:_ `reference/data_dictionary.md:72`–`74`, `:78`–`81`; `sample_claims/IS-CLM-2025004222/status_history.md:10` (a senior-review tier exists); `analysis/review_floor.py` sections 1, 4, and 6.
- **V4 [pre-scope] — What was excluded before sampling?** Were EDI submissions the parser dropped, claims with missing fields, withdrawn claims, or reopened claims left out? Does the date range (June–December 2025 only) miss seasonal patterns?
  - _Why:_ Exclusions would bias the extract toward clean claims, understating fax/EDI pain and cycle time. Seven months can't show seasonality, and the pre-sales notes mention seasonal contractor surges.
  - _Sources:_ Systems, 28:15 (line 142, EDI parser drops ~12%); `docs/project/presales_notes.md:11` (seasonal surges); `analysis/review_floor.py` section 5 (filed months).
- **V5 [pre-scope] — Is the calibration sample representative?** It was described as a random sample, and its mix matches the full extract within about 3 points on channel, complexity, and claim type. How were the claims chosen, and why are 20 of the 500 still pending?
  - _Why:_ Finding 3 and any rebuilt flag are measured against these labels. Our checks show no skew on the fields we can see, but reviewer selection or timing could still bias them.
  - _Sources:_ `reference/analytics_memo.md` ("The 2021 eligibility score…", "Known limits"); `reference/data_dictionary.md:141`; `analysis/review_floor.py` section 5.

## Compliance (via Michael Torres)

- **C1 [pre-scope] — Redefine the review-rate target.** Which of the candidate redefinitions above does Compliance accept, and at what level?
  - _Why:_ The target is below the regulatory floor (25.4%) and below what a perfect flag would produce (~44%). See the section above.
  - _Sources:_ `docs/project/sow.md:18`, `:21`; `reference/data_dictionary.md:80`; `reference/analytics_memo.md:15`, `:33`; `analysis/review_floor.py`.
- **C2 [pre-scope] — The month-3 claims review standard.** Who drafts it, what does it measure, and when is it agreed?
  - _Why:_ Continuation past month 3 depends on "a claims review standard agreed with Meridian Compliance." It's the bar we are judged against, and it is not yet written.
  - _Sources:_ `docs/project/sow.md:29`; Kickoff, Laura at 12:57.
- **C3 [pre-workshop] — Does one-click confirmation count as human review?** Does an adjuster confirming a prepared recommendation satisfy the $10K rule and set the audit record's human-reviewed flag, or is a minimum review depth required?
  - _Why:_ Auto-approval is effectively off the table (M4), and finding 3 means the review _rate_ can barely move. A fast lane is how speed and cost gains survive the rules.
  - _Sources:_ Systems, 11:40 (line 88: "recommend approval … all fine"), 20:05 (line 121); `memory/decisions.md` (none yet; see T2).
- **C4 [pre-workshop] — Where is the line on denial-relevant evidence?** May the AI surface evidence pointing toward a denial without recommending one?
  - _Why:_ The AI can never deny. On IS-CLM-2025002993 the decisive evidence was a prior-repair estimate matching the claimed damage, exactly what a claim brief would surface.
  - _Sources:_ Systems, 11:40 (line 88); `sample_claims/IS-CLM-2025002993/adjuster_notes.md:16`; Ops, 39:35 (line 157).
- **C5 [pre-scope] — What counts as an "AI-assisted decision" for the five-field audit record?** Only recommendations and routing, or also summaries and extracted fields?
  - _Why:_ This sets the scope of the logging build, and Datadog doesn't cover it today.
  - _Sources:_ Systems, 12:45 (line 94), 17:05 (line 103), 18:00 (line 109).
- **C6 [delivery] — Appeals process.** Is there a documented appeals process for AI-assisted decisions, or does one need to be built?
  - _Why:_ Every state requires one for automated decisions.
  - _Sources:_ Systems, 20:05 (line 121).
- **C7 [delivery] — NAIC bias testing.** What methodology and attributes are expected, and is the data available?
  - _Why:_ It's a committed obligation, but policyholder fields are masked in the extract.
  - _Sources:_ Systems, 20:05 (line 121); `reference/analytics_memo.md` header (masking).

## Michael Torres — regulation data and systems

- **M1 [pre-workshop] — Confirm the 12 threshold states.** Are they the 8 named plus MA, MD, MI, VA?
  - _Why:_ Inferred from the extract, not stated by Meridian. See finding 2.
  - _Sources:_ Systems, 20:05 (line 121); `analysis/review_floor.py` section 2.
- **M2 [pre-workshop] — What drives the regulation flag in the other 8 states?** Which rule makes ~30% of claims regulated there, and which field records its input?
  - _Why:_ In AZ, IN, MO, NC, TN, TX, WA, WI, 30.1% of 2,084 claims are regulated, and **no field in the extract predicts which ones**. The rate is flat, within noise, by state (28–32%), claim type, channel, complexity, amount (30% under and 31% over $10K), the 2021 score, the review flag, and filing month. It isn't set by hand in any visible way: adjuster-to-adjuster variation is no larger than random shuffles produce. So the driver is an attribute of the claim or policy that the extract doesn't carry. Candidates to put to Michael:
    - **Policyholder consent status (weaker candidate).** Eight states restrict automated adjudication without consent (Systems, 20:05, line 121), there are exactly 8 states here, and a ~30% rate uniform across claim types looks like a policy-level attribute. But Michael said consent "isn't cleanly tracked … assume you can't rely on it", and a field that cleanly marks ~30% of claims doesn't fit that. If it is consent, it's the unreliable data he warned about.
    - **A carrier-client contract term.** Meridian is a TPA; some carrier clients may require human review on all their claims. The extract has no carrier field.
    - **Policy or claimant attributes** such as the policyholder's fleet size, a litigation or attorney-represented flag, or out-of-state claimants.
  - If it's a contract term or claimant attribute, it's reproducible from data we can request. If it's a masked field, the extract can never predict it and the design must read it from ClaimsPro per claim. **Whatever the answer, it does not reopen automation:** we assume no consent anywhere (M4).
  - _Sources:_ `analysis/review_floor.py` section 7; `reference/data_dictionary.md:78`–`81`; Systems, 20:05 (line 121).
- **M3 [pre-workshop] — Where did the 437 regulated-but-unflagged claims get their required review?** Can his team pull those claim IDs and show the review step in each status history?
  - _Why:_ The rules engine didn't flag them, but all 437 were worked by an adjuster and 66 were denied (always a human decision). Whether that's compliant depends on what the regulation requires (V3). Ask V3 first. 352 of the 437 are in the 8 non-threshold states, which suggests the engine applies the $10K rule but not the other states' rule (M2). Raise privately, framed as "help us read these fields", not "we found a gap".
  - _Sources:_ `analysis/review_floor.py` sections 4 and 6; `reference/data_dictionary.md:72`–`73`, `:78`–`81`.
- **M4 [pre-scope] — Which 8 states require consent for automated adjudication, and can consent ever be tracked?**
  - _Why:_ Consent "isn't cleanly tracked … assume you can't rely on it" (Systems, 20:05, line 121), and we don't know which 8 states have the rule. **Working assumption: no policyholder has consented, in any state**, so nothing is fully automated and every decision gets a human confirmation, including the fast lane. This holds even if M2 turns out to be consent-related: data Michael calls untrustworthy can't unlock automation.
  - _Scope of the assumption:_ no consent bans _fully automated_ adjudication; it does not require the extra review tier. Counting every no-consent claim as regulated would overstate the floor. If the consent states are the 8 non-threshold states, the floor would jump from 25.4% to ~54.6% (12.9% threshold-state claims over $10K, plus all 41.7% of claims in the other 8). Keep consent out of the floor numbers unless Compliance says the rule requires review (C1).
  - _Sources:_ Systems, 20:05 (line 121: "isn't cleanly tracked … assume you can't rely on it").
- **M5 [pre-scope] — Can we change assignment and ordering in ClaimsPro?** Through SOAP workflow operations or triage-rule configuration?
  - _Why:_ The dispatch leg depends on it. The sample histories show claims routed to a named adjuster's queue the moment they arrive.
  - _Sources:_ Systems, 4:40 (line 64); `sample_claims/IS-CLM-2025000300/status_history.md:8`; Ops, 20:15 (line 121).
- **M6 [pre-scope] — Can the 2021 score be retired from the adjuster screen** once a replacement is validated, and who owns that change?
  - _Why:_ An ignored score left on screen erodes trust in the replacement.
  - _Sources:_ Systems, 27:10; Ops, 14:50; `reference/analytics_memo.md` ("The 2021 eligibility score is not usable as-is").
- **M7 [pre-workshop] — Browser extension viability.** Would an overlay on ClaimsPro clear security review and CAB? The fallback is a ClaimsPro note via SOAP.
  - _Why:_ It avoids building "an eighth screen", but it's a new deployment surface. The technical preconditions are I1, I5, I6, and I7.
  - _Sources:_ Ops, 86:20 (line 241); Systems, 4:40 (line 64); `docs/project/presales_notes.md:35`.
- **M8 [pre-workshop] — PII masking for the demo.** Is masking before the LLM call acceptable, and is there a preferred approach?
  - _Why:_ Decision 4 bars PII from prompts, and the sample claims carry names and policy numbers.
  - _Sources:_ `memory/decisions.md:8`; `sample_claims/IS-CLM-2025002993/intake.md:15`; `sample_claims/IS-CLM-2025004222/intake.md:14`.
- **M9 [pre-scope] — PII and residency in production.** Is PII in prompts acceptable in production? What share of claims are Canadian, and are they in scope?
  - _Why:_ It determines the production architecture; the residency remediation is still in flight.
  - _Sources:_ Systems, 34:20 (line 148); `memory/decisions.md:9`.
- **M10 [delivery] — Audit store.** Where does the seven-year decision log live, and who operates it after month 6?
  - _Sources:_ Systems, 17:05 (line 103).
- **M11 [delivery] — Drift monitoring.** Is there preferred tooling on Databricks, and who responds to alerts after handover?
  - _Why:_ Drift with nobody watching killed attempt one.
  - _Sources:_ Systems, 10:45, 34:20 (line 148); Kickoff, 5:20.
- **M12 [pre-scope] — Who builds and runs what?** Who builds the single-claim view, and who owns production operations after the engagement?
  - _Why:_ His team offers integration support only; the data team takes 2–3 weeks per pipeline request.
  - _Sources:_ Systems, 3:40 (line 58), 35:35 (line 154); `docs/project/presales_notes.md:23`.
- **M13 [delivery] — Test environment.** Is there fresher data, or a sandbox for SOAP writes?
  - _Why:_ Staging runs on 3-month-old data, and discovery is read-only.
  - _Sources:_ Systems, 35:35 (line 154); `memory/decisions.md:6`.

## Michael's analytics team — data requests (file now; 2–3 week turnaround)

Turnaround per `docs/project/presales_notes.md:23`.

- **D1 [pre-scope] — Fax/EDI volume by sender.**
  - _Why:_ Needed to size the move-senders-off-fax track and answer Carlos. Upper bound so far: moving _all_ fax/EDI to the portal saves ~8.8% of blended cost _(extract)_.
  - _Sources:_ `reference/analytics_memo.md:19` ("it carries no sender field"); Kickoff, 27:10 (line 135).
- **D2 [pre-scope] — Claim status event log.** Per-claim timestamps and queue membership.
  - _Why:_ Queue replay needs event-level data; the extract only has aggregates.
  - _Sources:_ `sample_claims/*/status_history.md`; `reference/analytics_memo.md:32`.
- **D3 [pre-scope] — OCR ground truth.** Is OCR output linked to the original images, and are adjuster corrections recoverable?
  - _Why:_ It's the only way to measure extraction accuracy against the 78% baseline.
  - _Sources:_ Systems, 28:15 (line 142); `sample_claims/IS-CLM-2025002993/ocr_output.txt` vs `fax_transmission.pdf`.
- **D4 [pre-scope] — EDI drops.** Are silently dropped submissions logged anywhere?
  - _Sources:_ Systems, 28:15 (line 142); `reference/data_dictionary.md` (`intake_channel`).
- **D5 [pre-scope] — Calibration labels.** Who labeled them, was agreement checked, what did "needed" mean, and were reasons recorded?
  - _Why:_ Finding 3 depends on what "needed" meant, and the labels are our only evaluation set.
  - _Sources:_ `reference/data_dictionary.md:141`; `reference/analytics_memo.md:31`.
- **D6 [pre-scope] — How cost per claim is computed.** Activity-based or allocated?
  - _Why:_ If it's allocated, handling-time savings may not show up in the −25% metric.
  - _Sources:_ `reference/data_dictionary.md:46`.
- **D7 [delivery] — Effort data.** Any adjuster time-on-claim data?
  - _Why:_ `handling_hours` measures time open, not effort; a time-to-complete score needs a real effort measure.
  - _Sources:_ `reference/data_dictionary.md:93`.

## Sandra Okafor — operations

- **S1 [pre-workshop] — What does "blind to age" mean?** Time since filing, time in queue, or time against an SLA? Are there contractual SLAs?
  - _Sources:_ Ops, 20:15 (line 121), 28:05 (line 145).
- **S2 [pre-workshop] — When is complexity assigned?**
  - _Why:_ It's recorded at time of review, but routing needs it at intake, so it would have to be predicted.
  - _Sources:_ `reference/data_dictionary.md:59`.
- **S3 [pre-scope] — Adjuster tiers for routing.** Can complex and bodily-injury claims go to seniors from the start? Any certification or HR constraints?
  - _Why:_ The floor is not flat (12 seniors, 4 leads), and Sandra called out skill-blind assignment. The extract pools adjusters, so it can't answer this.
  - _Sources:_ `docs/project/presales_notes.md:11`; Ops, 20:15 (line 121); `reference/data_dictionary.md:121`.
- **S4 [pre-scope] — Senior review capacity.** How is the senior review queue staffed?
  - _Why:_ IS-CLM-2025004222 waited about 4 days, mostly in line.
  - _Sources:_ `sample_claims/IS-CLM-2025004222/status_history.md:10`–`11`; Ops, 61:25 (line 217), 62:15 (line 223).
- **S5 [pre-scope] — Labeling time.** Can two adjusters spend a few hours a week labeling extractions and grading briefs?
  - _Why:_ There's no trusted ground truth today, and Michael's bar is "show me how you know it's right."
  - _Sources:_ `reference/analytics_memo.md:31`; Systems, 21:40 (line 127).
- **S6 [pre-workshop] — Brief placement.** Note, overlay, or something else?
  - _Sources:_ Ops, 42:05 (line 169, seven screens), 86:20 (line 241).
- **S7 [pre-scope] — Phone intake.** Is the call center in her org? Could transcript extraction replace some agent keying?
  - _Why:_ Phone is the most expensive channel ($650).
  - _Sources:_ Ops, 4:10 (line 67); `sample_claims/IS-CLM-2025004222/call_excerpt.md`.
- **S8 [pre-scope] — Fax sender history.** Top senders, and past attempts to move them?
  - _Sources:_ Kickoff, 27:10 (line 135); `reference/analytics_memo.md:19`.
- **S9 [delivery] — Claimant communication.** What updates do claimants get while a claim waits, and is communication in scope?
  - _Why:_ CSAT tracks disposition and communication more than speed.
  - _Sources:_ `reference/analytics_memo.md:27`.

## Carlos Reyes — sponsor

- **R1 [pre-scope] — What counts toward −25%?** Channel shift, or AI savings only? Against which baseline?
  - _Sources:_ Kickoff, 3:32 (line 75), 27:10 (line 135); `docs/project/sow.md:21`.
- **R2 [pre-scope] — Secondary benefits.** Do overtime, contractor surge, and turnover count?
  - _Sources:_ `docs/project/presales_notes.md:11`; Ops, 23:05.
- **R3 [pre-scope] — Appetite to push senders.** Are the big fax senders carrier clients or their vendors? Is Meridian willing to require a channel change?
  - _Sources:_ Kickoff, 27:10 (line 135).
- **R5 [pre-workshop] — What problem was the <20% review-rate target meant to solve?** Less human effort per claim, flags adjusters trust, or readiness for automation?
  - _Why:_ In the extract a flag doesn't change a claim's cost or speed, so the target only makes sense tied to a purpose. The answer tells us what to measure instead (C1).
  - _Sources:_ `docs/project/sow.md:18`; "What the <20% target is for" above; `analysis/review_floor.py` section 8.
- **R4 [pre-scope] — What matters most at month 3?**
  - _Sources:_ `docs/project/sow.md:29`; Kickoff, 38:22 (line 153).

## Tribe internal (Laura, Priya)

- **T1 [pre-workshop] — Framing the review-rate finding.** Lead with it in the workshop, or take it to Carlos and Michael beforehand? M3 in particular shouldn't surprise Michael in front of his peers.
  - _Sources:_ the section at the top; Kickoff, 24:37 (line 117).
- **T2 [pre-workshop] — Auto-approve stance.** Confirm we drop auto-approval in favor of a one-click fast lane, pending M4 and C3.
  - _Sources:_ Systems, 11:40 (line 88), 20:05 (line 121).
- **T3 [pre-scope] — Build capacity.** What Tribe build capacity sits behind the FDPM and architect?
  - _Sources:_ `docs/project/sow.md` §4; Systems, 35:35 (line 154).
- **T4 [pre-workshop] — Prototype LLM provider.** Pick one for the demo.
  - _Sources:_ `memory/decisions.md:9`.

## Already answered from the data (don't ask)

- Complex claims are 19% of volume and 31% of cost; Moderate 28% and 31%; Simple 53% and 37% _(extract)_.
- Moving 100% of fax/EDI to the e-portal cuts blended cost by at most ~8.8%; moving all fax and phone, ~21.3% _(extract, assuming moved claims cost what portal claims of the same complexity cost)_. Channel shift alone does not reach −25%.
- Simple claims wait 41.7h in queue on average; capping that wait at 12h would put ~96% of them under 24h _(extract)_. Cycle time for simple claims is mostly a routing problem.
- `handling_hours` is time open, not effort (`reference/data_dictionary.md:93`). At 15–18 claims a day, adjuster effort is roughly 30 minutes per claim.
