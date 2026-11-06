// The whole page, top to bottom: headline, launch, live bots, graveyard, try to cheat, more, how it works.
// Data comes from useDashboard (the engine's /api routes). Motion is in components/ui/motion.ts.
import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Moon, Sun } from 'lucide-react';
import { LinkButton } from './components/ui/Button';
import { Ledger, Person, Tag, Tomb, Vault } from './components/ui/Glyphs';
import { useCursorRing, useReveal } from './components/ui/motion';
import { Section } from './components/ui/Section';
import { Arena } from './dashboard/Arena';
import { Cheat } from './dashboard/Cheat';
import { Facts } from './dashboard/Facts';
import { Launch } from './dashboard/Launch';
import { Live } from './dashboard/Live';
import { CompareBrains, Graveyard } from './dashboard/Record';
import { Swarm } from './dashboard/Swarm';
import { useDashboard } from './dashboard/useDashboard';

type Theme = 'dark' | 'light';
const nav = [['Launch', '#launch'], ['Live', '#live'], ['Graveyard', '#graveyard'], ['Try to cheat', '#cheat'], ['More', '#more']];
const steps = [
  [Person, 'A person approves the bot', 'World ID makes sure one human is behind each creator.'],
  [Tag, 'The bot gets a name', 'An ENS name like bot-7.parable.eth. It expires, can’t be sold, and can be taken away.'],
  [Vault, 'The vault does the trading', 'The bot only asks. The vault checks the name and the limits, then trades at the Chainlink price.'],
  [Ledger, 'Everything is written down', 'Births, trades, refusals and deaths go to Arkiv. Nobody can delete a dead bot.'],
] as const;

function savedTheme(): Theme {
  try { return localStorage.getItem('parable-theme') === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(savedTheme);
  const [scrolled, setScrolled] = useState(false);
  const d = useDashboard();
  const switching = useRef(false);
  useReveal();
  useCursorRing();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('parable-theme', theme); } catch { /* private browsing */ }
  }, [theme]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // The new theme grows out of the button in a circle (View Transitions); older browsers just switch.
  function toggleTheme(event: React.MouseEvent<HTMLButtonElement>) {
    if (switching.current) return;
    const next = theme === 'dark' ? 'light' : 'dark';
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !document.startViewTransition) { setTheme(next); return; }
    switching.current = true;
    const root = document.documentElement;
    root.style.setProperty('--ripple-x', `${event.clientX}px`);
    root.style.setProperty('--ripple-y', `${event.clientY}px`);
    document.startViewTransition(() => { root.dataset.theme = next; flushSync(() => setTheme(next)); })
      .finished.finally(() => { switching.current = false; });
  }

  const refreshAll = () => { void d.refreshLive(); void d.refreshRecord(); };
  return <div className="shell" id="top">
    <header className={`topbar ${scrolled ? 'scrolled' : ''}`}>
      <a className="brand" href="#top"><Tomb size={20}/>Parable</a>
      <nav aria-label="Sections">{nav.map(([label, href]) => <a key={href} href={href}>{label}</a>)}</nav>
      <button className="theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
        {theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}
      </button>
    </header>
    <main>
      {d.info?.offline && <div className="notice" role="status">Practice mode: this server runs a pretend chain, nothing here is on Sepolia.</div>}
      {d.error && <div className="notice" role="status">Can’t reach the server right now: {d.error}</div>}
      <section className="hero" id="hero">
        <h1 data-reveal>Every trading strategy<br/>has a <em>graveyard.</em></h1>
        <p className="lede" data-reveal>Bots on Parable never hold the money and never write their own history. A vault does both, so the failures stay visible.</p>
        <div className="hero-actions" data-reveal>
          <LinkButton variant="solid" href="#launch">Launch a bot</LinkButton>
          <LinkButton href="#graveyard" icon={<Tomb size={18}/>}>See the graveyard</LinkButton>
        </div>
        {d.report && <p className="hero-count" data-reveal>
          <span className="tiny-graves" aria-hidden="true">{Array.from({ length: Math.min(d.report.dead, 24) }, (_, i) => <Tomb key={i} size={16} style={{ '--i': i } as React.CSSProperties}/>)}</span>
          {d.report.launched} launched so far · {d.report.dead} in the graveyard
        </p>}
        <Facts info={d.info}/>
      </section>
      <Launch info={d.info} brains={d.brains} onBorn={creator => { d.setCreator(creator); refreshAll(); }}/>
      <Live bots={d.bots} creator={d.creator} botEvents={d.botEvents} info={d.info} onRefresh={refreshAll}/>
      <Graveyard graves={d.graves} report={d.report} creator={d.creator} recordError={d.recordError}/>
      <Cheat bots={d.bots}/>
      <Section id="more" n="05" title="More" intro="Extra tools built on the same record. Open the ones you want.">
        <div className="more-stack">
          <Swarm manager={d.manager} error={d.managerError} onUpdate={d.setManager}/>
          <CompareBrains comparison={d.comparison} recordError={d.recordError}/>
          <Arena/>
        </div>
      </Section>
      <section className="section how" id="how">
        <h2 data-reveal>How it works</h2>
        <ol className="how-steps">
          {steps.map(([Icon, title, text], i) => <li key={title} data-reveal style={{ '--i': i } as React.CSSProperties}>
            <Icon size={26}/><h3>{title}</h3><p>{text}</p>
          </li>)}
        </ol>
      </section>
    </main>
    <footer><span className="brand"><Tomb size={18}/>Parable</span><span>Built at ETHGlobal Mumbai on Sepolia, World ID, ENS and Arkiv.</span><a href="#top">Back to top</a></footer>
  </div>;
}
