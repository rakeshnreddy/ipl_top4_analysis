# Playoff Pulse: performance, SEO and frontend architecture audit

Audit date: 18 October 2026. Scope: read-only inspection of README.md, DESIGN.md, frontend source, build/deploy configuration, published Cloudflare and GitHub Pages HTML, response headers and live Cloudflare JS/CSS assets. Browser screenshots, Lighthouse and rendered contrast are owned by the main audit and are deliberately not duplicated here. No source changes, dependency installs or development servers were made by this auditor.

## What matters first

The static data architecture is a good fit for this product. It already avoids a runtime backend, trackers, third-party fonts and chart-library overhead. The largest opportunities are to deliver the right document before JavaScript, remove the serial data-loading dependency, and let a visitor download only the page family they open. The redesign should preserve this architecture.

The current main JavaScript budget is larger than the brief's shorthand suggests: the shared preloaded JS alone is about 63 KiB gzip, while **all initial JS totals 82.0 KiB gzip**. Use the total as the comparable before/after budget.

## Measured asset baseline

These are actual production Cloudflare assets fetched on the audit date, with local gzip compression for a reproducible size comparison. They are not claims about browser transfer encoding or Lighthouse timings. The checkout's existing `dist` was built on 4 October and was not used as the JS baseline.

| Production asset | Raw bytes | Local gzip bytes |
| --- | ---: | ---: |
| `main-BrITCQOy.js` | 75,862 | 19,836 |
| Preloaded `standings-DTxTt_11.js` | 202,794 | 64,178 |
| **Initial JS total** | **278,656** | **84,014** |
| `main-DwgX5NJ5.css` | 15,175 | 2,906 |
| `standings-Y_yjpBq1.css` | 26,556 | 5,762 |
| **Initial CSS total** | **41,731** | **8,668** |

The three main Latin WOFF2 font files total 91,940 bytes: IBM Plex Sans variable 45,712; Barlow Semi Condensed 600 22,984; Barlow 700 23,244. Actual font requests depend on the glyphs and weights on screen; non-Latin/extended subsets can add requests. `@fontsource` uses `font-display: swap` and `unicode-range`, which are useful existing safeguards. There are no font preloads in `index.html`.

Representative checked-in data sizes, measured from current `public/data`, rather than browser transfer:

| Payload | Raw bytes | Local gzip bytes | Relevant shape |
| --- | ---: | ---: | --- |
| League index | 21,546 | 2,143 | 44 published leagues |
| EPL 2026–27 | 129,148 | 13,141 | 315 fixtures, 65 results |
| IPL 2026 | 20,964 | 2,028 | Completed-season page |
| F1 2026 | 33,055 | 5,695 | Drivers, constructors, events |
| MLB 2026 | 545,376 | 32,055 | 2,461 results; UI shows latest ten |
| NHL 2026–27 | 408,010 | 28,428 | 1,210 fixtures; UI shows next ten |

Cloudflare correctly returns `Cache-Control: public, max-age=31536000, immutable` for hashed JS and `public, max-age=300, must-revalidate` for the league index. The GitHub mirror returns its platform cache policy, `max-age=600`. Font and gallery assets are self-hosted. Share gallery images already specify dimensions, `loading="lazy"` and `decoding="async"` (`src/share/SharePage.tsx:217`).

## Structured findings

Severity: P1 = directly breaks a requested product/quality outcome; P2 = meaningful improvement or confirmed design risk; P3 = optional maintenance or polish. Performance risks below are source-supported candidates for measurement, not invented Core Web Vitals failures.

