// Four plain facts under the headline: who approves bots, where names live, the price the vault uses,
// and where the history is kept. Each links to the page where anyone can look it up.
import { Ledger, Person, Price, Tag } from '../components/ui/Glyphs';
import type { Info } from './api';

const money = (n: number | null | undefined) => n == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

export function Facts({ info }: { info: Info | null }) {
  const address = info?.explorer?.replace('/tx/', '/address/');
  const rows = [
    { Icon: Person, label: 'Approved by', value: 'a person, via World ID', href: null },
    { Icon: Tag, label: 'Bot names', value: `*.${info?.ens_parent || 'parable.eth'}`, href: info?.ens_app ? `${info.ens_app}${info.ens_parent}` : null },
    { Icon: Price, label: 'ETH price used', value: money(info?.eth_price_usd), href: address && info?.vault_address ? `${address}${info.vault_address}` : null },
    { Icon: Ledger, label: 'History kept on', value: 'Arkiv', href: info?.arkiv_explorer && info.arkiv_writer ? `${info.arkiv_explorer}/address/${info.arkiv_writer}` : null },
  ];
  return <ul className="facts" data-reveal>
    {rows.map(({ Icon, label, value, href }) => <li key={label}>
      <Icon size={20}/>
      <span>{label}</span>
      {href ? <a href={href} target="_blank" rel="noreferrer">{value}</a> : <strong>{value}</strong>}
    </li>)}
  </ul>;
}
