"""FastAPI entry point for the demo: JSON API plus server-rendered pages.

Run: uv run uvicorn app:app --reload --port 8000
"""

from pathlib import Path
from typing import Annotated, Literal

import claimspro_page
import monitor
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import clock
import queues
from claimspro_sim import FaultConfig
from claimspro_sim.api import Sim
from claimspro_sim.api import router as claimspro_router
from fixtures import load_claim_fixtures, load_history, load_roster
from models import EXCEPTION_LABELS, Adjuster, Claim, LearningHistory

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


@app.get("/api/history")
def history() -> LearningHistory:
    return load_history()


# --- Pages ---


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# --- Admin monitor (#6) ---
# Unauthenticated, like the rest of the demo: ?view= only shapes the page. Real
# access control belongs on these routes before they serve live claim data.

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


# --- Admin queues (#7) ---


def require_admin(view: Viewer = "admin") -> None:
    # A demo gate on the query string, not security: it stops the manager view
    # from flipping faults, and marks where real access control goes.
    if view != "admin":
        raise HTTPException(status_code=403, detail="admin only")


def transfer_runner() -> queues.Runner:
    return queues.run_in_thread


@app.get("/admin/queues", response_class=HTMLResponse)
def admin_queues(request: Request, sim: Sim, view: Viewer = "admin"):
    now = clock.now()
    return templates.TemplateResponse(
        request,
        "admin/queues.html",
        {
            "viewer": view,
            "groups": queues.board(sim, now),
            "now": now,
            "fault_on": queues.transfer_fault_on(sim),
            "format_left": queues.format_left,
        },
    )


@app.post("/admin/queues/claims/{claim_id}/transfer", response_class=HTMLResponse)
def admin_transfer(
    request: Request,
    sim: Sim,
    run: Annotated[queues.Runner, Depends(transfer_runner)],
    claim_id: str,
    to: str,
    view: Viewer = "admin",
):
    try:
        key = queues.start_transfer(sim, claim_id, queues.roster_by_id().get(to), run)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}") from None
    except queues.TransferBlocked as blocked:
        return templates.TemplateResponse(
            request, "admin/_transfer_blocked.html", {"reason": blocked.reason}, status_code=409
        )
    return _write_status(request, sim, claim_id, key, view)


@app.get("/admin/queues/claims/{claim_id}/write-status", response_class=HTMLResponse)
def admin_write_status(request: Request, sim: Sim, claim_id: str, key: str, view: Viewer = "admin"):
    return _write_status(request, sim, claim_id, key, view)


def _write_status(request: Request, sim: Sim, claim_id: str, key: str, view: Viewer):
    return templates.TemplateResponse(
        request,
        "admin/_write_status.html",
        {
            "claim_id": claim_id,
            "key": key,
            "viewer": view,
            "progress": queues.write_progress(sim, claim_id, key),
            "max_attempts": queues.MAX_ATTEMPTS,
        },
    )


@app.post("/admin/queues/faults", dependencies=[Depends(require_admin)])
def admin_queue_faults(sim: Sim, on: bool) -> dict[str, bool]:
    # Only the transfer op, in one set(): other ops' faults are never touched.
    sim.faults.set({queues.TRANSFER: FaultConfig(failure_rate=1.0 if on else 0.0)})
    return {"on": queues.transfer_fault_on(sim)}


# --- Mock ClaimsPro (#10) ---
# Reads the simulator, not the fixtures, so pipeline writes show in the custom fields.


@app.get("/claimspro")
def claimspro_picker(claim: str = Query(pattern=r"^IS-CLM-\d{10}$")) -> RedirectResponse:
    # The claim picker is a plain GET form; redirect so the URL carries the claim ID.
    return RedirectResponse(f"/claimspro/{claim}", status_code=303)


@app.get("/claimspro/{claim_id}", response_class=HTMLResponse)
def claimspro(request: Request, sim: Sim, claim_id: str):
    claim = sim.store.get(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    prev_id, next_id = claimspro_page.neighbours(claim_id)
    return templates.TemplateResponse(
        request,
        "claimspro/page.html",
        {
            "claim": claim,
            "claim_ids": list(load_claim_fixtures()),
            "prev_id": prev_id,
            "next_id": next_id,
            "screens": claimspro_page.SCREENS,
            "details": claimspro_page.details_by_screen(claim),
            "documents": claimspro_page.documents(claim),
            "custom_field_rows": claimspro_page.custom_field_rows(claim, clock.now()),
            "notes": sim.store.notes(claim_id),
            "events": sim.events(claim_id),
        },
    )


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, claim: str | None = None):
    return templates.TemplateResponse(request, "panel.html", {"claim_id": claim})
