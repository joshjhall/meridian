---
source: sybill
conversation_id: e7b0c3d6-9a24-4f81-b5e2-0c8a1d4f7369
day: "Week 1, Thursday"
title: "Systems & Constraints Working Session with Michael Torres"
participants: [Michael Torres — VP Engineering (Meridian), You (FDPM), Priya Raman — Architect (Tribe)]
duration_minutes: 60
visibility: internal
---

## Summary

### The estate
Michael Torres (VP Engineering) walked the systems end to end. ClaimsPro (licensed from Veritas Systems) is the system of record: intake, queues, workflow, documents. Around it, the data splits two ways. Snowflake holds the structured side (claims transactions, policies, payments), Databricks the unstructured side (adjuster notes, call transcripts, document OCR, images), each fed by a nightly batch export. Both key on claim ID, so joining them ad hoc is routine for analysts; there is no productized single-claim view any application can consume.

### The write wall
ClaimsPro reads are a well-documented REST API (~25 endpoints). Writes are SOAP only (~15 operations: notes, status, documents, workflow), with no REST write API committed. The webhook is unreliable (~15-minute delay, ~5% of events silently dropped). The wall that shapes everything is that **there is no API for claim decisioning.** Approvals and denials go through the ClaimsPro UI or the batch file interface. Michael called the gap deliberate and said he has no intention of opening it for an AI.

### What died twice, and the bar it taught
Michael gave both postmortems unprompted. Attempt one is the 2021 score itself. It shipped with no monitoring and no recalibration loop, drifted, its authors moved on, and the floor's trust went with them; there was no way to know it was still right. Attempt two started from the Q4 2025 calibration labels and committed to a RAG pipeline over old claims and adjuster notes before deciding what product it served. The team never converged (triage assist? adjuster copilot?) and dissolved without anything ever reaching compliance review. The standard he now holds: if the team cannot show him how they know it's right, and keep showing him, it does not go near live claims. The concrete requirements behind it: AI never denies a claim (every denial is a human decision, regulatory and non-negotiable); every AI-assisted decision logged with five fields (input data, model version, output, confidence score, whether a human reviewed it); seven-year retention on those logs; and a human-readable rationale on demand for any challenged decision. Datadog today captures application events, not decision-level audit records. That has to be built, and he wants it in the design from day one.

### The regulatory shape
Claims adjudication is regulated state by state. Twelve states (CA, NY, NJ, FL, IL, PA, OH, GA among them) require human review of any claim decision over $10,000; eight prohibit fully automated adjudication without policyholder consent, which Meridian must enforce but does not cleanly track; all states require a documented appeals process for automated decisions; and Meridian has committed to the NAIC AI bulletin (bias testing, a human oversight framework, annual reporting).

### The score is his, and he isn't defending it
The 2021 automation eligibility score on every claim is his org's build: rules-based, never recalibrated, and orphaned now that the people who wrote it are gone. The Q4 2025 calibration test (500 claims manually re-reviewed by claims ops; the labels ship in the extract) measured how far it has drifted. His verdict: the concept is right, the build is dead, and "it needs a rebuild, not a defense." The labels to do it now exist; starting from them was the one right instinct of attempt two. The fax OCR pipeline (built ~2022 on an open-source engine, ~78% accuracy, tuned once and never revisited, no human verification before output enters ClaimsPro) got the same candor.

### AI infrastructure and capacity
Both Anthropic and OpenAI are security-assessed and approved for production; API calls route US-East, and Canadian policyholder data carries residency constraints (a remediation project is still in flight). Databricks Model Serving runs one live model (fraud scoring) with capacity for more; MLflow is in active use; there is no model-performance or drift monitoring today. Michael's platform team (12 engineers, 4 on ML/data) is committed to integration support (point of contact, PR reviews, architecture guidance) but cannot take on feature development; staging runs on 3-month-old data.

## Outcome

