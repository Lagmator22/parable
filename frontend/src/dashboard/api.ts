export type Info = { offline: boolean; explorer: string; vault_address: string; ens_parent: string; arkiv_writer: string; arkiv_explorer: string; ens_app: string; strategies: string[]; default_creator: string; eth_price_usd: number | null };
export type Brain = { brain: string; available: boolean };
export type Rules = { strategy: string; brain: string; start_cash_usd: number; max_trade_usd: number; max_loss_bps: number; lease_seconds: number };
export type Bot = { bot_id: number; bot_address: string; creator_id: string; ens_name: string; strategy: string; status: string; born_at: number; born_tx: string; rules: Rules; code_hash: string; equity_usd: number | null; pnl_bps: number | null; tx_url: string | null };
export type Event = { bot_id: number; kind: string; at: number; tx_hash: string | null; data: Record<string, unknown> };
export type Grave = { bot_id: number; cause: string; final_equity_usd: number; start_cash_usd: number; pnl_bps: number; lifetime_s: number; tx_hash: string; ens_name: string; brain: string; code_hash?: string; tx_url: string | null; trades?: number; arkiv_url?: string | null };
export type Report = { subject: string; launched: number; alive: number; dead: number; profitable: number; worst_pnl_bps: number; avg_pnl_bps: number; vault_count_matches: boolean };
export type BrainReport = Brain & Omit<Report, 'subject' | 'vault_count_matches'>;
export type Attack = { attack: string; blocked: boolean; reason: string };
export type SwarmBot = { bot_id: number; ens_name: string; brain: string; strategy: string; status: string; equity_usd: number; pnl_bps: number; trades: number; refused: number; left_s: number };
export type SwarmDecision = { at: number; action: 'launch' | 'keep' | 'flag' | 'stop'; bot_id: number | null; reason: string; by: string };
export type Swarm = { phase: 'idle' | 'waiting' | 'launching' | 'running' | 'done'; plan: { mind: string; workers: string[]; bots: number; minutes: number } | null; born: number; total: number; next_check_in: number | null; bots: SwarmBot[]; decisions: SwarmDecision[] };
export type SeriesBot = { bot_id: number; ens_name: string; brain: string; strategy: string; swarm: boolean; status: string; points: [number, number, number][] };
export type Series = { every_s: number; prices: [number, number | null, number | null][]; bots: SeriesBot[] };

export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body = await response.json().catch(() => ({ detail: `Server error (${response.status})` }));
  if (!response.ok) throw new ApiError(typeof body?.detail === 'string' ? body.detail : `Server error (${response.status})`, response.status);
  return body as T;
}

export function post<T>(url: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  return request<T>(url, { method: 'POST', headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...headers }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}

export function getCreator(): string {
  try { return localStorage.getItem('parable.creator') || localStorage.getItem('creator') || ''; } catch { return ''; }
}
export function saveCreator(value: string): void {
  try { localStorage.setItem('parable.creator', value); localStorage.setItem('creator', value); } catch { /* private browsing */ }
}
export function getOwner(id: number): string {
  try { return JSON.parse(localStorage.getItem('owners') || '{}')[String(id)] || ''; } catch { return ''; }
}
export function saveOwner(id: number, token: string): void {
  try {
    const owners = JSON.parse(localStorage.getItem('owners') || '{}');
    localStorage.setItem('owners', JSON.stringify({ ...owners, [String(id)]: token }));
  } catch { /* private browsing */ }
}

export const usd = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value / 1_000_000);
// Basis points to a percent with one decimal (1 bps = 0.01%). Anything that rounds to zero shows as plain 0.0%.
export const pct = (value: number | null | undefined) => {
  if (value == null) return '—';
  const rounded = Math.round(value / 10) / 10;
  return rounded === 0 ? '0.0%' : `${rounded > 0 ? '+' : ''}${rounded.toFixed(1)}%`;
};
/** 'up' or 'down' for coloring a return; tiny moves that show as 0.0% get no color. */
export const trend = (bps: number | null | undefined) => Math.round((bps || 0) / 10) > 0 ? 'up' : Math.round((bps || 0) / 10) < 0 ? 'down' : '';
// "gemini:gemini-3.5-flash-lite" -> "Gemini 3.5 Flash-Lite", "claude:claude-opus-5-5" -> "Claude Opus 5.5".
export const brainName = (value: string): string => {
  if (value === 'rule') return 'Simple rule (no AI)';
  if (value === 'unknown') return 'not recorded';
  if (value.startsWith('jev:')) return `Jev · ${brainName(value.slice(4))}`;  // Jev scores buy/sell/hold instead of writing text
  const model = value.includes(':') ? value.split(':')[1] : value;
  const words = model.replace(/-it$/, '').split('-').map(w => /^\d/.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1));
  const out: string[] = [];
  words.forEach(w => { const prev = out[out.length - 1]; if (prev && /^\d+$/.test(prev) && /^\d+$/.test(w)) out[out.length - 1] = `${prev}.${w}`; else out.push(w); });
  return out.join(' ').replace(/Flash Lite/, 'Flash-Lite').replace(/ (\d+)b\b/i, ' $1B').replace(/ A\d+b\b/i, '');
};
export const causeName = (value: string) => ({ expired: 'Its time ran out', killed: 'Stopped by its creator', loss_limit: 'Lost too much, the vault ended it' })[value as 'expired' | 'killed' | 'loss_limit'] || value;
// What each vault refusal means, in one plain sentence.
const vaultErrors: Record<string, string> = {
  OverTradeLimit: 'that trade is bigger than the bot is allowed.', NotBot: 'this wallet isn’t a registered bot.', BadgeInvalid: 'the bot’s name tag is no longer valid.',
  StalePrice: 'the price is too old to trade on.', NotOverLimit: 'the bot hasn’t lost enough to be stopped.', CreatorIdentityMismatch: 'this person already has a different wallet.',
  NotAlive: 'this bot has already stopped.', Expired: 'this bot’s time is up.', NotExpired: 'this bot still has time left.', InsufficientBalance: 'the bot doesn’t have that much.',
  Unauthorized: 'only the creator can do that.', BotOutOfGas: 'the bot has no test ETH left for fees.', UnknownError: 'the vault refused.',
};
export const explain = (reason: string) => {
  const text = vaultErrors[reason];
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : reason;
};
