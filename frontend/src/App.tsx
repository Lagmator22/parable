// This is Parable's public front door and navigation shell.
// It explains the product before sending visitors to the live app sections.
import { useEffect, useRef, useState } from 'react';
import { ArrowDownRight, Moon, Sun, X } from 'lucide-react';
import { ScrambleButton, ScrambleLink } from './components/ui/ScrambleButton';

type Theme = 'dark' | 'light';
const pages = [
  ['01', 'Overview', '#overview'], ['02', 'Launch a bot', '#launch'],
  ['03', 'Live bots', '#live'], ['04', 'Graveyard', '#graveyard'],
  ['05', 'Compare brains', '#compare'], ['06', 'Proof', '#proof'],
];

function initialTheme(): Theme {
  try { return localStorage.getItem('parable-theme') === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}

function Wordmark() {
  const ref = useRef<HTMLDivElement>(null);
  const [pulse, setPulse] = useState(false);
  function move(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    ref.current?.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`);
    ref.current?.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`);
  }
  return <div ref={ref} className={`wordmark-field ${pulse ? 'pulse' : ''}`} onPointerMove={move} onPointerLeave={() => { ref.current?.style.setProperty('--pointer-x', '-500px'); }} onClick={() => { setPulse(false); requestAnimationFrame(() => setPulse(true)); }}>
    <div className="wordmark-grain" aria-hidden="true" />
    <h1 className="wordmark">Parable<span className="wordmark-period">.</span></h1>
    <div className="wordmark-caption"><span>THE PUBLIC RECORD FOR AI TRADING BOTS</span><span>MOVE YOUR CURSOR · CLICK THE WORDMARK</span></div>
  </div>;
}

