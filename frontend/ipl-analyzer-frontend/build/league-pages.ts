import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { inflateSync } from 'node:zlib';
import type { Plugin } from 'vite';
import { Resvg } from '@resvg/resvg-js';
import { formatChance } from '../src/sport/format';

interface LeagueEntry {
  id: string;
  name: string;
  shortName: string;
  seasonLabel: string;
  sport?: string;
  champion?: string | null;
  path: string;
}

interface Standing {
  teamKey: string;
  shortName: string;
  fullName: string;
  rank: number;
  points?: number;
  wins?: number;
  played?: number;
  matches?: number;
  nrr?: number;
  group?: string;
  conference?: string;
  [key: string]: unknown;
}

export interface LeaguePayload {
  metadata: { generated_at: string; source: string; source_url?: string; season_status: string; warnings?: string[] };
  league: {
    id: string; name: string; shortName: string; seasonLabel: string; sport?: string;
    columns?: { key: string; label: string; signed?: boolean }[];
    tiers?: { key: string; label: string }[];
    qualification?: { size: number; label: string }[];
    eventsLeft?: number;
  };
  standings: Standing[];
  constructorStandings?: Standing[];
  playoffs?: { champion?: string | null };
  fixtures?: unknown[];
  analysis: {
    method: string; model?: string; modelNotes?: string[];
    probabilities?: Record<string, Record<string, number>>;
    overallProbabilities?: Record<string, Record<string, number>>;
    constructorProbabilities?: Record<string, Record<string, number>>;
  };
}

interface Fact { label: string; value: string }
interface Column { key: string; label: string; signed?: boolean; probability?: boolean }
export interface LeaguePage {
  id: string; title: string; heading: string; description: string; status: string;
  updated: string; canonical: string; image: string; base: string; dataUrl: string;
  facts: Fact[]; rows: Standing[]; columns: Column[]; payload: LeaguePayload;
}

const escapeHtml = (value: unknown) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const safeJson = (data: object) => JSON.stringify(data).replace(/</g, '\\u003c');
const validId = /^[a-z0-9-]+$/;

/** resvg reads SFNT fonts; unwrap the existing Fontsource WOFF without another font download. */
function unwrapWoff(woff: Buffer) {
  if (woff.toString('ascii', 0, 4) !== 'wOFF') throw new Error('Expected a WOFF font.');
  const count = woff.readUInt16BE(12);
  const font = Buffer.alloc(woff.readUInt32BE(16));
  font.writeUInt32BE(woff.readUInt32BE(4), 0);
  font.writeUInt16BE(count, 4);
  const power = 2 ** Math.floor(Math.log2(count));
  font.writeUInt16BE(power * 16, 6);
  font.writeUInt16BE(Math.log2(power), 8);
  font.writeUInt16BE(count * 16 - power * 16, 10);
  let offset = 12 + count * 16;
  let head = 0;
  for (let index = 0; index < count; index++) {
    const source = 44 + index * 20;
    const target = 12 + index * 16;
    const start = woff.readUInt32BE(source + 4);
    const compressed = woff.readUInt32BE(source + 8);
    const length = woff.readUInt32BE(source + 12);
    const data = woff.subarray(start, start + compressed);
    const table = compressed < length ? inflateSync(data) : data;
    if (table.length !== length) throw new Error('Malformed WOFF table.');
    woff.copy(font, target, source, source + 4);
    font.writeUInt32BE(woff.readUInt32BE(source + 16), target + 4);
    font.writeUInt32BE(offset, target + 8);
    font.writeUInt32BE(length, target + 12);
    table.copy(font, offset);
    if (woff.toString('ascii', source, source + 4) === 'head') head = offset;
    offset += (length + 3) & ~3;
  }
  if (head) {
    font.writeUInt32BE(0, head + 8);
    let checksum = 0;
    for (let offset = 0; offset < font.length; offset += 4) checksum = (checksum + font.readUInt32BE(offset)) >>> 0;
    font.writeUInt32BE((0xb1b0afba - checksum) >>> 0, head + 8);
  }
  return font;
}

