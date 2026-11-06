import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Moon, Sun, X } from 'lucide-react';
import { ScrambleButton, ScrambleLink } from './components/ui/ScrambleButton';
import { Arena } from './dashboard/Arena';
import { Launch } from './dashboard/Launch';
import { Live } from './dashboard/Live';
import { ProofBar } from './dashboard/ProofBar';
import { CompareBrains, Record } from './dashboard/Record';
import { Swarm } from './dashboard/Swarm';
import { useDashboard } from './dashboard/useDashboard';

type Theme = 'dark' | 'light';
const nav = [
  { label: 'Home', href: '#top' },
  { label: 'Launch', href: '#launch' },
  { label: 'Live bots', href: '#live' },
  { label: 'Graveyard', href: '#graveyard' },
  { label: 'Try to cheat', href: '#proof' },
  { label: 'Extras', href: '#extras' },
  { label: 'How it works', href: '#how' },
];

function savedTheme(): Theme {
  try { return localStorage.getItem('parable-theme') === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}

function scrollToSection(event: React.MouseEvent<HTMLAnchorElement>, hash: string) {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = document.getElementById(hash.slice(1));
  if (!target) return;
  event.preventDefault();
  if (window.location.hash !== hash) window.history.pushState(null, '', hash);
  target.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(savedTheme);
  const [menuOpen, setMenuOpen] = useState(false);
  const dashboard = useDashboard();
  const switching = useRef(false);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('parable-theme', theme); } catch { /* private browsing */ }
  }, [theme]);
  function toggleTheme(event: React.MouseEvent<HTMLButtonElement>) {
    if (switching.current) return;
    const next = theme === 'dark' ? 'light' : 'dark';
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion || !document.startViewTransition) { setTheme(next); return; }
    switching.current = true;
    const root = document.documentElement;
    const x = event.clientX;
    const y = event.clientY;
    root.style.setProperty('--ripple-x', `${x}px`);
    root.style.setProperty('--ripple-y', `${y}px`);
    const transition = document.startViewTransition(() => {
      root.dataset.theme = next;
      flushSync(() => setTheme(next));
    });
    transition.finished.finally(() => { switching.current = false; });
  }
  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);
  return <div className="site-shell" id="top">
    <header className="site-header" inert={menuOpen}>
      <a className="brand" href="#top">Parable<span>.</span></a>
      <div className="header-actions">
        <button className="theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>{theme === 'dark' ? <Sun size={22}/> : <Moon size={22}/>}</button>
        <ScrambleButton label="Menu" className="menu-trigger" onClick={() => setMenuOpen(true)} aria-expanded={menuOpen} aria-controls="page-menu" />
      </div>
    </header>
    <nav id="page-menu" className={`menu-overlay ${menuOpen ? 'open' : ''}`} aria-hidden={!menuOpen}>
      <div className="menu-head"><span>Navigate</span><button className="close-menu" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={26}/></button></div>
      <div className="menu-links">{nav.map(link => <ScrambleLink key={link.href} label={link.label} href={link.href} onClick={() => setMenuOpen(false)} tabIndex={menuOpen ? 0 : -1} arrow />)}</div>
      <p>Every strategy has a graveyard. Now you can see it.</p>
    </nav>
    <main inert={menuOpen}>
      {dashboard.info?.offline && <div className="offline-banner" role="status">Offline simulation: trades and identities here are practice data.</div>}
      {dashboard.error && <div className="engine-error" role="status">Public record unavailable: {dashboard.error}</div>}
      <ProofBar info={dashboard.info} creator={dashboard.creator}/>
      <section className="hero">
        <div className="hero-copy">
          <span className="live-tag">LIVE · Sepolia + World ID + ENSv2 + Arkiv</span>
          <h1>Every trading strategy has a graveyard.<br/><span>Parable is where bots can’t lie about theirs.</span></h1>
          <div className="hero-actions">
            <ScrambleLink label="Launch a bot" href="#launch" className="main-action" onClick={event => scrollToSection(event, '#launch')} arrow />
            <ScrambleLink label="See live bots" href="#live" onClick={event => scrollToSection(event, '#live')} arrow />
            <ScrambleLink label="Graveyard" href="#graveyard" onClick={event => scrollToSection(event, '#graveyard')} arrow />
          </div>
        </div>
      </section>
      <Launch info={dashboard.info} brains={dashboard.brains} onBorn={creator => { dashboard.setCreator(creator); void dashboard.refreshLive(); void dashboard.refreshRecord(); }}/>
      <Live bots={dashboard.bots} creator={dashboard.creator} botEvents={dashboard.botEvents} info={dashboard.info} onRefresh={() => { void dashboard.refreshLive(); void dashboard.refreshRecord(); }}/>
      <Record graves={dashboard.graves} report={dashboard.report} bots={dashboard.bots} creator={dashboard.creator} info={dashboard.info} recordError={dashboard.recordError}/>
      <section className="app-section" id="extras">
        <div className="app-heading">
          <div>
            <h2>Extras</h2>
            <p>AI Swarm oversight, head-to-head Market Arena simulation, and public brain comparison.</p>
          </div>
          <span className="section-number">05</span>
        </div>
        <div className="extras-stack">
          <Swarm manager={dashboard.manager} error={dashboard.managerError} onUpdate={dashboard.setManager}/>
          <Arena/>
          <CompareBrains comparison={dashboard.comparison} recordError={dashboard.recordError}/>
        </div>
      </section>
      <section className="content-section" id="how">
        <div className="section-heading">
          <h2>How it works</h2>
          <p>A bot can request a trade. The ParableVault on Sepolia checks its ENSv2 badge and risk rules, and Arkiv records every birth, trade, and death permanently.</p>
        </div>
        <div className="feature-grid">
          <article><span>01 · World ID</span><h3>One real creator</h3><p>World approval connects each bot to a verified human before launch.</p></article>
          <article><span>02 · ENSv2 + Vault</span><h3>Clear permissions</h3><p>A soulbound ENSv2 subname gives the bot an identity the Sepolia vault can check and revoke.</p></article>
          <article><span>03 · Arkiv</span><h3>No hidden losses</h3><p>Arkiv keeps births, trades, and deaths searchable forever, even after a bot dies.</p></article>
        </div>
      </section>
    </main>
    <footer inert={menuOpen}><strong>Parable<span>.</span></strong><span>Every strategy has a graveyard · Built on Sepolia, World ID, ENSv2 &amp; Arkiv</span><ScrambleLink label="Back to top" href="#top" onClick={event => scrollToSection(event, '#top')}/></footer>
  </div>;
}
