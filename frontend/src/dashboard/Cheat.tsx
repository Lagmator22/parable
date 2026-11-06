// Section 04, the black band: three things a dishonest creator might try. Each button asks the REAL vault on
// Sepolia to dry-run the attempt (eth_call: no fee, nothing changes). The answer is the vault's own error,
// and the "run it yourself" command repeats the exact same call so anyone can see the refusal without us.
import { useState } from 'react';
import { Section } from '../components/ui/Section';
import { explain, post, type Attack, type Bot } from './api';

type Answer = { ok: boolean; reason: string; text: string; code?: string; check?: string };
type Try = { key: string; title: string; text: string; path: (bots: Bot[]) => string | null };
const TRIES: Try[] = [
  { key: 'stranger', title: 'Trade without registering', text: 'A random wallet asks to trade with a bot’s money.', path: () => '/api/cheat/unregistered-trade' },
  { key: 'big', title: 'Trade past the limit', text: 'A running bot asks for 10 times its allowed size.', path: bots => bots[0] ? `/api/cheat/over-limit/${bots[0].bot_id}` : null },
  { key: 'twin', title: 'Start over with a new wallet', text: 'The same person tries to leave old graves behind.', path: () => '/api/cheat/second-identity' },
];

function CopyCommand({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return <button type="button" className="btn" style={{ height: 34, padding: '0 12px', fontSize: 13 }}
    onClick={() => void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1500); })}>
    {done ? 'copied' : 'copy the command'}</button>;
}

export function Cheat({ bots }: { bots: Bot[] }) {
  const [busy, setBusy] = useState('');
  const [answers, setAnswers] = useState<Record<string, Answer>>({});

  async function attempt(t: Try) {
    const path = t.path(bots);
    if (!path) return;
    setBusy(t.key);
    try {
      const a = await post<Attack & { code?: string; check?: string }>(path);
      setAnswers(p => ({ ...p, [t.key]: { ok: a.blocked, reason: a.reason, code: a.code, check: a.check,
        text: a.blocked ? `REFUSED: ${a.reason}. ${explain(a.reason)}` : 'It went through. That should never happen.' } }));
    } catch (err) {
      setAnswers(p => ({ ...p, [t.key]: { ok: false, reason: '', text: err instanceof Error ? explain(err.message) : 'Could not reach the vault.' } }));
    } finally { setBusy(''); }
  }

  return <Section id="cheat" label="04 Try to cheat" className="band">
    <h2>Try to hide a loser.</h2>
    <p className="lead">Each button asks the real vault on Sepolia to try it. The vault’s own rules answer, not our server. Copy the command to ask the contract yourself.</p>
    <div className="box">{TRIES.map(t => {
      const a = answers[t.key];
      const needsBot = t.key === 'big' && bots.length === 0;
      return <div className="attempt" key={t.key}>
        <div><h3>{t.title}</h3><p>{t.text}</p></div>
        <div className="answer" role="status">
          <p className={a?.ok ? 'refused' : ''}>{busy === t.key ? <><span className="live"/> asking the vault…</> : a ? a.text : 'Not tried yet'}</p>
          {a?.check && <div className="proof-row">
            <span>{a.code ? `The contract answers with error code ${a.code} (= ${a.reason}).` : 'Same call, straight to the contract:'}</span>
            <CopyCommand text={a.check}/>
          </div>}
        </div>
        <button type="button" className="btn" disabled={busy !== '' || needsBot} onClick={() => void attempt(t)}>{needsBot ? 'Needs a running bot' : a ? 'Try again' : 'Try it'}</button>
      </div>;
    })}</div>
    <p className="say" style={{ color: 'inherit', opacity: .75 }}>A dry run (eth_call) runs the vault’s code on Sepolia without sending a transaction, so it costs nothing and changes nothing. Run the copied command with Foundry’s cast.</p>
  </Section>;
}
