"""Evidence for the review-rate target discussion (open question C1).

Reproduces every figure cited in docs/discovery/open_questions.md under
"Why <20% is not reachable as written". Standard library only.

    python3 analysis/review_floor.py
"""

import csv
import math
import random
from collections import Counter
from pathlib import Path

EXTRACT = Path(__file__).resolve().parent.parent / "reference" / "claims_processing.csv"
NAMED_STATES = {"CA", "NY", "NJ", "FL", "IL", "PA", "OH", "GA"}  # named by Michael (W1 Thu, 20:05)
THRESHOLD = 10_000


def yes(row, field):
    return row[field] == "Yes"


def amount(row):
    return float(row["claim_amount_usd"])


def pct(k, n):
    return 100 * k / n


def ci95(k, n):
    """Normal-approximation 95% half-width, in percentage points."""
    p = k / n
    return 196 * math.sqrt(p * (1 - p) / n)


def share(rows, field):
    return f"{pct(sum(yes(r, field) for r in rows), len(rows)):5.1f}% (n={len(rows)})"


def main():
    rows = list(csv.DictReader(EXTRACT.open()))
    n = len(rows)

    print("== 1. Regulatory floor across the full extract ==")
    reg = sum(yes(r, "requires_human_by_regulation") for r in rows)
    flagged = sum(yes(r, "flagged_for_human_review") for r in rows)
    print(f"requires_human_by_regulation = Yes: {reg}/{n} = {pct(reg, n):.1f}% (±{ci95(reg, n):.1f})")
    print(f"flagged_for_human_review = Yes:     {flagged}/{n} = {pct(flagged, n):.1f}%")

    print("\n== 2. Regulation-flag rate by state, split at $10K ==")
    print("state  <=$10K           >$10K")
    inferred = set()
    for state in sorted({r["state"] for r in rows}):
        lo = [r for r in rows if r["state"] == state and amount(r) <= THRESHOLD]
        hi = [r for r in rows if r["state"] == state and amount(r) > THRESHOLD]
        if all(yes(r, "requires_human_by_regulation") for r in hi) and not any(
            yes(r, "requires_human_by_regulation") for r in lo
        ):
            inferred.add(state)
        tag = " named" if state in NAMED_STATES else (" inferred" if state in inferred else "")
        print(f"{state}     {share(lo, 'requires_human_by_regulation')}  {share(hi, 'requires_human_by_regulation')}{tag}")
    print(f"States behaving as $10K-threshold states: {len(inferred)}: {', '.join(sorted(inferred))}")
    print(f"  of which not named by Michael: {', '.join(sorted(inferred - NAMED_STATES))}")

    print("\n== 3. Floor under alternative readings ==")
    thresh_hi = sum(r["state"] in inferred and amount(r) > THRESHOLD for r in rows)
    other_reg = sum(r["state"] not in inferred and yes(r, "requires_human_by_regulation") for r in rows)
    strictest = sum(
        amount(r) > THRESHOLD or (r["state"] not in inferred and yes(r, "requires_human_by_regulation"))
        for r in rows
    )
    print(f"As marked: $10K rule in {len(inferred)} states ({pct(thresh_hi, n):.1f}%) "
          f"+ other states' rule ({pct(other_reg, n):.1f}%) = {pct(thresh_hi + other_reg, n):.1f}%")
    print(f"Strictest reading ($10K rule in all states + other states' rule): {pct(strictest, n):.1f}%")

    print("\n== 4. What a perfect flag would flag (500-claim calibration sample) ==")
    cal = [r for r in rows if r["review_actually_needed"]]
    m = len(cal)
    print("Caveats: n=500, Q4 2025, not built as an evaluation set (analytics_memo.md, 'Known limits').")
    print(f"Sample regulated share: {share(cal, 'requires_human_by_regulation')} vs {pct(reg, n):.1f}% in full extract")
    needed = sum(yes(r, "review_actually_needed") for r in cal)
    print(f"review_actually_needed = Yes: {needed}/{m} = {pct(needed, m):.1f}% (±{ci95(needed, m):.1f})")
    must = sum(yes(r, "review_actually_needed") or yes(r, "requires_human_by_regulation") for r in cal)
    print(f"Needed OR regulated (perfect-flag rate): {must}/{m} = {pct(must, m):.1f}% (±{ci95(must, m):.1f})")
    nonreg = [r for r in cal if not yes(r, "requires_human_by_regulation")]
    print(f"Needed among non-regulated claims: {share(nonreg, 'review_actually_needed')}")
    cal_flagged = sum(yes(r, "flagged_for_human_review") for r in cal)
    print(f"Current flag rate in the sample: {cal_flagged}/{m} = {pct(cal_flagged, m):.1f}%")
    confusion = Counter((r["flagged_for_human_review"], r["review_actually_needed"]) for r in cal)
    print("Current flag vs label (flagged, needed): "
          + ", ".join(f"{k}={v}" for k, v in sorted(confusion.items())))
    miss_reg = sum(
        yes(r, "requires_human_by_regulation") and not yes(r, "flagged_for_human_review") for r in rows
    )
    print(f"\nFull extract: regulation-required but NOT flagged: {miss_reg}")
    print(f"Full extract: flagged but NOT regulation-required: "
          f"{sum(yes(r, 'flagged_for_human_review') and not yes(r, 'requires_human_by_regulation') for r in rows)}")

    print("\n== 5. Representativeness checks ==")
    states = Counter(r["state"] for r in rows)
    print(f"Claims per state: min {min(states.values())}, max {max(states.values())} across {len(states)} states "
          "(near-uniform suggests stratification by state)")
    in_thresh = [r for r in rows if r["state"] in inferred]
    out_thresh = [r for r in rows if r["state"] not in inferred]
    print(f"Share of extract in threshold states: {pct(len(in_thresh), n):.0f}%")
    print(f"Floor if all volume were in threshold states: {share(in_thresh, 'requires_human_by_regulation')}")
    print(f"Floor if all volume were in the other states:  {share(out_thresh, 'requires_human_by_regulation')}")
    print("Filed months: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(r["filed_date"][:7] for r in rows).items())))
    for field in ("intake_channel", "complexity", "claim_type"):
        values = sorted({r[field] for r in rows})
        print(f"Calibration vs full, {field}: " + ", ".join(
            f"{v} {pct(sum(r[field] == v for r in cal), m):.0f}/{pct(sum(r[field] == v for r in rows), n):.0f}%"
            for v in values))
    mismatched = sum(
        abs(float(r["queue_wait_hours"]) + float(r["handling_hours"]) - float(r["total_cycle_time_hours"])) > 0.11
        for r in rows
    )
    stray_reason = sum(bool(r["denial_reason"]) != (r["disposition"] == "Denied") for r in rows)
    print(f"Consistency: cycle != wait+handling on {mismatched} rows; "
          f"denial_reason inconsistent with disposition on {stray_reason} rows; "
          f"duplicate claim IDs: {n - len({r['claim_id'] for r in rows})}")

    print("\n== 6. Regulated-but-unflagged claims (V3, M3) ==")
    gap = [r for r in rows if yes(r, "requires_human_by_regulation") and not yes(r, "flagged_for_human_review")]
    handling = sorted(float(r["handling_hours"]) for r in gap)
    print(f"n={len(gap)}; with an adjuster_id: {sum(bool(r['adjuster_id']) for r in gap)}; "
          f"handling hours min {handling[0]}, median {handling[len(handling) // 2]}")
    print(f"In threshold states: {sum(r['state'] in inferred for r in gap)}; "
          f"in other states: {sum(r['state'] not in inferred for r in gap)}")
    print("Dispositions: " + ", ".join(f"{k}={v}" for k, v in Counter(r["disposition"] for r in gap).most_common()))

    print("\n== 7. What explains the regulation flag outside the threshold states (M2) ==")
    other = [r for r in rows if r["state"] not in inferred]
    base = sum(yes(r, "requires_human_by_regulation") for r in other) / len(other)
    print(f"Other states: n={len(other)}, regulated {100 * base:.1f}%. "
          "Each line shows the rate per group; |z| > 2 would suggest the field matters.")

    def rate_by(label, key):
        groups = {}
        for r in other:
            groups.setdefault(key(r), []).append(yes(r, "requires_human_by_regulation"))
        cells = []
        worst = 0.0
        for k, v in sorted(groups.items()):
            p = sum(v) / len(v)
            z = (p - base) / math.sqrt(base * (1 - base) / len(v))
            worst = max(worst, abs(z))
            cells.append(f"{k} {100 * p:.0f}%")
        print(f"  {label:<14} max|z| {worst:.1f}: " + ", ".join(cells))

    def band(r):
        a = amount(r)
        return "<=10K" if a <= THRESHOLD else ">10K"

    rate_by("state", lambda r: r["state"])
    rate_by("claim_type", lambda r: r["claim_type"])
    rate_by("channel", lambda r: r["intake_channel"])
    rate_by("complexity", lambda r: r["complexity"])
    rate_by("amount", band)
    rate_by("score band", lambda r: f"{int(r['automation_eligibility_score']) // 20 * 20:02d}")
    rate_by("review flag", lambda r: r["flagged_for_human_review"])
    rate_by("filed month", lambda r: r["filed_date"][:7])

    # Adjuster: 50 codes, so the largest |z| is expected to be ~2.4 by chance alone.
    # Compare against shuffled labels rather than reading the max |z| directly.
    labels = [yes(r, "requires_human_by_regulation") for r in other]

    def max_adjuster_z(values):
        groups = {}
        for r, v in zip(other, values):
            groups.setdefault(r["adjuster_id"], []).append(v)
        return max(abs(sum(v) / len(v) - base) / math.sqrt(base * (1 - base) / len(v)) for v in groups.values())

    observed = max_adjuster_z(labels)
    rng = random.Random(1)
    shuffles = [max_adjuster_z(rng.sample(labels, len(labels))) for _ in range(500)]
    print(f"  adjuster       max|z| {observed:.1f}; share of 500 random shuffles at least as extreme: "
          f"{sum(s >= observed for s in shuffles) / len(shuffles):.2f} (near 0 would suggest manual entry)")

    print("\n== 8. What the review flag does, and what sets it (C1, R5, V3) ==")
    print("Cost and time, flagged vs not, holding complexity fixed:")
    for level in ("Simple", "Moderate", "Complex"):
        cells = []
        for flag in ("No", "Yes"):
            group = [r for r in rows if r["complexity"] == level and r["flagged_for_human_review"] == flag]
            cost = sum(float(r["cost_per_claim_usd"]) for r in group) / len(group)
            cycle = sum(float(r["total_cycle_time_hours"]) for r in group) / len(group)
            cells.append(f"{flag}: ${cost:.0f}, {cycle:.1f}h (n={len(group)})")
        print(f"  {level:<9} " + " | ".join(cells))

    def flag_rate(label, key):
        groups = {}
        for r in rows:
            groups.setdefault(key(r), []).append(yes(r, "flagged_for_human_review"))
        print(f"  flag rate by {label}: " + ", ".join(
            f"{k} {pct(sum(v), len(v)):.0f}%" for k, v in sorted(groups.items())))

    flag_rate("complexity", lambda r: r["complexity"])
    flag_rate("amount", lambda r: "a<=5K" if amount(r) <= 5_000 else "b<=10K" if amount(r) <= THRESHOLD
              else "c<=25K" if amount(r) <= 25_000 else "d>25K")
    flag_rate("2021 score", lambda r: f"{int(r['automation_eligibility_score']) // 20 * 20:02d}")
    flag_rate("channel", lambda r: r["intake_channel"])

    print("Scenario: the flag is a second-opinion request, and complex claims go to seniors first")
    complex_share = sum(r["complexity"] == "Complex" for r in rows)
    non_complex_flags = [r for r in rows if r["complexity"] != "Complex" and yes(r, "flagged_for_human_review")]
    cal_nc = [r for r in cal if r["complexity"] != "Complex" and yes(r, "flagged_for_human_review")]
    needed_nc = sum(yes(r, "review_actually_needed") for r in cal_nc) / len(cal_nc)
    print(f"  Non-complex claims flagged: {pct(len(non_complex_flags), n):.1f}% of all claims; "
          f"calibration says {100 * needed_nc:.0f}% of those were needed (n={len(cal_nc)})")
    print(f"  If only needed non-complex flags remain and complex claims need none: "
          f"{pct(len(non_complex_flags), n) * needed_nc:.1f}% flag rate")
    annual = 400_000
    print(f"  Complex share {pct(complex_share, n):.1f}% of {annual:,} claims/yr = "
          f"{annual * complex_share / n:,.0f} complex claims/yr for 16 seniors and leads "
          f"= {annual * complex_share / n / 16 / 250:.0f} per senior per working day")

    print("\n== 9. Review floor under the rule as stated in the clarification call ==")
    print("Stated rule: requires_human_by_regulation = claim over $10K in one of the listed states.")

    def stated(r):
        return r["state"] in inferred and amount(r) > THRESHOLD

    by_rule = sum(stated(r) for r in rows)
    disagree = [r for r in rows if yes(r, "requires_human_by_regulation") != stated(r)]
    print(f"Floor under the stated rule: {by_rule}/{n} = {pct(by_rule, n):.1f}% "
          f"(as labeled in the extract: {pct(reg, n):.1f}%)")
    print(f"Claims where the label disagrees with the rule: {len(disagree)}, "
          f"all outside the threshold states: {all(r['state'] not in inferred for r in disagree)}")
    print(f"Rule-regulated but not flagged for review: "
          f"{sum(stated(r) and not yes(r, 'flagged_for_human_review') for r in rows)}")
    any_review = sum(stated(r) or yes(r, "flagged_for_human_review") for r in rows)
    print(f"Claims reaching a human today (rule-regulated OR flagged): {pct(any_review, n):.1f}%")
    perfect = sum(yes(r, "review_actually_needed") or stated(r) for r in cal)
    print(f"Perfect flag under the rule (needed OR rule-regulated), calibration: "
          f"{perfect}/{m} = {pct(perfect, m):.1f}% (±{ci95(perfect, m):.1f})")
    free = [r for r in cal if not stated(r)]
    print(f"Second opinions actually needed on claims the rule doesn't cover: "
          f"{share(free, 'review_actually_needed')}")
    discretionary = sum(yes(r, "flagged_for_human_review") and not stated(r) for r in rows)
    print(f"Discretionary flags today (flagged, not rule-regulated): {pct(discretionary, n):.1f}%; "
          f"room left under a 20% total: {20 - pct(by_rule, n):.1f} pts")


if __name__ == "__main__":
    main()
