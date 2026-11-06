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
