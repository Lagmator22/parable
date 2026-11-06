import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Moon, Sun, X } from 'lucide-react';
import { ScrambleButton, ScrambleLink } from './components/ui/ScrambleButton';
import { Arena } from './dashboard/Arena';
import { Launch } from './dashboard/Launch';
import { Live } from './dashboard/Live';
import { ProofBar } from './dashboard/ProofBar';
import { Record } from './dashboard/Record';
import { Swarm } from './dashboard/Swarm';
import { useDashboard } from './dashboard/useDashboard';

type Theme = 'dark' | 'light';
const nav = [{ label: 'Home', href: '#top' }, { label: 'Launch', href: '#launch' }, { label: 'Live bots', href: '#live' }, { label: 'AI Swarm', href: '#swarm' }, { label: 'Market Arena', href: '#arena' }, { label: 'Graveyard', href: '#graveyard' }, { label: 'Compare brains', href: '#compare' }, { label: 'Test the vault', href: '#proof' }, { label: 'How it works', href: '#how' }];

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
          <h1>Every bot.<br/>Every trade.<br/><span>Every failure.</span></h1>
          <p>Creators can show you their winners. Parable shows you the whole record, including the bots that died.</p>
        </div>
        <div className="hero-visual" aria-label="Explore a bot's public history" onPointerMove={event => {
          if (event.pointerType === 'touch') return;
          const bounds = event.currentTarget.getBoundingClientRect();
          event.currentTarget.style.setProperty('--pointer-x', `${event.clientX - bounds.left}px`);
          event.currentTarget.style.setProperty('--pointer-y', `${event.clientY - bounds.top}px`);
        }}>
          <h2 className="visual-title">A bot's public history</h2>
          <a className="visual-line" href="#launch" onClick={event => scrollToSection(event, '#launch')} aria-label="Born, go to launch a bot"><span>01</span><div><strong>Born</strong><p>Approved by a real person</p></div></a>
          <a className="visual-line" href="#live" onClick={event => scrollToSection(event, '#live')} aria-label="Traded, go to live bots"><span>02</span><div><strong>Traded</strong><p>Checked by the vault</p></div></a>
          <a className="visual-line" href="#graveyard" onClick={event => scrollToSection(event, '#graveyard')} aria-label="Died, go to the graveyard"><span>03</span><div><strong>Died</strong><p>Still visible in the graveyard</p></div></a>
        </div>
      </section>
      <Launch info={dashboard.info} brains={dashboard.brains} onBorn={creator => { dashboard.setCreator(creator); void dashboard.refreshLive(); void dashboard.refreshRecord(); }}/>
      <Live bots={dashboard.bots} creator={dashboard.creator} latestEvents={dashboard.latestEvents} onRefresh={() => { void dashboard.refreshLive(); void dashboard.refreshRecord(); }}/>
      <Swarm manager={dashboard.manager} error={dashboard.managerError} onUpdate={dashboard.setManager}/>
      <Arena/>
      <Record graves={dashboard.graves} report={dashboard.report} comparison={dashboard.comparison} bots={dashboard.bots} creator={dashboard.creator} info={dashboard.info} recordError={dashboard.recordError}/>
      <section className="content-section" id="how">
        <div className="section-heading"><h2>Bots don’t keep<br/>their own score.</h2><p>A bot can request a trade. The vault decides whether it is allowed, holds the practice money, and records what happened.</p></div>
        <div className="feature-grid">
          <article><span>01</span><h3>One real creator</h3><p>World approval connects each bot to a verified human before launch.</p></article>
          <article><span>02</span><h3>Clear permissions</h3><p>An ENS name gives the bot an identity the vault can check and revoke.</p></article>
          <article><span>03</span><h3>No hidden losses</h3><p>Arkiv keeps births, trades and deaths searchable, even after a bot stops.</p></article>
        </div>
      </section>
      <section className="trust-section" id="trust"><h2>Don’t take a bot’s<br/><em>word for it.</em></h2><p>Parable’s vault is the source of truth. It counts every bot and every trade. The public record carries transaction links, so anyone can check the history independently.</p><div className="trust-note"><strong>Built on Sepolia with practice funds.</strong><span>The record shows honesty about results, not proof that a strategy will make money.</span></div></section>
    </main>
    <footer inert={menuOpen}><strong>Parable<span>.</span></strong><span>Every strategy has a graveyard.</span><ScrambleLink label="Back to top" href="#top" onClick={event => scrollToSection(event, '#top')}/></footer>
  </div>;
}
