// Section 01: pick limits, approve with World ID, then watch the six launch steps finish one by one.
// The step list follows what the server reports ("step N/6 done"), never a timer.
import { useEffect, useRef, useState } from 'react';
import { Button, OutLink } from '../components/ui/Button';
import { Check, Coin, Ledger, Person, Tag, Vault, Wallet } from '../components/ui/Glyphs';
import { Section } from '../components/ui/Section';
import { SelectMenu } from '../components/ui/SelectMenu';
import { ApiError, brainName, post, saveCreator, saveOwner, type Bot, type Brain, type Info, type Rules } from './api';

type Props = { info: Info | null; brains: Brain[]; onBorn: (creator: string) => void };
type Pending = { pending_id: string; claim: string; approve_url: string };
type Confirmed = { bot: Bot; owner_token: string; tx_url: string | null };
type Phase = 'ready' | 'waiting' | 'creating' | 'born';
const pause = (ms: number) => new Promise<void>(resolve => window.setTimeout(resolve, ms));

export function Launch({ info, brains, onBorn }: Props) {
  const [strategy, setStrategy] = useState('yolo');
  const [brain, setBrain] = useState('rule');
  const [cash, setCash] = useState('100');
  const [trade, setTrade] = useState('20');
  const [loss, setLoss] = useState('10');
  const [minutes, setMinutes] = useState('10');
  const [phase, setPhase] = useState<Phase>('ready');
  const [done, setDone] = useState(0);
  const [bornBot, setBornBot] = useState<Bot | null>(null);
  const [message, setMessage] = useState('');
  const [tx, setTx] = useState<string | null>(null);
  const [approvalUrl, setApprovalUrl] = useState('');
  const active = useRef(true);
  useEffect(() => () => { active.current = false; }, []);
  const available = brains.filter(item => item.available);
  useEffect(() => {  // start on the first AI brain if there is one; the plain rule stays one click away
    // 3.5 Flash-Lite answered every test question fastest in our benchmark, so it is the default AI
    const ai = available.find(item => item.brain === 'gemini:gemini-3.5-flash-lite') || available.find(item => item.brain.startsWith('gemini:'));
    if (ai && brain === 'rule') setBrain(ai.brain);
  }, [brains.length]); // eslint-disable-line react-hooks/exhaustive-deps

  async function launch(event: React.FormEvent) {
    event.preventDefault();
    if (phase === 'waiting' || phase === 'creating') return;
    const values = [cash, trade, loss, minutes].map(Number);
    if (values.some(value => !Number.isFinite(value) || value <= 0) || values[1] > values[0] || values[2] > 100) {
      setMessage('Use positive numbers. Max trade can’t be more than the starting cash, and max loss can’t pass 100%.'); return;
    }
    if (!available.some(item => item.brain === brain)) { setMessage('Pick a brain from the list.'); return; }
    // Money goes to the server in whole units: dollars have 6 decimals, percentages are basis points (1% = 100).
    const rules: Rules = { strategy, brain, start_cash_usd: Math.round(values[0] * 1e6), max_trade_usd: Math.round(values[1] * 1e6), max_loss_bps: Math.round(values[2] * 100), lease_seconds: Math.round(values[3] * 60) };
    setPhase('waiting'); setBornBot(null); setDone(0); setTx(null); setApprovalUrl('');
    setMessage('A World ID tab is opening. Approve the bot there.');
    const approvalTab = window.open('', '_blank');
    try {
      const pending = await post<Pending>('/api/launch', rules);
      if (approvalTab) approvalTab.location.href = pending.approve_url;
      else { setApprovalUrl(pending.approve_url); setMessage('Your browser blocked the new tab. Open World ID with the link below.'); }
      const deadline = Date.now() + 10 * 60_000;
      while (active.current && Date.now() < deadline) {
        try {
          const result = await post<Confirmed>(`/api/launch/${encodeURIComponent(pending.pending_id)}/confirm`, undefined, { 'x-claim': pending.claim });
          if (!active.current) return;
          saveCreator(result.bot.creator_id);
          saveOwner(result.bot.bot_id, result.owner_token);
          setBornBot(result.bot); setDone(6); setPhase('born'); setApprovalUrl('');
          setMessage(`${result.bot.ens_name} is running. Watch it below.`);
          setTx(result.tx_url); onBorn(result.bot.creator_id); return;
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 409)) throw err;
          if (err.message.startsWith('approved:')) {
            approvalTab?.close();
            setPhase('creating');
            setDone(Number(/step (\d)\/6/.exec(err.message)?.[1] ?? 1));
            setMessage('Approved. Setting the bot up on Sepolia, this takes about a minute.');
          } else setMessage('Waiting for you to approve in the World ID tab.');
          await pause(2_000);
        }
      }
      if (active.current) throw new Error('No approval within 10 minutes. Start again.');
    } catch (err) {
      approvalTab?.close();
      if (active.current) { setPhase('ready'); setApprovalUrl(''); setMessage(err instanceof Error ? err.message : 'The launch didn’t go through. Try again.'); }
    }
  }

  const walletUrl = bornBot && info?.explorer ? `${info.explorer.replace('/tx/', '/address/')}${bornBot.bot_address}` : null;
  const steps = [
    { Icon: Person, label: 'You approved it with World ID', link: null },
    { Icon: Wallet, label: 'The bot got its own wallet', link: walletUrl },
    { Icon: Coin, label: 'It got a little test ETH for fees', link: walletUrl },
    { Icon: Tag, label: bornBot ? `It got its name: ${bornBot.ens_name}` : 'It got its ENS name', link: bornBot && info?.ens_app ? `${info.ens_app}${bornBot.ens_name}` : null },
    { Icon: Vault, label: 'The vault registered it with your limits', link: tx },
    { Icon: Ledger, label: 'Its birth was written to Arkiv', link: null },
  ];
  const busy = phase === 'waiting' || phase === 'creating';

  return <Section id="launch" n="01" title="Launch a bot" intro="Choose how it trades and how much it may lose. You approve it, the vault holds the money.">
    <div className="panel launch" data-reveal>
      <form onSubmit={launch}>
        <div className="form-grid">
          <SelectMenu label="Strategy" value={strategy} onChange={setStrategy} options={(info?.strategies || ['yolo']).map(value => ({ value, label: value.replaceAll('_', ' ') }))}/>
          <SelectMenu label="Brain" value={brain} onChange={setBrain} options={available.map(item => ({ value: item.brain, label: brainName(item.brain) }))}/>
          <label>Starting cash ($)<input type="number" min="1" step="0.01" value={cash} onChange={e => setCash(e.target.value)}/></label>
          <label>Biggest trade ($)<input type="number" min="0.01" step="0.01" value={trade} onChange={e => setTrade(e.target.value)}/></label>
          <label>Max loss (%)<input type="number" min="0.01" max="100" step="0.01" value={loss} onChange={e => setLoss(e.target.value)}/></label>
          <label>Lifetime (minutes)<input type="number" min="1" step="1" value={minutes} onChange={e => setMinutes(e.target.value)}/></label>
        </div>
        <div className="form-foot">
          <Button type="submit" variant="solid" disabled={busy || available.length === 0}>
            {phase === 'creating' ? 'Setting it up…' : phase === 'waiting' ? 'Waiting for approval…' : 'Approve and launch'}
          </Button>
          <p>Practice money on the Sepolia test network. When the lifetime ends, the bot stops for good.</p>
        </div>
      </form>
      {message && <div className={`note ${phase === 'born' ? 'good' : ''}`} role="status">
        <span>{message}</span>
        {approvalUrl && <OutLink href={approvalUrl}>Open World ID</OutLink>}
      </div>}
      {(phase === 'creating' || phase === 'born') && <ol className="steps" aria-label="Launch progress">
        {steps.map(({ Icon, label, link }, i) => {
          const state = i < done ? 'done' : i === done ? 'now' : 'later';
          return <li key={i} className={state}>
            <span className="step-icon">{state === 'done' ? <Check size={16}/> : <Icon size={16}/>}</span>
            <span>{label}</span>
            {state === 'done' && <OutLink href={link}>view</OutLink>}
          </li>;
        })}
      </ol>}
    </div>
  </Section>;
}
