// This checks that theme switching works when the browser lacks View Transitions.
// The fallback matters on older browsers and when motion is disabled.
// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = '';
  document.documentElement.dataset.theme = 'light';
});

test('switches theme immediately without View Transitions', async () => {
  const saved = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
  });
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  Object.defineProperty(document, 'startViewTransition', {
    configurable: true,
    value: undefined,
  });
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<App />));

  const button = document.querySelector<HTMLButtonElement>(
    'button[aria-label="Switch to dark mode"]',
  );
  expect(button).not.toBeNull();
  await act(async () => button!.click());
  expect(document.documentElement.dataset.theme).toBe('dark');
  expect(saved.get('parable-theme')).toBe('dark');

  await act(async () => root.unmount());
});

test('renders sections in demo order, plain words, no emoji, and only launched brains', async () => {
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => (key === 'parable.creator' ? '0xcreator' : null),
    setItem: () => {},
  });
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const body =
      url === '/api/info' ? { offline: false, explorer: 'https://sepolia.etherscan.io/tx/', vault_address: '0xvault', ens_parent: 'parable.eth', arkiv_writer: '0xarkiv', arkiv_explorer: 'https://rabdi.explorer.arkiv.network', ens_app: 'https://sepolia.app.ens.domains/', strategies: ['momentum'], default_creator: '0xcreator', eth_price_usd: 2236.46 }
      : url === '/api/brains' ? [{ brain: 'rule', available: true }]
      : url === '/api/report/brains' ? [
          { brain: 'rule', available: true, launched: 3, alive: 0, dead: 3, profitable: 1, avg_pnl_bps: -200, worst_pnl_bps: -1000 },
          { brain: 'claude', available: false, launched: 0, alive: 0, dead: 0, profitable: 0, avg_pnl_bps: 0, worst_pnl_bps: 0 },
        ]
      : url === '/api/swarm' ? { phase: 'idle', plan: null, born: 0, total: 0, next_check_in: null, bots: [], decisions: [] }
      : url === '/api/series' ? { every_s: 10, prices: [], bots: [] }
      : url.startsWith('/api/graveyard/') ? [{ bot_id: 2, cause: 'loss_limit', final_equity_usd: 89_000_000, start_cash_usd: 100_000_000, pnl_bps: -1100, lifetime_s: 600, tx_hash: '0xdead', ens_name: 'bot-2.parable.eth', brain: 'rule', tx_url: 'https://sepolia.etherscan.io/tx/0xdead' }]
      : url.startsWith('/api/report?') ? { subject: '0xcreator', launched: 3, alive: 1, dead: 2, profitable: 1, worst_pnl_bps: -1100, avg_pnl_bps: -200, vault_count_matches: true }
      : [];
    return { ok: true, json: async () => body };
  }));
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<App />));

  const ids = Array.from(host.querySelectorAll('main > section')).map(el => el.id);
  expect(ids).toEqual(['hero', 'launch', 'live', 'register', 'cheat', 'swarm', 'bench', 'how']);
  const text = host.textContent || '';
  expect(text).toContain('Launch a');  // the sentence form
  expect(text).toContain('Lost too much, the vault ended it');
  expect(text).toContain('Practice arena');
  expect(text).not.toContain('Claude');  // brains with no launches are hidden from the comparison
  expect(text).not.toMatch(/LIVE ·|SIMULATION|proof/i);  // no shouting tags
  expect(text).not.toMatch(/\p{Extended_Pictographic}/u);  // our own icons, never emoji
  expect(host.querySelector('.register .struck')?.textContent).toBe('bot-2.parable.eth');  // dead names struck through
  await act(async () => root.unmount());
});
