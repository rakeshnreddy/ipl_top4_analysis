/// <reference types="vitest/globals" />
import { describe, expect, it, vi } from 'vitest';
import { loadIplData, type IplSeasonPayload } from './iplData';

const validPayload: IplSeasonPayload = {
  metadata: {
    season: 2026,
    generated_at: '2026-05-01T21:13:08Z',
    source: 'Cricbuzz',
    source_url: 'https://example.com',
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
    expect(fetchImpl).toHaveBeenCalledWith('/ipl_top4_analysis/data/ipl-2026.json', { cache: 'no-cache' });
  });

  it('rejects malformed payloads', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...validPayload, standings: [] }),
    });

    await expect(loadIplData(fetchImpl as unknown as typeof fetch)).rejects.toThrow('Expected 10 IPL teams');
  });
});
