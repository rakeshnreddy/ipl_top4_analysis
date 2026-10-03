/// <reference types="vitest/globals" />
import { describe, expect, it, vi } from 'vitest';
import { loadIplData, type IplSeasonPayload } from './iplData';

const validPayload: IplSeasonPayload = {
  metadata: {
    season: 2026,
    generated_at: '2026-05-01T21:13:08Z',
    source: 'CricketData',
    source_url: 'https://cricketdata.org/',
    data_freshness_status: 'fresh',
    warnings: [],
  },
  standings: Array.from({ length: 10 }, (_, index) => ({
    teamKey: `Team${index}`,
    shortName: `T${index}`,
    fullName: `Team ${index}`,
    matches: 8,
    wins: 4,
    losses: 4,
    noResult: 0,
    points: 8,
    nrr: index / 10,
    rank: index + 1,
    remainingMatches: 6,
  })),
  fixtures: [],
  analysis: {
    method: 'Exhaustive',
    simulationCount: 1,
    generatedAt: '2026-05-01T21:13:08Z',
    overallProbabilities: {},
    teamAnalysis: { '4': {}, '2': {} },
    qualificationPath: { '4': {}, '2': {} },
  },
};

describe('loadIplData', () => {
  it('loads and validates the canonical payload', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => validPayload,
    });

    await expect(loadIplData(fetchImpl as unknown as typeof fetch)).resolves.toEqual(validPayload);
    expect(fetchImpl).toHaveBeenCalledWith('/data/ipl-2026.json', { cache: 'no-cache' });
  });

  it('allows standings rows without NRR', async () => {
    const payloadWithoutNrr = {
      ...validPayload,
      standings: validPayload.standings.map((team) => ({ ...team, nrr: null })),
    };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => payloadWithoutNrr,
    });

    await expect(loadIplData(fetchImpl as unknown as typeof fetch)).resolves.toEqual(payloadWithoutNrr);
  });

  it('loads another league and checks its own team count', async () => {
    const fiveTeams = {
      ...validPayload,
      league: {
        id: 'wpl-2026',
        name: "Women's Premier League",
        shortName: 'WPL',
        season: '2025/26',
        seasonLabel: '2026',
        matchesPerTeam: 8,
        qualification: [{ size: 3, label: 'Top 3' }],
        secondChanceStages: [],
        teams: validPayload.standings.slice(0, 5).map((team) => ({
          key: team.teamKey,
          shortName: team.shortName,
          fullName: team.fullName,
          color: '#000000',
          textColor: '#ffffff',
        })),
      },
    };
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => fiveTeams });

    await expect(loadIplData(fetchImpl as unknown as typeof fetch, 'wpl-2026')).rejects.toThrow(
      'Expected 5 WPL teams, found 10.',
    );
    expect(fetchImpl).toHaveBeenCalledWith('/data/wpl-2026.json', { cache: 'no-cache' });
  });

  it('rejects malformed payloads', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...validPayload, standings: [] }),
    });

    await expect(loadIplData(fetchImpl as unknown as typeof fetch)).rejects.toThrow('Expected 10 IPL teams');
  });
});
