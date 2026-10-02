"""FastAPI entry point for the demo backend.

Run: uv run uvicorn app:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fixtures import load_claim_fixtures, load_roster
from models import Adjuster, Claim

app = FastAPI(title="Meridian demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/claims")
def list_claims() -> list[Claim]:
    return [f.claim for f in load_claim_fixtures().values()]


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: str) -> Claim:
    fixture = load_claim_fixtures().get(claim_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    return fixture.claim


@app.get("/api/roster")
def roster() -> list[Adjuster]:
    return load_roster()
