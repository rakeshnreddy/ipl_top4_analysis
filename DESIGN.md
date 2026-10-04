# Playoff Pulse design system

Playoff Pulse is a working tool with one front door. The landing page (the site root) says what the site does and shows the biggest races from the live data; every other page is a tool. Readers arrive to check a table and a few probabilities, often on a phone, often in the evening while games are on. Every rule below serves one goal: the standings start within the first phone screen, and every number is readable.

**North star: "Floodlit pitch".** A calm jade-and-amber field behind frosted-glass panels, light by day and dark by night. Rich, quiet colour, never neon; the data stays the brightest thing on the page.

Tokens live in `frontend/ipl-analyzer-frontend/src/index.css`. Shared components are styled in `src/App.css`; each page adds only what it needs (`sport/SportPage.css`, `hub/HubPage.css`, `landing/LandingPage.css`).

## Themes

- **Light and dark, one set of tokens.** Every colour is a single `light-dark()` pair. With no choice saved, the page follows the OS setting (`color-scheme: light dark`). The header's theme button saves `pp-theme` (`src/lib/theme.ts`) and sets `html[data-theme]`; an inline script in `index.html` and `share.html` applies a saved choice before first paint, so there is no flash.
- **The ambient field.** `body::before` is a fixed layer of three soft radial colour fields (jade top-left, amber top-right, azure at the foot: `--ambient-1/2/3`). It gives the glass something to blur and is the only decoration. Never put a halo behind specific content.
- **Glass, in one layer.** Page-level containers are frosted glass (`--glass`, `backdrop-filter: blur(--glass-blur)`, a `--glass-border` hairline and `--shadow-glass`, which is a lit top edge plus an offset drop). That covers panels, hub cards, the key-facts strip, the site header and the landing race list. Layers that float over content (the league menu) use `--glass-strong`. Inside a panel, surfaces are tints (`--surface-2/3`) or near-opaque tiles (`--surface-solid`), never more glass.
- **Shadows have an offset.** No zero-offset glows.

## Colour roles

| Token | Use |
| --- | --- |
| `--accent` (jade) | Links, focus rings, selected state, the brand mark, the one solid call to action |
| `--gold` | Champions and first place (`zone-first`) |
| `--good` | Qualifying places, wins, positive NRR |
| `--warn` | Play-in or middle zones, data warnings |
| `--bad` | Relegation and elimination, losses, negative NRR |
| `--heat-good` / `--heat-bad` | Probability cell tints only |

- Each role has a `-soft` background variant (a translucent tint) for pills and selected rows.
- Every text/background pair meets WCAG AA (4.5:1) in both themes, measured on the glass as it renders over the brightest part of the ambient field. For example, `--text-subtle` on light glass over amber is 5.7:1, and on dark glass over jade it is 6.2:1.
- Colour is never the only signal: zone stripes sit next to rank numbers, and ticks carry visually hidden text.

**Team colours are data, not theme.** They appear as a thin chip beside the team name, which has a hairline outline so near-black and near-white colours stay visible. When text sits on a team colour, `readableOn()` in `src/lib/ui.ts` picks black or white by contrast instead of trusting the feed's suggested text colour.

**Probability tints.** `heatStyle()` mixes the heat colour at up to 40% over the surface, so cell text stays above 4.5:1 at 100%.

## Type

- **Display:** Barlow Semi Condensed 600/700, for page titles, section headings, the wordmark and team badges.
- **UI:** IBM Plex Sans (variable), for everything else.
- Both are self-hosted via `@fontsource` (`src/fonts.ts`); no third-party font requests.
- **Scale:** 12 / 14 / 16 / 20 / 24 / 32 / 40 / 56px (`--text-xs` … `--text-4xl`; 56px is only the landing headline). Nothing renders below 12px.
- Numbers use `font-variant-numeric: tabular-nums` wherever they line up in columns.
- Uppercase is reserved for small labels (12px, 600, +0.04em tracking): table headers, fact labels and menu group names.

## Space, size, shape

