---
source: sybill
conversation_id: 3f8a1c92-7b4e-4d2a-9e15-6c0d8f2a4b31
day: "Week 1, Monday"
title: "Meridian Kickoff — Insurance Services AI Partnership"
participants: [Carlos Reyes — GM Insurance Services (Meridian), Sandra Okafor — VP Claims Operations (Meridian), Michael Torres — VP Engineering (Meridian), You (FDPM), Priya Raman — Architect (Tribe), Laura Chen — GM Commercial (Tribe)]
duration_minutes: 45
visibility: internal
---

## Summary

### Sponsor mandate
Carlos Reyes (GM, Insurance Services — executive sponsor) framed the engagement around cost-to-serve. A blended 25% reduction is the number his board is watching, and he wants it demonstrated, not promised. He was open about the two prior internal AI attempts (a 2021 scoring engine that shipped and went stale, and a recent generative-AI effort that never left the lab). His team's trust has to be earned before they commit time; he will not spend their hours on "another demo that goes nowhere."

### Engagement frame and stakes
The parties restated the $5M, six-month shape and the two-week discovery window. The formal midpoint checkpoint at the end of month three governs continuation. By then the work has to show demonstrated performance, not just activity.

### What died twice, firsthand
Both prior attempts belonged to the org of Michael Torres (VP Engineering), and he offered the postmortems himself. Two different deaths. The first is still running. The 2021 score shipped with no monitoring and no recalibration loop, drifted, its authors moved on, and the floor quietly stopped believing it. The second, a recent generative-AI effort that started from the 500-claim calibration labels, committed to a retrieval pipeline over old claims and notes before anyone decided what product it served; the architecture debate stood in for the product decision until the team dissolved. He wants early sight of anything touching claim decisions this time, and set a working session for Thursday to walk the systems and the constraints, with the architect requested in the room.

### Discovery access and data
Sandra Okafor (VP Claims Operations) volunteered a combined operations walkthrough and floor session for Tuesday, covering the intake-to-disposition path end to end, then seats next to her adjusters (one senior, one second-year) watching real handling. On a question about data from Priya Raman (Tribe architect), Michael said his analytics team recently completed a pass over a 5,000-claim extract from Snowflake; he will send the extract and their findings memo over today, masked on policyholder fields.

### The fax question
Carlos put one question on the table for the workshop: why get better at digesting faxes instead of getting rid of some of them? The expensive channels are where the cost sits, and moving senders off fax is the kind of answer his board understands. Nobody resolved it; he expects it addressed.

### Week-2 target
Laura Chen (Tribe GM, Commercial — engagement lead) set a two-hour working session for Tuesday of week 2. Tribe opens with a recommendation and a working demo ("show, don't tell"), and then the room shapes it together, aligned before discovery scope is locked.

## Week-1 schedule (agreed)

- **Mon** — Kickoff (this call).
- **Tue** — Sandra's ops walkthrough and floor session with adjusters.
- **Thu** — Systems and constraints session with Michael.
- **Week 2, Mon** — Internal dry run of the workshop opening.
- **Week 2, Tue** — Two-hour working session with all stakeholders; Tribe opens with recommendation + demo (~30 min), then the room workshops it.

## Action items

- **Ops walkthrough + floor session (Tue):** Sandra + you + Priya.
- **Extract + analytics memo:** Michael sends both today; lands in `reference/`.
- **Systems session (Thu):** you + Priya, with Michael.

## Outcome

The week-1 schedule was agreed: Sandra's walkthrough and floor session Tuesday, Michael's systems session Thursday, the extract and analytics memo in hand from day one. Laura anchored a two-hour workshop for Tuesday of week 2 to get aligned before locking discovery. Tribe opens with a recommendation and a working demo, and the room goes deep from there. Carlos's skepticism was named openly and accepted as the real constraint the demo has to answer. His fax question stands as one the workshop must be ready for.

## Transcript

[Laura Chen — GM Commercial (Tribe)] (0:45)
Thanks everyone for making the time. Since this is the first time most of us are meeting, let's do a quick round before we dive in. I'm Laura Chen, GM on the Tribe side — I own this engagement, and I'm your escalation path if anything needs it. Day to day you'll be working with our forward-deployed PM here — she's on the ground with you through discovery.

[You (FDPM)] (1:10)
Hi everyone. I'll be onsite with you most of this week, so you'll see a lot of me.

