// Section 01: the launch form is one sentence. Click an underlined word, pick from the tray under the
// sentence, approve with World ID, then watch the six launch steps finish (the server reports each step).
import { useEffect, useRef, useState } from 'react';
import { Section } from '../components/ui/Section';
import { ApiError, brainName, post, saveCreator, saveOwner, type Bot, type Brain, type Info, type Rules } from './api';

type Props = { info: Info | null; brains: Brain[]; onBorn: (creator: string) => void };
type Pending = { pending_id: string; claim: string; approve_url: string };
type Confirmed = { bot: Bot; owner_token: string; tx_url: string | null };
type Field = 'strategy' | 'brain' | 'cash' | 'trade' | 'loss' | 'life';
type Option = { value: string | number; label: string; note: string; off?: boolean };
const pause = (ms: number) => new Promise<void>(resolve => window.setTimeout(resolve, ms));

const STRATEGY_NOTES: Record<string, string> = { momentum: 'buys when the price is rising', dip_buyer: 'buys after the price drops', yolo: 'trades the most it may, every turn' };
const NUMBERS: Record<'cash' | 'trade' | 'loss' | 'life', { values: number[]; note: (n: number) => string; show: (n: number) => string; unit: string }> = {
  cash: { values: [50, 100, 250, 500], note: () => 'starting cash', show: n => `$${n}`, unit: 'dollars' },
  trade: { values: [5, 10, 20, 50], note: () => 'biggest single trade', show: n => `$${n}`, unit: 'dollars' },
  loss: { values: [2, 5, 10, 25], note: n => n <= 2 ? 'very strict' : n >= 25 ? 'very loose' : 'stop point', show: n => `${n}%`, unit: '%' },
  life: { values: [5, 10, 30, 60], note: n => n >= 60 ? 'long enough to see the price move' : 'lifetime', show: n => `${n} minutes`, unit: 'minutes' },
};
const TITLES: Record<Field, [string, string]> = {
  strategy: ['Pick a strategy', 'How it decides to buy or sell'], brain: ['Pick a brain', 'Dashed = not set up on this server'],
  cash: ['Starting cash', 'Practice money on Sepolia'], trade: ['Biggest single trade', 'The vault refuses anything bigger'],
  loss: ['Stop it if it loses', 'The vault ends the bot past this point'], life: ['How long it lives', 'Then it stops for good'],
};
const STEPS = ['You approved it', 'Its own wallet', 'Test ETH for fees', 'Its ENS name', 'Vault registers it', 'Written to Arkiv'];

