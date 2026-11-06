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
    assert c.post(f"/api/launch/{pid}/confirm", params={"claim": "wrong"}).status_code == 404  # not the requester
    assert c.post(f"/api/launch/{pid}/confirm", params={"claim": claim}).status_code == 409  # not approved yet
    world.decide(pid, True)
    return c.post(f"/api/launch/{pid}/confirm", params={"claim": claim}).json()["bot"]


def test_happy_path(client):
    c, world, _ = client
    bot = launch(c, world)
    assert c.get("/api/bots", params={"creator": bot["creator_id"]}).json()[0]["bot_id"] == bot["bot_id"]
    assert c.post(f"/api/bots/{bot['bot_id']}/check").status_code == 409  # not over its limit
    assert c.post(f"/api/bots/{bot['bot_id']}/kill").json()["ok"]
    grave = c.get(f"/api/graveyard/{bot['creator_id']}").json()
    assert grave[0]["cause"] == "killed" and grave[0]["ens_name"] == bot["ens_name"]
    report = c.get("/api/report", params={"creator": bot["creator_id"]}).json()
    assert report["launched"] == 1 and report["dead"] == 1 and report["vault_count_matches"]


def test_denied_launch(client):
    c, world, _ = client
    body = c.post("/api/launch", json={}).json()
    pid, claim = body["pending_id"], body["claim"]
    world.decide(pid, False)
    assert c.post(f"/api/launch/{pid}/confirm", params={"claim": claim}).status_code == 403
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
