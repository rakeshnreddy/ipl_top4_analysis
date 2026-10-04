import { vi } from 'vitest';
import type { IplSeasonPayload } from '../data/iplData';
import type { LeagueIndex } from '../data/leagues';
import type { ReelsManifest } from '../data/reelsManifest';

export const standings: IplSeasonPayload['standings'] = [
  { teamKey: 'Punjab', shortName: 'PBKS', fullName: 'Punjab Kings', matches: 8, wins: 6, losses: 1, noResult: 1, points: 13, nrr: 1.043, rank: 1, remainingMatches: 6 },
  { teamKey: 'Hyderabad', shortName: 'SRH', fullName: 'Sunrisers Hyderabad', matches: 9, wins: 6, losses: 3, noResult: 0, points: 12, nrr: 0.832, rank: 3, remainingMatches: 5 },
  { teamKey: 'Bangalore', shortName: 'RCB', fullName: 'Royal Challengers Bengaluru', matches: 9, wins: 6, losses: 3, noResult: 0, points: 12, nrr: 1.42, rank: 2, remainingMatches: 5 },
  { teamKey: 'Rajasthan', shortName: 'RR', fullName: 'Rajasthan Royals', matches: 10, wins: 6, losses: 4, noResult: 0, points: 12, nrr: 0.51, rank: 4, remainingMatches: 4 },
  { teamKey: 'Gujarat', shortName: 'GT', fullName: 'Gujarat Titans', matches: 9, wins: 5, losses: 4, noResult: 0, points: 10, nrr: -0.192, rank: 5, remainingMatches: 5 },
  { teamKey: 'Delhi', shortName: 'DC', fullName: 'Delhi Capitals', matches: 9, wins: 4, losses: 5, noResult: 0, points: 8, nrr: -0.895, rank: 6, remainingMatches: 5 },
  { teamKey: 'Chennai', shortName: 'CSK', fullName: 'Chennai Super Kings', matches: 8, wins: 3, losses: 5, noResult: 0, points: 6, nrr: -0.121, rank: 7, remainingMatches: 6 },
  { teamKey: 'Kolkata', shortName: 'KKR', fullName: 'Kolkata Knight Riders', matches: 8, wins: 2, losses: 5, noResult: 1, points: 5, nrr: -0.751, rank: 8, remainingMatches: 6 },
  { teamKey: 'Mumbai', shortName: 'MI', fullName: 'Mumbai Indians', matches: 8, wins: 2, losses: 6, noResult: 0, points: 4, nrr: -0.784, rank: 9, remainingMatches: 6 },
  { teamKey: 'Lucknow', shortName: 'LSG', fullName: 'Lucknow Super Giants', matches: 8, wins: 2, losses: 6, noResult: 0, points: 4, nrr: -1.106, rank: 10, remainingMatches: 6 },
];

export const mockPayload: IplSeasonPayload = {
  metadata: {
    season: 2026,
    generated_at: '2026-05-01T21:13:08Z',
    source: 'CricketData',
    source_url: 'https://cricketdata.org/',
    data_freshness_status: 'warning',
    warnings: ['Test source warning'],
  },
  standings,
  fixtures: [
    {
      id: 'cricbuzz-44',
      matchNo: 44,
      teamA: 'Chennai',
      teamB: 'Mumbai',
      dateTimeGMT: '2026-05-02T14:00:00Z',
      dateTimeLocal: 'Tomorrow , 7:30 PM LOCAL',
      venue: 'MA Chidambaram Stadium, Chennai',
      status: 'scheduled',
      sourceUrl: 'https://www.cricbuzz.com/live-cricket-scores/151987/csk-vs-mi-44th-match-ipl-2026',
    },
  ],
  analysis: {
    method: 'Exhaustive',
    simulationCount: 2,
    generatedAt: '2026-05-01T21:13:08Z',
    overallProbabilities: Object.fromEntries(
      standings.map((team) => [team.teamKey, { top4: team.rank <= 4 ? 100 : 0, top2: team.rank <= 2 ? 100 : 0 }]),
    ),
    teamAnalysis: { '4': {}, '2': {} },
    qualificationPath: {
      '4': Object.fromEntries(standings.map((team) => [team.teamKey, { possible: 0, guaranteed: null, target_matches: team.remainingMatches, method: 'Exhaustive' }])),
      '2': Object.fromEntries(standings.map((team) => [team.teamKey, { possible: 0, guaranteed: null, target_matches: team.remainingMatches, method: 'Exhaustive' }])),
    },
  },
};

