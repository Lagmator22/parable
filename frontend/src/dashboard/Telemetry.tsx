// The telemetry panel: slides down from the top bar (like a phone's control centre) and shows every live
// number in one place: headline counts, three live charts, each agent's numbers, a feed of every event,
// and links plus copy-paste commands so anyone can check each number themselves.
import { useEffect, useState } from 'react';
import { Chart, PALETTE } from '../components/ui/Chart';
import { OutLink } from '../components/ui/Button';
import { describe } from './Live';
import { brainName, pct, trend, usd, type Bot, type Event, type Info, type Report, type Series, type Swarm } from './api';

type Props = { open: boolean; onClose: () => void; info: Info | null; bots: Bot[]; botEvents: Record<number, Event[]>;
  series: Series | null; swarm: Swarm | null; report: Report | null };
const clock = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const money = (v: number | null | undefined) => v == null ? '—' : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return <button type="button" className="btn btn-quiet" style={{ height: 32, padding: '0 10px', fontSize: 12 }}
    onClick={() => { void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1500); }); }}>{done ? 'copied' : 'copy'}</button>;
}

/** Average return of every agent at each sample time: one line for "the whole fleet". */
function fleetLine(series: Series | null, pick: 1 | 2): [number, number][] {
  const byTime = new Map<number, number[]>();
  (series?.bots || []).forEach(b => b.points.forEach(p => byTime.set(p[0], [...(byTime.get(p[0]) || []), p[pick]])));
  return [...byTime.entries()].sort((a, b) => a[0] - b[0]).map(([t, v]) => [t, v.reduce((s, x) => s + x, 0) / v.length]);
}

