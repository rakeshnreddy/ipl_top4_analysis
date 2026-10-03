# IPL Playoff Pulse

Static IPL 2026 playoff probability site. The frontend is a React/Vite app that serves checked-in JSON and social PNG assets from `frontend/ipl-analyzer-frontend/public`.

The deployed app does not need a live backend. Data generation happens ahead of the frontend build, then the static output is deployed.

## What The Site Shows

During the league stage:

- Qualification probabilities in each league's own format (Top 4 and Top 2 for the IPL, Top 3 and Top 1 for the WPL).
- Current standings, remaining fixtures (in the reader's time zone), and selected-team paths.
- The biggest riser and faller since the previous update.
- Before the first result: the opening match and the number of playoff places.

Once the league stage is complete (no fixtures left and every team has played its full schedule):

- Final standings ranked by points, then NRR.
- Playoff results, champion and a season recap.
- Each team's season outcome and playoff journey.

Hash deep links: `#team=RCB`, `#standings`, `#top4`, `#playoffs`, and `#deep-dive`.

Social posting tools live on a separate page, `/share.html` (Share kit): the latest Reels slides, copy-ready captions, and a race PNG export. Old `#reels` links redirect there. The page is `noindex`.

## Data Rules

- Probabilities use exact all-combinations over remaining league fixtures. Playoff fixtures in the feed are ignored.
- In-season data comes from CricketData (`--source cricketdata`, the default). NRR is display-only when CricketData provides it and is not used in probability math.
- Completed seasons are rebuilt from Cricsheet (`--source cricsheet`): results, playoffs, and NRR computed from ball-by-ball data.
- Cricsheet data is licensed ODC-By 1.0. Keep the source and licence credit visible on the site.
- Do not add Cricbuzz or scraping fallback paths to production automation.

Canonical generated files:

- `frontend/ipl-analyzer-frontend/public/data/ipl-2026.json`
- `frontend/ipl-analyzer-frontend/public/social/instagram-carousel/manifest.json`
- `frontend/ipl-analyzer-frontend/public/social/instagram-carousel/latest-overview.png`
- `frontend/ipl-analyzer-frontend/public/social/instagram-carousel/<YYYY-MM-DD>/slide-*.png` (only the newest dated folder is kept)

## Leagues

Each competition season has a config in `leagues/<id>.json`: teams (names, short names, aliases, colours), games per team, qualification tiers (for example Top 4 and Top 2, or Top 3 and Top 1 for the WPL), playoff stage labels, playoff losses that are not exits (such as the IPL's Qualifier 1), and data sources.

Configured seasons, each checked against its official table:

| Id | League | Source |
| --- | --- | --- |
| `ipl-2026` | Indian Premier League 2026 | CricketData in season, Cricsheet once complete |
| `wpl-2026` | Women's Premier League 2026 | Cricsheet |
| `wpl-2027` | Women's Premier League 2027 (14 Jan - 7 Feb 2027) | CricketData in season, Cricsheet once complete |
| `psl-2026` | Pakistan Super League 2026 | Cricsheet, plus one abandoned match in `extraResults` |
| `bbl-2025-26` | Big Bash League 2025-26 | Cricsheet |
| `bbl-2026-27` | Big Bash League 2026-27 (12 Dec 2026 - 26 Jan 2027) | CricketData in season, Cricsheet once complete |
| `mlc-2026` | Major League Cricket 2026 | Cricsheet |

Build one league, or every configured league, then the site's `data/leagues.json` index is rewritten:

```bash
venv/bin/python extract_table.py --league wpl-2026
venv/bin/python extract_table.py --league all --source cricsheet
```

`--source auto` (the default) uses CricketData when a league configures it and Cricsheet otherwise. The site shows the default league (IPL) at `/` and any other at `/?league=<id>`.

To add a league season:

1. Copy a similar config in `leagues/` and update teams, games per team, qualification tiers, and playoff stages.
2. Cricsheet has no file for matches abandoned before a ball was bowled; list them under `extraResults`.
3. Build it and compare the table with the official one, then add the official points and NRR to `OFFICIAL_TABLES` in `tests/test_cricsheet.py`.

Live odds work for any league whose config has a CricketData source; the others show completed seasons. Leagues with bonus points (such as SA20) are not supported yet.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd frontend/ipl-analyzer-frontend
npm ci
```

## Daily Data And Social Workflow

The nightly workflow (`.github/workflows/update-ipl.yml`, 01:00 IST) runs:

```bash
export CRICDATA_API_KEY="..."
venv/bin/python extract_table.py --league active
```

`--league active` builds every league inside its `seasonStart`-`seasonEnd` window from CricketData. For 21 days after a season ends it retries the Cricsheet rebuild until the final is published. Off-season nights build nothing and call no API. The workflow commits only when data changed and builds and deploys only after a data commit. It can also be run manually with a league id, `all`, or `active`.

CricketData series ids: set `sources.cricketdata.seriesId` in the league config once the series is listed (most reliable). Otherwise the generator searches CricketData's series list for the configured `seriesNames` plus the season label. The `CRICDATA_SERIES_ID` secret applies only to the default league.

GitHub disables scheduled workflows after 60 days without repository activity. Check that the workflow is enabled under Actions before a season starts.

Rebuild a completed season from Cricsheet (no API key needed):

```bash
venv/bin/python extract_table.py --source cricsheet
```

This downloads `ipl_json.zip` from Cricsheet into `.cache/cricsheet/` and reuses it for six hours. Pass `--cricsheet-archive path/to/ipl_json.zip` to use a local copy. When the archive is cached, the test suite also checks the computed 2026 NRR against the official table.

Generate the latest carousel images and manifest:

```bash
venv/bin/python scripts/create_instagram_carousel.py
```

Run backend/data tests:

```bash
venv/bin/python -m unittest discover -s tests
```

## Frontend Commands

Run from `frontend/ipl-analyzer-frontend`.

```bash
npm run dev
npm test -- --run
npm run build
npm run build:cloudflare
npm run build:github
npm run preview
npm run preview:cloudflare
```

Command meanings:

- `npm run dev`: start the Vite development server at root base `/`.
- `npm test -- --run`: run Vitest once.
- `npm run build`: default production build for Cloudflare Pages root base `/`.
- `npm run build:cloudflare`: explicit Cloudflare Pages root build.
- `npm run build:github`: GitHub Pages build for `/ipl_top4_analysis/`.
- `npm run preview`: preview the current `dist` build.
- `npm run preview:cloudflare`: preview the current Cloudflare/root `dist` build on `127.0.0.1`.

## Deployment Targets

### Cloudflare Pages

This is the preferred root deployment target for the current site.

Project config is in `wrangler.jsonc`:

```json
{
  "name": "ipl-playoff-pulse",
  "pages_build_output_dir": "frontend/ipl-analyzer-frontend/dist",
  "compatibility_date": "2026-05-08"
}
```

Cloudflare Pages build settings, if configuring a Git-connected project:

- Build command: `cd frontend/ipl-analyzer-frontend && npm ci && npm run build:cloudflare`
- Build output directory: `frontend/ipl-analyzer-frontend/dist`
- Production branch: `main`

Manual deploy after tests pass:

```bash
cd frontend/ipl-analyzer-frontend
npm run build:cloudflare
cd ../..
npx wrangler pages deploy frontend/ipl-analyzer-frontend/dist --project-name ipl-playoff-pulse --branch main
```

No custom domain or DNS records are required for the current deployment. The result should be a Cloudflare-provided `*.pages.dev` URL.

### GitHub Pages

GitHub Pages remains subpath-compatible through `.github/workflows/pages.yml` and `.github/workflows/update-ipl.yml`.

Those workflows build with:

```bash
cd frontend/ipl-analyzer-frontend
npm run build:github
```

## Static Assets And Routing

Cloudflare Pages should serve these files directly from the static build:

- `/`
- `/share.html`
- `/data/ipl-2026.json`
- `/social/instagram-carousel/manifest.json`
- `/social/instagram-carousel/latest-overview.png`
- `/social/instagram-carousel/<latest-date>/slide-*.png`
- `/robots.txt`

The app uses hash links, so no Cloudflare redirects are needed for `#team=RCB`, `#standings`, `#top4`, `#playoffs`, or `#deep-dive`.

`public/_headers` keeps hashed Vite assets cacheable while giving canonical JSON and latest social assets short freshness windows.

## Future Domain And Ads

When a custom domain is ready:

1. Attach it in Cloudflare Pages.
2. Update any Cloudflare Pages project settings that should reference the new production URL.
3. Verify canonical URL, `og:url`, `og:image`, `twitter:image`, and JSON-LD on the custom domain.
4. Re-test `/data/ipl-2026.json`, the carousel manifest, latest overview image, and dated carousel PNGs.

For ads later:

- Keep ad scripts out until a provider is selected.
- Reserve layout space before loading ad units to avoid Cumulative Layout Shift.
- Load ads after primary content and data JSON.
- Keep image dimensions explicit and monitor Core Web Vitals after adding any ad network script.
