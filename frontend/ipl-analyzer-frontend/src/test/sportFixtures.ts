import type { LeagueIndex } from '../data/leagues';
import type { SportPayload } from '../data/sportData';
import { leagueIndex } from './fixtures';

const teams = [
  { key: 'Arsenal', shortName: 'ARS', fullName: 'Arsenal', color: '#EF0107', textColor: '#FFFFFF' },
  { key: 'Chelsea', shortName: 'CHE', fullName: 'Chelsea', color: '#034694', textColor: '#FFFFFF' },
  { key: 'Liverpool', shortName: 'LIV', fullName: 'Liverpool', color: '#C8102E', textColor: '#FFFFFF' },
  { key: 'Spurs', shortName: 'TOT', fullName: 'Tottenham Hotspur', color: '#132257', textColor: '#FFFFFF' },
];

const row = (rank: number, key: string, wins: number, draws: number, losses: number, gf: number, ga: number, form: string[]) => {
  const team = teams.find((item) => item.key === key)!;
  return {
    teamKey: key,
    shortName: team.shortName,
    fullName: team.fullName,
    rank,
    played: wins + draws + losses,
    wins,
    draws,
    losses,
    goalsFor: gf,
    goalsAgainst: ga,
    goalDifference: gf - ga,
    points: wins * 3 + draws,
    form,
    remaining: 3,
  };
};

export const footballPayload: SportPayload = {
  metadata: {
    season: '2026-27',
    generated_at: '2026-10-03T19:30:00Z',
    source: 'FixtureDownload',
    source_url: 'https://fixturedownload.com/',
    data_freshness_status: 'fresh',
    season_status: 'in_progress',
    warnings: [],
  },
  league: {
    id: 'epl-2026-27',
    configId: 'epl',
    sport: 'football',
    name: 'Premier League',
    shortName: 'Premier League',
    season: '2026-27',
    seasonLabel: '2026-27',
    tiers: [
      { key: 'title', label: 'Title', kind: 'top', size: 1 },
      { key: 'top2', label: 'Top 2', kind: 'top', size: 2 },
      { key: 'relegation', label: 'Relegation', shortLabel: 'Drop', kind: 'bottom', size: 1 },
    ],
    columns: [
      { key: 'played', label: 'P' },
      { key: 'wins', label: 'W' },
      { key: 'draws', label: 'D' },
      { key: 'losses', label: 'L' },
      { key: 'goalDifference', label: 'GD', signed: true },
      { key: 'points', label: 'Pts', strong: true },
    ],
    outcomes: ['home', 'draw', 'away'],
    teams,
  },
  standings: [
    row(1, 'Arsenal', 3, 0, 0, 7, 1, ['W', 'W', 'W']),
    row(2, 'Liverpool', 2, 0, 1, 5, 3, ['W', 'L', 'W']),
    row(3, 'Chelsea', 1, 0, 2, 3, 5, ['L', 'W', 'L']),
    row(4, 'Spurs', 0, 0, 3, 1, 7, ['L', 'L', 'L']),
  ],
  fixtures: [
    {
      id: '7',
      round: 4,
      date: '2099-10-10T14:00:00Z',
      home: 'Spurs',
      away: 'Arsenal',
      venue: 'Tottenham Hotspur Stadium',
      probabilities: { home: 0.2, draw: 0.25, away: 0.55 },
    },
    {
      id: '8',
      round: 4,
      date: '2099-10-10T16:30:00Z',
      home: 'Chelsea',
      away: 'Liverpool',
      venue: 'Stamford Bridge',
      probabilities: { home: 0.35, draw: 0.27, away: 0.38 },
    },
  ],
  results: [
    { id: '6', round: 3, date: '2026-09-27T14:00:00Z', home: 'Arsenal', away: 'Chelsea', homeScore: 2, awayScore: 0 },
    { id: '5', round: 3, date: '2026-09-27T14:00:00Z', home: 'Liverpool', away: 'Spurs', homeScore: 3, awayScore: 1 },
  ],
  analysis: {
    method: 'Monte Carlo',
    simulations: 20000,
    model: 'Poisson goals model',
    modelNotes: ['Each remaining match is simulated 20,000 times.'],
    probabilities: {
      Arsenal: { title: 81.2, top2: 99.96, relegation: 0 },
      Liverpool: { title: 17.5, top2: 80.1, relegation: 0.04 },
      Chelsea: { title: 1.3, top2: 19.9, relegation: 12.5 },
      Spurs: { title: 0, top2: 0.04, relegation: 87.46 },
    },
    positions: {
      Arsenal: [81.2, 18.76, 0.04, 0],
      Liverpool: [17.5, 62.6, 19.86, 0.04],
      Chelsea: [1.3, 18.6, 67.6, 12.5],
      Spurs: [0, 0.04, 12.46, 87.5],
    },
    expected: {
      Arsenal: { points: 15.1, position: 1.2 },
      Liverpool: { points: 11.4, position: 2 },
      Chelsea: { points: 6.2, position: 2.9 },
      Spurs: { points: 2.3, position: 3.9 },
    },
  },
  matchesThatMatter: [
    {
      fixtureId: '7',
      date: '2099-10-10T14:00:00Z',
      home: 'Spurs',
      away: 'Arsenal',
      tier: 'title',
      tierLabel: 'Title',
      team: 'Arsenal',
      swing: 30.2,
      ifHome: 58.1,
      ifDraw: 74,
      ifAway: 88.3,
    },
  ],
  movement: { since: '2026-10-02T19:30:00Z', changes: { Arsenal: { title: 6.5 }, Spurs: { relegation: 9.1 } } },
};

