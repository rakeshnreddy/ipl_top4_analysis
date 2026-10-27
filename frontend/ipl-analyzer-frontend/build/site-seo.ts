import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Plugin } from 'vite';
import { criticalPreloads } from './league-pages';
import { CRICKET_DESCRIPTION, CRICKET_TITLE, DIRECTORY_DESCRIPTION, DIRECTORY_TITLE, HOME_DESCRIPTION, HOME_TITLE, PRIMARY_SITE_URL, primaryPageUrl } from '../src/lib/siteIdentity';

export interface SearchLeague {
  id: string;
  name: string;
  seasonLabel: string;
  sport?: string;
  status: string;
}

const escape = (value: unknown) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const json = (value: object) => JSON.stringify(value).replace(/</g, '\\u003c');
const sports: Record<string, string> = { cricket: 'Cricket', football: 'Football', basketball: 'Basketball', 'american-football': 'American football', 'ice-hockey': 'Ice hockey', baseball: 'Baseball', motorsport: 'Formula 1' };
const snapshotStyle = `<style data-pp-search-style>#root{min-height:100vh}#search-snapshot{max-width:1280px;min-height:100vh;margin:0 auto;padding:36px 24px 64px;color:var(--text,#17212b);font:16px/1.65 var(--font-ui,system-ui,sans-serif)}#search-snapshot nav{display:flex;flex-wrap:wrap;gap:16px}#search-snapshot a{display:inline-flex;align-items:center;min-height:44px;color:var(--sport-accent,#246a9c)}#search-snapshot h1,#search-snapshot h2,#search-snapshot h3{font-family:var(--font-display,system-ui,sans-serif);line-height:1.2}#search-snapshot h1{font-size:clamp(36px,6vw,56px)}#search-snapshot h2{font-size:28px;margin-top:36px}#search-snapshot h3{font-size:22px}#search-snapshot p{max-width:76ch}#search-snapshot ul{padding-left:20px}#search-snapshot li{padding:3px 0}#search-snapshot a:focus-visible{outline:2px solid var(--focus,#456500);outline-offset:4px}</style>`;

function graph(path: string, title: string, description: string, entries?: SearchLeague[]) {
  const url = primaryPageUrl(path);
  return { '@context': 'https://schema.org', '@graph': [
    { '@type': 'WebSite', '@id': `${PRIMARY_SITE_URL}#website`, name: 'Playoff Pulse', url: PRIMARY_SITE_URL, description: HOME_DESCRIPTION },
    { '@type': entries ? 'CollectionPage' : 'WebPage', '@id': `${url}#webpage`, url, name: title, description, isPartOf: { '@id': `${PRIMARY_SITE_URL}#website` }, ...(entries ? { mainEntity: { '@type': 'ItemList', itemListElement: entries.map((entry, index) => ({ '@type': 'ListItem', position: index + 1, name: `${entry.name} ${entry.seasonLabel}`, url: primaryPageUrl(`league/${entry.id}/`) })) } } : {}) },
  ] };
}

/** Source and rendered pages use the same metadata and primary search identity. */
export function searchMetadata(template: string, path: string, title: string, description: string, structured: object) {
  const canonical = primaryPageUrl(path);
  const image = new URL('social/og/playoff-pulse.png', PRIMARY_SITE_URL).href;
  const clean = template
    .replace(/<title>[\s\S]*?<\/title>/i, `<title>${escape(title)}</title>`)
    .replace(/<link\b(?=[^>]*\brel="canonical")[^>]*>/gi, '')
    .replace(/<meta\b(?=[^>]*(?:\bname="(?:description|twitter:[^"]+)"|\bproperty="og:[^"]+"))[^>]*>/gi, '')
    .replace(/<script\b[^>]*data-ipl-jsonld[^>]*>[\s\S]*?<\/script>/gi, '');
  return clean.replace('</head>', `<link rel="canonical" href="${escape(canonical)}" />
<meta name="description" content="${escape(description)}" />
<meta property="og:site_name" content="Playoff Pulse" /><meta property="og:type" content="website" />
<meta property="og:title" content="${escape(title)}" /><meta property="og:description" content="${escape(description)}" /><meta property="og:url" content="${escape(canonical)}" />
<meta property="og:image" content="${escape(image)}" /><meta property="og:image:width" content="1200" /><meta property="og:image:height" content="630" /><meta property="og:image:alt" content="${escape(title)}" />
<meta name="twitter:card" content="summary_large_image" /><meta name="twitter:title" content="${escape(title)}" /><meta name="twitter:description" content="${escape(description)}" /><meta name="twitter:image" content="${escape(image)}" />
<script type="application/ld+json" data-ipl-jsonld="true">${json(structured)}</script>
${snapshotStyle}
</head>`);
}