let socialFonts: string[] | undefined;
export function renderSocialPng(svg: string) {
  if (!socialFonts) {
    const require = createRequire(import.meta.url);
    const directory = mkdtempSync(join(tmpdir(), 'playoff-pulse-fonts-'));
    process.once('exit', () => rmSync(directory, { recursive: true, force: true }));
    socialFonts = ['latin', 'latin-ext'].flatMap((subset) => [600, 700].map((weight) => {
      const font = unwrapWoff(readFileSync(require.resolve(`@fontsource/barlow-semi-condensed/files/barlow-semi-condensed-${subset}-${weight}-normal.woff`)));
      const path = join(directory, `${subset}-${weight}.ttf`);
      writeFileSync(path, font);
      return path;
    }));
  }
  return new Resvg(svg, { font: { loadSystemFonts: false, fontFiles: socialFonts, defaultFontFamily: 'Barlow Semi Condensed' } }).render().asPng();
}

/** Build metadata and the visible snapshot from the payload, never stale index fact strings. */
export function describeLeague(entry: LeagueEntry, payload: LeaguePayload, siteUrl: string): LeaguePage {
  if (!validId.test(entry.id) || payload.league.id !== entry.id) throw new Error(`Invalid league payload: ${entry.id}`);
  const base = siteUrl.endsWith('/') ? siteUrl : `${siteUrl}/`;
  const complete = payload.metadata.season_status === 'complete';
  const started = payload.standings.some((row) => Number(row.played ?? row.matches ?? 0) > 0);
  const status = complete ? 'Final' : /playoff|postseason/.test(payload.metadata.season_status) ? 'Playoffs' : started ? 'In season' : 'Pre-season';
  const heading = `${payload.league.name} ${payload.league.seasonLabel}`;
  const title = `${heading} ${complete ? 'Final Standings' : 'Standings & Odds'} | Playoff Pulse`;
  const rows = [...payload.standings].sort((a, b) => a.rank - b.rank);
  const cricket = (payload.league.sport ?? entry.sport ?? 'cricket') === 'cricket';
  const columns: Column[] = [...(payload.league.columns ?? (cricket
    ? [{ key: 'matches', label: 'Played' }, { key: 'wins', label: 'Wins' }, { key: 'points', label: 'Points' }, { key: 'nrr', label: 'NRR', signed: true }]
    : [{ key: 'points', label: 'Points' }, { key: 'wins', label: 'Wins' }]))];
  if (rows.some((row) => row.group || row.conference)) columns.unshift({ key: rows.some((row) => row.group) ? 'group' : 'conference', label: 'Group' });
  const tiers = payload.league.tiers ?? payload.league.qualification?.map((tier) => ({ key: `top${tier.size}`, label: tier.label })) ?? [];
  if (!complete) columns.push(...tiers.map((tier) => ({ ...tier, probability: true })));

  const facts: Fact[] = [];
  const championKey = payload.playoffs?.champion ?? entry.champion;
  const champion = rows.find((row) => row.teamKey === championKey || row.shortName === championKey);
  if (complete && champion) facts.push({ label: 'Champions', value: champion.fullName });
  const probabilities = payload.analysis.probabilities ?? payload.analysis.overallProbabilities ?? {};
  if (!complete && tiers[0]) {
    const tier = tiers[0];
    const favourite = [...rows].sort((a, b) => (probabilities[b.teamKey]?.[tier.key] ?? -1) - (probabilities[a.teamKey]?.[tier.key] ?? -1))[0];
    const chance = favourite && probabilities[favourite.teamKey]?.[tier.key];
    if (chance !== undefined) facts.push({ label: `${tier.label} favourite`, value: `${favourite.shortName} ${formatProbability(payload, chance)}` });
  }
  const leader = rows[0];
  if (leader) facts.push({ label: 'Standings leader', value: `${leader.fullName}${typeof leader.points === 'number' ? ` · ${leader.points} points` : typeof leader.wins === 'number' ? ` · ${leader.wins} wins` : ''}` });
  if (typeof payload.league.eventsLeft === 'number') facts.push({ label: 'Grands Prix remaining', value: String(payload.league.eventsLeft) });
  const description = `${heading}: ${status.toLowerCase()} standings${complete ? '' : ' and model probabilities'}. ${facts.map((fact) => `${fact.label}: ${fact.value}.`).join(' ')} Updated ${payload.metadata.generated_at.slice(0, 10)}.`;
  return {
    id: entry.id, title, heading, description, status, rows, columns, facts, payload, base,
    updated: payload.metadata.generated_at,
    canonical: new URL(`league/${entry.id}/`, base).href,
    image: new URL(`social/og/${entry.id}.png`, base).href,
    dataUrl: new URL(entry.path, base).href,
  };
}

