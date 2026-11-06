import { useEffect, useRef, useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { SelectMenu } from '../components/ui/SelectMenu';
import { ApiError, brainName, post, saveCreator, saveOwner, type Bot, type Brain, type Info, type Rules } from './api';

type Props = { info: Info | null; brains: Brain[]; onBorn: (creator: string) => void };
type Pending = { pending_id: string; claim: string; approve_url: string };
type Confirmed = { bot: Bot; owner_token: string; tx_url: string | null };
const pause = (ms: number) => new Promise<void>(resolve => window.setTimeout(resolve, ms));

export function Launch({ info, brains, onBorn }: Props) {
  const [strategy, setStrategy] = useState('momentum');
  const [brain, setBrain] = useState('rule');
  const [cash, setCash] = useState('100');
  const [trade, setTrade] = useState('20');
  const [loss, setLoss] = useState('10');
  const [minutes, setMinutes] = useState('60');
  const [phase, setPhase] = useState<'ready' | 'waiting' | 'creating' | 'born'>('ready');
  const [message, setMessage] = useState('');
  const [tx, setTx] = useState<string | null>(null);
  const [approvalUrl, setApprovalUrl] = useState('');
  const active = useRef(true);
  useEffect(() => () => { active.current = false; }, []);
  const available = brains.filter(item => item.available);

  async function launch(event: React.FormEvent) {
    event.preventDefault();
    if (phase === 'waiting' || phase === 'creating') return;
    const values = [cash, trade, loss, minutes].map(Number);
    if (values.some(value => !Number.isFinite(value) || value <= 0) || values[1] > values[0] || values[2] > 100) {
      setMessage('Enter positive amounts. Max trade must be no more than starting cash, and max loss at most 100%.'); return;
    }
    const rules: Rules = { strategy, brain, start_cash_usd: Math.round(values[0] * 1_000_000), max_trade_usd: Math.round(values[1] * 1_000_000), max_loss_bps: Math.round(values[2] * 100), lease_seconds: Math.round(values[3] * 60) };
    if (!available.some(item => item.brain === brain)) { setMessage('Choose an available brain.'); return; }
    setPhase('waiting'); setMessage('Starting World ID approval…'); setTx(null); setApprovalUrl('');
    const approvalTab = window.open('', '_blank');
    try {
      const pending = await post<Pending>('/api/launch', rules);
      if (approvalTab) approvalTab.location.href = pending.approve_url;
      else { setApprovalUrl(pending.approve_url); setMessage('Your browser blocked the approval tab. Open World ID below.'); }
      const deadline = Date.now() + 10 * 60_000;
      while (active.current && Date.now() < deadline) {
        try {
          const result = await post<Confirmed>(`/api/launch/${encodeURIComponent(pending.pending_id)}/confirm`, undefined, { 'x-claim': pending.claim });
          if (!active.current) return;
          saveCreator(result.bot.creator_id);
          saveOwner(result.bot.bot_id, result.owner_token);
          setPhase('born'); setApprovalUrl(''); setMessage(`${result.bot.ens_name} is alive. Its public record is ready.`);
          setTx(result.tx_url); onBorn(result.bot.creator_id); return;
        } catch (err) {
          if (err instanceof ApiError && err.status === 409) {
            if (err.message.startsWith('approved:')) {
              approvalTab?.close();
              setPhase('creating');
              setMessage('World ID approved ✓ — Creating the bot on Sepolia (ENSv2 badge + Vault registration, ~45s)…');
            }
            else setMessage('Waiting for World ID approval. Keep the approval tab open.');
            await pause(2_000); continue;
          }
          throw err;
        }
      }
      if (active.current) throw new Error('Approval timed out after 10 minutes. Start again.');
    } catch (err) {
      approvalTab?.close();
      if (active.current) { setPhase('ready'); setApprovalUrl(''); setMessage(err instanceof Error ? err.message : 'Launch failed. Try again.'); }
    }
  }

  return <section className="app-section" id="launch">
    <div className="app-heading"><div><h2>Launch a bot</h2><p>Set clear limits, then approve the bot with World ID.</p></div><span className="section-number">01</span></div>
    <div className="app-panel launch-panel">
      <form onSubmit={launch}>
        <div className="form-grid">
          <SelectMenu label="Strategy" value={strategy} onChange={setStrategy} options={(info?.strategies || ['momentum']).map(value => ({ value, label: value.replaceAll('_', ' ') }))}/>
          <SelectMenu label="Brain" value={brain} onChange={setBrain} options={available.map(item => ({ value: item.brain, label: brainName(item.brain) }))}/>
          <label>Starting cash ($)<input type="number" min="1" step="0.01" value={cash} onChange={event => setCash(event.target.value)}/></label>
          <label>Max trade ($)<input type="number" min="0.01" step="0.01" value={trade} onChange={event => setTrade(event.target.value)}/></label>
          <label>Max loss (%)<input type="number" min="0.01" max="100" step="0.01" value={loss} onChange={event => setLoss(event.target.value)}/></label>
          <label>Lifetime (minutes)<input type="number" min="1" step="1" value={minutes} onChange={event => setMinutes(event.target.value)}/></label>
        </div>
        <div className="form-foot"><ScrambleButton type="submit" label={phase === 'creating' ? 'Creating bot on-chain…' : phase === 'waiting' ? 'Waiting for approval' : 'Approve and launch'} disabled={phase === 'waiting' || phase === 'creating' || available.length === 0} className="solid-action"/><p>World ID approves the creator. The vault then registers the bot and its limits.</p></div>
      </form>
      {message && <div className={`status-message ${phase === 'born' ? 'success' : ''}`} role="status">{message}{approvalUrl && <a href={approvalUrl} target="_blank" rel="noreferrer">Open World ID ↗</a>}{tx && <a href={tx} target="_blank" rel="noreferrer">View transaction ↗</a>}</div>}
    </div>
  </section>;
}
