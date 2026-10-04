# Playoff Pulse

Static league tables and season odds: T20 cricket leagues (IPL first), European football leagues from the Premier League to the Süper Lig, the Champions League, Europa League and Conference League, MLS, the NFL, NBA, WNBA, NHL and MLB, and Australia's NBL and WNBL. The frontend is a React/Vite app that serves checked-in JSON and social PNG assets from `frontend/ipl-analyzer-frontend/public`.

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

Each competition season has a config in `leagues/<id>.json`: teams (names, short names, aliases, colours), games per team, the points system (`points`: win, no result, tie, optional bonus points: `bonusRunRateRatio` for the SA20's winner bonus, or `bonusRuns` and `bonusChaseRunRateRatio` for the women's Super Smash, where either side earns one for 150 runs, scaled to its overs in a shortened match, or for chasing at more than 1.25 times the first innings' rate), qualification tiers (for example Top 4 and Top 2, or Top 3 and Top 1 for the WPL and The Hundred), playoff stage labels (used only when Cricsheet repeats a stage name), playoff losses that are not exits (such as the IPL's Qualifier 1), and data sources. `gender` filters mixed archives and `nrrBallsPerUnit` sets the NRR scale. A tier can have a `shortLabel` for phones.

Leagues played in groups (the T20 Blast) list them under `groups` (name and team keys). Teams are ranked within their group, then seeded across groups: group winners first, then the second-placed teams, and so on, each ordered by points and NRR. A tier of size N is the top N seeds, so "the top two in each of three groups plus the two best thirds" is size 8, and the Blast's quarter-final draw (seed 1 v 8, 2 v 7, ...) follows from the seeds. The page shows one table per group. Group stages are always simulated (Monte Carlo), since the exact solver ranks one table. `deductions` takes points off a team (a sanction), and `targets` supplies the revised target and overs of a shortened match when its Cricsheet file has none, which NRR needs (the 2026 Blast files have no targets). Both are season-specific and are not rolled forward.

Configured seasons, each checked against its official table:

