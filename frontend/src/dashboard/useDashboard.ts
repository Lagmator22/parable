import { useCallback, useEffect, useRef, useState } from 'react';
import { getCreator, request, saveCreator, type Bot, type Brain, type BrainReport, type Event, type Grave, type Info, type Report, type Series, type Swarm } from './api';

export function useDashboard() {
  const [creator, setCreator] = useState(getCreator);
  const [info, setInfo] = useState<Info | null>(null);
  const [brains, setBrains] = useState<Brain[]>([]);
  const [bots, setBots] = useState<Bot[]>([]);
  const [latestEvents, setLatestEvents] = useState<Record<number, Event>>({});
  const [botEvents, setBotEvents] = useState<Record<number, Event[]>>({});
  const [swarm, setSwarm] = useState<Swarm | null>(null);
  const [series, setSeries] = useState<Series | null>(null);
  const [graves, setGraves] = useState<Grave[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [comparison, setComparison] = useState<BrainReport[]>([]);
  const [error, setError] = useState('');
  const [recordError, setRecordError] = useState('');
  const busy = useRef({ live: false, record: false, swarm: false });

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
      const byBot: Record<number, Event[]> = {};
      events.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          byBot[live[index].bot_id] = result.value.slice(0, 5);
          if (result.value[0]) latest[live[index].bot_id] = result.value[0];
        }
      });
      setLatestEvents(latest);
      setBotEvents(byBot);
      setError('');
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not load live bots.'); }
    finally { busy.current.live = false; }
  }, [creator]);

  // The swarm and the graphs: small, cheap reads (no Arkiv queries for the graphs).
  const refreshSwarm = useCallback(async () => {
    if (document.hidden || busy.current.swarm) return;
    busy.current.swarm = true;
    try {
      const [sw, se] = await Promise.allSettled([request<Swarm>('/api/swarm'), request<Series>('/api/series')]);
      if (sw.status === 'fulfilled') setSwarm(sw.value);
      if (se.status === 'fulfilled') setSeries(se.value);
    } finally { busy.current.swarm = false; }
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
    void refreshLive(); void refreshRecord(); void refreshSwarm();
    const liveTimer = window.setInterval(refreshLive, 5_000);
    const swarmTimer = window.setInterval(refreshSwarm, 5_000);
    const recordTimer = window.setInterval(refreshRecord, 15_000);
    const onVisible = () => { if (!document.hidden) { void refreshLive(); void refreshRecord(); void refreshSwarm(); } };
    document.addEventListener('visibilitychange', onVisible);
    return () => { window.clearInterval(liveTimer); window.clearInterval(swarmTimer); window.clearInterval(recordTimer); document.removeEventListener('visibilitychange', onVisible); };
  }, [refreshLive, refreshRecord, refreshSwarm]);

  return { creator, setCreator, info, brains, bots, latestEvents, botEvents, swarm, setSwarm, series, graves, report, comparison, error, recordError, refreshLive, refreshRecord, refreshSwarm };
}