export const mockManifest: ReelsManifest = {
  latestDate: '2026-05-04',
  dates: ['2026-05-04'],
  slides: [
    {
      date: '2026-05-04',
      fileName: 'slide-01-overview.png',
      path: 'social/instagram-carousel/2026-05-04/slide-01-overview.png',
      downloadName: 'ipl-playoff-pulse-2026-05-04-slide-01-overview.png',
      imageWidth: 1080,
      imageHeight: 1920,
    },
    {
      date: '2026-05-04',
      fileName: 'slide-02-pbks.png',
      path: 'social/instagram-carousel/2026-05-04/slide-02-pbks.png',
      downloadName: 'ipl-playoff-pulse-2026-05-04-slide-02-pbks.png',
      imageWidth: 1080,
      imageHeight: 1920,
    },
  ],
  generatedAt: '2026-05-04T09:00:00Z',
  source: {
    name: 'CricketData',
    url: 'https://cricketdata.org/',
    dataGeneratedAt: '2026-05-04T08:06:47Z',
  },
  warnings: [],
  imageWidth: 1080,
  imageHeight: 1920,
  latestPackPath: 'social/instagram-carousel/2026-05-04/',
  latestPreviewPath: 'social/instagram-carousel/latest-overview.png',
};

/** Stub fetch for the IPL payload and Reels manifest, plus any extra `routes` keyed by URL suffix. */
export function installFetch(
  payload: IplSeasonPayload = mockPayload,
  manifest: ReelsManifest = mockManifest,
  routes: Record<string, unknown> = {},
) {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const route = Object.keys(routes).find((suffix) => url.endsWith(suffix));
    if (route) {
      return Promise.resolve({
        ok: true,
        json: async () => routes[route],
      } as Response);
    }
    if (url.endsWith('/data/ipl-2026.json')) {
      return Promise.resolve({
        ok: true,
        json: async () => payload,
      } as Response);
    }
    if (url.endsWith('/social/instagram-carousel/manifest.json')) {
      return Promise.resolve({
        ok: true,
        json: async () => manifest,
      } as Response);
    }
    return Promise.resolve({
      ok: false,
      status: 404,
      json: async () => ({}),
    } as Response);
  }) as typeof fetch;
}

const finalRecords: Array<[string, string, string, number, number, number, number]> = [
  ['Bangalore', 'RCB', 'Royal Challengers Bengaluru', 9, 5, 0, 0.783],
  ['Gujarat', 'GT', 'Gujarat Titans', 9, 5, 0, 0.695],
  ['Hyderabad', 'SRH', 'Sunrisers Hyderabad', 9, 5, 0, 0.524],
  ['Rajasthan', 'RR', 'Rajasthan Royals', 8, 6, 0, 0.189],
  ['Punjab', 'PBKS', 'Punjab Kings', 7, 6, 1, 0.309],
  ['Delhi', 'DC', 'Delhi Capitals', 7, 7, 0, -0.651],
  ['Kolkata', 'KKR', 'Kolkata Knight Riders', 6, 7, 1, -0.147],
  ['Chennai', 'CSK', 'Chennai Super Kings', 6, 8, 0, -0.345],
  ['Mumbai', 'MI', 'Mumbai Indians', 4, 10, 0, -0.584],
  ['Lucknow', 'LSG', 'Lucknow Super Giants', 4, 10, 0, -0.74],
];

