import { useCallback, useEffect, useRef, useState } from 'react';
import type { FeedMeta } from './types';
type State<T> = {
  path: string | null;
  data: T | null;
  loading: boolean;
  error: string | null;
  checkedAt: string | null;
};
/** One foreground request at a time; aborts selection races and retains verified data on errors. */
export function useLiveFeed<T extends FeedMeta>(path: string | null, parse: (value: unknown) => T, paused: boolean, loader?: (signal: AbortSignal) => Promise<unknown>) {
  const [state, setState] = useState<State<T>>({
    path,
    data: null,
    loading: false,
    error: null,
    checkedAt: null
  });
  const [attempt, setAttempt] = useState(0);
  const parser = useRef(parse);
  const loadSource = useRef(loader);
  const accepted = useRef<{ path: string; data: T } | null>(null);
  loadSource.current = loader;
  parser.current = parse;
  const retry = useCallback(() => {
    if (!paused && !document.hidden) setAttempt(value => value + 1);
  }, [paused]);
  useEffect(() => {
    // Publication clocks order one resource, never two selected matches or feeds.
    if (accepted.current?.path !== path) accepted.current = null;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    let failures = 0;
    const stop = () => {
      clearTimeout(timer);
      controller?.abort();
      controller = undefined;
    };
    const load = async () => {
      if (!active || !path || paused || document.hidden) return;
      const request = new AbortController();
      controller = request;
      setState(previous => ({
        path,
        data: previous.path === path ? previous.data : null,
        checkedAt: previous.path === path ? previous.checkedAt : null,
        error: previous.path === path ? previous.error : null,
        loading: true
      }));
      const timeout = setTimeout(() => request.abort(), 15_000);
      let interval = 30;
      try {
        let raw: unknown;
        if (loadSource.current) {
          raw = await loadSource.current(request.signal);
        } else {
          const response = await fetch(path, {
            signal: request.signal,
            credentials: 'omit',
            cache: 'no-store',
            referrerPolicy: 'no-referrer',
            headers: {
              Accept: 'application/json'
            }
          });
          if (!response.ok) throw new Error(response.status === 404 ? 'This match is not in the current feed.' : 'The feed is temporarily unavailable.');
          raw = await response.json();
        }
        const data = parser.current(raw);
        if (!active || request.signal.aborted || paused || document.hidden) return;
        const previous = accepted.current;
        if (previous?.path === path && previous.data.source.id === data.source.id
          && previous.data.generatedAt && data.generatedAt
          && Date.parse(data.generatedAt) < Date.parse(previous.data.generatedAt)) {
          throw new Error('The feed returned an older snapshot. Last verified data is retained.');
        }
        accepted.current = { path, data };
        failures = 0;
        interval = data.refreshAfterSeconds;
        setState({
          path,
          data,
          loading: false,
          error: null,
          checkedAt: new Date().toISOString()
        });
      } catch (error) {
        if (!active || paused || document.hidden || controller !== request) return;
        failures += 1;
        interval = Math.min(300, 30 * 2 ** Math.min(failures - 1, 4));
        const message = request.signal.aborted ? 'The feed request timed out. Last verified data is retained.' : error instanceof Error && /^(Invalid|Match response|This match|The feed)/.test(error.message) ? error.message : 'Connection lost. Last verified data is retained.';
        setState(previous => ({
          path,
          data: previous.path === path ? previous.data : null,
          checkedAt: previous.path === path ? previous.checkedAt : null,
          error: message,
          loading: false
        }));
      } finally {
        clearTimeout(timeout);
        const ownsRequest = controller === request;
        if (ownsRequest) controller = undefined;
        if (ownsRequest && active && !paused && !document.hidden) timer = setTimeout(() => void load(), Math.max(5000, interval * 1000) * (0.9 + Math.random() * 0.2));
      }
    };
    const visibility = () => {
      stop();
      if (!document.hidden) void load();
    };
    document.addEventListener('visibilitychange', visibility);
    if (!paused && !document.hidden) void load();
    return () => {
      active = false;
      stop();
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [path, paused, attempt]);
  return {
    ...(state.path === path ? state : {
      path,
      data: null,
      loading: !!path && !paused,
      error: null,
      checkedAt: null
    }),
    retry
  };
}
