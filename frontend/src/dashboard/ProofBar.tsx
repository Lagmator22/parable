import type { Info } from './api';

const short = (value: string) => value ? `${value.slice(0, 8)}…${value.slice(-4)}` : 'Awaiting data';

export function ProofBar({ info, creator }: { info: Info | null; creator: string }) {
  return <div className="proof-bar" aria-label="Live sponsor proofs">
    <div className="proof-item"><span>World ID</span><strong>Verified Human Pass</strong><small>{short(creator || info?.default_creator || '')}</small></div>
    <div className="proof-item"><span>ENSv2</span><strong>Soulbound Badge Oracle</strong>{info?.ens_app ? <a href={info.ens_app} target="_blank" rel="noreferrer">{info.ens_parent || 'parable.eth'} ↗</a> : <small>Awaiting ENS</small>}</div>
    <div className="proof-item"><span>Chainlink ETH/USD</span><strong>{info?.eth_price_usd == null ? 'Price unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(info.eth_price_usd)}</strong><small>Sepolia oracle</small></div>
    <div className="proof-item"><span>Arkiv Rabdi</span><strong>Public Graveyard DB</strong>{info?.arkiv_explorer ? <a href={info.arkiv_explorer} target="_blank" rel="noreferrer">Explorer ↗</a> : <small>Awaiting Arkiv</small>}<small title={info?.arkiv_writer}>{short(info?.arkiv_writer || '')}</small></div>
  </div>;
}
