# Live Cricket browser verification

This is scoped automation evidence for the implementation plan, rather than a claim of complete exploratory, manual screen-reader or production performance coverage. All browser contexts and tabs were created for this work. No subscription, provider account or user browser session was used.

The main affected-route matrix passed on 24 October 2026, 02:22–02:23 PDT. The three `*-verified` reports describe that local build. They precede the later isolated parent-score freshness gate and cricket-entry layout/preload repairs; the focused follow-up below records their narrower subsequent browser coverage. Earlier reports preserve failures and test corrections.

| Main matrix target | Browser cases | Checks | Contrast samples | Report |
| --- | ---: | ---: | ---: | --- |
| Free source, GitHub base `/ipl_top4_analysis/` | 12/12 passed | 156 | 460 | [Results](github-free-verified/results.json) |
| Free source, Cloudflare base `/` | 12/12 passed | 156 | 460 | [Results](cloudflare-free-verified/results.json) |
| Configured API, synthetic service replay | 12/12 passed | 132 | 568 | [Results](github-service-verified/results.json) |

All 444 checks and 1,488 sampled contrast comparisons passed. No case reported page overflow, undersized standalone controls, sub-12px text or unexpected browser console/page errors. Each free-source target also passed an unmodified direct-browser CORS probe: SportScore supplied 17 covered fixtures and a selected match detail, using two anonymous requests per target. The synthetic service matrix made no provider requests.

## Isolated follow-up

Final source review added a model gate for an overdue parent score, even when the prediction itself is freshly calculated against the same revision. The browser harness now has a focused `--parent-score-only` mode. It establishes a visible fresh baseline, withholds the estimate when parent `observedAt` is ten minutes old, repeats with absent `observedAt` and ten-minute-old `generatedAt`, then confirms recovery on a fresh parent snapshot. Model prediction, collection and outer observation clocks remain fresh in both stale-parent fixtures.

The completed follow-up passed **2/2 browser cases and all 8 focused checks**, limited to Chromium and WebKit at 375px in the light theme against the rebuilt configured-service output. No provider requests or unexpected console/page errors occurred. It does not repeat the earlier 36-case matrix or the earlier 48-case season regression. [Follow-up results](parent-score-followup/results.json) preserve the exact synthetic clock contract for each case. Example frames show withholding for [stale parent observation](parent-score-followup/chromium-375-light-synthetic-old-score-model-withheld.png) and [stale publication fallback](parent-score-followup/webkit-375-light-synthetic-old-score-publication-model-withheld.png).

## Scope and method

The new section is checked with Chromium and WebKit at 320, 375 and 1280px, in light and dark themes. The 320px free-source cases and all service-contract cases use reduced motion. The larger free-source cases exercise explicit field tilt. Source responses are fetched once in an unmodified anonymous browser and then replayed unchanged **in memory** across the matrix. Raw provider payloads are not written to this directory.

Service-contract tests intercept only the configured test API in an owned local browser. Every test team, bookmaker, probability, scorecard and delivery is visibly named synthetic. These cases establish UI behavior under controlled states; they do not establish real bookmaker availability or model accuracy.

The matrices cover source attribution and coverage wording, lower-fixture selection, focus and scroll position, Back, search state, direct selected bookmarks and reloads, canonical/Open Graph paths for both hosting bases, keyboard tabs, theme persistence, paused polling, quote status, independent event/prediction/quote clocks, source outage and recovery, and the optional flat/tilted field guide.

Geometry checks reject page overflow, standalone targets smaller than 44px, and visible text below 12px. Contrast samples use resolved foreground colors and alpha blending over opaque UI planes. Gradient/ambient page backgrounds and disabled controls are excluded. The samples complement visual inspection; they are not a blanket WCAG conformance claim.

## Runtimes and reproduction

Chromium uses the existing `/Users/Rakesh/gstack/node_modules/playwright` runtime (1.62.1). Its expected WebKit revision is not installed. WebKit uses the existing Playwright 1.58.2 runtime at `/Users/Rakesh/.npm/_npx/520e866687cefe78/node_modules/playwright`, matching installed WebKit 2248. No runtime or browser was installed.

Run against separately built static outputs; do not rebuild an output while a matrix is using it:

