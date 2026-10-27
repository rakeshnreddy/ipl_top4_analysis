import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Plugin } from 'vite';
import { PRIMARY_SITE_URL } from '../src/lib/siteIdentity';

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
export function buildSitemap(_siteUrl: string, list: LeagueList): string {
  const base = PRIMARY_SITE_URL;
  const newest = list.leagues.map((league) => league.generatedAt).filter(Boolean).sort().pop();
  // The root is the landing page; the hub and every league have their own address.
  const urls: { loc: string; lastmod?: string }[] = [
    { loc: base, lastmod: newest },
    { loc: `${base}leagues/`, lastmod: newest },
    // Current matches are runtime data; season export times are not their lastmod.
    { loc: `${base}cricket/` },
    ...['about', 'methodology', 'privacy', 'advertise'].map((path) => ({ loc: `${base}${path}/` })),
  ];
  for (const league of list.leagues) {
    urls.push({ loc: `${base}league/${encodeURIComponent(league.id)}/`, lastmod: league.generatedAt });
  }
  const body = urls
    .map(
      ({ loc, lastmod }) =>
        `  <url><loc>${escapeXml(loc)}</loc>${lastmod ? `<lastmod>${escapeXml(lastmod.slice(0, 10))}</lastmod>` : ''}</url>`,
    )
    .join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`;
}

/** Both deployment outputs advertise only the primary site's canonical pages. */
export function sitemapPlugin(_siteUrl: string | undefined): Plugin {
  // The mirror's served origin is deliberately independent from canonical URLs.
  void _siteUrl;
  let publicDir = 'public';
  return {
    name: 'league-sitemap',
    apply: 'build',
    configResolved(config) {
      publicDir = config.publicDir;
    },
    generateBundle() {
      const list = JSON.parse(readFileSync(resolve(publicDir, 'data/leagues.json'), 'utf-8')) as LeagueList;
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: buildSitemap(PRIMARY_SITE_URL, list) });
    },
  };
}
