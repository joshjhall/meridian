# Common tasks for the Meridian demo. Run `just` to list recipes.
# Python and uv come from the devcontainer; the interpreter is pinned in
# demo/backend/.python-version.

backend := "demo/backend"
tailwind := "TAILWINDCSS_VERSION=v4.3.1 uv run tailwindcss -i styles/app.css -o static/app.css"

[private]
default:
    @just --list

# Create or update the backend venv from uv.lock
[working-directory('demo/backend')]
install:
    uv sync

# API and pages on http://localhost:8000, rebuilding CSS as templates change
[working-directory('demo/backend')]
dev: css
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' INT TERM EXIT
    {{ tailwind }} --watch=always &
    uv run uvicorn app:app --reload --port 8000 &
    wait

# API and pages only, without the Tailwind watcher
[working-directory('demo/backend')]
serve: install
    uv run uvicorn app:app --reload --port 8000

# Run the backend test suite; extra args go to pytest (e.g. `just test -k roster`)
[working-directory('demo/backend')]
test *args: install
    uv run pytest -q {{ args }}

# Build the minified Tailwind utilities (static/app.css is committed)
[working-directory('demo/backend')]
css: install
    {{ tailwind }} --minify

# Regenerate the six claim fixtures and the roster
[working-directory('demo/backend')]
data: install
    uv run python ../data/build_claims.py
    uv run python ../data/gen_roster.py

# --- Linting: `lint` checks everything (CI-safe); `fmt` applies fixes ---
# Python tools are pinned in uv.lock; the rest come from the devcontainer.

# Run every linter and format check without changing files
lint: lint-py lint-types lint-templates lint-web lint-docs lint-config lint-sh lint-spelling

# Apply every auto-fix and formatter
fmt: fmt-py fmt-templates fmt-web fmt-docs fmt-config fmt-sh

# Python: ruff lint + format check (config in demo/ruff.toml)
[working-directory('demo')]
lint-py: install
    uv run --project backend ruff check
    uv run --project backend ruff format --check

# Python: pyright type check
[working-directory('demo/backend')]
lint-types: install
    uv run pyright

# Jinja/HTMX templates: djlint lint + format check
[working-directory('demo/backend')]
lint-templates: install
    uv run djlint templates --lint
    uv run djlint templates --check

# CSS and JS: biome lint + format check
lint-web:
    biome check

# Markdown: rumdl
lint-docs:
    rumdl check .

# YAML/JSON (dprint) and TOML (taplo)
lint-config:
    dprint check
    git ls-files '*.toml' ':!containers' | xargs -r taplo fmt --check

# Shell scripts outside the containers submodule
lint-sh:
    git ls-files '*.sh' ':!containers' | xargs -r shellcheck --severity=warning
    git ls-files '*.sh' ':!containers' | xargs -r shfmt -d -i 4 -ci

# Spelling across the repo
lint-spelling:
    typos

[private]
[working-directory('demo')]
fmt-py: install
    uv run --project backend ruff format
    uv run --project backend ruff check --fix

[private]
[working-directory('demo/backend')]
fmt-templates: install
    -uv run djlint templates --reformat

[private]
fmt-web:
    biome check --write

[private]
fmt-docs:
    rumdl fmt .

[private]
fmt-config:
    dprint fmt
    git ls-files '*.toml' ':!containers' | xargs -r taplo fmt

[private]
fmt-sh:
    git ls-files '*.sh' ':!containers' | xargs -r shfmt -w -i 4 -ci

# Remove the venv and Python caches; `just install` rebuilds
clean:
    rm -rf {{ backend }}/.venv {{ backend }}/.pytest_cache {{ backend }}/.ruff_cache
    find demo -type d -name __pycache__ -prune -exec rm -rf {} +

# Clean, reinstall, and run the tests
reset: clean test
