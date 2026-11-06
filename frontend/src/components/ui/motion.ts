// Small motion helpers: fade sections in as they scroll into view, and a soft ring that follows the mouse.
// Both switch off for people who ask their system for reduced motion, and the ring only runs with a real mouse.
import { useEffect } from 'react';

const calm = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** Marks every [data-reveal] element with data-in the first time it scrolls into view, including elements
 *  added later (new bots, new graves). An attribute, not a class: React rewrites className and would wipe a class. */
export function useReveal() {
  useEffect(() => {
    const pending = () => Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]:not([data-in])'));
    if (calm() || typeof IntersectionObserver === 'undefined') {
      const showAll = () => pending().forEach(el => { el.dataset.in = ''; });
      showAll();
      const added = typeof MutationObserver === 'undefined' ? null : new MutationObserver(showAll);
      added?.observe(document.body, { childList: true, subtree: true });
      return () => added?.disconnect();
    }
    const seen = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { (entry.target as HTMLElement).dataset.in = ''; seen.unobserve(entry.target); }
    }), { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    const watch = () => pending().forEach(el => seen.observe(el));  // observing the same element twice is harmless
    watch();
    const added = new MutationObserver(watch);
    added.observe(document.body, { childList: true, subtree: true });
    return () => { seen.disconnect(); added.disconnect(); };
  }, []);
}

/** A ring that trails the mouse and grows over anything clickable. */
export function useCursorRing() {
  useEffect(() => {
    if (calm() || !window.matchMedia?.('(pointer: fine)').matches) return;
    const ring = document.createElement('div');
    ring.className = 'cursor-ring';
    document.body.append(ring);
    let x = -100, y = -100, rx = -100, ry = -100, frame = 0;
    const move = (e: PointerEvent) => {
      x = e.clientX; y = e.clientY;
      const hot = (e.target as Element | null)?.closest?.('a, button, [role="option"], input, .grave');
      ring.classList.toggle('hot', Boolean(hot));
    };
    const tick = () => {
      rx += (x - rx) * 0.2; ry += (y - ry) * 0.2;  // ease toward the pointer so it trails a little
      ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
      frame = requestAnimationFrame(tick);
    };
    const hide = () => ring.classList.add('gone');
    const show = () => ring.classList.remove('gone');
    window.addEventListener('pointermove', move);
    document.addEventListener('pointerleave', hide);
    document.addEventListener('pointerenter', show);
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame); ring.remove();
      window.removeEventListener('pointermove', move);
      document.removeEventListener('pointerleave', hide);
      document.removeEventListener('pointerenter', show);
    };
  }, []);
}
