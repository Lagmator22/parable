// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { ApiError, pct, request, usd } from './api';

afterEach(() => vi.unstubAllGlobals());

test('converts contract units to readable money and percentages', () => {
  expect(usd(100_000_000)).toBe('$100.00');
  expect(usd(null)).toBe('Unavailable');
  expect(pct(-150)).toBe('-1.5%');
});

test('shows a safe error when a server returns HTML', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: () => Promise.reject(new Error('HTML response')) }));
  await expect(request('/api/report/brains')).rejects.toEqual(new ApiError('Server error (503)', 503));
});