function navigation(base: string) {
  return `<nav aria-label="Site"><a href="${escape(base)}">Playoff Pulse</a><a href="${escape(base)}leagues/">Season Odds</a><a href="${escape(base)}cricket/">Live Cricket</a></nav>`;
}

function leagueLinks(entries: SearchLeague[], base: string) {
  const groups = [...new Set(entries.map((entry) => entry.sport ?? 'cricket'))];
  return groups.map((sport) => `<section><h3>${escape(sports[sport] ?? sport)}</h3><ul>${entries.filter((entry) => (entry.sport ?? 'cricket') === sport).map((entry) => `<li><a href="${escape(base)}league/${escape(entry.id)}/">${escape(entry.name)} ${escape(entry.seasonLabel)}</a> — ${entry.status === 'complete' ? 'Final standings and results' : 'Standings and season probabilities'}</li>`).join('')}</ul></section>`).join('');
}

function withContent(template: string, content: string) {
  if (!template.includes('<div id="root"></div>')) throw new Error('Search entry is missing its empty React root.');
  return template.replace('<div id="root"></div>', `<div id="root"><main id="search-snapshot">${content}</main></div>`);
}

/** Static hosts cannot issue query-dependent HTTP redirects; preserve old bookmarks. */
export function legacyQueryRedirectScript(entries: SearchLeague[], base: string) {
  return `(() => {
  const base = ${JSON.stringify(base)};
  if (location.pathname !== base && location.pathname !== base + 'index.html') return;
  const params = new URLSearchParams(location.search);
  const id = (params.get('league') || '').trim().toLowerCase();
  const published = ${json(entries.map((entry) => entry.id))};
  const target = id && published.includes(id) ? base + 'league/' + encodeURIComponent(id) + '/' : !id && params.get('view') === 'hub' ? base + 'leagues/' : null;
  if (target) location.replace(target + location.hash);
})();`;
}

export function renderHomeSource(template: string, entries: SearchLeague[], base: string) {
  const html = searchMetadata(template, '/', HOME_TITLE, HOME_DESCRIPTION, graph('/', HOME_TITLE, HOME_DESCRIPTION));
  return withContent(html, `${navigation(base)}<h1>Playoff odds, standings and live cricket</h1><p>${escape(HOME_DESCRIPTION)}</p><p>Season forecasts estimate how a competition may finish. The separate cricket match center shows the connected source's current coverage. Model percentages and bookmaker prices have different meanings.</p><p><a href="${escape(base)}leagues/">Explore season odds by league</a> · <a href="${escape(base)}cricket/">Open Live Cricket</a></p><h2>Published competitions</h2>${leagueLinks(entries, base)}<h2>Understand the numbers</h2><p>Read our <a href="${escape(base)}methodology/">sources and model methodology</a> to understand simulations, freshness and uncertainty. Completed seasons show their final standings rather than new predictions. <a href="${escape(base)}about/">About Playoff Pulse</a>.</p>`);
}

