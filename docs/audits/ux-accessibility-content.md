# UX, accessibility and content audit

Audited 18 October 2026 against checkout `9c0f071`. Scope: landing, hub, cricket, shared football/US-sport pages, Formula 1 and Share Kit. Read README.md, DESIGN.md, the full redesign brief, route/data loaders, shared components, page components and their CSS. This is the source audit for the parallel site review; the lead auditor owns production screenshots and browser reproduction on [Cloudflare Pages](https://ipl-playoff-pulse.pages.dev) and the [GitHub Pages mirror](https://rakeshnreddy.github.io/ipl_top4_analysis/).

Severity: **P1** means a non-negotiable brief requirement or data interpretation is at risk; **P2** means a meaningful usability/accessibility defect; **P3** means polish. Source-confirmed findings below are distinct from browser follow-ups. No model, payload or application code was changed by this audit.

## Findings

### UXA-01 — Repeated controls fall below the required 44px target

- **Page / element:** All league pages, page-section links and segmented goal/table controls; Share Kit actions and slide download links.
- **Severity:** P1, accessibility acceptance criterion.
- **Evidence:** `src/App.css:397` sets `.page-sections a` to `min-height: 36px`; `:802` sets `.goal-tabs button` to 36px; `:1095` sets share actions to 40px. `.reel-slide-card div a` at `:1140` only sets its 12px text, with no minimum target. Footer links at `:1038` also have no minimum hit area. These are frequent direct interactions despite the 44px token already existing at `src/index.css:46`.
- **Suggestion:** Use `min-height: var(--tap)` for standalone controls and at least 44px in both target dimensions for icon/short controls. Give downloads a full-width hit area if space is tight. Keep inline prose links inline; verify standalone footer/action links separately. Measure bounding boxes at 320px and 375px.

### UXA-02 — Team selection moves the viewport while leaving keyboard focus behind

- **Page / element:** Cricket and shared sport table team selectors.
- **Severity:** P2, keyboard and screen-reader continuity.
- **Evidence:** Cricket `src/App.tsx:445–448` changes state and scrolls to `deep-dive`; shared sport `src/sport/SportPage.tsx:312–315` does the same for `team`. The targets at `App.tsx:556` / `SportPage.tsx:810–815` have no focusable heading, and the selected detail is not a live region. Selectors have `aria-pressed` but no relationship to the controlled panel. A keyboard activation can therefore scroll away from the focused table button; the next Tab follows the old table sequence.
- **Suggestion:** Add a stable heading ref with `tabIndex={-1}`, `aria-controls` on the selectors, and focus the updated heading after intentional activation. Alternatively, keep the viewport/focus in the table for keyboard selection and announce the panel update. Preserve the shareable team hash and reduced-motion behavior.

### UXA-03 — Escape hides a focused league link without restoring focus

- **Page / element:** Shared Leagues disclosure.
- **Severity:** P2, keyboard navigation.
- **Evidence:** `src/components/SiteHeader.tsx:71–75` handles Escape only by closing the panel. The trigger has no ref, and the focused link can become hidden by `hidden={!open}` at `:114`. There is also no focus-out closure: after tabbing through the list, the menu can remain open over the page.
- **Suggestion:** Keep this as a native disclosure/navigation pattern, save a trigger ref, and return focus to it on Escape. Close when focus leaves the disclosure, without trapping focus. Test Enter, Tab, Shift+Tab and Escape with the menu scrolled near its bottom.

### UXA-04 — Forty-four leagues have no search or compact sport navigation

- **Page / element:** Leagues menu, landing league list and all-races hub.
- **Severity:** P2, core navigation cost.
- **Evidence:** `src/components/SiteHeader.tsx:119–142` renders every league; `src/App.css:193–199` puts it in a vertically scrolling floating panel. `src/hub/HubPage.tsx:92–100` renders all sport groups without filters or jump links. The checked-in index contains 44 leagues. Every visit to a less prominent league requires scanning a large list, especially on a phone.
- **Suggestion:** Add a labeled search field matching full names, short names and sports; display sport filters or anchor chips; show a clear no-results state and result count. Retain ordinary links and current-page indication so this remains usable by keyboard and without a custom combobox implementation. Show both acronym and full league name in results.

### UXA-05 — Malformed team hashes are decoded without protection

- **Page / element:** Direct `#team=` links on cricket and shared sport pages.
- **Severity:** P2, resilient deep links.
- **Evidence:** `src/App.tsx:200` and `src/sport/SportPage.tsx:196` call `decodeURIComponent` on untrusted URL fragments without `try/catch`. `#team=%` throws `URIError` instead of being ignored. Cricket subsequently calls the same parser in a payload effect (`App.tsx:372–387`), outside the fetch error handler.
- **Suggestion:** Catch invalid percent encoding and treat it as an unknown team. Render the normal league with the default selection, keeping the original league query. Add a small regression case for malformed hashes and one for a valid percent-encoded team name.

### UXA-06 — Initial deep-link behavior is inconsistent across page families

- **Page / element:** Shared sport `#team=…` and section fragments; F1 section fragments.
- **Severity:** P2, browser verification required before calling this a production failure.
- **Evidence:** Cricket explicitly invokes its hash synchronizer after payload load (`src/App.tsx:385–387`). Shared sport selects the initial hash team at `src/sport/SportPage.tsx:213` but installs scrolling only for later `hashchange` events (`:260–273`); it never calls the synchronizer initially. F1 renders section targets after async loading but has no post-load fragment handling (`src/f1/F1Page.tsx:81–131`). Browser handling of an initial target inserted after fetch needs direct verification.
- **Suggestion:** Share a post-load fragment resolver that preserves path/query, ignores invalid/unknown fragments, selects a team when needed, and scrolls after the target exists. Verify fresh direct arrivals to EPL `#team=MCI`, EPL `#fixtures`, IPL `#team=RCB` and F1 `#constructors` on both hosting bases. Do not replace working same-page URLs with bare hashes.

### UXA-07 — Share Kit's return link goes to the landing page

- **Page / element:** `/share.html`, “Back to standings.”
- **Severity:** P2, incorrect navigation destination.
- **Evidence:** `src/share/SharePage.tsx:123` sets the href to `import.meta.env.BASE_URL`, while `src/Root.tsx:42–44` now sends that address to the landing page. The page already has the loaded IPL league identity.
- **Suggestion:** Link to `leagueHref(payload.league?.id ?? DEFAULT_LEAGUE_ID)` with `#standings` if appropriate, using a full path/query-safe URL. Keep the wordmark as the route home.

### UXA-08 — League-index failure silently changes the requested page type

- **Page / element:** Landing, hub and non-cricket league routes when `leagues.json` fails.
- **Severity:** P2, error-state clarity and recovery.
- **Evidence:** `src/Root.tsx:20–27` discards the index error. With no index, the root/hub fallback goes to cricket (`:43–55`); an explicit football/F1 route also falls through to the cricket component because sport routing depends on the missing index entry. ErrorState only offers a home link (`src/components/PageState.tsx:14–21`), which can repeat the same fallback. Cricket loading/errors omit SiteHeader entirely (`src/App.tsx:415–425`), unlike the other families.
- **Suggestion:** Give the index its own error state with Retry and a consistent header. Do not present IPL as the response to “all races,” and do not run a different payload parser for an explicit non-cricket route. Keep a known route/family mapping or retry the required index before rendering a league. Distinguish unknown league, temporary load failure and empty valid data in user-facing copy.

### UXA-09 — Distribution percentages can only be inspected with hover or assistive technology

- **Page / element:** Selected team finishing-position chart.
- **Severity:** P2, information access on the main phone audience.
- **Evidence:** `src/sport/SportPage.tsx:861–887` draws bars inside `aria-hidden`; each value is a `title` on a non-focusable span (`:871`). The equivalent list is visually hidden. The chart has no visible value axis, and the bar height is scaled against the team's peak (`:793`, `:872`). A sighted keyboard or touch user cannot reliably obtain an individual percentage.
- **Suggestion:** Add a visible data summary (“Most likely: 8th, 19%”) and a compact accessible disclosure/table for the full distribution, or an inspectable chart with visible selected values. Preserve the text equivalent. Label whether bar heights are relative or absolute. For 20–36 positions, do not create tiny unlabelled touch targets.

### UXA-10 — Position-zone meaning is carried by color, and table cutlines are hidden from readers

- **Page / element:** Current table zone stripes and finishing-position chart zones.
- **Severity:** P2, interpretation/accessibility.
- **Evidence:** `src/App.css:625–638` encodes first/top/middle/bottom places only as colored inset stripes. `src/sport/SportPage.tsx:430` marks cutline rows, including text such as “Split,” `aria-hidden`. Chart zone labels are likewise class names (`:869–874`) with no legend. Rank numbers identify position but do not explain which competition outcome the color represents.
- **Suggestion:** Show a compact textual zone legend and provide a row-level status or meaningful group/cutline description. Make informative cutline labels available to assistive technology. Keep both rank and written competition outcome so monochrome/forced-colors views remain understandable. Measure the neutral bars separately: `.position-bar.zone-none` uses the low-contrast border token (`SportPage.css:171–172`), so its rendered graphical contrast needs explicit verification.

### UXA-11 — Pre-season is counted and described as “in season now”

- **Page / element:** Landing live count and hub headline/section copy.
- **Severity:** P2, state accuracy.
- **Evidence:** `src/data/leagues.ts:54–56` defines live as anything except complete, while `statusLabel` separately recognizes pre-season. `src/landing/LandingPage.tsx:110` calls this count “in season now”; `src/hub/HubPage.tsx:90` says “Seasons in progress.” The index currently includes `nba-2026-27` with `started: false`, so the labels and the displayed state disagree.
- **Suggestion:** Either separate “Live” and “Pre-season” groups/counts or use “Current and upcoming seasons” for the combined scope. Preserve clear Pre-season pills and never imply results have already occurred.

### UXA-12 — Generic method copy incorrectly describes every sport as strength-rated

- **Page / element:** Landing “How the Odds Are Made.”
- **Severity:** P1, data-truth copy.
- **Evidence:** `src/landing/LandingPage.tsx:160–170` asserts a model rates each team from recent results and the remaining season is simulated tens of thousands of times. Cricket's exact solver enumerates remaining winner combinations (`extract_table.py:1063–1071`), and its Monte Carlo branch draws equal binary outcomes (`:1164–1169`); it does not share the football/F1 rating model. Even if every current cricket page is final, this copy is the explanation given to users before the next live season.
- **Suggestion:** Use a true common explanation, then distinguish “ratings-based forecasts” for football/US sports/F1 from “equal-chance qualification scenarios” for cricket. State the NRR limitation in the cricket explanation. Drive method names and counts from payloads wherever the explanation is league-specific. No model changes are needed.

### UXA-13 — Odds changes are described as standings points or lack units

- **Page / element:** Cricket rival impacts and shared-sport movers.
- **Severity:** P1, numerical interpretation.
- **Evidence:** `src/App.tsx:1193` says “adds X pts to … odds”; `:1211` says “costs X pts versus preferred result.” Here the values are changes in probability, while the same page uses “pts” for standings points. Shared sport movers format `+X.X` without any unit at `src/sport/SportPage.tsx:574–575`.
- **Suggestion:** Say “+X.X percentage points” or “+X.X pp” with a visible explanation, and reserve “pts” for standings. For a compact mobile example, use “Chance rises from 32% to 44% (+12 pp)” only when both endpoints exist in the real payload. Keep percent and percentage-point changes distinct.

### UXA-14 — Warnings and update promises need a consistent, truthful place

- **Page / element:** League status, timestamp and data notes.
- **Severity:** P2, confidence and content clarity.
- **Evidence:** Sport and F1 warnings are rendered only in the footer (`src/sport/SportPage.tsx:527–530`, `src/f1/F1Page.tsx:461–464`), while their main status can still say Live. Cricket has a top warning only for “stale”/“invalid” and otherwise relegates warnings to the footer (`src/App.tsx:439–441`, `:696`). Current payloads include missing-result warnings for La Liga/Eredivisie and table disagreements for Europa/Conference League. Cricket also promises “Updated daily after the night match” for every league (`App.tsx:693`), despite the documented twice-daily UTC schedule and global time zones.
- **Suggestion:** Place a compact, plain-language data note beside the table timestamp when a warning affects interpretation. Keep technical details expandable and sources credited below. Use “Updated twice daily” plus the actual local timestamp rather than promising synchronization with an unspecified night match. Distinguish live season status from live score updates.

### UXA-15 — Cricket abbreviations and model language are not explained where used

- **Page / element:** Cricket table, chance notes and selected-team path.
- **Severity:** P2, international/new-fan comprehension.
- **Evidence:** Cricket's table headers are plain `Pts` and `NRR` (`src/App.tsx:796–797`); the first probability note says “Probabilities exclude NRR simulation” (`:520`), and path copy includes “own-win guarantee,” “win buckets” and “material neutral fixture dependency” (`:234–236`, `:1199`, `:1232`). “Net run rate” is expanded much later in a final-team detail, without a short explanation of what positive/negative values mean (`:1078–1080`).
- **Suggestion:** Expand NRR in the header with an accessible explanation and a touch/keyboard-usable details link. Suggested short copy: “Net run rate: scoring rate minus opponents' scoring rate; it separates teams level on points.” Use “If they win N of their remaining games” for win buckets and “No rival result changes the chance much” for the empty impact message. Keep the exact-model caveat explicit: current NRR is displayed, future NRR is not forecast.

### UXA-16 — Share Kit status and images lack useful failure/text alternatives

- **Page / element:** Copy/export buttons and Reels slides.
- **Severity:** P2, designed action states and accessible content.
- **Evidence:** `src/share/SharePage.tsx:95–107` only records success/exporting, with no visible copy or export error. `src/share/sharing.ts:36–46` ignores the boolean return from the deprecated copy fallback, so it can claim success even if copying failed. `SharePage.tsx:218` uses generic “IPL … slide N” alt text for graphics whose actual information is not transcribed on the page; the manifest's “Pack note” is at least surfaced (`:205–206`).
- **Suggestion:** Add a live status message for Copied/Download started/Unable to copy, expose a selectable text fallback, and give export failure a retry path. Keep a visible preview of the exact caption that will be copied. If slides contain unique data, provide a short text description from real manifest content or a link to the corresponding accessible league data, rather than inventing image content.

## Existing strengths to preserve

- Real `<table>`, captions, column scopes and row headers are implemented across all three league families. Cricket/shared sport selection is a real button with `aria-pressed`; settled outcomes include hidden “yes/no” text.
- Tables scroll within `.table-scroll`. Full tier labels remain in the accessibility tree when abbreviated on mobile (`SportPage.css:57–70`), while optional columns deliberately disappear.
- Global `:focus-visible` styling and skip links are present (`src/index.css:212–237`). Minimum text tokens begin at 12px; no smaller page CSS font-size was found.
- `prefers-reduced-motion` disables CSS motion (`index.css:251–258`), and the shared scroll helper checks the preference (`src/lib/ui.ts:3–21`).
- Team-color text uses contrast-based black/white selection through `readableOn`; do not replace it with arbitrary feed-provided foreground colors.
- F1 already explains countback in ordinary language immediately below its table (`src/f1/F1Page.tsx:285`): race wins, then second places, excluding sprints. This should remain near the data.
- Pre-season, playoffs and final states exist. Cricket has helpful final-season summaries and explicit empty playoff/fixture text; these are assets to the redesign.
- The `samePageHref` helper and PageHeader preserve league query strings under GitHub Pages' `<base>` path. This is a behavior requirement, not a styling detail.

## Browser handoff / acceptance checks

The source audit does **not** certify rendered WCAG AA contrast or runtime behavior. The production matrix must measure actual composited glass surfaces in both themes and include the following:

1. 320/375px page width with no page-level horizontal overflow; wide tables scroll locally; standalone targets measure at least 44px.
2. Landing → hub → league → team on both hosting bases, plus browser Back/Forward, fresh team/section links, unknown team and malformed `%` team fragments.
3. Menu open/close, search if added, first/last item, Escape focus restoration and leaving the menu by Tab; verify current-page indication.
4. Team selection with pointer, Enter and Space, checking viewport, focus and selected-panel announcements.
5. Reduced-motion, 200% zoom, keyboard-only use and a screen-reader table pass; neutral chart bars and zone meanings in monochrome/forced-colors.
6. Delayed/failed index fetch, failed league fetch, empty valid arrays, no upcoming fixtures, pre-season NBA, mid-season EPL, postseason MLB/WNBA and completed IPL. Errors must explain recovery without silently changing the requested competition.
7. Share Kit copy success/failure, denied clipboard permission, PNG export failure, manifest failure and the return-to-standings destination.

Fixes above can be made entirely in frontend presentation, navigation and copy. They do not require new services, a runtime backend or altered probability models.
