# Completeness critic: Playoff Pulse redesign

Read-only review on 18 October 2026 of the complete owner brief and the three parallel audit reports: `visual-data-inspiration.md`, `ux-accessibility-content.md` and `performance-seo-code.md`. This critic did not change application code, data, configuration or deployment state. The findings describe gaps in the evidence reviewed so far; they do not imply that later build/verification work has already failed.

## Verdict

The audits cover all nine requested lenses, identify real defects and correctly distinguish source evidence from rendered proof. The strongest risks are now clear: truth in chart geometry and method copy, missing static previews, state accuracy, navigation resilience, and the cost of making every panel glass. The remaining danger is to call the source audit complete visual verification, or to ship one attractive landing screen while overlooking the many league states and the mirror's base path.

**The redesign is not ready for a completion claim on these reports alone.** Required real-screen direction comparisons, measured before/after evidence, cross-browser checks and staged deployment proof remain work to perform and record.

## Required coverage still to make concrete

| Requirement | Coverage already in the audits | What must exist before the corresponding phase is called complete |
| --- | --- | --- |
| Multi-agent analysis and synthesis | Three independent workers cover visual/data/research, UX/accessibility/content, performance/SEO/code. | Synthesize, deduplicate and prioritize them in `docs/site-analysis.md`; link screenshots and this completeness review. Retain source-vs-rendered confidence labels. |
| Visual analysis of every page type | Source-based visual findings and three direction specifications exist. | Before screenshots of landing, hub, football, cricket, F1 and Share Kit at 375, 768 and 1280px, light and dark; include an NFL view and relevant special table/bracket views. Inspect 320px for overflow as an extra quality check. |
| Three genuinely different directions | Night Signal, Season Ledger and Race Control have palettes, typography, surfaces, motion and scorecards. Scores are explicitly provisional. | Render each direction on the five specified families—landing, football, cricket, F1 and hub—at phone and desktop width using real payloads. That is at least 30 distinct page renders; verify both themes across the selected real screens. Changing only colors on one layout does not substantiate three directions. Re-score from the actual images. |
| Final design decision | A direction is recommended, with sensible borrowing from the others. | Rewrite `DESIGN.md` around the implemented winner: complete light/dark tokens, sport accents, table/chart semantics, motion fallbacks, interaction rules, state designs and measured contrast pairs. A palette proposal is not an AA certificate. |
| Logical staged delivery | Audits suggest shared primitives and family ownership. | Foundation PR, then page-family PRs on branches based on current `origin/main`, merged sequentially after all required checks. Shared CSS edits need one clear owner. Link each resulting PR and deployment; attach created PRs to the chat. |
| All page states | Many state defects are identified; current live examples are available for some states. | An explicit state-by-family verification matrix, including delayed/failed fetch and empty-valid-data cases, with screenshots or behavioral evidence. Some states are inapplicable to some families; say so rather than inventing an F1 playoff state. |
| Accessibility | Source audit identifies targets, focus, labels and color semantics. | Rendered composited contrast in both themes; keyboard and screen-reader passes; 44px standalone targets; 12px text floor; zoom/reflow and reduced motion. An automated accessibility score alone cannot prove these. |
| Performance | Production JS/CSS sizes and source risks are measured. | Matching before/after Lighthouse runs and artifacts, route totals rather than one chunk, mobile scrolling/interaction evidence and an honest account of INP limits. Do not certify real-user INP from a Lighthouse score or TBT. |
| Static sharing | Architecture and missing metadata/images are well documented. | Fetch distinct generated league documents without JS on both deployments; inspect league title, canonical, JSON-LD, image URL/alt/dimensions and meaningful league content. Confirm new links reach these paths while old query/hash links still work. |
| Ship and prove | Release rules are supplied by the owner. | Full checks before every commit; green CI before merge; successful GitHub Pages deployment and actual Cloudflare “Deployment complete” log evidence; then production screenshots and live route checks on both hosts. A green build or successful HTTP status alone is insufficient. |

## State and sport cases most likely to be missed

The current checked-in index has **24 in-progress, 2 postseason, 1 preseason and 17 complete** seasons. The preseason entry is NBA 2026–27; MLB and WNBA are postseason. This is useful state diversity, but every currently published cricket league is complete. A tour of today's public cricket pages cannot verify the redesigned in-season odds, goal tabs, own-win buckets, mover summaries, fixture impacts or the pre-season opening-match treatment.

