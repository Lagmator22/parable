// Under "More": a practice arena. Four bots replay made-up price paths (a crash, a rally, choppy prices)
// against a copy of the vault's rules kept in memory. Nothing here touches the Sepolia vault or Arkiv.
import { useEffect, useState } from 'react';
import { Button } from '../components/ui/Button';
import { Fall, Price } from '../components/ui/Glyphs';
import { pct, post, request, usd } from './api';

type Step = { round: number; price_usd: number; action: string; equity_usd: number; pnl_bps: number; note: string };
type Contender = { bot_id: number; label: string; status: string; final_equity_usd: number; pnl_bps: number; trades: number; blocked: number; steps: Step[] };
type ArenaData = {
  scenario: { id: string; title: string; subtitle: string; prices_usd: number[] };
  scenarios: { id: string; title: string; subtitle: string }[];
  contenders: Contender[];
};

/** A tiny line drawing of the price path. */
function Spark({ prices }: { prices: number[] }) {
  if (prices.length < 2) return null;
  const lo = Math.min(...prices), hi = Math.max(...prices), span = hi - lo || 1;
  const pts = prices.map((p, i) => `${(i / (prices.length - 1)) * 100},${30 - ((p - lo) / span) * 28 - 1}`).join(' ');
  return <svg className="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true"><polyline points={pts}/></svg>;
}

export function Arena() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ArenaData | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open || data) return;
    request<ArenaData>('/api/arena').then(setData).catch(e => setError(e instanceof Error ? e.message : 'Could not load the arena.'));
  }, [open, data]);

  async function run(id: string) {
    setBusy(id); setError('');
    try { setData(await post<ArenaData>('/api/arena/run', { scenario: id, live_llm: true })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not run it.'); }
    finally { setBusy(''); }
  }

  return <details className="panel extra" id="arena" onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}>
    <summary><div><h3>Practice arena</h3><p>Made-up markets to see how each brain copes with a crash or a rally. Separate from the real vault.</p></div></summary>
    {error && <p className="note">{error}</p>}
    {!data ? open && <p className="quiet">Loading…</p> : <>
      <div className="arena-pick">{data.scenarios.map(s => <Button key={s.id} variant={data.scenario.id === s.id ? 'solid' : 'quiet'} disabled={Boolean(busy)} onClick={() => void run(s.id)}>
        {busy === s.id ? 'Running…' : s.title.split(' (')[0]}
      </Button>)}</div>
      <div className="arena-tape"><Price size={18}/><span>{data.scenario.subtitle}</span><Spark prices={data.scenario.prices_usd}/></div>
      <div className="arena-grid">{data.contenders.map(c => <article key={c.bot_id} className={`contender ${c.status === 'alive' ? '' : 'out'}`}>
        <h4>{c.label}</h4>
        <p className={c.pnl_bps > 0 ? 'up' : c.pnl_bps < 0 ? 'down' : ''}>{pct(c.pnl_bps)} <small>{usd(c.final_equity_usd)}</small></p>
        <p className="quiet">{c.trades} trades · {c.blocked} refused{c.status === 'alive' ? '' : <> · <Fall size={14}/> ended by the vault</>}</p>
      </article>)}</div>
    </>}
  </details>;
}
