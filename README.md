# Playoff Pulse

Static league tables and season odds: T20 cricket leagues (IPL first), Europe's top five football leagues, and the NFL, NBA, NHL and MLB. The frontend is a React/Vite app that serves checked-in JSON and social PNG assets from `frontend/ipl-analyzer-frontend/public`.

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

Each competition season has a config in `leagues/<id>.json`: teams (names, short names, aliases, colours), games per team, the points system (`points`: win, no result, tie, optional bonus point), qualification tiers (for example Top 4 and Top 2, or Top 3 and Top 1 for the WPL and The Hundred), playoff stage labels (used only when Cricsheet repeats a stage name), playoff losses that are not exits (such as the IPL's Qualifier 1), and data sources. `gender` filters mixed archives and `nrrBallsPerUnit` sets the NRR scale.

Configured seasons, each checked against its official table:

| Id | League | Source |
| --- | --- | --- |
| `ipl-2026` | Indian Premier League 2026 | CricketData in season, Cricsheet once complete |
| `ipl-2027` | Indian Premier League 2027 (tentative 10 Mar - 30 May 2027) | CricketData in season, Cricsheet once complete |
| `wpl-2026` | Women's Premier League 2026 | Cricsheet |
| `wpl-2027` | Women's Premier League 2027 (14 Jan - 7 Feb 2027) | CricketData in season, Cricsheet once complete |
| `psl-2026` | Pakistan Super League 2026 | Cricsheet, plus one abandoned match in `extraResults` |
| `psl-2027` | Pakistan Super League 2027 (tentative 19 Mar - 2 May 2027) | CricketData in season, Cricsheet once complete |
| `bbl-2025-26` | Big Bash League 2025-26 | Cricsheet |
| `bbl-2026-27` | Big Bash League 2026-27 (12 Dec 2026 - 26 Jan 2027) | CricketData in season, Cricsheet once complete |
| `mlc-2026` | Major League Cricket 2026 | Cricsheet |
| `sa20-2025-26` | SA20 2026 (4 points a win, bonus point at 1.25x the loser's run rate) | Cricsheet, plus three abandoned matches |
| `sa20-2026-27` | SA20 2027 (17 Jan - 21 Feb 2027) | CricketData in season, Cricsheet once complete |
| `ilt-2025-26` | International League T20 2025-26 | Cricsheet |
| `ilt-2026-27` | International League T20 2026-27 (22 Nov - 20 Dec 2026) | CricketData in season, Cricsheet once complete |
| `hundred-men-2026` | The Hundred 2026, men (4 points a win, NRR per 5-ball set) | Cricsheet, filtered by gender |
| `hundred-women-2026` | The Hundred 2026, women | Cricsheet, plus one abandoned match |
| `cpl-2026` | Caribbean Premier League 2026 | Cricsheet; published once Cricsheet adds the playoffs |
| `lpl-2026` | Lanka Premier League 2026 | Cricsheet |
| `bpl-2025-26` | Bangladesh Premier League 2025-26 | Cricsheet |

Build one league, or every configured league, then the site's `data/leagues.json` index is rewritten:

```bash
venv/bin/python extract_table.py --league wpl-2026
venv/bin/python extract_table.py --league all --source cricsheet
```

`--source auto` (the default) uses CricketData when a league configures it and Cricsheet otherwise. The site shows the default league (IPL) at `/` and any other at `/?league=<id>`.

Seasons roll forward on their own: once a competition's newest configured season is over, the next one is created from it in memory (same teams and rules, dates a year later and marked tentative, no fixed CricketData series id), so `--league active` keeps building new seasons without new files. CricketData finds the new series by name and season label. When a season changes teams, format or dates, add a real config for it; the first build of a rolled season reports a team mismatch as a warning.

To add a league season:

1. Copy a similar config in `leagues/` and update teams, games per team, qualification tiers, and playoff stages.
2. Cricsheet has no file for matches abandoned before a ball was bowled; list them under `extraResults`.
3. Build it and compare the table with the official one, then add the official points and NRR to `OFFICIAL_TABLES` in `tests/test_cricsheet.py`.

Live odds work for any league whose config has a CricketData source; the others show completed seasons. Bonus points are simulated at the rate seen in the previous season.

## Football

The Premier League, La Liga, Bundesliga, Serie A and Ligue 1 use rolling configs (`leagues/epl.json` and so on, `"sport": "football"`). A rolling config describes the competition, not one season: the `season` rule (`startMonth`, `endMonth`, a `label` such as `{year}-{yy}` and a `feed` such as `epl-{year}`) works out the current season, so a new season is picked up on 1 August without a new file. Payload ids carry the season, for example `epl-2026-27`.

- Fixtures and results: [FixtureDownload](https://fixturedownload.com/) JSON feeds, no key. Credit it on the site. The standings are computed from results (points, goal difference, goals scored) and were checked against the official tables of all five leagues.
- Tiers per league in `tiers`: `top` tiers count table places from the top (title, top four), `bottom` ones from the bottom (relegation). `shortLabel` is the column header on phones.
- Model (`football.py`): a time-weighted Poisson goals model (attack, defence, home advantage; 240-day half-life; promoted sides start below average) fitted on this and last season, then 20,000 simulated seasons. Each simulated season lets team strength drift, which backtesting on 18 league-seasons since 2022-23 showed is needed for calibrated early-season odds. Match predictions score 0.20-0.21 (ranked probability score) against 0.22-0.23 for base rates.
- The page shows the table with title, top-four and relegation chances, finishing-position chances per team, fixture predictions, the matches that swing a race most, recent results, and the biggest moves since the previous update.

To add a football league, copy `leagues/epl.json`, set the FixtureDownload feed name, tiers and any team colours (teams without one get a generated colour), then run `venv/bin/python extract_table.py --league <id>`.

## NFL, NBA, NHL And MLB

`leagues/nfl.json`, `nba.json`, `nhl.json` and `mlb.json` are rolling configs too, with conferences, divisions, team colours and the playoff format. `us_sports.py` builds them:

- Data, no keys: FixtureDownload for the NFL, NBA and MLB; the NHL stats API (`api.nhle.com`) for the NHL, because it records overtime and shootout results (overtime losses are worth a point). Playoff rounds, "to be announced" placeholders and the NBA Cup final are left out of the regular season; games not yet on the NBA schedule are simulated against an average opponent; games never played when a schedule ends (MLB rainouts) are dropped.
- Tables: wins, losses, ties (NFL), overtime losses and points (NHL), win percentage, games behind, differential, last ten and streak, with league, conference and division views. Conference views are in seed order with the playoff line (and the NBA play-in line).
- Seeding: NFL division winners take seeds 1-4 and three wild cards follow; the NBA seeds 1-6 directly and simulates the play-in for 7 and 8; the NHL takes three teams per division plus two wild cards; MLB division winners take seeds 1-3, the top two get byes, and three wild cards follow. Tiebreakers are simplified (win percentage, then division or conference record; points, games played and regulation wins in the NHL).
- Model: ratings from capped score margins with home advantage and a time decay, fitted on this and last season. The regular season is simulated 20,000 times with season-long strength drift, then the playoff bracket (single games in the NFL, best-of-3/5/7 series elsewhere) for title odds. Settings were chosen by backtesting the 2023-24 to 2025-26 seasons: week-ahead game predictions for the half-life, ridge and spread, and playoff odds at 25%, 50% and 75% of each season for the drift.
- Tiers: playoffs, division title, a top seed (NFL and NBA No. 1 seed, NBA top 6, MLB bye, NHL Presidents' Trophy) and the title.
- Playoffs: once a regular season ends, results come from the MLB Stats API, the NHL stats API, ESPN's public scoreboard (NBA; the NBA's own feed blocks automated requests) or the NFL feed's playoff rounds. Settled places show as ticks, finished series fix their winners, series under way start from their real score, and the rest of the bracket is simulated for title odds. Real tiebreakers only reorder teams level on record, so the seeding is matched to the real bracket by trying the orders of tied teams; if none matches, the title column is left out with a warning. This reproduces the 2025-26 playoffs of all four leagues exactly.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd frontend/ipl-analyzer-frontend
npm ci
```

## Daily Data And Social Workflow

The data workflow (`.github/workflows/update-ipl.yml`, 19:30 and 07:00 UTC) runs:

```bash
export CRICDATA_API_KEY="..."
venv/bin/python extract_table.py --league active
```

`--league active` builds every cricket league inside its `seasonStart`-`seasonEnd` window from CricketData and every football league in season. For 21 days after a cricket season ends it retries the Cricsheet rebuild until the final is published. A payload that differs from the published one only in its timestamp is not rewritten, so the workflow commits, builds and deploys only when something changed. It can also be run manually with a league id, `all`, or `active`.

Built to run unattended:

- One league failing (a source down, a changed format, a missing key) is logged as a warning annotation and the other leagues still update. The run fails only if every league fails.
- Downloads are retried, and the workflow caches `.cache/` between runs so a source that is down for a night falls back to its last good copy.
- The data commit is rebased and pushed again if `main` moved during the run.

API keys: only `CRICDATA_API_KEY` (free CricketData plan, 100 calls a day, personal and non-commercial use) for live cricket. Without it, cricket leagues are skipped with a warning. Football, NFL, NBA, NHL and MLB need no key. Keyless sources and their terms: FixtureDownload (credit it), the NHL stats API, the MLB Stats API (individual, non-commercial use) and ESPN's public scoreboard (unofficial; only the NBA playoffs use it, and the page falls back to no title odds if it changes).

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