// Listed out of order so the test proves the ladder re-sorts by points, then NRR.
export const finalStandings: IplSeasonPayload['standings'] = [...finalRecords].reverse().map(
  ([teamKey, shortName, fullName, wins, losses, noResult, nrr]) => ({
    teamKey,
    shortName,
    fullName,
    matches: 14,
    wins,
    losses,
    noResult,
    points: wins * 2 + noResult,
    nrr,
    rank: finalRecords.findIndex((record) => record[0] === teamKey) + 1,
    remainingMatches: 0,
  }),
);

export const finalPayload: IplSeasonPayload = {
  metadata: {
    season: 2026,
    generated_at: '2026-10-01T07:54:32Z',
    source: 'Cricsheet',
    source_url: 'https://cricsheet.org/',
    source_license: 'ODC-By 1.0',
    source_license_url: 'https://opendatacommons.org/licenses/by/1-0/',
    data_freshness_status: 'fresh',
    season_status: 'complete',
    warnings: [],
  },
  standings: finalStandings,
  fixtures: [],
  playoffs: {
    matches: [
      { id: 'q1', stage: 'Qualifier 1', date: '2026-05-26', teamA: 'Bangalore', teamB: 'Gujarat', winner: 'Bangalore', result: 'RCB won by 92 runs', venue: null },
      { id: 'el', stage: 'Eliminator', date: '2026-05-27', teamA: 'Rajasthan', teamB: 'Hyderabad', winner: 'Rajasthan', result: 'RR won by 47 runs', venue: null },
      { id: 'q2', stage: 'Qualifier 2', date: '2026-05-29', teamA: 'Rajasthan', teamB: 'Gujarat', winner: 'Gujarat', result: 'GT won by 7 wickets', venue: null },
      { id: 'fi', stage: 'Final', date: '2026-05-31', teamA: 'Gujarat', teamB: 'Bangalore', winner: 'Bangalore', result: 'RCB won by 5 wickets', venue: 'Narendra Modi Stadium, Ahmedabad' },
    ],
    champion: 'Bangalore',
    runnerUp: 'Gujarat',
  },
  analysis: {
    method: 'Final standings',
    simulationCount: 1,
    generatedAt: '2026-10-01T07:54:32Z',
    overallProbabilities: Object.fromEntries(
      finalStandings.map((team) => [team.teamKey, { top4: team.rank <= 4 ? 100 : 0, top2: team.rank <= 2 ? 100 : 0 }]),
    ),
    teamAnalysis: { '4': {}, '2': {} },
    qualificationPath: { '4': {}, '2': {} },
  },
};

const wplTeams = [
  { key: 'RCB', shortName: 'RCB', fullName: 'Royal Challengers Bengaluru', color: '#EC1C24', textColor: '#FFFFFF' },
  { key: 'GG', shortName: 'GG', fullName: 'Gujarat Giants', color: '#E8601C', textColor: '#FFFFFF' },
  { key: 'DC', shortName: 'DC', fullName: 'Delhi Capitals', color: '#2561AE', textColor: '#FFFFFF' },
  { key: 'MI', shortName: 'MI', fullName: 'Mumbai Indians', color: '#004B8D', textColor: '#FFFFFF' },
  { key: 'UPW', shortName: 'UPW', fullName: 'UP Warriorz', color: '#5B2C83', textColor: '#FFFFFF' },
];

const wplRecords: Array<[string, number, number, number]> = [
  ['RCB', 6, 2, 1.247],
  ['GG', 5, 3, -0.168],
  ['DC', 4, 4, -0.055],
  ['MI', 3, 5, 0.059],
  ['UPW', 2, 6, -1.076],
];

