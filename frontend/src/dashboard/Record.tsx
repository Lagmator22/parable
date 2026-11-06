// Section 03, the register: every bot ever launched, dead ones included, read from Arkiv. A dead bot's name
// is struck through; orange only when the vault ended it for losing. Also the brain comparison table.
import { Fragment, useMemo, useState } from 'react';
import { Button, OutLink } from '../components/ui/Button';
import { Section } from '../components/ui/Section';
import { brainName, causeName, pct, trend, type BrainReport, type Grave, type Report } from './api';

type Props = { graves: Grave[]; report: Report | null; recordError: string };
const PAGE_SIZE = 10;
const lived = (s: number) => s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : `${(s / 3600).toFixed(1)} h`;

function GraveyardPages({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const lastPage = Math.ceil(total / PAGE_SIZE);
  const first = Math.max(2, Math.min(page - 1, lastPage - 3));
  const last = Math.min(lastPage - 1, first + 2);
  const pages = [1];
  for (let number = first; number <= last; number++) pages.push(number);
  pages.push(lastPage);

  return <nav className="grave-pages" aria-label="Graveyard pages">
    <span role="status">Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total} bots</span>
    <div className="grave-page-buttons">
      <Button type="button" disabled={page === 1} onClick={() => onPage(page - 1)}>Previous</Button>
      {pages.map((number, index) => <Fragment key={number}>
        {index > 0 && number > pages[index - 1] + 1 && <span aria-hidden="true">…</span>}
        <Button type="button" variant={number === page ? 'solid' : 'line'}
          aria-label={`Page ${number}`} aria-current={number === page ? 'page' : undefined}
          onClick={() => onPage(number)}>{number}</Button>
      </Fragment>)}
      <Button type="button" disabled={page === lastPage} onClick={() => onPage(page + 1)}>Next</Button>
    </div>
  </nav>;
}

export function Register({ graves, report, recordError }: Props) {
  const [selectedPage, setPage] = useState(1);
  const rows = useMemo(() => [...graves].sort((a, b) => b.bot_id - a.bot_id), [graves]);
  const page = Math.min(selectedPage, Math.max(1, Math.ceil(rows.length / PAGE_SIZE)));
  if (selectedPage !== page) setPage(page);
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return <Section id="register" label="03 Register">
    <h2>The graveyard</h2>
    <p className="lead">Every bot that ever stopped on this vault, and how. Nobody can remove a row: the vault writes them, not the bots, and each one links to its read-only record on Arkiv. {report && (report.vault_count_matches
      ? `The vault counts ${report.launched} bots and so does this list, so none are missing.`
      : 'This list and the vault’s count differ right now; it usually catches up within a minute.')}</p>
    {recordError && <div className="box empty">{recordError}</div>}
    <div className="box rows register">
      {rows.length > PAGE_SIZE && <GraveyardPages page={page} total={rows.length} onPage={setPage}/>}
      <div className="row head"><span>No.</span><span>Name</span><span>Brain</span><span>Trades</span><span>Lived</span><span>Return</span><span>How it ended</span><span>Check it</span></div>
      {rows.length === 0 ? <div className="empty">{recordError ? 'Shows up once Arkiv answers.' : 'No bot has died yet.'}</div>
        : visibleRows.map(g => <div className={`row ${g.cause === 'loss_limit' ? 'refused' : ''}`} key={g.bot_id}>
          <span>{g.bot_id}</span><span><span className="struck">{g.ens_name}</span>{g.approval === 'demo' && <span className="muted" title="Approved without World ID (demo approval)"> · demo</span>}</span><span>{brainName(g.brain)}</span><span>{g.trades ?? '—'}</span>
          <span>{lived(g.lifetime_s)}</span><span className={trend(g.pnl_bps)}>{pct(g.pnl_bps)}</span>
          <span>{causeName(g.cause)}</span>
          <span className="links"><OutLink href={g.arkiv_url}>Arkiv</OutLink><OutLink href={g.tx_url}>tx</OutLink></span>
        </div>)}
    </div>
    {report && <div className="legend"><span>Launched {report.launched}</span><span>Running {report.alive}</span><span>Dead {report.dead}</span>
      <span>Made money {report.profitable}</span><span>Average {pct(report.avg_pnl_bps)}</span></div>}
  </Section>;
}

export function CompareBrains({ comparison, recordError }: { comparison: BrainReport[]; recordError: string }) {
  const rows = comparison.filter(r => r.launched > 0);
  return <div className="box">
    <div className="box-head"><span>Every brain’s full record, dead bots included</span><span className="muted">from Arkiv</span></div>
    {rows.length === 0 ? <div className="empty">{recordError ? 'Shows up once Arkiv answers.' : 'No bots launched yet.'}</div>
      : <div className="table-wrap"><table>
        <thead><tr><th>Brain</th><th>Launched</th><th>Running</th><th>Dead</th><th>Made money</th><th>Average</th><th>Worst</th></tr></thead>
        <tbody>{rows.map(r => <tr key={r.brain}><th scope="row">{brainName(r.brain)}</th><td>{r.launched}</td><td>{r.alive}</td><td>{r.dead}</td>
          <td>{r.profitable}</td><td className={trend(r.avg_pnl_bps)}>{pct(r.avg_pnl_bps)}</td><td className={trend(r.worst_pnl_bps)}>{pct(r.worst_pnl_bps)}</td></tr>)}</tbody>
      </table></div>}
  </div>;
}