[Priya Raman — Architect (Tribe)] (1:30)
Priya Raman, architect on the Tribe side. I'll be shaping the technical design.

[Laura Chen — GM Commercial (Tribe)] (2:18)
Carlos, do you want to do the honors on your side?

[Carlos Reyes — GM Insurance Services (Meridian)] (2:33)
Sure. Carlos Reyes, Meridian — I run Insurance Services, so this is my P&L we're talking about. Sandra?

[Sandra Okafor — VP Claims Operations (Meridian)] (2:45)
Sandra Okafor, VP of claims operations here at Meridian. The adjusters you'll be sitting with this week are my team.

[Michael Torres — VP Engineering (Meridian)] (2:57)
Michael Torres, VP of engineering. The systems you'll be integrating with are mine — and so were the last two attempts at this, so you'll be hearing plenty from me.

[Laura Chen — GM Commercial (Tribe)] (3:17)
Good. Carlos, over to you to frame what success looks like.

[Carlos Reyes — GM Insurance Services (Meridian)] (3:32)
I'll be direct, because I think it's the most useful thing I can be. My board is watching cost-to-serve. We're at four-thirty to six-fifty a claim depending on channel, and I've told them we take twenty-five percent out of that, blended. That's the number.

[Carlos Reyes — GM Insurance Services (Meridian)] (3:57)
And here's the context you should have going in. We've taken two swings at this ourselves. The first one actually shipped — a scoring engine, back in 2021, that was supposed to tell us which claims could be handled automatically. It ran on every claim, it went stale, and my people stopped believing it. It's still on their screens today, which tells you something. The second was a few months back — new team, new technology, a lot of enthusiasm and whiteboards, and it never got out of the lab. My people gave up evenings for that one. We signed with you because we think this time can be different. Just understand what you're walking into — if I push hard, that's why.

[You (FDPM)] (4:32)
That helps us, actually. What killed them — was it the tech, or was it something else?

[Carlos Reyes — GM Insurance Services (Meridian)] (4:57)
Michael should answer that. They were his teams.

[Michael Torres — VP Engineering (Meridian)] (5:20)
They were, and I'll give it to you straight, because it's cheaper for you to hear it now. Two different deaths. The score shipped and then quietly rotted — we never built a way to check it was still right, the people who wrote it moved on, and by the time the floor stopped trusting it there was nobody left who could say why it scored anything the way it did. Nobody killed it. It just stopped mattering, which is worse. The second attempt never shipped anything. We finally had real labeled data, a team of mine picked it up to do something with generative AI, decided the answer was a retrieval pipeline over our old claims and notes — and then spent a quarter arguing about how to fold it together instead of deciding what it was for. Everyone drifted back to their day jobs. I'll give you the full postmortems Thursday.

[You (FDPM)] (5:55)
That's a more useful postmortem than most engagements start with. We intend to do the opposite. Design inside the constraints from day one, not discover them at the end.

[Laura Chen — GM Commercial (Tribe)] (12:57)
Understood, and that's the frame we're building to. Just so it's said out loud — this is five million, six months. Two-week discovery, which is where we are now. And there's a formal checkpoint at the end of month three. That's a real gate. Continuation depends on what we can show by then against the goals in the SOW.

[Carlos Reyes — GM Insurance Services (Meridian)] (13:27)
Good. I want that gate to mean something.

[You (FDPM)] (13:52)
Then let me tell you how we want to spend this first week, because it's the opposite of "trust us, integrate later." We're going to be in your office, talking to you and to your staff. Understand how a claim actually moves, where the cost sits, what compliance won't allow, before we propose anything.

[Sandra Okafor — VP Claims Operations (Meridian)] (14:22)
That I can help with. I'd rather you sit with us than read about us. Come tomorrow — I'll walk you through operations end to end. Intake, triage, how it lands in an adjuster's queue, disposition. All three channels. And then I'll put you on the floor next to my adjusters — one senior, one in his second year, so you see the learning curve too. Watch them work real claims. That's where you'll actually see it.

[You (FDPM)] (15:17)
That's exactly what we need. Thank you, Sandra.

[Priya Raman — Architect (Tribe)] (15:42)
Michael, while I've got you — where do we stand on data? I'd rather we reason off your real claims than assumptions, and I don't want to spend week one waiting on access requests.

