/** Synthetic contracts exclusively for tests. Never imported by production modules. */
import type { MatchDetailSnapshot, MatchListSnapshot, MatchSummary, Part } from './types';
const time = '2026-10-23T12:00:00Z';
export const summaryFixture = (id = 'synthetic-one'): MatchSummary => ({
  id,
  providerIds: {},
  teams: [{
    id: 'a',
    name: 'Synthetic Alpha',
    shortName: 'ALP'
  }, {
    id: 'b',
    name: 'Synthetic Beta',
    shortName: 'BET'
  }],
  competition: {
    id: 'test',
    name: 'Synthetic test competition'
  },
  format: 'T20',
  gender: 'women',
  state: 'live',
  statusText: 'Synthetic innings in progress',
  startTime: time,
  venue: 'Test ground',
  scores: [{
    id: 'inn-1',
    team: 'Synthetic Alpha',
    label: 'First innings',
    runs: 100,
    wickets: 2,
    legalBalls: 72,
    overs: '12.0'
  }],
  observedAt: time,
  fetchedAt: time,
  revision: 'revision-1',
  capabilities: {
    scorecard: false,
    commentary: false,
    model: false,
    markets: false
  },
  source: {
    id: 'test',
    name: 'Synthetic test provider',
    url: 'https://example.test'
  }
});
const unavailable = <T,>(): Part<T> => ({
  status: 'unavailable',
  source: 'Synthetic test provider',
  observedAt: null,
  fetchedAt: time,
  reason: 'No test coverage',
  data: null
});
export const listFixture = (): MatchListSnapshot => ({
  schemaVersion: 1,
  status: 'ok',
  message: null,
  source: summaryFixture().source,
  generatedAt: time,
  refreshAfterSeconds: 30,
  staleAfterSeconds: 90,
  coverage: [],
  matches: [summaryFixture()]
});
export const detailFixture = (id = 'synthetic-one'): MatchDetailSnapshot => ({
  ...listFixture(),
  match: summaryFixture(id),
  scorecard: unavailable(),
  commentary: unavailable(),
  model: unavailable(),
  markets: unavailable()
});
