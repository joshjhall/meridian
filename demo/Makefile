BACKEND := backend

.PHONY: dev test data install

install:
	cd $(BACKEND) && uv sync

# API and pages on http://localhost:8000
dev: install
	cd $(BACKEND) && uv run uvicorn app:app --reload --port 8000

test:
	cd $(BACKEND) && uv run pytest -q

# Regenerate the six claim fixtures and the roster.
data:
	cd $(BACKEND) && uv run python ../data/build_claims.py && uv run python ../data/gen_roster.py
