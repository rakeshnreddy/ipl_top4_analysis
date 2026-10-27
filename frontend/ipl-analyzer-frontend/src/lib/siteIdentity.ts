/** One search identity for the production site and its usable GitHub mirror. */
export const PRIMARY_SITE_URL = 'https://ipl-playoff-pulse.pages.dev/';
export const HOME_TITLE = 'Playoff Pulse | Playoff Odds, Standings & Live Cricket';
export const HOME_DESCRIPTION = 'Explore season title, playoff and relegation probabilities across sports, plus covered cricket fixtures and available live scores. See sources and model methods.';
export const DIRECTORY_TITLE = 'Season Odds by League | Playoff Pulse';
export const DIRECTORY_DESCRIPTION = 'Browse published cricket, football, basketball, American sports and Formula 1 seasons. Compare standings and model probabilities, with completed-season results kept distinct.';
export const CRICKET_TITLE = 'Live Cricket Scores & Match Center | Playoff Pulse';
export const CRICKET_DESCRIPTION = 'Follow covered cricket fixtures, available scores and match details. Scorecards, model estimates and bookmaker prices appear only when supplied and verified.';

const MIRROR_ORIGIN = 'https://rakeshnreddy.github.io';
const MIRROR_BASE = '/ipl_top4_analysis/';
const validId = /^[a-z0-9-]+$/;

/** Normalize a site page without changing external source/attribution URLs. */
export function primaryPageUrl(pathOrUrl: string, base = '/') {
  const url = new URL(pathOrUrl, PRIMARY_SITE_URL);
  const relative = !/^[a-z][a-z0-9+.-]*:/i.test(pathOrUrl) && !pathOrUrl.startsWith('//');
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (!relative && url.origin !== new URL(PRIMARY_SITE_URL).origin && url.origin !== MIRROR_ORIGIN && !local) return pathOrUrl;

  let path = url.pathname;
  const servedBase = new URL(base, PRIMARY_SITE_URL).pathname;
  for (const prefix of [MIRROR_BASE, servedBase]) {
    if (prefix !== '/' && (path === prefix.slice(0, -1) || path.startsWith(prefix))) {
      path = `/${path.slice(prefix.length)}`;
      break;
    }
  }
  path = path.replace(/\/index\.html$/, '/');
  const league = url.searchParams.get('league')?.trim().toLowerCase();
  if (path === '/' && league && validId.test(league)) path = `/league/${league}/`;
  else if (path === '/' && url.searchParams.get('view') === 'hub') path = '/leagues/';
  if (path === '/cricket') path = '/cricket/';
  if (path === '/leagues') path = '/leagues/';
  if (!/\.[a-z0-9]+$/i.test(path) && !path.endsWith('/')) path += '/';
  return new URL(path, PRIMARY_SITE_URL).href;
}
