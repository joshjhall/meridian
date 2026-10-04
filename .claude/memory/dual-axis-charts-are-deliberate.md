---
type: feedback
title: Learning-loop charts use one y-axis per plot
description: The operator reversed the dual-axis choice for the #8 learning-loop charts; each series gets its own single-axis plot, paired in a box
---

The issue #8 learning-loop charts (routing: agreement % + avg hours; intake: OCR accuracy + EDI drops) first used dual y-axes, at the operator's request. On 2026-10-03 the operator reversed this: they could read the dual axes, but lay people would be confused. Each chart is now a box with two stacked single-axis plots that share the week axis and the release flags.

**Why:** the audience is lay stakeholders, and with two y-axes they have to work out which line belongs to which scale.

**How to apply:** don't bring dual y-axes back for these charts. The dataviz skill's "no dual axis" rule applies here as well. Keep the two measures of one chart in a shared box, on a shared x-axis and release flags.
