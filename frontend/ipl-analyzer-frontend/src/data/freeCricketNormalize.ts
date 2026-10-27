import type { FeedMeta, InningsScore, MatchDetailSnapshot, MatchListSnapshot, MatchState, MatchSummary, Part, Source } from '../live/types';

/** API-specific terms: https://sportscore.com/developers/terms/ (attribution required). */
export const SPORT_SCORE: Source = { id: 'sportscore', name: 'SportScore', url: 'https://sportscore.com/' };
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown, max = 240): string => typeof value === 'string' ? value.trim().slice(0, max) : '';
const date = (value: unknown): string | null => typeof value === 'string' && /^\d{4}-\d\d-\d\dT/.test(value) && Number.isFinite(Date.parse(value)) ? value : null;
const slugify = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

function envelope(payload: unknown): Record<string, unknown> {
  if (!record(payload) || payload.sport !== 'cricket') throw new Error('The cricket source returned an unsupported response.');
  return payload;
}

function stateOf(status: string, description: string): MatchState {
  const phase = description.toLowerCase();
  if (/abandon|cancel/.test(phase) || ['cancelled', 'canceled', 'abandoned'].includes(status)) return 'abandoned';
  if (/stumps/.test(phase)) return 'stumps';
  if (/rain|delay|wet outfield/.test(phase)) return 'delayed';
  if (/innings break|lunch|tea break/.test(phase)) return 'innings-break';
  if (/suspend/.test(phase)) return 'suspended';
  if (['finished', 'completed', 'ended', 'final'].includes(status)) return 'completed';
  if (['live', 'inprogress', 'in_progress', 'in progress'].includes(status)) return 'live';
  if (['upcoming', 'scheduled', 'notstarted', 'not_started'].includes(status)) return 'scheduled';
  if (/toss/.test(phase)) return 'toss';
  return 'unknown';
}

/** Preserve raw multi-innings notation; parse only an unambiguous single-innings score. */
function score(value: unknown, team: string, id: string, format: string): InningsScore | null {
  if (value === null || value === undefined || value === '') return null;
  const raw = typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? String(value) : text(value, 120);
  if (!raw || /^(?:[-–—]+|n\/a)$/i.test(raw)) return null;
  const match = /^(\d{1,4})(?:\/(\d{1,2}))?(?:\s*\((\d{1,3})(?:\.([0-5]))?\s*(?:ov(?:ers?)?)?\))?$/.exec(raw);
  const wickets = match?.[2] === undefined ? null : Number(match[2]);
  const valid = match && (wickets === null || wickets <= 10);
  return {
    id, team, label: `${team} innings`, display: raw,
    runs: valid ? Number(match[1]) : null, wickets: valid ? wickets : null,
    legalBalls: valid && match[3] && ['T20', 'T10', 'ODI', 'TEST', 'FIRST-CLASS', 'LIST A'].includes(format) ? Number(match[3]) * 6 + Number(match[4] ?? 0) : null,
    overs: valid && match[3] ? `${match[3]}${match[4] === undefined ? '' : `.${match[4]}`}` : null,
  };
}

