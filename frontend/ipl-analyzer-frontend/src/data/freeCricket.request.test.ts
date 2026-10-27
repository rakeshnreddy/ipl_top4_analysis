import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadFreeMatches } from './freeCricket';

const fixture = { sport: 'cricket', count: 0, matches: [], updated: '2026-10-23T12:00:00Z' };
const maxBytes = 1_048_576;
const jsonHeaders = { 'Content-Type': 'application/json' };

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('free cricket public request boundary', () => {
  // Value: protects=denied or unsupported upstream responses cannot become match snapshots;
  // fails_when=HTTP, content-type, declared-size or body guards are removed;
  // why_new=normalizer tests receive already decoded objects; seam=none.
  // Assertions: exact reader-facing errors, fixed endpoint and credential-free requests.
  it('rejects HTTP denials and unsupported responses at the public loader', async () => {
    const cases = [
      { response: new Response('limited', { status: 429 }), error: 'The free cricket source is rate limited. Please try later.' },
      { response: new Response('unavailable', { status: 503 }), error: 'The free cricket source is temporarily unavailable.' },
      { response: new Response(JSON.stringify(fixture), { headers: { 'Content-Type': 'text/html' } }), error: 'The cricket source returned an unsupported response.' },
      { response: new Response(JSON.stringify(fixture), { headers: { ...jsonHeaders, 'Content-Length': String(maxBytes + 1) } }), error: 'The cricket source returned an unsupported response.' },
      { response: new Response(null, { headers: jsonHeaders }), error: 'The cricket source returned an unsupported response.' },
    ];
    for (const { response, error } of cases) {
      const fetcher = vi.fn().mockResolvedValue(response);
      vi.stubGlobal('fetch', fetcher);
      await expect(loadFreeMatches()).rejects.toThrow(error);
      expect(fetcher).toHaveBeenCalledExactlyOnceWith('https://sportscore.com/api/widget/matches/?sport=cricket&limit=50', expect.objectContaining({
        credentials: 'omit', referrerPolicy: 'no-referrer', headers: { Accept: 'application/json' },
      }));
    }
  });

  // Value: protects=the public loader accepts bounded chunked JSON and cancels oversized streams;
  // fails_when=stream size accumulation or its strict byte boundary is lost;
  // why_new=declared-size checks cannot protect a response with no length header; seam=none.
  // Assertions: an exact-limit synthetic snapshot succeeds; the next byte rejects and cancels.
  it('bounds streamed bytes even when the source omits Content-Length', async () => {
    const bytes = new TextEncoder().encode(JSON.stringify(fixture).padEnd(maxBytes, ' '));
    const valid = new ReadableStream<Uint8Array>({ start(controller) {
      controller.enqueue(bytes.subarray(0, 31));
      controller.enqueue(bytes.subarray(31));
      controller.close();
    } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(valid, { headers: jsonHeaders })));
    await expect(loadFreeMatches()).resolves.toMatchObject({ status: 'ok', generatedAt: fixture.updated, matches: [] });

    const cancelled = vi.fn();
    const oversized = new ReadableStream<Uint8Array>({ start(controller) {
      controller.enqueue(bytes);
      controller.enqueue(new Uint8Array([32]));
    }, cancel: cancelled });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(oversized, { headers: jsonHeaders })));
    await expect(loadFreeMatches()).rejects.toThrow('The cricket response is too large.');
    expect(cancelled).toHaveBeenCalledTimes(1);
  });

  // Value: protects=caller cancellation and the 12-second deadline abort the public source request;
  // fails_when=signal forwarding, pre-abort handling or the deadline is removed;
  // why_new=normalization and hook mocks do not execute the free-source request; seam=none.
  // Assertions: no early deadline, AbortError at each cancellation boundary, no lingering timer.
  it('honors caller aborts and its own deadline without retaining a timeout', async () => {
    vi.useFakeTimers();
    for (const mode of ['caller', 'already-aborted', 'deadline']) {
      const caller = new AbortController();
      if (mode === 'already-aborted') caller.abort();
      let forwarded: AbortSignal | undefined;
      vi.stubGlobal('fetch', vi.fn((_input: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
        forwarded = init?.signal as AbortSignal;
        const abort = () => reject(new DOMException('Aborted', 'AbortError'));
        if (forwarded.aborted) abort();
        else forwarded.addEventListener('abort', abort, { once: true });
      })));
      let settled = false;
      const outcome = loadFreeMatches(caller.signal).then(() => { settled = true; return null; }, (error: unknown) => { settled = true; return error; });
      if (mode === 'caller') caller.abort();
      if (mode === 'deadline') {
        await vi.advanceTimersByTimeAsync(11_999);
        expect(settled).toBe(false);
        expect(forwarded?.aborted).toBe(false);
        await vi.advanceTimersByTimeAsync(1);
      }
      expect(await outcome).toMatchObject({ name: 'AbortError' });
      expect(forwarded?.aborted).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    }
  });
});
