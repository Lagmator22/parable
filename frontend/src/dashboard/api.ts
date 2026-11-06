export type Info = { offline: boolean; explorer: string; vault_address: string; ens_parent: string; arkiv_writer: string; arkiv_explorer: string; ens_app: string; strategies: string[]; default_creator: string; eth_price_usd: number | null };
export type Brain = { brain: string; available: boolean };
export type Rules = { strategy: string; brain: string; start_cash_usd: number; max_trade_usd: number; max_loss_bps: number; lease_seconds: number };
export type Bot = { bot_id: number; bot_address: string; creator_id: string; ens_name: string; strategy: string; status: string; born_at: number; born_tx: string; rules: Rules; code_hash: string; equity_usd: number | null; pnl_bps: number | null; tx_url: string | null };
export type Event = { bot_id: number; kind: string; at: number; tx_hash: string | null; data: Record<string, unknown> };
export type Grave = { bot_id: number; cause: string; final_equity_usd: number; start_cash_usd: number; pnl_bps: number; lifetime_s: number; tx_hash: string; ens_name: string; brain: string; code_hash?: string; tx_url: string | null };
export type Report = { subject: string; launched: number; alive: number; dead: number; profitable: number; worst_pnl_bps: number; avg_pnl_bps: number; vault_count_matches: boolean };
export type BrainReport = Brain & Omit<Report, 'subject' | 'vault_count_matches'>;
export type Attack = { attack: string; blocked: boolean; reason: string };
export type ManagerDecision = { at: number; action: 'launch' | 'keep' | 'flag' | 'kill'; bot_id: number | null; reason: string };
export type Manager = { enabled: boolean; mind: string; bots: number[]; decisions: ManagerDecision[] };

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

export const usd = (value: number | null | undefined) => value == null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value / 1_000_000);
export const pct = (value: number | null | undefined) => value == null ? 'Unavailable' : `${value > 0 ? '+' : ''}${(value / 100).toFixed(1)}%`;
export const brainName = (value: string) => value === 'rule' ? 'Simple rule (no AI)' : value.startsWith('gemini:') || value.startsWith('gemma:') ? value.split(':')[1] : value;
export const causeName = (value: string) => ({ expired: 'Lease ran out', killed: 'Stopped by creator', loss_limit: 'Hit its loss limit (vault killed it)' })[value as 'expired' | 'killed' | 'loss_limit'] || value;
const vaultErrors: Record<string, string> = {
  OverTradeLimit: 'This trade exceeds the bot’s limit.', NotBot: 'This wallet is not a registered bot.', BadgeInvalid: 'The bot’s identity badge is invalid.', StalePrice: 'The price is too old.', NotOverLimit: 'The loss limit has not been reached.', CreatorIdentityMismatch: 'This identity belongs to a different creator.', NotAlive: 'This bot is no longer active.', Expired: 'This bot’s lease has ended.', NotExpired: 'This bot’s lease is still active.', InsufficientBalance: 'The vault has insufficient funds.', Unauthorized: 'This action is not authorized.', UnknownError: 'The vault rejected the action.'
};
export const explain = (reason: string) => vaultErrors[reason] ? `${reason}: ${vaultErrors[reason]}` : reason;
