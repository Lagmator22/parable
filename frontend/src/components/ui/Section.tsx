// One numbered page section: a small number, a short title, one line of explanation, then its content.
import type { ReactNode } from 'react';

export function Section({ id, n, title, intro, children }: { id: string; n: string; title: string; intro: string; children: ReactNode }) {
  return <section className="section" id={id}>
    <header className="section-head" data-reveal>
      <span className="section-n">{n}</span>
      <div><h2>{title}</h2><p>{intro}</p></div>
    </header>
    {children}
  </section>;
}