function formatProbability(payload: LeaguePayload, value: number) {
  return payload.analysis.method.toLowerCase().includes('monte carlo') ? formatChance(value) : `${Number(value.toFixed(2))}%`;
}

function cell(page: LeaguePage, row: Standing, column: Column) {
  if (column.probability) {
    const value = (page.payload.analysis.probabilities ?? page.payload.analysis.overallProbabilities)?.[row.teamKey]?.[column.key];
    return typeof value === 'number' ? formatProbability(page.payload, value) : '—';
  }
  const value = row[column.key];
  if (typeof value === 'number') {
    if (column.key === 'nrr') return `${value > 0 ? '+' : ''}${value.toFixed(3)}`;
    if (column.key === 'pct') return value.toFixed(3);
    return `${column.signed && value > 0 ? '+' : ''}${value}`;
  }
  return typeof value === 'string' ? value : '—';
}

function standingsTable(page: LeaguePage) {
  const headers = page.columns.map((column) => `<th scope="col">${escapeHtml(column.label)}</th>`).join('');
  const rows = page.rows.map((row) => `<tr><td>${row.rank}</td><th scope="row">${escapeHtml(row.fullName)}</th>${page.columns.map((column) => `<td>${escapeHtml(cell(page, row, column))}</td>`).join('')}</tr>`).join('\n');
  return `<div class="snapshot-scroll"><table><caption>${escapeHtml(page.heading)} ${page.status === 'Final' ? 'final' : 'current'} standings</caption><thead><tr><th scope="col">Rank</th><th scope="col">${page.payload.league.sport === 'motorsport' ? 'Driver' : 'Team'}</th>${headers}</tr></thead><tbody>${rows || `<tr><td colspan="${page.columns.length + 2}">Standings are not available yet.</td></tr>`}</tbody></table></div>`;
}

export function leagueJsonLd(page: LeaguePage) {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      { '@type': 'WebSite', '@id': `${page.base}#website`, name: 'Playoff Pulse', url: page.base },
      { '@type': 'WebPage', '@id': `${page.canonical}#webpage`, url: page.canonical, name: page.title, description: page.description, dateModified: page.updated, isPartOf: { '@id': `${page.base}#website` }, mainEntity: { '@id': `${page.canonical}#dataset` }, primaryImageOfPage: { '@type': 'ImageObject', url: page.image, width: 1200, height: 630 } },
      { '@type': 'Dataset', '@id': `${page.canonical}#dataset`, name: `${page.heading} standings and probabilities`, description: page.description, url: page.canonical, dateModified: page.updated, creator: { '@type': 'Organization', name: 'Playoff Pulse' }, distribution: { '@type': 'DataDownload', encodingFormat: 'application/json', contentUrl: page.dataUrl }, ...(page.payload.metadata.source_url ? { isBasedOn: page.payload.metadata.source_url } : {}) },
    ],
  };
}

/** Initial source content for crawlers and JavaScript-free readers; React replaces it when it loads. */
export function renderLeagueHtml(template: string, page: LeaguePage) {
  const content = `<main id="source-snapshot"><nav aria-label="Site"><a href="${escapeHtml(page.base)}">Playoff Pulse</a> · <a href="${escapeHtml(page.base)}?view=hub">All sports</a></nav><p>${escapeHtml(page.status)}</p><h1>${escapeHtml(page.heading)}</h1><p>${escapeHtml(page.description)}</p><dl>${page.facts.map((fact) => `<div><dt>${escapeHtml(fact.label)}</dt><dd>${escapeHtml(fact.value)}</dd></div>`).join('')}</dl>${standingsTable(page)}<h2>Source and method</h2><p>Snapshot updated <time datetime="${escapeHtml(page.updated)}">${escapeHtml(page.updated)}</time>. Source: ${escapeHtml(page.payload.metadata.source)}. Method: ${escapeHtml(page.payload.analysis.model ?? page.payload.analysis.method)}.</p>${(page.payload.metadata.warnings ?? []).map((warning) => `<p>Source notice: ${escapeHtml(warning)}</p>`).join('')}<details><summary>Model notes</summary><ul>${(page.payload.analysis.modelNotes ?? []).map((note) => `<li>${escapeHtml(note)}</li>`).join('')}</ul></details><p>Interactive team analysis loads when JavaScript is available. <a href="${escapeHtml(page.dataUrl)}">View this data snapshot</a>.</p></main>`;
  let html = template.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(page.title)}</title>`)
    .replace(/<link\b(?=[^>]*\brel="canonical")[^>]*>/gi, '')
    .replace(/<meta\b(?=[^>]*(?:\bname="(?:description|twitter:[^"]+)"|\bproperty="og:[^"]+"))[^>]*>/gi, '');
  const meta = `<link rel="canonical" href="${escapeHtml(page.canonical)}" />
