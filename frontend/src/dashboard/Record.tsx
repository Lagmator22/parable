// Section 03, the graveyard: every bot that stopped, read from Arkiv, plus the creator's totals.
// Also the brain comparison table shown under "More".
import { useEffect, useState } from 'react';
import { OutLink } from '../components/ui/Button';
import { Check, Tomb, causeGlyph } from '../components/ui/Glyphs';
import { Section } from '../components/ui/Section';
import { brainName, pct, request, trend, usd, type BrainReport, type Grave, type Report } from './api';

const causeText = (cause: string) => ({ expired: 'Its time ran out', killed: 'Stopped by its creator', loss_limit: 'Lost too much, the vault ended it' })[cause] || cause;
const lifetime = (s: number) => s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : `${(s / 3600).toFixed(1)} h`;

type Props = { graves: Grave[]; report: Report | null; creator: string; recordError: string };

export function Graveyard({ graves, report, creator, recordError }: Props) {
  const [everyone, setEveryone] = useState(false);
  const [all, setAll] = useState<Grave[]>([]);
  const [allError, setAllError] = useState('');
  useEffect(() => {
    if (!everyone) return;
    let live = true;
    const load = () => { if (!document.hidden) request<Grave[]>('/api/graveyard/all').then(v => { if (live) { setAll(v); setAllError(''); } }).catch(e => { if (live) setAllError(e instanceof Error ? e.message : 'Could not load.'); }); };
    load();
    const t = window.setInterval(load, 15_000);
    return () => { live = false; window.clearInterval(t); };
  }, [everyone]);
  const shown = [...(everyone ? all : graves)].sort((a, b) => b.bot_id - a.bot_id);
  const problem = everyone ? allError : recordError;

  return <Section id="graveyard" n="03" title="The graveyard" intro="Bots that stopped, and why. They stay here for good: the vault writes the record, not the bot.">
    {report && <div className="totals" data-reveal>
      <dl>
        <div><dt>Launched</dt><dd>{report.launched}</dd></div>
        <div><dt>Running</dt><dd>{report.alive}</dd></div>
        <div><dt>Dead</dt><dd>{report.dead}</dd></div>
        <div><dt>Made money</dt><dd>{report.profitable}</dd></div>
        <div><dt>Average return</dt><dd className={trend(report.avg_pnl_bps)}>{pct(report.avg_pnl_bps)}</dd></div>
      </dl>
      <p className={report.vault_count_matches ? 'match' : 'mismatch'}>
        {report.vault_count_matches ? <><Check size={16}/>The vault counts {report.launched} bots too. None are missing.</> : 'This list and the vault’s count differ right now. It usually catches up within a minute.'}
      </p>
    </div>}
    <div className="grave-bar" data-reveal>
      <div className="switch" role="group" aria-label="Whose graves">
        <button type="button" aria-pressed={!everyone} onClick={() => setEveryone(false)}>Mine</button>
        <button type="button" aria-pressed={everyone} onClick={() => setEveryone(true)}>Everyone’s</button>
      </div>
      <span>Read from Arkiv</span>
    </div>
    {problem && <div className="note" role="status">{problem}</div>}
    {!everyone && !creator ? <div className="panel empty"><Tomb size={28}/><p>Launch a bot to start your record.</p></div>
      : shown.length === 0 ? <div className="panel empty"><Tomb size={28}/><p>{problem ? 'The graves will show up once Arkiv answers.' : 'No graves yet. Every bot ends up here eventually.'}</p></div>
      : <div className="graves">{shown.map((g, i) => {
        const Why = causeGlyph(g.cause);
        return <article className="grave" key={g.bot_id} data-reveal style={{ '--i': i % 6 } as React.CSSProperties}>
          <Tomb className="grave-mark" size={30}/>
          <h3>{g.ens_name}</h3>
          <p className={`why why-${g.cause}`}><Why size={16}/>{causeText(g.cause)}</p>
          <dl className="stats">
            <div><dt>Ended</dt><dd>{usd(g.final_equity_usd)}</dd></div>
            <div><dt>Return</dt><dd className={trend(g.pnl_bps)}>{pct(g.pnl_bps)}</dd></div>
            <div><dt>Lived</dt><dd>{lifetime(g.lifetime_s)}</dd></div>
          </dl>
          <p className="epitaph">{brainName(g.brain)}{g.code_hash ? <> · <span title="Fingerprint of its brain and strategy, saved in its ENS name">code {g.code_hash.slice(0, 8)}</span></> : null}</p>
          <OutLink href={g.tx_url}>last transaction</OutLink>
        </article>;
      })}</div>}
  </Section>;
}

export function CompareBrains({ comparison, recordError }: { comparison: BrainReport[]; recordError: string }) {
  const rows = comparison.filter(row => row.launched > 0);
  return <details className="panel extra" id="compare">
    <summary><div><h3>Compare brains</h3><p>Which AI model did best, counting the bots that died too.</p></div></summary>
    {rows.length === 0 ? <p className="quiet">{recordError ? 'Available once Arkiv answers.' : 'No bots launched yet.'}</p>
      : <div className="table-wrap"><table>
        <thead><tr><th>Brain</th><th>Launched</th><th>Running</th><th>Dead</th><th>Made money</th><th>Average</th><th>Worst</th></tr></thead>
        <tbody>{rows.map(r => <tr key={r.brain}><th scope="row">{brainName(r.brain)}</th><td>{r.launched}</td><td>{r.alive}</td><td>{r.dead}</td><td>{r.profitable}</td><td className={trend(r.avg_pnl_bps)}>{pct(r.avg_pnl_bps)}</td><td className={trend(r.worst_pnl_bps)}>{pct(r.worst_pnl_bps)}</td></tr>)}</tbody>
      </table></div>}
  </details>;
}
