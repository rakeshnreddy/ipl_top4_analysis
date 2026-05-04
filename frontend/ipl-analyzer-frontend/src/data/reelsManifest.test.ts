/// <reference types="vitest/globals" />
import { describe, expect, it, vi } from 'vitest';
import { loadReelsManifest, publicAssetUrl, type ReelsManifest } from './reelsManifest';

const validManifest: ReelsManifest = {
  latestDate: '2026-05-04',
  dates: ['2026-05-04'],
  slides: [
    {
      date: '2026-05-04',
      fileName: 'slide-01-overview.png',
      path: 'social/instagram-carousel/2026-05-04/slide-01-overview.png',
      downloadName: 'ipl-playoff-pulse-2026-05-04-slide-01-overview.png',
      imageWidth: 1080,
      imageHeight: 1920,
    },
  ],
  generatedAt: '2026-05-04T09:00:00Z',
  source: {
    name: 'CricketData',
    url: 'https://cricketdata.org/',
    dataGeneratedAt: '2026-05-04T08:06:47Z',
  },
  warnings: [],
  imageWidth: 1080,
  imageHeight: 1920,
  latestPackPath: 'social/instagram-carousel/2026-05-04/',
  latestPreviewPath: 'social/instagram-carousel/latest-overview.png',
};

describe('loadReelsManifest', () => {
  it('loads and validates the latest carousel manifest', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => validManifest,
    });

    await expect(loadReelsManifest(fetchImpl as unknown as typeof fetch)).resolves.toEqual(validManifest);
    expect(fetchImpl).toHaveBeenCalledWith('/ipl_top4_analysis/social/instagram-carousel/manifest.json', { cache: 'no-cache' });
  });

  it('rejects malformed manifests', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...validManifest, slides: [{ path: 'missing-file-name.png' }] }),
    });

    await expect(loadReelsManifest(fetchImpl as unknown as typeof fetch)).rejects.toThrow('missing file metadata');
  });

  it('builds public asset URLs under the app base path', () => {
    expect(publicAssetUrl('social/instagram-carousel/latest-overview.png')).toBe(
      '/ipl_top4_analysis/social/instagram-carousel/latest-overview.png',
    );
  });
});
