// This gives links and buttons the same readable text-scramble interaction.
// It restores the real label on completion and respects reduced-motion settings.
import { useEffect, useRef, useState } from 'react';
import type { ButtonHTMLAttributes, AnchorHTMLAttributes } from 'react';

const glyphs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

function useScramble(label: string) {
  const [text, setText] = useState(label);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => { setText(label); return () => window.clearInterval(timer.current); }, [label]);
  function start() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    window.clearInterval(timer.current);
    let step = 0;
    timer.current = window.setInterval(() => {
      step += 1;
      setText([...label].map((char, index) => char === ' ' || index < step / 2 ? char : glyphs[Math.floor(Math.random() * glyphs.length)]).join(''));
      if (step >= label.length * 2) { window.clearInterval(timer.current); setText(label); }
    }, 24);
  }
  return { text, start };
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { label: string; arrow?: boolean };
export function ScrambleLink({ label, arrow, className = '', ...props }: LinkProps) {
  const { text, start } = useScramble(label);
  return <a {...props} className={`scramble ${className}`} onMouseEnter={start} onFocus={start} onTouchStart={start} aria-label={label}><span className="scramble-text" aria-hidden="true">{text}</span>{arrow && <span className="scramble-arrow" aria-hidden="true">↗</span>}</a>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { label: string; arrow?: boolean };
export function ScrambleButton({ label, arrow, className = '', ...props }: ButtonProps) {
  const { text, start } = useScramble(label);
  return <button {...props} className={`scramble ${className}`} onMouseEnter={start} onFocus={start} onTouchStart={start} aria-label={label}><span className="scramble-text" aria-hidden="true">{text}</span>{arrow && <span className="scramble-arrow" aria-hidden="true">↗</span>}</button>;
}
