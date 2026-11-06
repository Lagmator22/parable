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
  const [data, setData] = useState<ArenaData | null>(null);
  const [busy, setBusy] = useState<string>('');
  const [error, setError] = useState('');

  useEffect(() => {
    request<ArenaData>('/api/arena').then(setData).catch(err => setError(err instanceof Error ? err.message : 'Could not load arena'));
  }, []);

  async function runScenario(id: string) {
    setBusy(id); setError('');
    try { setData(await post<ArenaData>('/api/arena/run', { scenario: id, live_llm: true })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not run arena benchmark'); }
    finally { setBusy(''); }
  }

  return <section className="app-section" id="arena">
    <div className="app-heading">
      <div>
        <h2>Market Arena Benchmark</h2>
        <p>Simulate AI brains head-to-head across crypto market crashes, rallies, and live Binance ETH/USDT feeds (modeled after nof1 Alpha Arena, Recall Network & FinAI Agent Market Arena).</p>
      </div>
      <span className="section-number">04</span>
    </div>
    {error && <div className="status-message" role="status">{error}</div>}
    {data && <div className="app-panel">
      <div className="card-actions" style={{ marginBottom: '1rem' }}>
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
      <p style={{ marginBottom: '0.75rem' }}><strong>{data.scenario.title}:</strong> {data.scenario.subtitle}</p>
      <div className="stat-row" style={{ marginBottom: '1rem' }}>
        <div><span>ETH Price Tape</span><strong>{data.scenario.prices_usd.map(p => `$${p.toLocaleString()}`).join(' → ')}</strong></div>
        <div><span>Survived</span><strong>{data.summary.survived} / {data.summary.launched}</strong></div>
        <div><span>Auto-killed by Vault</span><strong>{data.summary.killed_by_vault} 🪦</strong></div>
        <div><span>Best / Worst Return</span><strong>{pct(data.summary.best_pnl_bps)} / {pct(data.summary.worst_pnl_bps)}</strong></div>
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
                {c.status === 'alive' ? 'Survived ✓' : '🪦 Vault Killed (loss_limit)'}
              </span>
            </div>
            <span className="code-pill">ENSv2 code: {c.code_hash.slice(0, 10)}</span>
            <div className="stat-row">
              <div><span>Final Equity</span><strong>{usd(c.final_equity_usd)}</strong></div>
              <div><span>Return</span><strong>{pct(c.pnl_bps)}</strong></div>
              <div><span>Trades / Blocked</span><strong>{c.trades} / {c.blocked}</strong></div>
            </div>
            <div className="timeline">
              <h4>Round-by-round market replay</h4>
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
    </div>}
  </section>;
}
