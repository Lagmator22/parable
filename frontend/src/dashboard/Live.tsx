// Section 02: bots that are running right now. Each card shows money, time left and its last few events,
// newest first. Anyone can ask the vault to check a bot; only the creator's browser can stop it.
import { useEffect, useState } from 'react';
import { Button, OutLink } from '../components/ui/Button';
import { Brain, Heartbeat, Sprout, eventGlyph } from '../components/ui/Glyphs';
import { Section } from '../components/ui/Section';
import { brainName, explain, getOwner, pct, post, trend, usd, type Bot, type Event, type Info } from './api';

type Props = { bots: Bot[]; creator: string; botEvents: Record<number, Event[]>; info: Info | null; onRefresh: () => void };

/** One line of plain English for an event in a bot's history. */
export function describe(ev: Event): string {
  const d = ev.data || {};
  if (ev.kind === 'birth') return 'Born and registered by the vault';
  if (ev.kind === 'death') return 'Died';
  if (ev.kind === 'rejected') return `Vault said no: ${explain(String(d.reason ?? d.error ?? 'UnknownError'))}`;
  const action = String(d.action ?? 'trade');
  const amount = d.amount_usd != null ? ` ${usd(Number(d.amount_usd))} of ETH` : '';
  return `${action === 'buy' ? 'Bought' : action === 'sell' ? 'Sold' : 'Traded'}${amount}`;
}


export function Live({ bots, creator, botEvents, info, onRefresh }: Props) {
  const [busy, setBusy] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);

  async function act(id: number, action: 'kill' | 'check' | 'expire') {
    setBusy(id);
    try {
      const token = action === 'kill' ? getOwner(id) : '';
      await post(`/api/bots/${id}/${action}`, undefined, token ? { 'x-owner-token': token } : undefined);
      setFeedback(prev => ({ ...prev, [id]: action === 'kill' ? 'Stopped. It’s in the graveyard now.' : 'The vault ended it.' }));
      onRefresh();
    } catch (err) {
      setFeedback(prev => ({ ...prev, [id]: `Vault said no: ${explain(err instanceof Error ? err.message : 'UnknownError')}` }));
    } finally { setBusy(null); }
  }

  return <Section id="live" n="02" title="Running now" intro="Each bot trades with the vault’s money under the limits you set. Every move lands in its history.">
    {!creator || bots.length === 0
      ? <div className="panel empty" data-reveal><Sprout size={28}/><p>{creator ? 'No bot is running right now. Finished bots are in the graveyard.' : 'Launch a bot and it shows up here.'}</p></div>
      : <div className="bot-grid">{bots.map((bot, i) => {
        const left = Math.max(0, Math.ceil(bot.born_at + bot.rules.lease_seconds - now / 1000));
        const share = Math.min(1, left / Math.max(1, bot.rules.lease_seconds));
        const events = (botEvents[bot.bot_id] || []).slice(0, 5);
        const mine = Boolean(getOwner(bot.bot_id));
        return <article className="panel bot" key={bot.bot_id} data-reveal style={{ '--i': i } as React.CSSProperties}>
          <div className="bot-head">
            <div>
              <h3>{bot.ens_name}</h3>
              <p><Brain size={15}/>{brainName(bot.rules.brain)} · {bot.strategy.replaceAll('_', ' ')}</p>
            </div>
            <span className="alive"><Heartbeat size={20}/>alive</span>
          </div>
          <dl className="stats">
            <div><dt>Value</dt><dd>{usd(bot.equity_usd)}</dd></div>
            <div><dt>Return</dt><dd className={trend(bot.pnl_bps)}>{pct(bot.pnl_bps)}</dd></div>
            <div><dt>Time left</dt><dd>{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}</dd></div>
          </dl>
          <div className="lease" aria-hidden="true"><span style={{ transform: `scaleX(${share})` }}/></div>
          <ol className="history" aria-label={`Latest events for ${bot.ens_name}`}>
            {events.length === 0 ? <li className="quiet">Waiting for its first move…</li> : events.map(ev => {
              const G = eventGlyph(ev.kind);
              return <li key={`${ev.kind}-${ev.at}-${ev.tx_hash || ''}`} className={`ev ev-${ev.kind}`}>
                <G size={16}/><span>{describe(ev)}</span>
                <time>{new Date(ev.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
                <OutLink href={ev.tx_hash && info?.explorer ? `${info.explorer}${ev.tx_hash}` : null}>tx</OutLink>
              </li>;
            })}
          </ol>
          <div className="actions">
            {mine && <Button variant="solid" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'kill')}>Stop this bot</Button>}
            <Button variant="quiet" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'check')}>Check its loss</Button>
            <Button variant="quiet" disabled={busy === bot.bot_id} onClick={() => void act(bot.bot_id, 'expire')}>Check its time</Button>
          </div>
          {feedback[bot.bot_id] && <p className="feedback" role="status">{feedback[bot.bot_id]}</p>}
        </article>;
      })}</div>}
  </Section>;
}
