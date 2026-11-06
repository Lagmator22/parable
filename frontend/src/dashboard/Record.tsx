import { useEffect, useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { brainName, causeName, explain, pct, post, request, usd, type Attack, type Bot, type BrainReport, type Grave, type Info, type Report } from './api';

const pnlClass = (bps: number | null | undefined) => (bps || 0) > 0 ? 'pnl-pos' : (bps || 0) < 0 ? 'pnl-neg' : '';

export function Record({ graves, report, bots, creator, info, recordError }: { graves: Grave[]; report: Report | null; bots: Bot[]; creator: string; info: Info | null; recordError: string }) {
  const [attack, setAttack] = useState<Attack | null>(null);
  const [attackError, setAttackError] = useState('');
  const [attackBusy, setAttackBusy] = useState(false);
  const [allMode, setAllMode] = useState(false);
  const [allGraves, setAllGraves] = useState<Grave[]>([]);
  const [allError, setAllError] = useState('');
  useEffect(() => {
    if (!allMode) return;
    let active = true;
    const refresh = () => {
      if (document.hidden) return;
      request<Grave[]>('/api/graveyard/all').then(value => { if (active) { setAllGraves(value); setAllError(''); } }).catch(err => { if (active) setAllError(err instanceof Error ? err.message : 'Could not load all graves.'); });
    };
    refresh();
    const timer = window.setInterval(refresh, 15_000);
    document.addEventListener('visibilitychange', refresh);
    return () => { active = false; window.clearInterval(timer); document.removeEventListener('visibilitychange', refresh); };
  }, [allMode]);
  async function tryAttack(path: string) {
    setAttackBusy(true); setAttack(null); setAttackError('');
    try { setAttack(await post<Attack>(path)); }
    catch (err) { setAttackError(err instanceof Error ? explain(err.message) : 'Could not test the vault.'); }
    finally { setAttackBusy(false); }
  }
  const shownGraves = allMode ? allGraves : graves;
  return <>
    <section className="app-section" id="graveyard">
      <div className="app-heading">
        <div>
          <span className="live-tag">LIVE · Arkiv + Sepolia</span>
          <h2>🪦 Graveyard + Report card</h2>
          <p>Stopped bots stay in the public record forever. Nothing can be deleted.</p>
        </div>
        <span className="section-number">03</span>
      </div>
      {creator && report && <div className="app-panel report-panel">
        <div className="report-head">
          <h3>Creator report card</h3>
          <span className={report.vault_count_matches ? 'verified-badge' : 'warning-badge'}>
            {report.vault_count_matches ? '✓ Vault count matches public record' : 'Vault count does not match'}
          </span>
        </div>
        <div className="stat-row">
          <div><span>Launched</span><strong>{report.launched}</strong></div>
          <div><span>Alive</span><strong>{report.alive}</strong></div>
          <div><span>Dead</span><strong>{report.dead}</strong></div>
          <div><span>Profitable</span><strong>{report.profitable}</strong></div>
          <div><span>Average return</span><strong className={pnlClass(report.avg_pnl_bps)}>{pct(report.avg_pnl_bps)}</strong></div>
        </div>
      </div>}
      <div className="record-source" id="record">
        <span>Read live from Arkiv</span>
        <div className="record-switch" role="group" aria-label="Graveyard scope">
          <button type="button" className={!allMode ? 'selected' : ''} aria-pressed={!allMode} onClick={() => setAllMode(false)}>Creator record</button>
          <button type="button" className={allMode ? 'selected' : ''} aria-pressed={allMode} onClick={() => setAllMode(true)}>All Graves on Arkiv</button>
        </div>
        {info?.arkiv_explorer && <a href={info.arkiv_explorer} target="_blank" rel="noreferrer">Open Arkiv ↗</a>}
      </div>
      {(allMode ? allError : recordError) && <div className="status-message record-error" role="status">{allMode ? allError : recordError}</div>}
      {!allMode && !creator ? <div className="app-panel empty-state">Launch a bot to see its full history.</div> : shownGraves.length === 0 ? <div className="app-panel empty-state">{(allMode ? allError : recordError) ? 'History will appear when Arkiv responds.' : 'No graves recorded yet.'}</div> : <div className="grave-grid">{shownGraves.map(grave => <article className="app-panel grave-card" key={grave.bot_id}>
        <div className="bot-top">
          <span className="dead-badge">🪦 Dead</span>
          {grave.code_hash && <span className="code-pill" title="Brain and strategy fingerprint stored on the ENSv2 text record">ENSv2: {grave.code_hash.slice(0, 10)}</span>}
        </div>
        <div className="grave-cause">{grave.cause === 'loss_limit' ? 'Hit loss limit' : causeName(grave.cause)}</div>
        <h3>{grave.ens_name}</h3>
        <div className="stat-row">
          <div><span>Final equity</span><strong>{usd(grave.final_equity_usd)}</strong></div>
          <div><span>Return (PnL)</span><strong className={pnlClass(grave.pnl_bps)}>{pct(grave.pnl_bps)}</strong></div>
          <div><span>Lifetime</span><strong>{Math.max(1, Math.round(grave.lifetime_s / 60))} min</strong></div>
        </div>
        <p>Brain: {brainName(grave.brain)}</p>
        {grave.tx_url && <a className="proof-link" href={grave.tx_url} target="_blank" rel="noreferrer">Death transaction ↗</a>}
      </article>)}</div>}
    </section>
    <section className="app-section" id="proof">
      <div className="app-heading">
        <div>
          <span className="live-tag">LIVE · Sepolia</span>
          <h2>Try to cheat</h2>
          <p>Test the vault’s rules yourself on-chain. A blocked attack is the expected result.</p>
        </div>
        <span className="section-number">04</span>
      </div>
      <div className="app-panel proof-panel">
        <div className="card-actions">
          <ScrambleButton label="Unregistered wallet" disabled={attackBusy} onClick={() => void tryAttack('/api/cheat/unregistered-trade')}/>
          <ScrambleButton label="Trade over the limit" disabled={attackBusy || bots.length === 0} onClick={() => void tryAttack(`/api/cheat/over-limit/${bots[0].bot_id}`)}/>
          <ScrambleButton label="Try second identity" disabled={attackBusy} onClick={() => void tryAttack('/api/cheat/second-identity')}/>
        </div>
        {attack && <div className={`status-message ${attack.blocked ? 'success' : 'danger'}`} role="status"><strong>{attack.blocked ? 'Blocked by the vault ✓' : 'Attack was not blocked'}</strong><span className="reason-badge">{attack.reason}</span><span>{explain(attack.reason)}</span></div>}
        {attackError && <div className="status-message" role="status">{attackError}</div>}
        <div className="proof-addresses">
          {info?.vault_address && <p>Vault: <a href={`${info.explorer.replace('/tx/', '/address/')}${info.vault_address}`} target="_blank" rel="noreferrer">{info.vault_address} ↗</a></p>}
          {info?.arkiv_writer && <p>Arkiv writer: <span>{info.arkiv_writer}</span></p>}
          {info?.ens_parent && <p>ENS namespace: <a href={info.ens_app} target="_blank" rel="noreferrer">{info.ens_parent} ↗</a></p>}
          <p>ERC-8004 feed: <a href="/api/erc8004" target="_blank" rel="noreferrer">/api/erc8004 ↗</a></p>
        </div>
      </div>
    </section>
  </>;
}

export function CompareBrains({ comparison, recordError }: { comparison: BrainReport[]; recordError: string }) {
  const activeRows = comparison.filter(row => row.launched > 0);
  return <div className="app-panel extra-block" id="compare">
    <div className="extra-head">
      <div>
        <span className="live-tag">LIVE · Arkiv</span>
        <h3>Compare brains</h3>
        <p>Public track record across brains with launched bots. Every failure counts.</p>
      </div>
    </div>
    {activeRows.length === 0 ? <p className="empty-state">{recordError ? 'Comparison is unavailable until Arkiv responds.' : 'No bots launched yet.'}</p> : <div className="table-wrap"><table><thead><tr><th>Brain</th><th>Launched</th><th>Alive</th><th>Dead</th><th>Profitable</th><th>Average return</th><th>Worst return</th></tr></thead><tbody>{activeRows.map(row => <tr key={row.brain}><th scope="row">{brainName(row.brain)}{!row.available && <span className="unavailable">Unavailable now</span>}</th><td>{row.launched}</td><td>{row.alive}</td><td>{row.dead}</td><td>{row.profitable}</td><td className={pnlClass(row.avg_pnl_bps)}>{pct(row.avg_pnl_bps)}</td><td className={pnlClass(row.worst_pnl_bps)}>{pct(row.worst_pnl_bps)}</td></tr>)}</tbody></table></div>}
  </div>;
}