| ID | Page / element | Severity | Evidence | Suggested change |
| --- | --- | --- | --- | --- |
| SEO-1 | Every league / initial document and link preview | P1 | Raw HTML for `https://ipl-playoff-pulse.pages.dev/?league=epl-2026-27` and the equivalent GitHub mirror URL contains the generic site title/description and `<div id="root"></div>`. It contains no league title, table or JSON-LD. `index.html:6` initially canonicalizes to the root; `SportPage.tsx:226`, `App.tsx:395` and `F1Page.tsx:99` correct tags only after payload loading. | Generate distinct static league documents with league-specific title, description, canonical, JSON-LD and useful visible content. Keep legacy query links working. Do not describe DOM-injected metadata as a static preview fix. |
| SEO-2 | All pages / missing social image | P1 | Neither `index.html` nor `src/lib/seo.ts:26` declares `og:image`, `twitter:image`, image dimensions or image alt text. Existing carousel PNGs are cricket-specific and are not referenced by league metadata. | Generate a 1200×630 PNG per league at build time from its actual payload: league/season, update date and a small selection of real headline odds. Add absolute image URL, dimensions, alt text and `summary_large_image`. Include a general site image for landing/hub. |
| SEO-3 | Primary and mirror / canonical identity | P2 | `appBaseHref()` and each page's canonical use `window.location.origin`; each mirror page therefore self-canonicalizes. The HTML initially declares a different root canonical before JS changes it to the league. `SITE_URL` currently controls only sitemap generation. | Separate asset base from canonical site origin. Emit a consistent canonical in static HTML and the enhanced client, using Cloudflare as the declared primary. Mirror asset URLs must still honor `/ipl_top4_analysis/`. |
| PERF-1 | Landing, hub and all leagues / eager page code | P2 | `Root.tsx:2–9` statically imports cricket, generic sports, F1, landing and hub. There are no `React.lazy` or dynamic imports anywhere in the current view routing. All five page families contribute to the initial app bundle, even on the landing page. | Use dynamic imports with a shared, stable fallback; keep React and common primitives shared. Start loading the requested view in parallel with its data rather than adding a new serial wait after the index. A raw SVG bar does not need Chart.js. |
| PERF-2 | League entry / serial data requests and two loading screens | P2 | `Root.tsx:18–40` waits for `loadLeagueIndex()` to settle before mounting a family page. Those pages start their payload requests only in `useEffect` (`App.tsx:329`, `SportPage.tsx:207`, `F1Page.tsx:81`). `LoadingState` is a centered spinner. `cache: 'no-cache'` in data loaders requests revalidation despite the five-minute CDN freshness window. | Bootstrap the league index from generated HTML; preload the known league JSON, or fetch index and requested JSON concurrently with memoized promises. Use a stable page-header/table skeleton. Retain explicit freshness dates and a retryable error state. |
| PERF-3 | Hub and long league pages / repeated backdrop blur | P2, measurement required | `--glass-blur:18px` (`index.css:61`) applies to every `.panel`, key-facts strip and sticky header; every `.hub-card` separately blurs the backdrop (`HubPage.css:29`), and the menu uses 24px. There is no mobile blur reduction or `@supports` fallback. | Keep the intended depth through translucent fills, borders and restrained shadows. Limit live backdrop blur to the header/menu or a small number of major surfaces. Profile long-table scrolling on a throttled phone before claiming it passes INP. Do not animate blur. |
| PERF-4 | First screen / font discovery | P3 | Three Latin fonts can cost about 92 KB before compression; they are discovered through CSS and all are imported globally in `src/fonts.ts`. Their existing swap/subset behavior is sound. | Retain self-hosting. Preload only a measured critical WOFF2, if the waterfall justifies it, and reuse that exact URL/crossorigin mode. Consider a single display weight or a smaller single-family system if the chosen visual direction gains nothing from both display weights. Verify layout stability after font swapping. |
| CODE-1 | Cricket, sports and F1 / repeated document/data lifecycle | P2 maintenance risk | Page families separately implement fetch/active guards, loading/error wrappers, SEO construction, JSON-LD graphs, status mapping, source footer and date formatting. The files are 1,256, 942 and 471 lines. Existing behavioral drift: cricket's initial loading/error returns no `SiteHeader`, while sports/F1 retain one; cricket clears errors on successful reload but sports/F1 do not. | Extract a small `useLeaguePayload` lifecycle accepting initial data, a shared `PageFrame`, a common SEO metadata builder, and common loading/error scaffolding. Keep sport-specific standings, playoff rules and schemas distinct. This also makes true prerendering practical. |
| CODE-2 | Site-wide redesign / CSS ownership | P2 maintenance risk | `App.css` is 1,144 lines and contains the frame/header/table system alongside cricket deep-dive, playoff and Share Kit styles. It is imported by every page family. Sports add 459 lines; F1 adds 139. The correct token system already exists in `index.css`. | Divide CSS by stable shared primitives and page family, with one source for each table/panel/control. Route-level CSS then follows dynamic imports. Avoid a new parallel stylesheet that keeps overriding old rules. Preserve the existing 12px scale and 44px control tokens. |
| DATA-1 | Generic sport fixtures / outcome-bar geometry | P2 | `SportPage.tsx:612` sets each width to `Math.max(value*100,6)`. The actual Conference League fixture `2050402` has a 0.7% away chance, which is assigned 6% width before flex shrinking. Across checked-in payloads, 112 fixture outcomes are below 6%. A chart whose geometry changes to fit labels no longer faithfully encodes the payload. | Keep segment widths proportional to the actual values. Place labels in a separate row or text legend; show tiny segments without forcing a minimum percentage. Preserve the existing accessible text equivalent. |
| DATA-2 | Generic sport fixtures and selected-team next games / rounding edge case | P2 latent defect | `SportPage.tsx:606,617,905–907` uses `Math.round(probability*100)` rather than the bounded `formatChance()`. A 99.6% modeled fixture chance would print `100%`, and 0.4% would print `0%`. No current fixture payload crosses those bounds, so this is an implementation edge case, not a claim of a currently visible false certainty. | Reuse the shared odds formatter with the correct scale conversion. Check both the visible labels and accessible descriptions. Add a narrow boundary regression for the explicitly required no-false-100% contract. |
| PWA-1 | Mobile home-screen entry / missing manifest and app icons | P3 | `public` has only an SVG favicon; `index.html` has no manifest link or Apple touch icon. There is no service worker. | Generate a base-aware web manifest plus 192px/512px maskable icons and a touch icon. This can remain fully static. Treat offline cached odds as a separate feature requiring visible freshness handling. |

