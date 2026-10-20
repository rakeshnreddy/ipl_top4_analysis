# Independent static league-page review

Reviewed 2026-10-19 against `codex/night-signal-league-pages`, implementation `925a4a2` and follow-up `de79ac2`, in `/Users/Rakesh/Projects/pp-redesign-league-pages`. Application sources were reviewed read-only. The reviewer changed only `scripts/verify_redesign.mjs` at the release coordinator’s request and wrote this evidence report.

No remaining blocking finding was confirmed in the reviewed static-page sources. Final integration and production verification remain release gates: this branch began from the foundation release, before the separate page-family releases.

## Findings and verified repairs

| Page / element | Severity | Evidence and resolution |
| --- | --- | --- |
| Normal league navigation | P1, resolved | Initially, normal links still opened `?league=…`, so copying the browser address missed the generated social preview. `leagueHref()` now emits `/league/<id>/`; legacy query parsing remains. The independent Chromium canonical harness passed six cases, checking all 44 menu destinations against the published index, performing a real menu navigation, returning with Back, and preserving the exact original path, query and fragment. |
| Initial source snapshot | P2, resolved | The source table is now inside `<noscript>` outside the empty React root. JavaScript-enabled visitors do not briefly see a second page/header. This is a factual JavaScript-free fallback plus a client-rendered application, rather than React SSR or hydration. The recorded mobile Lighthouse CLS is 0. |
| F1 fallback | P2, resolved | The initial fallback omitted constructors. Both driver and constructor tables now render real standings and probabilities. Independent JavaScript-disabled checks found both tables on both hosts in both themes at 320px. |
| Fallback controls and wide tables | P2, resolved | Navigation/data links and the notes summary now measure at least 44px high. Wide tables have named, keyboard-focusable scroll regions, captions, column scopes and row-header scopes. All 16 independent JavaScript-disabled phone cases passed their DOM, target, semantics and overflow checks. |
| Canonical EPL load performance | P2, resolved in sampled lab run | The initial LCP was 2.841s. Its LCP element was the page heading; the delay came from main script → index → route module → payload → display font discovery. Route/module/CSS, JSON and font preloads lowered the same local mobile Lighthouse sample to 2.292s. An independent JavaScript-enabled request probe observed one index request and one payload request, with no duplicate requests or unused-preload warnings. |

## Metadata, files and data truth

Both final compiled builds were scanned independently: 44 league HTML documents and 44 raster social cards per host. Every document has one absolute canonical, one league-specific OG image, `summary_large_image`, matching JSON-LD WebPage/Dataset URLs, the correct payload download URL and the payload’s own timestamp. All PNG headers confirm 1200×630. Each sitemap contains 46 locations: the root, hub and 44 canonical league paths.

Cloudflare addresses use `/`; GitHub addresses retain `/ipl_top4_analysis/`. Generated data and image URLs use the corresponding host/base. App section/team interactions now require exact pathname and query retention, closing the previous harness blind spot where a canonical link could accidentally return to the site root and still pass a base-prefix check.

Snapshot facts are derived from the full payload instead of cached index fact strings. Completed seasons have final titles and actual champion names; zero-game seasons do not invent a standings leader. Simulation estimates use the existing safe formatter. The artifact scan found no simulated `100%` in active-season tables. Payload warnings are visible in the fallback, including the current EPL notice about four past fixtures without results. The data timestamp is a snapshot timestamp, not a claim that a source is continuously live.

Source HTML escapes display text and JSON-LD, uses validated league IDs and fixed `data/<id>.json` paths, and does not introduce runtime hosting or external fonts/scripts. Social rendering uses existing self-hosted font files and a build-only dependency.

## Accessibility and manifest

The source fallback uses opaque white surfaces in either system theme. Its text `#17212b` and links/focus colour `#456500` have calculated contrast of 16.29:1 and 6.74:1 against white. The independent no-JavaScript checks covered EPL, F1, completed IPL and pre-season NBA, both hosts, light/dark, at 320px. Tables stayed inside their scroll regions; no horizontal page overflow was found. JavaScript-enabled canonical checks ran actual axe. The JavaScript-disabled checks used direct rendered-DOM, target and semantic checks; axe depends on script timers and was not used to claim no-JavaScript coverage.

The manifest has base-relative scope/start URL and local 192/512px, maskable and Apple-touch icons. No service worker, offline cache, tracker, paid service or new key was introduced. This does not promise offline odds or an install prompt on every platform. Ordinary browser and social-provider caching still applies; production preview checks must inspect the dated card rather than assume a third-party cache has refreshed immediately.

## Performance evidence and limits

| Local Lighthouse 13.5 mobile sample | Performance | FCP | LCP | CLS | TBT |
| --- | ---: | ---: | ---: | ---: | ---: |
| Canonical EPL before preloads | 92 | 2.200s | 2.841s | 0 | 10.5ms |
| Canonical EPL after preloads | 96 | 1.842s | 2.292s | 0 | 0ms |
| Root after font preloads | 98 | 1.442s | 2.167s | 0 | 0ms |

