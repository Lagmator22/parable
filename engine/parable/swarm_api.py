"""Web routes for the swarm (start, approve, watch, stop) and for the live graphs.
The swarm's claim code works like a launch's: only the browser that started it can confirm or stop it.
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from parable.launcher import ApprovalPending, LaunchError
from parable.manager import SwarmManager
from parable.series import Recorder

router = APIRouter()
_manager: SwarmManager | None = None
_recorder: Recorder | None = None


def _launcher():
    from parable.api import get_launcher  # late import: api.py includes this router

    return get_launcher()


def get_manager() -> SwarmManager:
    global _manager
    if _manager is None or _manager.launcher is not _launcher():
        _manager = SwarmManager(_launcher())
    return _manager


def get_recorder() -> Recorder:
    global _recorder
    if _recorder is None or _recorder.launcher is not _launcher():
        _recorder = Recorder(_launcher(), swarm_ids=lambda: get_manager().bot_ids)
    return _recorder


class SwarmRequest(BaseModel):
    mind: str
    workers: list[str] = Field(default_factory=lambda: ["rule"])
    bots: int = 3
    minutes: int = 15
    approval: str = "world"  # or "demo": no World App, every worker marked "demo"


@router.get("/api/swarm")
def swarm_status():
    return get_manager().status()


@router.post("/api/swarm/start")
def swarm_start(req: SwarmRequest):
    from parable import world_pass

    if req.approval == "demo" and not (world_pass.demo_allowed() and world_pass.take_demo_slot()):
        raise HTTPException(429, "demo approval is off or busy right now; approve with World ID")
    try:
        pid, claim = get_manager().start(req.mind, req.workers, req.bots, req.minutes, demo=req.approval == "demo")
    except LaunchError as err:
        raise HTTPException(400, str(err))
    # The same World ID check as launching one bot; the approval covers the whole swarm.
    return {"pending_id": pid, "claim": claim, "approve_url": f"/world/start?purpose=launch_bot&ref={pid}"}


@router.post("/api/swarm/{pending_id}/confirm")
def swarm_confirm(pending_id: str, claim: str = Header("", alias="x-claim")):
    try:
        return get_manager().confirm(pending_id, claim)
    except ApprovalPending as err:
        raise HTTPException(409, str(err))
    except LaunchError as err:
        raise HTTPException(403 if str(err).startswith("not approved") else 404, str(err))


@router.post("/api/swarm/stop")
def swarm_stop(claim: str = Header("", alias="x-claim")):
    try:
        return get_manager().stop(claim)
    except LaunchError as err:
        raise HTTPException(403, str(err))


@router.get("/api/series")
def series():
    """Graph data: market and Chainlink prices, plus each bot's value over time (in basis points)."""
    return get_recorder().to_dict()