export const multiSportIndex: LeagueIndex = {
  default: 'ipl-2026',
  leagues: [
    {
      id: 'epl-2026-27',
      sport: 'football',
      name: 'Premier League',
      shortName: 'Premier League',
      seasonLabel: '2026-27',
      status: 'in_progress',
      champion: null,
      generatedAt: '2026-10-03T19:30:00Z',
      path: 'data/epl-2026-27.json',
    },
    ...leagueIndex.leagues,
  ],
};

/** Four NFL-style teams in two conferences, with conference seeds and a playoff line after one team. */
export const conferencePayload: SportPayload = {
  ...footballPayload,
  league: {
    ...footballPayload.league,
    id: 'nfl-2026',
    configId: 'nfl',
    sport: 'american-football',
    name: 'NFL',
    shortName: 'NFL',
    headline: 'NFL Playoff & Super Bowl Odds',
    season: '2026',
    seasonLabel: '2026',
    tiers: [
      { key: 'playoffs', label: 'Playoffs', kind: 'playoffs' },
      { key: 'title', label: 'Super Bowl', kind: 'champion', shortLabel: 'SB' },
    ],
    columns: [
      { key: 'wins', label: 'W' },
      { key: 'losses', label: 'L' },
      { key: 'pct', label: 'PCT', format: 'pct', strong: true },
      { key: 'streak', label: 'STRK', optional: true },
    ],
    outcomes: ['home', 'away'],
    groups: [
      { key: 'AFC', label: 'AFC', teams: ['Chelsea', 'Arsenal'], cutoffs: [{ after: 1, label: 'Playoff line' }] },
      { key: 'NFC', label: 'NFC', teams: ['Liverpool', 'Spurs'], cutoffs: [{ after: 1, label: 'Playoff line' }] },
    ],
    rankLabel: 'League',
    positionLabel: 'Conference seed',
    positionZones: [{ to: 1, kind: 'top' }],
  },
  standings: footballPayload.standings.map((row) => ({
    ...row,
    record: `${row.wins}-${row.losses}`,
    pct: row.wins / Math.max(row.played, 1),
    streak: 'W1',
    conference: ['Arsenal', 'Chelsea'].includes(row.teamKey) ? 'AFC' : 'NFC',
    seed: row.teamKey === 'Chelsea' || row.teamKey === 'Liverpool' ? 1 : 2,
  })),
  analysis: {
    ...footballPayload.analysis,
    probabilities: {
      Arsenal: { playoffs: 40, title: 20 },
      Chelsea: { playoffs: 60, title: 30 },
      Liverpool: { playoffs: 70, title: 35 },
      Spurs: { playoffs: 30, title: 15 },
    },
    positions: { Arsenal: [40, 60], Chelsea: [60, 40], Liverpool: [70, 30], Spurs: [30, 70] },
    expected: {
      Arsenal: { wins: 9.1, seed: 1.6 },
      Chelsea: { wins: 9.8, seed: 1.4 },
      Liverpool: { wins: 10.2, seed: 1.3 },
      Spurs: { wins: 8.4, seed: 1.7 },
    },
  },
  matchesThatMatter: [],
  movement: null,
};
