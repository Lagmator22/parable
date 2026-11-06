import { useEffect, useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { pct, post, request, usd } from './api';

type ArenaStep = { round: number; price_usd: number; action: string; amount_usd?: number; equity_usd: number; pnl_bps: number; note: string };
type ArenaContender = { bot_id: number; label: string; ens_name: string; brain: string; strategy: string; code_hash: string; status: string; cause: string | null; final_equity_usd: number; hwm_usd: number; pnl_bps: number; trades: number; blocked: number; steps: ArenaStep[] };
type ArenaData = {
  ran_at: number;
  scenario: { id: string; title: string; subtitle: string; prices_usd: number[] };
  scenarios: { id: string; title: string; subtitle: string }[];
  benchmarks: { name: string; focus: string }[];
  summary: { launched: number; survived: number; killed_by_vault: number; profitable: number; best_pnl_bps: number; worst_pnl_bps: number };
  contenders: ArenaContender[];
};

export function Arena() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ArenaData | null>(null);
  const [busy, setBusy] = useState<string>('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open || data) return;
    request<ArenaData>('/api/arena').then(setData).catch(err => setError(err instanceof Error ? err.message : 'Could not load arena'));
  }, [open, data]);

  async function runScenario(id: string) {
    setBusy(id); setError('');
    try { setData(await post<ArenaData>('/api/arena/run', { scenario: id, live_llm: true })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not run arena benchmark'); }
    finally { setBusy(''); }
  }

  return <div className="app-panel extra-block" id="arena">
    <div className="extra-head">
      <div>
        <span className="sim-badge">SIMULATION, not the real vault</span>
        <h3>Market Arena Benchmark</h3>
        <p>Head-to-head AI brain stress test across market crashes, rallies, and live Binance ETH/USDT feeds.</p>
      </div>
      <ScrambleButton label={open ? 'Hide simulation' : 'Open simulation'} onClick={() => setOpen(prev => !prev)} aria-expanded={open}/>
    </div>
    {open && <div className="arena-body">
      {error && <div className="status-message" role="status">{error}</div>}
      {data && <>
        <div className="card-actions" style={{ marginBottom: '14px' }}>
          {data.scenarios.map(s => (
            <ScrambleButton
              key={s.id}
              className={data.scenario.id === s.id ? 'solid-action' : ''}
              label={busy === s.id ? `Running ${s.title.split(' (')[0]}…` : s.title}
              disabled={Boolean(busy)}
              onClick={() => void runScenario(s.id)}
            />
          ))}
        </div>
        <p style={{ margin: '0 0 12px', color: 'var(--muted)' }}><strong>{data.scenario.title}:</strong> {data.scenario.subtitle}</p>
        <div className="stat-row">
          <div><span>ETH Price Tape</span><strong>{data.scenario.prices_usd.map(p => `$${p.toLocaleString()}`).join(' → ')}</strong></div>
          <div><span>Survived</span><strong>{data.summary.survived} / {data.summary.launched}</strong></div>
          <div><span>Auto-killed</span><strong>{data.summary.killed_by_vault} 🪦</strong></div>
          <div><span>Best / Worst</span><strong>{pct(data.summary.best_pnl_bps)} / {pct(data.summary.worst_pnl_bps)}</strong></div>
        </div>
        <div className="bot-grid">
          {data.contenders.map(c => (
            <article className="app-panel bot-card" key={c.bot_id}>
              <div className="bot-top">
                <div>
                  <h3>{c.label}</h3>
                  <p>{c.ens_name}</p>
                </div>
                <span className={c.status === 'alive' ? 'alive-badge' : 'dead-badge'}>
                  {c.status === 'alive' ? 'Survived ✓' : '🪦 Hit loss limit'}
                </span>
              </div>
              <div className="stat-row">
                <div><span>Final Equity</span><strong>{usd(c.final_equity_usd)}</strong></div>
                <div><span>Return</span><strong className={c.pnl_bps > 0 ? 'pnl-pos' : c.pnl_bps < 0 ? 'pnl-neg' : ''}>{pct(c.pnl_bps)}</strong></div>
                <div><span>Trades / Blocked</span><strong>{c.trades} / {c.blocked}</strong></div>
              </div>
              <div className="timeline">
                <h4>Round-by-round replay</h4>
                {c.steps.map((st, idx) => (
                  <div className="timeline-row" key={`${st.round}-${idx}`}>
                    <strong>R{st.round} (${st.price_usd.toLocaleString()}): {st.action.toUpperCase()}</strong>
                    <span>{usd(st.equity_usd)} ({pct(st.pnl_bps)})</span>
                    <span>{st.note}</span>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </>}
    </div>}
  </div>;
}
