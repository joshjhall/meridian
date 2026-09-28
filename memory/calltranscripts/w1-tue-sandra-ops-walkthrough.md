---
source: sybill
conversation_id: a1d4e7b9-2c85-4f6a-b3d1-9e0c5a7f8241
day: "Week 1, Tuesday"
title: "Claims Operations Walkthrough & Floor Session with Sandra Okafor"
participants: [Sandra Okafor — VP Claims Operations (Meridian), Senior Adjuster (Meridian, 11 years), Second-Year Adjuster (Meridian), You (FDPM), Priya Raman — Architect (Tribe)]
duration_minutes: 90
visibility: internal
---

## Summary

### How a claim moves
Sandra Okafor (VP Claims Operations) walked the full path: intake (from one of three channels) → triage in ClaimsPro's rules engine → assignment to an adjuster queue → the adjuster works it → disposition (paid, partially paid, denied, or routed for more review). Assignment within a queue is largely round-robin, not skill-matched. Most of a claim's life is queue wait.

### The three channels and their pain
E-Portal (~42% of volume, ~$430/claim) is the clean, cheap path, with structured data written straight into ClaimsPro. Phone (~31%, ~$650) is the most expensive; call-center agents key everything in by hand. Fax/EDI (~27%, ~$610) is the messiest. Faxes are OCR'd at roughly 78% accuracy, and adjusters re-key and correct garbled fields before they can even start deciding.

### One claim, end to end
Sandra walked a real E-Portal collision claim, IS-CLM-2025000300 (Florida, ~$2,825, worked by one of her senior adjusters), from clean intake through a 34.7-hour cycle to paid-in-full. Almost none of that cycle is handling; the claim sits in queue waiting to be picked up, which puts the bottleneck upstream of the adjuster. And it is the best case. She was explicit that most claims are not this tidy.

### The score the adjusters ignore
Every claim carries a 2021 automation-eligibility score, produced by the triage engine, and nobody trusts it. Sandra's team has learned to ignore it ("it's usually wrong") because it over-weights dollar amount and doesn't look at complexity, and nobody has recalibrated it since. It's on the screen, and everybody works around it.

### Sandra's first fix: sort the queue
Asked what she'd fix first with a free hand, Sandra didn't pick a new tool. Assignment inside each queue is round-robin, blind to age, amount, and who's good at what. In her words, "half my cycle-time problem is a dispatch problem." Her bar for anything new is that it has to beat the boring fix already sitting there.

