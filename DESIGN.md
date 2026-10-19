# Playoff Pulse · Night Signal

A season has dozens of possible endings. The design should make them feel immediate, then make the numbers effortless to read. Night Signal replaces the uniform green glass wash with ink, slate, a distinctive citron signature and solid, precise data planes. Readers are often on a phone, at night, watching a game. Tables and odds take priority over decoration.

## Direction and evidence

Three directions were rendered with the site's actual payloads across landing, hub, football, cricket and Formula 1, at 375 and 1280px in both themes. The full 60-image comparison is in `docs/screenshots/directions/`; source studies are in `docs/design-directions/`.

| Direction | Beauty | Odds clarity | Distinctiveness | Accessibility potential | Performance safety | Night fit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Night Signal: ink, citron, selective glass | 9 | 9 | 9 | 9 | 9 | 10 |
| Season Ledger: editorial serif, paper, open rules | 8 | 9 | 9 | 9 | 10 | 7 |
| Race Control: coral, squared timing boards, condensed capitals | 8 | 8 | 8 | 8 | 10 | 9 |

These scores are design judgments from the renders, not measured user-study results. Night Signal wins for night reading and a recognisable multi-sport identity. It borrows the Ledger's disciplined dividers and Race Control's sport-specific accents. The final implementation goes beyond the studies with purpose-built page compositions. See `docs/site-analysis.md` for audit and release evidence.

## Tokens

The source of truth is `frontend/ipl-analyzer-frontend/src/index.css`. Each colour has a `light-dark()` pair; system preference applies unless `html[data-theme]` overrides it. `pp-theme` remains the storage key. Inline head scripts apply the choice before first paint on both entry documents. Toolbar colours match the ground.

| Role | Day | Night |
| --- | --- | --- |
| Ground | `#eef0f2` | `#0b1016` |
| Data plane | `#ffffff` | `#151e28` |
| Quiet inset | `#f3f5f7` | `#1b2632` |
| Main ink | `#17212b` | `#f2f5f8` |
| Secondary ink | `#46576a` | `#b7c4d1` |
| Small labels | `#506175` | `#9eafc1` |
| Citron action | `#456500` | `#d4f75b` |
| Action text | `#ffffff` | `#172000` |
| Champion | `#815200` | `#f4cd72` |
| Qualifying / positive | `#08734d` | `#6ddbb0` |
| Elimination / negative | `#ad342e` | `#ff9c95` |
| Play-in / caution | `#8f4b00` | `#ffc184` |

Solid surfaces make contrast predictable. Glass is 90% opaque, with a 10px blur, limited to the header and selected feature surfaces. League tables, stat tiles and repeating hub cards do not blur. The subtle fixed two-direction ambient field is never animated. No nested blur and no stacked glowing panels.

## Typography, spacing and shape

Self-hosted Barlow Semi Condensed 600/700 supplies display headings and prominent odds. Self-hosted IBM Plex Sans variable supplies UI, prose and tables. Keep the existing fonts: distinct type without extra downloads. Numbers align with tabular figures.

The text scale is 12 / 14 / 16 / 20 / 24 / 32 / 40 / 56px; landing display may grow to 88px. Nothing below 12px. Uppercase only for short labels. The main league heading is compact enough that the table starts on the first phone screen. Space uses a 4px base, with 16px phone and 24px desktop gutters. Maximum content width is 1280px. Radius distinguishes layers: 16px major planes, 12px groups, 6px controls; pills only for status and small selectors. All interactive targets have at least 44px in each dimension, including icon and section controls.

## Sport and team identity

`--sport-accent` identifies the current competition. Football uses the brand citron, cricket azure, basketball apricot, American football lilac, ice hockey ice, baseball sky and Formula 1 coral. These colours label the sport and highlight a feature, never replace qualifying, danger or championship semantics. Pair each with text. Team colours remain payload data, confined to identity chips and actual match probability segments. Use `readableOn()` for text over a team colour; outline chips so black and white teams stay visible.

## Components and composition

Rollout: the foundation implements tokens, shared surfaces/header/search, control sizes, theme semantics, lazy routes and loading/recovery. The page-family and static-sharing rules below are the target contract for the subsequent dedicated PRs; they do not claim those features already shipped in the foundation.

- Shared header: citron pulse tile, wordmark, searchable league picker, theme toggle. The picker searches sport, long/short league names and season. Escape returns focus to the trigger. The theme button reports its pressed state.
- League header: sport rail, breadcrumb and status, one h1, concise method/freshness strap, joined key facts and 44px section navigation. Facts use solid tiles with crisp dividers.
- Data plane: one bordered surface, quiet column headers, aligned figures and a clear selected row. Real tables retain captions, scoped headers and row-header buttons. Wide data scrolls inside its own container; the page never scrolls sideways at 320px.
- Selected team: immediate quantitative payoff, readable distribution, and named next fixture. A selected state must be distinguishable beyond colour.
- Probability tracks: exact 0–100% geometry. Zero has zero length. Labels live outside segments when they do not fit. Do not give an unlikely event extra visual width. Finishing-position distributions state their scale and make values available on touch and keyboard.
- Conditional match impact: show the affected team/outcome, the named results and the difference in **percentage points**. Do not imply the probabilities are additive across overlapping season outcomes.
- F1: a timing-board rhythm with points, constructors and a derived points gap. Display actual remaining races/sprints; do not invent possible-points calculations.
- Landing: a distinct editorial front door with real race facts and direct league destinations, clear coverage, then method. No decorative charts, fake history, testimonials, vanity counters or stock photos.
- Hub: search and sport filtering above dense, scannable league destinations. Pre-season, ongoing and final states have honest labels. “Live” describes the season, not second-by-second updates.
- Share kit: genuine generated media, a visible date/archive state, and a correct route back to its league. No stale asset masquerades as current.
- Loading: static skeleton geometry and a polite status. Errors explain recovery; pre-season and completed views are designed states, not blank fallbacks.

## Motion and platform support

140–180ms on explicit colour, border, opacity, shadow and transform properties. Small lifts signal a clickable destination. No idle animations, parallax or moving backgrounds. Supported cross-document View Transitions are progressive enhancement; reduced-motion disables them. Avoid scroll-driven or gradient animation unless it conveys a real change. The site works without those APIs and without backdrop-filter. `light-dark()` has a conservative fallback. Never hide content pending an animation.

## Data, navigation and delivery rules

Only real payload data. Never draw an odds timeline from one snapshot or parse prose into chart data. Use the shared probability formatters, including near-certainty rules; simulated estimates never round to 100%. Explain model differences and limitations in context. All hash navigation must use `samePageHref()` because `<base>` otherwise drops `?league=`. Keep query routes, team hashes and both hosting bases working.

No runtime server, external fonts, trackers or paid dependencies. Load page families lazily. Per-league static HTML must have meaningful source content and metadata, with social images derived from the data. Existing query links remain compatible.

## Verification

Before every merge: Python tests, Vitest, ESLint, GitHub build; rendered phone and desktop checks in light/dark, no page overflow, no console errors, real clicks on league section/team links, and independent review. Measure contrast on the actual composited surfaces, not token names. Check Chromium and WebKit, theme persistence and reduced motion. Record Lighthouse's test conditions and lab metrics; TBT is not measured real-user INP. Match the deployed revision to the merge SHA, inspect Cloudflare's completion log, then capture production evidence. Never claim unperformed checks passed.
