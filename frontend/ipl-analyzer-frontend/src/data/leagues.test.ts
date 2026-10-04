/// <reference types="vitest/globals" />
import { describe, expect, it, vi } from 'vitest';
import { leagueHref, leagueIdFromLocation, leaguesBySport, loadLeagueIndex, type LeagueSummary } from './leagues';

describe('league helpers', () => {
  it('reads a well-formed league id from the query string', () => {
    expect(leagueIdFromLocation('?league=WPL-2026')).toBe('wpl-2026');
    expect(leagueIdFromLocation('?league=../secrets')).toBeNull();
    expect(leagueIdFromLocation('')).toBeNull();
  });

  it('links the default league to the site root', () => {
    expect(leagueHref('ipl-2026', 'ipl-2026')).toBe('/');
    expect(leagueHref('bbl-2025-26', 'ipl-2026')).toBe('/?league=bbl-2025-26');
  });

  it('gives basketball its own row, away from the other North American leagues', () => {
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
      leagues: [league('nfl', 'american-football'), league('nba', 'basketball'), league('nbl', 'basketball'), league('nhl', 'ice-hockey')],
    });

    expect(rows.map((row) => [row.label, row.leagues.map((item) => item.id)])).toEqual([
      ['US sports', ['nfl', 'nhl']],
      ['Basketball', ['nba', 'nbl']],
    ]);
  });

  it('rejects a malformed league list', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ leagues: 'nope' }) });

    await expect(loadLeagueIndex(fetchImpl as unknown as typeof fetch)).rejects.toThrow('League list is malformed.');
  });
});