<meta name="description" content="${escapeHtml(page.description)}" />
<meta property="og:site_name" content="Playoff Pulse" /><meta property="og:type" content="website" />
<meta property="og:title" content="${escapeHtml(page.title)}" /><meta property="og:description" content="${escapeHtml(page.description)}" /><meta property="og:url" content="${escapeHtml(page.canonical)}" />
<meta property="og:image" content="${escapeHtml(page.image)}" /><meta property="og:image:width" content="1200" /><meta property="og:image:height" content="630" /><meta property="og:image:alt" content="${escapeHtml(page.title)}" />
<meta name="twitter:card" content="summary_large_image" /><meta name="twitter:title" content="${escapeHtml(page.title)}" /><meta name="twitter:description" content="${escapeHtml(page.description)}" /><meta name="twitter:image" content="${escapeHtml(page.image)}" />
<script type="application/ld+json" data-ipl-jsonld="true">${safeJson(leagueJsonLd(page))}</script>
<style>#source-snapshot{font-family:system-ui,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;color:#17212b;background:#fff}#source-snapshot a{color:#456500}#source-snapshot h1{font-size:32px}#source-snapshot dl{display:flex;flex-wrap:wrap;gap:24px}#source-snapshot dd{margin:4px 0;font-weight:600}#source-snapshot .snapshot-scroll{overflow-x:auto}#source-snapshot table{border-collapse:collapse;min-width:640px;width:100%;font-variant-numeric:tabular-nums}#source-snapshot caption{text-align:left;font-weight:600;padding:16px 0}#source-snapshot th,#source-snapshot td{text-align:left;padding:12px;border-bottom:1px solid #dce2e8}#source-snapshot details{padding:16px 0}</style>`;
  html = html.replace('</head>', `${meta}\n</head>`);
  if (!/<div id="root"><\/div>/.test(html)) throw new Error('Built index is missing its React root.');
  return html.replace('<div id="root"></div>', `<div id="root">${content}</div>`);
}

const accents: Record<string, string> = { cricket: '#82c4ff', motorsport: '#ff9b8d', basketball: '#ffbd88', 'american-football': '#c4afff', 'ice-hockey': '#a4daed', baseball: '#97c7ff' };
function wrap(value: string, max = 34) {
  const lines: string[] = [];
  value.split(/\s+/).forEach((word) => {
    const last = lines.length - 1;
    if (last < 0 || `${lines[last]} ${word}`.length > max) lines.push(word);
    else lines[last] += ` ${word}`;
  });
  return lines;
}

/** A current snapshot card, without invented movement, trends or history. */
export function renderLeagueOgSvg(page: LeaguePage) {
  const accent = accents[page.payload.league.sport ?? 'cricket'] ?? '#d4f75b';
  const heading = wrap(page.heading, 36).slice(0, 3);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630"><rect width="1200" height="630" fill="#0b1016"/><rect x="0" y="0" width="12" height="630" fill="${accent}"/><g font-family="Barlow Semi Condensed"><path d="M62 63h18l10-26 19 50 11-33h23" fill="none" stroke="#d4f75b" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><text x="166" y="72" fill="#f2f5f8" font-size="32" font-weight="700">PLAYOFF PULSE</text><text x="1128" y="72" text-anchor="end" fill="${accent}" font-size="24">${escapeHtml(page.status.toUpperCase())}</text>${heading.map((line, i) => `<text x="64" y="${154 + i * 60}" fill="#f2f5f8" font-size="50" font-weight="700">${escapeHtml(line)}</text>`).join('')}<line x1="64" x2="1136" y1="322" y2="322" stroke="#334353"/>${page.facts.slice(0, 2).map((fact, i) => `<text x="${64 + i * 550}" y="374" fill="#9eafc1" font-size="22">${escapeHtml(fact.label.toUpperCase())}</text>${wrap(fact.value, 30).slice(0, 2).map((line, j) => `<text x="${64 + i * 550}" y="${421 + j * 38}" fill="${i ? '#f2f5f8' : accent}" font-size="32" font-weight="700">${escapeHtml(line)}</text>`).join('')}`).join('')}<text x="64" y="558" fill="#b7c4d1" font-size="22">${escapeHtml(page.payload.analysis.model ?? page.payload.analysis.method)}</text><text x="64" y="596" fill="#9eafc1" font-size="20">Data updated ${escapeHtml(page.updated.slice(0, 16).replace('T', ' '))} UTC · playoff-pulse</text></g></svg>`;
}

