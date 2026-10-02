"""FastAPI entry point for the demo: JSON API plus server-rendered pages.

Run: uv run uvicorn app:app --reload --port 8000
"""

from pathlib import Path
from typing import Literal

import monitor
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from claimspro_sim.api import router as claimspro_router
from fixtures import load_claim_fixtures, load_roster
from models import EXCEPTION_LABELS, Adjuster, Claim

HERE = Path(__file__).resolve().parent

app = FastAPI(title="Meridian demo")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
app.include_router(claimspro_router)

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


# --- Admin monitor (#6) ---

Viewer = Literal["admin", "manager"]


def render_card(view: monitor.ClaimView) -> str:
    return templates.get_template("admin/_card.html").module.card(view)  # type: ignore[attr-defined]


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, view: Viewer = "admin"):
    return templates.TemplateResponse(
        request,
        "admin/monitor.html",
        {
            "viewer": view,
            "lanes": monitor.LANES,
            "stories": monitor.STORIES,
            "pipeline_version": monitor.PIPELINE_VERSION,
            # The replay runner (#5) will serve /api/events; point this at it then.
            "events_url": "/admin/events",
        },
    )


@app.get("/admin/events")
def admin_events(
    speed: float = Query(1.0, gt=0, le=100), limit: int | None = Query(None, ge=1)
) -> StreamingResponse:
    return StreamingResponse(
        monitor.event_stream(render_card, speed=speed, limit=limit),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/admin/claims/{claim_id}/trace", response_class=HTMLResponse)
def admin_trace(request: Request, claim_id: str, upto: int | None = Query(None, ge=1)):
    # The card passes how many steps it has seen, so the trace never runs ahead
    # of the board. #9 replaces this with the expanded audit record.
    view = monitor.replay().claims.get(claim_id)
    if view is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    if upto is not None:
        view.trace = view.trace[:upto]
    return templates.TemplateResponse(
        request,
        "admin/_trace.html",
        {"view": view, "labels": EXCEPTION_LABELS},
    )


@app.get("/claimspro/{claim_id}", response_class=HTMLResponse)
def claimspro(request: Request, claim_id: str):
    return templates.TemplateResponse(
        request, "claimspro.html", {"claim": get_claim_or_404(claim_id)}
    )


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, claim: str | None = None):
    return templates.TemplateResponse(request, "panel.html", {"claim_id": claim})
