"""Replay endpoints, mounted by app.py: the SSE feed and its speed and pause controls.

The controls are a separate router so app.py can mount them behind the same
admin and CSRF guards as the queues board. The feed can't carry those: an
EventSource sends no custom headers.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from replay import runner
from replay.runner import Replay

router = APIRouter(prefix="/api")
controls = APIRouter(prefix="/api")


def get_replay(request: Request) -> Replay:
    return request.app.state.replay


ReplayDep = Annotated[Replay, Depends(get_replay)]


class Controls(BaseModel):
    speed: float | None = Field(default=None, gt=0, le=48)  # simulated hours per second
    paused: bool | None = None


class Restart(BaseModel):
    seed: int | None = None


@router.get("/events")
async def events(replay: ReplayDep, limit: int | None = Query(None, ge=1)) -> Response:
    # Checked here, not in `stream`: the headers go out before the stream's first read,
    # which is where it subscribes. So the cap is soft: viewers accepted in the same
    # instant can overshoot it until they read. The browser's EventSource retries.
    if replay.viewers >= runner.MAX_VIEWERS:
        return JSONResponse(
            {"detail": "too many viewers"}, status_code=503, headers={"Retry-After": "5"}
        )
    return StreamingResponse(
        replay.stream(limit=limit),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/replay")
async def status(replay: ReplayDep) -> dict:
    return replay.status()


@controls.post("/replay")
async def control(replay: ReplayDep, body: Controls) -> dict:
    replay.set(speed=body.speed, paused=body.paused)
    return replay.status()


@controls.post("/replay/restart")
async def restart(replay: ReplayDep, body: Restart | None = None) -> dict:
    replay.restart(body.seed if body else None)
    return replay.status()
