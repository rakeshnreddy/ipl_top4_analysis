import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLiveFeed } from './useLiveFeed';
import { parseListSnapshot } from './client';
import { listFixture } from './testFixtures';
const response = () => new Response(JSON.stringify(listFixture()), { status: 200 });
beforeEach(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: false }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
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
});
