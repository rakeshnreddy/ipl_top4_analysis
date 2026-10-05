/** Formula 1 payloads (formula1.py): drivers' and constructors' championships, title odds and race favourites. */

export interface F1Tier {
  key: string;
  label: string;
  shortLabel?: string;
  kind: 'champion' | 'top' | string;
  size?: number;
}

export interface F1Team {
  key: string;
  shortName: string;
  fullName: string;
  color: string;
  textColor: string;
}

export interface F1Driver {
  teamKey: string;
  shortName: string;
  fullName: string;
  number: string | null;
  /** The constructor of the driver's latest car. */
  team: string | null;
  teams: string[];
  rank: number;
  points: number;
  wins: number;
  podiums: number;
  sprintWins: number;
  played: number;
  /** In the current line-up (drivers who were replaced keep their points but race no more). */
  racing: boolean;
}

export interface F1Constructor {
  teamKey: string;
  shortName: string;
  fullName: string;
  rank: number;
  points: number;
  wins: number;
  podiums: number;
  drivers: string[];
}

export interface F1Event {
  key: string;
  round: number;
  kind: 'race' | 'sprint';
  name: string;
  date: string;
  circuit: string;
  locality: string;
  country: string;
}

export interface F1UpcomingEvent extends F1Event {
  favourites: { driver: string; win: number; podium: number }[];
}

export interface F1Result extends F1Event {
  podium: string[];
}

export interface F1Payload {
  metadata: {
    season: string;
    generated_at: string;
    source: string;
    source_url: string;
    data_freshness_status: string;
    season_status: string;
    warnings: string[];
    notes?: string[];
  };
  league: {
    id: string;
    configId: string;
    sport: string;
    name: string;
    shortName: string;
    headline?: string | null;
    season: string;
    seasonLabel: string;
    tiers: F1Tier[];
    constructorTiers: F1Tier[];
    teams: F1Team[];
    rounds: number;
    eventsLeft: number;
    rules?: { summary: string; sources: { label: string; url: string }[] } | null;
  };
  standings: F1Driver[];
  constructorStandings: F1Constructor[];
  events: F1UpcomingEvent[];
  results: F1Result[];
  analysis: {
    method: string;
    simulations: number;
    model: string;
    modelNotes: string[];
    probabilities: Record<string, Record<string, number>>;
    constructorProbabilities: Record<string, Record<string, number>>;
    expected?: Record<string, { points: number }>;
  };
}

export const f1DataUrl = (leagueId: string) => `${import.meta.env.BASE_URL}data/${leagueId}.json`;

function assertF1Payload(payload: unknown): asserts payload is F1Payload {
  const candidate = payload as Partial<F1Payload> | null;
  if (!candidate || typeof candidate !== 'object' || !candidate.metadata || !candidate.league) {
    throw new Error('Formula 1 payload is empty or malformed.');
  }
  if (!Array.isArray(candidate.standings) || !Array.isArray(candidate.constructorStandings) || !Array.isArray(candidate.events)) {
    throw new Error('Formula 1 payload is missing the standings or the calendar.');
  }
  if (!candidate.analysis?.probabilities || !candidate.analysis.constructorProbabilities) {
    throw new Error('Formula 1 payload is missing probabilities.');
  }
}

export async function loadF1Data(fetchImpl: typeof fetch, leagueId: string): Promise<F1Payload> {
  const response = await fetchImpl(f1DataUrl(leagueId), { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load ${leagueId} data (${response.status}).`);
  }
  const payload = await response.json();
  assertF1Payload(payload);
  return payload;
}