Priya Raman (Tribe architect) left with the envelope drawn clearly: the decisioning wall, SOAP-only writes, the split data estate with no unified claim view, the denial rule, the five-field decision log with seven-year retention, and on-demand explainability. Michael made his stance explicit. Meet the evidentiary bar and he becomes an internal champion, with the scars to make the case. He also named the two failure modes to avoid: drift with nobody watching, and architecture debates standing in for product decisions. For the team, whatever gets demonstrated has to come with a way to show it's right, because that is the condition on ever reaching production. Both approved LLM providers are usable for prototyping; production choice is deferred.

## Transcript

[Michael Torres — VP Engineering (Meridian)] (0:50)
Come on in. Did Sandra's floor wear you out on Tuesday?

[You (FDPM)] (1:10)
In the best way. I have a new respect for anyone who can read a faxed repair estimate.

[Michael Torres — VP Engineering (Meridian)] (1:25)
Ha. Wait until you see the ones that come in upside down. Sit, sit — there's coffee on the credenza, and it's the one thing this office does well.

[Priya Raman — Architect (Tribe)] (1:50)
I'm set, thanks. We came with a full page of questions. Your analytics team's memo answered half of last week's, so these are the harder ones.

[Michael Torres — VP Engineering (Meridian)] (2:10)
Good, that's what they're for. And you said Monday you'd bring questions, not answers — I'd rather shape the constraints before you've built anything than after. Let me give you the tour first, then the walls.

[Michael Torres — VP Engineering (Meridian)] (2:40)
The system of record is ClaimsPro. Third-party, licensed from Veritas. Intake, queues, workflow, documents — a claim lives its whole life in there. Everything else orbits it. Structured data lands in Snowflake off a nightly batch — transactions, policies, payments. The unstructured side lives in Databricks — adjuster notes, call transcripts, the OCR output, images.

[Priya Raman — Architect (Tribe)] (3:15)
Two systems. Who has the whole claim?

[Michael Torres — VP Engineering (Meridian)] (3:40)
Nobody, is the honest answer. Both sides key on claim ID, so an analyst can join them in a notebook — my team does it every week. But there's no service you can call that hands an application the full picture of one claim. If you're imagining a product that needs that view, you're building that view. Budget for it.

[Priya Raman — Architect (Tribe)] (4:10)
Noted. Now the integration surface — what can we actually touch?

[Michael Torres — VP Engineering (Meridian)] (4:40)
Reads are easy. REST, about twenty-five endpoints, documented, decently fast. Writes are where people's plans go to die. Writes are SOAP — notes, status updates, attaching documents, workflow transitions. About fifteen operations. Veritas has a REST write API "on the roadmap," which is where it's been for two years. And the webhook — don't build on the webhook. Fifteen-minute delays, and about one event in twenty just doesn't arrive.

[Priya Raman — Architect (Tribe)] (5:20)
And decisioning? If a system concludes a claim should be paid —

[Michael Torres — VP Engineering (Meridian)] (5:45)
Then a person enters that in the ClaimsPro UI, or it goes in through the batch file interface. There is no API for claim decisioning. None. And before you ask — that gap is deliberate, and I have no intention of opening it for an AI. Whatever you design, the decision travels through a human's hands or the batch process. Design for that from the start.

[You (FDPM)] (6:15)
That's the kind of thing that sinks a project if it's discovered late. We'd rather build around it from day one.

[Michael Torres — VP Engineering (Meridian)] (10:45)
Which brings me to the part I actually asked you here for. Carlos told you Monday the last two attempts were mine, and I promised you the postmortems. They're different lessons, so take both. The first attempt is still on every screen in this building — the eligibility score. My org built it in 2021. It shipped, it ran on every claim, and we never built the loop that checks it's still right. No monitoring, no recalibration. When the two people who really understood it moved on, that was that. It drifted, the floor noticed before we did, and the trust went. Trust on that floor, once it's gone, does not come back. Sandra's people work around the score to this day.

[Priya Raman — Architect (Tribe)] (11:00)
And the second?