[Michael Torres — VP Engineering (Meridian)] (16:05)
You won't have to. My analytics team finished a pass over our claims data recently — a five-thousand-claim extract out of Snowflake, stratified, masked on policyholder fields, with a findings memo on top of it. I'll send you both today. Read their memo before you re-derive anything; they're good, and it'll save you a week.

[Priya Raman — Architect (Tribe)] (16:30)
That's the best answer I've gotten to that question in years. We'll start there.

[Michael Torres — VP Engineering (Meridian)] (24:37)
Now the part I care about, because I've watched this go wrong two different ways. Anything — anything — that gets near a claim decision, I want to see before it goes anywhere. That's not me trying to slow you down. It's the opposite. My systems are what enforce the rules here, and the bar for anything new is a lot higher than it was in 2021 — the score never had to face what you'll have to face. Loop me in early and I can tell you where the walls are while it's cheap to move. Loop me in late and you'll meet them the expensive way.

[You (FDPM)] (25:32)
That's how we'd want it too.

[Michael Torres — VP Engineering (Meridian)] (25:52)
Then let's book real time. Thursday. I'll walk you through the systems — ClaimsPro, the data estate, what you can and can't touch — and the constraints that killed the last two builds. Bring whoever's shaping the technical approach.

[Priya Raman — Architect (Tribe)] (26:10)
That'll be me. I'll come with questions, not answers. I want to understand your non-negotiables before I draw a single box.

[Michael Torres — VP Engineering (Meridian)] (26:22)
Good answer.

[Carlos Reyes — GM Insurance Services (Meridian)] (26:47)
Somebody owning the decision and checking the work is exactly what the last two didn't have. So — I like this so far. But I'll hold my judgment for the demo.

[Carlos Reyes — GM Insurance Services (Meridian)] (27:10)
And put one more thing on your list, because I'll raise it at that workshop if you don't. Somebody explain to me why we should get better at digesting faxes instead of getting rid of some of them. A quarter of our volume walks in the expensive door. Move the big senders — the provider networks, the body shops — onto the portal or clean EDI, and that cost just goes away. No claim touched. Maybe there's a good reason we haven't. I want to hear it either way.

[You (FDPM)] (27:35)
It's on the list. That's exactly the kind of question discovery is for.

[You (FDPM)] (27:55)
Sandra, one thing I want to protect for tomorrow — I don't want to just be shown the happy path. The clean claim that flows through. I want to see the messy ones. The fax that came in garbled, the bodily-injury claim the adjuster's nervous about. That's where the cost and the risk live.

[Sandra Okafor — VP Claims Operations (Meridian)] (28:20)
Then you'll like the floor. Believe me, my adjusters will not sugarcoat it. They'll tell you exactly what's broken. That's half of why turnover's where it is.

[Laura Chen — GM Commercial (Tribe)] (37:27)
Let me land where this is going, so expectations are shared. The week-1 plan: Sandra's walkthrough and floor session tomorrow, Michael's systems session Thursday, and the extract and memo in our hands today.

[Laura Chen — GM Commercial (Tribe)] (37:52)
Then the Tuesday after next — that's the session that matters, and I want to ask for real time. Two hours, working-session format, everyone on this call. We'll open it — half an hour, where we've landed and a working demo. Show, don't tell. Something real, Carlos, to your point. And then we shape it together in the room, before we lock discovery scope. Not a finished product. A concrete thing you can push on, and two hours to push on it.

[Carlos Reyes — GM Insurance Services (Meridian)] (38:22)
That's the right ask. A demo I can react to. If it's real, my team leans in. If it's slideware, they've seen that movie twice.

[Sandra Okafor — VP Claims Operations (Meridian)] (38:42)
And I'll have adjusters who'll want to see it too, because they're the ones who'd use it.

[You (FDPM)] (39:00)
Then that's the bar. We open with a recommendation and a working demo, and we leave that room aligned on scope. We know the checkpoint at month three is the real gate. That workshop is how we earn the runway to it.

[Michael Torres — VP Engineering (Meridian)] (39:22)
Just keep me between here and there. Nothing near live claims without me seeing it.

[You (FDPM)] (39:37)
Continuously. Not just Thursday.

[Carlos Reyes — GM Insurance Services (Meridian)] (40:05)
All right. Sandra's got you tomorrow. Michael Thursday. Let's see what you find.

[Laura Chen — GM Commercial (Tribe)] (40:27)
Appreciate it, everyone. We'll see you onsite tomorrow morning.
