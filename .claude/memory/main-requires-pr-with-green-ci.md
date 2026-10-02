---
type: project
title: main requires a PR with green CI
description: main is protected by a ruleset; every change lands via PR with test, css, and lint green, never a direct push
---

The "Main protections" ruleset on `main` requires the GitHub Actions checks `test`, `css`, and `lint`. It also blocks force-push and deletion, and has no bypass actors, not even the owner. The checks come from `.github/workflows/ci.yml`.

**Why:** parallel agents work issues on separate branches, so CI is the only shared gate that catches a change breaking the demo's shared models, fixtures, or built CSS.

**How to apply:** never push straight to `main`. In ship-issue, use Branch + PR, not "commit to main + push". Before pushing, run `just css` if templates changed, so the committed `app.css` stays current, and run `just test` and `just lint` locally. Confirm with `git status` that `app.css` actually changed: a first `just css` in a fresh venv can exit 0 after only downloading the Tailwind binary, and that misread let a stale `app.css` fail the `css` check on PR #44. The `conform` commit-msg hook enforces conventional commits with **no scope** (`feat:`, not `feat(demo):`), and rejects a `;` in the description. The session's `GITHUB_TOKEN` cannot edit repo settings or rulesets, so hand those to the owner. See [[devcontainer-fuse-overlay-quirks]] for running `just` locally.
