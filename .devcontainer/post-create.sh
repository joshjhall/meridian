#!/usr/bin/env bash
# post-create.sh — Runs once when the devcontainer is first created.
# Nothing to build yet; verify the tooling the containers submodule provides.

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
require node node
require npm node
require op op
require docker docker
require lefthook dev-tools

echo "    node $(node --version)"

if docker info >/dev/null 2>&1; then
    echo "    docker daemon reachable"
else
    echo "WARN: docker CLI present but the host daemon is not reachable via /var/run/docker.sock"
fi

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
