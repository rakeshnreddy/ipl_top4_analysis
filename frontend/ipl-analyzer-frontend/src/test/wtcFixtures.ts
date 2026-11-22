import type { LeagueIndex } from '../data/leagues';
import type { WtcPayload, WtcSeries, WtcStanding, WtcTest } from '../wtc/wtcData';
import { leagueIndex } from './fixtures';

const team = (key: string, fullName: string, color: string, textColor = '#FFFFFF') => ({ key, shortName: key, fullName, color, textColor });
const TEAMS = [
  team('SA', 'South Africa', '#007749'),
  team('AUS', 'Australia', '#FFCD00', '#000000'),
  team('IND', 'India', '#2D7FF9'),
  team('ENG', 'England', '#1C2C5B'),
];

const row = (rank: number, key: string, record: [number, number, number, number], deducted: number, points: number, pct: number | null, extra: Partial<WtcStanding> = {}): WtcStanding => {
  const meta = TEAMS.find((item) => item.key === key)!;
  const [played, won, lost, drawn] = record;
  return {
    ...meta, teamKey: key, rank, played, won, lost, drawn, tied: 0, pointsWon: points + deducted, deducted, points, pct,
    seriesWon: 1, seriesPlayed: 1, awayPlayed: 1, awayPct: 50, testsLeft: 3, bestPct: 80, worstPct: 30, form: ['W'], ...extra,
  };
};

const test = (key: string, number: number, start: string, state: WtcTest['state'], extra: Partial<WtcTest> = {}): WtcTest => ({
  key, number, start, end: start, venue: 'Ground', country: null, neutral: false, state, tentative: false, precision: 'day', ...extra,
});

const SERIES: WtcSeries[] = [
  {
    id: 'sa-aus-2026', name: 'Australia tour of South Africa', host: 'SA', visitor: 'AUS', status: 'complete', start: '2026-10-09', end: '2026-10-31',
    scheduled: 3, counted: 2, score: { SA: 1, AUS: 0, draws: 1 }, winner: 'SA',
    tests: [
      test('sa-aus-2026-1', 1, '2026-10-09', 'result', { venue: 'Kingsmead, Durban', country: 'SA', result: { kind: 'host', winner: 'SA', margin: '214 runs', points: { SA: 12, AUS: 0 }, source: 'Cricsheet' }, deductions: [{ team: 'AUS', points: 3, note: '3 overs short', source: 'https://example.org/icc' }] }),
      test('sa-aus-2026-2', 2, '2026-10-18', 'result', { venue: 'Newlands, Cape Town', country: 'SA', result: { kind: 'abandoned', winner: null, margin: '', points: { SA: 4, AUS: 4 }, source: 'ICC' } }),
      test('sa-aus-2026-3', 3, '2026-10-27', 'cancelled', { venue: "St George's Park, Gqeberha", country: 'SA' }),
    ],
  },
  {
    id: 'ind-eng-2026', name: 'England tour of India', host: 'IND', visitor: 'ENG', status: 'in_progress', start: '2026-11-10', end: '2026-12-01',
    scheduled: 3, counted: 3, score: { IND: 1, ENG: 0, draws: 0 }, winner: null,
    tests: [
      test('ind-eng-2026-1', 1, '2026-11-10', 'result', { venue: 'Eden Gardens, Kolkata', country: 'IND', result: { kind: 'host', winner: 'IND', margin: '7 wickets', points: { IND: 12, ENG: 0 }, source: 'CricketData' } }),
      test('ind-eng-2026-2', 2, '2026-11-19', 'in_progress', { venue: 'Wankhede Stadium, Mumbai', country: 'IND', live: 'Day 3: Stumps' }),
      test('ind-eng-2026-3', 3, '2026-11-28', 'scheduled', { venue: 'Arun Jaitley Stadium, Delhi', country: 'IND', odds: { host: 60, draw: 15, visitor: 25 } }),
    ],
  },
  {
    id: 'eng-sa-2027', name: 'South Africa tour of England', host: 'ENG', visitor: 'SA', status: 'scheduled', start: '2027-01-10', end: '2027-01-14',
    scheduled: 1, counted: 1, score: { ENG: 0, SA: 0, draws: 0 }, winner: null,
    tests: [test('eng-sa-2027-1', 1, '2027-01-10', 'scheduled', { venue: 'Dubai International Cricket Stadium', country: 'UAE', neutral: true, odds: { host: 30, draw: 20, visitor: 50 } })],
  },
  {
    id: 'aus-ind-2027', name: 'Border–Gavaskar Trophy', host: 'AUS', visitor: 'IND', status: 'scheduled', start: '2027-02-01', end: '2027-02-28',
    scheduled: 1, counted: 1, score: { AUS: 0, IND: 0, draws: 0 }, winner: null,
    tests: [test('aus-ind-2027-1', 1, '2027-02-01', 'scheduled', { venue: null, country: 'AUS', precision: 'month', tentative: true, odds: { host: 50, draw: 10, visitor: 40 } })],
  },
];

