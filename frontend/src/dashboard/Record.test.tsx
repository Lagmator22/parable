// Exercises the public register with enough graves to require several pages.
// Checks that older records stay reachable as the shared data refreshes.
// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test, vi } from 'vitest';
import { Register } from './Record';
import type { Grave } from './api';

test('shows ten graves at a time and keeps the oldest records reachable', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const host = document.createElement('div');
  const root = createRoot(host);
  const graves: Grave[] = Array.from({ length: 103 }, (_, index) => ({
    bot_id: index + 1, ens_name: `bot-${index + 1}.parable.eth`, brain: 'rule', cause: 'expired',
    final_equity_usd: 100, start_cash_usd: 100, pnl_bps: 0, lifetime_s: 600,
    tx_hash: '0xdead', tx_url: null, arkiv_url: `https://example.test/entity/${index + 1}`,
  }));
  const render = (records: Grave[]) => act(async () => root.render(
    <Register graves={records} report={null} recordError=""/>,
  ));
  const ids = () => [...host.querySelectorAll('.register .row:not(.head)')]
    .map(row => Number(row.firstElementChild?.textContent));
  const button = (label: string) => [...host.querySelectorAll<HTMLButtonElement>('button')]
    .find(el => (el.getAttribute('aria-label') ?? el.textContent) === label)!;

  try {
    await render(graves);
    expect(ids()).toEqual([103, 102, 101, 100, 99, 98, 97, 96, 95, 94]);
    expect(button('Previous').disabled).toBe(true);
    await act(async () => button('Next').click());
    expect(ids()).toEqual([93, 92, 91, 90, 89, 88, 87, 86, 85, 84]);
    expect(button('Page 2').getAttribute('aria-current')).toBe('page');
    await render([...graves]);
    expect(ids()[0]).toBe(93);
    await act(async () => button('Page 11').click());
    expect(ids()).toEqual([3, 2, 1]);
    expect(host.querySelector('[role="status"]')?.textContent).toBe('Showing 101–103 of 103 bots');
    expect(host.querySelector('a[href="https://example.test/entity/1"]')).not.toBeNull();
    expect(button('Next').disabled).toBe(true);

    await render(graves.slice(0, 11));
    expect(ids()).toEqual([1]);
    expect(button('Page 2').getAttribute('aria-current')).toBe('page');
    await render(graves.slice(0, 10));
    expect(ids()).toHaveLength(10);
    expect(host.querySelector('[aria-label="Graveyard pages"]')).toBeNull();
  } finally {
    await act(async () => root.unmount());
    vi.unstubAllGlobals();
  }
});