export function Launch({ info, brains, onBorn }: Props) {
  const [v, setV] = useState({ strategy: 'yolo', brain: 'rule', cash: 100, trade: 20, loss: 10, life: 10 });
  const [open, setOpen] = useState<Field | null>(null);
  const [phase, setPhase] = useState<'ready' | 'waiting' | 'creating' | 'born'>('ready');
  const [done, setDone] = useState(0);
  const [message, setMessage] = useState('');
  const [approvalUrl, setApprovalUrl] = useState('');
  const [tx, setTx] = useState<string | null>(null);
  const active = useRef(true);
  useEffect(() => () => { active.current = false; }, []);
  useEffect(() => {  // default to the AI that answered fastest in our benchmark, if it is set up
    const ok = brains.filter(b => b.available).map(b => b.brain);
    const pick = ['gemini:gemini-3.5-flash-lite', ...ok.filter(b => b !== 'rule')].find(b => ok.includes(b));
    if (pick) setV(prev => prev.brain === 'rule' ? { ...prev, brain: pick } : prev);
  }, [brains]);

  const options = (f: Field): Option[] => {
    if (f === 'strategy') return (info?.strategies || ['momentum', 'dip_buyer', 'yolo']).map(s => ({ value: s, label: s.replace('_', ' '), note: STRATEGY_NOTES[s] || '' }));
    if (f === 'brain') return brains.map(b => ({ value: b.brain, label: brainName(b.brain), off: !b.available,
      note: !b.available ? (b.brain.startsWith('claude') ? 'not set up: needs API credit' : 'not set up') : b.brain === 'rule' ? 'no AI, never fails' : b.brain.split(':')[0] }));
    const n = NUMBERS[f];
    return n.values.map(x => ({ value: x, label: n.show(x), note: n.note(x) }));
  };
  const label = (f: Field) => f === 'strategy' ? String(v.strategy).replace('_', ' ') : f === 'brain' ? brainName(v.brain) : NUMBERS[f].show(v[f]);
  const word = (f: Field) => <button type="button" className="word" aria-expanded={open === f} onClick={() => setOpen(open === f ? null : f)}>{label(f)}</button>;
  const tooBig = v.trade > v.cash;
  const busy = phase === 'waiting' || phase === 'creating';

  async function launch() {
    if (busy || tooBig) return;
    const rules: Rules = { strategy: v.strategy, brain: v.brain, start_cash_usd: Math.round(v.cash * 1e6), max_trade_usd: Math.round(v.trade * 1e6),
      max_loss_bps: Math.round(v.loss * 100), lease_seconds: Math.round(v.life * 60) };  // dollars have 6 decimals; 1% = 100 bps
    setOpen(null); setPhase('waiting'); setDone(0); setTx(null); setApprovalUrl(''); setMessage('A World ID tab is opening. Approve the bot there.');
    const tab = window.open('', '_blank');
    try {
      const pending = await post<Pending>('/api/launch', rules);
      if (tab) tab.location.href = pending.approve_url;
      else { setApprovalUrl(pending.approve_url); setMessage('Your browser blocked the new tab. Use the link below.'); }
      const deadline = Date.now() + 10 * 60_000;
      while (active.current && Date.now() < deadline) {
        try {
          const r = await post<Confirmed>(`/api/launch/${encodeURIComponent(pending.pending_id)}/confirm`, undefined, { 'x-claim': pending.claim });
          if (!active.current) return;
          saveCreator(r.bot.creator_id); saveOwner(r.bot.bot_id, r.owner_token);
          setDone(6); setPhase('born'); setTx(r.tx_url); setApprovalUrl('');
          setMessage(`${r.bot.ens_name} is running. It shows up below.`); onBorn(r.bot.creator_id); return;
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 409)) throw err;
          if (err.message.startsWith('approved:')) {
            tab?.close(); setPhase('creating');
            setDone(Number(/step (\d)\/6/.exec(err.message)?.[1] ?? 1));
            setMessage('Approved. Setting the bot up on Sepolia');
          } else setMessage('Waiting for you to approve in the World ID tab');
          await pause(2_000);
        }
      }
      if (active.current) throw new Error('No approval within 10 minutes. Start again.');
    } catch (err) {
      tab?.close();
      if (active.current) { setPhase('ready'); setApprovalUrl(''); setMessage(err instanceof Error ? err.message : 'The launch didn’t go through. Try again.'); }
    }
  }

  return <Section id="launch" label="01 Launch">
    <p className="sentence">
      Launch a {word('strategy')} bot that thinks with <span className="nowrap">{word('brain')},</span> starts with <span className="nowrap">{word('cash')},</span> trades
      at most {word('trade')} at a time, is stopped if it loses <span className="nowrap">{word('loss')},</span> and lives <span className="nowrap">{word('life')}.</span>
    </p>
    {open && <div className="box">
      <div className="box-head"><strong style={{ fontFamily: 'var(--head)', fontSize: 18 }}>{TITLES[open][0]}</strong><span className="muted">{TITLES[open][1]}</span>
        <button type="button" className="square-btn" aria-label="Close" onClick={() => setOpen(null)}>×</button></div>
      <div className="tray-options">{options(open).map(o => <button type="button" key={String(o.value)} className="opt" disabled={o.off}
        aria-pressed={v[open] === o.value} onClick={() => { setV(prev => ({ ...prev, [open]: o.value })); setOpen(null); }}>
        <strong style={{ textTransform: open === 'strategy' ? 'capitalize' : undefined }}>{o.label}</strong><span>{o.note}</span></button>)}</div>
      {open !== 'strategy' && open !== 'brain' && <label className="custom">Or type your own
        <input type="number" min="1" value={v[open]} onChange={e => { const n = Number(e.target.value); if (n > 0) setV(prev => ({ ...prev, [open]: n })); }}/>
        <span className="muted">{NUMBERS[open].unit}</span></label>}
    </div>}
    <div className="actions">
      <button type="button" className="btn btn-solid" disabled={busy || tooBig || brains.length === 0} onClick={() => void launch()}>
        {phase === 'creating' ? 'Setting it up…' : phase === 'waiting' ? 'Waiting for approval…' : 'Approve with World ID'}</button>
      <p className={`say ${tooBig ? 'bad' : ''}`}>{tooBig ? 'The biggest trade can’t be more than the starting cash.'
        : `The vault holds the $${v.cash} and enforces the $${v.trade} and ${v.loss}% limits, not the bot. Practice money on Sepolia.`}</p>
    </div>
    {message && <div className="box">
      <div className="box-head"><span>{phase === 'creating' && <span className="live"/>} {message}</span>
        <span>{phase === 'creating' || phase === 'born' ? `step ${Math.min(done + (phase === 'born' ? 0 : 1), 6)} of 6` : ''}</span></div>
      {(phase === 'creating' || phase === 'born') && <ol className="steps">{STEPS.map((s, i) =>
        <li key={s} className={i < done ? 'done' : i === done ? 'now' : ''}><span>{i < done ? `${i + 1} done` : i === done ? <><span className="live"/> working</> : i + 1}</span>{s}</li>)}</ol>}
      {(approvalUrl || tx) && <div className="chart-note">{approvalUrl && <a href={approvalUrl} target="_blank" rel="noreferrer">Open World ID</a>}
        {tx && <a href={tx} target="_blank" rel="noreferrer">See the vault transaction</a>}</div>}
    </div>}
  </Section>;
}