| Family / state | Representative evidence to use | Specific risk to check |
| --- | --- | --- |
| Landing/hub, mixed season states | Current 44-league index; search returning zero results; all-current/all-final fixtures if needed | Counts and prose agree: upcoming does not mean “in season now”; search/filter changes do not destroy normal links or current-page indication. “Featured” does not claim a closest-race ranking without one. |
| Football midseason | EPL 2026–27 | Table-first phone hierarchy, points versus chance grouping, team selection/focus/hash, distribution inspection, fixtures and conditional swing units. |
| Football with data notes | La Liga, Eredivisie, Europa League, Conference League | Missing-result/table-disagreement warnings remain visible beside the update and data; “Live” never conceals a source warning. |
| Scottish split | Current Scottish page plus existing split test data | Top-six/bottom-six separation, textual split/cutline meaning, a play-off tier with `skip`, no accidental resort that reunites the halves. |
| Grouped cricket | T20 Blast 2026 | Multiple tables, group captions/headings, group qualification explanation, retained group ordering, no page overflow. |
| Cricket live/preseason/playoffs | Existing historical or test fixtures through an explicitly labeled development fixture harness | Exact/equal-chance wording, NRR limitation, real zero/tiny probability geometry, qualification controls and paths, postponed/no-result handling, settled-versus-estimated outcomes. Do not edit production JSON to fabricate a live season. |
| Cricket complete | IPL/WPL 2026 | Final table, champion, recap, playoff journey and archived Share Kit context remain designed and functional. |
| NFL/groups | NFL 2026 | League/conference/division controls, seed/rank labels, optional stats, cutoffs, long names and 44px tabs. An EPL-only generic-sport check does not cover this. |
| Basketball preseason | NBA 2026–27 | Zero played games, projected odds, correct Pre-season label, no fabricated form/movers/results. |
| Postseason | MLB and WNBA 2026 | Bracket scores/series, unknown participants, settled regular-season ticks, title estimates, remaining fixtures and eliminated teams. |
| F1 | F1 2026, plus complete/empty fixtures | Drivers and constructors, retired/replaced drivers, race versus sprint counts, podium favorites, countback explanation and actual points gap. No implied total remaining points without scoring-rule data. |
| Share Kit | Current completed IPL and archived May pack; separate failure harness | Visible archive date, accurate return-to-standings link, no stale “today” claim, copy/export/manifest failures, slide text alternatives, noindex and image loading behavior. |
| Shared loading/error | Delayed index; failed index; failed/malformed league payload; valid empty sections | Header and route remain stable, Retry works, no silent change from a football/F1/hub request into the cricket parser, no unhandled malformed hash. |

Fixture-harness screenshots should be clearly labeled as test states. Production proof should use the deployed real data. This distinction permits thorough state testing without displaying fabricated odds to fans.

## Claims that need qualification or reconciliation

1. **Severity needs one synthesis scale.** Minimum-width bars are P1 in the visual/data report and P2 in the technical report. Both establish the same defect. Deduplicate it and assign one final severity based on the owner's data-truth bar rather than count it twice.
2. **“63 KB main JS” is not total initial JS.** The live preloaded shared file alone gzips to 64,178 bytes; the initial main file adds 19,836. Use 84,014 bytes total as the before baseline, keeping the same gzip method after. A smaller renamed app chunk is not proof of a lighter page if more chunks are immediately requested.
3. **Blur is a supported risk, not a measured failure.** Many 18px layers justify a focused phone trace, but no report yet proves a specific dropped-frame count, LCP failure or INP regression. Keep those claims conditional until measured.
4. **Existing chart-library dependencies do not prove chart-library bundle cost.** The packages are listed in `package.json` but no current page imports them. Do not attribute the bundle size to Chart.js without module evidence.
5. **Google indexing is not equivalent to non-JS previews.** The raw shell confirms weak crawler-independent league identity, and changing root canonicals is an avoidable inconsistency. It does not prove that Google has failed to index all leagues. Static content/metadata fixes should still be verified with raw fetches.
6. **Metadata-only HTML is not a full odds prerender.** It can fix a new URL's preview but still contains no table. The shared pages currently start with null payloads; true content generation needs an initial-data contract or presentation layer. Do not label a fallback spinner a prerendered league page.
7. **Existing `?league=` previews cannot vary by static query.** New file paths are needed for distinct HTML on plain static hosting. Old query URLs must still work, but a client redirect does not retroactively give their initial responses league-specific metadata for non-JS preview crawlers. Share new canonical links and document this compatibility limit.
8. **Fixture labels currently have no false `100%` example.** Their `Math.round` implementation is a real boundary risk, but the technical/data audits correctly found no current fixture crossing 99.5%. Preserve that qualifier; add boundary verification rather than invent a visible production failure.
9. **Design scores are judgments.** The paper-led option totals 55/60 and Night Signal 54/60; choosing Night Signal for expressed owner taste is a coherent decision. Explain it and replace provisional beauty scores with inspection notes from real renders.
10. **Competitive research is partial by design.** Opta, Apple documentation, F1, 538 data documentation and Premier League navigation were inspected. FBref and ESPNcricinfo were blocked and The Athletic was not inspected. Do not imply a full visual comparative audit of those products. A source's documentation verifies a pattern, not its current performance.
11. **Contrast ratios must describe the rendered new system.** `DESIGN.md`'s old ratios do not certify new alpha surfaces, sport accents, probability fills, selected rows or source warning treatments. Measure the actual foreground/background pair at the brightest underlying field location in both themes.
12. **A manifest is a capability addition, not proof of all PWA behavior.** Check icons, scope and launch routes on both bases. Do not claim offline freshness, install prompts on every browser or push notifications if only manifest/icons were added.

## Data-truth guardrails for the chosen visuals

