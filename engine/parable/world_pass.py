"""Human approval for every bot launch via World ID (OIDC authorization code + PKCE).

Flow: /world/start creates a single-use state (nonce + PKCE verifier bound to the
pending launch id) and redirects to World. /world/callback redeems the code on the
server, verifies the ID token against World's JWKS and stores an Approval. The
launch endpoint must only proceed when get_approval(pending_id).approved is True.

WORLD_MOCK=1 replaces the World redirect with a local Approve / Deny page that
yields the same Approval objects (for demos without the portal).
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import re
import secrets
import json
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


import jwt
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

try:  # repo-root .env, same convention as the rest of the engine
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass

STATE_TTL_S = 600  # a started attempt must complete within 10 minutes
CLOCK_SKEW_S = 60
PURPOSE = "launch_bot"
_REF_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

router = APIRouter(prefix="/world", tags=["world"])


class Approval(BaseModel):
    pending_id: str
    subject: str  # World pairwise `sub` (mock: a fixed fake id)
    approved: bool
    reason: str
    at: int


@dataclass
class _Attempt:
    state: str
    nonce: str
    verifier: str
    pending_id: str
    created_at: int
    used: bool = False


class ApprovalStore:
    """In-memory, single-process store for attempts and outcomes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: dict[str, _Attempt] = {}
        self._approvals: dict[str, Approval] = {}
        self._pending: set[str] = set()  # launch ids created by Parable's own server
        self._demo: set[str] = set()  # launch ids the person chose to approve WITHOUT World ID (marked "demo")

    def register_pending(self, pending_id: str, demo: bool = False) -> None:
        with self._lock:
            self._pending.add(pending_id)
            if demo:
                self._demo.add(pending_id)

    def is_demo(self, pending_id: str) -> bool:
        with self._lock:
            return pending_id in self._demo

    def is_pending(self, pending_id: str) -> bool:
        with self._lock:
            return pending_id in self._pending

    def new_attempt(self, pending_id: str) -> _Attempt:
        a = _Attempt(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            verifier=secrets.token_urlsafe(64),
            pending_id=pending_id,
            created_at=int(time.time()),
        )
        with self._lock:
            self._attempts[a.state] = a
        return a

    def consume(self, state: str) -> tuple[_Attempt | None, str | None]:
        """Atomically mark a state used. Returns (attempt, problem); problem is
        'unknown' or 'replayed' (attempt then stays untouched) or None."""
        with self._lock:
            a = self._attempts.get(state)
            if a is None:
                return None, "unknown"
            if a.used:
                return a, "replayed"
            a.used = True
            return a, None

    def record(self, approval: Approval) -> Approval:
        """First approval is final; a denial may later be superseded by an approval."""
        with self._lock:
            cur = self._approvals.get(approval.pending_id)
            if cur is not None and cur.approved:
                return cur
            self._approvals[approval.pending_id] = approval
            return approval

    def get(self, pending_id: str) -> Approval | None:
        with self._lock:
            return self._approvals.get(pending_id)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()
            self._approvals.clear()
            self._pending.clear()


store = ApprovalStore()


def get_approval(pending_id: str) -> Approval | None:
    return store.get(pending_id)


def register_pending(pending_id: str, demo: bool = False) -> None:
    """The launcher calls this, so /world/start only works for launches our server created.
    demo=True: the person chose "demo approval" (no World App); the bot is marked "demo" in its record."""
    store.register_pending(pending_id, demo)


def demo_allowed() -> bool:
    """Demo approval lets people try Parable without World App. Set WORLD_ALLOW_DEMO=0 to switch it off."""
    return os.environ.get("WORLD_ALLOW_DEMO", "1") != "0"


# ---------------------------------------------------------------- config

def _mock() -> bool:
    return os.environ.get("WORLD_MOCK", "") == "1"


def _issuer() -> str:
    # sandbox: https://sandbox.auth.world.org
    return os.environ.get("WORLD_ISSUER", "https://auth.world.org").rstrip("/")


def _redirect_uri() -> str:
    return os.environ.get("WORLD_REDIRECT_URI", "http://localhost:8000/world/callback")


def _client() -> tuple[str, str]:
    cid = os.environ.get("WORLD_CLIENT_ID", "")
    secret = os.environ.get("WORLD_CLIENT_SECRET", "")
    if not cid or not secret:
        raise HTTPException(503, "World not configured: set WORLD_CLIENT_ID and WORLD_CLIENT_SECRET (or WORLD_MOCK=1)")
    return cid, secret


# ---------------------------------------------------------------- World HTTP (patched in tests)

