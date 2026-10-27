import { describe, expect, it } from 'vitest';
import { advertisingEligible, commercialSurfaceAllowed, monetizationFromEnv, normalizePublisherId, sponsorshipFor, type CommercialContext } from './monetization';

const reviewed: CommercialContext = {
  url: 'https://ipl-playoff-pulse.pages.dev/cricket/?match=ss-test',
  sourceIds: ['sportscore'], contentReady: true, attributionVisible: true,
};
const approved = {
  VITE_ADS_ENABLED: 'true', VITE_ADSENSE_PUBLISHER_ID: 'ca-pub-9876543210987654',
  VITE_ADSENSE_SITE_APPROVED: 'true', VITE_ADSENSE_CMP_READY: 'true',
};

describe('monetization prerequisites', () => {
  it('normalizes a supplied public publisher ID and rejects malformed or example identifiers', () => {
    expect(normalizePublisherId(' pub-9876543210987654 ')).toBe('ca-pub-9876543210987654');
    for (const value of ['', 'pub-0000000000000000', 'ca-pub-1234567890123456', 'pub-1234', 'secret', '<script>']) {
      expect(normalizePublisherId(value)).toBeNull();
    }
  });

  it('keeps ads disabled by default and when only a public publisher ID is supplied', () => {
    expect(advertisingEligible(monetizationFromEnv(), reviewed)).toBe(false);
    expect(advertisingEligible(monetizationFromEnv({ VITE_ADSENSE_PUBLISHER_ID: approved.VITE_ADSENSE_PUBLISHER_ID }), reviewed)).toBe(false);
    expect(monetizationFromEnv({ VITE_ADS_ENABLED: '1' }).adsEnabled).toBe(false);
  });

  it('requires every explicit approval and a reviewed substantive source surface', () => {
    expect(advertisingEligible(monetizationFromEnv(approved), reviewed)).toBe(true);
    for (const key of Object.keys(approved)) {
      expect(advertisingEligible(monetizationFromEnv({ ...approved, [key]: '' }), reviewed)).toBe(false);
    }
    for (const context of [
      { ...reviewed, url: 'https://rakeshnreddy.github.io/ipl_top4_analysis/cricket/' },
      { ...reviewed, url: 'https://ipl-playoff-pulse.pages.dev.attacker.example/cricket/' },
      { ...reviewed, url: 'http://ipl-playoff-pulse.pages.dev/cricket/' },
      { ...reviewed, url: 'https://ipl-playoff-pulse.pages.dev/league/f1-2026/' },
      { ...reviewed, url: 'https://ipl-playoff-pulse.pages.dev/cricket/unknown-route/' },
      { ...reviewed, url: 'https://ipl-playoff-pulse.pages.dev:8443/cricket/' },
      { ...reviewed, sourceIds: ['sportscore', 'cricketdata'] },
      { ...reviewed, sourceIds: ['jolpica'] },
      { ...reviewed, sourceIds: [] },
      { ...reviewed, contentReady: false },
      { ...reviewed, attributionVisible: false },
    ]) expect(advertisingEligible(monetizationFromEnv(approved), context)).toBe(false);
    expect(commercialSurfaceAllowed({ ...reviewed, url: 'not a URL' })).toBe(false);
  });

  it('requires supplied HTTPS sponsor details and preserves disclosure separately from provider credit', () => {
    const env = { VITE_SPONSOR_NAME: 'Example sponsor', VITE_SPONSOR_URL: 'https://sponsor.example/campaign', VITE_SPONSOR_MESSAGE: 'A supplied campaign message.' };
    expect(sponsorshipFor(monetizationFromEnv(env), reviewed)).toEqual({ name: env.VITE_SPONSOR_NAME, url: env.VITE_SPONSOR_URL, message: env.VITE_SPONSOR_MESSAGE, disclosure: 'Advertisement', rel: 'sponsored noopener noreferrer' });
    expect(sponsorshipFor(monetizationFromEnv(), reviewed)).toBeNull();
    for (const url of ['javascript:alert(1)', 'http://sponsor.example', 'https://user:password@sponsor.example']) {
      expect(sponsorshipFor(monetizationFromEnv({ ...env, VITE_SPONSOR_URL: url }), reviewed)).toBeNull();
    }
    expect(sponsorshipFor(monetizationFromEnv({ ...env, VITE_SPONSOR_MESSAGE: '' }), reviewed)).toBeNull();
    expect(sponsorshipFor(monetizationFromEnv(env), { ...reviewed, sourceIds: ['mlb'] })).toBeNull();
  });
});
