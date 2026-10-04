# Playoff Pulse

Static league tables and season odds: T20 cricket leagues (IPL first), eight European football leagues, the Champions League, and the NFL, NBA, NHL and MLB. The frontend is a React/Vite app that serves checked-in JSON and social PNG assets from `frontend/ipl-analyzer-frontend/public`.

The deployed app does not need a live backend. Data generation happens ahead of the frontend build, then the static output is deployed.

## What The Site Shows

The home page is an all-sports hub while no IPL season is on: a card per live league with its headline odds (title favourite, relegation risk, playoff bubble), then last season's final tables. During the IPL season the home page is the IPL; the hub stays at `/?view=hub`. Every league page links back to it.

Cricket pages, during the league stage:

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
| `wbbl-2025-26` | Women's Big Bash League 2025-26 (Top 4; first goes straight to the final, third plays fourth in the Knockout) | Cricsheet, plus one abandoned match |
| `wbbl-2026-27` | Women's Big Bash League 2026-27 (29 Oct - 5 Dec 2026) | CricketData in season, Cricsheet once complete |

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

The Premier League, La Liga, Bundesliga, Serie A, Ligue 1, EFL Championship, Eredivisie and Primeira Liga use rolling configs (`leagues/epl.json` and so on, `"sport": "football"`). A rolling config describes the competition, not one season: the `season` rule (`startMonth`, `endMonth`, a `label` such as `{year}-{yy}` and a `feed` such as `epl-{year}`) works out the current season, so a new season is picked up on 1 August without a new file. Payload ids carry the season, for example `epl-2026-27`.