The canonical inconsistency is more than a stylistic preference: Google's guidance recommends a canonical in HTML and cautions against changing it to another value through JavaScript. Google can render JavaScript, so it would be inaccurate to claim that these league pages are categorically unindexable; other crawlers may see only the initial shell. See [Google's JavaScript SEO guidance](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics). The [Open Graph protocol](https://ogp.me/) identifies `og:image` among its four basic required properties and supports explicit image alt text and dimensions.

## Static generation feasibility

### Per-league HTML: feasible, moderate refactor

The necessary data is already in `public/data`, and `build/sitemap.ts` demonstrates reading the league index in a Vite build plugin. Emit one document per published league, for example `/league/epl-2026-27/index.html`, plus the landing and hub documents. There is no need for a server, paid service, data-model change or external API.

**Important routing constraint:** a static file host serves the same root file for all `?league=` query values. A build cannot attach 44 different HTML heads to one root file without a runtime request handler. Distinct paths solve this; retain `?league=` as a compatibility entry and teach `Root` to resolve both query and path IDs. Keep `samePageHref()` for every in-page link, and verify both root and GitHub subpath builds.

A metadata-only generated shell is a useful limited first step but does not prerender the odds/table. True content prerendering requires initial payload/index props or a pure presentation layer: current state initializes to `null` and server rendering would produce the loading screen. Inject the build data safely, use the same snapshot for hydration, and update it from canonical JSON after mount only when needed. Keep time-dependent fixture cutoffs and localized date strings deterministic on the server, then localize after hydration to avoid mismatches. Avoid embedding full MLB result history in HTML when the visible page only needs a small snapshot.

Recommended build contract: one pure metadata function per payload family, reused by static generation and the client; one canonical origin separate from `BASE_URL`; static JSON-LD containing truthful dates/source credits; sitemap entries that point to the new canonical paths; old query, hash and team links still resolve. The workflow already performs one build per deployment base, so generated paths/assets can follow that existing split.

### Per-league Open Graph images: feasible, low-to-moderate effort

Use local fonts and the same summary data used by the hub. A Python image generator can fit the existing social-asset workflow without adding browser-side JS. An SVG-to-PNG build tool is another option if already available. Do not require image-generation services for deterministic text, logos or numbers. Generate images for all payload families, including F1 constructors/drivers and cricket finals/preseason states. Include the update date in the composition and consider versioned image URLs to avoid stale preview caches. The resulting assets are requested by preview crawlers and do not increase initial page JS or require an on-screen hero image.

### PWA: feasible, low effort for manifest/icons

A local web manifest can provide name, display mode, colors, launch URL and icons; ensure `start_url`, `scope` and `id` follow the deployment base. The [web.dev manifest guide](https://web.dev/articles/add-manifest) documents the required metadata and common icon sizes. Browser-specific installation UI should be verified separately rather than inferred from a manifest's presence.

If offline support is added later, cache hashed UI assets separately from odds JSON, retain the last successful update date and visibly label cached/offline data. Do not silently replay stale probabilities as current, and do not precache every social PNG or all 44 historical payloads on installation. A manifest/icons enhancement can ship without committing the product to offline odds behavior.

## Acceptance checks for the redesign

1. Compare total initial JS and CSS for landing, hub, cricket, sport and F1 against the production baseline above. Report both the app chunk and all preloaded/deferred chunks; count only requests actually needed by that route.
2. Use the main audit's same Lighthouse configuration before/after. Report LCP and CLS as lab results. Lighthouse does not prove real-user INP; exercise menu opening, theme toggling, team selection and long-table scrolling with a performance trace or event timing.
3. Fetch generated league pages without executing JavaScript on both deployment bases. Assert a unique title, stable canonical, absolute social image, matching JSON-LD and real league content.
4. Verify legacy `?league=`, `?view=hub`, section links and `#team=` links in a browser with `<base href>` active. Check reduced motion and both saved themes.
5. Keep exact proportional bars, the existing bounded probability formatter and explicit non-color states when the new visuals are applied.

Useful existing foundations to preserve: self-hosted fonts, hashed immutable assets, short JSON freshness windows, real tables, accessible chart equivalents, `readableOn()` for team-color text, `samePageHref()`, scoped table overflow, reduced-motion support, separate noindex Share Kit, and data-backed daily sitemap generation.
