/// <reference types="vitest/globals" />
import { describe, expect, it, vi } from 'vitest';
import { canonicalLeagueHref, hubHref, leagueHref, leagueIdFromLocation, leaguesBySport, loadLeagueIndex, sportName, type LeagueSummary } from './leagues';
import { setJsonLd, setPageMeta } from '../lib/seo';
import { samePageHref } from '../lib/ui';

describe('league helpers', () => {
  it('reads a well-formed league id from the query string', () => {
    expect(leagueIdFromLocation('?league=WPL-2026')).toBe('wpl-2026');
    expect(leagueIdFromLocation('?league=../secrets')).toBeNull();
    expect(leagueIdFromLocation('')).toBeNull();
  });

  it('gives every league and the hub an address of its own (the root is the landing page)', () => {
    expect(leagueHref('ipl-2026', 'ipl-2026')).toBe('/?league=ipl-2026');
    expect(leagueHref('bbl-2025-26')).toBe('/?league=bbl-2025-26');
    expect(hubHref('hub')).toBe('/?view=hub');
  });

  it('opens canonical paths while preserving legacy query links', () => {
    expect(canonicalLeagueHref('epl-2026-27')).toBe('/league/epl-2026-27/');
    expect(leagueIdFromLocation('', '/league/epl-2026-27/')).toBe('epl-2026-27');
    expect(leagueIdFromLocation('?league=ipl-2026', '/league/f1-2026/index.html')).toBe('f1-2026');
    expect(leagueIdFromLocation('?league=ipl-2026', '/')).toBe('ipl-2026');
    expect(leagueIdFromLocation('', '/league/../secrets/')).toBeNull();
    expect(leagueIdFromLocation('', '/league/%25/')).toBeNull();
  });

  it('keeps section and team destinations on canonical paths under the GitHub base', () => {
    vi.stubEnv('BASE_URL', '/ipl_top4_analysis/');
    window.history.replaceState(null, '', '/ipl_top4_analysis/league/epl-2026-27/?source=share#team=Arsenal');
    expect(leagueIdFromLocation()).toBe('epl-2026-27');
    expect(canonicalLeagueHref('epl-2026-27')).toBe('/ipl_top4_analysis/league/epl-2026-27/');
    expect(samePageHref('standings')).toBe('/ipl_top4_analysis/league/epl-2026-27/?source=share#standings');
    expect(samePageHref('team=Arsenal')).toBe('/ipl_top4_analysis/league/epl-2026-27/?source=share#team=Arsenal');
    window.history.replaceState(null, '', '/');
    vi.unstubAllEnvs();
  });

  it('canonicalizes legacy metadata and JSON-LD while preserving their fragments', () => {
    const origin = window.location.origin;
    setPageMeta('Premier League', 'A current snapshot', `${origin}/?league=epl-2026-27`);
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`${origin}/league/epl-2026-27/`);
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(`${origin}/social/og/epl-2026-27.png`);
    setJsonLd({ '@id': `${origin}/?league=epl-2026-27#dataset`, url: 'https://example.org/?league=external' });
    const data = JSON.parse(document.querySelector('script[data-ipl-jsonld]')!.textContent!);
    expect(data['@id']).toBe(`${origin}/league/epl-2026-27/#dataset`);
    expect(data.url).toBe('https://example.org/?league=external');
  });

  it('gives basketball and motorsport their own rows, away from the other North American leagues', () => {
    const league = (id: string, sport: string): LeagueSummary => ({
      id,
      sport,
      name: id,
      shortName: id.toUpperCase(),
      seasonLabel: '2026',
      status: 'in_progress',
      champion: null,
      generatedAt: '2026-10-04T00:00:00Z',
      path: `data/${id}.json`,
    });
    const rows = leaguesBySport({
      default: 'hub',
      leagues: [
        league('nfl', 'american-football'),
        league('nba', 'basketball'),
        league('nbl', 'basketball'),
        league('nhl', 'ice-hockey'),
        league('f1-2026', 'motorsport'),
      ],
    });

    expect(rows.map((row) => [row.label, row.leagues.map((item) => item.id)])).toEqual([
      ['US sports', ['nfl', 'nhl']],
      ['Basketball', ['nba', 'nbl']],
      ['Motorsport', ['f1-2026']],
    ]);
    expect(sportName('motorsport')).toBe('Motorsport');
  });

  it('rejects a malformed league list', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ leagues: 'nope' }) });

    await expect(loadLeagueIndex(fetchImpl as unknown as typeof fetch)).rejects.toThrow('League list is malformed.');
  });
});
