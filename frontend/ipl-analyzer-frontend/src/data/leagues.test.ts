/// <reference types="vitest/globals" />
import { describe, expect, it, vi } from 'vitest';
import { leagueHref, leagueIdFromLocation, loadLeagueIndex } from './leagues';

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

  it('rejects a malformed league list', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ leagues: 'nope' }) });

    await expect(loadLeagueIndex(fetchImpl as unknown as typeof fetch)).rejects.toThrow('League list is malformed.');
  });
});