export const wplFinalPayload: IplSeasonPayload = {
  metadata: {
    season: '2026',
    generated_at: '2026-10-01T09:00:00Z',
    source: 'Cricsheet',
    source_url: 'https://cricsheet.org/',
    source_license: 'ODC-By 1.0',
    source_license_url: 'https://opendatacommons.org/licenses/by/1-0/',
    data_freshness_status: 'fresh',
    season_status: 'complete',
    warnings: [],
  },
  league: {
    id: 'wpl-2026',
    name: "Women's Premier League",
    shortName: 'WPL',
    season: '2025/26',
    seasonLabel: '2026',
    matchesPerTeam: 8,
    qualification: [
      { size: 3, label: 'Top 3' },
      { size: 1, label: 'Top 1' },
    ],
    secondChanceStages: [],
    teams: wplTeams,
  },
  standings: wplRecords.map(([teamKey, wins, losses, nrr], index) => {
    const team = wplTeams.find((item) => item.key === teamKey)!;
    return {
      teamKey,
      shortName: team.shortName,
      fullName: team.fullName,
      matches: 8,
      wins,
      losses,
      noResult: 0,
      points: wins * 2,
      nrr,
      rank: index + 1,
      remainingMatches: 0,
    };
  }),
  fixtures: [],
  playoffs: {
    matches: [
      { id: 'el', stage: 'Eliminator', date: '2026-02-03', teamA: 'GG', teamB: 'DC', winner: 'DC', result: 'DC won by 7 wickets', venue: null },
      { id: 'fi', stage: 'Final', date: '2026-02-05', teamA: 'DC', teamB: 'RCB', winner: 'RCB', result: 'RCB won by 6 wickets', venue: null },
    ],
    champion: 'RCB',
    runnerUp: 'DC',
  },
  analysis: {
    method: 'Final standings',
    simulationCount: 1,
    generatedAt: '2026-10-01T09:00:00Z',
    overallProbabilities: Object.fromEntries(
      wplRecords.map(([teamKey], index) => [teamKey, { top4: 0, top2: 0, top3: index < 3 ? 100 : 0, top1: index < 1 ? 100 : 0 }]),
    ),
    teamAnalysis: { '4': {}, '2': {} },
    qualificationPath: { '4': {}, '2': {} },
  },
};

export const leagueIndex: LeagueIndex = {
  default: 'ipl-2026',
  leagues: [
    { id: 'ipl-2026', name: 'Indian Premier League', shortName: 'IPL', seasonLabel: '2026', status: 'complete', champion: 'RCB', generatedAt: '2026-10-01T09:00:00Z', path: 'data/ipl-2026.json' },
    { id: 'wpl-2026', name: "Women's Premier League", shortName: 'WPL', seasonLabel: '2026', status: 'complete', champion: 'RCB', generatedAt: '2026-10-01T09:00:00Z', path: 'data/wpl-2026.json' },
  ],
};

const livePairs: Array<[string, string]> = [
  ['RCB', 'GG'], ['DC', 'MI'], ['UPW', 'RCB'], ['GG', 'DC'], ['MI', 'UPW'],
  ['RCB', 'DC'], ['GG', 'MI'], ['UPW', 'DC'], ['MI', 'RCB'], ['GG', 'UPW'],
];

