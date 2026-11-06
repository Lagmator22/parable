// Section 05, the swarm: pick a "mind" model and the worker bots' brains, approve once with World ID, then
// watch it live: which workers are running, how they're doing, and every keep/stop decision with who made it.
import { useEffect, useRef, useState } from 'react';
import { Section } from '../components/ui/Section';
import { ApiError, brainName, pct, post, saveOwner, trend, type Brain, type Swarm as SwarmState } from './api';

type Props = { brains: Brain[]; swarm: SwarmState | null; onUpdate: (s: SwarmState) => void; onBorn: () => void };
type Pending = { pending_id: string; claim: string; approve_url: string };
const CLAIM_KEY = 'parable.swarm-claim';
const pause = (ms: number) => new Promise<void>(r => window.setTimeout(r, ms));
const readClaim = () => { try { return localStorage.getItem(CLAIM_KEY) || ''; } catch { return ''; } };
const clock = (at: number) => new Date(at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

function Stepper({ value, set, min, max, unit }: { value: number; set: (n: number) => void; min: number; max: number; unit: string }) {
  return <div className="actions"><div className="stepper">
    <button type="button" aria-label={`Fewer ${unit}`} onClick={() => set(Math.max(min, value - (unit === 'minutes' ? 5 : 1)))}>−</button>
    <output>{value}</output>
    <button type="button" aria-label={`More ${unit}`} onClick={() => set(Math.min(max, value + (unit === 'minutes' ? 5 : 1)))}>+</button>
  </div><span className="mono muted" style={{ fontSize: 13 }}>{unit}</span></div>;
}

export function Swarm({ brains, swarm, onUpdate, onBorn }: Props) {
  const ai = brains.filter(b => b.brain !== 'rule');
  const [mind, setMind] = useState('');
  const [workers, setWorkers] = useState<string[]>([]);
  const [count, setCount] = useState(3);
  const [minutes, setMinutes] = useState(15);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const active = useRef(true);
  useEffect(() => () => { active.current = false; }, []);
  useEffect(() => {  // defaults: the strongest available mind, a fast AI worker plus the plain rule to compare against
    const ok = brains.filter(b => b.available).map(b => b.brain);
    if (!mind) setMind(['claude:claude-opus-5-5', 'claude:claude-sonnet-5-5', 'gemini:gemini-3.5-flash-lite', ...ok.filter(b => b !== 'rule')].find(b => ok.includes(b)) || '');
    if (!workers.length) setWorkers(['gemini:gemini-3.5-flash-lite', 'rule'].filter(b => ok.includes(b)));
  }, [brains]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {  // this browser started the swarm, so it may stop its workers too
    const claim = readClaim();
    if (claim && swarm?.bots) swarm.bots.forEach(b => saveOwner(b.bot_id, claim));
  }, [swarm?.bots?.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const running = swarm?.phase === 'launching' || swarm?.phase === 'running';
  const toggleWorker = (b: string) => setWorkers(w => w.includes(b) ? w.filter(x => x !== b) : [...w, b]);

  async function start() {
    setBusy(true); setMsg('A World ID tab is opening. One approval covers the whole swarm.');
    const tab = window.open('', '_blank');
    try {
      const p = await post<Pending>('/api/swarm/start', { mind, workers, bots: count, minutes });
      try { localStorage.setItem(CLAIM_KEY, p.claim); } catch { /* private window */ }
      if (tab) tab.location.href = p.approve_url; else setMsg('Your browser blocked the tab. Allow pop-ups and try again.');
      const deadline = Date.now() + 10 * 60_000;
      while (active.current && Date.now() < deadline) {
        try { onUpdate(await post<SwarmState>(`/api/swarm/${p.pending_id}/confirm`, undefined, { 'x-claim': p.claim })); tab?.close(); setMsg(''); onBorn(); return; }
        catch (err) { if (!(err instanceof ApiError && err.status === 409)) throw err; await pause(2_000); }
      }
      throw new Error('No approval within 10 minutes. Start again.');
    } catch (err) { tab?.close(); if (active.current) setMsg(err instanceof Error ? err.message : 'Could not start the swarm.'); }
    finally { if (active.current) setBusy(false); }
  }

  async function stop() {
    try { onUpdate(await post<SwarmState>('/api/swarm/stop', undefined, { 'x-claim': readClaim() })); }
    catch (err) { setMsg(err instanceof Error ? err.message : 'Could not stop it.'); }
  }

  return <Section id="swarm" label="05 Swarm">
    <h2>One mind, many bots.</h2>
    <p className="lead">A mind model checks every worker each minute and decides who keeps trading. It has no extra powers: the vault still checks every trade, and every bot it stops stays on the register.</p>
    {!running && <div className="box">
      <div className="swarm-form">
        <div><span className="field-label">The mind (decides keep or stop)</span><div className="chips">{ai.map(b =>
          <button type="button" key={b.brain} className="chip" disabled={!b.available} aria-pressed={mind === b.brain} onClick={() => setMind(b.brain)}
            title={b.available ? '' : 'Not set up on this server'}>{brainName(b.brain)}</button>)}</div></div>
        <div><span className="field-label">The workers’ brains (they take turns)</span><div className="chips">{brains.map(b =>
          <button type="button" key={b.brain} className="chip" disabled={!b.available} aria-pressed={workers.includes(b.brain)} onClick={() => toggleWorker(b.brain)}>{brainName(b.brain)}</button>)}</div></div>
        <div><span className="field-label">How many workers</span><Stepper value={count} set={setCount} min={1} max={6} unit="bots"/></div>
        <div><span className="field-label">How long they live</span><Stepper value={minutes} set={setMinutes} min={5} max={120} unit="minutes"/></div>
      </div>
      <div className="box-head" style={{ borderBottom: 0, borderTop: '1px solid var(--ink)' }}>
        <button type="button" className="btn btn-solid" disabled={busy || !mind || workers.length === 0} onClick={() => void start()}>Approve swarm with World ID</button>
        <span className="muted">{msg || `${count} bots × $100 practice money, ~1 minute each to set up on Sepolia`}</span>
      </div>
    </div>}
    {swarm && swarm.phase !== 'idle' && swarm.plan && <div className="box">
      <div className="box-head">
        <span>{running && <span className="live"/>} {swarm.phase === 'launching' ? `Setting up workers: ${swarm.born} of ${swarm.total} born`
          : swarm.phase === 'running' ? `Running · mind: ${brainName(swarm.plan.mind)} · next check in ${swarm.next_check_in ?? '…'}s`
          : swarm.phase === 'waiting' ? 'Waiting for World ID approval' : `Finished · mind: ${brainName(swarm.plan.mind)}`}</span>
        {running && readClaim() && <button type="button" className="btn" onClick={() => void stop()}>Stop the mind</button>}
      </div>
      <div className="rows swarm-table">
        <div className="row head"><span/><span>Worker</span><span>Brain</span><span>Return</span><span>Trades</span><span>Refused</span><span>Left</span></div>
        {swarm.bots.length === 0 ? <div className="empty">No workers yet.</div> : swarm.bots.map(b => <div className="row" key={b.bot_id}>
          <span>{b.status === 'alive' ? <span className="live"/> : '—'}</span><span className={b.status === 'alive' ? '' : 'struck'}>{b.ens_name}</span>
          <span>{brainName(b.brain)}</span><span className={trend(b.pnl_bps)}>{pct(b.pnl_bps)}</span><span>{b.trades}</span>
          <span className={b.refused ? 'refused' : ''}>{b.refused}</span><span>{b.status === 'alive' ? `${Math.floor(b.left_s / 60)}m` : 'stopped'}</span>
        </div>)}
      </div>
      <div className="rows decisions">
        <div className="row head"><span>Time</span><span>Decision</span><span>Why</span><span>Decided by</span></div>
        {swarm.decisions.length === 0 ? <div className="empty">The first check happens a minute after the workers start.</div> : swarm.decisions.slice(0, 12).map((d, i) =>
          <div className="row" key={`${d.at}-${i}`}><time className="muted">{clock(d.at)}</time>
            <span className={d.action === 'stop' || d.action === 'flag' ? 'tag-stop' : 'tag-keep'}>{d.action}</span>
            <span>{d.reason}</span><span className="muted">{d.by === 'safety rule' || d.by === 'swarm' ? d.by : brainName(d.by)}</span></div>)}
      </div>
    </div>}
  </Section>;
}
