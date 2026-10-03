import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Plugin } from 'vite';

interface IndexEntry {
  id: string;
  generatedAt?: string;
}

interface LeagueList {
  default: string;
  leagues: IndexEntry[];
}

const escapeXml = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** sitemap.xml for every published league page, from the league list in public/data. */
export function buildSitemap(siteUrl: string, list: LeagueList): string {
  const base = siteUrl.endsWith('/') ? siteUrl : `${siteUrl}/`;
  const newest = list.leagues.map((league) => league.generatedAt).filter(Boolean).sort().pop();
  const urls: { loc: string; lastmod?: string }[] = [{ loc: base, lastmod: newest }];
  if (list.default !== 'hub') {
    urls.push({ loc: `${base}?view=hub`, lastmod: newest });
  }
  for (const league of list.leagues) {
    if (league.id !== list.default) {
      urls.push({ loc: `${base}?league=${encodeURIComponent(league.id)}`, lastmod: league.generatedAt });
    }
  }
  const body = urls
    .map(
      ({ loc, lastmod }) =>
        `  <url><loc>${escapeXml(loc)}</loc>${lastmod ? `<lastmod>${escapeXml(lastmod.slice(0, 10))}</lastmod>` : ''}</url>`,
    )
    .join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`;
}

/** Emits sitemap.xml when SITE_URL names where the build will be served. */
export function sitemapPlugin(siteUrl: string | undefined): Plugin {
  let publicDir = 'public';
  return {
    name: 'league-sitemap',
    apply: 'build',
    configResolved(config) {
      publicDir = config.publicDir;
    },
    generateBundle() {
      if (!siteUrl) {
        return;
      }
      const list = JSON.parse(readFileSync(resolve(publicDir, 'data/leagues.json'), 'utf-8')) as LeagueList;
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: buildSitemap(siteUrl, list) });
    },
  };
}
