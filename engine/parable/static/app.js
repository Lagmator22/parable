// Dashboard logic: talks to /api/* and redraws every 3 seconds. Plain JavaScript, no framework.
const $ = (id) => document.getElementById(id);
const usd = (n) => (n == null ? "?" : "$" + (n / 1e6).toFixed(2));
const pct = (bps) => (bps == null ? "?" : (bps / 100).toFixed(1) + "%");
const cls = (bps) => (bps >= 0 ? "good" : "bad");
const link = (url, text) => (url ? `<a href="${url}" target="_blank" rel="noopener">${text}</a>` : "");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function api(path, method = "GET") {
  const res = await fetch(path, { method });
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, body };
}

function creator() {
  try { return $("creator").value.trim() || localStorage.getItem("creator") || ""; } catch { return $("creator").value.trim(); }
}

function liveCard(b) {
  const minsLeft = Math.max(0, Math.round((b.born_at + b.rules.lease_seconds - Date.now() / 1000) / 60));
  return `<div class="card"><b>${esc(b.ens_name)}</b><br>
    <span class="muted">${esc(b.strategy)} · ${minsLeft} min left</span><br>
    Equity ${usd(b.equity_usd)} <span class="${cls(b.pnl_bps)}">${pct(b.pnl_bps)}</span><br>
    ${link(b.tx_url, "birth tx")}<br>
    <button class="small" onclick="act(${b.bot_id},'kill')">Kill</button>
    <button class="small" onclick="act(${b.bot_id},'check')">Check loss limit</button>
    <button class="small" onclick="act(${b.bot_id},'expire')">Expire</button></div>`;
}

function tombstone(d) {
  return `<div class="card tomb">🪦<br><b>${esc(d.ens_name)}</b><br>
    lived ${Math.round(d.lifetime_s / 60)} min<br>
    <span class="${cls(d.pnl_bps)}">PnL ${pct(d.pnl_bps)}</span> (${usd(d.final_equity_usd)})<br>
    cause: ${esc(d.cause)}<br>${link(d.tx_url, "death tx")}</div>`;
}

function reportHtml(r) {
  const match = r.vault_count_matches ? '<span class="good">vault count matches Arkiv ✓</span>' : '<span class="bad">vault count does NOT match Arkiv ✗</span>';
  return `Launched <b>${r.launched}</b> · alive <b>${r.alive}</b> · dead <b>${r.dead}</b> · profitable <b>${r.profitable}</b> ·
    worst loss <b class="bad">${pct(r.worst_pnl_bps)}</b><br>${match}`;
}

async function refresh() {
  const me = creator();
  const q = me ? `?creator=${encodeURIComponent(me)}` : "";
  const live = await api("/api/bots" + q + (q ? "&" : "?") + "status=alive");
  $("live").innerHTML = (live.body.length ? live.body.map(liveCard).join("") : '<span class="muted">No live bots.</span>');
  if (!me) return;
  const grave = await api("/api/graveyard/" + encodeURIComponent(me));
  $("graveyard").innerHTML = grave.body.length ? grave.body.map(tombstone).join("") : '<span class="muted">Empty. No bot has died yet.</span>';
  const rep = await api("/api/report" + q);
  if (rep.ok) $("report").innerHTML = reportHtml(rep.body);
}

async function act(id, action) {
  const r = await api(`/api/bots/${id}/${action}`, "POST");
  alert(r.ok ? `${action} done. tx: ${r.body.tx_hash}` : `Blocked by the vault: ${r.body.detail}`);
  refresh();
}

async function launch() {
  const num = (id) => Number($(id).value);
  const rules = { strategy: $("strategy").value, start_cash_usd: num("cash") * 1e6, max_trade_usd: num("maxtrade") * 1e6,
                  max_loss_bps: num("maxloss") * 100, lease_seconds: num("lease") * 60 };
  const res = await fetch("/api/launch", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(rules) });
  const { pending_id, claim, approve_url } = await res.json();
  window.open(approve_url, "_blank");  // the World ID approval page
  $("launch-msg").textContent = "Waiting for World ID approval in the new tab...";
  const timer = setInterval(async () => {
    const r = await api(`/api/launch/${pending_id}/confirm?claim=${encodeURIComponent(claim)}`, "POST");
    if (r.status === 409) return;  // still waiting
    clearInterval(timer);
    if (r.ok) {
      $("creator").value = r.body.bot.creator_id;
      try { localStorage.setItem("creator", r.body.bot.creator_id); } catch {}
      $("launch-msg").textContent = "Born: " + r.body.bot.ens_name;
    } else {
      $("launch-msg").textContent = "No bot launched: " + r.body.detail;
    }
    refresh();
  }, 2000);
}

async function cheat(url) {
  const r = await api(url, "POST");
  const b = r.body;
  $("cheat-out").innerHTML = r.ok ? `${b.blocked ? "✅ BLOCKED" : "⚠️ NOT BLOCKED"}: ${esc(b.attack)}\nvault says: ${esc(b.reason)}` : esc(b.detail);
}

async function start() {
  const info = (await api("/api/info")).body;
  $("banner").hidden = !info.offline;
  try { $("creator").value = localStorage.getItem("creator") || ""; } catch {}
  $("launch").onclick = launch;
  document.querySelectorAll("button.cheat[data-url]").forEach((b) => (b.onclick = () => cheat(b.dataset.url)));
  $("overlimit").onclick = async () => {
    const live = (await api("/api/bots?status=alive")).body;
    live.length ? cheat(`/api/cheat/over-limit/${live[0].bot_id}`) : ($("cheat-out").textContent = "Launch a bot first.");
  };
  refresh();
  setInterval(refresh, 3000);
}
start();
