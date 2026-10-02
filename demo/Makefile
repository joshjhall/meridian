BACKEND := backend
TAILWIND := cd $(BACKEND) && TAILWINDCSS_VERSION=v4.3.1 uv run tailwindcss -i styles/app.css -o static/app.css

.PHONY: dev test data css install

install:
	cd $(BACKEND) && uv sync

# Tailwind utilities for the templates (standalone binary via pytailwindcss; no Node).
css: install
	$(TAILWIND) --minify

# API and pages on http://localhost:8000, rebuilding CSS as templates change. Ctrl-C stops both.
dev: css
	trap 'kill 0' INT TERM EXIT; \
	  ($(TAILWIND) --watch=always) & \
	  (cd $(BACKEND) && uv run uvicorn app:app --reload --port 8000) & \
	  wait

test:
	cd $(BACKEND) && uv run pytest -q

# Regenerate the six claim fixtures and the roster.
data:
	cd $(BACKEND) && uv run python ../data/build_claims.py && uv run python ../data/gen_roster.py
