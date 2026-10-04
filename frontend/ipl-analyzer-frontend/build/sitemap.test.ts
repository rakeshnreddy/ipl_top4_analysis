/// <reference types="vitest/globals" />
import { describe, expect, it } from 'vitest';
import { buildSitemap } from './sitemap';

describe('buildSitemap', () => {
  it('lists the home page and every league page', () => {
    const xml = buildSitemap('https://example.org/pulse', {
      default: 'hub',
      leagues: [
        { id: 'epl-2026-27', generatedAt: '2026-10-03T19:30:00Z' },
        { id: 'ipl-2026', generatedAt: '2026-06-01T00:00:00Z' },
      ],
    });

    expect(xml).toContain('<loc>https://example.org/pulse/</loc><lastmod>2026-10-03</lastmod>');
    expect(xml).toContain('<loc>https://example.org/pulse/?league=epl-2026-27</loc><lastmod>2026-10-03</lastmod>');
    expect(xml).toContain('<loc>https://example.org/pulse/?league=ipl-2026</loc><lastmod>2026-06-01</lastmod>');
    // The root is the landing page, so the hub has its own address.
    expect(xml).toContain('<loc>https://example.org/pulse/?view=hub</loc>');
  });

  it('lists a live IPL under its own address too', () => {
    const xml = buildSitemap('https://example.org/', { default: 'ipl-2027', leagues: [{ id: 'ipl-2027' }] });

    expect(xml).toContain('<loc>https://example.org/?view=hub</loc>');
    expect(xml).toContain('<loc>https://example.org/?league=ipl-2027</loc>');
  });
});
