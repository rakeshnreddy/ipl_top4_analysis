import { describe, expect, it } from 'vitest';
import { legacyQueryRedirectScript, renderCricketSource, renderDirectorySource, renderHomeSource, renderNotFound, type SearchLeague } from './site-seo';
import { CRICKET_TITLE, HOME_TITLE, PRIMARY_SITE_URL } from '../src/lib/siteIdentity';

const template = '<!doctype html><html><head><base href="/" /><title>Old</title><link rel="canonical" href="https://rakeshnreddy.github.io/ipl_top4_analysis/" /><meta name="description" content="old" /></head><body><div id="root"></div><script type="module" src="/assets/main.js"></script></body></html>';
const entries: SearchLeague[] = [
  { id: 'epl-2026-27', name: 'Premier League', seasonLabel: '2026–27', sport: 'football', status: 'league_stage' },
  { id: 'ipl-2026', name: 'Indian Premier League', seasonLabel: '2026', sport: 'cricket', status: 'complete' },
];
const documentOf = (html: string) => new DOMParser().parseFromString(html, 'text/html');

describe('initial search documents', () => {
  it('serves useful home content and real league links on both deployment bases', () => {
    for (const base of ['/', '/ipl_top4_analysis/']) {
      const doc = documentOf(renderHomeSource(template, entries, base));
      expect(doc.title).toBe(HOME_TITLE);
      expect(doc.querySelector('#root h1')?.textContent).toBe('Playoff odds, standings and live cricket');
      expect(doc.querySelector('noscript')).toBeNull();
      expect(doc.querySelector('a[href="' + base + 'league/epl-2026-27/"]')).not.toBeNull();
      expect(doc.body.textContent).toContain('Final standings and results');
      expect(doc.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
      expect(doc.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(PRIMARY_SITE_URL);
      expect(doc.querySelector('meta[property="og:url"]')?.getAttribute('content')).toBe(PRIMARY_SITE_URL);
      expect(doc.querySelector('script[type="module"]')?.getAttribute('src')).toBe('/assets/main.js');
    }
  });

  it('gives the directory a durable canonical and a list matching visible published leagues', () => {
    const doc = documentOf(renderDirectorySource(template, entries, '/ipl_top4_analysis/'));
    expect(doc.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`${PRIMARY_SITE_URL}leagues/`);
    const data = JSON.parse(doc.querySelector('script[type="application/ld+json"]')!.textContent!);
    const list = data['@graph'][1].mainEntity.itemListElement;
    expect(list).toHaveLength(entries.length);
    expect(list[0].url).toBe(`${PRIMARY_SITE_URL}league/epl-2026-27/`);
    expect(doc.querySelectorAll('#root section li')).toHaveLength(entries.length);
  });

  it('describes cricket capability without inventing matches and retains crawlable attribution', () => {
    const credited = template.replace('</body>', '<footer><a href="https://sportscore.com/" rel="dofollow" title="Sports data by SportScore">Powered by SportScore</a></footer></body>');
    const doc = documentOf(renderCricketSource(credited, '/'));
    expect(doc.title).toBe(CRICKET_TITLE);
    expect(doc.querySelector('#root')?.textContent).toContain('Missing scorecards');
    expect(doc.querySelector('footer a')?.getAttribute('rel')).toBe('dofollow');
    const data = JSON.parse(doc.querySelector('script[type="application/ld+json"]')!.textContent!);
    expect(data['@type']).toBe('CollectionPage');
    expect(data.url).toBe(`${PRIMARY_SITE_URL}cricket/`);
    expect(JSON.stringify(data)).not.toContain('SportsEvent');
  });

  it('offers an unindexable standalone 404 without an app fallback or a home canonical', () => {
    for (const base of ['/', '/ipl_top4_analysis/']) {
      const doc = documentOf(renderNotFound(base));
      expect(doc.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, follow');
      expect(doc.querySelector('h1')?.textContent).toBe('Page not found');
      expect(doc.querySelector('link[rel="canonical"]')).toBeNull();
      expect(doc.querySelector('script')).toBeNull();
      expect(doc.querySelector(`a[href="${base}leagues/"]`)).not.toBeNull();
    }
  });

  it('escapes published names in content and structured data', () => {
    const malicious = [{ ...entries[0], name: '</script><img src=x onerror=alert(1)>' }];
    const doc = documentOf(renderDirectorySource(template, malicious, '/'));
    expect(doc.querySelector('img')).toBeNull();
    expect(doc.querySelector('section a')?.textContent).toContain(malicious[0].name);
    expect(JSON.parse(doc.querySelector('script[type="application/ld+json"]')!.textContent!)['@graph'][1].mainEntity.itemListElement[0].name).toContain(malicious[0].name);
  });

  it('redirects published legacy query bookmarks to their static local path and keeps team fragments', () => {
    for (const base of ['/', '/ipl_top4_analysis/']) {
      const redirects: string[] = [];
      const run = (search: string, pathname = base) => new Function('location', legacyQueryRedirectScript(entries, base))({ pathname, search, hash: '#team=ARS', replace: (url: string) => redirects.push(url) });
      run('?league=%20EPL-2026-27%20&utm_source=old');
      run('?view=hub');
      expect(redirects).toEqual([`${base}league/epl-2026-27/#team=ARS`, `${base}leagues/#team=ARS`]);
      run('?league=unpublished&view=hub');
      run('?league=../other');
      run('?league=ipl-2026', `${base}league/epl-2026-27/`);
      expect(redirects).toHaveLength(2);
    }
  });
});
