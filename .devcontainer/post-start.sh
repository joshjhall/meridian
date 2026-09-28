#!/usr/bin/env bash
# post-start.sh — Runs every time the devcontainer starts.
# Configures git identity, CLI auth, and installs git hooks.

set -euo pipefail

# Editors differ on the cwd they run lifecycle hooks from; anchor to the repo root.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# --- Git & CLI setup (from the containers submodule's runtime) ---
echo "==> Configuring git..."
setup-git

echo "==> Configuring gh..."
setup-gh

# --- Git hooks via lefthook (only once the repo has a lefthook.yml) ---
if [ -f lefthook.yml ] && command -v lefthook >/dev/null 2>&1; then
    echo "==> Installing lefthook hooks..."
    # lefthook refuses to install when core.hooksPath is set.
    git config --unset-all core.hooksPath 2>/dev/null || true
    lefthook install
fi

echo "==> Post-start setup complete."
