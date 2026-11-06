// "Approve with: World ID (scan) | Demo (no phone)". Demo approval skips the human check, so every bot it
// launches is marked "demo" on the public register and never counts as human-verified.
import type { ApprovalMode } from '../../dashboard/api';

export function ApprovalSwitch({ mode, onChange }: { mode: ApprovalMode; onChange: (m: ApprovalMode) => void }) {
  return <div className="actions">
    <span className="mono muted" style={{ fontSize: 13 }}>Approve with</span>
    <div className="toggle" role="group" aria-label="How to approve">
      <button type="button" aria-pressed={mode === 'world'} onClick={() => onChange('world')}>World ID · scan</button>
      <button type="button" aria-pressed={mode === 'demo'} onClick={() => onChange('demo')}>Demo · no phone</button>
    </div>
    <span className="mono muted" style={{ fontSize: 12 }}>{mode === 'demo' ? 'No human check: the bot is marked “demo” on the register.' : 'One real person, checked by World ID.'}</span>
  </div>;
}
