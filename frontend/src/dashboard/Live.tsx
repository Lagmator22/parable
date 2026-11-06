import { useEffect, useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { explain, getOwner, pct, post, request, usd, type Attack, type Bot, type Event } from './api';

function Timeline({ id }: { id: number }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { request<Event[]>(`/api/bots/${id}/events`).then(setEvents).catch(err => setError(err.message)); }, [id]);
  return <div className="timeline"><h4>Public timeline</h4>{error && <p>{error}</p>}{events.length === 0 && !error && <p>No events recorded yet.</p>}{events.map((event, index) => <div className="timeline-row" key={`${event.kind}-${event.at}-${index}`}><strong>{event.kind}</strong><span>{new Date(event.at * 1000).toLocaleString()}</span><span>{Object.entries(event.data || {}).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${key === 'error' ? explain(String(value)) : String(value)}`).join(', ')}</span></div>)}</div>;
}

export function Live({ bots, creator, latestEvents, onRefresh }: { bots: Bot[]; creator: string; latestEvents: Record<number, Event>; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [now, setNow] = useState(Date.now());
  const [identityResult, setIdentityResult] = useState<Attack | null>(null);
  const [identityError, setIdentityError] = useState('');
  const [identityBusy, setIdentityBusy] = useState(false);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  async function act(id: number, action: 'kill' | 'check' | 'expire') {
    setBusy(id);
    try {
      const token = action === 'kill' ? getOwner(id) : '';
      if (action === 'kill' && !token) throw new Error('This browser does not have the owner token for this bot.');
      const result = await post<{ tx_url: string | null }>(`/api/bots/${id}/${action}`, undefined, token ? { 'x-owner-token': token } : undefined);
      setFeedback(prev => ({ ...prev, [id]: `${action === 'kill' ? 'Stopped' : action === 'check' ? 'Checked' : 'Expired'} by the vault.${result.tx_url ? ` Transaction: ${result.tx_url}` : ''}` }));
      onRefresh();
    } catch (err) { setFeedback(prev => ({ ...prev, [id]: `The vault said no: ${explain(err instanceof Error ? err.message : 'UnknownError')}` })); }
    finally { setBusy(null); }
  }
  async function trySecondIdentity() {
    setIdentityBusy(true); setIdentityResult(null); setIdentityError('');
    try { setIdentityResult(await post<Attack>('/api/cheat/second-identity')); }
    catch (err) { setIdentityError(err instanceof Error ? explain(err.message) : 'Could not test identity protection.'); }
    finally { setIdentityBusy(false); }
  }
  return <section className="app-section" id="live"><div className="app-heading"><div><h2>Live bots</h2><p>Each bot has a public identity, a balance, and a lease.</p></div><span className="section-number">02</span></div>
    <div className="identity-check app-panel"><div><strong>Test the human limit</strong><p>Try a second wallet for the same person. The vault should reject it.</p></div><ScrambleButton label="Try second identity" disabled={identityBusy} onClick={() => void trySecondIdentity()}/>{identityResult && <div className={`status-message ${identityResult.blocked ? 'success' : 'danger'}`} role="status"><strong>{identityResult.blocked ? 'Blocked: true ✓' : 'Attack was not blocked'}</strong><span className="reason-badge">{identityResult.reason}</span><span>{explain(identityResult.reason)}</span></div>}{identityError && <div className="status-message" role="status">{identityError}</div>}</div>
    {!creator ? <div className="app-panel empty-state">Launch a bot to see your live record here.</div> : bots.length === 0 ? <div className="app-panel empty-state">No live bots for this creator yet.</div> : <div className="bot-grid">{bots.map(bot => {
      const left = Math.max(0, Math.ceil(bot.born_at + bot.rules.lease_seconds - now / 1000));
      return <article className="app-panel bot-card" key={bot.bot_id}>
        <div className="bot-top"><div><h3>{bot.ens_name || `Bot ${bot.bot_id}`}</h3><p>{bot.strategy.replaceAll('_', ' ')}  {bot.rules.brain === 'rule' ? 'Simple rule' : bot.rules.brain}</p></div><span className="alive-badge">Alive</span></div>
        {bot.code_hash && <span className="code-pill" title="Brain and strategy fingerprint stored on the ENSv2 text record">ENSv2 code: {bot.code_hash.slice(0, 10)}</span>}
        <div className="stat-row"><div><span>Equity</span><strong>{usd(bot.equity_usd)}</strong></div><div><span>Return</span><strong>{pct(bot.pnl_bps)}</strong></div><div><span>Time left</span><strong>{Math.floor(left / 60)}m {left % 60}s</strong></div></div>
        <div className="latest-event"><span>Latest activity</span>{latestEvents[bot.bot_id] ? <p><strong>{latestEvents[bot.bot_id].kind === 'rejected' ? 'Blocked trade' : latestEvents[bot.bot_id].kind === 'birth' ? 'Born' : latestEvents[bot.bot_id].kind === 'trade' ? 'Trade' : 'Stopped'}</strong> {Object.entries(latestEvents[bot.bot_id].data || {}).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${key === 'error' ? explain(String(value)) : String(value)}`).join(', ') || new Date(latestEvents[bot.bot_id].at * 1000).toLocaleString()}</p> : <p>Waiting for the first event.</p>}</div>
        <div className="card-actions"><ScrambleButton label={expanded === bot.bot_id ? 'Hide events' : 'View events'} onClick={() => setExpanded(expanded === bot.bot_id ? null : bot.bot_id)}/><ScrambleButton label="Check loss" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'check')}/><ScrambleButton label="Check expiry" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'expire')}/>{getOwner(bot.bot_id) && <ScrambleButton label="Stop bot" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'kill')}/>}</div>
        {bot.tx_url && <a className="proof-link" href={bot.tx_url} target="_blank" rel="noreferrer">Birth transaction ↗</a>}
        {feedback[bot.bot_id] && <p className="inline-feedback" role="status">{feedback[bot.bot_id]}</p>}
        {expanded === bot.bot_id && <Timeline id={bot.bot_id}/>}
      </article>;
    })}</div>}
  </section>;
}
