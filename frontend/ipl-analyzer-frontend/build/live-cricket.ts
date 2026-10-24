import type { Plugin } from 'vite';

/** The fixed lobby entry needs no SPA rewrite, even for unknown match query IDs. */
export function liveCricketEntryPlugin(siteUrl?: string): Plugin {
  let base = '/';
  return {
    name: 'live-cricket-entry', apply: 'build', enforce: 'post',
    configResolved(config) { base = config.base; },
    generateBundle: {
      order: 'post',
      handler(_options, bundle) {
        const entry = bundle['cricket/index.html'];
        if (!entry || entry.type !== 'asset') throw new Error('Missing static cricket entry.');
        const site = siteUrl ?? (base === '/' ? 'https://ipl-playoff-pulse.pages.dev/' : `https://rakeshnreddy.github.io${base}`);
        const canonical = new URL('cricket/', site.endsWith('/') ? site : `${site}/`).href.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
        entry.source = String(entry.source)
          .replace(/<link\b(?=[^>]*\brel="canonical")[^>]*>/i, `<link rel="canonical" href="${canonical}" />`)
          .replace(/<meta property="og:url"[^>]*>/i, `<meta property="og:url" content="${canonical}" />`);
        // This is a known route: discover its lazy page and heading fonts before
        // React runs, while keeping other page families out of the critical path.
        const hints: string[] = [];
        for (const [file, output] of Object.entries(bundle)) {
          const href = `${base}${file}`.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
          if (output.type === 'chunk' && /\/live\/LiveCricketPage\.tsx$/.test(output.facadeModuleId ?? '')) {
            hints.push(`<link rel="modulepreload" crossorigin href="${href}" />`);
          } else if (/^assets\/LiveCricketPage-[^/]+\.css$/.test(file)) {
            hints.push(`<link rel="stylesheet" crossorigin href="${href}" />`);
          } else if (/(?:barlow-semi-condensed-latin-700-normal|ibm-plex-sans-latin-wght-normal)[^/]*\.woff2$/.test(file)) {
            hints.push(`<link rel="preload" as="font" type="font/woff2" crossorigin href="${href}" />`);
          }
        }
        entry.source = String(entry.source).replace('</head>', `${hints.join('\n')}\n</head>`);
      },
    },
  };
}
