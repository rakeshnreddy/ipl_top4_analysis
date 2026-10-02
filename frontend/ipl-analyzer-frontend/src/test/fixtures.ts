import { vi } from 'vitest';
import type { IplSeasonPayload } from '../data/iplData';
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

export function installFetch(payload: IplSeasonPayload = mockPayload, manifest: ReelsManifest = mockManifest) {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
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
