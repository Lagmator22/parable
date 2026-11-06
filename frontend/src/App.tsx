// This simple landing page explains Parable and links to its real sections.
// The full application views will be connected to the Python engine later.
import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Moon, Sun, X } from 'lucide-react';
import { ScrambleButton, ScrambleLink } from './components/ui/ScrambleButton';

type Theme = 'dark' | 'light';
const nav = [{ label: 'Home', href: '#top' }, { label: 'How it works', href: '#how' }, { label: 'Why trust it', href: '#trust' }];

function savedTheme(): Theme {
  try { return localStorage.getItem('parable-theme') === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(savedTheme);
  const [menuOpen, setMenuOpen] = useState(false);
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
        <ScrambleButton label={menuOpen ? 'Close' : 'Menu'} onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen} aria-controls="page-menu" />
      </div>
    </header>
    <nav id="page-menu" className={`menu-overlay ${menuOpen ? 'open' : ''}`} aria-hidden={!menuOpen}>
      <div className="menu-head"><span>Navigate</span><button className="close-menu" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={26}/></button></div>
      <div className="menu-links">{nav.map((link, index) => <ScrambleLink key={link.href} label={`${String(index + 1).padStart(2, '0')}  ${link.label}`} href={link.href} onClick={() => setMenuOpen(false)} tabIndex={menuOpen ? 0 : -1} arrow />)}</div>
      <p>Every strategy has a graveyard. Now you can see it.</p>
    </nav>
    <main inert={menuOpen}>
      <section className="hero">
        <div className="hero-copy">
          <h1>Every bot.<br/>Every trade.<br/><span>Every failure.</span></h1>
          <p>Creators can show you their winners. Parable shows you the whole record, including the bots that died.</p>
          <div className="hero-actions"><ScrambleLink label="See how it works" href="#how" arrow className="main-action"/><ScrambleLink label="Why trust it?" href="#trust"/></div>
        </div>
        <div className="hero-visual" aria-label="Illustration of a bot's public history">
          <h2 className="visual-title">A bot's public history</h2>
          <div className="visual-line"><span>01</span><div><strong>Born</strong><p>Approved by a real person</p></div></div>
          <div className="visual-line"><span>02</span><div><strong>Traded</strong><p>Checked by the vault</p></div></div>
          <div className="visual-line"><span>03</span><div><strong>Died</strong><p>Still visible in the graveyard</p></div></div>
        </div>
      </section>
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
    <footer inert={menuOpen}><strong>Parable<span>.</span></strong><span>Every strategy has a graveyard.</span><ScrambleLink label="Back to top" href="#top"/></footer>
  </div>;
}
