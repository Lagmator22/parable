// Section 04, the black band: three things a dishonest creator might try. Each button really sends the
// attempt to the vault on Sepolia; the answer next to it is what the vault said.
import { useState } from 'react';
import { Section } from '../components/ui/Section';
import { explain, post, type Attack, type Bot } from './api';

type Try = { key: string; title: string; text: string; path: (bots: Bot[]) => string | null };
const TRIES: Try[] = [
  { key: 'stranger', title: 'Trade without registering', text: 'A random wallet asks to trade with a bot’s money.', path: () => '/api/cheat/unregistered-trade' },
  { key: 'big', title: 'Trade past the limit', text: 'A running bot asks for 10 times its allowed size.', path: bots => bots[0] ? `/api/cheat/over-limit/${bots[0].bot_id}` : null },
  { key: 'twin', title: 'Start over with a new wallet', text: 'The same person tries to leave old graves behind.', path: () => '/api/cheat/second-identity' },
];

export function Cheat({ bots }: { bots: Bot[] }) {
  const [busy, setBusy] = useState('');
  const [answers, setAnswers] = useState<Record<string, { ok: boolean; text: string }>>({});

  async function attempt(t: Try) {
    const path = t.path(bots);
    if (!path) return;
    setBusy(t.key);
    try {
      const a = await post<Attack>(path);
      setAnswers(p => ({ ...p, [t.key]: { ok: a.blocked, text: a.blocked ? `REFUSED. ${explain(a.reason)}` : 'It went through. That should never happen.' } }));
    } catch (err) {
      setAnswers(p => ({ ...p, [t.key]: { ok: false, text: err instanceof Error ? explain(err.message) : 'Could not reach the vault.' } }));
    } finally { setBusy(''); }
  }

  return <Section id="cheat" label="04 Try to cheat" className="band">
    <h2>Try to hide a loser.</h2>
    <p className="lead">Each button sends a real attempt to the vault on Sepolia. The right answer is no.</p>
    <div className="box">{TRIES.map(t => {
      const a = answers[t.key];
      const needsBot = t.key === 'big' && bots.length === 0;
      return <div className="attempt" key={t.key}>
        <div><h3>{t.title}</h3><p>{t.text}</p></div>
        <p className={`answer ${a?.ok ? 'refused' : ''}`} role="status">{busy === t.key ? <><span className="live"/> asking the vault…</> : a ? a.text : 'Not tried yet'}</p>
        <button type="button" className="btn" disabled={busy !== '' || needsBot} onClick={() => void attempt(t)}>{needsBot ? 'Needs a running bot' : a ? 'Try again' : 'Try it'}</button>
      </div>;
    })}</div>
  </Section>;
}
