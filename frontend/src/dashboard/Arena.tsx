// Inside Benchmarks: the practice arena. Four bots replay a made-up market (a crash, a rally, choppy prices,
// or recent Binance prices made 15x bigger) against a copy of the vault's rules kept in memory.
// Nothing here touches the Sepolia vault or Arkiv, and the page says so.
import { useEffect, useState } from 'react';
import { Chart, PALETTE } from '../components/ui/Chart';
import { pct, post, request } from './api';

type Step = { round: number; pnl_bps: number };
type Contender = { bot_id: number; label: string; status: string; pnl_bps: number; trades: number; blocked: number; steps: Step[] };
type ArenaData = { scenario: { id: string; title: string; subtitle: string }; scenarios: { id: string; title: string }[]; contenders: Contender[] };

export function Arena() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ArenaData | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (open && !data) request<ArenaData>('/api/arena').then(setData).catch(e => setError(e instanceof Error ? e.message : 'Could not load it.'));
  }, [open, data]);

  async function run(id: string) {
    setBusy(id); setError('');
    try { setData(await post<ArenaData>('/api/arena/run', { scenario: id, live_llm: true })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not run it.'); }
    finally { setBusy(''); }
  }

  return <details className="box" onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}>
    <summary><div><strong>Practice arena</strong><span>Made-up markets to see how each brain copes with a crash or a rally. Separate from the vault.</span></div></summary>
    {error && <div className="empty">{error}</div>}
    {open && !data && !error && <div className="empty"><span className="live"/> loading…</div>}
    {data && <>
      <div className="box-head" style={{ borderTop: '1px solid var(--ink)' }}>
        <div className="toggle" role="group" aria-label="Market">{data.scenarios.map(s => <button type="button" key={s.id} aria-pressed={data.scenario.id === s.id}
          disabled={Boolean(busy)} onClick={() => void run(s.id)}>{busy === s.id ? 'running…' : s.title.split(' (')[0]}</button>)}</div>
      </div>
      <Chart label="Practice arena returns by round" zero yFormat={v => pct(v)} xFormat={x => `round ${x}`}
        lines={data.contenders.map((c, i) => ({ name: c.label.replace('Gemini 3.5 Flash-Lite', 'Gemini').replace('Rule Baseline', 'Rule'), color: PALETTE[i % PALETTE.length],
          dashed: c.status !== 'alive', points: [[0, 0], ...c.steps.map(s => [s.round, s.pnl_bps] as [number, number])] }))}/>
      <div className="chart-note">{data.scenario.subtitle} Dashed line = the vault ended that bot for losing too much.</div>
    </>}
  </details>;
}