```sh
WEBKIT_PLAYWRIGHT_MODULE=/existing/compatible/playwright \
  node scripts/verify_live_cricket.mjs http://127.0.0.1:5193/ipl_top4_analysis/ github-free

WEBKIT_PLAYWRIGHT_MODULE=/existing/compatible/playwright \
  node scripts/verify_live_cricket.mjs http://127.0.0.1:5195/ cloudflare-free

# This output must be built with a local VITE_LIVE_CRICKET_API_URL origin.
WEBKIT_PLAYWRIGHT_MODULE=/existing/compatible/playwright \
  node scripts/verify_live_cricket.mjs http://127.0.0.1:5194/ipl_top4_analysis/ service --service

# Narrow model parent-score follow-up only.
WEBKIT_PLAYWRIGHT_MODULE=/existing/compatible/playwright \
  LIVE_VERIFY_BROWSERS=chromium,webkit LIVE_VERIFY_WIDTHS=375 LIVE_VERIFY_THEMES=light \
  node scripts/verify_live_cricket.mjs http://127.0.0.1:5194/ipl_top4_analysis/ parent-score-followup --parent-score-only
```

The script also accepts `LIVE_VERIFY_BROWSERS`, `LIVE_VERIFY_WIDTHS` and `LIVE_VERIFY_THEMES` for a bounded reproduction. Use a fresh label to preserve prior evidence. Scripts and JSON report timestamps are UTC; captures show the browser's America/Los_Angeles display times.

## Findings and rechecks

The first six-family regression passed all 48 executed cases: landing, hub, football, cricket season, F1 and Share, at 320/1280px in both themes and both browsers. Chromium's first report also records an initial unavailable default WebKit executable; the separate compatible-runtime WebKit report contains the 24 successful WebKit cases. These broad regression checks preceded the isolated Live Cricket repairs and were not silently claimed to have been rerun afterward.

Confirmed findings were sent to the implementation owner, who made the product repairs. This verification task did not edit application code.

| Finding | Evidence | Recheck |
| --- | --- | --- |
| Native WebKit filter selects rendered 23px high despite `min-height:44px` | `github-free/results.json`, WebKit geometry checks | Explicit 44px height passed in both final free-source base matrices and service matrix |
| Selecting a lower fixture left the new match center above the viewport | Implementation owner's separate browser reproduction | Heading focus and visibility passed in both final free-source matrices |
| Retained bookmaker quotes still said current after a 503 outage | `github-outage-repro/results.json` | All 12 `github-service-final` cases passed the outage quote gate |
| Browser Back focused the lobby heading outside the viewport | `github-free-final/results.json`, `cloudflare-free-final/results.json` | Passed all 24 `*-free-verified` cases; selected and lobby headings are focused, visible and clear of the sticky header after settled history restoration |
| Fresh outer model observation time masked an old `model.predictedAt` | `github-service-final/results.json` | Passed all 12 `github-service-verified` cases; prediction clock and score revision are tested independently |

The initial `github-service` report includes an incorrect expected display label (`In progress` rather than `Live`); this was a test assertion error, not a product defect. The first free-source runs also used an ambiguous attribution locator and assumed Safari mouse clicks focus buttons. Later tests scope the attribution to the actual section and exercise focus with keyboard Enter. Those earlier failures are preserved rather than relabelled as product failures.

`visual-free` and `visual-service` contain a small additional capture pass of the already verified flows. The script now records viewport frames: tall element screenshots can paint a sticky header halfway through a captured element, which is a capture artifact rather than the actual page composition. Representative frames are retained in the repository; duplicate captures are archived as recorded in `capture-archive.json`. All JSON reports, including pre-fix failure evidence, remain intact.

Representative frames: [real free-source lobby](visual-free/chromium-1280-dark-real-lobby.png), [phone field guide](visual-free/chromium-375-dark-real-field-guide.png), [synthetic phone scorecard](visual-service/chromium-375-dark-synthetic-scorecard.png), [synthetic retained prices during an outage](visual-service/chromium-1280-dark-synthetic-outage.png). The retained visual passes also passed all four browser cases; they are additional evidence, not added to the 36-case matrix totals above.

## Limits

These local checks do not prove continuous free-feed coverage, worldwide completeness, bookmaker entitlement, statistical calibration, a provider update SLA or a deployed production revision. Free source snapshots may include no active matches. Unavailable scorecards, commentary, model output and prices are checked for honest presentation; they are not replaced with invented data.

The real-source probe did not establish live coverage of rain/DLS changes, super overs or an active multi-day Test. The synthetic contract matrix covers one labelled T20 match and the listed UI failure/freshness states; it does not substitute for provider-specific cricket edge-case validation.

The browser matrices make no Lighthouse claim. Separate measured lab runs are documented in [the performance report](performance/README.md); they do not establish real-user INP. No manual assistive-technology pass or factual spatial replay is claimed. The field diagram is illustrative CSS/SVG, with an equivalent readable text legend. Final release/deployment checks remain the release owner's responsibility.
