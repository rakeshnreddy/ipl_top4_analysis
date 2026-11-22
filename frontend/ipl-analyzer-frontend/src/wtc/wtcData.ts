/** World Test Championship payloads (wtc.py): PCT table, exact claims, series and final odds. */

export interface WtcTeam {
  key: string;
  shortName: string;
  fullName: string;
  color: string;
  textColor: string;
}

export interface WtcStanding extends WtcTeam {
  teamKey: string;
  rank: number;
  played: number;
  won: number;
  lost: number;
  drawn: number;
  tied: number;
  pointsWon: number;
  deducted: number;
  points: number;
  /** Percentage of points, rounded to two decimals; null before a team's first Test. */
  pct: number | null;
  seriesWon: number;
  seriesPlayed: number;
  awayPlayed: number;
  awayPct: number | null;
  testsLeft: number;
  bestPct: number | null;
  worstPct: number | null;
  form: string[];
}

export type WtcTestState = 'result' | 'in_progress' | 'awaiting' | 'scheduled' | 'cancelled' | 'postponed';
export type WtcResultKind = 'host' | 'visitor' | 'draw' | 'tie' | 'abandoned' | 'unfit' | 'awarded' | 'forfeit';

export interface WtcOdds {
  host: number;
  draw: number;
  visitor: number;
}

export interface WtcTest {
  key: string;
  number: number;
  start: string;
  end: string;
  venue: string | null;
  country: string | null;
  neutral: boolean;
  state: WtcTestState;
  tentative: boolean;
  precision: 'day' | 'month';
  note?: string;
  result?: {
    kind: WtcResultKind;
    winner: string | null;
    margin: string;
    points: Record<string, number>;
    source: string;
    note?: string;
  };
  live?: string;
  odds?: WtcOdds;
  deductions?: { team: string; points: number; note: string; source: string }[];
}

export interface WtcSeries {
  id: string;
  name: string;
  host: string;
  visitor: string;
  status: 'complete' | 'in_progress' | 'scheduled' | 'cancelled';
  start: string;
  end: string;
  scheduled: number;
  counted: number;
  score: Record<string, number>;
  winner: string | null;
  tests: WtcTest[];
  note?: string;
}

export interface WtcFixture {
  id: string;
  series: string;
  number: number;
  host: string;
  visitor: string;
  start: string;
  end: string;
  venue: string | null;
  country: string | null;
  neutral: boolean;
  state: WtcTestState;
  precision: 'day' | 'month';
  tentative: boolean;
  odds?: WtcOdds;
}

export type WtcNeedStatus =
  | 'clinched'
  | 'clinched-unless-level'
  | 'in-control'
  | 'needs-help'
  | 'level-only'
  | 'eliminated'
  | 'undetermined';

export interface WtcNeed {
  status: WtcNeedStatus;
  testsLeft: number;
  bestPct: number | null;
  worstPct: number | null;
  ownDestiny: 'yes' | 'level' | 'no';
  fewestWins?: number;
  winsToClinch?: number;
  statements: string[];
}

export interface WtcSwing {
  fixtureId: string;
  series: string;
  number: number;
  date: string;
  host: string;
  visitor: string;
  team: string;
  ifHost: number | null;
  ifDraw: number | null;
  ifVisitor: number | null;
  swing: number;
}

export interface WtcSource {
  label: string;
  url: string;
}

export interface WtcFinal {
  venue: string | null;
  city: string | null;
  country: string;
  start: string | null;
  end: string | null;
  reserveDay: string | null;
  drawResult: 'joint';
  tentative: boolean;
  note: string;
  sources: WtcSource[];
  finalists: string[] | null;
  standingsClose: string;
  /** Once the finalists are known: each side's win chance and the draw (joint champions). */
  odds?: Record<string, number>;
  result?: { kind: 'win' | 'joint'; winner: string | null; joint: string[] | null; margin: string };
  /** The final's state while it is being played (CricketData). */
  live?: string;
  matchups?: { teams: string[]; chance: number }[];
}

export interface WtcChances {
  final: number;
  title: number;
  joint: number;
  champion: number;
}

export interface WtcPayload {
  metadata: {
    season: string;
    generated_at: string;
    source: string;
    source_url: string;
    license?: string;
    license_url?: string;
    data_freshness_status: string;
    season_status: 'pre_season' | 'league_stage' | 'playoffs' | 'complete' | string;
    warnings: string[];
    notes: string[];
  };
  league: {
    id: string;
    sport: string;
    engine: 'wtc';
    name: string;
    shortName: string;
    season: string;
    seasonLabel: string;
    points: { win: number; tie: number; draw: number; loss: number };
    finalists: number;
    tiers: { key: string; label: string; shortLabel?: string; kind: string; size?: number }[];
    columns: { key: string; label: string; decimals?: number }[];
    teams: WtcTeam[];
    tiebreakers: string[];
    rankings: { order: string[]; asOf: string | null; source: string | null } | null;
    testsTotal: number;
    testsLeft: number;
    seasonStart: string;
    seasonEnd: string;
    rules?: { summary: string; sources: WtcSource[] } | null;
    deductions: { team: string; points: number; test: string; note: string; source: string }[];
  };
  standings: WtcStanding[];
  series: WtcSeries[];
  fixtures: WtcFixture[];
  results: { id: string; series: string; number: number; host: string; visitor: string; start: string; venue: string | null; kind: WtcResultKind; winner: string | null; margin: string }[];
  final: WtcFinal;
  analysis: {
    method: string;
    simulations: number;
    model: string;
    modelNotes: string[];
    probabilities: Record<string, WtcChances>;
    positions: Record<string, number[]>;
    expectedPct: Record<string, number> | null;
    needs: Record<string, WtcNeed>;
    swing: WtcSwing[];
    ratings: Record<string, number>;
  };
  playoffs?: { champion: string | null; jointChampions: string[] | null };
}

export const wtcDataUrl = (leagueId: string) => `${import.meta.env.BASE_URL}data/${leagueId}.json`;

function assertWtcPayload(payload: unknown): asserts payload is WtcPayload {
  const candidate = payload as Partial<WtcPayload> | null;
  if (!candidate || typeof candidate !== 'object' || !candidate.metadata || !candidate.league) {
    throw new Error('World Test Championship payload is empty or malformed.');
  }
  if (!Array.isArray(candidate.standings) || !Array.isArray(candidate.series) || !candidate.final) {
    throw new Error('World Test Championship payload is missing the table, the series or the final.');
  }
  if (!candidate.analysis?.probabilities || !candidate.analysis.needs) {
    throw new Error('World Test Championship payload is missing its odds.');
  }
}

export async function loadWtcData(fetchImpl: typeof fetch, leagueId: string): Promise<WtcPayload> {
  const response = await fetchImpl(wtcDataUrl(leagueId), { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load ${leagueId} data (${response.status}).`);
  }
  const payload = await response.json();
  assertWtcPayload(payload);
  return payload;
}

/** PCT as the ICC prints it: two decimals. */
export const formatPct = (value: number | null | undefined) => (value === null || value === undefined ? '–' : value.toFixed(2));