/** A small cycle in its round stage: every kind of Test state, deductions and exact claims. */
export const wtcPayload: WtcPayload = {
  metadata: {
    season: '2025-27',
    generated_at: '2026-11-21T19:30:00Z',
    source: 'CricketData and Cricsheet',
    source_url: 'https://cricsheet.org/',
    license: 'ODC-By 1.0',
    license_url: 'https://opendatacommons.org/licenses/by/1-0/',
    data_freshness_status: 'fresh',
    season_status: 'league_stage',
    warnings: [],
    notes: ['IND, ENG are level on 50.00% and are ordered by series wins (clause 16.12).'],
  },
  league: {
    id: 'wtc-2025-27', sport: 'cricket', engine: 'wtc', name: 'ICC World Test Championship', shortName: 'WTC', season: '2025-27', seasonLabel: '2025-27',
    points: { win: 12, tie: 6, draw: 4, loss: 0 }, finalists: 2,
    tiers: [{ key: 'final', label: 'Reach the final', shortLabel: 'Final', kind: 'top', size: 2 }, { key: 'title', label: 'Win the title', shortLabel: 'Title', kind: 'champion' }],
    columns: [{ key: 'played', label: 'M' }, { key: 'pct', label: 'PCT', decimals: 2 }],
    teams: TEAMS,
    tiebreakers: ['Percentage of points (PCT)', 'Series wins', 'Away PCT', 'ICC Test ranking at the end of the competition window'],
    rankings: { order: ['SA', 'AUS', 'IND', 'ENG'], asOf: '17 November 2026', source: 'https://www.icc-cricket.com/rankings' },
    testsTotal: 8, testsLeft: 4, seasonStart: '2025-06-17', seasonEnd: '2027-06-14',
    rules: { summary: 'A win is worth 12 points.', sources: [{ label: 'ICC Playing Conditions', url: 'https://example.org/pc.pdf' }] },
    deductions: [{ team: 'AUS', points: 3, test: 'sa-aus-2026-1', note: '3 overs short at Durban', source: 'https://example.org/icc' }],
  },
  standings: [
    row(1, 'SA', [2, 1, 0, 1], 0, 16, 66.67),
    row(2, 'AUS', [2, 0, 1, 1], 3, 1, 4.17, { awayPct: 4.17 }),
    row(3, 'IND', [1, 1, 0, 0], 0, 6, 50.0),
    row(4, 'ENG', [1, 0, 1, 0], 0, 0, 0.0, { bestPct: 32.5, worstPct: 0 }),
  ],
  series: SERIES,
  fixtures: [
    { id: 'ind-eng-2026-2', series: 'ind-eng-2026', number: 2, host: 'IND', visitor: 'ENG', start: '2026-11-19', end: '2026-11-23', venue: 'Wankhede Stadium, Mumbai', country: 'IND', neutral: false, state: 'in_progress', precision: 'day', tentative: false, odds: { host: 55, draw: 20, visitor: 25 } },
    { id: 'ind-eng-2026-3', series: 'ind-eng-2026', number: 3, host: 'IND', visitor: 'ENG', start: '2026-11-28', end: '2026-12-02', venue: 'Arun Jaitley Stadium, Delhi', country: 'IND', neutral: false, state: 'scheduled', precision: 'day', tentative: false, odds: { host: 60, draw: 15, visitor: 25 } },
    { id: 'eng-sa-2027-1', series: 'eng-sa-2027', number: 1, host: 'ENG', visitor: 'SA', start: '2027-01-10', end: '2027-01-14', venue: 'Dubai International Cricket Stadium', country: 'UAE', neutral: true, state: 'scheduled', precision: 'day', tentative: false, odds: { host: 30, draw: 20, visitor: 50 } },
    { id: 'aus-ind-2027-1', series: 'aus-ind-2027', number: 1, host: 'AUS', visitor: 'IND', start: '2027-02-01', end: '2027-02-28', venue: null, country: 'AUS', neutral: false, state: 'scheduled', precision: 'month', tentative: true, odds: { host: 50, draw: 10, visitor: 40 } },
  ],
  results: [],
  final: {
    venue: 'The Oval', city: 'London', country: 'ENG', start: '2027-06-09', end: '2027-06-13', reserveDay: null, drawResult: 'joint', tentative: false,
    note: '', sources: [{ label: 'ICC: final venue and dates', url: 'https://example.org/final' }], finalists: null, standingsClose: '2027-04-30',
    matchups: [{ teams: ['IND', 'SA'], chance: 55.5 }, { teams: ['AUS', 'SA'], chance: 30 }],
  },
  analysis: {
    method: 'Monte Carlo', simulations: 20000, model: 'Davidson Test rating model',
    modelNotes: ['Each Test is rated by a Davidson model.'],
    probabilities: {
      SA: { final: 85, title: 40.4, joint: 5, champion: 45.4 },
      IND: { final: 70, title: 30, joint: 4, champion: 34 },
      AUS: { final: 45, title: 15, joint: 1, champion: 16 },
      ENG: { final: 0, title: 0, joint: 0, champion: 0 },
    },
    positions: {
      SA: [50, 35, 15, 0],
      IND: [30, 40, 30, 0],
      AUS: [20, 25, 55, 0],
      ENG: [0, 0, 0, 100],
    },
    expectedPct: { SA: 60, IND: 55, AUS: 40, ENG: 10 },
    needs: {
      SA: { status: 'in-control', testsLeft: 1, bestPct: 77.78, worstPct: 44.44, ownDestiny: 'yes', statements: ['In control: winning all 1 remaining Test would take them to the final, whatever else happens.'] },
      AUS: { status: 'needs-help', testsLeft: 1, bestPct: 36.11, worstPct: 2.78, ownDestiny: 'no', statements: ['Needs help: even winning all 1 remaining Test could leave two teams above them.'] },
      IND: { status: 'level-only', testsLeft: 3, bestPct: 80, worstPct: 30, ownDestiny: 'level', statements: ['Can still finish level on PCT for a final place, but not above: the tie-breakers would decide.'] },
      ENG: { status: 'eliminated', testsLeft: 3, bestPct: 32.5, worstPct: 0, ownDestiny: 'no', statements: ['Cannot reach the final on results: at least two teams will finish above them whatever happens.'] },
    },
    swing: [{ fixtureId: 'ind-eng-2026-3', series: 'ind-eng-2026', number: 3, date: '2026-11-28', host: 'IND', visitor: 'ENG', team: 'AUS', ifHost: 30, ifDraw: 45.5, ifVisitor: 60, swing: 30 }],
    ratings: { SA: 0.8, AUS: 0.7, IND: 0.6, ENG: 0.3 },
  },
};

