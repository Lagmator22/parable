import base64
import json
import re
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from parable import world_pass as wp

ISS = "https://auth.world.org"
CID = "app_test"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    wp.store.clear()
    wp._jwks_cache.update(keys=None, at=0.0)
    for k in ("WORLD_MOCK", "WORLD_RETURN_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("WORLD_CLIENT_ID", CID)
    monkeypatch.setenv("WORLD_CLIENT_SECRET", "worldidp_client_secret_test")
    monkeypatch.setenv("WORLD_ISSUER", ISS)
    monkeypatch.setattr(wp, "_discovery", lambda: {
        "authorization_endpoint": f"{ISS}/api/v1/authorize",
        "token_endpoint": f"{ISS}/api/v1/token",
        "jwks_uri": f"{ISS}/.well-known/jwks.json",
    })


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(wp.router)
    return TestClient(app, follow_redirects=False)


# ---- local IdP: RSA key + JWKS

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(kid="k1"):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_key.public_key()))
    return {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}


def _id_token(nonce, **over):
    now = int(time.time())
    claims = {"iss": ISS, "aud": CID, "sub": "pairwise-sub-1", "iat": now, "exp": now + 300,
              "auth_time": now, "nonce": nonce, "acr": "https://world.org/oidc/acr/orb"}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, _key, algorithm="RS256", headers={"kid": "k1"})


def _start_real(client, ref="p1"):
    wp.register_pending(ref)
    r = client.get("/world/start", params={"purpose": "launch_bot", "ref": ref})
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    return r, {k: v[0] for k, v in q.items()}


def _wire(monkeypatch, id_token_for):
    """Patch network: token endpoint returns an ID token built from the attempt's nonce."""
    monkeypatch.setattr(wp, "fetch_jwks", _jwks)

    def fake_exchange(code, verifier):
        assert code == "good-code"
        attempt = next(a for a in wp.store._attempts.values() if a.verifier == verifier)
        return {"id_token": id_token_for(attempt.nonce)}

    monkeypatch.setattr(wp, "exchange_code", fake_exchange)


# ---- real flow

def test_start_builds_pkce_authorize_redirect(client):
    r, q = _start_real(client)
    assert r.headers["location"].startswith(f"{ISS}/api/v1/authorize?")
    assert q["client_id"] == CID and q["response_type"] == "code" and q["scope"] == "openid"
    assert q["code_challenge_method"] == "S256" and q["max_age"] == "0"
    attempt = wp.store._attempts[q["state"]]
    assert attempt.pending_id == "p1" and attempt.nonce == q["nonce"]
    assert q["code_challenge"] == wp._pkce_challenge(attempt.verifier)


def test_start_rejects_bad_input(client):
    assert client.get("/world/start", params={"purpose": "other", "ref": "p1"}).status_code == 400
    assert client.get("/world/start", params={"purpose": "launch_bot", "ref": "a b<"}).status_code == 400


def test_callback_approves_valid_id_token(client, monkeypatch):
    _wire(monkeypatch, _id_token)
    _, q = _start_real(client)
    r = client.get("/world/callback", params={"state": q["state"], "code": "good-code", "iss": ISS})
    assert r.status_code == 200
    ap = wp.get_approval("p1")
    assert ap and ap.approved and ap.subject == "pairwise-sub-1"


def test_callback_access_denied(client):
    _, q = _start_real(client)
    client.get("/world/callback", params={"state": q["state"], "error": "access_denied", "iss": ISS})
    ap = wp.get_approval("p1")
    assert ap and not ap.approved and "denied" in ap.reason


def test_replayed_state_rejected_and_does_not_change_outcome(client, monkeypatch):
    _wire(monkeypatch, _id_token)
    _, q = _start_real(client)
    p = {"state": q["state"], "code": "good-code", "iss": ISS}
    assert client.get("/world/callback", params=p).status_code == 200
    assert client.get("/world/callback", params=p).status_code == 400
    # a replayed denial must not downgrade the approval either
    assert client.get("/world/callback", params={"state": q["state"], "error": "access_denied", "iss": ISS}).status_code == 400
    assert wp.get_approval("p1").approved


def test_unknown_state_rejected(client):
    assert client.get("/world/callback", params={"state": "nope", "code": "x", "iss": ISS}).status_code == 400
    assert wp.get_approval("p1") is None


def test_expired_state_denies(client, monkeypatch):
    _wire(monkeypatch, _id_token)
    _, q = _start_real(client)
    wp.store._attempts[q["state"]].created_at -= wp.STATE_TTL_S + 5
    client.get("/world/callback", params={"state": q["state"], "code": "good-code", "iss": ISS})
    ap = wp.get_approval("p1")
    assert ap and not ap.approved and "expired" in ap.reason


def test_issuer_param_mismatch_denies(client, monkeypatch):
    _wire(monkeypatch, _id_token)
    _, q = _start_real(client)
    client.get("/world/callback", params={"state": q["state"], "code": "good-code", "iss": "https://evil.example"})
    assert not wp.get_approval("p1").approved


@pytest.mark.parametrize("name,build", [
    ("nonce", lambda n: _id_token("other-nonce")),
    ("audience", lambda n: _id_token(n, aud="someone-else")),
    ("issuer", lambda n: _id_token(n, iss="https://evil.example")),
    ("expired", lambda n: _id_token(n, exp=int(time.time()) - 3600)),
    ("auth_time missing", lambda n: _id_token(n, auth_time=None)),
    ("auth_time stale", lambda n: _id_token(n, auth_time=int(time.time()) - 3600)),
])
def test_bad_id_tokens_deny(client, monkeypatch, name, build):
    _wire(monkeypatch, build)
    _, q = _start_real(client)
    client.get("/world/callback", params={"state": q["state"], "code": "good-code", "iss": ISS})
    ap = wp.get_approval("p1")
    assert ap and not ap.approved, name


