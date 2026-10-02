"""Replay endpoints, mounted by app.py: the SSE feed and its speed and pause controls."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from replay.runner import Replay

router = APIRouter(prefix="/api")


def get_replay(request: Request) -> Replay:
    return request.app.state.replay


ReplayDep = Annotated[Replay, Depends(get_replay)]


class Controls(BaseModel):
    speed: float | None = Field(default=None, gt=0, le=48)  # simulated hours per second
    paused: bool | None = None


class Restart(BaseModel):
    seed: int | None = None


@router.get("/events")
async def events(replay: ReplayDep, limit: int | None = Query(None, ge=1)) -> StreamingResponse:
    return StreamingResponse(
        replay.stream(limit=limit),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/replay")
async def status(replay: ReplayDep) -> dict:
    return replay.status()


@router.post("/replay")
async def control(replay: ReplayDep, body: Controls) -> dict:
    replay.set(speed=body.speed, paused=body.paused)
    return replay.status()


@router.post("/replay/restart")
async def restart(replay: ReplayDep, body: Restart | None = None) -> dict:
    replay.restart(body.seed if body else None)
    return replay.status()