- Fixtures and results: [FixtureDownload](https://fixturedownload.com/) JSON feeds, no key. Credit it on the site. The standings are computed from results and were checked against the official tables of all eight leagues.
- Tiebreakers: goal difference, then goals scored; `"tiebreak": "head-to-head"` (Portugal) ranks teams level on points by their games against each other first, and `"head-to-head-complete"` (Spain, Italy) does so once they have met home and away.
- Points deductions: with `sources.espn` set, each team is matched to ESPN's table by its record (played, wins, draws, losses, goals), with no name matching, and any points difference is applied as a deduction and listed in the notes. If ESPN is unavailable, nothing changes.
- Tiers per league in `tiers`: `top` tiers count table places from the top (title, top four), `bottom` ones from the bottom (relegation). `shortLabel` is the column header on phones.
- Model (`football.py`): a time-weighted Poisson goals model (attack, defence, home advantage; 240-day half-life; promoted sides start below average) fitted on this and last season, then 20,000 simulated seasons. Each simulated season lets team strength drift, which backtesting on 18 league-seasons since 2022-23 showed is needed for calibrated early-season odds. Match predictions score 0.20-0.21 (ranked probability score) against 0.22-0.23 for base rates.
- The page shows the table with title, top-four and relegation chances, finishing-position chances per team, fixture predictions, the matches that swing a race most, recent results, and the biggest moves since the previous update.

To add a football league, copy `leagues/epl.json`, set the FixtureDownload feed name, tiers and any team colours (teams without one get a generated colour), then run `venv/bin/python extract_table.py --league <id>`.

## European Cups

The UEFA Champions League (`leagues/champions-league.json`) is a rolling football config with `"engine": "european_cups"`, built by `european_cups.py`. The season runs September to June, and the payload id carries the season, for example `champions-league-2026-27`.

- **Data** comes from the public JSON services behind uefa.com (`uefa.py`). No key is needed, but they are unofficial for third parties, like ESPN's, so every download is cached and a failed refresh falls back to the last good copy. Match data covers every qualifying and main-draw match, with 90-minute, extra-time and shoot-out scores and the winner of each tie. The official league-phase table is also used.
- **Table:** the 36-club league phase is ranked by UEFA's criteria: points, goal difference, goals, away goals, wins, away wins, then the opponents' combined points, goal difference and goals. UEFA's published order is used when it agrees with the results on every club's record. The 2025-26 tables of all three competitions are reproduced exactly (`tests/test_european_cups.py`).
- **Model:** a Poisson goals model (attack, defence, home advantage; a 730-day half-life) fitted on every UEFA club match from this season and the three before, qualifiers included. Domestic league games from FixtureDownload are added at half weight. They come from England, Spain, Germany, Italy, France, the Netherlands, Portugal, Scotland and Turkey, and are linked to UEFA clubs by name only when the match is unambiguous.
- **Backtest:** week-ahead predictions of the 1,062 main-draw matches of 2024-25 and 2025-26 in the three competitions score 0.2065 (ranked probability score). That compares with 0.2082 without domestic games and 0.2323 for home/draw/away base rates. Season-long strength drift (0.1) was chosen by scoring top-8, top-24, round-reached and title odds at five checkpoints of those six competitions.
- **Simulation:** the rest of the league phase and the knockouts are simulated 20,000 times:
  - The knockout play-offs pair places 9/10 v 23/24, 11/12 v 21/22, 13/14 v 19/20 and 15/16 v 17/18.
  - The top eight meet the play-off winners of the matching pair.
  - Each top-eight pair is split between the two halves of the bracket.
  - Two-legged ties go to extra time and then penalties (a coin flip).
  - Real draws and results replace the simulated ones as they happen.
- **Page:** the table with Top 8, Top 24, Quarter-final and Title odds, fixture predictions, the matches that matter, and, from the knockout play-offs on, a bracket with aggregate scores.

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

`--league active` builds every cricket league inside its `seasonStart`-`seasonEnd` window from CricketData and every football league in season. For 45 days after a cricket season ends it retries the Cricsheet rebuild until the final is published; if nothing has been published for that season yet, the league table and playoff results so far are published in the meantime. A payload that differs from the published one only in its timestamp is not rewritten, so the workflow commits, builds and deploys only when something changed. It can also be run manually with a league id, `all`, or `active`.

Built to run unattended:

- One league failing (a source down, a changed format, a missing key) is logged as a warning annotation and the other leagues still update. The run fails only if every league fails.
- Downloads are retried, and the workflow caches `.cache/` between runs so a source that is down for a night falls back to its last good copy.
- The data commit is rebased and pushed again if `main` moved during the run.

API keys: only `CRICDATA_API_KEY` (free CricketData plan, 100 calls a day, personal and non-commercial use) for live cricket. Without it, cricket leagues are skipped with a warning. Football, NFL, NBA, NHL and MLB need no key. Keyless sources and their terms: FixtureDownload (credit it), the NHL stats API, the MLB Stats API (individual, non-commercial use), ESPN's public scoreboard (unofficial; only the NBA playoffs use it, and the page falls back to no title odds if it changes) and UEFA.com's match and standings services (unofficial; the European cups, cached, credited on the page).

CricketData series ids: set `sources.cricketdata.seriesId` in the league config once the series is listed (most reliable). Otherwise the generator searches CricketData's series list for the configured `seriesNames` plus the season label. A men's league skips series named "Women's ..." (so the BBL never picks up the WBBL); a league is a women's one when its config sets `"gender": "female"` or names a women's series. The `CRICDATA_SERIES_ID` secret applies only to the default league.

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

Automatic deploys: both workflows that deploy GitHub Pages (code merges and data updates) also build the site for the root path and deploy it to the `ipl-playoff-pulse` project, once two repository secrets exist:

- `CLOUDFLARE_API_TOKEN`: a Cloudflare API token with the **Account > Cloudflare Pages > Edit** permission.
- `CLOUDFLARE_ACCOUNT_ID`: the Cloudflare account id (shown by `npx wrangler whoami`).

Without them the Cloudflare steps are skipped; if Cloudflare fails, the step shows a warning and the run still succeeds.

Manual deploy after tests pass (wrangler 4 needs Node 22; `npx wrangler@3` works on Node 20):

```bash
cd frontend/ipl-analyzer-frontend
SITE_URL=https://ipl-playoff-pulse.pages.dev/ npm run build:cloudflare
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
- `/sitemap.xml`: the home page and every published league page, written at build time when `SITE_URL` is set (the GitHub Pages workflows take it from the Pages configuration; set it for a Cloudflare or custom-domain build too)

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
