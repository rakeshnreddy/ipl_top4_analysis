/// <reference types="vitest/globals" />
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { afterEach, describe, expect, it } from 'vitest';
import { shareDataPreloads } from './share-preloads';

const directories: string[] = [];
afterEach(() => directories.splice(0).forEach((path) => rmSync(path, { recursive: true, force: true })));
function files(latestDate = '2027-04-20', firstPath = `social/instagram-carousel/${latestDate}/overview.png`) {
  const root = mkdtempSync(join(tmpdir(), 'playoff-share-test-'));
  directories.push(root);
  const write = (path: string, value: unknown) => {
    const target = join(root, path);
    mkdirSync(join(target, '..'), { recursive: true });
    writeFileSync(target, typeof value === 'string' ? value : JSON.stringify(value));
  };
  write('data/leagues.json', { default: 'hub', ipl: 'ipl-2027', leagues: [{ id: 'ipl-2027', path: 'data/ipl-2027.json' }] });
  write('data/ipl-2027.json', {});
  write('social/instagram-carousel/manifest.json', { latestDate, slides: [{ date: latestDate, path: firstPath }, { date: '2026-05-24', path: 'social/instagram-carousel/2026-05-24/old.png' }] });
  write('social/instagram-carousel/2026-05-24/old.png', 'image placeholder');
  if (!firstPath.includes('..') && !firstPath.includes(':')) write(firstPath, 'image placeholder');
  return root;
}

describe('share critical discovery', () => {
  it('preloads the current season and actual first displayed image on both bases', () => {
    const root = files();
    for (const base of ['/', '/ipl_top4_analysis/']) {
      expect(shareDataPreloads(root, base)).toEqual([
        { href: `${base}data/leagues.json`, as: 'fetch' },
        { href: `${base}data/ipl-2027.json`, as: 'fetch' },
        { href: `${base}social/instagram-carousel/manifest.json`, as: 'fetch' },
        { href: `${base}social/instagram-carousel/2027-04-20/overview.png`, as: 'image' },
      ]);
    }
  });
  it('mirrors visible manifest order even when an older slide precedes the latest date', () => {
    const root = files();
    writeFileSync(join(root, 'social/instagram-carousel/manifest.json'), JSON.stringify({ latestDate: '2027-04-20', slides: [{ date: '2026-05-24', path: 'social/instagram-carousel/2026-05-24/old.png' }, { date: '2027-04-20', path: 'social/instagram-carousel/2027-04-20/overview.png' }] }));
    expect(shareDataPreloads(root, '/').find((hint) => hint.as === 'image')?.href).toBe('/social/instagram-carousel/2026-05-24/old.png');
  });
  it('preloads the smaller preview when published and falls back to the PNG otherwise', () => {
    const root = files();
    const previewPath = 'social/instagram-carousel/2027-04-20/overview.preview.webp';
    const path = 'social/instagram-carousel/2027-04-20/overview.png';
    writeFileSync(join(root, 'social/instagram-carousel/manifest.json'), JSON.stringify({ slides: [{ path, previewPath }] }));
    expect(shareDataPreloads(root, '/').find((hint) => hint.as === 'image')?.href).toBe(`/${path}`);
    writeFileSync(join(root, previewPath), 'preview placeholder');
    expect(shareDataPreloads(root, '/').find((hint) => hint.as === 'image')?.href).toBe(`/${previewPath}`);
  });
  it('does not preload an external or traversing manifest path', () => {
    for (const path of ['https://example.org/image.png', 'social/../../private.png']) {
      expect(shareDataPreloads(files('2027-04-20', path), '/').some((hint) => hint.as === 'image')).toBe(false);
    }
  });
  it('lets an absent optional carousel use the existing application fallback', () => {
    const root = mkdtempSync(join(tmpdir(), 'playoff-share-test-'));
    directories.push(root);
    expect(shareDataPreloads(root, '/')).toEqual([]);
  });
  it('ignores malformed optional slide entries without breaking the build', () => {
    const root = files();
    for (const slides of [null, 'invalid', [null], [{ path: null }], [{ path: { unexpected: true } }]]) {
      writeFileSync(join(root, 'social/instagram-carousel/manifest.json'), JSON.stringify({ slides }));
      expect(shareDataPreloads(root, '/').some((hint) => hint.as === 'image')).toBe(false);
    }
  });
});