export function renderDirectorySource(template: string, entries: SearchLeague[], base: string) {
  const html = searchMetadata(template, '/leagues/', DIRECTORY_TITLE, DIRECTORY_DESCRIPTION, graph('/leagues/', DIRECTORY_TITLE, DIRECTORY_DESCRIPTION, entries));
  return withContent(html, `${navigation(base)}<h1>Season odds by league</h1><p>${escape(DIRECTORY_DESCRIPTION)}</p><p>Open a competition for its published source timestamp, current or final table, and supported title, playoff or relegation probabilities. The interactive directory also supports search and filters.</p>${leagueLinks(entries, base)}<p><a href="${escape(base)}methodology/">How season forecasts work</a></p>`);
}

export function renderCricketSource(template: string, base: string) {
  const url = primaryPageUrl('/cricket/');
  const structured = { '@context': 'https://schema.org', '@type': 'CollectionPage', '@id': `${url}#webpage`, name: CRICKET_TITLE, description: CRICKET_DESCRIPTION, url, isPartOf: { '@type': 'WebSite', '@id': `${PRIMARY_SITE_URL}#website`, name: 'Playoff Pulse', url: PRIMARY_SITE_URL } };
  const html = searchMetadata(template, '/cricket/', CRICKET_TITLE, CRICKET_DESCRIPTION, structured).replace(/<noscript>[\s\S]*?<\/noscript>/gi, '');
  return withContent(html, `${navigation(base)}<h1>Live Cricket</h1><p>${escape(CRICKET_DESCRIPTION)}</p><h2>Current coverage, clearly labelled</h2><p>Enable JavaScript to check the connected source and open a covered match. The fixture list changes over time; it does not include every cricket match worldwide. Missing scorecards, commentary, probabilities or markets stay unavailable.</p><p>Score observations, source checks, model calculations and bookmaker quotes have separate timestamps. A connection failure cannot turn an old value into a fresh one.</p><h2>Two kinds of odds</h2><p>Model estimates express a calculated chance of winning. Bookmaker decimal prices include market terms and margin. A season qualification probability is not a match-win estimate.</p><p><a href="${escape(base)}methodology/">Read about sources, models and limitations</a> · <a href="${escape(base)}leagues/">Browse season odds and standings</a></p>`);
}

export function renderNotFound(base: string) {
  return `<!doctype html><html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><meta name="robots" content="noindex, follow" /><meta name="color-scheme" content="light dark" /><title>Page Not Found | Playoff Pulse</title>${snapshotStyle}</head><body><main id="search-snapshot">${navigation(base)}<h1>Page not found</h1><p>This address does not identify a published Playoff Pulse page. A competition may have moved or the link may be incomplete.</p><p><a href="${escape(base)}leagues/">Find a published league</a> · <a href="${escape(base)}cricket/">Open Live Cricket</a></p></main></body></html>`;
}

/** Register after the league and cricket build plugins; no provider request occurs. */
export function siteSeoPlugin(): Plugin {
  let publicDir: string;
  let base: string;
  return {
    name: 'site-search-entries', apply: 'build', enforce: 'post',
    configResolved(config) { publicDir = config.publicDir; base = config.base; },
    generateBundle: { order: 'post', handler(_options, bundle) {
      const home = bundle['index.html'];
      const cricket = bundle['cricket/index.html'];
      if (!home || home.type !== 'asset' || !cricket || cricket.type !== 'asset') throw new Error('Missing search entry.');
      const entries = (JSON.parse(readFileSync(resolve(publicDir, 'data/leagues.json'), 'utf8')) as { leagues: SearchLeague[] }).leagues;
      if (!entries.every((entry) => /^[a-z0-9-]+$/.test(entry.id))) throw new Error('Invalid published league ID.');
      const template = String(home.source);
      home.source = renderHomeSource(template, entries, base).replace('<head>', `<head><script data-pp-legacy-redirect>${legacyQueryRedirectScript(entries, base)}</script>`);
      cricket.source = renderCricketSource(String(cricket.source), base);
      const directory = renderDirectorySource(template, entries, base).replace('</head>', `${criticalPreloads(bundle, 'hub', null, base, template)}\n</head>`);
      this.emitFile({ type: 'asset', fileName: 'leagues/index.html', source: directory });
      this.emitFile({ type: 'asset', fileName: '404.html', source: renderNotFound(base) });
    } },
  };
}