def _http_json(url: str, data: dict[str, str] | None = None, basic: tuple[str, str] | None = None) -> dict[str, Any]:
    # stdlib on purpose: the resolved `httpx` here is a 1.0 dev build with a different API
    req = urllib.request.Request(url, data=urlencode(data).encode() if data is not None else None)
    req.add_header("Accept", "application/json")
    if basic:
        # RFC 6749 2.3.1: form-urlencode id and secret before base64
        cred = f"{urlencode({'': basic[0]})[1:]}:{urlencode({'': basic[1]})[1:]}"
        req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    with urllib.request.urlopen(req, timeout=15) as resp:  # raises HTTPError/URLError (OSError)
        return json.loads(resp.read())


_discovery_cache: dict[str, Any] = {}
_jwks_cache: dict[str, Any] = {"keys": None, "at": 0.0}


def _discovery() -> dict[str, Any]:
    iss = _issuer()
    if _discovery_cache.get("issuer_url") != iss:
        doc = _http_json(f"{iss}/.well-known/openid-configuration")
        if doc.get("issuer") != iss:
            raise ValueError("discovery issuer mismatch")
        _discovery_cache.clear()
        _discovery_cache.update(doc, issuer_url=iss)
    return _discovery_cache


def fetch_jwks() -> dict[str, Any]:
    return _http_json(_discovery()["jwks_uri"])


def exchange_code(code: str, verifier: str) -> dict[str, Any]:
    """Redeem the authorization code server-side (client_secret_basic, the portal default)."""
    cid, secret = _client()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _redirect_uri(),
        "code_verifier": verifier,
    }
    if os.environ.get("WORLD_TOKEN_AUTH", "basic") == "post":
        data.update(client_id=cid, client_secret=secret)
        return _http_json(_discovery()["token_endpoint"], data)
    return _http_json(_discovery()["token_endpoint"], data, basic=(cid, secret))


def _signing_key(token: str) -> Any:
    """Pick the JWKS key by kid; refresh the JWKS once if the kid is unknown (key rotation)."""
    kid = jwt.get_unverified_header(token).get("kid")
    for attempt in (0, 1):
        stale = time.time() - _jwks_cache["at"] > 3600
        if _jwks_cache["keys"] is None or stale or attempt == 1:
            _jwks_cache["keys"] = jwt.PyJWKSet.from_dict(fetch_jwks())
            _jwks_cache["at"] = time.time()
        for k in _jwks_cache["keys"].keys:
            if k.key_id == kid:
                return k.key
    raise jwt.InvalidTokenError("no JWKS key matches token kid")


def verify_id_token(id_token: str, attempt: _Attempt) -> dict[str, Any]:
    """Signature (RS256 only), iss, aud, exp, nonce, and auth_time belonging to this attempt."""
    claims = jwt.decode(
        id_token,
        _signing_key(id_token),
        algorithms=["RS256"],
        issuer=_issuer(),
        audience=_client()[0],
        leeway=CLOCK_SKEW_S,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    if not secrets.compare_digest(str(claims.get("nonce", "")), attempt.nonce):
        raise jwt.InvalidTokenError("nonce mismatch")
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, int):
        raise jwt.InvalidTokenError("missing auth_time")
    # max_age=0 was requested: the authentication must have happened after this attempt began
    if auth_time < attempt.created_at - CLOCK_SKEW_S or auth_time > time.time() + CLOCK_SKEW_S:
        raise jwt.InvalidTokenError("auth_time not fresh for this attempt")
    return claims


# ---------------------------------------------------------------- helpers

def _pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _outcome(pending_id: str, subject: str, approved: bool, reason: str):
    """Persist the Approval, then redirect to WORLD_RETURN_URL or show a result page."""
    ap = store.record(Approval(pending_id=pending_id, subject=subject, approved=approved, reason=reason, at=int(time.time())))
    ret = os.environ.get("WORLD_RETURN_URL")
    if ret:
        sep = "&" if "?" in ret else "?"
        return RedirectResponse(f"{ret}{sep}{urlencode({'pending_id': ap.pending_id, 'approved': str(ap.approved).lower()})}", status_code=303)
    title = "Approved" if ap.approved else "Not approved"
    body = (
        f"<h1>{title}</h1><p>{html.escape(ap.reason)}</p>"
        f"<p>Launch <code>{html.escape(ap.pending_id)}</code>: "
        f"{'you can return to Parable.' if ap.approved else 'the bot will not be launched.'}</p>"
    )
    return HTMLResponse(_page(title, body))


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font:16px system-ui;max-width:32rem;margin:3rem auto;padding:0 16px}"
        "button{font:inherit;padding:.6rem 1.2rem;margin-right:.5rem;cursor:pointer}"
        ".mock{background:#fff3cd;border:1px solid #e0b100;padding:.5rem .75rem;border-radius:6px}</style>"
        f"{body}"
    )


