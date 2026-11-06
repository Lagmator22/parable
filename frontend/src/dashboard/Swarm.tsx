import { useState } from 'react';
import { ScrambleButton } from '../components/ui/ScrambleButton';
import { brainName, post, type Manager } from './api';

export function Swarm({ manager, error, onUpdate }: { manager: Manager | null; error: string; onUpdate: (value: Manager) => void }) {
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState('');
  async function start() {
    setRunning(true); setActionError('');
    try { onUpdate(await post<Manager>('/api/manager/start', { bots: 3, minutes: 15 })); }
    catch (err) { setActionError(err instanceof Error ? err.message : 'Could not run the swarm pass.'); }
    finally { setRunning(false); }
  }
  return <section className="app-section" id="swarm"><div className="app-heading"><div><h2>AI Swarm Manager</h2><p>One manager audits the worker bots and records every decision.</p></div><span className="section-number">03</span></div>
    <div className="app-panel swarm-panel">
      <div className="swarm-summary"><div><span>Manager mind</span><strong>{manager?.mind ? brainName(manager.mind) : 'Connecting'}</strong></div><div><span>Audited bots</span><strong>{manager?.bots?.length ? manager.bots.map(id => `#${id}`).join(', ') : 'None yet'}</strong></div><ScrambleButton className="solid-action" label={running ? 'Running pass…' : 'Audit / Run Swarm Pass'} disabled={running || manager?.enabled === false} onClick={() => void start()}/></div>
      {(error || actionError) && <div className="status-message" role="status">{actionError || error}</div>}
      <h3>Decision feed</h3>
      {!manager?.decisions?.length ? <p className="swarm-empty">No decisions recorded yet. Run a pass to see the manager's audit.</p> : <div className="decision-list">{manager.decisions.map((decision, index) => <div className="decision-row" key={`${decision.at}-${decision.bot_id}-${index}`}><span className={`decision-action action-${decision.action}`}>{decision.action}</span><div><strong>{decision.bot_id == null ? 'Swarm' : `Bot #${decision.bot_id}`}</strong><p>{decision.reason}</p></div><time dateTime={new Date(decision.at * 1000).toISOString()}>{new Date(decision.at * 1000).toLocaleString()}</time></div>)}</div>}
    </div>
  </section>;
}
