// Section 02: bots running right now. Left: money, time left and buttons. Right: its history, newest first.
// Anyone can ask the vault to check a bot; only the creator's browser (it holds the owner code) can stop it.
import { useEffect, useState } from 'react';
import { OutLink } from '../components/ui/Button';
import { Section } from '../components/ui/Section';
import { brainName, explain, getOwner, pct, post, trend, usd, type Bot, type Event, type Info } from './api';

type Props = { bots: Bot[]; creator: string; botEvents: Record<number, Event[]>; info: Info | null; onRefresh: () => void };

/** One line of plain English for an event in a bot's history. */
export function describe(ev: Event): string {
  const d = ev.data || {};
  if (ev.kind === 'birth') return 'Born. The vault registered it';
  if (ev.kind === 'death') return 'Died';
  if (ev.kind === 'rejected') return `Vault said no: ${explain(String(d.reason ?? d.error ?? 'UnknownError')).toLowerCase()}`;
  const action = String(d.action ?? 'trade');
  const amount = d.amount_usd != null ? ` ${usd(Number(d.amount_usd))} of ETH` : '';
  return `${action === 'buy' ? 'Bought' : action === 'sell' ? 'Sold' : 'Traded'}${amount}`;
}

const clock = (at: number) => new Date(at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });

export function Live({ bots, creator, botEvents, info, onRefresh }: Props) {
  const [busy, setBusy] = useState<number | null>(null);
  const [said, setSaid] = useState<Record<number, string>>({});
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);

  async function act(id: number, action: 'kill' | 'check' | 'expire') {
    setBusy(id);
    try {
      const token = action === 'kill' ? getOwner(id) : '';
      await post(`/api/bots/${id}/${action}`, undefined, token ? { 'x-owner-token': token } : undefined);
      setSaid(p => ({ ...p, [id]: action === 'kill' ? 'Stopped. It’s on the register now.' : 'The vault ended it.' }));
      onRefresh();
    } catch (err) {
      setSaid(p => ({ ...p, [id]: `Vault said no: ${explain(err instanceof Error ? err.message : 'UnknownError').toLowerCase()}` }));
    } finally { setBusy(null); }
  }

  return <Section id="live" label="02 Running">
    {!creator || bots.length === 0
      ? <div className="box empty">{creator ? 'Nothing is running right now. Finished bots are on the register below.' : 'Launch a bot and it shows up here.'}</div>
      : <div className="bot-list">{bots.map(bot => {
        const left = Math.max(0, Math.ceil(bot.born_at + bot.rules.lease_seconds - now / 1000));
        const share = Math.min(1, left / Math.max(1, bot.rules.lease_seconds));
        const events = (botEvents[bot.bot_id] || []).slice(0, 6);
        return <article className="box bot" key={bot.bot_id}>
          <div className="bot-side">
            <span className="mono" style={{ fontSize: 13 }}><span className="live"/> running</span>
            <h3>{bot.ens_name}</h3>
            <p className="mono muted" style={{ fontSize: 13 }}>{brainName(bot.rules.brain)} · {bot.strategy.replace('_', ' ')} · limit {usd(bot.rules.max_trade_usd)} · stop at −{bot.rules.max_loss_bps / 100}%</p>
            <dl className="stats">
              <div><dt>Value</dt><dd>{usd(bot.equity_usd)}</dd></div>
              <div><dt>Return</dt><dd className={trend(bot.pnl_bps)}>{pct(bot.pnl_bps)}</dd></div>
              <div><dt>Time left</dt><dd className="mono">{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}</dd></div>
            </dl>
            <div className="lease" aria-hidden="true"><span style={{ width: `${share * 100}%` }}/></div>
            <div className="actions">
              {getOwner(bot.bot_id) && <button type="button" className="btn btn-solid" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'kill')}>Stop this bot</button>}
              <button type="button" className="btn" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'check')}>Check its loss</button>
              <button type="button" className="btn" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'expire')}>Check its time</button>
            </div>
            {said[bot.bot_id] && <p className="say" role="status">{said[bot.bot_id]}</p>}
          </div>
          <div className="rows log">
            <div className="row head"><span>Its history, newest first</span></div>
            {events.length === 0 ? <div className="empty">Waiting for its first move…</div> : events.map(ev =>
              <div className={`row ${ev.kind === 'rejected' ? 'refused' : ''}`} key={`${ev.kind}-${ev.at}-${ev.tx_hash || ''}`}>
                <time className="muted">{clock(ev.at)}</time><span>{describe(ev)}</span>
                <OutLink href={ev.tx_hash && info?.explorer ? `${info.explorer}${ev.tx_hash}` : null}>tx</OutLink>
              </div>)}
          </div>
        </article>;
      })}</div>}
  </Section>;
}
