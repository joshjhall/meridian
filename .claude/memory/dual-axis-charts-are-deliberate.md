---
type: feedback
title: Dual-axis charts are deliberate
description: Demo learning-loop charts use dual y-axes on purpose, overriding the dataviz skill's no-dual-axis rule
---

The operator chose dual y-axes for the issue #8 learning-loop charts (agreement % + avg hours; OCR accuracy + EDI drops), overriding the dataviz skill's "never dual-axis" rule.

**Why:** The issue specifies it. The operator judged the skill's rule wrong for this case: the paired measures belong on one plot with the release flags.

**How to apply:** Don't re-raise the dual-axis question for these charts. Do caption that the scaling between the two axes is arbitrary. Label each axis with its own units and color-match each axis to its series.
