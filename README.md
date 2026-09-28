# Meridian Engagement — Candidate Instructions (Staff UX Designer)

## What this is

You are a Staff UX Designer at Tribe. The Forward Deployed PM running the Meridian engagement has brought you in at the end of week 1 to put a designer's eye on what gets built. Something new will be built: the engagement runs six months and ships Meridian's first production AI capability, and this is week 1 of the two-week discovery that decides what that capability is. This repository is the engagement's shared memory (every Tribe engagement runs on one), exactly as she shared it with you on Friday morning. One convention to know: the repo is written from her seat, so she appears in the transcripts as "You (FDPM)", the PM who brought you in.

`docs/` holds the durable artifacts: the signed SOW and the pre-engagement research notes. `memory/` is the running record of the work: call transcripts and decisions of record. `reference/` holds what Meridian handed over: the claims extract, its data dictionary, and their analytics team's findings memo. `sample_claims/` holds real claim files. Anyone who opens this repo has the full context of the engagement so far, including you.

## Your session

In the fiction: Tuesday of week 2 is a two-hour working session with Meridian's stakeholders, where discovery becomes a decision about what to build. Tribe opens it with one recommendation and a working demo. The direction is not locked; that pick is the PM's to make, and she makes it Friday. What she has asked you for is your own, independent perspective on the experience: who touches this system, what actually changes on the adjusters' floor, where a human stays in the loop, and what the first thing worth building feels like to use. You have Friday to form that perspective and build it out. Monday morning, you walk the Tribe team through it. That Monday session is this session: deliver it as you would to your own team, then your colleagues poke at it.

Outside the fiction: this is a 45-minute panel interview. The first 30 minutes are that walkthrough; the remaining 15 are Q&A for your Tribe team to "poke" and ask questions. The panel sits where your Tribe colleagues sit. Nobody is playing Meridian.

## What to bring

Two things: a short context deck and a demo. Spend most of your time on the demo.

**The deck** is context, not the main event; the PM will flesh it out for the client room. Keep it short and cover:

- The experience point of view you'd fight for, and why, grounded in the specific people, claims, and constraints in this repo.
- Who the users are and what changes for them, including where a human stays in the loop and what that handoff looks like.
- The two or three design decisions that matter most, and what you considered and rejected.

**The demo** carries the argument: the experience working rather than described, something concrete the room can react to and pull apart. It has to run, not just be a static mock. Rough is expected; sharp decisions are not optional. The sample claims in `sample_claims/` are good inputs, though you are not required to use them.

## What we are not asking for

Not a product strategy, business case, or delivery plan (that is the PM's half of the work). Not an exhaustive data analysis; Meridian's analytics team already did a pass, in `reference/analytics_memo.md`. Not pixel polish. We want sharp, defensible experience decisions, not finished visuals.

## Time

This exercise is designed to take 4–6 hours, including building your demo. We tried our best to set it up to not reward more time than that.

## Where to start

Core reading, about an hour:

- `AGENTS.md` — the engagement's context file: who's who, the goals, the systems, where things live
- `docs/project/sow.md` — the signed Statement of Work, goals, and structure
- The three call summaries in `memory/calltranscripts/`
- `reference/analytics_memo.md` — Meridian's own analysis of the claims extract
- `sample_claims/` — representative claims to build and test against

Then: the rest of `reference/` is background (the dataset and its data dictionary). Consult them as needed; do not exhaustively analyze them.

## AI tools

Use them. They are strongly encouraged for everything here: analyzing the data, shaping your pitch, building your demo, and yes, pointing an agent at this repo to get oriented fast. That is exactly the kind of leverage the role is about.

Two rules. You own every element you present and must be able to defend it; if it is in your demo, it is yours. And unedited AI output is obvious to the panel: the best work we see is concise, opinionated, and clearly human-edited. Expect to be asked about your process.
