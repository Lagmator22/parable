// Section 06, benchmarks: live graphs of every bot this server is running (swarm workers dashed), the ETH
// price, every brain's full record, and the practice arena. Graph lines start when the server starts.
import { useState } from 'react';
import { Chart, PALETTE } from '../components/ui/Chart';
import { Section } from '../components/ui/Section';
import { Arena } from './Arena';
import { CompareBrains } from './Record';
import { brainName, pct, type BrainReport, type Series } from './api';

const clock = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
const dollars = (v: number) => `$${v.toLocaleString('en-US', { maximumFractionDigits: v > 100 ? 0 : 2 })}`;

export function Bench({ series, comparison, recordError }: { series: Series | null; comparison: BrainReport[]; recordError: string }) {
  const [view, setView] = useState<'market' | 'vault'>('market');
  const bots = (series?.bots || []).filter(b => b.points.length > 1).slice(-6);
  const botLines = bots.map((b, i) => ({
    name: `${b.ens_name.split('.')[0]} ${brainName(b.brain).split(' ')[0]}`, color: PALETTE[i % PALETTE.length], dashed: b.swarm,
    points: b.points.map(p => [p[0], view === 'market' ? p[2] : p[1]] as [number, number]),
  }));
  const prices = series?.prices || [];
  const priceLines = [
    { name: 'Market (Coinbase)', color: 'var(--ink)', points: prices.filter(p => p[1] != null).map(p => [p[0], p[1] as number] as [number, number]) },
    { name: 'Vault (Chainlink)', color: 'var(--orange)', points: prices.filter(p => p[2] != null).map(p => [p[0], p[2] as number] as [number, number]) },
  ];
  const anyRunning = bots.some(b => b.status === 'alive');

  return <Section id="bench" label="06 Benchmarks">
    <h2>How they’re doing.</h2>
    <p className="lead">Every bot’s value over time, updated every {series?.every_s ?? 10} seconds. Swarm workers are dashed.</p>
    <div className="charts">
      <div className="box">
        <div className="box-head"><span>{anyRunning && <span className="live"/>} Bots, return since launch</span>
          <div className="toggle" role="group" aria-label="Which value">
            <button type="button" aria-pressed={view === 'market'} onClick={() => setView('market')}>at market price</button>
            <button type="button" aria-pressed={view === 'vault'} onClick={() => setView('vault')}>vault’s value</button>
          </div></div>
        {botLines.length ? <Chart label="Bot returns over time" zero lines={botLines} yFormat={v => pct(v)} xFormat={clock}/>
          : <div className="empty">Launch a bot or a swarm; its line appears here within a few seconds.</div>}
        <div className="chart-note">{view === 'market'
          ? 'Each bot’s cash and ETH valued at the live market price, so you see moves as they happen.'
          : 'The official score: the vault values ETH at the Chainlink price, which updates about once an hour on this test network.'}</div>
      </div>
      <div className="box">
        <div className="box-head"><span>{prices.length > 0 && <span className="live"/>} ETH price</span><span className="muted">dollars</span></div>
        {prices.length > 1 ? <Chart label="ETH price over time" lines={priceLines} yFormat={dollars} xFormat={clock}/>
          : <div className="empty">Collecting prices…</div>}
        <div className="chart-note">The vault trades only at the Chainlink price. The market line is there to compare.</div>
      </div>
    </div>
    <CompareBrains comparison={comparison} recordError={recordError}/>
    <Arena/>
  </Section>;
}
