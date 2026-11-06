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
  document.documentElement.dataset.theme = 'dark';
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
    'button[aria-label="Switch to light mode"]',
  );
  expect(button).not.toBeNull();
  await act(async () => button!.click());
  expect(document.documentElement.dataset.theme).toBe('light');
  expect(saved.get('parable-theme')).toBe('light');

  await act(async () => root.unmount());
});

test('renders demo-first section order, collapsed simulation arena, and filters compare brains to launched > 0', async () => {
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
      : url === '/api/manager' ? { enabled: true, mind: 'gemini:gemini-3.5-flash-lite', bots: [5], decisions: [] }
      : url.startsWith('/api/graveyard/') ? [{ bot_id: 2, cause: 'loss_limit', final_equity_usd: 89_000_000, start_cash_usd: 100_000_000, pnl_bps: -1100, lifetime_s: 600, tx_hash: '0xdead', ens_name: 'bot-2.parable.eth', brain: 'rule', tx_url: 'https://sepolia.etherscan.io/tx/0xdead' }]
      : url.startsWith('/api/report?') ? { subject: '0xcreator', launched: 3, alive: 1, dead: 2, profitable: 1, worst_pnl_bps: -1100, avg_pnl_bps: -200, vault_count_matches: true }
      : [];
    return { ok: true, json: async () => body };
  }));
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<App />));

  const ids = Array.from(host.querySelectorAll('main > section, main > .proof-bar'))
    .map(el => el.id || el.className);
  expect(ids).toEqual(['proof-bar', 'hero', 'launch', 'live', 'graveyard', 'proof', 'extras', 'how']);
  expect(host.textContent).toContain('SIMULATION, not the real vault');
  expect(host.querySelector('.arena-body')).toBeNull();
  expect(host.textContent).toContain('Hit loss limit');
  expect(host.textContent).toContain('Simple rule (no AI)');
  expect(host.textContent).not.toContain('claude');

  await act(async () => root.unmount());
});
