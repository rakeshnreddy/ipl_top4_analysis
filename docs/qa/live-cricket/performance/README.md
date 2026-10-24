# Live Cricket loading checks

Local cold-load lab measurements on 24 October 2026, using Lighthouse 13.5.0 and existing Chromium. Each run used Lighthouse's default simulated mobile profile: 412×823px, 4× CPU slowdown, 150ms RTT and approximately 1.6Mbps throughput. Reports retain exact settings, timestamps, request chains and layout-shift elements. The free provider was accessed anonymously; no test market or model was substituted.

| Hosting base | Performance before → after | LCP before → after | CLS before → after | Final TBT |
| --- | --- | --- | --- | --- |
| Cloudflare `/` | 80 → 97 | 2.63s → 2.35s | 0.333 → 0.040 | 8ms |
| GitHub `/ipl_top4_analysis/` | 78 → 98 | 2.66s → 2.32s | 0.350 → 0.040 | 2ms |

Reports: [Cloudflare before](cloudflare-mobile.json), [Cloudflare after](cloudflare-mobile-after.json), [GitHub before](github-mobile.json), [GitHub after](github-mobile-after.json).

## Investigation

**Symptom:** the initial mobile load moved visible content and exceeded the plan's loading/stability targets.

**Root cause:** the static attribution footer was initially painted above an empty React root, then displaced by the loading shell and the full page. Lighthouse attributed 0.292 of Cloudflare CLS to that footer. The live route and heading font were also discovered after the main JavaScript executed.

**Fix:** the dedicated cricket entry reserves at least one viewport for the root before first paint. Its build plugin emits early hints for the known live route, its stylesheet and the two initial text fonts. Other page families remain lazy. Source changes are confined to `cricket/index.html` and `build/live-cricket.ts` in the frontend package. The scope-lock helper was unavailable; this file boundary was followed manually.

**Evidence:** paired before/after cold loads on both generated bases. The footer no longer contributes to CLS in either final report. The remaining 0.040 comes from the source coverage note appearing above the workspace. Both final runs satisfy the plan's LCP ≤2.5s and CLS ≤0.1 targets. No further loading optimization is justified by these measurements.

**Regression probe:** rebuild the relevant base and run the existing Lighthouse CLI against its `/cricket/` entry, preserving a new JSON output. Inspect measured LCP/CLS and the `layout-shifts` audit, rather than only the aggregate score. All emitted local asset/preload URLs must resolve under the chosen base.

**Status:** DONE for the two local lab targets. No production, percentile or real-user performance claim.

## Limits

These are single paired lab runs on local static previews, not repeated statistical estimates or production measurements. Provider response time, device load, hosting compression and cache behavior can change real results. Loading checks do not measure INP; TBT is a lab indicator, not a substitute for real interactions. The [Web Vitals reference](https://web.dev/articles/vitals) defines good field LCP, CLS and INP and explains the difference between lab and field results. Real-user INP and manual assistive-technology testing remain unmeasured.
