import type { LeagueIndex } from '../data/leagues';
import type { F1Payload } from '../f1/f1Data';
import { leagueIndex } from './fixtures';

const driver = (rank: number, key: string, code: string, name: string, team: string, points: number, wins: number, podiums: number, racing = true) => ({
  teamKey: key,
  shortName: code,
  fullName: name,
  number: null,
  team,
  teams: [team],
  rank,
  points,
  wins,
  podiums,
  sprintWins: 0,
  played: 16,
  racing,
});

/** A small F1 2026 season after round 16: four drivers, three teams, two events to go. */
export const f1Payload: F1Payload = {
  metadata: {
    season: '2026',
    generated_at: '2026-10-04T21:00:00Z',
    source: 'Jolpica F1 API',
    source_url: 'https://github.com/jolpica/jolpica-f1',
    data_freshness_status: 'fresh',
    season_status: 'in_progress',
    warnings: [],
    notes: [],
  },
  league: {
    id: 'f1-2026',
    configId: 'f1',
    sport: 'motorsport',
    name: 'Formula 1 World Championship',
    shortName: 'F1',
    headline: "F1 Title Odds: Drivers' & Constructors' Championships",
    season: '2026',
    seasonLabel: '2026',
    tiers: [
      { key: 'title', label: "Drivers' title", shortLabel: 'Title', kind: 'champion' },
      { key: 'top3', label: 'Top 3', kind: 'top', size: 3 },
    ],
    constructorTiers: [{ key: 'title', label: "Constructors' title", shortLabel: 'Title', kind: 'champion' }],
    teams: [
      { key: 'red_bull', shortName: 'RBR', fullName: 'Red Bull Racing', color: '#3671C6', textColor: '#FFFFFF' },
      { key: 'mercedes', shortName: 'MER', fullName: 'Mercedes', color: '#27F4D2', textColor: '#000000' },
      { key: 'rb', shortName: 'RB', fullName: 'Racing Bulls', color: '#6692FF', textColor: '#000000' },
    ],
    rounds: 18,
    eventsLeft: 2,
    rules: {
      summary: 'Grand Prix points 25-18-15-12-10-8-6-4-2-1, sprint points 8-7-6-5-4-3-2-1.',
      sources: [{ label: 'FIA 2026 Formula 1 Regulations, Section A', url: 'https://www.fia.com/' }],
    },
  },
  standings: [
    driver(1, 'max_verstappen', 'VER', 'Max Verstappen', 'red_bull', 300, 9, 12),
    driver(2, 'antonelli', 'ANT', 'Kimi Antonelli', 'mercedes', 280, 5, 11),
    driver(3, 'russell', 'RUS', 'George Russell', 'mercedes', 200, 2, 8),
    driver(4, 'tsunoda', 'TSU', 'Yuki Tsunoda', 'rb', 1, 0, 0, false),
  ],
  constructorStandings: [
    { teamKey: 'mercedes', shortName: 'MER', fullName: 'Mercedes', rank: 1, points: 480, wins: 7, podiums: 19, drivers: ['antonelli', 'russell'] },
    { teamKey: 'red_bull', shortName: 'RBR', fullName: 'Red Bull Racing', rank: 2, points: 300, wins: 9, podiums: 12, drivers: ['max_verstappen'] },
    { teamKey: 'rb', shortName: 'RB', fullName: 'Racing Bulls', rank: 3, points: 1, wins: 0, podiums: 0, drivers: [] },
  ],
  events: [
    {
      key: '2026-17-sprint',
      round: 17,
      kind: 'sprint',
      name: 'Singapore Grand Prix',
      date: '2026-10-10T09:00:00Z',
      circuit: 'Marina Bay Street Circuit',
      locality: 'Marina Bay',
      country: 'Singapore',
      favourites: [
        { driver: 'max_verstappen', win: 41.5, podium: 80.2 },
        { driver: 'antonelli', win: 33.1, podium: 75 },
      ],
    },
    {
      key: '2026-17-race',
      round: 17,
      kind: 'race',
      name: 'Singapore Grand Prix',
      date: '2026-10-11T12:00:00Z',
      circuit: 'Marina Bay Street Circuit',
      locality: 'Marina Bay',
      country: 'Singapore',
      favourites: [
        { driver: 'antonelli', win: 38, podium: 77 },
        { driver: 'max_verstappen', win: 37, podium: 76 },
      ],
    },
  ],
  results: [
    {
      key: '2026-16-race',
      round: 16,
      kind: 'race',
      name: 'Bahrain Grand Prix in Malaysia',
      date: '2026-10-04T07:00:00Z',
      circuit: 'Sepang',
      locality: 'Kuala Lumpur',
      country: 'Malaysia',
      podium: ['max_verstappen', 'antonelli', 'russell'],
    },
  ],
  analysis: {
    method: 'Monte Carlo',
    simulations: 20000,
    model: 'Plackett-Luce pace model',
    modelNotes: ['Pace comes from a rank-ordered logit (Plackett-Luce) model of finishing orders.'],
    probabilities: {
      max_verstappen: { title: 54, top3: 99 },
      antonelli: { title: 44.5, top3: 98 },
      russell: { title: 1.5, top3: 98 },
      tsunoda: { title: 0, top3: 0 },
    },
    constructorProbabilities: { mercedes: { title: 80 }, red_bull: { title: 20 }, rb: { title: 0 } },
  },
};

export const f1Index: LeagueIndex = {
  ...leagueIndex,
  default: 'hub',
  leagues: [
    ...leagueIndex.leagues,
    {
      id: 'f1-2026',
      sport: 'motorsport',
      name: 'Formula 1 World Championship',
      shortName: 'F1',
      seasonLabel: '2026',
      status: 'in_progress',
      champion: null,
      started: true,
      facts: [
        { label: "Drivers' title favourite", value: 'VER 54%' },
        { label: "Constructors' title favourite", value: 'MER 80%' },
      ],
      generatedAt: '2026-10-04T21:00:00Z',
      path: 'data/f1-2026.json',
    },
  ],
};
