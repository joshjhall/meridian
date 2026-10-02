BACKEND := backend
WEB := web

.PHONY: dev backend web test data install

install:
	cd $(BACKEND) && uv sync
	cd $(WEB) && pnpm install

# Backend on :8000, web on :5173 (proxies /api). Ctrl-C stops both.
dev: install
	trap 'kill 0' INT TERM EXIT; \
	  (cd $(BACKEND) && uv run uvicorn app:app --reload --port 8000) & \
	  (cd $(WEB) && pnpm dev) & \
	  wait

backend:
	cd $(BACKEND) && uv run uvicorn app:app --reload --port 8000

web:
	cd $(WEB) && pnpm dev

test:
	cd $(BACKEND) && uv run pytest -q
	cd $(WEB) && pnpm typecheck

# Regenerate the six claim fixtures and the roster.
data:
	cd $(BACKEND) && uv run python ../data/build_claims.py && uv run python ../data/gen_roster.py
