export interface LeagueSummary {
  id: string;
  /** Older league lists predate other sports; a missing sport means cricket. */
  sport?: string;
  name: string;
  shortName: string;
  seasonLabel: string;
  status: 'league_stage' | 'playoffs' | 'complete' | string;
  champion: string | null;
  /** Headline numbers for the home page, e.g. "Title favourite: MCI 50%". */
  facts?: { label: string; value: string }[];
  /** False before the first game: the odds are pre-season projections. */
  started?: boolean;
  generatedAt: string;
  path: string;
}

export interface LeagueIndex {
  /** A league id, or "hub" for the all-sports home page. */
  default: string;
  /** The newest IPL season, for the share kit. */
  ipl?: string;
  leagues: LeagueSummary[];
}

export const HUB_ID = 'hub';

export const leagueIndexUrl = `${import.meta.env.BASE_URL}data/leagues.json`;

const LEAGUE_ID_PATTERN = /^[a-z0-9-]+$/;

/** The league requested with ?league=, if it is a well-formed id. */
export function leagueIdFromLocation(search: string = window.location.search): string | null {
  const requested = new URLSearchParams(search).get('league')?.trim().toLowerCase();
  return requested && LEAGUE_ID_PATTERN.test(requested) ? requested : null;
}

/** A league's page. The site root is the landing page, so every league has its own address. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function leagueHref(leagueId: string, _defaultId?: string) {
  return `${import.meta.env.BASE_URL}?league=${leagueId}`;
}

/** The all-sports hub of live races (the site root is the landing page). */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function hubHref(_defaultId?: string) {
  return `${import.meta.env.BASE_URL}?view=hub`;
}

export function hubRequested(search: string = window.location.search) {
  return new URLSearchParams(search).get('view') === HUB_ID;
}

export function isLive(league: Pick<LeagueSummary, 'status'>) {
  return league.status !== 'complete';
}

export function statusLabel(league: Pick<LeagueSummary, 'status' | 'started'>) {
  if (league.status === 'complete') {
    return 'Final';
  }
  if (league.status === 'postseason' || league.status === 'playoffs') {
    return 'Playoffs';
  }
  return league.started === false ? 'Pre-season' : 'Live';
}

/** Switcher rows: the NFL, NHL and MLB share one row; basketball (NBA, WNBA, NBL, WNBL) has its own. */
const SPORT_GROUPS: Record<string, string> = {
  cricket: 'Cricket',
  football: 'Football',
  'american-football': 'US sports',
  basketball: 'Basketball',
  'ice-hockey': 'US sports',
  baseball: 'US sports',
};

export const sportOf = (league: Pick<LeagueSummary, 'sport'>) => league.sport ?? 'cricket';

const SPORT_NAMES: Record<string, string> = {
  cricket: 'Cricket',
  football: 'Football',
  'american-football': 'American football',
  basketball: 'Basketball',
  'ice-hockey': 'Ice hockey',
  baseball: 'Baseball',
};

/** Display name for a payload's sport, for page breadcrumbs. */
export const sportName = (sport: string) => SPORT_NAMES[sport] ?? sport;

/** Leagues grouped by sport, keeping the list's order (live leagues first) within each group. */
export function leaguesBySport(index: LeagueIndex) {
  const groups = new Map<string, LeagueSummary[]>();
  index.leagues.forEach((league) => {
    const label = SPORT_GROUPS[sportOf(league)] ?? sportOf(league);
    groups.set(label, [...(groups.get(label) ?? []), league]);
  });
  return [...groups.entries()].map(([label, leagues]) => ({ sport: label, label, leagues }));
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
