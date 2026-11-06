import { useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

type Option = { value: string; label: string };
type Props = { label: string; value: string; options: Option[]; onChange: (value: string) => void };

export function SelectMenu({ label, value, options, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLDivElement | null)[]>([]);
  const id = useId();
  const selected = Math.max(0, options.findIndex(option => option.value === value));

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useEffect(() => { if (open) items.current[active]?.focus(); }, [open, active]);

  function show() { setActive(selected); setOpen(true); }
  function choose(index: number) { onChange(options[index].value); setOpen(false); trigger.current?.focus(); }
  function keyDown(event: React.KeyboardEvent) {
    if (!open && ['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) { event.preventDefault(); show(); return; }
    if (!open) return;
    if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
    if (event.key === 'ArrowDown') { event.preventDefault(); setActive(index => (index + 1) % options.length); }
    if (event.key === 'ArrowUp') { event.preventDefault(); setActive(index => (index - 1 + options.length) % options.length); }
    if (event.key === 'Home') { event.preventDefault(); setActive(0); }
    if (event.key === 'End') { event.preventDefault(); setActive(options.length - 1); }
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(active); }
    if (event.key === 'Tab') setOpen(false);
  }

  return <div className="select-field" ref={root} onKeyDown={keyDown}>
    <span id={`${id}-label`}>{label}</span>
    <button ref={trigger} type="button" className="select-trigger" aria-haspopup="listbox" aria-expanded={open} aria-labelledby={`${id}-label ${id}-value`} aria-controls={`${id}-options`} onClick={() => open ? setOpen(false) : show()} disabled={options.length === 0}>
      <span id={`${id}-value`}>{options[selected]?.label || 'Unavailable'}</span><ChevronDown size={19} aria-hidden="true"/>
    </button>
    {open && <div id={`${id}-options`} className="select-options" role="listbox" aria-labelledby={`${id}-label`}>
      {options.map((option, index) => <div key={option.value} ref={node => { items.current[index] = node; }} id={`${id}-option-${index}`} role="option" tabIndex={index === active ? 0 : -1} aria-selected={index === selected} className={`select-option ${index === active ? 'active' : ''}`} onClick={() => choose(index)}>
        <span>{option.label}</span>{index === selected && <Check size={18} aria-hidden="true"/>}
      </div>)}
    </div>}
  </div>;
}