| Id | League | Source |
| --- | --- | --- |
| `ipl-2026` | Indian Premier League 2026 | CricketData in season, Cricsheet once complete |
| `ipl-2027` | Indian Premier League 2027 (tentative 10 Mar - 30 May 2027: the BCCI is weighing 10 Mar - 15 May against the earlier 14 Mar - 30 May plan; 74 matches) | CricketData in season, Cricsheet once complete |
| `wpl-2026` | Women's Premier League 2026 | Cricsheet |
| `wpl-2027` | Women's Premier League 2027 (14 Jan - 7 Feb 2027, announced by the BCCI) | CricketData in season, Cricsheet once complete |
| `psl-2026` | Pakistan Super League 2026 | Cricsheet, plus one abandoned match in `extraResults` |
| `psl-2027` | Pakistan Super League 2027 (tentative 19 Mar - 2 May 2027, reported but not yet announced by the PCB) | CricketData in season, Cricsheet once complete |
| `bbl-2025-26` | Big Bash League 2025-26 | Cricsheet |
| `bbl-2026-27` | Big Bash League 2026-27 (12 Dec 2026 - 26 Jan 2027) | CricketData in season, Cricsheet once complete |
| `mlc-2026` | Major League Cricket 2026 | Cricsheet |
| `sa20-2025-26` | SA20 2026 (4 points a win, bonus point at 1.25x the loser's run rate) | Cricsheet, plus three abandoned matches |
| `sa20-2026-27` | SA20 2027 (17 Jan - 21 Feb 2027) | CricketData in season, Cricsheet once complete |
| `ilt-2025-26` | International League T20 2025-26 | Cricsheet |
| `ilt-2026-27` | International League T20 season 5 (22 Nov - 20 Dec 2026; labelled 2026) | CricketData in season, Cricsheet once complete |
| `hundred-men-2026` | The Hundred 2026, men (4 points a win, NRR per 5-ball set) | Cricsheet, filtered by gender |
| `hundred-women-2026` | The Hundred 2026, women | Cricsheet, plus one abandoned match |
| `cpl-2026` | Caribbean Premier League 2026 | Cricsheet; published once Cricsheet adds the playoffs |
| `wcpl-2026` | Women's Caribbean Premier League 2026 (4 teams, 3 games each; Top 3, first goes straight to the final) | Cricsheet; 2027 is rolled forward from it |
| `lpl-2026` | Lanka Premier League 2026 | Cricsheet |
| `bpl-2025-26` | Bangladesh Premier League 2025-26 | Cricsheet |
| `wbbl-2025-26` | Women's Big Bash League 2025-26 (Top 4; first goes straight to the final, third plays fourth in the Knockout) | Cricsheet, plus one abandoned match |
| `wbbl-2026-27` | Women's Big Bash League 2026-27 (29 Oct - 5 Dec 2026; labelled 2026) | CricketData in season (fixed series id), Cricsheet once complete |
| `super-smash-men-2025-26` | Super Smash 2025-26, men (4 points a win, 2 a tie or no result; Top 3, first goes straight to the final) | Cricsheet, filtered by gender, plus three abandoned matches |
| `super-smash-women-2025-26` | Super Smash 2025-26, women (bonus point for 150 runs or a fast chase, win or lose) | Cricsheet, filtered by gender, plus one abandoned match |
| `super-smash-men-2026-27` | Super Smash 2026-27, men (tentative 26 Dec 2026 - 31 Jan 2027: NZC said the schedule would come in late September, but had not published it by 3 Oct 2026) | CricketData in season, Cricsheet once complete |
| `super-smash-women-2026-27` | Super Smash 2026-27, women (same tentative dates) | CricketData in season, Cricsheet once complete |
| `t20-blast-2026` | T20 Blast 2026, men: three groups of six; the top two in each and the two best thirds reach the quarter-finals (4 points a win) | Cricsheet, plus the targets of two shortened matches and Sussex's 2-point deduction; 2027 is rolled forward from it |

Build one league, or every configured league, then the site's `data/leagues.json` index is rewritten:

```bash
venv/bin/python extract_table.py --league wpl-2026
venv/bin/python extract_table.py --league all --source cricsheet
```

`--source auto` (the default) uses CricketData when a league configures it and Cricsheet otherwise. The site shows the default league (IPL) at `/` and any other at `/?league=<id>`.

Seasons roll forward on their own: once a competition's newest configured season is over, the next one is created from it in memory (same teams and rules, dates a year later and marked tentative, no fixed CricketData series id), so `--league active` keeps building new seasons without new files. CricketData finds the new series by name and season label. When a season changes teams, format or dates, add a real config for it; the first build of a rolled season reports a team mismatch as a warning.

CricketData names a season inside one calendar year by that year ("SA20, 2025", "Womens Big Bash League 2026") and one that spans New Year by both ("Big Bash League 2025-26", "SA20, 2025-26"). Discovery needs the season label in the series name, so the WBBL and ILT20, played between October and December, are labelled by their year (a year label also matches a "2026-27" name). Once CricketData lists a series, its id can be fixed in `sources.cricketdata.seriesId`, as for WBBL 2026. Winners are read from CricketData's result text by team name or alias, ignoring punctuation, so aliases cover the names CricketData uses, such as the Super Smash's associations ("Northern Knights", "Central Districts"), and "Durbans Super Giants won" counts for Durban's Super Giants.

To add a league season:

1. Copy a similar config in `leagues/` and update teams, games per team, qualification tiers, and playoff stages.
2. Cricsheet has no file for matches abandoned before a ball was bowled; list them under `extraResults`.
3. Build it and compare the table with the official one, then add the official points and NRR to `OFFICIAL_TABLES` in `tests/test_cricsheet.py`.

Live odds work for any league whose config has a CricketData source; the others show completed seasons. Bonus points are simulated at the rate seen in the previous season (`bonusSimulationRate` for winners, `bonusLoserSimulationRate` for losers). A tie that stands, as in the Super Smash, is read from CricketData's match status.

## Football

The Premier League, La Liga, Bundesliga, Serie A, Ligue 1, EFL Championship, Ligue 2, Eredivisie, Primeira Liga, Süper Lig, Women's Super League and Scottish Premiership use rolling configs (`leagues/epl.json` and so on, `"sport": "football"`). A rolling config describes the competition, not one season: the `season` rule (`startMonth`, `endMonth`, a `label` such as `{year}-{yy}` and a `feed` such as `epl-{year}`) works out the current season, so a new season is picked up on 1 August (1 July in Scotland, which starts in late July) without a new file. Payload ids carry the season, for example `epl-2026-27`.

- Fixtures and results: [FixtureDownload](https://fixturedownload.com/) JSON feeds, no key. Credit it on the site. The standings are computed from results and were checked against the official tables of every league.
- Tiebreakers: goal difference, then goals scored; `"tiebreak": "head-to-head"` (Portugal) ranks teams level on points by their games against each other first, and `"head-to-head-complete"` (Spain, Italy) does so once they have met home and away. A config can instead list its league's own steps in order (`football.TIEBREAK_STEPS`): `goal-difference`, `goals`, `wins`, `away-wins`, `head-to-head` (points, then goal difference in the games between the teams still level), `head-to-head-complete` (the same once they have all met home and away) and `head-to-head-goals-complete` (also goals in those games). `"goals-then-head-to-head"` (Scotland, [SPFL Rule C36](https://spfl.co.uk/admin/filemanager/images/shares/pdfs/June%202026%20Rules%20and%20Regs.pdf)) is shorthand for `["goal-difference", "goals", "head-to-head"]`: the games between the teams still level come last. A head-to-head step is applied once: teams it leaves level go on to the next step. Simulated seasons break ties by goal difference, then goals scored.
- Points deductions: with `sources.espn` set, each team is matched to ESPN's table by its record (played, wins, draws, losses, goals), with no name matching, and any points difference is applied as a deduction and listed in the notes. If ESPN is unavailable, nothing changes.
- Tiers per league in `tiers`: `top` tiers count table places from the top (title, top four), `bottom` ones from the bottom (relegation). `skip` leaves out places at the tier's edge, so Scotland's play-off tier (`bottom`, size 1, skip 1) is 11th place only; the table colours it as a middle zone. `shortLabel` is the column header on phones.
- Model (`football.py`): a time-weighted Poisson goals model (attack, defence, home advantage; 240-day half-life; promoted sides start below average) fitted on this and last season, then 20,000 simulated seasons. Each simulated season lets team strength drift, which backtesting on 18 league-seasons since 2022-23 showed is needed for calibrated early-season odds. Match predictions score 0.20-0.21 (ranked probability score) against 0.22-0.23 for base rates. A feed that starts with the current season (`season.firstYear`) has no previous one: the ratings use this season only and the notes say so.
- Leagues that split (`"split": {"after": 33, "size": 6}`, `football_split.py`): after 33 games the Scottish Premiership splits into a top six and a bottom six, each team plays the other five in its half once more, and no team can leave its half ([SPFL Rules C15-C17](https://spfl.co.uk/admin/filemanager/images/shares/pdfs/June%202026%20Rules%20and%20Regs.pdf)). Each pair's first three meetings are pre-split. The post-split fixtures are published only after round 33, so until they are in the feed every simulated season splits its own table and plays those games itself, the team that had fewer home games against an opponent hosting it (102 of the 120 real post-split home sides of 2021-22, 2022-23, 2024-25 and 2025-26; the SPFL swapped the rest to give every club two or three home games). Each half is ranked separately in every simulation; once the split has happened, the table keeps the halves apart (Hearts finished seventh in 2024-25 with more points than sixth), the Top 6 column becomes ticks, and real post-split fixtures replace the simulated ones as they appear. A dashed "Split" line marks the cut on the table.
- Scottish Premiership (`leagues/scottish-premiership.json`): title, Top 3, Top 6, the play-off place (11th, against the Championship play-off winner) and relegation (12th) ([SPFL Rules C18-C19, C24-C25](https://spfl.co.uk/admin/filemanager/images/shares/pdfs/June%202026%20Rules%20and%20Regs.pdf)). European places from 2026-27 follow [UEFA's 2026 association ranking](https://www.uefa.com/nationalassociations/uefarankings/country/#/yr/2026), where Scotland is 18th, and the current access list ([UEFA Champions League regulations 2026/27](https://documents.uefa.com/r/Regulations-of-the-UEFA-Champions-League-2026/27-Online)): the champions enter the Champions League second qualifying round, second and third the Conference League second qualifying round, and the Scottish Cup winners the Europa League, so fourth qualifies too when the cup winners finish in the top three. Check this note each summer; the allocation moves with the ranking. FixtureDownload has no Scottish season before 2026-27 (`season.firstYear`), so 2026-27 ratings use this season only, every club starting level with the first-season ridge of 4 (promoted St Johnstone get no promoted-side prior), and there is no FixtureDownload season to backtest. On ESPN's results for 2021-22, 2022-23, 2024-25 and 2025-26 (912 games), week-ahead predictions score 0.2039 (ranked probability score) fitted on the season so far and 0.1971 with last season too, against 0.2310 for base rates; title, top-three, top-six, play-off and relegation odds at six points of those seasons (rounds 7 to 33, through the split) score a Brier score of 0.055, against 0.092 for the table at the time and 0.133 for base rates. Ridge, half-life and drift were left as they are (no setting was better by more than 0.001; ridge 4, the first-season setting, scored best fitted on the season so far, 0.2030).
- The page shows the table with title, top-four and relegation chances, finishing-position chances per team, fixture predictions, the matches that swing a race most, recent results, and the biggest moves since the previous update.
- Süper Lig (`leagues/super-lig.json`, ESPN `tur.1` for deductions): 18 clubs, 34 rounds, and 16th to 18th go down ([TFF 2026-27 statute](https://www.tff.org/Resources/TFF/Documents/STATULER/2026-2027/2026-2027-sezonu-super-lig-musabakalari-statusu.pdf), Article 3). Teams level on points are ranked by the games between them, then overall goal difference and goals ([TFF Futbol Müsabaka Talimatı](https://www.tff.org/Resources/TFF/Documents/TALIMATLAR/Futbol-Musabaka-Talimati.pdf), Article 9: head-to-head points and goal difference, plus head-to-head goals when three or more are level). The [TFF table](https://www.tff.org/default.aspx?pageID=198) applies head-to-head only once the teams have met home and away: after six rounds of 2026-27 it ranks every tie by goal difference, and the [2025-26 final table](https://www.tff.org/default.aspx?pageID=1768) puts Kocaelispor above Alanyaspor and Gaziantep, and Kayserispor above Fatih Karagümrük, by head-to-head. Both are reproduced in `tests/test_super_lig.py`. Backtest (2023-24 to 2025-26, 1,024 matches): 0.197 against 0.226 for base rates; other half-lives (120, 365 days) and ridges (1, 4) were within 0.0007, so the shared settings stay.
- Ligue 2 (`leagues/ligue-2.json`, ESPN `fra.2` for deductions), from the [LFP's 2026-27 competition rules](https://www.lfp.fr/assets/26_27_Reglement_Competitions_08_09_2026_45d0881157.pdf):
  - Format: 18 clubs. The top two go up (Article 519). 3rd to 5th play the play-offs (5th at 4th, then the winner at 3rd), and the winner meets Ligue 1's 16th over two legs (Article 519 ter).
  - Relegation: the bottom two go down to Ligue 3, and 16th plays the Ligue 3 play-off winner over two legs (Article 519 bis). Tiers: Title, Promotion (top 2), Top 5, Relegation (bottom 2) and Bottom 3.
  - Tiebreakers (Article 518 ter): goal difference first, then head-to-head points and goal difference (only once both meetings are played), then goals, wins and away wins. Discipline comes after that, which the feed lacks.
  - Validation: the table matches the [LFP's](https://ligue1.com/fr/competitions/ligue2bkt/standings) after seven rounds (`tests/test_ligue_2.py`).
  - Ratings: FixtureDownload has no Ligue 2 season before 2026-27 (`season.firstYear`), so 2026-27 ratings start level for every club and use this season only.
- Women's Super League (`leagues/wsl.json`, ESPN `eng.w.1` for deductions):
  - Format: 14 clubs from 2026-27. 14th is relegated and 13th plays The Play-Off against the winner of BWSL2's 2nd v 3rd pre-qualifier ([WSL Football, 2026-27 fixtures](https://www.wslfootball.com/news/the-2026-27-fixtures-are-out)). The top three qualify for the Champions League ([official table key](https://www.wslfootball.com/standings/wsl)).
  - Tiers: Title, Champions League (top 3), Relegation (bottom 1) and Bottom 2.
  - Tiebreakers: goal difference, then goals scored, wins and head-to-head ([WSL Football](https://www.wslfootball.com/news/barclays-womens-super-league-explained)).
  - Validation: the table matches the official one (`tests/test_wsl.py`).
  - Backtest (2024-25 and 2025-26, 263 matches): 0.175 against 0.242 for base rates. Other half-lives and ridges were within 0.002, so the shared settings stay.

To add a football league, copy `leagues/epl.json`, set the FixtureDownload feed name, tiers and any team colours (teams without one get a generated colour), then run `venv/bin/python extract_table.py --league <id>`. A config's `notes` are added to the page's model notes, and `rules` (a summary and source links) documents the league's format. When FixtureDownload's feeds of a league start later than last season, set `season.firstYear` to the first one: that season's ratings then use its own results only, with every team starting level and a ridge of 4 instead of 2 (`FIRST_SEASON_RIDGE`: without a previous season, week-ahead predictions of 2023-24 to 2025-26 scored better that way in all eight leagues), and the page says so instead of warning about a missing previous season.

Backtest a league before publishing its odds: `scripts/backtest_football.py` predicts every past match a week ahead, as the site would have, and compares the ranked probability score with home/draw/away base rates; it also scores the title, top and bottom chances at 25%, 50% and 75% of each finished season against the final table (Brier score, next to a no-skill guess). `--half-lives` and `--ridges` try other model settings, and `--no-history` drops the previous season.

```bash
venv/bin/python scripts/backtest_football.py --league epl --seasons 2023 2024 2025
```

## European Cups

The UEFA Champions League, Europa League and Conference League (`leagues/champions-league.json`, `europa-league.json`, `conference-league.json`) are rolling football configs with `"engine": "european_cups"`, built by `european_cups.py`; they differ only in the UEFA competition id (`sources.uefa`: 1, 14 and 2019). The Conference League's league phase is six games per club instead of eight; the knockout format is the same. The season runs September to June, and the payload id carries the season, for example `champions-league-2026-27`.

- **Data** comes from the public JSON services behind uefa.com (`uefa.py`). No key is needed, but they are unofficial for third parties, like ESPN's, so every download is cached and a failed refresh falls back to the last good copy. Match data covers every qualifying and main-draw match, with 90-minute, extra-time and shoot-out scores and the winner of each tie. The official league-phase table is also used.
- **Table:** the 36-club league phase is ranked by UEFA's criteria: points, goal difference, goals, away goals, wins, away wins, then the opponents' combined points, goal difference and goals. UEFA's published order is used when it agrees with the results on every club's record. The 2025-26 tables of all three competitions are reproduced exactly (`tests/test_european_cups.py`).
- **Model:** a Poisson goals model (attack, defence, home advantage; a 730-day half-life) fitted on every UEFA club match from this season and the three before, qualifiers included.
  - Domestic league games from FixtureDownload are added at a quarter weight. They come from England, Spain, Germany, Italy, France, the Netherlands, Portugal, Scotland and Turkey, and are linked to UEFA clubs by name only when the match is unambiguous.
  - Each club is rated as its country's level plus its own difference from it, shrunk hard. A club with three European games and no domestic results then sits near its compatriots instead of being rated on three scores.
- **Backtest:** week-ahead predictions of the 1,062 main-draw matches of 2024-25 and 2025-26 in the three competitions score 0.2033 (ranked probability score). That compares with 0.2065 without country levels, 0.2082 also without domestic games, and 0.2323 for home/draw/away base rates. Season-long strength drift (0.1) was chosen by scoring top-8, top-24, round-reached and title odds at five checkpoints of those six competitions.
- **Simulation:** the rest of the league phase and the knockouts are simulated 20,000 times:
  - The knockout play-offs pair places 9/10 v 23/24, 11/12 v 21/22, 13/14 v 19/20 and 15/16 v 17/18.
  - The top eight meet the play-off winners of the matching pair.
  - Each top-eight pair is split between the two halves of the bracket.
  - Two-legged ties go to extra time and then penalties (a coin flip).
  - Real draws and results replace the simulated ones as they happen.
- **Page:** the table with Top 8, Top 24, Quarter-final and Title odds, fixture predictions, the matches that matter, and, from the knockout play-offs on, a bracket with aggregate scores.
- **Known limitation:** a club from a strong country with no domestic results in the data (a second-division cup winner, say) starts at its country's average until its European results move it.

## MLS And Football Playoffs

Major League Soccer (`leagues/mls.json`) is a rolling football config with `"engine": "football_playoffs"`, built by `football_playoffs.py`: football.py's table and goals model plus conference tables, seeding and a playoff bracket. The season runs February to December, and the payload id carries the year (`mls-2026`).

**Data**

- The regular season comes from FixtureDownload (`mls-{year}`).
- ESPN's public scoreboard (`usa.1`) supplies the playoff results and cross-checks every FixtureDownload score; where they differ, ESPN's score is used and the page lists the change. The 2026 feed had three wrong: LA Galaxy 1-3 St. Louis and LAFC 3-1 Real Salt Lake (22 July) were reversed, and Orlando City 1-2 Chicago (19 August) was 1-0. ESPN's scores agree with [mlssoccer.com](https://www.mlssoccer.com/standings/2026/conference).
- ESPN's table supplies the order of teams our tiebreakers cannot separate (it matches mlssoccer.com) and any points deductions. It is used only when every club's record agrees with the results.
- Both ESPN downloads are cached in compact form; if ESPN fails or changes its format, the last good copy is used with a warning, and with no copy at all the page leaves out title odds after the regular season.
- FixtureDownload names teams differently from season to season (2025's "New York" is 2026's "Red Bull New York") and from ESPN, so `aliases` maps every spelling to one name.

**Rules** ([2026 Competition Guidelines](https://www.mlssoccer.com/news/2026-mls-competition-guidelines), [2026 playoff schedule](https://www.mlssoccer.com/news/major-league-soccer-announces-audi-2026-mls-cup-playoffs-schedule))

- 30 clubs in two conferences of 15, 34 games each; 3 points a win, 1 a tie.
- Ties on points: total wins, goal difference, goals scored, head-to-head points then goal difference (same conference only; new in 2026, [2025 guidelines](https://www.mlssoccer.com/news/2025-mls-competition-guidelines)), fewest disciplinary points (not in any keyless data, so ESPN's order settles it), away goal difference, away goals, home goal difference, home goals.
- The top nine in each conference reach the Audi MLS Cup Playoffs:
  - Seeds 8 and 9 meet in a Wild Card match at the 8th seed. A level game goes straight to penalties.
  - Seeds 1-7 go straight to Round One, best of three: 1 v the Wild Card winner, 4 v 5, 2 v 7, 3 v 6. The higher seed hosts games 1 and 3, and every level game goes straight to penalties.
  - The Conference Semifinals (1/8/9 v 4/5, 2/7 v 3/6, no reseeding), Conference Finals and MLS Cup are single matches with extra time and penalties, hosted by the higher seed. MLS Cup is hosted by the finalist higher in the Supporters' Shield standings.
- The Supporters' Shield goes to the best regular-season record.

**Checks** (`tests/test_football_playoffs.py`, offline fixtures in `tests/fixtures/mls-2025.json` and `mls-2026.json`)

- The 2026 conference tables on 3 October 2026 (404 of 510 games) match [mlssoccer.com](https://www.mlssoccer.com/standings/2026/conference) for all 30 clubs: played, wins, losses, ties, goals, points and order. Level teams are split by wins before goal difference (New England above Miami, Red Bull New York above New York City and Cincinnati).
- The final 2025 tables match [mlssoccer.com](https://www.mlssoccer.com/standings/2025/conference).
- The 2025 playoffs are rebuilt from the final table and ESPN's games: every Wild Card, Round One series, semifinal, final and MLS Cup score, with Inter Miami as champion ([results](https://www.mlssoccer.com/playoffs/2025/news/who-s-left-audi-2025-mls-cup-playoffs-teams-matchups-results), [MLS Cup](https://www.mlssoccer.com/playoffs/2025/news/champions-inter-miami-lionel-messi-win-mls-cup-over-vancouver-whitecaps)).
- A mid-playoff state (4 November 2025) checks that series under way start from their real score and that title odds go only to teams still in.

**Model:** football.py's goals model and settings: a 240-day half-life, ridge 2, strength drift 0.2, and expansion sides starting below average. `scripts/backtest_football_playoffs.py --league mls` backtested them on 2024 and 2025:

- Week-ahead predictions of all 1,003 games score 0.2237 (ranked probability score) against 0.2315 for home/draw/away base rates (2024: 0.2267 v 0.2325; 2025: 0.2207 v 0.2306). The best half-life and ridge tried (120 days, ridge 4) scored 0.2229, too close to change. MLS is harder to predict than Europe's leagues (0.20-0.21).
- Season odds at 25%, 50% and 75% of both seasons scored a mean Brier of 0.0707-0.0709 for every drift from 0.1 to 0.25 (0.0712 at 0, 0.0711 at 0.3), so the European drift of 0.2 stays. Playoff-place odds by bin, predicted v observed (teams): 0.04 v 0.04 (27), 0.22 v 0.12 (17), 0.41 v 0.33 (21), 0.59 v 0.68 (28), 0.83 v 0.84 (25), 0.97 v 0.98 (59); the middle bins are small.
- With 2023 added (no 2022 feed, so early 2023 odds rest on that season alone), drift 0.3 scored best, which is why the drift is kept in the config (`model.drift`).

**Page:** one table per conference with the Wild Card and playoff lines, an overall table (the Supporters' Shield race), Playoffs, Top 7 (straight to Round One), Supporters' Shield and MLS Cup odds, conference-position chances, and, once the regular season ends, the bracket with series scores and match scores (penalties noted).

**The engine** (`football_playoffs.py`) is for any football league that ends in playoffs:

- `conferences` (each team has a `conference`), or none for one table.
- `tiebreakers`, in order: `wins`, `goal-difference`, `goals-for`, `head-to-head`, `away-goal-difference`, `away-goals`, `home-goal-difference`, `home-goals`.
- `playoffs.rounds`, played in each conference, or once across them with `"across": true`:
  - `match`: `single`, `series` (`bestOf`, `hosts` such as `1-1-1`) or `two-legged` (aggregate goals; the lower seed hosts the first leg).
  - `decider` for a level match or tie: `extra-time` (then penalties), `penalties` or `higher-seed`.
  - `pairs` fix the bracket, from seeds (`8`), winners (`"WC.1"`), losers (`"Q.1.loser"`) and, across conferences, `"East:CF.1"`. `teams` with no pairs reseeds the round, best seed left against the worst. Teams that enter later have a bye.
  - The better seed hosts unless the round is `neutral`; across conferences, the better overall record does.
- Tiers: `playoffs`, `seed` (top N of a conference), `top`/`bottom` (league table places), `best-record`, `champion` and `round` (reaching a round).
- Penalties are a coin flip and extra time is a third of a match. Real results from ESPN replace simulated ones (series start from their real score, a played first leg counts), and a real game that does not fit the bracket leaves title odds out with a warning.

## NFL, NBA, WNBA, NHL, MLB, NBL And WNBL

`leagues/nfl.json`, `nba.json`, `wnba.json`, `nhl.json`, `mlb.json`, `nbl.json` and `wnbl.json` are rolling configs too, with conferences, divisions, team colours and the playoff format. `us_sports.py` builds them:

- Data, no keys: FixtureDownload for the NFL, NBA, WNBA, NBL, WNBL and MLB; the NHL stats API (`api.nhle.com`) for the NHL, because it records overtime and shootout results (overtime losses are worth a point). Playoff rounds, "to be announced" placeholders and the NBA Cup, WNBA Commissioner's Cup and NBL Ignite Cup finals are left out of the regular season; games not yet on the NBA schedule are simulated against an average opponent; games never played when a schedule ends (MLB rainouts) are dropped.
- Tables: wins, losses, ties (NFL), overtime losses and points (NHL), win percentage, games behind, differential, last ten and streak, with league, conference and division views. Conference views are in seed order with the playoff line (and the NBA play-in line); a league seeded as one table (the WNBA, NBL and WNBL) shows its lines on the league table. The NBL and WNBL tables add points percentage, their tiebreaker.
- Seeding: NFL division winners take seeds 1-4 and three wild cards follow; the NBA seeds 1-6 directly and simulates the play-in for 7 and 8; the NHL takes three teams per division plus two wild cards; MLB division winners take seeds 1-3, the top two get byes, and three wild cards follow; the WNBA seeds its top eight 1-8 across the league, regardless of conference; the NBL's top six make the Finals, 1st and 2nd straight into the semi-finals and 3rd to 6th into a play-in; the WNBL's top five do, with 4th hosting 5th in an eliminator. Tiebreakers are simplified (win percentage, then division or conference record; points, games played and regulation wins in the NHL), except where a config lists the league's own (`playoffs.tiebreakers`): the WNBA table uses head-to-head record, record against teams at .500 or better, head-to-head points difference, then points difference; the NBL ladder uses points percentage (points scored over points conceded), which is how the NBL25 play-in put South East Melbourne above Sydney although Sydney won all three meetings. The WNBL has used the same rule since WNBL26 ([Basketball Australia](https://www.basketball.com.au/news/wnbl26-finals-race-fourth-place-permutations)); WNBL25 broke ties on head-to-head. Simulated seasons still break ties at random.
- Model: ratings from capped score margins with home advantage and a time decay, fitted on this and last season. The regular season is simulated 20,000 times with season-long strength drift, then the playoff bracket (single games in the NFL, best-of-3/5/7 series elsewhere) for title odds. Settings were chosen by backtesting the 2023-24 to 2025-26 seasons: week-ahead game predictions for the half-life, ridge and spread, and playoff odds at 25%, 50% and 75% of each season for the drift. Leagues with settings of their own (`LEAGUE_MODELS`) were backtested the same way with `scripts/backtest_us_sports.py`:

  | League | Seasons | Week-ahead games | Log loss (base rate) | Cap, half-life, last season, ridge, sigma | Drift (playoff-odds Brier) |
  | --- | --- | --- | --- | --- | --- |
  | WNBA | 2022-2026 | 1,312 | 0.609 (0.690) | 25, 120 days, 0.5x, 2, 11.5 | 4 (0.083) |
  | NBL | 2021-22 to 2025-26 | 729 | 0.647 (0.691) | 40, 60 days, 1x, 3, 15.75 | 7 (0.129) |
  | WNBL | 2021-22 to 2025-26 | 410 | 0.608 (0.692) | 35, 90 days, 1x, 0.5, 18 | 10 (0.119) |

- Tiers: playoffs, division title, a top seed (NFL, NBA and WNBA No. 1 seed, NBA top 6, WNBA top 4, NBL top 2, WNBL top 3, NBL and WNBL minor premiership, MLB bye, NHL Presidents' Trophy) and the title.
- Playoffs: once a regular season ends, results come from the MLB Stats API, the NHL stats API, ESPN's public scoreboard (NBA, WNBA and NBL; the NBA's own feed blocks automated requests) or the NFL feed's playoff rounds. Settled places show as ticks, finished series fix their winners, series under way start from their real score, and the rest of the bracket is simulated for title odds. Real tiebreakers only reorder teams level on record, so the seeding is matched to the real bracket by trying the orders of tied teams; if none matches, the title column is left out with a warning. This reproduces the 2025-26 playoffs of the NFL, NBA, NHL and MLB exactly, the WNBA's 2025 playoffs and 2026 first round, and the NBL's NBL25 and NBL26 finals (`tests/test_basketball.py`). ESPN's NBL games carry no round names, so each game is placed in the bracket by walking it in date order: it joins the unfinished series between its two teams. The Ignite Cup final, which ESPN lists as a postseason game, fits no series and is dropped; Ignite Cup finals at a neutral venue are skipped outright.
- WNBA format (from [wnba.com](https://www.wnba.com/news/2026-wnba-postseason-faq)): eight teams, best-of-three First Round (1-1-1), best-of-five Semifinals (2-2-1) and best-of-seven Finals (2-2-1-1-1) since 2025; 1 v 8 and 4 v 5 meet in one semifinal, with no reseeding. The series formats are in the config (`playoffs.series`), so a change of format is a config edit.
- NBL format (from [nbl.com.au](https://league.nbl.com.au/news/the-nbl26-finals-format-explained), used since NBL23): 3rd hosts 4th, and the winner meets 2nd; 5th hosts 6th, and the 3 v 4 loser hosts that winner for the semi-final against 1st. Semi-finals are best of three and the Championship Series best of five, with the higher ladder place hosting games 1, 3 and 5. NBL27 (2026-27, 33 games each) has not announced a different format.
- WNBL format (WNBL27, [wnbl.com.au](https://www.wnbl.com.au/news/wnbl-unveils-exciting-new-finals-format)): nine clubs and 22 games each with the Tasmania Jewels' arrival, and five finalists. 4th hosts 5th in a one-off eliminator whose winner meets 1st; 2nd meets 3rd. Semi-finals and the Championship Series are best of three, the higher place hosting games 1 and 3, as in [WNBL26](https://www.wnbl.com.au/news/wnbl26-finals-series-confirmed). No keyless source publishes WNBL finals results (ESPN has no WNBL, and the WNBL site's data service needs a key), so once the regular season ends the page shows the final ladder without title odds. Ignite Cup games count on the ladder; [the Ignite Cup Finals do not](https://www.nbl.com.au/news/the-hungry-jacks-nbl27-ignite-cup-schedule-tickets-rules-more).

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

API keys: only `CRICDATA_API_KEY` (free CricketData plan, 100 calls a day, personal and non-commercial use) for live cricket. Without it, cricket leagues are skipped with a warning. Football, MLS, NFL, NBA, WNBA, NBL, NHL and MLB need no key. Keyless sources and their terms: FixtureDownload (credit it), the NHL stats API, the MLB Stats API (individual, non-commercial use), ESPN's public scoreboard and table (unofficial; the NBA, WNBA, NBL and MLS playoffs, MLS score checks and football deductions use them, and the page falls back to no title odds if they change) and UEFA.com's match and standings services (unofficial; the European cups, cached, credited on the page).

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
