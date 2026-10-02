#!/usr/bin/env bash
# post-create.sh — Runs once when the devcontainer is first created.
# Verifies the tooling the containers submodule provides, then installs the
# demo's Python environment (runtime + dev/lint tools) from uv.lock.

set -euo pipefail

# Editors differ on the cwd they run lifecycle hooks from; anchor to the repo root.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

require() {
    command -v "$1" >/dev/null || {
        echo "ERROR: $1 not on PATH (expected from the containers $2 feature)"
        exit 1
    }
}

echo "==> Verifying tooling..."
require python3 python
require uv python-dev
require op op
require docker docker
require lefthook dev-tools
require just dev-tools
# Linters the lefthook hooks and `just lint` call directly.
for tool in biome dprint rumdl taplo typos shellcheck shfmt gitleaks; do
    require "$tool" dev-tools
done

echo "    $(python3 --version)"

if docker info >/dev/null 2>&1; then
    echo "    docker daemon reachable"
else
    echo "WARN: docker CLI present but the host daemon is not reachable via /var/run/docker.sock"
fi

# uv.lock pins every Python dependency, including the dev group's linters
# (ruff, djlint, pyright) and pytest. Add new Python tools there with
# `uv add --dev <pkg>` rather than pip/pipx so they land here automatically.
echo "==> Installing demo Python environment..."
just install
echo "    $(cd demo/backend && uv run python --version) venv at demo/backend/.venv"

# Build the codegraph index for the codegraph MCP server. It lives on a named
# volume that survives rebuilds, so only initialize when missing.
echo "==> Ensuring codegraph index..."
if command -v codegraph >/dev/null; then
    if codegraph status 2>&1 | grep -q "Not initialized"; then
        echo "    No index found — running codegraph init..."
        codegraph init
    else
        echo "    Index already present — skipping."
    fi
else
    echo "    codegraph not on PATH — skipping (MCP server unavailable)."
fi

echo "==> Post-create setup complete."