[Michael Torres — VP Engineering (Meridian)] (11:10)
The second is more embarrassing, because it started from the right asset. The calibration labels — for once we had real reviewer judgment on five hundred claims. A team of mine picked those up to do something with generative AI, and decided the answer was retrieval — a RAG pipeline over our old claims and adjuster notes, because that's what the right way to use this stuff was supposed to look like. Then they spent a quarter arguing about how to fold it together. Retrieval feeding what, in front of whom, for which decision — a triage assist, a copilot for the adjusters — nobody would make that call, and the architecture argument stood in for the product decision until everyone drifted back to their day jobs. Nothing ever reached compliance, because there was never a thing to review.

[Priya Raman — Architect (Tribe)] (11:30)
So one died of drift and one died of nobody deciding. What's the constraint set for the one that lives?

[Michael Torres — VP Engineering (Meridian)] (11:40)
Relayed from our compliance office and endorsed by me — my systems are what enforce these rules, and anything new faces a bar the 2021 score never had to. Start with the one that never moves. AI cannot deny a claim. Not "usually." Not "unless it's very confident." Ever. Every denial in this operation goes to a human being. That's state regulation and it's an executive mandate, and I'll tell you it's my line too. Recommend approval, ask for documents, route to a specialist, flag for review — all fine. The moment it's a denial, a person owns it.

[Priya Raman — Architect (Tribe)] (12:05)
Understood. What else is non-negotiable?

[Michael Torres — VP Engineering (Meridian)] (12:45)
Logging. And I want to be precise, because people hear "logging" and think about server logs. That's not what compliance means. For every AI-assisted decision, they need a record of five things. The input data the model saw. The model version. The output. The confidence score. And whether a human reviewed it. All five. Every time.

[Priya Raman — Architect (Tribe)] (13:10)
So a decision-level audit record, not an application log.

[Michael Torres — VP Engineering (Meridian)] (13:40)
Correct. And here's the problem you'll hit — we don't have that today. Datadog gives us application events. It tells you the service ran. It does not tell you "on this claim, this model version saw this input, produced this output at this confidence, and a human did or didn't check it." That has to be built. I'm telling you now so it's in your design from day one, not bolted on in month five. The score never had anything like it — which is half of why nobody could say when it stopped being right.

[Michael Torres — VP Engineering (Meridian)] (17:05)
Two more. Retention on those logs is seven years. People hear that and nod, and then design storage like it's seven weeks. Whatever you store, assume it sits there for seven years and pick the schema with that in mind.

[Priya Raman — Architect (Tribe)] (17:35)
That shapes storage decisions now. Good to know before we pick anything.

[Michael Torres — VP Engineering (Meridian)] (18:00)
And the last one is explainability. If a policyholder challenges a decision, or a regulator asks about one, Meridian has to produce a human-readable rationale. Not a feature vector. Not "the model scored it point-eight-seven." A person has to be able to read why, and it has to make sense to someone who's never heard of a neural network.

[You (FDPM)] (18:30)
So the rationale is a first-class output, not a debug artifact.

[Michael Torres — VP Engineering (Meridian)] (18:55)
Exactly. If you can only explain it to a data scientist, you can't explain it to a regulator, and then it's useless to everyone.

[Priya Raman — Architect (Tribe)] (19:25)
What's the regulatory shape beyond the denial rule? This runs state by state, presumably.

[Michael Torres — VP Engineering (Meridian)] (20:05)
It does, and it's not subtle. Twelve of our states — California, New York, New Jersey, Florida, the big ones — require human review on any claim decision over ten thousand dollars, no matter what a system says. Eight states prohibit fully automated adjudication without the policyholder's consent — and consent is the carrier's to collect, but ours to enforce, and it isn't cleanly tracked in ClaimsPro, so assume you can't rely on it. Every state wants a documented appeals process for automated decisions. And we've committed to the NAIC bulletin on AI — bias testing, human oversight framework, annual reporting to regulators. None of that is optional, and all of it is load you should design under from the start.

[Priya Raman — Architect (Tribe)] (21:00)
Let me make sure I have the envelope. No denials from AI. Human review over ten thousand in the threshold states. Five-field decision log per AI-assisted decision. Seven-year retention. Human-readable rationale on demand.

