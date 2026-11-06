// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { ApiError, brainName, explain, pct, request, trend, usd } from './api';

afterEach(() => vi.unstubAllGlobals());

test('converts contract units to readable money and percentages', () => {
  expect(usd(100_000_000)).toBe('$100.00');
  expect(usd(null)).toBe('—');
  expect(pct(-150)).toBe('-1.5%');
  expect(pct(-1)).toBe('0.0%');  // a tiny loss that rounds to zero is not shown as "-0.0%"
  expect(trend(-1)).toBe('');
  expect(trend(-150)).toBe('down');
});

test('vault refusals read as plain sentences', () => {
  expect(explain('OverTradeLimit')).toBe('That trade is bigger than the bot is allowed.');
  expect(explain('SomethingNew')).toBe('SomethingNew');
});

test('shows a safe error when a server returns HTML', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: () => Promise.reject(new Error('HTML response')) }));
  await expect(request('/api/report/brains')).rejects.toEqual(new ApiError('Server error (503)', 503));
});

test('model ids read as product names', () => {
  expect(brainName('gemini:gemini-3.5-flash-lite')).toBe('Gemini 3.5 Flash-Lite');
  expect(brainName('claude:claude-opus-5-5')).toBe('Claude Opus 5.5');
  expect(brainName('gemma:gemma-4-26b-a4b-it')).toBe('Gemma 4 26B');
  expect(brainName('gemma:gemma-4-31b-it')).toBe('Gemma 4 31B');
  expect(brainName('rule')).toBe('Simple rule (no AI)');
  expect(brainName('jev:gemma-4-31b-it')).toBe('Jev · Gemma 4 31B');
});
