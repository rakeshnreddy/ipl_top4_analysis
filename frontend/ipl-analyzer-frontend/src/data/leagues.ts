export interface LeagueSummary {
  id: string;
  name: string;
  shortName: string;
  seasonLabel: string;
  status: 'league_stage' | 'playoffs' | 'complete' | string;
  champion: string | null;
  generatedAt: string;
  path: string;
}

export interface LeagueIndex {
  default: string;
  leagues: LeagueSummary[];
}

export const leagueIndexUrl = `${import.meta.env.BASE_URL}data/leagues.json`;

const LEAGUE_ID_PATTERN = /^[a-z0-9-]+$/;

/** The league requested with ?league=, if it is a well-formed id. */
export function leagueIdFromLocation(search: string = window.location.search): string | null {
  const requested = new URLSearchParams(search).get('league')?.trim().toLowerCase();
  return requested && LEAGUE_ID_PATTERN.test(requested) ? requested : null;
}

export function leagueHref(leagueId: string, defaultId: string) {
  return leagueId === defaultId ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}?league=${leagueId}`;
}

export async function loadLeagueIndex(fetchImpl: typeof fetch = fetch): Promise<LeagueIndex> {
  const response = await fetchImpl(leagueIndexUrl, { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load the league list (${response.status}).`);
  }

  const index = (await response.json()) as Partial<LeagueIndex>;
  if (typeof index.default !== 'string' || !Array.isArray(index.leagues)) {
    throw new Error('League list is malformed.');
  }
  return index as LeagueIndex;
}