function normalizeMatch(value: unknown, fetchedAt: string): MatchSummary | null {
  if (!record(value)) return null;
  const home = text(value.home); const away = text(value.away);
  const competition = text(value.competition); const start = date(value.time);
  const path = /^\/cricket\/match\/([a-z0-9-]{1,160})\/$/.exec(text(value.url, 200));
  if (!home || !away || home === away || !competition || !start || !path) return null;
  const epoch = Math.floor(Date.parse(start) / 1000);
  const id = `ss-${epoch}-${path[1]}`;
  const statusText = text(value.status_text) || 'Match state unavailable';
  const suppliedFormat = text(value.format).toUpperCase();
  const rawFormat = suppliedFormat === 'T20I' ? 'T20' : suppliedFormat;
  const format = ['T20', 'T20I', 'ODI', 'TEST', 'T10', 'FIRST-CLASS', 'LIST A', 'HUNDRED'].includes(rawFormat) ? rawFormat
    : /\bT20\b|Twenty20/i.test(competition) ? 'T20' : /\bT10\b/i.test(competition) ? 'T10'
      : /\bODI\b|One-Day/i.test(competition) ? 'ODI' : /\bTest\b/i.test(competition) ? 'TEST' : 'Unknown';
  const gender = /\bwomen\b|\bwomen's\b/i.test(competition) ? 'female' : /\bmen\b|\bmen's\b/i.test(competition) ? 'male' : 'unknown';
  const teams = [home, away].map((name) => ({ id: slugify(name), name, shortName: name }));
  const scores = [score(value.home_score, home, `${id}-home`, format), score(value.away_score, away, `${id}-away`, format)].filter((item): item is InningsScore => item !== null);
  const state = stateOf(text(value.status).toLowerCase(), statusText);
  return {
    id, providerIds: { sportscoreSlug: path[1], sportscoreStartTime: start }, teams,
    competition: { id: slugify(competition), name: competition }, format, gender, state, statusText, startTime: start,
    venue: text(value.venue) || null, scores, observedAt: null, fetchedAt,
    // Content revision is deliberately independent of fetch/collection clocks.
    revision: JSON.stringify([id, home, away, state, statusText, scores, text(value.venue)]),
    capabilities: { scorecard: false, commentary: false, model: false, markets: false }, source: SPORT_SCORE,
  };
}

function meta(payload: Record<string, unknown>): FeedMeta {
  return { schemaVersion: 1, status: 'ok', message: null, source: SPORT_SCORE, generatedAt: date(payload.updated), refreshAfterSeconds: 60, staleAfterSeconds: 180 };
}

export function normalizeSportScoreList(payload: unknown, fetchedAt: string): MatchListSnapshot {
  const source = envelope(payload);
  if (!Array.isArray(source.matches) || source.matches.length > 50 || !Number.isSafeInteger(source.count) || Number(source.count) < source.matches.length || !date(fetchedAt)) throw new Error('The cricket match list is malformed.');
  const seen = new Set<string>();
  const matches = source.matches.flatMap((row) => {
    const match = normalizeMatch(row, fetchedAt);
    if (!match || seen.has(match.id)) return [];
    seen.add(match.id); return [match];
  });
  const partial = matches.length !== source.matches.length || source.matches.length === 50 || Number(source.count) > source.matches.length;
  return {
    ...meta(source), status: partial ? 'partial' : 'ok',
    message: partial ? 'Some matches may be omitted by the free source or could not be read.' : 'Free source coverage is limited; detailed scorecards and bookmaker prices are separate feeds.',
    matches,
    coverage: [...new Set(matches.map((match) => match.competition.name))].map((competition) => ({ competition, scores: matches.some((match) => match.competition.name === competition && match.scores.some((score) => score.runs !== null || /\d/.test(score.display ?? ''))), scorecard: false, commentary: false, markets: false, note: 'Discovery and available score totals only. Detailed coverage is not guaranteed.' })),
  };
}

function unavailable<T>(reason: string, fetchedAt: string): Part<T> {
  return { status: 'unavailable', source: SPORT_SCORE.name, observedAt: null, fetchedAt, reason, data: null };
}

export function normalizeSportScoreDetail(payload: unknown, summary: MatchSummary, fetchedAt: string): MatchDetailSnapshot {
  const source = envelope(payload);
  const match = normalizeMatch(source.match, fetchedAt);
  if (!match || match.id !== summary.id || match.teams.some((team, index) => team.name !== summary.teams[index]?.name) || match.competition.name !== summary.competition.name) throw new Error('Match identity changed; return to the current match list.');
  return {
    ...meta(source), status: 'partial', message: 'This free source supplies match status and available totals. Detailed feeds are not connected.', match,
    scorecard: unavailable('Full batting and bowling cards are not supplied by this free source.', fetchedAt),
    commentary: unavailable('An ordered cricket delivery stream is not supplied by this free source.', fetchedAt),
    model: { ...unavailable('No validated model is enabled for this match state.', fetchedAt), source: 'Playoff Pulse' },
    markets: { ...unavailable('Bookmaker prices require a free Odds API key and verified matching coverage.', fetchedAt), source: 'The Odds API' },
  };
}
