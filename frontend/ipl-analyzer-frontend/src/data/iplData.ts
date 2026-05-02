export interface IplMetadata {
  season: number;
  generated_at: string;
  source: string;
  source_url: string;
  data_freshness_status: 'fresh' | 'warning' | 'stale' | string;
  warnings: string[];
}

export interface IplStanding {
  teamKey: string;
  shortName: string;
  fullName: string;
  matches: number;
  wins: number;
  losses: number;
  noResult: number;
  points: number;
  nrr: number;
  rank: number;
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

export interface IplProbability {
  top4: number;
  top2: number;
  top4Clear?: number;
  top2Clear?: number;
  top4Possible?: number;
  top2Possible?: number;
}

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
  qualificationPath: Record<'4' | '2', Record<string, QualificationPathResult>>;
  scenarioBreakdown?: Record<'4' | '2', Record<string, unknown>>;
}

export interface IplSeasonPayload {
  metadata: IplMetadata;
  standings: IplStanding[];
  fixtures: IplFixture[];
  analysis: IplAnalysis;
}

export const canonicalDataUrl = `${import.meta.env.BASE_URL}data/ipl-2026.json`;

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

  if (candidate.standings.length !== 10) {
    throw new Error(`Expected 10 IPL teams, found ${candidate.standings.length}.`);
  }

  candidate.standings.forEach((team) => {
    if (!isString(team.teamKey) || !isString(team.shortName) || !isNumber(team.points) || !isNumber(team.nrr)) {
      throw new Error('One or more standings rows are missing team, points, or NRR fields.');
    }
  });
}

export async function loadIplData(fetchImpl: typeof fetch = fetch): Promise<IplSeasonPayload> {
  const response = await fetchImpl(canonicalDataUrl, { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load IPL data (${response.status}).`);
  }

  const payload = await response.json();
  assertPayload(payload);
  return payload;
}