function renderHomeOgSvg(leagueCount: number, sportCount: number) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630"><rect width="1200" height="630" fill="#0b1016"/><rect width="12" height="630" fill="#d4f75b"/><g font-family="Barlow Semi Condensed"><path d="M64 76h24l13-34 25 65 15-43h40" fill="none" stroke="#d4f75b" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><text x="64" y="235" fill="#f2f5f8" font-size="100" font-weight="700">Playoff Pulse</text><text x="64" y="320" fill="#d4f75b" font-size="56" font-weight="700">Follow the race. See the possibilities.</text><line x1="64" x2="1136" y1="390" y2="390" stroke="#334353"/><text x="64" y="468" fill="#f2f5f8" font-size="36">${leagueCount} competitions · ${sportCount} sports</text><text x="64" y="532" fill="#b7c4d1" font-size="30">Standings · title odds · playoff paths · relegation</text><text x="64" y="592" fill="#9eafc1" font-size="22">Data-backed season snapshots · Playoff Pulse</text></g></svg>`;
}

/** Build-only: one real document and raster social card per published league. */
export function leaguePagesPlugin(siteUrl: string | undefined): Plugin {
  let publicDir: string;
  let base: string;
  return {
    name: 'static-league-pages', enforce: 'post', apply: 'build',
    configResolved(config) { publicDir = config.publicDir; base = config.base; },
    generateBundle: {
      order: 'post',
      handler(_options, bundle) {
        const template = bundle['index.html'];
        if (!template || template.type !== 'asset') throw new Error('Missing built index.html.');
        const site = siteUrl ?? (base === '/' ? 'https://ipl-playoff-pulse.pages.dev/' : `https://rakeshnreddy.github.io${base}`);
        const entries = (JSON.parse(readFileSync(resolve(publicDir, 'data/leagues.json'), 'utf8')) as { leagues: LeagueEntry[] }).leagues;
        this.emitFile({ type: 'asset', fileName: 'social/og/playoff-pulse.png', source: renderSocialPng(renderHomeOgSvg(entries.length, new Set(entries.map((entry) => entry.sport ?? 'cricket')).size)) });
        const homeImage = new URL('social/og/playoff-pulse.png', site).href;
        const homeTemplate = String(template.source).replace(/<link\b(?=[^>]*\brel="canonical")[^>]*>/i, `<link rel="canonical" href="${escapeHtml(site)}" />`).replace(/<meta property="og:url"[^>]*>/i, `<meta property="og:url" content="${escapeHtml(site)}" />`).replace(/<meta name="twitter:card"[^>]*>/i, '<meta name="twitter:card" content="summary_large_image" />').replace('</head>', `<meta property="og:image" content="${escapeHtml(homeImage)}" /><meta name="twitter:image" content="${escapeHtml(homeImage)}" />\n</head>`);
        template.source = homeTemplate;
        for (const entry of entries) {
          if (!validId.test(entry.id) || entry.path !== `data/${entry.id}.json`) throw new Error(`Unsafe league path: ${entry.id}`);
          const payload = JSON.parse(readFileSync(resolve(publicDir, entry.path), 'utf8')) as LeaguePayload;
          const page = describeLeague(entry, payload, site);
          this.emitFile({ type: 'asset', fileName: `league/${entry.id}/index.html`, source: renderLeagueHtml(homeTemplate, page) });
          const png = renderSocialPng(renderLeagueOgSvg(page));
          this.emitFile({ type: 'asset', fileName: `social/og/${entry.id}.png`, source: png });
        }
      },
    },
  };
}
