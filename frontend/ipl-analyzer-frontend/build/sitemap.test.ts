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

    expect(xml).toContain('<loc>https://ipl-playoff-pulse.pages.dev/</loc><lastmod>2026-10-03</lastmod>');
    expect(xml).toContain('<loc>https://ipl-playoff-pulse.pages.dev/league/epl-2026-27/</loc><lastmod>2026-10-03</lastmod>');
    expect(xml).toContain('<loc>https://ipl-playoff-pulse.pages.dev/league/ipl-2026/</loc><lastmod>2026-06-01</lastmod>');
    // The root is the landing page, so the hub has its own address.
    expect(xml).toContain('<loc>https://ipl-playoff-pulse.pages.dev/leagues/</loc>');
  });

  it('lists a live IPL under its own address too', () => {
    const xml = buildSitemap('https://example.org/', { default: 'ipl-2027', leagues: [{ id: 'ipl-2027' }] });

    expect(xml).toContain('<loc>https://ipl-playoff-pulse.pages.dev/leagues/</loc>');
    expect(xml).toContain('<loc>https://ipl-playoff-pulse.pages.dev/league/ipl-2027/</loc>');
  });

  it('lists stable trust pages without inventing live or policy update timestamps', () => {
    const xml = buildSitemap('https://rakeshnreddy.github.io/ipl_top4_analysis/', { default: 'hub', leagues: [] });
    for (const path of ['cricket', 'about', 'methodology', 'privacy', 'advertise']) {
      expect(xml).toContain(`<loc>https://ipl-playoff-pulse.pages.dev/${path}/</loc></url>`);
    }
    expect(xml).not.toContain('github.io');
    expect(xml).not.toContain('lastmod');
    expect(xml).not.toContain('share.html');
  });
});
