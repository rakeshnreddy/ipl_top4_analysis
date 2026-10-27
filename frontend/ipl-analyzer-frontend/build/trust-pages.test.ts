import { describe, expect, it } from 'vitest';
import { buildTrustPages } from './trust-pages';

describe('crawlable trust and revenue documents', () => {
  it('publishes useful standalone documents with primary canonicals and local navigation on both bases', () => {
    for (const base of ['/', '/ipl_top4_analysis/']) {
      const pages = buildTrustPages(base);
      expect(Object.keys(pages).sort()).toEqual(['about/index.html', 'advertise/index.html', 'methodology/index.html', 'privacy/index.html']);
      for (const [path, html] of Object.entries(pages)) {
        const page = new DOMParser().parseFromString(html, 'text/html');
        const slug = path.replace('index.html', '');
        expect(page.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`https://ipl-playoff-pulse.pages.dev/${slug}`);
        expect(page.querySelectorAll('h1')).toHaveLength(1);
        expect(page.querySelector('main')!.textContent!.length).toBeGreaterThan(1500);
        expect(page.querySelector('nav[aria-label="Main sections"] a[href="'+base+'cricket/"]')).not.toBeNull();
        expect(page.querySelector('nav[aria-label="About Playoff Pulse"] a[href="'+base+'privacy/"]')).not.toBeNull();
        expect(page.querySelector('meta[name="description"]')?.getAttribute('content')?.length).toBeGreaterThan(60);
        expect(page.querySelector('script[src]')).toBeNull();
        expect(page.querySelector('main')!.textContent).not.toContain('pub-0000000000000000');
      }
      expect(pages['methodology/index.html']).toContain('17.5');
      expect(pages['methodology/index.html']).toContain('107 legal balls');
      expect(pages['privacy/index.html']).toContain('pp-theme');
      expect(pages['privacy/index.html']).toContain('SportScore');
      expect(pages['advertise/index.html']).toContain('https://github.com/rakeshnreddy/ipl_top4_analysis/issues/new');
    }
  });

  it('does not emit an ads.txt declaration or advertiser verification without an actual supplied ID', () => {
    const defaults = buildTrustPages('/');
    expect(defaults['ads.txt']).toBeUndefined();
    expect(Object.values(defaults).join('')).not.toContain('google-adsense-account');
    expect(buildTrustPages('/', { VITE_ADSENSE_PUBLISHER_ID: 'ca-pub-0000000000000000' })['ads.txt']).toBeUndefined();
    const supplied = buildTrustPages('/', { VITE_ADSENSE_PUBLISHER_ID: 'ca-pub-9876543210987654' });
    expect(supplied['ads.txt']).toBe('google.com, pub-9876543210987654, DIRECT, f08c47fec0942fa0\n');
    expect(supplied['about/index.html']).toContain('<meta name="google-adsense-account" content="ca-pub-9876543210987654"');
    expect(Object.values(supplied).join('')).not.toContain('adsbygoogle.js');
    const mirror = buildTrustPages('/ipl_top4_analysis/', { VITE_ADSENSE_PUBLISHER_ID: 'ca-pub-9876543210987654' });
    expect(mirror['ads.txt']).toBeUndefined();
    expect(Object.values(mirror).join('')).not.toContain('google-adsense-account');
  });

  it('uses a supplied public contact address safely and never fabricates a private address', () => {
    const valid = buildTrustPages('/', { VITE_PUBLIC_CONTACT_EMAIL: 'partnerships@example.org' });
    const document = new DOMParser().parseFromString(valid['advertise/index.html'], 'text/html');
    expect(document.querySelector('a[href^="mailto:"]')?.getAttribute('href')).toBe('mailto:partnerships@example.org');
    for (const email of ['', 'bad\naddress@example.org', '<img src=x onerror=alert(1)>', 'address@example.org?bcc=private@example.org']) {
      const html = buildTrustPages('/', { VITE_PUBLIC_CONTACT_EMAIL: email })['advertise/index.html'];
      const page = new DOMParser().parseFromString(html, 'text/html');
      expect(page.querySelector('a[href^="mailto:"]')).toBeNull();
      expect(page.querySelector('img')).toBeNull();
    }
  });
});
