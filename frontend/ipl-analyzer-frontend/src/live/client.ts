import type { MatchDetailSnapshot, MatchListSnapshot } from './types';
type ObjectValue = Record<string, unknown>;
type Guard = (value: unknown) => boolean;
const record = (v: unknown): v is ObjectValue => typeof v === 'object' && v !== null && !Array.isArray(v);
const text: Guard = v => typeof v === 'string' && v.length <= 20_000;
const nonempty: Guard = v => text(v) && (v as string).length > 0;
const number: Guard = v => typeof v === 'number' && Number.isFinite(v);
const integer: Guard = v => number(v) && Number.isInteger(v) && v as number >= 0;
const bool: Guard = v => typeof v === 'boolean';
const nullable = (guard: Guard): Guard => v => v === null || guard(v);
const optional = (guard: Guard): Guard => v => v === undefined || guard(v);
const display = optional(nullable(v => typeof v === 'string' && v.length <= 240));
const choices = (...values: string[]): Guard => v => typeof v === 'string' && values.includes(v);
const date: Guard = v => typeof v === 'string' && v.length < 64 && Number.isFinite(Date.parse(v));
const array = (guard: Guard, limit = 10_000): Guard => v => Array.isArray(v) && v.length <= limit && v.every(guard);
const shape = (fields: Record<string, Guard>): Guard => v => record(v) && Object.entries(fields).every(([key, guard]) => guard(v[key]));
const unique = (v: unknown, key = 'id') => Array.isArray(v) && new Set(v.map((entry: ObjectValue) => entry[key])).size === v.length;
const validUrl: Guard = v => {
  if (typeof v !== 'string') return false;
  try {
    const u = new URL(v);
    return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password;
  } catch {
    return false;
  }
};
const source = shape({
  id: nonempty,
  name: nonempty,
  url: validUrl
});
const innings = shape({
  id: nonempty,
  team: text,
  label: text,
  display,
  runs: nullable(integer),
  wickets: nullable(integer),
  legalBalls: nullable(integer),
  overs: nullable(text)
});
const summary = shape({
  id: nonempty,
  providerIds: v => record(v) && Object.values(v).every(text),
  teams: array(shape({
    id: nonempty,
    name: nonempty,
    shortName: text
  }), 8),
  competition: shape({
    id: nonempty,
    name: nonempty
  }),
  format: nonempty,
  gender: nonempty,
  state: choices('scheduled', 'toss', 'live', 'innings-break', 'delayed', 'stumps', 'suspended', 'completed', 'abandoned', 'unknown'),
  statusText: text,
  startTime: nullable(date),
  venue: nullable(text),
  scores: v => array(innings, 32)(v) && unique(v),
  observedAt: nullable(date),
  fetchedAt: nullable(date),
  revision: nonempty,
  capabilities: shape({
    scorecard: bool,
    commentary: bool,
    model: bool,
    markets: bool
  }),
  source
});
const meta = shape({
  schemaVersion: v => v === 1,
  status: choices('ok', 'partial', 'unavailable', 'error'),
  message: nullable(text),
  source,
  generatedAt: nullable(date),
  refreshAfterSeconds: v => integer(v) && v as number >= 5 && v as number <= 86_400,
  staleAfterSeconds: v => integer(v) && v as number >= 5 && v as number <= 604_800
});
const part = (data: Guard): Guard => v => shape({
  status: choices('available', 'unavailable', 'stale', 'error'),
  source: text,
  observedAt: nullable(date),
  fetchedAt: nullable(date),
  reason: nullable(text),
  data: nullable(data)
})(v) && record(v) && (v.status !== 'available' || v.data !== null);
const card = shape({
  id: nonempty,
  team: text,
  label: text,
  display,
  runs: nullable(integer),
  wickets: nullable(integer),
  legalBalls: nullable(integer),
  overs: nullable(text),
  batting: array(shape({
    id: nonempty,
    name: nonempty,
    dismissal: nullable(text),
    runs: nullable(integer),
    balls: nullable(integer),
    fours: nullable(integer),
    sixes: nullable(integer),
    strikeRate: nullable(number)
  }), 30),
  bowling: array(shape({
    id: nonempty,
    name: nonempty,
    overs: nullable(text),
    maidens: nullable(integer),
    runs: nullable(integer),
    wickets: nullable(integer),
    economy: nullable(number)
  }), 30),
  extras: nullable(text),
  fallOfWickets: array(text, 20),
  partnerships: array(text, 30)
});
const delivery = shape({
  id: nonempty,
  sequence: integer,
  innings: nonempty,
  over: text,
  batter: nullable(text),
  bowler: nullable(text),
  runs: nullable(integer),
  extras: nullable(integer),
  wickets: nullable(integer),
  text,
  observedAt: nullable(date),
  revision: nonempty
});
const probabilities: Guard = v => array(shape({
  outcome: nonempty,
  probability: n => number(n) && n as number >= 0 && n as number <= 1
}), 12)(v) && Array.isArray(v) && v.length >= 2 && Math.abs(v.reduce((sum, p) => sum + p.probability, 0) - 1) <= 0.001 && unique(v, 'outcome');
const model = shape({
  modelId: nonempty,
  modelVersion: nonempty,
  scoreRevision: nonempty,
  predictedAt: date,
  conditioning: nonempty,
  probabilities,
  history: array(shape({
    scoreRevision: nonempty,
    at: date,
    probabilities
  }), 10_000)
});
const market = shape({
  key: nonempty,
  name: nonempty,
  state: choices('open', 'suspended', 'closed', 'unknown'),
  updatedAt: nullable(date),
  settlement: nullable(text),
  outcomes: array(v => shape({
    name: nonempty,
    price: n => number(n) && n as number > 1 && n as number < 1_000_000
  })(v) && record(v) && (v.point === undefined || number(v.point)), 100)
});
const bookmakers = (v: unknown) => array(shape({
  key: nonempty,
  title: nonempty,
  updatedAt: nullable(date),
  markets: array(market, 100)
}), 100)(v) && unique(v, 'key');

/** Deployment config holds an origin only, never provider keys or paths. */
export function apiOrigin(input: unknown): string | null {
  if (typeof input !== 'string' || !input.trim()) return null;
  try {
    const u = new URL(input.trim());
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(u.hostname);
    if (u.protocol !== 'https:' && !(local && u.protocol === 'http:') || u.username || u.password || u.pathname !== '/' || u.search || u.hash) return null;
    return u.origin;
  } catch {
    return null;
  }
}
export function parseListSnapshot(value: unknown): MatchListSnapshot {
  if (!meta(value) || !shape({
    coverage: array(shape({
      competition: text,
      scores: bool,
      scorecard: bool,
      commentary: bool,
      markets: bool,
      note: text
    }), 500),
    matches: v => array(summary, 2000)(v) && unique(v)
  })(value)) throw new Error('Invalid match feed. The last verified snapshot is retained.');
  return value as MatchListSnapshot;
}
export function parseDetailSnapshot(value: unknown, expectedId: string): MatchDetailSnapshot {
  if (!meta(value) || !shape({
    match: summary,
    scorecard: part(v => array(card, 32)(v) && unique(v)),
    commentary: part(v => array(delivery)(v) && unique(v)),
    model: part(model),
    markets: part(bookmakers)
  })(value)) throw new Error('Invalid match detail. The last verified snapshot is retained.');
  const result = value as MatchDetailSnapshot;
  if (result.match.id !== expectedId) throw new Error('Match response does not match the selected match.');
  return result;
}
