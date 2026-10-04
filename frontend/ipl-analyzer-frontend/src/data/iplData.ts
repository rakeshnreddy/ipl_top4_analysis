export interface IplMetadata {
  season: number | string;
  generated_at: string;
  source: string;
  source_url: string;
  data_freshness_status: 'fresh' | 'warning' | 'stale' | string;
  season_status?: 'league_stage' | 'playoffs' | 'complete' | string;
  source_license?: string;
  source_license_url?: string;
  warnings: string[];
  notes?: string[];
}

export interface IplStanding {
  teamKey: string;
  shortName: string;
  fullName: string;
  matches: number;
  wins: number;
  losses: number;
  noResult: number;
  /** Ties without a Super Over (The Hundred); absent in most leagues. */
  ties?: number;
  /** SA20-style bonus points, already included in `points`. */
  bonusPoints?: number;
  /** Points taken off by a sanction, already subtracted from `points`. */
  deductedPoints?: number;
  points: number;
  nrr: number | null;
  /** Overall rank; in a group stage, the seed across groups (winners first, then seconds...). */
  rank: number;
  /** Group-stage leagues (the T20 Blast): the team's group and its place in it. */
  group?: string;
  groupRank?: number;
  remainingMatches: number;
}

export interface IplFixture {
  id: string;
  matchNo: number | null;
  teamA: string;
  teamB: string;
  dateTimeGMT: string | null;
  dateTimeLocal: string | null;
  venue: string | null;
  status: string;
  sourceUrl: string;
}

/** Chances keyed by tier, e.g. `top4`, `top4Clear`, `top2`; WPL payloads use `top3` and `top1`. */
export type IplProbability = Record<string, number>;

export interface OwnWinBucket {
  wins: number;
  scenarios: number;
  probability: number;
  possibleRate: number;
  guaranteedRate: number;
}

export interface FixtureImpact {
  fixtureId: string;
  matchNo: number | null;
  label: string;
  teamA: string;
  teamB: string;
  preferredWinner: string;
  preferredLabel: string;
  teamAWinProbability: number;
  teamBWinProbability: number;
  impact: number;
}

export interface QualificationPathResult {
  possible: number | null;
  likely?: number | null;
  guaranteed: number | null;
  target_matches: number;
  method: string;
  ownWinBuckets?: OwnWinBucket[];
  fixtureImpacts?: FixtureImpact[];
  nextFixtureImpacts?: FixtureImpact[];
}

export interface IplAnalysis {
  method: string;
  simulationCount: number;
  generatedAt: string;
  modelNotes?: string[];
  overallProbabilities: Record<string, IplProbability>;
  teamAnalysis: Record<string, Record<string, unknown>>;
  qualificationPath: Record<string, Record<string, QualificationPathResult>>;
  scenarioBreakdown?: Record<string, Record<string, unknown>>;
}

export interface IplPlayoffMatch {
  id: string;
  stage: string;
  date: string;
  teamA: string;
  teamB: string;
  winner: string | null;
  result: string;
  venue: string | null;
}

export interface IplPlayoffs {
  matches: IplPlayoffMatch[];
  champion: string | null;
  runnerUp: string | null;
}

export interface QualificationTier {
  size: number;
  label: string;
  /** Column header on phones, such as "QF". */
  shortLabel?: string;
}

export interface LeagueTeam {
  key: string;
  shortName: string;
  fullName: string;
  color: string;
  textColor: string;
}

/** League details written by the pipeline; older IPL payloads omit it. */
export interface IplLeague {
  id: string;
  name: string;
  shortName: string;
  season: string;
  seasonLabel: string;
  matchesPerTeam: number;
  qualification: QualificationTier[];
  secondChanceStages: string[];
  points?: { win: number; noResult: number; tie: number; bonus: boolean };
  teams: LeagueTeam[];
  /** A league stage played in groups; a tier of size N is the top N seeds across them. */
  groups?: LeagueGroup[];
  deductions?: PointsDeduction[];
}

export interface LeagueGroup {
  name: string;
  teams: string[];
}

export interface PointsDeduction {
  team: string;
  points: number;
  note: string;
}

/** Change in each team's playoff-tier chance (percentage points) since the previous update. */
export interface ProbabilityMovement {
  since: string;
  tier: string;
  changes: Record<string, number>;
}

export interface IplSeasonPayload {
  metadata: IplMetadata;
  league?: IplLeague;
  movement?: ProbabilityMovement | null;
  standings: IplStanding[];
  fixtures: IplFixture[];
  playoffs?: IplPlayoffs;
  analysis: IplAnalysis;
}

/** The league stage is over once no fixtures remain and every team has played its full schedule. */
export const isLeagueComplete = (payload: IplSeasonPayload) =>
  payload.fixtures.length === 0 && payload.standings.every((team) => team.remainingMatches === 0);

export const DEFAULT_LEAGUE_ID = 'ipl-2026';

export const leagueDataUrl = (leagueId: string) => `${import.meta.env.BASE_URL}data/${leagueId}.json`;

const isNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const isString = (value: unknown): value is string => typeof value === 'string';

function assertPayload(payload: unknown): asserts payload is IplSeasonPayload {
  if (!payload || typeof payload !== 'object') {
    throw new Error('IPL payload is empty or malformed.');
  }

  const candidate = payload as Partial<IplSeasonPayload>;
  if (!candidate.metadata || !Array.isArray(candidate.standings) || !Array.isArray(candidate.fixtures)) {
    throw new Error('IPL payload is missing metadata, standings, or fixtures.');
  }

  if (!candidate.analysis?.overallProbabilities || !candidate.analysis?.qualificationPath) {
    throw new Error('IPL payload is missing analysis results.');
  }

  if (!isString(candidate.metadata.generated_at) || !isString(candidate.metadata.source)) {
    throw new Error('IPL metadata is missing generated_at or source.');
  }

  const expectedTeams = candidate.league?.teams?.length ?? 10;
  if (candidate.standings.length !== expectedTeams) {
    const leagueName = candidate.league?.shortName ?? 'IPL';
    throw new Error(`Expected ${expectedTeams} ${leagueName} teams, found ${candidate.standings.length}.`);
  }

  candidate.standings.forEach((team) => {
    if (!isString(team.teamKey) || !isString(team.shortName) || !isNumber(team.points)) {
      throw new Error('One or more standings rows are missing team or points fields.');
    }
    if (team.nrr !== null && !isNumber(team.nrr)) {
      throw new Error('One or more standings rows have malformed NRR fields.');
    }
  });
}

export async function loadIplData(
  fetchImpl: typeof fetch = fetch,
  leagueId: string = DEFAULT_LEAGUE_ID,
): Promise<IplSeasonPayload> {
  const response = await fetchImpl(leagueDataUrl(leagueId), { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load ${leagueId} data (${response.status}).`);
  }

  const payload = await response.json();
  assertPayload(payload);
  return payload;
}
