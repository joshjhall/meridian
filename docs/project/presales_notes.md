# Meridian Pre-Engagement Research Notes

**Internal Tribe notes. Not for circulation to client.**

Compiled before kickoff from pre-sales conversations with Meridian's Insurance Services (IS) BU. This is the organizational picture we walked in with (team shapes, capacity, change-control
cadence), captured so the delivery team starts with shared context instead of rediscovering it
onsite. Treat as background; verify anything load-bearing during Discovery.

## Claims operations

The claims org runs 95 adjusters, including 12 seniors and 4 team leads, reporting to Sandra
Okafor (VP Claims Operations). Adjusters process 15–18 claims a day. Staffing covers roughly 390K
claims a year, but actual volume is around 400K and growing ~8% year over year; the gap is
absorbed through overtime and seasonal contractor surges. That shows up as burnout and cost
pressure. Annual turnover is 22%, against an industry average of 18%. The recurring theme from
their last engagement survey, "too much time on paperwork, not enough on judgment calls,"
is worth keeping in front of us. The pain adjusters feel is clerical load, not decision-making.

## Data and analytics

The IS data/analytics team is 6 data engineers and 3 data scientists, reporting up to Michael
Torres (VP Engineering). They own the Snowflake/Databricks environment and are our primary point
of contact for data access. Read on them: responsive but capacity-constrained. Expect roughly 2–3 weeks turnaround
on a new data-pipeline request, so anything we need built on their side should be raised early.

## IT support

IT support for IS is a 5-engineer group: 2 on ClaimsPro, 2 on infrastructure, 1 on integrations.
They handle business-as-usual support and minor enhancements. Anything more substantial pulls in
the platform team under Michael Torres (VP Engineering), so we should scope around what this group
can absorb directly versus what needs escalation.

## Change control

All production changes go through the Change Advisory Board (CAB), which meets weekly on Thursdays.
Average approval time is about 5 business days from the time of submission. Emergency changes require sign-off from the VP Engineering and
the GM. Practically: any path to production has a CAB gate on it, so we need lead time in
the delivery schedule.
