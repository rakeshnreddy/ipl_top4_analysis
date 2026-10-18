# Visual, data-design and inspiration audit

Audit date: 18 October 2026. Auditor scope: visual system, information design/data visualisation, and primary-source inspiration research. This worker made no application changes and did not use the shared browser session. The lead worker owns the viewport/theme screenshot matrix and should add its visual evidence to the synthesis. Findings below are supported by the checked-in application and real payloads; subjective appearance judgments are explicitly design judgments, not measured accessibility or performance results.

Reviewed: `README.md`, `DESIGN.md`, shared tokens/components, landing, hub, cricket, generic sport, F1 and share-kit implementations. Live addresses supplied for the synthesis: [Cloudflare primary](https://ipl-playoff-pulse.pages.dev), [GitHub Pages mirror](https://rakeshnreddy.github.io/ipl_top4_analysis/). Verified current F1 route: `?league=f1-2026` (`sport: motorsport`). The index contains 44 leagues.

## Assessment

The existing system is coherent and unusually careful about the fundamentals: self-hosted fonts, real tables, tabular numerals, one-layer panel treatments, compact league headers, accessible text equivalents for position charts, correct probability formatters for season estimates, and distinct completed-season views. Preserve those advantages.

The visual limitation is the uniform treatment. A title race, a data table, a method explainer and a media tool all receive essentially the same 18px rounded jade glass panel. The site has a palette but little compositional identity. Its strongest content—the real numbers and the consequences of the next game—should become the visual signature. A striking front door can coexist with compact, solid, exceptionally legible league pages.

The most urgent data-design repair is more concrete: current minimum bar widths misrepresent very small probabilities. Numbers can be correct while the chart geometry tells a different story.

## Rendered baseline observations

After the source audit, eight representative baseline frames were opened directly from `docs/screenshots/before` (landing dark 1280/light 375; football dark 375/light 1280; F1 dark 1280; cricket light 375; hub dark 375; share light 1280). The baseline confirms the source judgment: the green/amber wash remains prominent behind every tool, the panels share nearly identical treatment, and the landing has no distinct data-led focal point. The numerical tables are readable in these frames and the first rows appear on the phone screen. The hub uses a long introductory paragraph above a uniform card collection. The baseline share-light-1280 capture contains several still-loading thumbnails, so it should not be used as evidence of a broken gallery. See `foundation-visual.md` for the subsequent full 24-frame foundation review.

## Structured findings

Severity: P1 = threatens faithful data interpretation; P2 = materially weakens comprehension or the requested visual result; P3 = polish or an opportunity. Source locations are one-based and refer to the pre-redesign source.

| Page | Element | Severity | Evidence | Suggestion |
| --- | --- | --- | --- | --- |
| Football / US / basketball / cups | Fixture probability bars | **P1** | `sport/SportPage.tsx:612` clamps every segment to at least 6%. An inspection of current checked-in fixture payloads found 112 outcome values below 6%; for example WSL outcomes include 2%. The flex layout then has to compress the inflated total. | Use exact proportions with a stable home/draw/away order. Put labels below the bar when a segment is too narrow. Do not enlarge a 2% event to fit text. Keep the text equivalent. |
| Cricket, in season | Qualification race bars | **P1** | `App.tsx:538` uses `Math.max(probability, 2)`: even a zero chance paints 2% of the track. | Give zero a zero-length fill and a readable numeric/status label. If a tiny nonzero outcome needs a marker, use an explicitly non-scaled hairline marker with an explanation. |
| Team detail, generic sport | Finishing-position distribution | **P2** | `SportPage.tsx:793,872` rescales every team to its own maximum, then gives any positive value a minimum 3% chart height. No visible probability axis or value appears; exact values are only in `title` and a hidden list. Real Arsenal distribution peaks at 36.3%; Aston Villa at 8.06%, yet both peaks fill the chart. | Use a labelled probability axis and state the scale. Prefer a fixed 0–100% scale for cross-team comparison, or an explicitly labelled adaptive scale with its maximum. Make the modal position and its probability visible; touch/keyboard interaction should expose any bar's value. |
| Landing | “Biggest races right now” | **P2** | `LandingPage.tsx:42` takes the first six non-complete leagues with facts, not the six closest races or largest swings. Current six are all football. The hero prints only `facts[0]` per league (`:83`), generally a title favourite. | Rename to “Featured races” unless a documented ranking is computed. Choose a deterministic cross-sport spread and expose real second/third race facts. A future closeness score must come from numerical data, not parsed prose. |
| Landing | Hero product demonstration | **P2** | `LandingPage.tsx:76–101` gives the product six mostly textual lines, while the large headline and long lede describe coverage. The content contains no visual comparison of competitors. | Build one hero race module from verified structured facts: outcome label, team, large probability, exact track, and a clear league link. Retain a compact live-race list beside or below it. Do not invent a historical curve or imply real-time updating. |
| Landing, hub, all league pages | Surface hierarchy | **P2**, visual judgment | `App.css:433–447` applies exactly the same blur, border, radius and shadow to `.panel`, ladder, odds, summaries, spotlight and share sections. `index.css:49–61` provides the same three-colour ambient field everywhere. | Restrict glass to the header and a small number of feature surfaces. Give dense tables nearly opaque surfaces. Use composition, scale and restrained sport accents to make hero, selected team, supporting lists and method visibly different. |
| All sports | Brand and sport identity | **P2**, visual judgment | The accent is jade for every sport (`index.css:78`); sport pages share all primary table/panel styling. Sport identity is largely confined to words and 4px team chips. | Introduce one controlled sport-accent token for section markers, breadcrumb marks and a feature-edge tint. Keep success/danger semantics independent of sport accents and team colours. Use short text labels or simple line marks as a second identifier. |
| Hub | Dozens of equally weighted cards | **P2** | `HubPage.tsx:92–100` renders the entire live collection in grouped card grids. Cards use the same label/value layout (`:27–35`) and text scale; there is no focal featured race. | Add a compact sport filter/search and one featured module; maintain a dense scannable league grid beneath it. Use small, accurate probability tracks only when numeric data is available. Ensure final and upcoming states remain visually recognisable. |
| Hub and landing | “Live” terminology | **P2** | `data/leagues.ts:isLive()` means any status except complete; the status badge can simultaneously say Pre-season. Landing prose says all `isLive` items are “in season now”, and hub section prose says “Seasons in progress”. | Separate in-progress, upcoming and final counts. “Active seasons” can include preseason; “Live” should be explained as a season state, since data refreshes twice daily rather than play by play. |
| Generic sport | Matches That Matter | **P2** | `SportPage.tsx:722–755` shows three conditional percentages as a small definition list. The payload already supplies `swing`; current EPL example gives Coventry relegation 51.0% after a Spurs win, 39.8% draw, 27.3% Coventry win, with a 23.7 percentage-point swing. | Present a labelled horizontal range/dot plot from 27.3 to 51.0%, plus a large “23.7 percentage-point swing”. Name the affected team and outcome immediately. Keep the original conditional numbers readable in text. |
| Generic sport | Knockout bracket | **P2** | `SportPage.css:.bracket-rounds` is an auto-fit set of round columns; `BracketPanel` has no advancement connectors or selected-team path. On narrow screens it becomes successive round lists. | On desktop use restrained connectors tied to actual bracket relationships. On mobile use round tabs or a vertical path with explicit “winner advances to” text. Do not draw connectors by assuming adjacency when the payload does not encode it. |
| F1 | Points and title-race context | **P2** | `F1Page.tsx:215–288` is a conventional table with points and odds. The header says who is favoured but not the points gap or races remaining together. Current payload has Antonelli 340, Russell 238, six remaining events. | Add a compact, derived championship summary: a 102-point lead and the real remaining race/sprint counts. A points-gap dot plot can make the hierarchy instantly legible. Show available points only if computed from the configured scoring rules. |
| F1 | Sport-specific personality | **P3**, visual judgment | `F1Page.css` deliberately inherits the general panel/table system and adds only name cells, event tiles and podium lists. | Use a timing-board rhythm: crisp tabular points, slim constructor-colour rails and a racing-red sport accent. Keep table headings and values as readable as the other sports; avoid telemetry-like decoration without data. |
| All league tables | Odds versus current stats | **P2** | The same table contains rank/points/form and simulated future outcomes; probability columns are tints, but their headers are ordinary labels. `App.css` has no strong column-group heading. | Visually group “Today” and “Season chances”, with a small visible `%`/“chance” explanation. If horizontal scroll is required, pin team identity and show a scroll cue. Preserve true column/table semantics. |
| All league tables | Qualification/relegation cutoffs | **P2** | Shared tables mark zones with a 3px rank-cell colour stripe (`App.css:625–638`). Some explicit cutline labels exist for groups/splits, but standard league zones do not consistently explain the boundary next to it. | Use a quiet divider labelled “Top 4” or “Relegation” at relevant cutoffs or provide a visible textual key. Keep rank, label and colour together; a rank number alone does not explain what the stripe means. |
| Cricket | Selected team detail hierarchy | **P3** | `App.tsx:556–609` separates a selected-team heading-only glass panel from summary and detailed team content. Users see a large container with name/tabs but no immediate quantitative payoff. | Join the selected-team name, goal control and primary chance in one coherent detail header. Let the deeper sections flow from it without repeating every fact in equally weighted tiles. |
| Share kit | Completed-season media freshness | **P2** | `SharePage.tsx` warns that league-stage slides do not show the final table, then renders the dated pack. A warning and a polished image gallery can compete in visual emphasis. | Mark every outdated thumbnail/pack as archived with an explicit date. Lead the completed state with the actual final-season context and a route back to that league. Never let stale share graphics visually outrank the warning. |
| All page families | Loading/error/empty appearance | **P3** | `PageState.tsx` has a generic spinner panel and error panel. The layout does not reserve the coming table/hero geometry, and empty fixture/results sections frequently disappear. | Use calm skeleton rows and a fixed-size shell for the major content, respecting reduced motion. Empty states should say why there are no games/odds and what comes next; completed and preseason states should look intentional. |

### Important interpretation limits

- The season-level `formatChance()` is already careful about simulated near-certainty (`>99.9%`). Preserve it. Fixture labels and team-next-game labels use `Math.round(value * 100)` independently; no current inspected fixture rounds to 100%, but reuse the safe formatter so future inputs cannot violate the owner's rule.
- Do not add a title-odds timeline from the current payload. A single probability snapshot is not history. The current movement snapshot can support a before/after comparison when both values are available, but cannot support an invented continuous line.
- No screenshot-based contrast failure, scrollbar failure, breakpoint overflow or measured performance regression is asserted by this worker. The lead auditor must resolve those from rendered evidence.

## Data visualisation priorities

| Question a fan asks | Appropriate visual | Available now? | Rules |
| --- | --- | --- | --- |
| Who is most likely to qualify/win? | Exact horizontal probability tracks with aligned text | Yes, league odds | Fixed 0–100%; avoid floors; sport accent is separate from outcome meaning. |
| Where might my team finish? | Discrete finishing-position bars with a visible scale and modal probability | Yes, generic sports `analysis.positions` | Do not smooth across discrete places; keep all exact values available to keyboard/touch and assistive tech. |
| What changes if this game goes either way? | Conditional dot/range plot | Yes, `matchesThatMatter` | Show the three named results and affected outcome; use **percentage points**, not “percent”, for differences. |
| Who just gained ground? | Before/after dumbbell or a signed delta row | Partly, movement payloads | Do not draw a timeline from one change. Include the “since” timestamp. |
| How do I reach the final? | Connected bracket/path plus round list | Bracket scores exist; validate relationship encoding | Never assume a series feeds another merely by screen position. Unresolved participants stay “To be decided”. |
| How far behind is this F1 driver? | Points-gap plot plus explicit lead text | Yes, standings | Zero means the leader, and smaller gaps are better; label this orientation. Use real scoring rules for possible remaining points. |
| What must my cricket team win? | Win-bucket distribution/step chart | Yes, own-win buckets | Use full bucket labels and explain equal-strength/NRR limitations in place. Do not imply an exact clinch if the model excludes NRR. |
| How has the title race evolved? | Multi-team probability timeline | **No**, capped history is backlog | Defer until persisted, timestamped history exists. |

Use small SVG or CSS charts rather than a charting dependency. Each chart should have a nearby sentence or simple table giving its takeaway and exact figures. The main standings stay first on league pages.

## Primary-source inspiration research

Research was performed on 18 October 2026. These are verified content/interaction patterns from primary sources. They are recommendations inferred from those patterns; no claim is made about browser-measured speed or visual quality of the external products.

| Source | Verified pattern | Adaptation for Playoff Pulse |
| --- | --- | --- |
| [Opta Analyst Premier League table](https://theanalyst.com/competition/premier-league/table) | Separates Actual, Expected and Predicted table modes; league pages also distinguish overview, articles, stats, rankings, table and fixtures. | Clearly group present standings and future estimates. Use shallow section navigation. A small selected-team panel is more useful here than copying the publication's many editorial destinations. |
| [Apple Sports user guide](https://support.apple.com/guide/apple-sports-app/welcome/web) | Gives fans favourite teams/leagues, recent/upcoming games, then deeper game details. | Design the phone hierarchy around “my race → my team → next consequence”. A local favourites list is a useful later enhancement without needing accounts. Do not imply Apple-style real-time data freshness. |
| [Official F1 drivers standings](https://www.formula1.com/en/results/2026/drivers) | Presents position, driver, nationality, team and points, with year and driver/team result destinations. | Preserve a recognisable timing-table layout and constructor context, then add the site's distinct contribution: probabilistic outcomes and championship gaps. Avoid filling the view with unrelated media. |
| [FiveThirtyEight's own soccer data documentation](https://github.com/fivethirtyeight/data/tree/master/soccer-spi) | Documents home/away/draw forecasts, projected goals and separate importance values for each side, with a model explainer. | Make the distinction between match win probability and season impact explicit. Place a plain-language method explanation beside assumptions, and offer inspectable data/method links. This source documents its data; it is not evidence that a current live 538 product exists. |
| [Official Premier League table page](https://www.premierleague.com/en/tables/premier-league) | Keeps Table, Matches, Statistics and club destinations distinct. | Reuse familiar “Table” and “Fixtures” language, and layer future odds onto the table without making the navigation an analytics taxonomy. The text extraction did not expose the JS-rendered table, so visual treatment is not independently verified. |

ESPNcricinfo's [IPL standings page](https://www.espncricinfo.com/series/ipl-2026-1510719/points-table-standings) and [FBref](https://fbref.com/en/) returned HTTP 403 to this research tool. Do not report them as inspected. The Athletic was not independently inspected. The important competitive opportunity is still clear from the verified sources: all-sport season consequences, accessible on a phone, without ads, live-score clutter, sign-in or bookmaker framing.

## Three distinct visual directions

These are proposed directions for the lead worker to render with real data. Scores are design judgments before those renders, not usability-study results. All palettes require contrast measurement on their final rendered surfaces. Surface/text hexes are a starting point, not an AA certificate.

### A. Night Signal — recommended

**Mood:** a premium evening sports broadcast, calm enough to keep open through a game. High-contrast ink, glacial mint, crisp statistics and a small amount of luminous glass. It evolves the owner's requested glass feeling while replacing the full-page green wash with a deliberate composition.

| Role | Light | Dark |
| --- | --- | --- |
| Ground | `#EEF3F5` | `#071119` |
| Main table surface | `#FCFEFF` | `#101E29` |
| Feature glass | `#FFFFFFD9` | `#142B39C7` |
| Text | `#10232E` | `#EFF6FA` |
| Muted text | `#4C616E` | `#B0C1CC` |
| Brand/action | `#006B62` | `#79E2C4` |
| Championship | `#815200` | `#F4CD72` |
| Danger | `#AD342E` | `#FF9C95` |

- **Type:** existing self-hosted Barlow Semi Condensed 600/700 + IBM Plex Sans variable. Display numbers can be 52–88px on the landing feature, 28–36px on a team feature; tables stay 14px. This earns impact without downloading new families.
- **Composition/depth:** editorial split hero with a real race module; opaque table plane, one raised selected-team plane; glass only in header, featured race and active picker. Cool ambient colour sits at the perimeter, with a visible border and restrained offset shadow. More quiet space between sections, fewer containers inside containers.
- **Motion:** 140–180ms selection/hover; short crossfade for filtered content; optional supported view transition between league pages. No always-moving glow or scroll-bound number reveal. Reduced motion removes all travel.
- **Data style:** exact thin probability tracks, prominently aligned numbers, labelled distributions and conditional dots. Most ink is neutral; outcome status uses text plus colour.
- **Sport identity:** football mint `#79E2C4`, cricket azure `#8CCBFF`, basketball apricot `#FFC08A`, American football lilac `#C5B6FF`, hockey ice `#95E1EC`, baseball sky `#9CBFFF`, F1 coral `#FFA49B` (dark accent examples; generate measured darker light pairs). Accents appear in a rail, marker or feature tint. Team chips remain the team's own colours, never the page background.
- **Page translation:** landing gets the most composition; hub gets compact sport-labelled modules; cricket uses the race tracks and win buckets; football uses the solid table and selected-team detail; F1 uses a points-gap rail; share kit uses a large real asset preview with date/state controls.

### B. The Season Ledger

**Mood:** a beautifully typeset sports annual with the precision of a financial results sheet. Cream, ink and oxblood; editorial spacing and rules rather than soft panels. This is intentionally a different design philosophy from glass.

| Role | Light | Dark |
| --- | --- | --- |
| Ground | `#F4F0E6` | `#191916` |
| Main surface | `#FFFCF5` | `#23241F` |
| Text | `#23251F` | `#F4F0E5` |
| Muted | `#5F6255` | `#BFC1AF` |
| Brand/action | `#8E2435` | `#F0A6AE` |
| Championship | `#7C5900` | `#DBBE75` |
| Positive | `#2D654A` | `#A6D0AD` |
| Danger | `#A03321` | `#ECA18D` |

- **Type:** self-hostable Fraunces variable display + IBM Plex Sans variable UI. Use optical-size-aware headings and a disciplined number column; avoid serif numerals in dense tables.
- **Composition/depth:** strong masthead, short editorial hero, horizontal rules, broad margins and flat paper surfaces. Squarer 4–8px corners, one very slight offset shadow on a feature sheet. Tables feel like the main document.
- **Motion:** 120ms ink and underline changes; a simple 160ms content fade. No animated background or parallax.
- **Data style:** black-on-paper numbers, hatching/labels for zones, narrow ink bars, small multiples and quiet dot plots. Explicit facts and captions do more work than saturation.
- **Sport identity:** subtle named section tabs and one ink accent per sport; team colours restricted to chips. Distinct section numerals can give cricket/football/F1 their own rhythm without changing the table language.
- **Page translation:** landing behaves like the front page of an annual; hub becomes a race index; football/cricket are annotated tables; F1 is a championship ledger; share kit is an editorial proof sheet.
- **Tradeoff:** excellent daylight clarity and performance, but may recreate the owner's earlier “bland/plain” reaction unless the editorial compositions and typography are exceptionally strong; night mode is comfortable but less atmospheric.

### C. Race Control

**Mood:** energetic broadcast graphics and a pit-wall instrument panel. Cobalt, lime and carbon; asymmetric blocks and decisive geometry. This is the most visibly sporting and the most restrained in softness.

| Role | Light | Dark |
| --- | --- | --- |
| Ground | `#E9EDF5` | `#090B13` |
| Main surface | `#FFFFFF` | `#161A28` |
| Text | `#151C34` | `#F2F5FF` |
| Muted | `#515D78` | `#B4BED8` |
| Brand/action | `#2449D8` | `#A6B8FF` |
| Feature accent | `#4C6500` | `#D2F565` |
| Championship | `#7D5100` | `#F3CB68` |
| Danger | `#AD263E` | `#FFA3B1` |

- **Type:** self-hostable Space Grotesk variable display + IBM Plex Sans UI. Large race numbers and tight short headings; body prose stays uncondensed.
- **Composition/depth:** angular graphic framing on the hero, 4–10px corners, strong grid lines, dark feature block, a narrow glass control strip. Tables remain opaque. The hero may use one factual title-odds ladder as a central graphic, not a decorative fake track.
- **Motion:** one subtle 200ms entrance for a selected feature; 120ms active tab/track changes. Any progress movement represents a user action, not live data arrival. Reduced motion gives instant state changes.
- **Data style:** race-lane bars, colour-controlled dot plots, crisp numeric overlays and explicit axes; no gauges without meaningful bounded quantities. Avoid lime for both brand and qualification status.
- **Sport identity:** compact named sport tags and different edge patterns (pitch lane, crease rule, court arc, timing stripe) restricted to non-data chrome. All charts retain the same geometry and semantics across sports.
- **Page translation:** landing is a broadcast race board; hub is a multi-sport control wall; league pages are timing boards; cricket uses qualification lanes; F1 feels native; share kit is a compact production console.
- **Tradeoff:** the strongest first impression and F1 fit, but highest risk of crowding a 375px viewport and fatigue during long evening reading. Requires discipline with saturation.

### Pre-render scorecard

Ten is best. “Performance safety” means lower implementation/performance risk.

| Direction | Beauty | Odds clarity | Distinctiveness | Accessibility potential | Performance safety | Night viewing | Total / 60 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A. Night Signal | 9 | 9 | 8 | 9 | 9 | 10 | **54** |
| B. The Season Ledger | 8 | 10 | 9 | 10 | 10 | 8 | **55** |
| C. Race Control | 9 | 8 | 10 | 8 | 8 | 8 | **51** |

The raw score favours Ledger's clarity/safety, but the owner's expressed taste and primary evening use favour **Night Signal**. Pick A, borrow B's precision and warmer daytime neutral, and borrow C's sport-labelled race lanes and decisive feature composition. Do not combine all three palettes, font families or panel shapes. Actual phone/desktop renders must decide whether A earns its expected beauty score.

## Acceptance checks for the chosen direction

1. Capture landing, hub, football, cricket, F1 and share kit at 375/768/1280px in both themes. Main standings should begin in the first phone screen on league pages, and all odds remain readable at 320px.
2. Check a saturated team colour, a white team colour and a black team colour in fixture bars and badges. Their meaning must survive grayscale and each label must remain readable.
3. Use source values of 0, 0.1, 2, 50, 99.95 and 100 to inspect chart geometry/formatting. A label must never force the underlying probability track to grow.
4. Inspect a broad distribution and a sharp distribution using the same documented scale; reveal exact probabilities with touch, mouse and keyboard.
5. Verify preseason, midseason, postseason, complete, missing-data, loading and error states with real fixtures, not an invented visual demo.
6. Confirm that a beautiful hero does not delay the league table, that no constantly animated gradient competes with the numbers, and that reducing motion leaves a complete usable page.

