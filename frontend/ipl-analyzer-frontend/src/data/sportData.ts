/** Payloads for team sports other than cricket (football and the European cups, NFL, NBA, WNBA, NHL, MLB, NBL). */

export interface SportTier {
  key: string;
  label: string;
  /** Narrow-screen table header, e.g. "Drop" for "Relegation". */
  shortLabel?: string;
  /** Decided already (regular-season tiers once the playoffs start): shown as ticks, not odds. */
  settled?: boolean;
  /** "top" and "bottom" tiers are table positions; others (division titles, playoff spots) are sport-specific. */
  kind?: 'top' | 'bottom' | string;
  size?: number;
}

export interface SportColumn {
  key: string;
  label: string;
  title?: string;
  signed?: boolean;
  strong?: boolean;
  format?: 'pct' | 'decimal';
  /** Hidden on phones. */
  optional?: boolean;
}

export interface SportTeam {
  key: string;
  shortName: string;
  fullName: string;
  color: string;
  textColor: string;
}

export interface SportGroup {
  key: string;
  label: string;
  /** Members in table order (conference seed or division rank). */
  teams: string[];
  /** Lines drawn under a table position, e.g. the playoff line after the 7th seed. */
  cutoffs?: { after: number; label: string }[];
}

export interface SportStanding {
  teamKey: string;
  shortName: string;
  fullName: string;
  rank: number;
  played: number;
  wins: number;
  losses: number;
  draws?: number;
  points?: number;
  form: string[];
  remaining: number;
  [column: string]: unknown;
}

export interface SportFixture {
  id: string;
  round: number | null;
  date: string;
  home: string;
  away: string;
  venue: string | null;
  /** Playoff round name, e.g. "Division Series". */
  stage?: string;
  probabilities: Record<string, number>;
}

export interface BracketSeries {
  stage: string;
  conference: string | null;
  /** Unknown until the earlier rounds are decided. */
  top: string | null;
  bottom: string | null;
  topSeed: number | null;
  bottomSeed: number | null;
  topWins: number;
  bottomWins: number;
  bestOf: number;
  winner: string | null;
  /** Two-legged ties (European cups): total goals over both legs instead of series wins. */
  aggregate?: { top: number; bottom: number } | null;
  /** How a level tie was settled, e.g. "4-3 on penalties". */
  note?: string;
}

export interface Bracket {
  rounds: { key: string; label: string; series: BracketSeries[] }[];
  champion: string | null;
}

export interface SportResult {
  id: string;
  round: number | null;
  date: string;
  home: string;
  away: string;
  homeScore: number;
  awayScore: number;
  note?: string | null;
}

export interface MatchThatMatters {
  fixtureId: string;
  date: string;
  home: string;
  away: string;
  tier: string;
  tierLabel: string;
  team: string;
  swing: number;
  ifHome: number | null;
  ifDraw?: number | null;
  ifAway: number | null;
}

export interface SportMovement {
  since: string;
  changes: Record<string, Record<string, number>>;
}

export interface SportPayload {
  metadata: {
    season: string;
    generated_at: string;
    source: string;
    source_url: string;
    data_freshness_status: string;
    season_status: string;
    warnings: string[];
    credits?: { name: string; url: string; note?: string }[];
  };
  league: {
    id: string;
    configId: string;
    sport: string;
    name: string;
    shortName: string;
    season: string;
    seasonLabel: string;
    tiers: SportTier[];
    columns: SportColumn[];
    outcomes: string[];
    teams: SportTeam[];
    groups?: SportGroup[];
    /** Lines on the league table itself, for leagues seeded as one table (the WNBA's playoff line). */
    cutoffs?: SportGroup['cutoffs'];
    /** What the table's rank means when groups exist, e.g. "League" or "Overall". */
    rankLabel?: string;
    positionLabel?: string;
    /** Colours for the finishing-position chart: positions up to `to` are in the zone. */
    positionZones?: { to: number; kind: 'top' | 'mid' | 'bottom' | string }[];
    /** Page heading, e.g. "NFL Playoff & Super Bowl Odds"; built from the tiers when absent. */
    headline?: string;
  };
  standings: SportStanding[];
  fixtures: SportFixture[];
  results: SportResult[];
  analysis: {
    method: string;
    simulations: number;
    model: string;
    modelNotes: string[];
    probabilities: Record<string, Record<string, number>>;
    positions?: Record<string, number[]>;
    expected?: Record<string, Record<string, number>>;
  };
  matchesThatMatter: MatchThatMatters[];
  movement?: SportMovement | null;
  bracket?: Bracket;
}

export const sportDataUrl = (leagueId: string) => `${import.meta.env.BASE_URL}data/${leagueId}.json`;

function assertSportPayload(payload: unknown): asserts payload is SportPayload {
  const candidate = payload as Partial<SportPayload> | null;
  if (!candidate || typeof candidate !== 'object' || !candidate.metadata || !candidate.league) {
    throw new Error('League payload is empty or malformed.');
  }
  if (!Array.isArray(candidate.standings) || !Array.isArray(candidate.fixtures) || !Array.isArray(candidate.league.tiers)) {
    throw new Error('League payload is missing standings, fixtures or tiers.');
  }
  if (!candidate.analysis?.probabilities) {
    throw new Error('League payload is missing probabilities.');
  }
  if (candidate.standings.length !== candidate.league.teams.length) {
    throw new Error(`Expected ${candidate.league.teams.length} teams, found ${candidate.standings.length}.`);
  }
}

export async function loadSportData(fetchImpl: typeof fetch, leagueId: string): Promise<SportPayload> {
  const response = await fetchImpl(sportDataUrl(leagueId), { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load ${leagueId} data (${response.status}).`);
  }
  const payload = await response.json();
  assertSportPayload(payload);
  return payload;
}

export const isSeasonComplete = (payload: SportPayload) => payload.metadata.season_status === 'complete';
