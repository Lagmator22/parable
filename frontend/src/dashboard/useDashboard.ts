import { useCallback, useEffect, useRef, useState } from 'react';
import { getCreator, request, saveCreator, type Bot, type Brain, type BrainReport, type Event, type Grave, type Info, type Manager, type Report } from './api';

export function useDashboard() {
  const [creator, setCreator] = useState('');
  const [info, setInfo] = useState<Info | null>(null);
  const [brains, setBrains] = useState<Brain[]>([]);
  const [bots, setBots] = useState<Bot[]>([]);
  const [latestEvents, setLatestEvents] = useState<Record<number, Event>>({});
  const [manager, setManager] = useState<Manager | null>(null);
  const [managerError, setManagerError] = useState('');
  const [graves, setGraves] = useState<Grave[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [comparison, setComparison] = useState<BrainReport[]>([]);
  const [error, setError] = useState('');
  const [recordError, setRecordError] = useState('');
  const busy = useRef({ live: false, record: false, manager: false });

  useEffect(() => {
    const savedCreator = getCreator();
    if (savedCreator) setCreator(savedCreator);
    Promise.allSettled([request<Info>('/api/info'), request<Brain[]>('/api/brains')]).then(([a, b]) => {
      if (a.status === 'fulfilled') {
        setInfo(a.value);
        if (!savedCreator && a.value.default_creator) {
          saveCreator(a.value.default_creator);
          setCreator(a.value.default_creator);
        }
      } else setError(a.reason instanceof Error ? a.reason.message : 'Cannot reach the engine.');
      if (b.status === 'fulfilled') setBrains(b.value);
    });
  }, []);

  const refreshLive = useCallback(async () => {
    if (!creator || document.hidden || busy.current.live) return;
    busy.current.live = true;
    try {
      const live = await request<Bot[]>(`/api/bots?creator=${encodeURIComponent(creator)}&status=alive`);
      setBots(live);
      const events = await Promise.allSettled(live.map(bot => request<Event[]>(`/api/bots/${bot.bot_id}/events`)));
      const latest: Record<number, Event> = {};
      events.forEach((result, index) => { if (result.status === 'fulfilled' && result.value[0]) latest[live[index].bot_id] = result.value[0]; });
      setLatestEvents(latest);
      setError('');
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not load live bots.'); }
    finally { busy.current.live = false; }
  }, [creator]);

  const refreshManager = useCallback(async () => {
    if (document.hidden || busy.current.manager) return;
    busy.current.manager = true;
    try { setManager(await request<Manager>('/api/manager')); setManagerError(''); }
    catch (err) { setManagerError(err instanceof Error ? err.message : 'Could not load the swarm.'); }
    finally { busy.current.manager = false; }
  }, []);

  const refreshRecord = useCallback(async () => {
    if (document.hidden || busy.current.record) return;
    busy.current.record = true;
    try {
      const results = await Promise.allSettled([
        request<BrainReport[]>('/api/report/brains'),
        ...(creator ? [request<Grave[]>(`/api/graveyard/${encodeURIComponent(creator)}`), request<Report>(`/api/report?creator=${encodeURIComponent(creator)}`)] : []),
      ]);
      if (results[0].status === 'fulfilled') setComparison(results[0].value as BrainReport[]);
      if (creator && results[1]?.status === 'fulfilled') setGraves(results[1].value as Grave[]);
      if (creator && results[2]?.status === 'fulfilled') setReport(results[2].value as Report);
      const rejected = results.find(result => result.status === 'rejected');
      setRecordError(rejected?.status === 'rejected' ? (rejected.reason instanceof Error ? rejected.reason.message : 'Could not load the public record.') : '');
    } finally { busy.current.record = false; }
  }, [creator]);

  useEffect(() => {
    void refreshLive(); void refreshRecord(); void refreshManager();
    const liveTimer = window.setInterval(refreshLive, 5_000);
    const managerTimer = window.setInterval(refreshManager, 5_000);
    const recordTimer = window.setInterval(refreshRecord, 15_000);
    const onVisible = () => { if (!document.hidden) { void refreshLive(); void refreshRecord(); void refreshManager(); } };
    document.addEventListener('visibilitychange', onVisible);
    return () => { window.clearInterval(liveTimer); window.clearInterval(managerTimer); window.clearInterval(recordTimer); document.removeEventListener('visibilitychange', onVisible); };
  }, [refreshLive, refreshRecord, refreshManager]);

  return { creator, setCreator, info, brains, bots, latestEvents, manager, managerError, setManager, graves, report, comparison, error, recordError, refreshLive, refreshRecord, refreshManager };
}
