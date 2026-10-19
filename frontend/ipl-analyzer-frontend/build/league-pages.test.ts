/// <reference types="vitest/globals" />
/// <reference lib="dom" />
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { describeLeague, leagueJsonLd, renderLeagueHtml, renderLeagueOgSvg, renderSocialPng, type LeaguePayload } from './league-pages';

const publicDir = resolve(import.meta.dirname, '../public');
const entries = (JSON.parse(readFileSync(resolve(publicDir, 'data/leagues.json'), 'utf8')) as { leagues: { id: string; name: string; shortName: string; seasonLabel: string; path: string }[] }).leagues;
const load = (id: string) => {
  const entry = entries.find((entry) => entry.id === id)!;
  return { entry, payload: JSON.parse(readFileSync(resolve(publicDir, entry.path), 'utf8')) as LeaguePayload };
};
const template = '<html><head><base href="/" /><title>Generic</title><meta name="description" content="generic" /><meta property="og:title" content="generic" /><link rel="canonical" href="/" /></head><body><div id="root"></div><script type="module" src="/assets/main.js"></script></body></html>';

describe('static league source documents', () => {
  it('renders real source standings and metadata for every published league on both bases', () => {
    expect(entries.length).toBeGreaterThan(0);
    for (const base of ['https://ipl-playoff-pulse.pages.dev/', 'https://rakeshnreddy.github.io/ipl_top4_analysis/']) {
      for (const entry of entries) {
        const payload = load(entry.id).payload;
        const page = describeLeague(entry, payload, base);
        const document = new DOMParser().parseFromString(renderLeagueHtml(template, page), 'text/html');
        expect(document.querySelector('h1')?.textContent).toBe(page.heading);
        expect(document.querySelectorAll('tbody tr').length).toBe(payload.standings.length || 1);
        if (payload.standings[0]) expect(document.querySelector('tbody')?.textContent).toContain(payload.standings[0].fullName);
        expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`${base}league/${entry.id}/`);
        expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(`${base}social/og/${entry.id}.png`);
        const graph = JSON.parse(document.querySelector('script[type="application/ld+json"]')!.textContent!)['@graph'];
        expect(graph[1].url).toBe(page.canonical);
        expect(graph[2].distribution.contentUrl).toBe(`${base}${entry.path}`);
      }
    }
  });

  it('does not publish rounded simulation certainty or reuse stale index facts', () => {
    const { entry, payload } = load('f1-2026');
    payload.analysis.probabilities![payload.standings[0].teamKey].title = 100;
    const page = describeLeague(entry, payload, 'https://example.org/');
    expect(page.facts[0].value).toContain('>99.9%');
    const document = new DOMParser().parseFromString(renderLeagueHtml(template, page), 'text/html');
    expect(document.querySelector('tbody')?.textContent).toContain('>99.9%');
    expect(document.querySelector('tbody')?.textContent).not.toMatch(/100%/);
    expect(page.description).toContain(payload.standings[0].fullName);
  });

  it('keeps completed cricket results exact and names the actual champion', () => {
    const { entry, payload } = load('ipl-2026');
    const page = describeLeague(entry, payload, 'https://example.org/');
    expect(page.status).toBe('Final');
    expect(page.facts[0]).toEqual({ label: 'Champions', value: 'Royal Challengers Bengaluru' });
    const document = new DOMParser().parseFromString(renderLeagueHtml(template, page), 'text/html');
    expect(document.querySelector('tbody')?.textContent).toContain('+0.783');
    expect(document.querySelector('thead')?.textContent).not.toContain('Top 4');
  });

  it('escapes source text and structured data instead of allowing embedded markup', () => {
    const { entry, payload } = load('epl-2026-27');
    payload.league.name = 'A < B </script><script>alert(1)</script>';
    payload.standings[0].fullName = '<img src=x onerror=alert(1)>';
    const page = describeLeague(entry, payload, 'https://example.org/');
    const document = new DOMParser().parseFromString(renderLeagueHtml(template, page), 'text/html');
    expect(document.querySelector('h1')?.textContent).toBe(page.heading);
    expect(document.querySelector('img')).toBeNull();
    expect(document.querySelectorAll('script')).toHaveLength(2);
    expect(JSON.parse(document.querySelector('script[type="application/ld+json"]')!.textContent!)).toEqual(leagueJsonLd(page));
  });

  it('rasterizes a real snapshot social card to 1200 by 630 PNG', () => {
    const { entry, payload } = load('epl-2026-27');
    const page = describeLeague(entry, payload, 'https://example.org/');
    const svg = renderLeagueOgSvg(page);
    expect(svg).toContain(page.heading);
    expect(svg).toContain(page.updated.slice(0, 10));
    const image = renderSocialPng(svg);
    expect(image.readUInt32BE(16)).toBe(1200);
    expect(image.readUInt32BE(20)).toBe(630);
    expect(image.subarray(1, 4).toString()).toBe('PNG');
    expect(image.length).toBeGreaterThan(10000);
  });
});
