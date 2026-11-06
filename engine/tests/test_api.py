"""API tests: happy path and the three cheat routes, all on the fake chain."""

import time

import pytest
from fastapi.testclient import TestClient

from parable import api
from parable.fake_chain import FakeRunner, fake_backends
from parable.launcher import Launcher
from tests.test_launcher import FakeWorld


@pytest.fixture
def client():
    world = FakeWorld()
    backends = fake_backends(world)
    backends.runner = FakeRunner(backends.vault, step_s=0.05)
    lau = Launcher(backends, secret="test-secret-1234567")
    api.set_launcher(lau)
    yield TestClient(api.app), world, lau
    for bot in lau.live.values():
        bot.stop.set()
    api.set_launcher(None)


def launch(c, world):
    body = c.post("/api/launch", json={"strategy": "momentum"}).json()
    pid, claim = body["pending_id"], body["claim"]
    assert c.post(f"/api/launch/{pid}/confirm", headers={"x-claim": "wrong"}).status_code == 404  # not the requester
    assert c.post(f"/api/launch/{pid}/confirm", headers={"x-claim": claim}).status_code == 409  # not approved yet
    world.decide(pid, True)
    out = c.post(f"/api/launch/{pid}/confirm", headers={"x-claim": claim}).json()
    return {**out["bot"], "owner_token": out["owner_token"]}


def test_happy_path(client):
    c, world, _ = client
    bot = launch(c, world)
    assert c.get("/api/bots", params={"creator": bot["creator_id"]}).json()[0]["bot_id"] == bot["bot_id"]
    assert c.post(f"/api/bots/{bot['bot_id']}/check").status_code == 409  # not over its limit
    assert c.post(f"/api/bots/{bot['bot_id']}/kill", headers={"x-owner-token": "stranger"}).status_code == 404  # not the creator
    assert c.post(f"/api/bots/{bot['bot_id']}/kill", headers={"x-owner-token": bot["owner_token"]}).json()["ok"]
    grave = c.get(f"/api/graveyard/{bot['creator_id']}").json()
    assert grave[0]["cause"] == "killed" and grave[0]["ens_name"] == bot["ens_name"]
    report = c.get("/api/report", params={"creator": bot["creator_id"]}).json()
    assert report["launched"] == 1 and report["dead"] == 1 and report["vault_count_matches"]


def test_denied_launch(client):
    c, world, _ = client
    body = c.post("/api/launch", json={}).json()
    pid, claim = body["pending_id"], body["claim"]
    world.decide(pid, False)
    assert c.post(f"/api/launch/{pid}/confirm", headers={"x-claim": claim}).status_code == 403
    assert c.get("/api/bots").json() == []


def test_cheat_routes_are_blocked(client):
    c, world, _ = client
    bot = launch(c, world)
    time.sleep(0.1)
    r = c.post("/api/cheat/unregistered-trade").json()
    assert r["blocked"] and r["reason"] == "NotBot"
    r = c.post(f"/api/cheat/over-limit/{bot['bot_id']}").json()
    assert r["blocked"] and r["reason"] == "OverTradeLimit"
    r = c.post("/api/cheat/second-identity").json()
    assert r["blocked"] and r["reason"] == "CreatorIdentityMismatch"


def test_info_reports_offline_flag(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setenv("PARABLE_OFFLINE", "1")
    assert c.get("/api/info").json()["offline"] is True


# ---------------------------------------------------------------- brains

def test_brains_lists_each_brain_without_any_key(client, monkeypatch):
    s = api.get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "SECRET-GOOGLE-KEY")
    monkeypatch.setattr(s, "anthropic_api_key", "SECRET-CLAUDE-KEY")
    monkeypatch.setattr(s, "gemini_models", "gem-model,gem-two")
    monkeypatch.setattr(s, "gemma_models", "")
    monkeypatch.setattr(s, "local_llm_model", "")
    c, _, _ = client
    r = c.get("/api/brains")
    assert "SECRET" not in r.text
    found = {b["brain"]: b["available"] for b in r.json()}
    assert found == {"rule": True, "claude": True, "local": False, "gemini:gem-model": True, "gemini:gem-two": True}


def test_launch_with_unconfigured_brain_is_rejected(client, monkeypatch):
    monkeypatch.setattr(api.get_settings(), "gemini_api_key", "")
    monkeypatch.setattr(api.get_settings(), "gemini_models", "m")
    c, _, lau = client
    assert c.post("/api/launch", json={"brain": "gemini:m"}).status_code == 400
    assert lau.pending == {}  # nothing was started


def test_launch_with_unknown_brain_is_rejected(client):
    c, _, _ = client
    assert c.post("/api/launch", json={"brain": "gpt-9000"}).status_code == 422


def test_brain_travels_to_bot_graveyard_and_report(client, monkeypatch):
    s = api.get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "k")
    monkeypatch.setattr(s, "gemini_models", "m")
    c, world, _ = client
    body = c.post("/api/launch", json={"brain": "gemini:m"}).json()
    world.decide(body["pending_id"], True)
    out = c.post(f"/api/launch/{body['pending_id']}/confirm", headers={"x-claim": body["claim"]}).json()
    bot = out["bot"]
    assert bot["rules"]["brain"] == "gemini:m"
    c.post(f"/api/bots/{bot['bot_id']}/kill", headers={"x-owner-token": out["owner_token"]})
    assert c.get(f"/api/graveyard/{bot['creator_id']}").json()[0]["brain"] == "gemini:m"
    assert c.get("/api/report", params={"brain": "gemini:m"}).json()["dead"] == 1
    assert c.get("/api/report", params={"brain": "rule"}).json()["launched"] == 0


def test_brain_table_events_and_info_in_one_go(client):
    c, world, _ = client
    bot = launch(c, world)
    rows = c.get("/api/report/brains").json()
    rule = next(r for r in rows if r["brain"] == "rule")
    assert rule["available"] and rule["launched"] == 1
    events = c.get(f"/api/bots/{bot['bot_id']}/events").json()
    assert events[-1]["kind"] == "birth"  # newest first, so birth is last
    info = c.get("/api/info").json()
    assert set(info["strategies"]) >= {"momentum", "dip_buyer", "yolo"}
    assert not any("key" in k or "secret" in k for k in info)  # public facts only


def test_launch_survives_an_arkiv_outage(client):
    c, world, lau = client
    real_put = lau.b.arkiv.put_bot

    def down(*a, **k):
        raise RuntimeError("arkiv down")

    lau.b.arkiv.put_bot = down
    bot = launch(c, world)  # the vault registered the bot, so the launch must still succeed
    assert bot["bot_id"] == 1 and len(lau.outbox.items) == 1
    lau.b.arkiv.put_bot = real_put
    assert lau.outbox.flush() == 0
    assert [r.bot_id for r in lau.b.arkiv.records] == [1]
