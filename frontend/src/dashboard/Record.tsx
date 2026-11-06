import { useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { brainName, causeName, explain, pct, post, usd, type Attack, type Bot, type BrainReport, type Grave, type Info, type Report } from './api';

export function Record({ graves, report, comparison, bots, creator, info, recordError }: { graves: Grave[]; report: Report | null; comparison: BrainReport[]; bots: Bot[]; creator: string; info: Info | null; recordError: string }) {
  const [attack, setAttack] = useState<Attack | null>(null);
  const [attackError, setAttackError] = useState('');
  const [attackBusy, setAttackBusy] = useState(false);
  async function tryAttack(path: string) {
    setAttackBusy(true); setAttack(null); setAttackError('');
    try { setAttack(await post<Attack>(path)); }
    catch (err) { setAttackError(err instanceof Error ? explain(err.message) : 'Could not test the vault.'); }
    finally { setAttackBusy(false); }
  }
  return <>
    <section className="app-section" id="graveyard"><div className="app-heading"><div><h2>Graveyard</h2><p>Stopped bots stay in the public record.</p></div><span className="section-number">03</span></div>
      {creator && report && <div className="app-panel report-panel"><div className="report-head"><h3>Creator report card</h3><span className={report.vault_count_matches ? 'verified-badge' : 'warning-badge'}>{report.vault_count_matches ? '✓ Vault count matches public record' : 'Vault count does not match'}</span></div><div className="stat-row"><div><span>Launched</span><strong>{report.launched}</strong></div><div><span>Alive</span><strong>{report.alive}</strong></div><div><span>Dead</span><strong>{report.dead}</strong></div><div><span>Profitable</span><strong>{report.profitable}</strong></div><div><span>Average return</span><strong>{pct(report.avg_pnl_bps)}</strong></div></div></div>}
      <div className="record-source">Read live from Arkiv{info?.arkiv_explorer && <a href={info.arkiv_explorer} target="_blank" rel="noreferrer">Open Arkiv ↗</a>}</div>
      {recordError && <div className="status-message record-error" role="status">{recordError.charAt(0).toUpperCase() + recordError.slice(1)}</div>}
      {!creator ? <div className="app-panel empty-state">Launch a bot to see its full history.</div> : graves.length === 0 ? <div className="app-panel empty-state">{recordError ? 'History will appear when Arkiv responds.' : 'No bot has died yet. Its record will appear here when it does.'}</div> : <div className="grave-grid">{graves.map(grave => <article className="app-panel grave-card" key={grave.bot_id}><span className="dead-badge">Dead</span><h3>{grave.ens_name}</h3><p>{causeName(grave.cause)}</p><div className="stat-row"><div><span>Final equity</span><strong>{usd(grave.final_equity_usd)}</strong></div><div><span>Return</span><strong>{pct(grave.pnl_bps)}</strong></div><div><span>Lifetime</span><strong>{Math.round(grave.lifetime_s / 60)} min</strong></div></div><p>Brain: {brainName(grave.brain)}</p>{grave.tx_url && <a className="proof-link" href={grave.tx_url} target="_blank" rel="noreferrer">Death transaction ↗</a>}</article>)}</div>}
    </section>
    <section className="app-section" id="compare"><div className="app-heading"><div><h2>Compare brains</h2><p>Results across all public bots. Every failure counts.</p></div><span className="section-number">04</span></div>
      {comparison.length === 0 ? <div className="app-panel empty-state">{recordError ? 'Comparison is unavailable until Arkiv responds.' : 'No bots to compare yet.'}</div> : <div className="app-panel table-wrap"><table><thead><tr><th>Brain</th><th>Launched</th><th>Alive</th><th>Dead</th><th>Profitable</th><th>Average return</th><th>Worst return</th></tr></thead><tbody>{comparison.map(row => <tr key={row.brain}><th scope="row">{brainName(row.brain)}{!row.available && <span className="unavailable">Unavailable now</span>}</th><td>{row.launched}</td><td>{row.alive}</td><td>{row.dead}</td><td>{row.profitable}</td><td>{pct(row.avg_pnl_bps)}</td><td>{pct(row.worst_pnl_bps)}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="app-section" id="proof"><div className="app-heading"><div><h2>Try to cheat</h2><p>Test the vault’s rules yourself. A blocked attack is the expected result.</p></div><span className="section-number">05</span></div>
      <div className="app-panel proof-panel"><div className="card-actions"><ScrambleButton label="Unregistered wallet" disabled={attackBusy} onClick={() => void tryAttack('/api/cheat/unregistered-trade')}/><ScrambleButton label="Trade over the limit" disabled={attackBusy || bots.length === 0} onClick={() => void tryAttack(`/api/cheat/over-limit/${bots[0].bot_id}`)}/><ScrambleButton label="Second identity" disabled={attackBusy || bots.length === 0} onClick={() => void tryAttack('/api/cheat/second-identity')}/></div>{attack && <div className={`status-message ${attack.blocked ? 'success' : 'danger'}`} role="status"><strong>{attack.blocked ? 'Blocked by the vault ✓' : 'Attack was not blocked'}</strong><span>{explain(attack.reason)}</span></div>}{attackError && <div className="status-message" role="status">{attackError}</div>}
        <div className="proof-addresses">{info?.vault_address && <p>Vault: <a href={`${info.explorer.replace('/tx/', '/address/')}${info.vault_address}`} target="_blank" rel="noreferrer">{info.vault_address} ↗</a></p>}{info?.arkiv_writer && <p>Arkiv writer: <span>{info.arkiv_writer}</span></p>}{info?.ens_parent && <p>ENS namespace: <a href={info.ens_app} target="_blank" rel="noreferrer">{info.ens_parent} ↗</a></p>}</div>
      </div>
    </section>
  </>;
}
