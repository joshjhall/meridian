"""FastAPI entry point for the demo: JSON API plus server-rendered pages.

Run: uv run uvicorn app:app --reload --port 8000
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Literal

import claimspro_page
import monitor
import panel
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import clock
import queues
from claimspro_sim import FaultConfig
from claimspro_sim.api import Sim
from claimspro_sim.api import router as claimspro_router
from fixtures import load_claim_fixtures, load_history, load_roster
from models import (
    EXCEPTION_LABELS,
    TIER_LABELS,
    Adjuster,
    Claim,
    CorrectionLogEntry,
    LearningHistory,
)
from pipeline import PIPELINE_VERSION
from replay import Replay
from replay.api import router as replay_router

HERE = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(format_left=queues.format_left, sentence=queues.sentence)


def render_card(view: monitor.ClaimView) -> str:
    return templates.get_template("admin/_card.html").module.card(view)  # type: ignore[attr-defined]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The replay exists from import, so the trace endpoint and tests can read it;
    # it only plays while the server runs.
    app.state.replay.start()
    yield
    await app.state.replay.stop()


app = FastAPI(title="Meridian demo", lifespan=lifespan)
app.state.replay = Replay(render_card)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.include_router(claimspro_router)
app.include_router(replay_router)

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


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, view: Viewer = "admin"):
    return templates.TemplateResponse(
        request,
        "admin/monitor.html",
        {
            "viewer": view,
            "lanes": monitor.LANES,
            "stories": monitor.STORIES,
            "pipeline_version": PIPELINE_VERSION,
            "events_url": "/api/events",
        },
    )


@app.get("/admin/claims/{claim_id}/trace", response_class=HTMLResponse)
def admin_trace(request: Request, claim_id: str, upto: int | None = Query(None, ge=1)):
    # The card passes how many steps it has seen, so the trace never runs ahead
    # of the board. #9 replaces this with the expanded audit record.
    view = request.app.state.replay.board.claims.get(claim_id)
    if view is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    if upto is not None:
        view = replace(view, trace=view.trace[:upto])  # the live board's card stays whole
    return templates.TemplateResponse(
        request,
        "admin/_trace.html",
        {"view": view, "labels": EXCEPTION_LABELS},
    )


# --- Admin queues (#7) ---


# The board's own script sends this on every POST. A cross-site form can't set a
# custom header, and a cross-site fetch that does fails the CORS preflight (only
# the side panel's extension origin is allowed), so it blocks CSRF on these routes.
BOARD_HEADER = "X-Meridian-Board"


def require_board_request(x_meridian_board: Annotated[str | None, Header()] = None) -> None:
    if x_meridian_board != "1":
        raise HTTPException(status_code=403, detail=f"missing {BOARD_HEADER} header")


def require_admin(view: Viewer | None = None) -> None:
    # A demo gate on the query string, not security: it stops the manager view
    # from flipping faults, and marks where real access control goes. No view
    # means no admin.
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
        },
    )


@app.post(
    "/admin/queues/claims/{claim_id}/transfer",
    response_class=HTMLResponse,
    dependencies=[Depends(require_board_request)],
)
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
def admin_write_status(
    request: Request,
    sim: Sim,
    claim_id: str,
    key: Annotated[str, Query(pattern=r"^[0-9a-f-]{36}$")],  # a uuid4 from start_transfer
    view: Viewer = "admin",
):
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


@app.post(
    "/admin/queues/faults",
    dependencies=[Depends(require_board_request), Depends(require_admin)],
)
def admin_queue_faults(sim: Sim, on: bool) -> dict[str, bool]:
    # Only the transfer op, in one set(): other ops' faults are never touched.
    sim.faults.set({queues.TRANSFER: FaultConfig(failure_rate=1.0 if on else 0.0)})
    return {"on": queues.transfer_fault_on(sim)}


# --- Mock ClaimsPro (#10) ---
# Reads the simulator, not the fixtures, so pipeline writes show in the custom fields.


@app.get("/claimspro")
def claimspro_picker(
    claim: str = Query(pattern=r"^IS-CLM-\d{10}$"),
    panel_mode: Literal["docked"] | None = Query(None, alias="panel"),
) -> RedirectResponse:
    # The claim picker is a plain GET form; redirect so the URL carries the claim ID.
    dock = "?panel=docked" if panel_mode else ""
    return RedirectResponse(f"/claimspro/{claim}{dock}", status_code=303)


@app.get("/claimspro/{claim_id}", response_class=HTMLResponse)
def claimspro(
    request: Request,
    sim: Sim,
    claim_id: str,
    panel_mode: Literal["docked"] | None = Query(None, alias="panel"),
):
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
            "docked": panel_mode == "docked",
        },
    )


# --- Side panel (#11) ---
# Served here and embedded by the MV3 extension (demo/extension/) or, as a demo
# safety net, docked beside the mock ClaimsPro page (?panel=docked).


@app.get("/panel", response_class=HTMLResponse)
def panel_page(request: Request, claim: str | None = Query(None, pattern=r"^IS-CLM-\d{10}$")):
    now = clock.now()
    summary = panel.build_summary(claim, now) if claim else None
    sla_label, sla_used = panel.sla_left(summary, now) if summary else ("", 0.0)
    return templates.TemplateResponse(
        request,
        "panel/page.html",
        {
            "claim_id": claim,
            "summary": summary,
            "sla_label": sla_label,
            "sla_used": sla_used,
            "tier_labels": TIER_LABELS,
            "claim_ids": list(load_claim_fixtures()),
        },
    )


PanelAction = Literal["confirm", "correct", "request", "flag"]


# Same CSRF guard as the queues board: the panel's HTMX requests carry this
# header (hx-headers on the page), which a cross-site form can't send.
PANEL_HEADER = "X-Meridian-Panel"


def require_panel_request(x_meridian_panel: Annotated[str | None, Header()] = None) -> None:
    if x_meridian_panel != "1":
        raise HTTPException(status_code=403, detail=f"missing {PANEL_HEADER} header")


@app.post(
    "/panel/{claim_id}/log",
    response_class=HTMLResponse,
    dependencies=[Depends(require_panel_request)],
)
def panel_log(
    request: Request,
    claim_id: str,
    section: str = Query(min_length=1, max_length=40),
    action: PanelAction = "flag",
    item: str | None = Query(None, max_length=200),
    note: str | None = Query(None, max_length=500),
):
    """One click on a "Needs attention" item (confirm, correct, request), or a "this is wrong" flag.

    Recorded in the correction log for the admin view; nothing is written to ClaimsPro.
    """
    get_claim_or_404(claim_id)
    entry = panel.log_correction(
        CorrectionLogEntry(
            claim_id=claim_id, section=section, action=action, item=item, note=note, at=clock.now()
        )
    )
    return templates.TemplateResponse(request, "panel/_logged.html", {"entry": entry})


@app.get("/api/corrections")
def corrections(claim: str | None = None) -> list[CorrectionLogEntry]:
    return panel.corrections(claim)
