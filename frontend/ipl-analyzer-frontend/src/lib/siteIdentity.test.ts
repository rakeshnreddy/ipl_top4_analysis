import { describe, expect, it } from 'vitest';
import { PRIMARY_SITE_URL, primaryPageUrl } from './siteIdentity';

describe('primary search identity', () => {
  it('consolidates mirror and local preview pages without carrying tracking or fragments', () => {
    expect(primaryPageUrl('https://rakeshnreddy.github.io/ipl_top4_analysis/league/epl-2026-27/?utm_source=x#team=ARS')).toBe(`${PRIMARY_SITE_URL}league/epl-2026-27/`);
    expect(primaryPageUrl('http://localhost:5193/ipl_top4_analysis/cricket/?match=ss-123-a-b#score', '/ipl_top4_analysis/')).toBe(`${PRIMARY_SITE_URL}cricket/`);
    expect(primaryPageUrl('/ipl_top4_analysis/index.html?view=hub', '/ipl_top4_analysis/')).toBe(`${PRIMARY_SITE_URL}leagues/`);
  });

  it('preserves existing query links as semantic canonical destinations', () => {
    expect(primaryPageUrl('/?league=%20IPL-2026%20&view=hub')).toBe(`${PRIMARY_SITE_URL}league/ipl-2026/`);
    expect(primaryPageUrl('/?view=hub')).toBe(`${PRIMARY_SITE_URL}leagues/`);
    expect(primaryPageUrl('/?league=../bad')).toBe(PRIMARY_SITE_URL);
    expect(primaryPageUrl('/league/f1-2026/?league=ipl-2026')).toBe(`${PRIMARY_SITE_URL}league/f1-2026/`);
  });

  it('retains external sources and maps site assets without inventing directory slashes', () => {
    expect(primaryPageUrl('https://cricsheet.org/using/#license')).toBe('https://cricsheet.org/using/#license');
    expect(primaryPageUrl('https://schema.org')).toBe('https://schema.org');
    expect(primaryPageUrl('https://rakeshnreddy.github.io/ipl_top4_analysis/social/og/ipl-2026.png')).toBe(`${PRIMARY_SITE_URL}social/og/ipl-2026.png`);
  });
});
