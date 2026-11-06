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


def test_arkiv_outage_gives_short_json_not_a_crash_page(client):
    from parable.arkiv_store import ArkivError

    c, _, lau = client

    def down(*a, **k):
        raise ArkivError("arkiv-bridge not reachable at http://127.0.0.1:8787: timed out")

    lau.b.arkiv.report_by_brain = down
    c2 = TestClient(api.app, raise_server_exceptions=False)
    r = c2.get("/api/report/brains")
    assert r.status_code == 503 and "8787" not in r.text  # no internal addresses leak
    assert r.json()["detail"].startswith("the public record")


def test_slow_arkiv_write_does_not_block_confirm_and_live_bot_is_listed(client):
    c, world, lau = client
    real_put = lau.b.arkiv.put_bot

    def slow_put(rec, lease):
        time.sleep(0.25)
        return real_put(rec, lease)

    lau.b.arkiv.put_bot = slow_put
    t0 = time.monotonic()
    bot = launch(c, world)
    assert time.monotonic() - t0 < 0.2  # confirm returned without waiting for slow_put
    # Even before slow_put finishes on Arkiv, /api/bots lists the live bot from memory.
    assert [b["bot_id"] for b in c.get("/api/bots", params={"status": "alive"}).json()] == [bot["bot_id"]]
    time.sleep(0.3)


def test_report_survives_vault_rpc_disconnect(client):
    c, world, lau = client
    bot = launch(c, world)
    lau.b.vault.counts = lambda _c: (_ for _ in ()).throw(ConnectionResetError("reset"))
    r = c.get("/api/report", params={"creator": bot["creator_id"]})
    assert r.status_code == 200 and r.json()["vault_count_matches"] is False


def test_code_fingerprint_default_creator_and_all_graveyard(client):
    c, world, _ = client
    bot = launch(c, world)
    listed = c.get("/api/bots").json()[0]
    assert listed["code_hash"].startswith("0x") and len(listed["code_hash"]) == 18
    info = c.get("/api/info").json()
    assert info["default_creator"] == bot["creator_id"] and info["eth_price_usd"] == 3000.0
    c.post(f"/api/bots/{bot['bot_id']}/kill", headers={"x-owner-token": bot["owner_token"]})
    all_graves = c.get("/api/graveyard/all").json()
    assert len(all_graves) == 1 and all_graves[0]["code_hash"] == listed["code_hash"]
    # Second identity cheat still works even after all bots are dead in the graveyard!
    assert c.post("/api/cheat/second-identity").json()["reason"] == "CreatorIdentityMismatch"


def test_swarm_manager_and_mcp_tools(client):
    from parable import mcp_server
    from parable.models import BotEvent

    c, world, lau = client
    bot = launch(c, world)
    # Record a rejected trade so the swarm manager flags the bot.
    lau.b.arkiv.put_event(BotEvent(bot_id=bot["bot_id"], kind="rejected", at=int(time.time()),
                                   data={"reason": "OverTradeLimit"}))
    st = c.get("/api/manager").json()
    assert st["enabled"] is True
    ran = c.post("/api/manager/start", json={"bots": 2, "minutes": 10}).json()
    actions = {d["action"] for d in ran["decisions"]}
    assert "flag" in actions and "keep" in actions
    # Verify MCP tools work against the same engine state.
    assert mcp_server.list_bots()[0]["bot_id"] == bot["bot_id"]
    assert mcp_server.report_card(creator_id=bot["creator_id"])["launched"] == 1
    assert mcp_server.bot_events(bot["bot_id"])[0]["kind"] in ("birth", "rejected", "trade")
    assert len(mcp_server.compare_brains()) >= 1
    # Verify ERC-8004 export + TUI scoreboard include living and dead agents.
    from parable.erc8004 import render_tui

    feed = c.get("/api/erc8004").json()
    assert feed["standard"] == "ERC-8004" and feed["totalAgents"] >= 1
    assert "ERC-8004 AGENT & GRAVEYARD REGISTRY" in render_tui(feed)


def test_market_arena_benchmark_crashes_and_rallies(client):
    c, _, _ = client
    crash = c.get("/api/arena").json()
    assert crash["scenario"]["id"] == "flash_crash"
    assert crash["summary"]["killed_by_vault"] >= 1 and crash["summary"]["survived"] >= 1
    assert any(b["blocked"] >= 1 for b in crash["contenders"])
    bull = c.post("/api/arena/run", json={"scenario": "bull_breakout", "live_llm": False}).json()
    assert bull["scenario"]["id"] == "bull_breakout"
    assert bull["summary"]["profitable"] >= 1 and bull["summary"]["best_pnl_bps"] > 0


def test_all_graves_view_lists_every_creator(client):
    c, world, _ = client
    bot = launch(c, world)
    c.post(f"/api/bots/{bot['bot_id']}/kill", headers={"x-owner-token": bot["owner_token"]})
    graves = c.get("/api/graveyard/all")
    assert graves.status_code == 200 and graves.json()[0]["bot_id"] == bot["bot_id"]
