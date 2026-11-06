// The whole page, top to bottom: headline with the born/dead counts, launch, running bots, the register,
// try to cheat, the swarm, benchmarks, how it works. Data comes from useDashboard (the engine's /api routes).
import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Moon, Sun } from 'lucide-react';
import { Tomb } from './components/ui/Glyphs';
import { Section } from './components/ui/Section';
import { Bench } from './dashboard/Bench';
import { Cheat } from './dashboard/Cheat';
import { Launch } from './dashboard/Launch';
import { Live } from './dashboard/Live';
import { Register } from './dashboard/Record';
import { Swarm } from './dashboard/Swarm';
import { Telemetry } from './dashboard/Telemetry';
import { causeName, pct, type Info } from './dashboard/api';
import { useDashboard } from './dashboard/useDashboard';

type Theme = 'dark' | 'light';
const NAV = [['Launch', '#launch'], ['Running', '#live'], ['Register', '#register'], ['Try to cheat', '#cheat'], ['Swarm', '#swarm'], ['Benchmarks', '#bench']];
const HOW = [
  ['A person approves it', 'World ID checks one human is behind each creator.'],
  ['It gets a name', 'An ENS name that expires, can’t be sold, and can be taken away.'],
  ['The vault trades', 'The bot only asks. The vault checks the name and limits, then trades at the Chainlink price.'],
  ['It’s all written down', 'Births, trades, refusals and deaths go to Arkiv. Nobody can delete a dead bot.'],
];

function savedTheme(): Theme {
  try { return localStorage.getItem('parable-theme') === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
}

function Facts({ info }: { info: Info | null }) {
  const address = info?.explorer?.replace('/tx/', '/address/');
  return <div className="wrap facts">
    <div><span>Who approves</span>one person, via World ID</div>
    <div><span>Bot names</span>{info?.ens_app ? <a href={`${info.ens_app}${info.ens_parent}`} target="_blank" rel="noreferrer">*.{info.ens_parent}</a> : '*.parable.eth'}</div>
    <div><span>ETH price the vault uses</span>{address && info?.vault_address ? <a href={`${address}${info.vault_address}`} target="_blank" rel="noreferrer">
      {info.eth_price_usd ? `$${info.eth_price_usd.toLocaleString('en-US')} (Chainlink)` : 'Chainlink'}</a> : 'Chainlink'}</div>
    <div><span>Register kept on</span>{info?.arkiv_explorer ? <a href={`${info.arkiv_explorer}/address/${info.arkiv_writer}`} target="_blank" rel="noreferrer">Arkiv</a> : 'Arkiv'}</div>
  </div>;
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(savedTheme);
  const [tele, setTele] = useState(false);
  const d = useDashboard();
  const switching = useRef(false);
  useEffect(() => {  // no page scrolling behind the open telemetry panel
    document.body.style.overflow = tele ? 'hidden' : '';
  }, [tele]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('parable-theme', theme); } catch { /* private browsing */ }
  }, [theme]);
  function toggleTheme() {  // instant swap; the View Transition only cross-fades where the browser has it
    if (switching.current) return;
    const next = theme === 'dark' ? 'light' : 'dark';
    if (!document.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setTheme(next); return; }
    switching.current = true;
    document.startViewTransition(() => { document.documentElement.dataset.theme = next; flushSync(() => setTheme(next)); })
      .finished.finally(() => { switching.current = false; });
  }
  const refreshAll = () => { void d.refreshLive(); void d.refreshRecord(); void d.refreshSwarm(); };
  const latest = [...d.graves].sort((a, b) => b.bot_id - a.bot_id).slice(0, 4);

  return <>
    <header className="topbar"><div className="wrap">
      <a className="brand" href="#top"><Tomb size={18}/>PARABLE</a>
      <nav aria-label="Sections">{NAV.map(([label, href]) => <a key={href} href={href}>{label}</a>)}</nav>
      <button type="button" className="tele-btn" aria-expanded={tele} onClick={() => setTele(t => !t)}>{d.bots.length > 0 && <span className="live"/>}Telemetry</button>
      <button type="button" className="square-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
        {theme === 'dark' ? <Sun size={16}/> : <Moon size={16}/>}</button>
    </div></header>
    <Telemetry open={tele} onClose={() => setTele(false)} info={d.info} bots={d.bots} botEvents={d.botEvents} series={d.series} swarm={d.swarm} report={d.report}/>
    <main id="top">
      {d.info?.offline && <div className="notice" role="status">Practice mode: this server runs a pretend chain. Nothing here is on Sepolia.</div>}
      {d.error && <div className="notice" role="status">Can’t reach the server right now: {d.error}</div>}
      <section className="section hero" id="hero">
        <div className="wrap">
          <div>
            <h1>Every trading strategy has a graveyard.</h1>
            <p className="lead">Bots on Parable never hold the money and never write their own history. A vault does both. So when a bot fails, it stays on the register.</p>
            <div className="actions"><a className="btn btn-solid" href="#launch">Launch a bot</a><a className="btn" href="#register">Read the register</a></div>
          </div>
          <div className="box">
            <dl className="counts">
              <div><dt>Born</dt><dd>{d.report?.launched ?? '—'}</dd></div>
              <div className="dead"><dt>Dead</dt><dd>{d.report?.dead ?? '—'}</dd></div>
            </dl>
            <div className="box-head"><span>{d.bots.length > 0 ? <><span className="live"/> {d.bots.length} running now</> : 'Latest deaths'}</span></div>
            <div className="rows deaths">{latest.length === 0 ? <div className="empty">No deaths yet.</div> : latest.map(g =>
              <div className="row" key={g.bot_id}><span className="struck">{g.ens_name}</span><span>{pct(g.pnl_bps)}</span><span className="muted">{causeName(g.cause).toLowerCase()}</span></div>)}</div>
          </div>
        </div>
        <Facts info={d.info}/>
      </section>
      <Launch info={d.info} brains={d.brains} onBorn={creator => { d.setCreator(creator); refreshAll(); }}/>
      <Live bots={d.bots} creator={d.creator} botEvents={d.botEvents} info={d.info} onRefresh={refreshAll}/>
      <Register report={d.report} recordError={d.recordError}/>
      <Cheat bots={d.bots}/>
      <Swarm brains={d.brains} swarm={d.swarm} onUpdate={d.setSwarm} onBorn={refreshAll}/>
      <Bench series={d.series} comparison={d.comparison} recordError={d.recordError}/>
      <Section id="how" label="How it works">
        <ol className="how-list">{HOW.map(([title, text], i) => <li key={title}><span className="mono">{i + 1}</span><h3>{title}</h3><p>{text}</p></li>)}</ol>
      </Section>
    </main>
    <footer><div className="wrap"><strong style={{ fontFamily: 'var(--head)', fontWeight: 900 }}>PARABLE</strong>
      <span>Built at ETHGlobal Mumbai on Sepolia, World ID, ENS and Arkiv.</span><a href="#top">Back to top</a></div></footer>
  </>;
}
