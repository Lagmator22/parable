// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, test, vi } from 'vitest';
import { useDashboard } from './useDashboard';

afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });

test('loads the public creator in a fresh browser and keeps a saved creator', async () => {
  const storage = new Map<string, string>();
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) });
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(url);
    const body = url === '/api/info' ? { default_creator: '0xpublic' } : url === '/api/manager' ? { enabled: true, mind: 'rule', bots: [], decisions: [] } : [];
    return { ok: true, json: async () => body };
  }));
  function Probe() { const dashboard = useDashboard(); return <span>{dashboard.creator}</span>; }
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  await act(async () => { root.render(<Probe />); });
  expect(host.textContent).toBe('0xpublic');
  expect(storage.get('parable.creator')).toBe('0xpublic');
  expect(calls.some(url => url.includes('creator=0xpublic'))).toBe(true);
  await act(async () => root.unmount());

  storage.set('parable.creator', '0xmine');
  const next = createRoot(host);
  await act(async () => { next.render(<Probe />); });
  expect(host.textContent).toBe('0xmine');
  await act(async () => next.unmount());
});
