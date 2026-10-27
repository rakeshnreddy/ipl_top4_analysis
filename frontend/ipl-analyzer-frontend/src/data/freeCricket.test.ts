import { describe, expect, it } from 'vitest';
import { normalizeSportScoreDetail, normalizeSportScoreList } from './freeCricket';

const at = '2026-10-23T12:00:00Z';
const row = { home: 'Example A', away: 'Example B', home_score: '122/3 (17.5)', away_score: null, status: 'live', status_text: 'In progress', time: '2026-10-23T10:00:00Z', competition: 'Example Women T20', url: '/cricket/match/example-a-vs-example-b/' };
const payload = { sport: 'cricket', updated: at, count: 1, matches: [row] };

describe('free cricket source contract', () => {
  it('keeps placeholder totals unavailable while treating a supplied zero as a score', () => {
    const missing = normalizeSportScoreList({ ...payload, matches: [{ ...row, home_score: '-', away_score: '—' }] }, at);
    expect(missing.matches[0].scores).toEqual([]);
    expect(missing.coverage[0].scores).toBe(false);
    const zero = normalizeSportScoreList({ ...payload, matches: [{ ...row, home_score: 0 }] }, at);
    expect(zero.matches[0].scores[0].runs).toBe(0);
    expect(zero.coverage[0].scores).toBe(true);
  });
  it('preserves scoring, legal balls and unknown event time without inventing a scorecard', () => {
    const feed = normalizeSportScoreList(payload, at);
    expect(feed.matches).toHaveLength(1);
    const match = feed.matches[0];
    expect(match.scores[0]).toMatchObject({ runs: 122, wickets: 3, legalBalls: 107, overs: '17.5' });
    expect(match.observedAt).toBeNull();
    expect(match.gender).toBe('female');
    expect(match.capabilities.scorecard).toBe(false);
    expect(match.capabilities.model).toBe(false);
  });
  it('leaves wickets and balls unknown for a bare run total, and future matches scheduled', () => {
    const feed = normalizeSportScoreList({ ...payload, matches: [{ ...row, home_score: 212, status: 'upcoming', status_text: 'Not started' }] }, at);
    expect(feed.matches[0].scores[0]).toMatchObject({ runs: 212, wickets: null, legalBalls: null });
    expect(feed.matches[0].state).toBe('scheduled');
  });
  it('rejects non-cricket and invalid envelopes instead of reporting no matches', () => {
    expect(() => normalizeSportScoreList({ matches: [] }, at)).toThrow();
    expect(() => normalizeSportScoreList({ ...payload, sport: 'football' }, at)).toThrow();
  });
  it('marks dropped malformed records as partial coverage', () => {
    const feed = normalizeSportScoreList({ ...payload, count: 2, matches: [row, { ...row, home: '' }] }, at);
    expect(feed.matches).toHaveLength(1);
    expect(feed.status).toBe('partial');
  });
  it('does not join a reused match slug for a different fixture', () => {
    const summary = normalizeSportScoreList(payload, at).matches[0];
    expect(() => normalizeSportScoreDetail({ sport: 'cricket', updated: at, match: { ...row, time: '2026-10-24T10:00:00Z' } }, summary, at)).toThrow(/identity/i);
    expect(() => normalizeSportScoreDetail({ sport: 'cricket', updated: at, match: { ...row, home: 'Other team' } }, summary, at)).toThrow(/identity/i);
  });
  it('keeps absent detail, predictions and external prices explicitly unavailable', () => {
    const summary = normalizeSportScoreList(payload, at).matches[0];
    const detail = normalizeSportScoreDetail({ sport: 'cricket', updated: at, match: row }, summary, at);
    expect(detail.match.id).toBe(summary.id);
    for (const part of [detail.scorecard, detail.commentary, detail.model, detail.markets]) {
      expect(part.status).toBe('unavailable');
      expect(part.data).toBeNull();
    }
  });
  it('preserves a delayed source collection timestamp on re-fetch', () => {
    const feed = normalizeSportScoreList(payload, '2026-10-23T15:00:00Z');
    expect(feed.generatedAt).toBe(at);
    expect(feed.matches[0].fetchedAt).toBe('2026-10-23T15:00:00Z');
  });
  it('uses the same format vocabulary as configured bookmaker scopes', () => {
    const a = normalizeSportScoreList({ ...payload, matches: [{ ...row, format: 'T20I' }] }, at);
    const b = normalizeSportScoreList({ ...payload, matches: [{ ...row, competition: 'Example Test Series' }] }, at);
    expect(a.matches[0].format).toBe('T20');
    expect(b.matches[0].format).toBe('TEST');
  });
  it('does not reinterpret Hundred or unknown-format notation as six-ball overs', () => {
    for (const format of ['HUNDRED', 'Unknown']) {
      const feed = normalizeSportScoreList({ ...payload, matches: [{ ...row, competition: 'Example competition', format }] }, at);
      expect(feed.matches[0].scores[0].display).toBe('122/3 (17.5)');
      expect(feed.matches[0].scores[0].legalBalls).toBeNull();
    }
  });
});