- Use structured numerical payload fields. Hub `facts[].value` is human-readable prose; do not parse percentages out of it to manufacture chart data. If the hero needs structured probabilities, derive a compact build snapshot from the real league payload.
- Keep percentages and percentage-point changes distinct. Current standings points, F1 championship points and model probability deltas are three different quantities.
- Preserve the model distinction: football/team sports and F1 have ratings-based forecasts; cricket's current qualification engine has equal-chance scenarios, exact enumeration where feasible, and explicit future-NRR limitations. Rewriting the design must not turn scenarios into claimed strength forecasts.
- Render zero as zero-length; keep small segments proportionate; do not smooth discrete finishing places. An adaptive distribution scale needs an explicit maximum and must not imply equal peaks mean equal probabilities.
- Do not invent history from one snapshot/change, imply a fixture bar is a season forecast, or draw bracket feed relationships that the data does not encode. Mark unresolved participants clearly.
- Distinguish mathematically settled tick/label outcomes from simulated near-certainty. Preserve the no-false-100% formatter and apply the right scale conversion for fixture fractions.
- A new title favorite, champion card or F1 gap must remain derived from the loaded payload. Before/after screenshots taken across an automatic data update may show different numbers; record `generated_at` and attribute the change accurately.
- Keep source/licence credits visible, including Cricsheet's ODC-By credit and configured sport sources. A footer redesign must not drop them.

## Cross-host and navigation verification

Run this on the Cloudflare root build and the GitHub `/ipl_top4_analysis/` build. A development server at `/` does not test mirror compatibility.

1. Land directly on a league with section/team hashes; select a team, change goal/group, open another league, then Back/Forward. Include malformed `#team=%`, unknown team and unknown league IDs.
2. Click every shared section-link pattern while on `?league=` and any new `/league/.../` path. Inspect the resulting URL: the selected league and deployment prefix must remain present. Use `samePageHref()` rather than bare hash links under `<base>`.
3. Toggle both themes, reload, open Share Kit and follow a league link. Test both an existing `pp-theme` choice and no choice. Initial HTML and new generated documents must apply saved theme before paint.
4. Verify search/disclosure focus, Escape return, no-results copy, and focus after team-detail activation. Retain ordinary anchors for destinations.
5. Fetch generated HTML, JSON, fonts, icons, OG images and manifest from both hosts. A root-absolute `/social/...` or `/data/...` URL can work on Cloudflare and fail on the mirror. Canonical origin and asset base are separate concepts.
6. Verify Share Kit's Back to standings reaches the actual IPL league, old `#reels` links still reach the kit, and clipboard/download actions produce usable feedback.

## Scope and authorization boundaries

The owner has already authorized implementation, branches, commits, PRs, merges and both existing site deployments. Routine reversible development should continue without check-ins. Their explicit exceptions remain: new paid services/API keys, Cloudflare dashboard or DNS changes, publication outside these sites, and deleting data require asking first.

No audit repair requires those exceptions. Static HTML/OG generation, base-aware manifest/icons, native SVG/CSS charts, self-hosted existing fonts and local search all fit the current static build. Avoid adding a runtime service to fix previews or a third-party tracking script. Cloudflare Web Analytics is an explicitly dashboard-dependent backlog item; report it as such, do not silently enable it. All-sport Share Kit, persistent odds history, a scenario tool, AFL/NRL and the feed/format follow-ups remain explicit backlog items unless deliberately delivered as additional logical units.

The owner's list of visual techniques is conditional (“where they add clarity or delight”). It does not require adding every animation API. Supported View Transitions, container queries and color mixing can be progressive enhancements; navigation, numbers and theme must work without them. New local font downloads are not a paid-service exception, but adding font families should earn their bytes. Keep the tight-disk rule: reuse/symlink existing `node_modules` in extra worktrees and clean only task-created temporary profiles/downloads. Do not remove existing user files or cached source data as housekeeping.

## Evidence packet the final owner report should point to

- `docs/site-analysis.md` with prioritized, deduplicated findings and links to the source audits/critic.
- Direction comparison board/screens, provisional-versus-final score notes and implemented `DESIGN.md`.
- Frozen before screenshots and deployed after screenshots for every page family in both themes, with matching viewport, route, timestamps and payload-update dates. Add the 768px audit views and 320px overflow results to the detailed evidence.
- Lighthouse JSON/HTML artifacts for identical before/after configurations, plus route JS/CSS totals and explicit limits of the INP evidence.
- A compact rendered-contrast table with pair, theme, surface/state and ratio; keyboard, reduced-motion, mobile overflow, screenshot and console results.
- State/special-format matrix, raw static-metadata assertions and cross-host/deep-link results.
- PRs, CI runs, deploy runs, Cloudflare completion-log evidence and final live links. Tests must cover the actual changed build/source, not an earlier branch snapshot.
- Explicit next steps for anything deferred. Do not describe the entire brief as fulfilled while required direction renders, per-family implementation or production proof remain absent.

This can be completed within the owner's authorized site scope. The next decision is execution and evidence discipline, not another permission round.
