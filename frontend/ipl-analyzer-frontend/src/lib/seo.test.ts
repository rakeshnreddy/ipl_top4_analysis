import { beforeEach, describe, expect, it } from 'vitest';
import { appBaseHref, setJsonLd, setPageMeta } from './seo';
import { PRIMARY_SITE_URL } from './siteIdentity';

beforeEach(() => { document.head.innerHTML = ''; });

describe('rendered search metadata', () => {
  it('uses one primary page identity and image under the mirror base', () => {
    setPageMeta('Premier League standings', 'Current model snapshot', 'https://rakeshnreddy.github.io/ipl_top4_analysis/league/epl-2026-27/?utm_source=x#team=ARS');
    expect(appBaseHref()).toBe(PRIMARY_SITE_URL);
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`${PRIMARY_SITE_URL}league/epl-2026-27/`);
    expect(document.querySelector('meta[property="og:url"]')?.getAttribute('content')).toBe(`${PRIMARY_SITE_URL}league/epl-2026-27/`);
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(`${PRIMARY_SITE_URL}social/og/epl-2026-27.png`);
  });

  it('preserves JSON-LD entity fragments and external source identities', () => {
    setJsonLd({ '@id': 'http://localhost:3000/?league=ipl-2026#dataset', url: 'https://cricsheet.org/using/#license' });
    const data = JSON.parse(document.querySelector('script[data-ipl-jsonld]')!.textContent!);
    expect(data['@id']).toBe(`${PRIMARY_SITE_URL}league/ipl-2026/#dataset`);
    expect(data.url).toBe('https://cricsheet.org/using/#license');
  });
});