function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [menuOpen, setMenuOpen] = useState(false);
  const [ripple, setRipple] = useState<{ x: number; y: number; next: Theme } | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('parable-theme', theme); } catch { /* private browsing */ }
  }, [theme]);

  useEffect(() => {
    const update = () => {
      const range = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(range > 0 ? window.scrollY / range : 0);
    };
    update(); window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, []);

  function toggleTheme(event: React.MouseEvent<HTMLButtonElement>) {
    if (ripple) return;
    const next = theme === 'dark' ? 'light' : 'dark';
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setTheme(next); return; }
    setRipple({ x: event.clientX, y: event.clientY, next });
    window.setTimeout(() => { setTheme(next); setRipple(null); }, 620);
  }

  return <div className="site-shell">
    <div className="scroll-progress" style={{ transform: `scaleX(${progress})` }} aria-hidden="true" />
    <header className="site-header">
      <a href="#top" className="brand" aria-label="Parable home">p<span>.</span></a>
      <span className="header-note">A PUBLIC RECORD FOR EVERY BOT</span>
      <div className="header-actions">
        <button className="icon-button theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>{theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}</button>
        <ScrambleButton label={menuOpen ? 'CLOSE' : 'MENU'} onClick={() => setMenuOpen(!menuOpen)} className="menu-trigger" aria-expanded={menuOpen} aria-controls="page-menu" />
      </div>
    </header>

    <nav id="page-menu" className={`menu-overlay ${menuOpen ? 'open' : ''}`} aria-hidden={!menuOpen}>
      <div className="menu-top"><span>EXPLORE PARABLE</span><button className="icon-button" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={20}/></button></div>
      <div className="menu-links">{pages.map(([number, name, href]) => <ScrambleLink key={href} label={`${number}  ${name}`} href={href} onClick={() => setMenuOpen(false)} tabIndex={menuOpen ? 0 : -1} arrow />)}</div>
      <div className="menu-bottom"><span>EVERY STRATEGY HAS A GRAVEYARD.</span><span>SEPOLIA · PRACTICE MONEY</span></div>
    </nav>

    <main id="top">
      <section className="hero" id="overview">
        <div className="hero-kicker"><span className="live-dot"/>TRANSPARENCY FOR AI TRADING</div>
        <Wordmark />
        <div className="hero-bottom"><p>Every trading strategy has a graveyard.<br/><strong>Here, bots can’t lie about theirs.</strong></p><ScrambleLink label="EXPLORE THE RECORD" href="#record" arrow className="hero-link" /></div>
        <a className="scroll-cue" href="#record" aria-label="Scroll to learn more"><ArrowDownRight size={18}/><span>SCROLL TO EXPLORE</span></a>
      </section>

      <section className="story-section" id="record">
        <div className="section-label"><span>01 / THE PROBLEM</span><span>WHAT YOU CANNOT SEE MATTERS</span></div>
        <div className="story-grid"><h2>Winners are easy<br/>to show.<em> Losses aren’t.</em></h2><div><p>A creator can launch twenty trading bots, delete the seventeen that fail, and advertise the lucky three. Parable makes the full record visible before anyone trusts the result.</p><div className="rule-row"><span>01</span><strong>Register before trading</strong><span>NO HIDDEN BOTS</span></div><div className="rule-row"><span>02</span><strong>One human per creator</strong><span>WORLD ID</span></div><div className="rule-row"><span>03</span><strong>The vault keeps score</strong><span>ON-CHAIN PROOF</span></div></div></div>
      </section>

      <section className="portal-section" id="launch"><div className="section-label"><span>02 / THE SYSTEM</span><span>FROM BIRTH TO GRAVEYARD</span></div><h2>Every bot leaves<br/><em>a trail.</em></h2><div className="trail-grid"><article><span>01 / IDENTITY</span><h3>Approved by a human.</h3><p>World approval is required before a bot is born. A denied request creates nothing.</p></article><article><span>02 / PERMISSION</span><h3>Named on ENS.</h3><p>An expiring, revocable badge tells the vault whether a bot may trade.</p></article><article><span>03 / RECORD</span><h3>Written to Arkiv.</h3><p>Births, trades and deaths form a searchable public history. The graveyard stays visible.</p></article></div><ScrambleLink label="EXPLORE THE APP" href="#app" arrow className="primary-action" /></section>

      <section className="app-preview" id="app"><div className="section-label"><span>03 / EXPLORE</span><span>THE LIVE APPLICATION</span></div><div className="app-heading"><h2>The record is<br/><em>open.</em></h2><p>Inspect every outcome, follow the evidence, and test the vault’s rules. Launching uses practice money on Sepolia.</p></div><div className="destination-grid">{pages.slice(1).map(([number, name, href]) => <a key={href} href={href === '#launch' ? '#launch' : href} className="destination"><span>{number} / PARABLE</span><strong>{name}</strong><span className="destination-arrow">↗</span></a>)}</div></section>

      <section className="placeholder-section" id="live"><span>LIVE BOTS</span><h2>Every trade is counted.</h2><p>Live bot cards and event timelines will connect to the Python engine here.</p></section>
      <section className="placeholder-section" id="graveyard"><span>THE GRAVEYARD</span><h2>Failures stay visible.</h2><p>Dead bots, their causes, outcomes and proof will appear here from Arkiv.</p></section>
      <section className="placeholder-section" id="compare"><span>COMPARE BRAINS</span><h2>Compare the full cohort.</h2><p>Every run is included in the report card, not just the winners.</p></section>
      <section className="placeholder-section" id="proof"><span>VERIFY THE RECORD</span><h2>Don’t take our word for it.</h2><p>Follow the vault, ENS identity and Arkiv records to their public sources.</p></section>
    </main>
    <footer><span>PARABLE / ETHGLOBAL MUMBAI 2026</span><ScrambleLink label="BACK TO TOP" href="#top" /><span>BUILT FOR HONEST BOT HISTORIES</span></footer>
    {ripple && <div className="theme-ripple" style={{ '--ripple-x': `${ripple.x}px`, '--ripple-y': `${ripple.y}px`, background: ripple.next === 'light' ? '#e9e1d0' : '#0a0a09' } as React.CSSProperties} aria-hidden="true"/>}
  </div>;
}

export default App;
