import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLiveFeed } from './useLiveFeed';
import { parseDetailSnapshot, parseListSnapshot } from './client';
import { detailFixture, listFixture } from './testFixtures';
import type { MatchDetailSnapshot, MatchListSnapshot } from './types';
const response = () => new Response(JSON.stringify(listFixture()), { status: 200 });
beforeEach(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: false }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
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
});
