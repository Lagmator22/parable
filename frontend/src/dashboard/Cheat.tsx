// Section 04: three things a dishonest creator might try. Each button really sends the attempt to the
// vault on Sepolia; the answer under the card is what the vault said.
import { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Person, Shield, Trade, Wallet } from '../components/ui/Glyphs';
import { Section } from '../components/ui/Section';
import { explain, post, type Attack, type Bot } from './api';

type Try = { key: string; Icon: typeof Wallet; title: string; text: string; path: (bots: Bot[]) => string | null };
const tries: Try[] = [
  { key: 'stranger', Icon: Wallet, title: 'Trade without registering', text: 'A random wallet asks the vault to trade with a bot’s money.', path: () => '/api/cheat/unregistered-trade' },
  { key: 'big', Icon: Trade, title: 'Trade past the limit', text: 'A running bot asks for a trade 10 times bigger than it’s allowed.', path: bots => bots[0] ? `/api/cheat/over-limit/${bots[0].bot_id}` : null },
  { key: 'twin', Icon: Person, title: 'Start over with a new wallet', text: 'The same person tries a fresh wallet to leave their old graves behind.', path: () => '/api/cheat/second-identity' },
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
      setAnswers(prev => ({ ...prev, [t.key]: { ok: a.blocked, text: a.blocked ? explain(a.reason) : 'It went through. That should never happen.' } }));
    } catch (err) {
      setAnswers(prev => ({ ...prev, [t.key]: { ok: false, text: err instanceof Error ? explain(err.message) : 'Could not reach the vault.' } }));
    } finally { setBusy(''); }
  }

  return <Section id="cheat" n="04" title="Try to cheat" intro="Each button sends a real attempt to the vault. A refusal is the right answer.">
    <div className="tries">{tries.map((t, i) => {
      const answer = answers[t.key];
      const needsBot = t.key === 'big' && bots.length === 0;
      return <article className={`panel try ${answer ? (answer.ok ? 'held' : 'broke') : ''}`} key={t.key} data-reveal style={{ '--i': i } as React.CSSProperties}>
        <t.Icon size={26}/>
        <h3>{t.title}</h3>
        <p>{t.text}</p>
        <Button disabled={busy !== '' || needsBot} onClick={() => void attempt(t)}>{busy === t.key ? 'Asking the vault…' : needsBot ? 'Needs a running bot' : 'Try it'}</Button>
        {answer && <p className="answer" role="status"><Shield size={16}/>{answer.ok ? 'Refused. ' : ''}{answer.text}</p>}
      </article>;
    })}</div>
  </Section>;
}
