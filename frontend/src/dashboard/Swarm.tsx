// Under "More": an AI manager that looks over every bot's history and decides keep, flag or stop.
// It has no special powers: it can only do what a creator can do, and the vault still checks everything.
import { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Brain } from '../components/ui/Glyphs';
import { brainName, post, type Manager } from './api';

const verb = { launch: 'Launched', keep: 'Kept', flag: 'Flagged', kill: 'Stopped' } as const;

export function Swarm({ manager, error, onUpdate }: { manager: Manager | null; error: string; onUpdate: (value: Manager) => void }) {
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState('');
  async function start() {
    setRunning(true); setActionError('');
    try { onUpdate(await post<Manager>('/api/manager/start', { bots: 3, minutes: 15 })); }
    catch (err) { setActionError(err instanceof Error ? err.message : 'Could not run the manager.'); }
    finally { setRunning(false); }
  }
  return <details className="panel extra" id="swarm">
    <summary><div><h3>AI manager</h3><p>One AI reads every bot’s history and decides which to keep, flag or stop.</p></div></summary>
    <div className="swarm-bar">
      <span><Brain size={16}/>Thinking with {manager?.mind ? brainName(manager.mind) : '…'}</span>
      <Button variant="solid" disabled={running || manager?.enabled === false} onClick={() => void start()}>{running ? 'Looking…' : 'Run a check now'}</Button>
    </div>
    {(error || actionError) && <p className="note">{actionError || error}</p>}
    {!manager?.decisions?.length ? <p className="quiet">No decisions yet.</p>
      : <ol className="decisions">{manager.decisions.slice(0, 6).map((dec, i) => <li key={`${dec.at}-${dec.bot_id}-${i}`} className={`dec dec-${dec.action}`}>
        <strong>{verb[dec.action] ?? dec.action}</strong>
        <span>{dec.bot_id == null ? '' : `Bot ${dec.bot_id}: `}{dec.reason}</span>
        <time>{new Date(dec.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time>
      </li>)}</ol>}
  </details>;
}
