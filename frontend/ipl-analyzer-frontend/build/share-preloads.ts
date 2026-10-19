import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Plugin } from 'vite';

type ShareIndex = { ipl?: string; default?: string; leagues?: ({ id?: unknown; path?: unknown } | null)[] };
type ShareManifest = { slides?: ({ path?: unknown; previewPath?: unknown } | null)[] };

const attribute = (value: string) => value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
function readJson<T>(path: string): T | null {
  try { return JSON.parse(readFileSync(path, 'utf8')) as T; } catch { return null; }
}
function published(publicDir: string, path: string) {
  return /^(?:data|social)\/[a-zA-Z0-9_./-]+$/.test(path) && !path.split('/').includes('..') && existsSync(resolve(publicDir, path));
}

/** Hints follow the same current IPL and carousel selection as the share page. */
export function shareDataPreloads(publicDir: string, base: string) {
  const hints: { href: string; as: 'fetch' | 'image' }[] = [];
  const fetchHint = (path: string) => { if (published(publicDir, path)) hints.push({ href: base + path, as: 'fetch' }); };
  fetchHint('data/leagues.json');
  const index = readJson<ShareIndex>(resolve(publicDir, 'data/leagues.json'));
  const id = index?.ipl ?? (index?.default !== 'hub' ? index?.default : undefined);
  const path = Array.isArray(index?.leagues) ? index.leagues.find((league) => league?.id === id)?.path : undefined;
  if (typeof path === 'string') fetchHint(path);
  const manifestPath = 'social/instagram-carousel/manifest.json';
  fetchHint(manifestPath);
  const manifest = readJson<ShareManifest>(resolve(publicDir, manifestPath));
  // The page displays slides in manifest order, including mixed-date archive packs.
  const slide = Array.isArray(manifest?.slides) ? manifest.slides[0] : undefined;
  const first = typeof slide?.previewPath === 'string' && published(publicDir, slide.previewPath) ? slide.previewPath : slide?.path;
  if (typeof first === 'string' && /\.(?:png|jpe?g|webp)$/i.test(first) && published(publicDir, first)) hints.push({ href: base + first, as: 'image' });
  return hints;
}

/** Discover the first graphic, its data, and the fonts used for initial headings. */
export function sharePreloadsPlugin(): Plugin {
  let publicDir: string;
  let base: string;
  return {
    name: 'share-critical-preloads', apply: 'build', enforce: 'post',
    configResolved(config) { publicDir = config.publicDir; base = config.base; },
    generateBundle: {
      order: 'post',
      handler(_options, bundle) {
        const share = bundle['share.html'];
        if (share?.type !== 'asset') return;
        let html = String(share.source);
        const hints = shareDataPreloads(publicDir, base).map(({ href, as }) => ({ href, tag: `<link rel="preload" as="${as}" href="${attribute(href)}" ${as === 'fetch' ? 'crossorigin="anonymous"' : 'fetchpriority="high"'} />` }));
        for (const file of Object.keys(bundle)) {
          if (/(?:barlow-semi-condensed-latin-700-normal|ibm-plex-sans-latin-wght-normal)[^/]*\.woff2$/.test(file)) {
            const href = base + file;
            hints.push({ href, tag: `<link rel="preload" as="font" type="font/woff2" crossorigin href="${attribute(href)}" />` });
          }
        }
        for (const { href, tag } of hints) if (!html.includes(`href="${attribute(href)}"`)) html = html.replace('</head>', `${tag}\n</head>`);
        share.source = html;
      },
    },
  };
}
