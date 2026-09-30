---
type: project
title: The <20% review-rate target is below the regulatory floor
description: 25.4% of claims need human review by regulation; a perfect flag still sends ~44% to review.
stale_check: "re-run python3 analysis/review_floor.py; figures change only if reference/claims_processing.csv changes"
---

The SOW's review-rate target (45% → <20%, `docs/project/sow.md:18`) is not reachable as written:

- **25.4%** of claims are `requires_human_by_regulation` (extract).
- The $10K human-review rule matches **12 states** in the data: the 8 Michael named plus MA, MD, MI, VA. The other 8 states show ~30% regulated regardless of amount, from a rule nobody has explained.
- In the 500-claim calibration sample, a *perfect* flag (needed OR regulated) still flags **~44%**, against 47.4% today.
- 437 regulation-required claims were **not** flagged. Raise privately with Michael first.

Full argument, caveats, and sources: the top section of `docs/discovery/open_questions.md`. Reproduce with `python3 analysis/review_floor.py`.

**Why:** It reframes the design problem. The number of claims a human touches barely falls, so the value is in making each touch cheaper: a prepared brief plus one-click confirmation (see [working positions](/working-positions-from-discovery-read.md)).

**How to apply:** Don't design toward "fewer humans in the loop." Design the human touch to be fast and well-informed. Quote the script's output rather than restating numbers from memory.