These are single local simulated mobile runs, not production p75 measurements. The static preloads apply to canonical league paths; old query URLs remain supported but cannot receive different server HTML per query on static hosting. The final merged build still needs page-family measurements and deployment checks.

An independent Chromium Event Timing probe at 4× CPU, 375×812, exercised menu opening/search/Escape, theme toggle, two table-team selections and keyboard page scrolling. The maximum recorded event duration was 168ms (theme toggle); menu opening reached 104ms, typed search 32ms, and table selections 40ms. The probe records event counts and durations with a 16ms threshold and browser quantization. It is lab interaction-latency evidence, **not field INP**, and cannot establish the user’s p75 INP target without field telemetry.

## Evidence

- [Artifact scan and both-host metadata checks](../screenshots/verification-static-independent-source/artifacts.json)
- [Six independent canonical Chromium cases with axe and 44-link checks](../screenshots/verification-static-independent-source/canonical-github-results.json)
- [Sixteen JavaScript-disabled phone cases](../screenshots/verification-static-independent-source/source.json)
- [F1 JavaScript-free phone screenshot](../screenshots/verification-static-independent-source/gh-dark-nojs-320.png)
- [Writer’s separate 24-case browser/base/width matrix](../screenshots/verification-static-independent-source/writer-final-matrix.json)
- [Canonical Lighthouse before](../performance/static-canonical-before.json), [after](../performance/static-canonical-after.json), [root after](../performance/static-root-after.json)
- [Independent 4× CPU Event Timing and preload-reuse probe](../performance/static-interaction-lab.json)

Release follow-up: run legacy and canonical matrices on the final combined build on both bases; verify the separate Share Kit’s return links after integration; confirm production canonical pages, sitemap, images and manifest return the intended files; then record production performance without representing synthetic TBT or these event samples as field INP.


## Integrated release follow-up — 2026-10-20 UTC

Read-only source review of final static commit `2162d35`, rebased onto the combined page-family releases and nightly data `6774576`, confirmed no new blocking issue. The original single-run measurements above describe the earlier branch, not this final integration.

The root-only hint helper now selects Landing, Hub, or an allowlisted published league family. It accepts only the deployment root or its `index.html`; canonical and Share documents omit the helper. It normalizes a league ID, checks own-property membership, preserves league precedence over `view=hub`, and leaves unknown IDs alone. Root/Hub hints include the index without guessing a league payload. Static import traversal does not preload unrelated dynamic page families. Hrefs remain same-origin and base-relative; the helper changes neither location nor history and deduplicates existing links. An independent isolated-DOM check against both final compiled hosts passed 24/24 root/Hub, conflicting-query, invalid-ID, path, origin and duplicate-link cases. Earlier independent checks cover 58 built-helper guards and seven real browser request-reuse cases; those earlier runs preceded the root/Hub extension.

The final Share performance repair removes only Share's manifest link. Root and canonical league entries retain installation metadata, and no service worker or stale odds cache is added. The trial heading/font change was fully reverted, so typography and slide provenance are unchanged. A controlled local Lighthouse comparison repeated Share LCP at 2.568/2.567s with the manifest link and 2.422/2.420s without it. Inspection found the additional manifest/icon request chain, rather than duplicate font or payload downloads: the first 58KB preview, index, payload and carousel manifest each had one request. This supports the measured contention improvement; it does not establish field p75 performance or explain every difference from the earlier standalone 2.273s sample.

The writer's final latest-data mobile Lighthouse samples were root 2.423s, Hub 2.261s, EPL query 2.409s, IPL canonical/query 2.265/2.261s and F1 canonical/query 2.262/2.259s. Share's two manifest-off samples scored 97 with CLS 0 and TBT 6.5/0ms. These are local simulated mobile results. Share has roughly 80ms of margin below the 2.5s lab target, so production measurement remains a release gate rather than a guarantee of real-user LCP.

The separate already-deployed Share release passed an independent 24-case Chromium production matrix at `https://ipl-playoff-pulse.pages.dev/`: six page families, 375/1280px and both themes, with actual axe. All four Share cases loaded and decoded all 11 previews at 720×1280 before full-page screenshots. That run used retained query URLs and preceded the static deployment; it does not replace final production canonical/base checks.

Additional evidence:

- [Final root/Hub built-helper checks, 24/24](../screenshots/verification-legacy-preload-independent/root-hub-guards.json)
- [Earlier helper guard checks, 58/58](../screenshots/verification-legacy-preload-independent/guards.json)
- [Earlier real browser request probes, 7/7](../screenshots/verification-legacy-preload-independent/browser.json)
- [Share production matrix, 24/24, with decoded gallery diagnostics](../release/share-production.json)
