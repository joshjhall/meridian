"""FastAPI entry point for the demo: JSON API plus server-rendered pages.

Run: uv run uvicorn app:app --reload --port 8000
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fixtures import load_claim_fixtures, load_roster
from models import Adjuster, Claim, Stage

HERE = Path(__file__).resolve().parent

app = FastAPI(title="Meridian demo")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

# The side panel extension calls the API from its own chrome-extension:// origin.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_claim_or_404(claim_id: str) -> Claim:
    fixture = load_claim_fixtures().get(claim_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    return fixture.claim


# --- JSON API ---


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/claims")
def list_claims() -> list[Claim]:
    return [f.claim for f in load_claim_fixtures().values()]


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: str) -> Claim:
    return get_claim_or_404(claim_id)


@app.get("/api/roster")
def roster() -> list[Adjuster]:
    return load_roster()


# --- Pages ---


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    return templates.TemplateResponse(request, "admin.html", {"stages": list(Stage)})


@app.get("/claimspro/{claim_id}", response_class=HTMLResponse)
def claimspro(request: Request, claim_id: str):
    return templates.TemplateResponse(
        request, "claimspro.html", {"claim": get_claim_or_404(claim_id)}
    )


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, claim: str | None = None):
    return templates.TemplateResponse(request, "panel.html", {"claim_id": claim})
