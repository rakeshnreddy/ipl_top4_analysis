# IPL Playoff Pulse Frontend

React/Vite frontend for the static IPL Playoff Pulse site.

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

## Static Data

The app reads checked-in public assets:

- `public/data/ipl-2026.json`
- `public/social/instagram-carousel/manifest.json`
- `public/social/instagram-carousel/latest-overview.png`
- `public/social/instagram-carousel/<YYYY-MM-DD>/slide-*.png`

The URL base is controlled by Vite `base`. Cloudflare uses `/`; GitHub Pages uses `/ipl_top4_analysis/`.