/** WPL 2027 during the league stage: four games each played, or none yet. */
export function wplLivePayload(played: boolean): IplSeasonPayload {
  const records: Array<[string, number, number, number | null, number, number]> = played
    ? [
        ['RCB', 4, 0, 1.2, 98.5, 71.2],
        ['GG', 3, 1, 0.4, 85, 20],
        ['DC', 2, 2, 0.1, 70, 7],
        ['MI', 1, 3, -0.5, 35, 1.5],
        ['UPW', 0, 4, -1.1, 11.5, 0.3],
      ]
    : wplTeams.map((team) => [team.key, 0, 0, null, 60, 20] as [string, number, number, number | null, number, number]);
  const pairs = played ? livePairs : [...livePairs, ...livePairs.map(([a, b]) => [b, a] as [string, string])];
  const path = (remaining: number) => ({ possible: 0, likely: 1, guaranteed: 3, target_matches: remaining, method: 'Exact all-combinations' });

  return {
    ...wplFinalPayload,
    metadata: {
      season: '2027',
      generated_at: '2027-01-22T19:30:00Z',
      source: 'CricketData',
      source_url: 'https://cricketdata.org/',
      data_freshness_status: 'fresh',
      season_status: 'league_stage',
      warnings: [],
    },
    league: { ...wplFinalPayload.league!, id: 'wpl-2027', season: '2026/27', seasonLabel: '2027' },
    standings: records.map(([teamKey, wins, losses, nrr], index) => {
      const team = wplTeams.find((item) => item.key === teamKey)!;
      return {
        teamKey,
        shortName: team.shortName,
        fullName: team.fullName,
        matches: wins + losses,
        wins,
        losses,
        noResult: 0,
        points: wins * 2,
        nrr,
        rank: index + 1,
        remainingMatches: 8 - wins - losses,
      };
    }),
    fixtures: pairs.map(([teamA, teamB], index) => ({
      id: `wpl-2027-${index + 1}`,
      matchNo: (played ? 11 : 1) + index,
      teamA,
      teamB,
      dateTimeGMT: `2027-01-${String(14 + index).padStart(2, '0')}T14:00:00Z`,
      dateTimeLocal: null,
      venue: 'Kotambi Stadium, Vadodara',
      status: 'scheduled',
      sourceUrl: 'https://api.cricapi.com/v1/series_info',
    })),
    playoffs: undefined,
    movement: played
      ? { since: '2027-01-21T19:30:00Z', tier: 'top3', changes: { RCB: 2.1, GG: 12.5, DC: -3.2, MI: -0.6, UPW: -8 } }
      : null,
    analysis: {
      method: played ? 'Exact all-combinations' : 'Exact all-combinations',
      simulationCount: 2 ** pairs.length,
      generatedAt: '2027-01-22T19:30:00Z',
      overallProbabilities: Object.fromEntries(records.map(([key, , , , top3, top1]) => [key, { top3, top1 }])),
      teamAnalysis: { '3': {}, '1': {} },
      qualificationPath: {
        '3': Object.fromEntries(records.map(([key, wins, losses]) => [key, path(8 - wins - losses)])),
        '1': Object.fromEntries(records.map(([key, wins, losses]) => [key, path(8 - wins - losses)])),
      },
    },
  };
}

const blastGroups = [
  { name: 'North', teams: ['NOT', 'YOR', 'LAN', 'DUR'] },
  { name: 'Central', teams: ['NOR', 'SOM', 'GLO', 'WAR'] },
  { name: 'South', teams: ['HAM', 'SUR', 'ESS', 'SUS'] },
];

// key, full name, wins, losses, ties, points, NRR, seed (winners, then seconds, then thirds, then fourths).
const blastRecords: Array<[string, string, number, number, number, number, number, number]> = [
  ['NOR', 'Northamptonshire Steelbacks', 9, 3, 0, 36, 0.936, 1],
  ['HAM', 'Hampshire Hawks', 8, 4, 0, 32, 0.283, 2],
  ['NOT', 'Notts Outlaws', 8, 4, 0, 32, 0.169, 3],
  ['YOR', 'Yorkshire', 7, 4, 1, 30, 0.72, 4],
  ['SOM', 'Somerset', 7, 5, 0, 28, 0.763, 5],
  ['SUR', 'Surrey', 7, 5, 0, 28, 0.666, 6],
  ['ESS', 'Essex', 7, 5, 0, 28, 0.354, 7],
  ['GLO', 'Gloucestershire', 7, 5, 0, 28, 0.288, 8],
  ['LAN', 'Lancashire Lightning', 6, 5, 1, 26, -0.335, 9],
  ['WAR', 'Warwickshire Bears', 6, 6, 0, 24, 0.367, 10],
  ['DUR', 'Durham', 5, 7, 0, 20, 0.462, 11],
  ['SUS', 'Sussex Sharks', 3, 9, 0, 10, -1.168, 12],
];

const blastFixture = (id: string, teamA: string, teamB: string) => ({
  id,
  matchNo: null,
  teamA,
  teamB,
  dateTimeGMT: '2026-07-10T17:30:00Z',
  dateTimeLocal: null,
  venue: null,
  status: 'scheduled',
  sourceUrl: '',
});