export function Telemetry({ open, onClose, info, bots, botEvents, series, swarm, report }: Props) {
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', esc);
    return () => document.removeEventListener('keydown', esc);
  }, [open, onClose]);

  const swarmIds = new Set(swarm?.bots.map(b => b.bot_id) || []);
  const seriesById = new Map((series?.bots || []).map(b => [b.bot_id, b]));
  const all = bots.map(b => {
    const ev = botEvents[b.bot_id] || [];
    const last = seriesById.get(b.bot_id)?.points.at(-1);
    return { b, trades: ev.filter(e => e.kind === 'trade').length, refused: ev.filter(e => e.kind === 'rejected').length,
      marketBps: last ? last[2] : null, lastEvent: ev[0] };
  });
  const trades = all.reduce((s, a) => s + a.trades, 0);
  const refused = all.reduce((s, a) => s + a.refused, 0);
  const totalValue = bots.reduce((s, b) => s + (b.equity_usd ?? 0), 0);
  const ranked = [...all].filter(a => a.marketBps != null).sort((x, y) => (y.marketBps ?? 0) - (x.marketBps ?? 0));
  const price = series?.prices.at(-1);
  const feed = Object.values(botEvents).flat().sort((a, b) => b.at - a.at).slice(0, 14);
  const address = info?.explorer?.replace('/tx/', '/address/') || '';
  const lines = (series?.bots || []).filter(b => b.points.length > 1).slice(-6).map((b, i) => ({
    name: b.ens_name.split('.')[0], color: PALETTE[i % PALETTE.length], dashed: b.swarm, points: b.points.map(p => [p[0], p[2]] as [number, number]) }));
  const priceRows = series?.prices || [];
  // Shell-safe: double quotes outside, single quotes inside for Arkiv's str('…') (it does not decode \u0027).
  const arkivQuery = `curl -s https://rpc.rabdi.db-chain.testnet.arkiv.network -H "content-type: application/json" -d "{\\"jsonrpc\\":\\"2.0\\",\\"id\\":1,\\"method\\":\\"arkiv_query\\",\\"params\\":[\\"arkiv.schema = str('parable.death') AND \\$owner = addr(${info?.arkiv_writer || '0x…'})\\",{\\"select\\":{\\"key\\":true,\\"attributes\\":true}}]}"`;
  const castCall = `cast call ${info?.vault_address || '0x…'} "equityUsd(uint256)(uint256)" ${bots[0]?.bot_id ?? 1} --rpc-url https://ethereum-sepolia-rpc.publicnode.com`;

  return <>
    <div className={`tele-scrim ${open ? 'open' : ''}`} onClick={onClose} aria-hidden="true"/>
    <aside className={`tele ${open ? 'open' : ''}`} aria-label="Telemetry" aria-hidden={!open} inert={!open}>
      <div className="wrap tele-inner">
        <div className="actions" style={{ justifyContent: 'space-between' }}>
          <h2 className="tele-title">{bots.length > 0 && <span className="live"/>} Telemetry</h2>
          <span className="mono muted" style={{ fontSize: 13 }}>updates every {series?.every_s ?? 10}s · Esc closes</span>
          <button type="button" className="square-btn" aria-label="Close telemetry" onClick={onClose}>×</button>
        </div>

        <dl className="kpis">
          <div><dt>Running</dt><dd>{bots.length}</dd></div>
          <div><dt>Swarm workers</dt><dd>{swarmIds.size}</dd></div>
          <div><dt>Trades</dt><dd>{trades}</dd></div>
          <div><dt>Refused by vault</dt><dd className={refused ? 'refused' : ''}>{refused}</dd></div>
          <div><dt>Dead, all time</dt><dd className="refused">{report?.dead ?? '—'}</dd></div>
          <div><dt>Value in vault</dt><dd>{usd(totalValue)}</dd></div>
          <div><dt>ETH market</dt><dd>{money(price?.[1])}</dd></div>
          <div><dt>ETH vault (Chainlink)</dt><dd>{money(price?.[2])}</dd></div>
          <div><dt>Best agent</dt><dd className={trend(ranked[0]?.marketBps)}>{ranked[0] ? pct(ranked[0].marketBps) : '—'}</dd></div>
          <div><dt>Worst agent</dt><dd className={trend(ranked.at(-1)?.marketBps)}>{ranked.length ? pct(ranked.at(-1)?.marketBps) : '—'}</dd></div>
          <div><dt>Mind</dt><dd style={{ fontSize: 16 }}>{swarm?.plan ? brainName(swarm.plan.mind) : 'none'}</dd></div>
          <div><dt>Next mind check</dt><dd>{swarm?.next_check_in != null ? `${swarm.next_check_in}s` : '—'}</dd></div>
        </dl>

        <div className="tele-charts">
          <div className="box"><div className="box-head"><span>Each agent, return at market price</span></div>
            {lines.length ? <Chart label="Agent returns" zero lines={lines} yFormat={v => pct(v)} xFormat={clock}/> : <div className="empty">No agent running yet.</div>}</div>
          <div className="box"><div className="box-head"><span>All agents, average return</span></div>
            {fleetLine(series, 2).length > 1 ? <Chart label="Average return of all agents" zero yFormat={v => pct(v)} xFormat={clock}
              lines={[{ name: 'at market', color: 'var(--ink)', points: fleetLine(series, 2) }, { name: 'vault value', color: 'var(--orange)', dashed: true, points: fleetLine(series, 1) }]}/>
              : <div className="empty">Waiting for two samples…</div>}</div>
          <div className="box"><div className="box-head"><span>ETH price</span></div>
            {priceRows.length > 1 ? <Chart label="ETH price" yFormat={v => `$${Math.round(v)}`} xFormat={clock} lines={[
              { name: 'market', color: 'var(--ink)', points: priceRows.filter(p => p[1] != null).map(p => [p[0], p[1] as number] as [number, number]) },
              { name: 'Chainlink', color: 'var(--orange)', points: priceRows.filter(p => p[2] != null).map(p => [p[0], p[2] as number] as [number, number]) }]}/>
              : <div className="empty">Collecting prices…</div>}</div>
        </div>

        <div className="tele-split">
          <div className="box rows tele-agents">
            <div className="row head"><span/><span>Agent</span><span>Brain</span><span>Vault value</span><span>At market</span><span>Trades</span><span>Refused</span><span>Check</span></div>
            {all.length === 0 ? <div className="empty">Nothing running. Launch a bot or a swarm.</div> : all.map(({ b, trades: t, refused: r, marketBps }) => <div className="row" key={b.bot_id}>
              <span><span className="live"/></span>
              <span title={b.ens_name}>{b.ens_name.replace('.parable.eth', '')}{swarmIds.has(b.bot_id) && <span className="muted"> · swarm</span>}</span>
              <span>{brainName(b.rules.brain)}</span><span>{usd(b.equity_usd)}</span>
              <span className={trend(marketBps)}>{pct(marketBps)}</span><span>{t}</span><span className={r ? 'refused' : ''}>{r}</span>
              <span className="links" style={{ gap: 10 }}><OutLink href={address ? `${address}${b.bot_address}` : null}>wallet</OutLink><OutLink href={b.tx_url}>birth</OutLink></span>
            </div>)}
          </div>
          <div className="box rows log">
            <div className="row head"><span>Every event, newest first</span></div>
            {feed.length === 0 ? <div className="empty">No events yet.</div> : feed.map(ev => {
              const name = bots.find(b => b.bot_id === ev.bot_id)?.ens_name.split('.')[0] || `bot ${ev.bot_id}`;
              return <div className={`row ${ev.kind === 'rejected' ? 'refused' : ''}`} key={`${ev.bot_id}-${ev.kind}-${ev.at}-${ev.tx_hash || ''}`}>
                <time className="muted">{clock(ev.at)}</time><span>{name}: {describe(ev)}</span>
                <OutLink href={ev.tx_hash && info?.explorer ? `${info.explorer}${ev.tx_hash}` : null}>tx</OutLink></div>;
            })}
          </div>
        </div>

        <div className="box">
          <div className="box-head"><span>Check it yourself</span><span className="muted">nothing here needs our server</span></div>
          <div className="rows verify">
            <div className="row"><span>The vault contract (source published)</span><OutLink href={address && info ? `${address}${info.vault_address}` : null}>Etherscan</OutLink></div>
            <div className="row"><span>Every record our server wrote to Arkiv</span><OutLink href={info ? `${info.arkiv_explorer}/address/${info.arkiv_writer}` : null}>Arkiv explorer</OutLink></div>
            <div className="row"><span>Bot names under {info?.ens_parent || 'parable.eth'}</span><OutLink href={info ? `${info.ens_app}${info.ens_parent}` : null}>ENS</OutLink></div>
            <div className="row"><span>Ask Arkiv for every grave, from your terminal</span><Copy text={arkivQuery}/></div>
            <div className="row"><span>Ask the vault for a bot’s value (needs Foundry’s cast)</span><Copy text={castCall}/></div>
          </div>
        </div>
      </div>
    </aside>
  </>;
}
