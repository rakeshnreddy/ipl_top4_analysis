import type { MatchDetailSnapshot, MatchListSnapshot, MatchSummary } from '../live/types';
import { SPORT_SCORE, normalizeSportScoreList, normalizeSportScoreDetail } from './freeCricketNormalize';
export { SPORT_SCORE, normalizeSportScoreList, normalizeSportScoreDetail } from './freeCricketNormalize';
const API = 'https://sportscore.com/api/widget/';
const MAX_BYTES = 1_048_576;

/** Bounded public request, with a timeout even if the caller keeps the view open. */
async function request(path: string, signal?: AbortSignal): Promise<unknown> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(abort, 12_000);
  try {
    const response = await fetch(`${API}${path}`, { signal: controller.signal, headers: { Accept: 'application/json' }, credentials: 'omit', referrerPolicy: 'no-referrer' });
    if (!response.ok) throw new Error(response.status === 429 ? 'The free cricket source is rate limited. Please try later.' : 'The free cricket source is temporarily unavailable.');
    if (!response.headers.get('content-type')?.includes('application/json') || Number(response.headers.get('content-length') ?? 0) > MAX_BYTES || !response.body) throw new Error('The cricket source returned an unsupported response.');
    const reader = response.body.getReader(); const chunks: Uint8Array[] = []; let length = 0;
    try {
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        length += value.byteLength;
        if (length > MAX_BYTES) { await reader.cancel(); throw new Error('The cricket response is too large.'); }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    return JSON.parse(new TextDecoder().decode(bytes));
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort); }
}

export async function loadFreeMatches(signal?: AbortSignal): Promise<MatchListSnapshot> {
  return normalizeSportScoreList(await request('matches/?sport=cricket&limit=50', signal), new Date().toISOString());
}

export async function loadFreeDetail(id: string, summary: MatchSummary, signal?: AbortSignal): Promise<MatchDetailSnapshot> {
  if (id !== summary.id || summary.source.id !== SPORT_SCORE.id || !/^[a-z0-9-]{1,160}$/.test(summary.providerIds.sportscoreSlug ?? '')) throw new Error('Invalid cricket match selection.');
  return normalizeSportScoreDetail(await request(`match/?sport=cricket&slug=${encodeURIComponent(summary.providerIds.sportscoreSlug)}`, signal), summary, new Date().toISOString());
}
