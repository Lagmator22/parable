import { useEffect, useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { explain, getOwner, pct, post, usd, type Bot, type Event, type Info } from './api';

type Props = {
  bots: Bot[];
  creator: string;
  botEvents: Record<number, Event[]>;
  info: Info | null;
  onRefresh: () => void;
};

function formatEventData(data: Record<string, unknown>): string {
  const entries = Object.entries(data || {});
  if (entries.length === 0) return '';
  return entries
    .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${k === 'error' || k === 'reason' ? explain(String(v)) : k === 'amount_usd' ? usd(Number(v)) : String(v)}`)
    .join(' · ');
}

export function Live({ bots, creator, botEvents, info, onRefresh }: Props) {
  const [busy, setBusy] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  async function act(id: number, action: 'kill' | 'check' | 'expire') {
    setBusy(id);
    try {
      const token = action === 'kill' ? getOwner(id) : '';
      if (action === 'kill' && !token) throw new Error('This browser does not have the owner token for this bot.');
      const result = await post<{ tx_url: string | null }>(`/api/bots/${id}/${action}`, undefined, token ? { 'x-owner-token': token } : undefined);
      setFeedback(prev => ({ ...prev, [id]: `${action === 'kill' ? 'Stopped' : action === 'check' ? 'Checked' : 'Expired'} by the vault.${result.tx_url ? ` Transaction: ${result.tx_url}` : ''}` }));
      onRefresh();
    } catch (err) {
      setFeedback(prev => ({ ...prev, [id]: `The vault said no: ${explain(err instanceof Error ? err.message : 'UnknownError')}` }));
    } finally {
      setBusy(null);
    }
  }

  return <section className="app-section" id="live">
    <div className="app-heading">
      <div>
        <span className="live-tag">LIVE · Sepolia + Arkiv</span>
        <h2>Live bots</h2>
        <p>Each bot has a soulbound ENSv2 badge, a vault balance, and a live countdown.</p>
      </div>
      <span className="section-number">02</span>
    </div>
    {!creator ? <div className="app-panel empty-state">Launch a bot above to see your live record here.</div> : bots.length === 0 ? <div className="app-panel empty-state">No bots currently running — all finished bots are in the Graveyard below.</div> : <div className="bot-grid">{bots.map(bot => {
      const left = Math.max(0, Math.ceil(bot.born_at + bot.rules.lease_seconds - now / 1000));
      const events = (botEvents[bot.bot_id] || []).slice(0, 5);
      return <article className="app-panel bot-card" key={bot.bot_id}>
        <div className="bot-top">
          <div>
            <h3>{bot.ens_name || `Bot ${bot.bot_id}`}</h3>
            <p>{bot.strategy.replaceAll('_', ' ')} · {bot.rules.brain === 'rule' ? 'Simple rule' : bot.rules.brain}</p>
          </div>
          <span className="alive-badge"><span className="pulse-dot" aria-hidden="true"/>Alive</span>
        </div>
        {bot.code_hash && <span className="code-pill" title="Brain and strategy fingerprint stored on the ENSv2 text record">ENSv2 code: {bot.code_hash.slice(0, 10)}</span>}
        <div className="stat-row">
          <div><span>Equity</span><strong>{usd(bot.equity_usd)}</strong></div>
          <div><span>Return</span><strong className={(bot.pnl_bps || 0) > 0 ? 'pnl-pos' : (bot.pnl_bps || 0) < 0 ? 'pnl-neg' : ''}>{pct(bot.pnl_bps)}</strong></div>
          <div><span>Time left</span><strong>{Math.floor(left / 60)}m {left % 60}s</strong></div>
        </div>
        <div className="timeline">
          <h4>Last {events.length || 0} events (inline from Arkiv)</h4>
          {events.length === 0 ? <p>Waiting for the first event…</p> : events.map(ev => {
            const isBlocked = ev.kind === 'rejected';
            const txHref = ev.tx_hash && info?.explorer ? `${info.explorer}${ev.tx_hash}` : null;
            return <div className={`timeline-row event-flash ${isBlocked ? 'event-blocked' : ''}`} key={`${ev.kind}-${ev.at}-${ev.tx_hash || ''}`}>
              <strong className={isBlocked ? 'blocked-tag' : ''}>{isBlocked ? 'BLOCKED' : ev.kind.toUpperCase()}</strong>
              <span>{new Date(ev.at * 1000).toLocaleTimeString()}</span>
              <span>
                {formatEventData(ev.data)}{' '}
                {txHref && <a className="proof-inline-link" href={txHref} target="_blank" rel="noreferrer">Etherscan ↗</a>}
              </span>
            </div>;
          })}
        </div>
        <div className="card-actions" style={{ marginTop: '16px' }}>
          <ScrambleButton label="Check loss" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'check')}/>
          <ScrambleButton label="Check expiry" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'expire')}/>
          {getOwner(bot.bot_id) && <ScrambleButton label="Stop bot" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'kill')}/>}
        </div>
        {bot.tx_url && <a className="proof-link" href={bot.tx_url} target="_blank" rel="noreferrer">Birth transaction ↗</a>}
        {feedback[bot.bot_id] && <p className="inline-feedback" role="status">{feedback[bot.bot_id]}</p>}
      </article>;
    })}</div>}
  </section>;
}