### On the floor: the 8am ritual and the fax grind
The second half of the session moved to the floor. Both adjusters start the day the same way: open ClaimsPro, read the overnight queue, and triage by gut. Nothing is sorted by age, risk, or SLA. The senior adjuster (11 years in, covering the shared fax queue) re-keyed a garbled OCR estimate live, then walked her specimen fax claim, IS-CLM-2025002993 (California, ~$49K, closed a few months back, a colleague's), end to end: an estimate line the OCR read as "1,B00" instead of 1,800, a claimant-contact field the fax cut off that took a phone chase, and, after all the cleanup, a pre-existing-damage denial. Her line: "I spend more time fixing what the fax machine ate than deciding anything." A single claim spans roughly seven ClaimsPro screens, reconciled in the adjuster's head.

### The judgment call with no precedent
The second-year adjuster walked back through IS-CLM-2025004222 (New York, ~$59.5K), a phone bodily-injury claim he closed a few months back. Unsure on the coverage call, he built the injury timeline by hand from a rough auto-generated transcript, escalated to senior review, and watched the claim come back paid-in-full four days later. What he wants most is to see how senior adjusters handled similar claims before. That reference doesn't exist today; it's in people's heads or in old claim notes he can't search.

### Where the senior's week actually goes
Pressed on whether killing the intake grind fixes the job, the senior adjuster said no; it fixes the mornings. Her week goes to the hard files. A complex bodily-injury claim is two or three days of records-gathering, timeline-building, and writing a justification that will hold up if challenged. Her estimate: a fifth of the queue, most of her real hours. In her telling, nobody who pitches automation has ever once offered to help with those.

### Capacity reality
Adjusters carry 15–18 claims a day. The gap between capacity and a volume growing ~8% a year is covered by overtime and contractor surges, which feed a 22% annual turnover rate. The team is always partly training up. Exit interviews repeat one line: too much time on paperwork, not enough on judgment.

## Outcome

The FDPM and Priya Raman (Tribe architect) left with a concrete mental model of the intake-to-disposition path, the cost gap between channels, and where time is actually lost (queue wait and fax rework, not adjuster speed), plus Sandra's unprompted bet that fixing assignment and prioritization would move the numbers before anything new lands on an adjuster's screen. The floor's asks pull in different directions, though: the senior adjuster wants the fax grind gone but argues the deeper sink is the complex files; the second-year wants precedent for judgment calls; both want fewer screens and a queue that sorts itself. Which of those anchors wave one is an open product call, not something the session settled.

## Transcript

[Sandra Okafor — VP Claims Operations (Meridian)] (0:50)
Morning, you two. You found the building okay? The signage in that lobby is useless.

[You (FDPM)] (1:10)
The badges got us through, and Priya found the coffee machine.

[Priya Raman — Architect (Tribe)] (1:25)
"Found" is generous. It made something coffee-adjacent.

[Sandra Okafor — VP Claims Operations (Meridian)] (1:45)
I should have warned you. There's a decent place across the street — that's a day-two lesson. All right, you've got me for ninety minutes. First half is the map and a real claim on screen. Second half we go out on the floor and you sit with two of my adjusters. Let me use it.

[Sandra Okafor — VP Claims Operations (Meridian)] (2:10)
Okay. Let me give you the map first, or none of it'll make sense. A claim comes in through one of three doors. Then ClaimsPro triages it — rules engine, looks at type, amount, region — and drops it into a queue. An adjuster picks it up, works it, and dispositions it. Paid, partly paid, denied, or kicked for more review.

[You (FDPM)] (2:55)
And the three doors are e-portal, phone, fax slash EDI?

[Sandra Okafor — VP Claims Operations (Meridian)] (3:25)
Right. And they could not be more different in cost. E-portal's about forty-two percent of our volume, and it's the cheap one — call it four-thirty a claim. Data's structured, writes straight into ClaimsPro, barely touched by a human until an adjuster looks at it.

[Sandra Okafor — VP Claims Operations (Meridian)] (4:10)
Phone's about thirty-one percent, and it's our most expensive — six-fifty a claim. A call-center agent is typing everything a person says into the system in real time. Every field is hand-keyed.

[Priya Raman — Architect (Tribe)] (4:55)
And fax slash EDI?

[Sandra Okafor — VP Claims Operations (Meridian)] (5:20)
Twenty-seven percent, around six-ten. That's the messy one. EDI's fine when it's clean, but a lot of it is faxed repair estimates and medical docs. We OCR the faxes, and the OCR is — Priya, be generous and call it seventy-eight percent. So an adjuster's first job on a fax claim isn't deciding anything. It's fixing what came through wrong.

[You (FDPM)] (6:15)
Let's come back to that, because it sounds like where cost hides. Can we walk a real one first?

[Sandra Okafor — VP Claims Operations (Meridian)] (7:55)
Yes. Let me pull a clean one so you see the ideal path, and then you'll appreciate how rare it is. Here — IS-CLM-2025000300. E-portal collision, Florida, about twenty-eight hundred dollars. One of my senior adjusters worked it — you'll be sitting with her in a bit.

[You (FDPM)] (8:30)
Walk me through what happens from the moment it lands.

[Sandra Okafor — VP Claims Operations (Meridian)] (9:30)
So it comes in through the portal, structured, clean. ClaimsPro triages it — simple collision, low amount, Florida — routes it to a queue. She picks it up. Everything she needs is already in the fields, because the portal captured it. She verifies coverage, checks the estimate, no red flags. Paid in full.

[You (FDPM)] (10:40)
And how long did that whole thing take?

[Sandra Okafor — VP Claims Operations (Meridian)] (11:10)
Start to disposition, this one was about thirty-five hours. And here's what I want you to notice — almost none of that thirty-five hours is her working. It's the claim sitting in the queue waiting for her to get to it. The actual hands-on time is tiny.

[Priya Raman — Architect (Tribe)] (12:05)
So the cycle time is mostly wait, not work.

[Sandra Okafor — VP Claims Operations (Meridian)] (12:30)
On the clean ones, absolutely. Which is why "make the adjuster faster" is the wrong instinct. They're not slow. The claim's waiting in line.

[You (FDPM)] (13:10)
I see a field here — automation eligibility score, eighty-five. What's that driving?

[Sandra Okafor — VP Claims Operations (Meridian)] (13:40)
Honestly? Not much. That's an old score. Rules engine somebody built back in 2021 to guess whether a claim could be auto-handled. Michael's people own it — ask him Thursday what he thinks of it. It won't be a defense.

[You (FDPM)] (14:05)
Do your adjusters use it?

[Sandra Okafor — VP Claims Operations (Meridian)] (14:50)
My team has learned to ignore it — it's usually wrong. It'll tell you a hairy bodily-injury claim is a slam dunk and flag a clean two-thousand-dollar collision as risky. It weights the dollar amount too hard and doesn't look at complexity at all. Nobody's recalibrated it since it went in. So it's on the screen, and everybody just works around it.

[Priya Raman — Architect (Tribe)] (15:15)
It's a column in the extract Michael sent over — I'll look at how it's distributed against the rest.

[Sandra Okafor — VP Claims Operations (Meridian)] (15:40)
Look all you want — his analytics people already took a swing at it, it's in their memo. I'm just telling you what the people who work these claims think of it. Ask me or ask my adjusters what a claim actually is — you'll get a straighter read than any field on that screen.

[You (FDPM)] (19:35)
Can I ask you something direct? If you had our budget and didn't have to clear it with anyone, what would you fix first?

[Sandra Okafor — VP Claims Operations (Meridian)] (20:15)
You'll laugh. I'd sort the queue. I'm serious. Assignment inside a queue is round-robin. A claim can sit there three days and nothing in the system cares, and my fastest bodily-injury adjuster gets handed the same mix as somebody who started in the spring. Half my cycle-time problem is a dispatch problem.

[Priya Raman — Architect (Tribe)] (20:50)
That's barely even an AI problem.

[Sandra Okafor — VP Claims Operations (Meridian)] (21:30)
I know it. And that's why nobody's ever fixed it. Everybody who comes through here wants to build something new for my adjusters to look at, and the whole time the claims are standing in the wrong lines. If what you end up building is mostly a smarter dispatcher, you won't hear me complain.

[You (FDPM)] (22:20)
Understood. And on a fax claim — what does an adjuster actually spend the time on?

[Sandra Okafor — VP Claims Operations (Meridian)] (23:05)
Re-keying. The OCR mangles a repair estimate, drops a field, misreads a number. She's reading the original fax next to the record and retyping it. And if a field's just missing — no claimant phone number, no policy detail — she's chasing it down before she can move. Don't take my word for it. Come on, let's go out to the floor and you can watch. Fifteen to eighteen claims a day, each of them, while volume grows about eight percent a year. We cover the gap with overtime and seasonal contractors, which is exactly how you burn people out — twenty-two percent turnover, industry's around eighteen. The exit interviews all say the same thing: too much time on paperwork, not enough on judgment.

[Sandra Okafor — VP Claims Operations (Meridian)] (26:40)
Here we are. Two of my best — eleven years, and second year. Pull up chairs. Pretend you're not here, just watch them work.

[Senior Adjuster (Meridian, 11 years)] (27:10)
Hope you brought a sweater. Facilities keeps this floor at meat-locker temperature and we've all given up complaining. Okay — eight a.m., every day, same thing. I open ClaimsPro, pull up my queue, and just read it. What came in overnight, what's aging, what's going to be a fight. Nobody sorts it for me. I decide the order in my head. Today I've also got the fax queue up — covering for someone who's out.

[Priya Raman — Architect (Tribe)] (27:40)
So the system doesn't prioritize? No "this one's about to breach"?

[Senior Adjuster (Meridian, 11 years)] (28:05)
No. If something's aging, I catch it because I've been doing this eleven years. My colleague here is in his second year — he doesn't always catch it yet. That's not on him, there's just no flag for it.

[You (FDPM)] (28:30)
Can you take one and walk it?

[Senior Adjuster (Meridian, 11 years)] (28:55)
Sure. Top of the fax queue I'm covering — came in overnight, faxed repair estimate on it. This is the kind that ruins a morning. Watch.

[Senior Adjuster (Meridian, 11 years)] (38:45)
So this came in as a fax. Repair estimate, the works. It got OCR'd, and half the line items came through garbled. So I've got the original fax open here, and the record here, and I'm literally reading one and retyping into the other. By hand. Every fax claim, some amount of this. And this one's mild, honestly. Let me show you the one I keep as the example.

[Senior Adjuster (Meridian, 11 years)] (39:35)
IS-CLM-2025002993. Closed a few months back, off this same shared queue — a colleague's, not mine, but it's the whole pattern in one file. Bodily injury, California, about forty-nine thousand. The OCR read the eighteen-hundred-dollar bumper line as "1,B00". And see this field — claimant contact, blank. The fax cut it off at the edge of the page. So before it could move, somebody had to call and chase it. A phone call, a note, two days of wait — it's all in the log.

[Priya Raman — Architect (Tribe)] (40:20)
And after all that?

[Senior Adjuster (Meridian, 11 years)] (40:45)
After all that, the photos showed old corrosion on the rear quarter and it went out as a denial — pre-existing damage. Days of cleanup and chasing on a claim that ends in a no. That's the fax queue for you. This is the part that gets me. I'm an adjuster. I'm supposed to be deciding whether claims hold up. Instead — I spend more time fixing what the fax machine ate than deciding anything. On a bad day that's most of my day.

[You (FDPM)] (41:20)
How many screens are you touching just to get the picture on this one claim?

[Senior Adjuster (Meridian, 11 years)] (42:05)
Let's count. Summary screen. Coverage. Documents — that's where the fax lives. Notes. Payments. Correspondence, for the letters. Workflow tasks. That's seven. And there's no one screen that shows me the claim. I hold it together in my head by tabbing. You get fast at it. Whether fast is the same as good, I couldn't tell you. On this claim I've spent — what, ten minutes? — and I haven't made a single adjudication decision yet. I've done data entry.

[Priya Raman — Architect (Tribe)] (42:50)
Say the cleanup went away tomorrow. Every fax lands clean, nothing to re-key. Does that fix the job?

[Senior Adjuster (Meridian, 11 years)] (43:35)
It'd help, don't get me wrong. But that's my mornings. Where the week goes is the hard ones. A complex bodily-injury file is two, three days of real work. Records requests. Building out the injury timeline. Then the write-up, which has to hold if a lawyer pulls the file later, or a regulator. That's maybe a fifth of what's in my queue and it's most of my hours.

[Senior Adjuster (Meridian, 11 years)] (44:20)
Eleven years, and every automation pitch I've sat through is about the easy claims. The easy claims were never the problem. They're slow because they sit in line, not because anyone's working them. Nobody's once come in and said, we'll help you with the write-up on the hard one.

[You (FDPM)] (44:45)
Nobody's pitched you that? Ever?

[Senior Adjuster (Meridian, 11 years)] (45:15)
You'd be the first.

[You (FDPM)] (45:40)
Okay. That's good for us to hear. Thank you. Can we switch to the phone side?

[Second-Year Adjuster (Meridian)] (56:10)
Yeah, so — this is the one that stuck with me. I closed it a few months back. IS-CLM-2025004222. Phone intake, New York, bodily injury, and it's big — just under sixty thousand. Fifty-nine five.

[You (FDPM)] (56:40)
Talk me through why it stuck.

[Second-Year Adjuster (Meridian)] (57:15)
Because it was a judgment call and I didn't have a strong read. The claimant's account and the medical documentation didn't line up cleanly — the first medical visit came days after the loss. It was over the threshold where I can't just wave it through. And with bodily injury that size, if I get the coverage call wrong, that's a real problem — for the claimant and for us.

[Priya Raman — Architect (Tribe)] (57:40)
What do you do when you're unsure like this?

[Second-Year Adjuster (Meridian)] (58:10)
Honestly? I sit on it. I re-read it. Maybe I catch one of the seniors between claims and ask. But they've got their own queues. What I really wish I had — I wish I could see how the senior adjusters handled claims like this one before. Similar injury, similar amount, similar mismatch. Show me five of those and what they decided and why, and I'd know what I'm looking at.

[You (FDPM)] (58:35)
And there's no way to pull that up today?

[Second-Year Adjuster (Meridian)] (59:10)
No. It's all in people's heads, or buried in old claim notes I can't search. So a second-year like me is basically guessing, or interrupting someone who's been here eleven years. There's no in-between.

[Senior Adjuster (Meridian, 11 years)] (60:10)
And that's how mistakes happen. Not because he's not smart — because he's got no reference. When I was new, I sat next to someone for two years. He doesn't get that. Everybody's too busy.

[You (FDPM)] (60:40)
So on that claim, what did you end up doing?

[Second-Year Adjuster (Meridian)] (61:25)
I had seven documents open across — same thing she said, the screens. I built the injury timeline by hand from the notes and the phone transcript. The call transcript's rough, it's auto-generated, so I was half-guessing what was actually said. Then I wrote it up and routed it for senior review, because I wasn't confident enough to call it alone. It came back four days later — coverage responds, paid in full. Four days I'd have saved if I could've seen five claims like it.

[Priya Raman — Architect (Tribe)] (61:50)
Which was the safe move, but it's another human touch on a claim.

[Second-Year Adjuster (Meridian)] (62:15)
Right. And senior review was backed up too. Most of those four days it wasn't being looked at — it was waiting in another line.

[You (FDPM)] (84:35)
This is incredibly useful, all of you. If I play it back — mornings you self-triage a queue nobody's sorted, you're across seven screens per claim, the fax cleanup eats the mornings and the complex files eat the week, and the hard calls have no precedent to lean on.

[Senior Adjuster (Meridian, 11 years)] (85:00)
That's the day. You just described the whole day.

[Second-Year Adjuster (Meridian)] (85:20)
And the part that stings is none of it is the actual claims work. The cleanup and the guessing, that's what makes it a bad day. Give me the claim clean and something to compare it against, and I'd be fine.

[Sandra Okafor — VP Claims Operations (Meridian)] (85:45)
Now you've seen it, not read about it. Don't automate the decision — that's the fun part, and half of it we're not even allowed to. Automate the grind that gets a claim ready to decide. And ask me anything the numbers throw up — half the time there's a story behind them the extract won't show you.

[You (FDPM)] (86:05)
That framing is exactly what we needed. Thank you — all three of you.

[Senior Adjuster (Meridian, 11 years)] (86:20)
Come back anytime. Just don't build us an eighth screen.