/** The table is settled: SA and IND meet in the final. */
export const wtcFinalAhead: WtcPayload = {
  ...wtcPayload,
  metadata: { ...wtcPayload.metadata, season_status: 'playoffs' },
  league: { ...wtcPayload.league, testsLeft: 0 },
  fixtures: [],
  final: { ...wtcPayload.final, finalists: ['SA', 'IND'], odds: { SA: 47.5, draw: 9, IND: 43.5 }, matchups: [] },
  analysis: {
    ...wtcPayload.analysis,
    probabilities: {
      SA: { final: 100, title: 47, joint: 9.2, champion: 56.2 },
      IND: { final: 100, title: 43.8, joint: 9.2, champion: 53 },
      AUS: { final: 0, title: 0, joint: 0, champion: 0 },
      ENG: { final: 0, title: 0, joint: 0, champion: 0 },
    },
    needs: {
      ...wtcPayload.analysis.needs,
      SA: { ...wtcPayload.analysis.needs.SA, status: 'clinched', statements: ['Through to the final, whatever the remaining results.'] },
      IND: { ...wtcPayload.analysis.needs.IND, status: 'clinched', statements: ['Through to the final, whatever the remaining results.'] },
      AUS: { ...wtcPayload.analysis.needs.AUS, status: 'eliminated' },
    },
    swing: [],
  },
};

const completeBase: WtcPayload = {
  ...wtcFinalAhead,
  metadata: { ...wtcFinalAhead.metadata, season_status: 'complete' },
  analysis: { ...wtcFinalAhead.analysis, method: 'Final standings', simulations: 0 },
};

/** South Africa won the final. */
export const wtcComplete: WtcPayload = {
  ...completeBase,
  final: { ...completeBase.final, odds: undefined, result: { kind: 'win', winner: 'SA', joint: null, margin: '5 wickets' } },
  playoffs: { champion: 'SA', jointChampions: null },
};

/** A drawn final: joint champions. */
export const wtcJoint: WtcPayload = {
  ...completeBase,
  final: { ...completeBase.final, odds: undefined, result: { kind: 'joint', winner: null, joint: ['SA', 'IND'], margin: 'drawn' } },
  playoffs: { champion: null, jointChampions: ['SA', 'IND'] },
};

/** Before the first Test. */
export const wtcPreSeason: WtcPayload = {
  ...wtcPayload,
  metadata: { ...wtcPayload.metadata, season_status: 'pre_season', notes: [] },
  standings: wtcPayload.standings.map((item) => ({ ...item, played: 0, won: 0, lost: 0, drawn: 0, points: 0, pointsWon: 0, deducted: 0, pct: null, seriesWon: 0, seriesPlayed: 0, awayPct: null })),
  league: { ...wtcPayload.league, deductions: [] },
};

export const wtcIndex: LeagueIndex = {
  ...leagueIndex,
  default: 'hub',
  leagues: [
    ...leagueIndex.leagues,
    {
      id: 'wtc-2025-27', sport: 'cricket', engine: 'wtc', name: 'ICC World Test Championship', shortName: 'WTC', seasonLabel: '2025-27',
      status: 'league_stage', champion: null, started: true, facts: [{ label: 'Likely final', value: 'SA v IND' }],
      generatedAt: '2026-11-21T19:30:00Z', path: 'data/wtc-2025-27.json',
    },
  ],
};