def test_token_signed_by_unknown_key_denies(client, monkeypatch):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = lambda n: jwt.encode(  # noqa: E731
        {"iss": ISS, "aud": CID, "sub": "x", "iat": int(time.time()), "exp": int(time.time()) + 99,
         "auth_time": int(time.time()), "nonce": n},
        other, algorithm="RS256", headers={"kid": "k1"})
    _wire(monkeypatch, forged)
    _, q = _start_real(client)
    client.get("/world/callback", params={"state": q["state"], "code": "good-code", "iss": ISS})
    assert not wp.get_approval("p1").approved


def test_alg_none_rejected(client, monkeypatch):
    def none_token(n):
        b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
        now = int(time.time())
        return b({"alg": "none", "kid": "k1"}) + "." + b(
            {"iss": ISS, "aud": CID, "sub": "x", "iat": now, "exp": now + 99, "auth_time": now, "nonce": n}) + "."
    _wire(monkeypatch, none_token)
    _, q = _start_real(client)
    client.get("/world/callback", params={"state": q["state"], "code": "good-code", "iss": ISS})
    assert not wp.get_approval("p1").approved


# ---- mock flow

def _mock_state(client, ref="m1"):
    wp.register_pending(ref)
    r = client.get("/world/start", params={"purpose": "launch_bot", "ref": ref})
    assert r.status_code == 200 and "Demo approval" in r.text
    return re.search(r"name=state value='([^']+)'", r.text).group(1)


def test_mock_approve(client, monkeypatch):
    monkeypatch.setenv("WORLD_MOCK", "1")
    s = _mock_state(client)
    assert client.post("/world/mock/decision", data={"state": s, "decision": "approve"}).status_code == 200
    ap = wp.get_approval("m1")
    assert ap and ap.approved and ap.subject == "mock-human-demo"


def test_mock_deny(client, monkeypatch):
    monkeypatch.setenv("WORLD_MOCK", "1")
    s = _mock_state(client)
    client.post("/world/mock/decision", data={"state": s, "decision": "deny"})
    ap = wp.get_approval("m1")
    assert ap and not ap.approved


def test_mock_replay_and_expiry(client, monkeypatch):
    monkeypatch.setenv("WORLD_MOCK", "1")
    s = _mock_state(client)
    client.post("/world/mock/decision", data={"state": s, "decision": "deny"})
    assert client.post("/world/mock/decision", data={"state": s, "decision": "approve"}).status_code == 400
    assert not wp.get_approval("m1").approved
    s2 = _mock_state(client, "m2")
    wp.store._attempts[s2].created_at -= wp.STATE_TTL_S + 5
    client.post("/world/mock/decision", data={"state": s2, "decision": "approve"})
    assert not wp.get_approval("m2").approved


def test_mock_endpoint_refuses_unknown_state_without_flag(client):
    # No mock flag and no demo launch: a made-up state is refused (never approves anything).
    assert client.post("/world/mock/decision", data={"state": "x", "decision": "approve"}).status_code in (400, 404)


def test_demo_approval_works_only_for_launches_marked_demo(client, monkeypatch):
    monkeypatch.delenv("WORLD_MOCK", raising=False)
    wp.register_pending("real-1")
    wp.register_pending("demo-1", demo=True)
    assert "Demo approval" not in client.get("/world/start", params={"purpose": "launch_bot", "ref": "real-1"}, follow_redirects=False).text
    page = client.get("/world/start", params={"purpose": "launch_bot", "ref": "demo-1"})
    assert page.status_code == 200 and "Demo approval" in page.text
    state = page.text.split("name=state value='")[1].split("'")[0]
    client.post("/world/mock/decision", data={"state": state, "decision": "approve"})
    assert wp.get_approval("demo-1").approved and "demo" in wp.get_approval("demo-1").reason
    monkeypatch.setenv("WORLD_ALLOW_DEMO", "0")
    wp.register_pending("demo-2", demo=True)
    assert "Demo approval" not in client.get("/world/start", params={"purpose": "launch_bot", "ref": "demo-2"}, follow_redirects=False).text


def test_retry_after_denial_can_approve_but_approval_is_final(client, monkeypatch):
    monkeypatch.setenv("WORLD_MOCK", "1")
    client.post("/world/mock/decision", data={"state": _mock_state(client), "decision": "deny"})
    client.post("/world/mock/decision", data={"state": _mock_state(client), "decision": "approve"})
    assert wp.get_approval("m1").approved
    client.post("/world/mock/decision", data={"state": _mock_state(client), "decision": "deny"})
    assert wp.get_approval("m1").approved


def test_unconfigured_real_mode_fails_closed(client, monkeypatch):
    monkeypatch.delenv("WORLD_CLIENT_SECRET")
    wp.register_pending("p1")
    assert client.get("/world/start", params={"purpose": "launch_bot", "ref": "p1"}).status_code == 503


def test_unknown_launch_id_is_rejected(client):
    """World approval only works for launch ids that Parable's server created (no hijacking)."""
    assert client.get("/world/start", params={"purpose": "launch_bot", "ref": "never-created"}).status_code == 404