[Michael Torres — VP Engineering (Meridian)] (21:40)
That's the envelope. And let me give you the test I apply to all of it, because it's simpler than the list, and the score is what taught it to me. If you can't show me how you know it's right, it doesn't go near live claims. And "know" is not a launch-day word — the score looked right in 2021 and was quietly wrong within two years. That's it. That's the whole standard. Everything I just said is downstream of that one sentence.

[You (FDPM)] (22:10)
That's a bar we can build to. Honestly, it's clearer than most compliance guidance we get.

[Priya Raman — Architect (Tribe)] (26:30)
Can I take you to the models, then? Sandra told us Tuesday her adjusters ignore the eligibility score. She said to ask you about it, and that it wouldn't be a defense.

[Michael Torres — VP Engineering (Meridian)] (27:10)
She's right, and I gave you the eulogy earlier — that score is attempt one. Amount, type, tenure, prior claims; never recalibrated since it went in, and the people who wrote it are gone. The calibration labels are in the extract we sent you — they measure exactly how far it's drifted, and these days it mostly just reads claim amount; complexity never made it into the inputs. My verdict on my own system: the concept is right, the build is dead. It needs a rebuild, not a defense. And for once we actually have the labels to do it. Starting from those labels was the one thing the second attempt got right; deciding on an architecture before deciding on a product was everything it got wrong.

[Priya Raman — Architect (Tribe)] (27:45)
That's more candor than most vendors give us about their own systems.

[Michael Torres — VP Engineering (Meridian)] (28:15)
The fax OCR gets the same treatment. My team built it around an open-source engine in 2022, tuned it once at deployment, and nobody's touched it since. It runs about seventy-eight percent on faxed documents, and there's no human check before its output lands in ClaimsPro. Sandra's adjusters live with what that means — you saw it Tuesday. Same story with the EDI parser: about one partner submission in eight arrives with missing fields, and the parser drops them silently instead of flagging. I'm not proud of any of this. I'm telling you so you scope with your eyes open.

[You (FDPM)] (33:40)
What about model infrastructure, if we get that far? And LLMs — what's approved?

[Michael Torres — VP Engineering (Meridian)] (34:20)
Better news there. Databricks Model Serving is live — one model in production, fraud scoring, and there's capacity for more. MLflow for the registry, the data science team uses it daily. No drift monitoring yet; that would be new. On LLMs, both Anthropic and OpenAI have been through our vendor security assessment and are approved for production. Calls route through US-East — and mind the Canadian policyholder data, there are residency rules and our own remediation on that isn't finished. For prototyping in discovery, use either provider; we'll make the production call in delivery.

[Priya Raman — Architect (Tribe)] (35:00)
And your team's capacity, so I don't design around people who don't exist?

[Michael Torres — VP Engineering (Meridian)] (35:35)
Twelve engineers on platform, four of those on ML and data, and most of them are heads-down on the cloud migration. What I can commit is integration support — a dedicated point of contact, PR reviews, architecture guidance. What I can't commit is feature development. And be warned about staging: it runs on three-month-old data, so don't trust it to behave like production.

[Michael Torres — VP Engineering (Meridian)] (37:45)
Right. And I want to be clear about something, because after two failures people expect me to be the skeptic in the building. I am not here to kill this. The opposite — nobody in this company wants the third attempt to work more than I do. Bring the evidence and the audit trail as you go, and I will make the case for this internally myself, with the scars to make it credible. I want an efficient claims operation as much as Carlos does. I just won't get there by pretending the risk isn't real.

[Priya Raman — Architect (Tribe)] (38:10)
So the earlier we bring you real evidence —

[Michael Torres — VP Engineering (Meridian)] (38:35)
The more useful I am to you. Show me the "how do you know it's right" every step, and you'll find I'm the opposite of an obstacle.

[You (FDPM)] (39:05)
That's the partnership we want. We'll design the logging and the rationale in from the start, and we'll show you the evidence as it comes — not at the end.

[Priya Raman — Architect (Tribe)] (39:50)
We'll take you up on that. Continuously — not just when we need a signature.

[Michael Torres — VP Engineering (Meridian)] (40:15)
That's the only way it works. Drift killed the first one and dithering killed the second. Evidence and a decision — that's how the third one lives.
