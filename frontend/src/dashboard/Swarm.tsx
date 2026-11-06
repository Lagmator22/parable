// Section 05, the swarm: pick one "mind" model, then build the team of workers like a cart (a brain and how
// many of it), approve once with World ID, and watch it live: each worker's numbers and every keep/stop
// decision with who made it (the mind, or the safety rule).
import { useEffect, useRef, useState } from 'react';
import { Section } from '../components/ui/Section';
import { ApprovalSwitch } from '../components/ui/ApprovalSwitch';
import { ApiError, brainName, getApprovalMode, pct, post, saveApprovalMode, saveOwner, trend, type ApprovalMode, type Brain, type Swarm as SwarmState } from './api';

type Props = { brains: Brain[]; swarm: SwarmState | null; onUpdate: (s: SwarmState) => void; onBorn: () => void; demoAllowed?: boolean };
type Pending = { pending_id: string; claim: string; approve_url: string };
const CLAIM_KEY = 'parable.swarm-claim';
const MAX_WORKERS = 6;
const pause = (ms: number) => new Promise<void>(r => window.setTimeout(r, ms));
const readClaim = () => { try { return localStorage.getItem(CLAIM_KEY) || ''; } catch { return ''; } };
const clock = (at: number) => new Date(at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

function Stepper({ value, set, min, max, step = 1, label }: { value: number; set: (n: number) => void; min: number; max: number; step?: number; label: string }) {
  return <div className="stepper">
    <button type="button" aria-label={`Less ${label}`} disabled={value <= min} onClick={() => set(Math.max(min, value - step))}>−</button>
    <output aria-label={label}>{value}</output>
    <button type="button" aria-label={`More ${label}`} disabled={value >= max} onClick={() => set(Math.min(max, value + step))}>+</button>
  </div>;
}

export function Swarm({ brains, swarm, onUpdate, onBorn, demoAllowed }: Props) {
  const [approval, setApproval] = useState<ApprovalMode>(getApprovalMode);
  const ready = brains.filter(b => b.available);
  const [mind, setMind] = useState('');
  const [team, setTeam] = useState<Record<string, number>>({});
  const [minutes, setMinutes] = useState(15);
  const [msg, setMsg] = useState('');
  const [waiting, setWaiting] = useState<{ url: string } | null>(null);
  const cancelled = useRef(false);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  useEffect(() => {  // defaults: the strongest available mind; two fast AI workers plus the plain rule to compare against
    const ok = ready.map(b => b.brain);
    if (!mind) setMind(['claude:claude-opus-5-5', 'claude:claude-sonnet-5-5', 'gemini:gemini-3.5-flash-lite', ...ok.filter(b => b !== 'rule')].find(b => ok.includes(b)) || '');
    if (!Object.keys(team).length && ok.includes('gemini:gemini-3.5-flash-lite')) setTeam({ 'gemini:gemini-3.5-flash-lite': 2, ...(ok.includes('rule') ? { rule: 1 } : {}) });
  }, [brains]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {  // this browser started the swarm, so it may stop its workers too
    const claim = readClaim();
    if (claim && swarm?.bots) swarm.bots.forEach(b => saveOwner(b.bot_id, claim));
  }, [swarm?.bots?.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = Object.values(team).reduce((s, n) => s + n, 0);
  const setCount = (brain: string, n: number) => setTeam(t => { const next = { ...t, [brain]: n }; if (n <= 0) delete next[brain]; return next; });
  const running = swarm?.phase === 'launching' || swarm?.phase === 'running';

  async function start() {
    cancelled.current = false;
    setMsg('A World ID tab is opening. One approval covers the whole swarm.');
    const tab = window.open('', '_blank');
    try {
      // The server takes the workers as a list and hands them out in order: ["gemini", "gemini", "rule"].
      const workers = Object.entries(team).flatMap(([b, n]) => Array(n).fill(b));
      const p = await post<Pending>('/api/swarm/start', { mind, workers, bots: workers.length, minutes, approval: demoAllowed ? approval : 'world' });
      try { localStorage.setItem(CLAIM_KEY, p.claim); } catch { /* private window */ }
      if (tab) tab.location.href = p.approve_url;
      setWaiting({ url: p.approve_url });
      const deadline = Date.now() + 10 * 60_000;
      while (alive.current && !cancelled.current && Date.now() < deadline) {
        try { onUpdate(await post<SwarmState>(`/api/swarm/${p.pending_id}/confirm`, undefined, { 'x-claim': p.claim })); tab?.close(); setMsg(''); onBorn(); return; }
        catch (err) { if (!(err instanceof ApiError && err.status === 409)) throw err; await pause(2_000); }
      }
      if (cancelled.current) { setMsg('Cancelled. Nothing was started.'); return; }
      throw new Error('No approval within 10 minutes. Start again.');
    } catch (err) { tab?.close(); if (alive.current) setMsg(err instanceof Error ? err.message : 'Could not start the swarm.'); }
    finally { if (alive.current) setWaiting(null); }
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
        <div><span className="field-label">1 · The mind: which model decides keep or stop</span><div className="chips">{ready.filter(b => b.brain !== 'rule').map(b =>
          <button type="button" key={b.brain} className="chip" disabled={!b.available} aria-pressed={mind === b.brain} onClick={() => setMind(b.brain)}
            title={b.available ? '' : 'Not set up on this server'}>{brainName(b.brain)}</button>)}</div></div>
        <div><span className="field-label">2 · The workers: {total} of {MAX_WORKERS}</span>
          <div className="rows team">{Object.keys(team).length === 0 ? <div className="empty">Add at least one worker below.</div> : Object.entries(team).map(([b, n]) =>
            <div className="row" key={b}><span>{brainName(b)}</span>
              <Stepper value={n} set={x => setCount(b, x)} min={0} max={n + MAX_WORKERS - total} label={`${brainName(b)} workers`}/></div>)}</div>
          <span className="field-label" style={{ marginTop: 14 }}>Add a worker</span>
          <div className="chips">{ready.filter(b => !team[b.brain]).map(b =>
            <button type="button" key={b.brain} className="chip" disabled={total >= MAX_WORKERS} onClick={() => setCount(b.brain, 1)}>+ {brainName(b.brain)}</button>)}</div>
        </div>
        <div><span className="field-label">3 · How long the workers live</span>
          <div className="actions"><Stepper value={minutes} set={setMinutes} min={5} max={120} step={5} label="minutes"/><span className="mono muted" style={{ fontSize: 13 }}>minutes</span></div></div>
        <div><span className="field-label">What happens</span><p className="say">Each worker gets $100 of practice money and takes about a minute to set up on Sepolia. A minute after that, the mind starts checking.</p></div>
      </div>
      <div className="box-head" style={{ borderBottom: 0, borderTop: '1px solid var(--ink)' }}>
        {waiting ? <div className="actions">
          <span><span className="live"/> Waiting for your World ID approval</span>
          <a className="btn btn-quiet" href={waiting.url} target="_blank" rel="noreferrer">Open World ID again</a>
          <button type="button" className="btn" onClick={() => { cancelled.current = true; }}>Cancel</button>
        </div> : <div className="actions">
          {demoAllowed && <ApprovalSwitch mode={approval} onChange={m => { setApproval(m); saveApprovalMode(m); }}/>}
          <button type="button" className="btn btn-solid" disabled={!mind || total === 0} onClick={() => void start()}>
            {approval === 'demo' && demoAllowed ? `Approve swarm of ${total} (demo)` : `Approve swarm of ${total} with World ID`}</button></div>}
        <span className="muted">{msg}</span>
      </div>
    </div>}
    {swarm && swarm.phase !== 'idle' && swarm.plan && <div className="box">
      <div className="box-head">
        <span>{running && <span className="live"/>} {swarm.phase === 'launching' ? `Setting up workers: ${swarm.born} of ${swarm.total} born`
          : swarm.phase === 'running' ? `Running · mind: ${brainName(swarm.plan.mind)} · next check in ${swarm.next_check_in ?? '…'}s`
          : `Last swarm · mind: ${brainName(swarm.plan.mind)}`}</span>
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
