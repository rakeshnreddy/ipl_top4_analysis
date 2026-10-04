# Playoff Pulse design system

Playoff Pulse is a working tool, not a landing page. Readers arrive to check a table and a few probabilities, often on a phone. Every rule below serves one goal: the standings start within the first phone screen, and every number is readable.

Tokens live in `frontend/ipl-analyzer-frontend/src/index.css`. Shared components are styled in `src/App.css`; each page adds only what it needs (`sport/SportPage.css`, `hub/HubPage.css`).

## Themes

- Light and dark both follow the reader's OS setting (`prefers-color-scheme`), and `color-scheme: light dark` is set so form controls and scrollbars match.
- Surfaces are flat. Hierarchy comes from `--bg` → `--surface` → `--surface-2/3` and hairline borders. There are no glass panels, glows or decorative gradients.
- Shadows are limited to things that float: the league menu (`--shadow-md`) and a faint `--shadow-sm` on panels in the light theme only.

## Colour roles

| Token | Use |
| --- | --- |
| `--accent` | Links, focus rings, selected state, the brand mark |
| `--gold` | Champions and first place (`zone-first`) |
| `--good` | Qualifying places, wins, positive NRR |
| `--warn` | Play-in or middle zones, data warnings |
| `--bad` | Relegation and elimination, losses, negative NRR |
| `--heat-good` / `--heat-bad` | Probability cell tints only |

- Each role has a `-soft` background variant for pills and selected rows.
- Every text/background pair meets WCAG AA (4.5:1) in both themes.
- Colour is never the only signal: zone stripes sit next to rank numbers, and ticks carry visually hidden text.

**Team colours are data, not theme.** They appear as a thin chip beside the team name, which has a hairline outline so near-black and near-white colours stay visible. When text sits on a team colour, `readableOn()` in `src/lib/ui.ts` picks black or white by contrast instead of trusting the feed's suggested text colour.

**Probability tints.** `heatStyle()` mixes the heat colour at up to 40% over the surface, so cell text stays above 4.5:1 at 100%.

## Type

- **Display:** Barlow Semi Condensed 600/700, for page titles, section headings, the wordmark and team badges.
- **UI:** IBM Plex Sans (variable), for everything else.
- Both are self-hosted via `@fontsource` (`src/fonts.ts`); no third-party font requests.
- **Scale:** 12 / 14 / 16 / 20 / 24 / 32 / 40px (`--text-xs` … `--text-3xl`). Nothing renders below 12px.
- Numbers use `font-variant-numeric: tabular-nums` wherever they line up in columns.
- Uppercase is reserved for small labels (12px, 600, +0.04em tracking): table headers, fact labels and menu group names.

## Space, size, shape

- Spacing is on a 4px base: `--space-1` (4) to `--space-7` (48). Use tight gaps inside a group and larger gaps between sections.
- Radius: `--radius-sm` 6px for inner blocks, `--radius-md` 10px for panels, and `--radius-pill` for pills and segmented controls.
- Tap targets are at least 44px (`--tap`). This covers table rows, team buttons, menu items, list links and section links.
- Content is at most 1280px wide, with gutters of 16px on phones and 24px from 960px.

## Page structure

Every page uses the same frame:

1. **Skip link** to `#main`.
2. **Site header** (`components/SiteHeader.tsx`). It is sticky and holds the wordmark (links home) and one **Leagues** menu grouped by sport, with the sports that have the most live races first. This replaces the rows of league chips that used to sit above every page.
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
   | Hub | Live races grouped by sport, then final tables |

5. **Footer**, outside `<main>`. It always starts with "Model estimates for fans, not betting advice." and then credits sources.

## Components

- **Panels** (`.panel` and friends) are a single surface. Do not nest a card in a card. Inside a panel:
  - Group stats in a joined block (`.stat-grid`, `.race-summary-grid`, `.key-facts`): one border, 1px dividers, wrapping flex so a short last row stretches.
  - Lists of games are separator lists (`.fixture-list`, `.sport-results`), not stacks of boxes.
- **Hub cards** are whole-card links, the one place a bordered card earns its keep.
- **Section headings:** an `h2` plus an optional one-line `p` note. No kicker labels above headings and no decorative icons beside them.
- **Tables** (`.data-table`):
  - Real `<table>` with a visually hidden caption, `scope` on headers, and the team name as a `th scope="row"` containing a button with `aria-pressed`.
  - Optional columns hide below 760px.
  - Short tier labels replace long ones on phones, but the long label stays for screen readers.
  - A league played in groups shows one table per group, each under an `h3` with its own caption, ranked within the group. The zone stripe marks the qualifying places across groups, and a note under the tables states the rule.
- **Segmented controls** (`.goal-tabs`): buttons with `aria-pressed`. They stay on one row and scroll sideways when there are many choices.
- **Charts:** decorative bars are `aria-hidden`, and a visually hidden list carries the values.

## Motion

- Transitions are 120–160ms on colour, border and transform only.
- `prefers-reduced-motion` removes animation and smooth scrolling. `scrollToSection()` jumps instead of gliding when it is set.

## Checks before shipping UI changes

- `npm run lint` and `npx vitest run` in `frontend/ipl-analyzer-frontend`.
- Look at a cricket page, a football page, an NFL page and the hub at 375px and at desktop width, in light and dark. Check for no horizontal scroll and no console errors.
- No text below 12px. No new raw hex values outside `index.css`, except team data.