- Spacing is on a 4px base: `--space-1` (4) to `--space-8` (72). Use tight gaps inside a group and larger gaps between sections; the landing page uses the large end.
- Radius: `--radius-lg` 18px for glass containers, `--radius-md` 12px and `--radius-sm` 8px for things inside them, and `--radius-pill` for pills, the theme button and the call to action.
- Tap targets are at least 44px (`--tap`). This covers table rows, team buttons, menu items, list links and section links.
- Content is at most 1280px wide, with gutters of 16px on phones and 24px from 960px.

## Page structure

Every page uses the same frame:

1. **Skip link** to `#main`.
2. **Site header** (`components/SiteHeader.tsx`). It is sticky glass and holds:
   - the wordmark, which links to the landing page;
   - one **Leagues** menu grouped by sport, with the sports that have the most live races first ("All live races" opens the hub);
   - the theme button.
3. **Page header** (`components/PageHeader.tsx`), in this order:
   - Breadcrumb with a status pill (Live, Playoffs, Final, Pre-season).
   - One `h1`.
   - A one-line strap.
   - A joined strip of 3–4 key facts.
   - A row of in-page section links.
4. **Main content**, which is the table first:

   | Page | Order |
   | --- | --- |
   | Cricket | Standings, odds or playoffs, season summary, team view |
   | Football and US sports | Bracket (postseason only), table + sticky team panel, movers, fixtures, swing games, results, method |
   | Landing (the root) | Hero (headline, one-line lede, one solid call to action to the hub, a text link to the method) beside the biggest live races from the data; every league by sport; how the odds are made |
   | Hub (`?view=hub`) | Live races grouped by sport, then final tables |

5. **Footer**, outside `<main>`. It always starts with "Model estimates for fans, not betting advice." and then credits sources.

## Components

- **Panels** (`.panel` and friends) are a single surface. Do not nest a card in a card. Inside a panel:
  - Group stats in a joined block (`.stat-grid`, `.race-summary-grid`, `.key-facts`): one border, 1px dividers, wrapping flex so a short last row stretches.
  - Lists of games are separator lists (`.fixture-list`, `.sport-results`), not stacks of boxes.
- **Hub cards** are whole-card links, the one place a bordered card earns its keep. They lift 2px on hover.
- **Links within a page** use `samePageHref()`, never a bare `#id`: the page's `<base href>` would send a bare hash to the site root.
- **The landing page shows the product, not decoration.** Its "biggest races" list and sport lists come from `leagues.json`. Avoid feature-icon grids, stock imagery, big vanity numbers and gradient buttons.
- **Section headings:** an `h2` plus an optional one-line `p` note. No kicker labels above headings and no decorative icons beside them.
- **Tables** (`.data-table`):
  - Real `<table>` with a visually hidden caption, `scope` on headers, and the team name as a `th scope="row"` containing a button with `aria-pressed`.
  - Optional columns hide below 760px.
  - Short tier labels replace long ones on phones, but the long label stays for screen readers.
  - A league played in groups shows one table per group, each under an `h3` with its own caption, ranked within the group. The zone stripe marks the qualifying places across groups, and a note under the tables states the rule.
  - A football table that splits in two (Scotland) draws a dashed "Split" line between the halves and keeps its tier stripes. A play-off place just above the drop (11th) takes the `--warn` stripe; the drop itself stays `--bad`.
- **Segmented controls** (`.goal-tabs`): buttons with `aria-pressed`. They stay on one row and scroll sideways when there are many choices.
- **Charts:** decorative bars are `aria-hidden`, and a visually hidden list carries the values.

## Motion

- Transitions are 120–160ms on colour, border, shadow and transform only. The one authored moment is the hover lift on cards and the call to action.
- `prefers-reduced-motion` removes animation and smooth scrolling. `scrollToSection()` jumps instead of gliding when it is set.

## Checks before shipping UI changes

- `npm run lint` and `npx vitest run` in `frontend/ipl-analyzer-frontend`.
- Look at the landing page, a cricket page, a football page, an NFL page and the hub at 375px and at desktop width, in light and dark (toggle the theme button too). Check for no horizontal scroll and no console errors, and click a section link on a `?league=` page to confirm it stays on the league.
- No text below 12px. No new raw hex values outside `index.css`, except team data.