def _bad_request(msg: str) -> HTMLResponse:
    return HTMLResponse(_page("Invalid request", f"<h1>Invalid request</h1><p>{html.escape(msg)}</p>"), status_code=400)


# ---------------------------------------------------------------- routes

@router.get("/start")
def start(purpose: str = Query(...), ref: str = Query(...)):
    if purpose != PURPOSE:
        raise HTTPException(400, f"unsupported purpose; expected {PURPOSE}")
    if not _REF_RE.match(ref):
        raise HTTPException(400, "invalid ref")
    if not store.is_pending(ref):
        raise HTTPException(404, "unknown launch id: start the launch from Parable first")
    if _mock() or (store.is_demo(ref) and demo_allowed()):
        attempt = store.new_attempt(ref)
        form = lambda decision, label: (  # noqa: E731
            f"<form method=post action='/world/mock/decision' style='display:inline'>"
            f"<input type=hidden name=state value='{html.escape(attempt.state)}'>"
            f"<input type=hidden name=decision value={decision}><button>{label}</button></form>"
        )
        body = (
            "<p class=mock><b>Demo approval</b>: no World App, no human check. The bot is marked "
            "<b>demo</b> on the public register so it never counts as human-verified.</p>"
            f"<h1>Approve bot launch?</h1><p>Launch <code>{html.escape(ref)}</code> needs a human approval.</p>"
            f"{form('approve', 'Approve')}{form('deny', 'Deny')}"
        )
        return HTMLResponse(_page("Approve launch (mock)", body))
    cid, _ = _client()
    discovery = _discovery()
    attempt = store.new_attempt(ref)
    params = {
        "client_id": cid,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid",
        "state": attempt.state,
        "nonce": attempt.nonce,
        "code_challenge": _pkce_challenge(attempt.verifier),
        "code_challenge_method": "S256",
        "max_age": "0",  # fresh authentication for this launch
    }
    return RedirectResponse(f"{discovery['authorization_endpoint']}?{urlencode(params)}", status_code=302)


@router.post("/mock/decision")
def mock_decision(state: str = Form(...), decision: str = Form(...)):
    attempt, problem = store.consume(state)
    if problem or attempt is None:
        return _bad_request(f"state {problem}")
    if not (_mock() or (store.is_demo(attempt.pending_id) and demo_allowed())):
        raise HTTPException(404)
    if int(time.time()) - attempt.created_at > STATE_TTL_S:
        return _outcome(attempt.pending_id, "", False, "expired: approval took longer than 10 minutes")
    if decision == "approve":
        subject = os.environ.get("WORLD_MOCK_SUBJECT", "mock-human-demo")
        return _outcome(attempt.pending_id, subject, True, "approved (demo approval, no World ID)")
    return _outcome(attempt.pending_id, "", False, "denied by user (mock World ID)")


@router.get("/callback")
def callback(
    state: str = Query(""),
    code: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    iss: str | None = Query(None),
):
    attempt, problem = store.consume(state)
    if problem or attempt is None:
        # Unknown or replayed state: reject without touching any stored Approval.
        return _bad_request(f"state {problem or 'missing'}")
    pid = attempt.pending_id
    if int(time.time()) - attempt.created_at > STATE_TTL_S:
        return _outcome(pid, "", False, "expired: approval took longer than 10 minutes")
    # If World sends `iss` back (RFC 9207), it must be World. If it doesn't send it, the ID token's
    # own issuer is still checked below, so a missing value is fine.
    if iss is not None and iss != _issuer():
        return _outcome(pid, "", False, "rejected: callback issuer mismatch")
    if error:
        why = "denied by user" if error == "access_denied" else f"world error: {error}"
        return _outcome(pid, "", False, why)
    if not code:
        return _outcome(pid, "", False, "rejected: no authorization code")
    try:
        tokens = exchange_code(code, attempt.verifier)
        claims = verify_id_token(tokens["id_token"], attempt)
    except HTTPException:
        raise
    except jwt.InvalidTokenError as e:
        return _outcome(pid, "", False, f"rejected: invalid ID token ({e})")
    except (OSError, KeyError, ValueError) as e:
        return _outcome(pid, "", False, f"rejected: token exchange failed ({type(e).__name__})")
    return _outcome(pid, str(claims["sub"]), True, "approved: World ID verified server-side")
