import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLiveFeed } from './useLiveFeed';
import { parseDetailSnapshot, parseListSnapshot } from './client';
import { detailFixture, listFixture } from './testFixtures';
import type { MatchDetailSnapshot, MatchListSnapshot } from './types';
const response = () => new Response(JSON.stringify(listFixture()), { status: 200 });
beforeEach(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: false }); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
type Snapshot = MatchListSnapshot | MatchDetailSnapshot;
const later = '2026-10-23T12:02:00Z';
const earlier = '2026-10-23T12:01:00Z';
function sportscoreSnapshot(kind: 'list' | 'detail', generatedAt: string | null, runs: number): Snapshot {
  const data: Snapshot = kind === 'list' ? listFixture() : detailFixture();
  data.source.id = 'sportscore';
  data.generatedAt = generatedAt;
  const match = 'matches' in data ? data.matches[0] : data.match;
  match.source.id = 'sportscore';
  match.observedAt = null;
  match.fetchedAt = '2026-10-23T12:03:00Z';
  match.scores[0].runs = runs;
  return data;
}
const runs = (data: Snapshot | null) => data ? ('matches' in data ? data.matches[0] : data.match).scores[0].runs : null;
const parseSnapshot = (kind: 'list' | 'detail') => (value: unknown): Snapshot => kind === 'list' ? parseListSnapshot(value) : parseDetailSnapshot(value, 'synthetic-one');
describe('foreground refresh control', () => {
  it('does not request while paused and resumes with a fresh request', async () => {
    const fetcher = vi.fn().mockImplementation(async () => response()); vi.stubGlobal('fetch', fetcher);
    const { result, rerender } = renderHook(({ paused }) => useLiveFeed('https://feed.test/v1/matches', parseListSnapshot, paused), { initialProps: { paused: true } });
    expect(fetcher).not.toHaveBeenCalled();
    rerender({ paused: false });
    await waitFor(() => expect(result.current.data?.matches).toHaveLength(1));
    rerender({ paused: true });
    await act(async () => result.current.retry());
    expect(fetcher).toHaveBeenCalledTimes(1);
    rerender({ paused: false });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
  it('retains a good snapshot when the next response fails validation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(async () => response()).mockResolvedValueOnce(new Response('{"bad":true}')));
    const { result } = renderHook(() => useLiveFeed('https://feed.test/v1/matches', parseListSnapshot, false));
    await waitFor(() => expect(result.current.data?.matches).toHaveLength(1));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.error).toMatch(/invalid/i));
    expect(result.current.data?.matches[0].id).toBe('synthetic-one');
  });
  it('ignores an old match request after the selected path changes', async () => {
    let finish: (response: Response) => void = () => {};
    const first = new Promise<Response>((resolve) => { finish = resolve; });
    vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(first).mockImplementation(async () => response()));
    const { result, rerender } = renderHook(({ path }) => useLiveFeed(path, parseListSnapshot, false), { initialProps: { path: 'https://feed.test/one' } });
    rerender({ path: 'https://feed.test/two' });
    await waitFor(() => expect(result.current.data?.matches).toHaveLength(1));
    const old = listFixture(); old.matches[0].id = 'old';
    await act(async () => { finish(new Response(JSON.stringify(old))); });
    expect(result.current.data?.matches[0].id).toBe('synthetic-one');
  });
  it('suspends hidden-tab requests and refreshes once visible', async () => {
    const fetcher = vi.fn().mockImplementation(async () => response()); vi.stubGlobal('fetch', fetcher);
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    const { result } = renderHook(() => useLiveFeed('https://feed.test/v1/matches', parseListSnapshot, false));
    expect(fetcher).not.toHaveBeenCalled();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await waitFor(() => expect(result.current.data?.matches).toHaveLength(1));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each(['list', 'detail'] as const)('retains the newer SportScore %s publication when an older one arrives later', async kind => {
    const snapshots = [sportscoreSnapshot(kind, later, 100), sportscoreSnapshot(kind, earlier, 90), sportscoreSnapshot(kind, '2026-10-23T12:03:00Z', 101)];
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(snapshots.shift())));
    const { result } = renderHook(() => useLiveFeed('https://feed.test/matches', parseSnapshot(kind), false));
    await waitFor(() => expect(runs(result.current.data)).toBe(100));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(runs(result.current.data)).toBe(100);
    expect(result.current.data?.generatedAt).toBe(later);
    expect(result.current.error).toMatch(/older snapshot/i);
    act(() => result.current.retry());
    await waitFor(() => expect(runs(result.current.data)).toBe(101));
    expect(result.current.error).toBeNull();
  });
  it.each(['list', 'detail'] as const)('accepts a lower-score correction in an equal-time SportScore %s publication', async kind => {
    const snapshots = [sportscoreSnapshot(kind, later, 100), sportscoreSnapshot(kind, later, 99)];
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(snapshots.shift())));
    const { result } = renderHook(() => useLiveFeed('https://feed.test/matches', parseSnapshot(kind), false));
    await waitFor(() => expect(runs(result.current.data)).toBe(100));
    act(() => result.current.retry());
    await waitFor(() => expect(runs(result.current.data)).toBe(99));
    expect(result.current.error).toBeNull();
  });
  it('resets publication ordering when selecting another resource, including a return selection', async () => {
    const snapshots = [sportscoreSnapshot('list', later, 100), sportscoreSnapshot('list', earlier, 90), sportscoreSnapshot('list', '2026-10-23T12:00:00Z', 80)];
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(snapshots.shift())));
    const { result, rerender } = renderHook(({ path }) => useLiveFeed(path, parseListSnapshot, false), { initialProps: { path: 'https://feed.test/one' } });
    await waitFor(() => expect(runs(result.current.data)).toBe(100));
    rerender({ path: 'https://feed.test/two' });
    await waitFor(() => expect(runs(result.current.data)).toBe(90));
    rerender({ path: 'https://feed.test/one' });
    await waitFor(() => expect(runs(result.current.data)).toBe(80));
    expect(result.current.error).toBeNull();
  });
  it('does not invent publication ordering for absent clocks or a different source', async () => {
    const other = sportscoreSnapshot('list', earlier, 97); other.source.id = 'another-source';
    const snapshots = [sportscoreSnapshot('list', null, 100), sportscoreSnapshot('list', later, 99), sportscoreSnapshot('list', null, 98), other];
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(snapshots.shift())));
    const { result } = renderHook(() => useLiveFeed('https://feed.test/matches', parseListSnapshot, false));
    await waitFor(() => expect(runs(result.current.data)).toBe(100));
    for (const expected of [99, 98, 97]) {
      act(() => result.current.retry());
      await waitFor(() => expect(runs(result.current.data)).toBe(expected));
      expect(result.current.error).toBeNull();
    }
  });

  // Value: protects=refresh failures retain verified data and expose safe, actionable error text;
  // fails_when=timeout aborts, HTTP error mapping or retained clocks/data regress;
  // why_new=existing validation and outage tests do not exercise these failure boundaries; seam=none.
  // Assertions: deadline does not fire early; timeout/404/503/network text, data and check time.
  it('retains the verified snapshot and distinguishes timeout, HTTP and connection errors', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    const cases = [
      { kind: 'timeout', message: 'The feed request timed out. Last verified data is retained.' },
      { kind: 'missing', message: 'This match is not in the current feed.' },
      { kind: 'unavailable', message: 'The feed is temporarily unavailable.' },
      { kind: 'network', message: 'Connection lost. Last verified data is retained.' },
    ];
    for (const { kind, message } of cases) {
      const fetcher = vi.fn().mockResolvedValueOnce(response()).mockImplementationOnce((_input: string, init?: RequestInit) => {
        if (kind === 'timeout') return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
        });
        if (kind === 'network') return Promise.reject(new Error('private provider detail must not escape'));
        return Promise.resolve(new Response(null, { status: kind === 'missing' ? 404 : 503 }));
      });
      vi.stubGlobal('fetch', fetcher);
      const { result, unmount } = renderHook(() => useLiveFeed('https://feed.test/v1/matches', parseListSnapshot, false));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(result.current.data?.matches[0].id).toBe('synthetic-one');
      const verified = result.current.data;
      const checkedAt = result.current.checkedAt;
      await act(async () => result.current.retry());
      if (kind === 'timeout') {
        await act(async () => { await vi.advanceTimersByTimeAsync(14_999); });
        expect(result.current.loading).toBe(true);
        expect(result.current.error).toBeNull();
        await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      }
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe(message);
      expect(result.current.data).toEqual(verified);
      expect(result.current.checkedAt).toBe(checkedAt);
      expect(fetcher).toHaveBeenCalledTimes(2);
      unmount();
      expect(vi.getTimerCount()).toBe(0);
    }
  });

  // Value: protects=automatic refresh backs off after repeated failures, caps at five minutes and resets on recovery;
  // fails_when=retries run early, grow unbounded or keep an old failure count after success;
  // why_new=manual retry tests cannot exercise automatic failure cadence; seam=none.
  // Assertions: request counts immediately before/at every retry boundary and recovery cadence.
  it('caps automatic retry backoff and resets it after a successful refresh', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    const good = listFixture(); good.refreshAfterSeconds = 5;
    let attempts = 0;
    const fetcher = vi.fn(async () => {
      attempts += 1;
      if (attempts === 7 || attempts === 9) return Response.json(good);
      throw new Error('Synthetic network outage');
    });
    vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(() => useLiveFeed('https://feed.test/v1/matches', parseListSnapshot, false));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(result.current.error).toBe('Connection lost. Last verified data is retained.');
    let expectedCalls = 1;
    for (const delay of [30_000, 60_000, 120_000, 240_000, 300_000, 300_000]) {
      await act(async () => { await vi.advanceTimersByTimeAsync(delay - 1); });
      expect(fetcher).toHaveBeenCalledTimes(expectedCalls);
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expectedCalls += 1;
      expect(fetcher).toHaveBeenCalledTimes(expectedCalls);
    }
    expect(result.current.data).toEqual(good);
    expect(result.current.error).toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync(4_999); });
    expect(fetcher).toHaveBeenCalledTimes(7);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(fetcher).toHaveBeenCalledTimes(8);
    expect(result.current.error).toBe('Connection lost. Last verified data is retained.');
    expect(result.current.data).toEqual(good);
    await act(async () => { await vi.advanceTimersByTimeAsync(29_999); });
    expect(fetcher).toHaveBeenCalledTimes(8);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(fetcher).toHaveBeenCalledTimes(9);
    expect(result.current.error).toBeNull();
  });
});