/** A T20 Blast-style season in three groups: final (with playoffs) or with two games each left (with odds). */
export function blastPayload(final: boolean): IplSeasonPayload {
  const group = (key: string) => blastGroups.find((item) => item.teams.includes(key))!;
  const odds = (seed: number) =>
    final ? { top8: seed <= 8 ? 100 : 0, top4: seed <= 4 ? 100 : 0 } : { top8: Math.max(0, 100 - seed * 8), top4: Math.max(0, 60 - seed * 6) };
  return {
    metadata: {
      season: '2026',
      generated_at: '2026-10-03T12:00:00Z',
      source: final ? 'Cricsheet' : 'CricketData',
      source_url: final ? 'https://cricsheet.org/' : 'https://cricketdata.org/',
      data_freshness_status: 'fresh',
      season_status: final ? 'complete' : 'league_stage',
      warnings: [],
    },
    league: {
      id: 't20-blast-2026',
      name: 'T20 Blast',
      shortName: 'T20 Blast',
      season: '2026',
      seasonLabel: '2026',
      matchesPerTeam: 12,
      qualification: [
        { size: 8, label: 'Quarter-finals', shortLabel: 'QF' },
        { size: 4, label: 'Home quarter-final', shortLabel: 'Home QF' },
      ],
      secondChanceStages: [],
      teams: blastRecords.map(([key, fullName]) => ({ key, shortName: key, fullName, color: '#123456', textColor: '#FFFFFF' })),
      groups: blastGroups,
      deductions: [{ team: 'SUS', points: 2, note: 'ECB financial agreement' }],
    },
    standings: blastRecords.map(([teamKey, fullName, wins, losses, ties, points, nrr, seed]) => ({
      teamKey,
      shortName: teamKey,
      fullName,
      matches: final ? 12 : 10,
      wins: final ? wins : wins - 1,
      losses: final ? losses : losses - 1,
      noResult: 0,
      ties,
      points: final ? points : points - 4,
      ...(teamKey === 'SUS' ? { deductedPoints: 2 } : {}),
      nrr,
      rank: seed,
      group: group(teamKey).name,
      groupRank: group(teamKey).teams.indexOf(teamKey) + 1,
      remainingMatches: final ? 0 : 2,
    })),
    fixtures: final
      ? []
      : blastGroups.flatMap(({ name, teams }) => [
          blastFixture(`${name}-1`, teams[0], teams[1]),
          blastFixture(`${name}-2`, teams[2], teams[3]),
          blastFixture(`${name}-3`, teams[0], teams[2]),
          blastFixture(`${name}-4`, teams[1], teams[3]),
        ]),
    playoffs: final
      ? {
          matches: [
            { id: 'qf1', stage: 'Quarter-final', date: '2026-07-15', teamA: 'NOR', teamB: 'GLO', winner: 'NOR', result: 'NOR won by 8 wickets', venue: null },
            { id: 'qf2', stage: 'Quarter-final', date: '2026-07-15', teamA: 'NOT', teamB: 'SUR', winner: 'NOT', result: 'NOT won by 7 runs', venue: null },
            { id: 'fi', stage: 'Final', date: '2026-07-18', teamA: 'NOR', teamB: 'HAM', winner: 'NOR', result: 'NOR won by 14 runs', venue: 'Edgbaston, Birmingham' },
          ],
          champion: 'NOR',
          runnerUp: 'HAM',
        }
      : undefined,
    analysis: {
      method: final ? 'Final standings' : 'Monte Carlo',
      simulationCount: final ? 1 : 40000,
      generatedAt: '2026-10-03T12:00:00Z',
      overallProbabilities: Object.fromEntries(blastRecords.map(([key, , , , , , , seed]) => [key, odds(seed)])),
      teamAnalysis: { '8': {}, '4': {} },
      qualificationPath: { '8': {}, '4': {} },
    },
  };
}

