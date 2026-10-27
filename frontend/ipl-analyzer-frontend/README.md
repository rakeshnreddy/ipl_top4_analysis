# IPL Playoff Pulse Frontend

React/Vite frontend for Playoff Pulse season forecasts and the separate free Live Cricket section. See the [project README](../../README.md), [live implementation notes](../../docs/live-cricket-implementation.md) and [revenue readiness](../../docs/revenue-readiness.md) for current scope and verification.

## Commands

```bash
npm run dev
npm test -- --run
npm run build
npm run build:cloudflare
npm run build:github
npm run preview
npm run preview:cloudflare
```

- `npm run dev`: Vite dev server with root base `/`.
- `npm test -- --run`: Vitest once.
- `npm run build`: default Cloudflare/root production build.
- `npm run build:cloudflare`: explicit Cloudflare Pages build with base `/`.
- `npm run build:github`: GitHub Pages build with base `/ipl_top4_analysis/`.
- `npm run preview`: preview the current `dist` build.
- `npm run preview:cloudflare`: preview a root-based build locally.

To reproduce the footer loading regression from this directory, serve separate root and GitHub-base builds, then run `node build/verify-entry-layout.mjs http://127.0.0.1:5395/ http://127.0.0.1:5393/ipl_top4_analysis/` with those preview URLs adjusted to your servers. It uses installed Playwright/Chromium; set `PLAYWRIGHT_MODULE` to an existing Playwright module path if needed. It holds the league response, blocks SportScore requests and checks the loading footer plus final page geometry at 375px and 1280px. [Dated results and limitations](../../docs/live-cricket-implementation.md#release-candidate-recheck-on-27-october-2026).

## Static Data

The app reads checked-in public assets:

- `public/data/ipl-2026.json`
- `public/social/instagram-carousel/manifest.json`
- `public/social/instagram-carousel/latest-overview.png`
- `public/social/instagram-carousel/<YYYY-MM-DD>/slide-*.png`

The URL base is controlled by Vite `base`. Cloudflare uses `/`; GitHub Pages uses `/ipl_top4_analysis/`. Both outputs use the primary Cloudflare origin for canonical page URLs. Live Cricket at `/cricket/` reads SportScore directly by default; leave `VITE_LIVE_CRICKET_API_URL` unset unless reviewing an optional configured service.
