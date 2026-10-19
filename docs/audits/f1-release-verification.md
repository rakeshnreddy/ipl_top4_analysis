# F1 release verification

Verified 2026-10-19 against application commit `f0ee5c2`, rebased onto `6ecef1d`, using the GitHub-base production build at `http://127.0.0.1:5221/ipl_top4_analysis/?league=f1-2026`.

The release coordinator regenerated WPL/the league index and ran all 300 Python tests before this frontend pass: successful, with two skips. Regeneration left the release checkout unchanged. The independent frontend pass ran all 84 Vitest tests with one worker, ESLint and `build:github`; all passed.

## Hub integration refresh

On 2026-10-19, merged published `origin/main` at hub release `1581bdb` into this branch using merge commit `ccf2bab`; no history rewrite. Regenerated with `extract_table.py --league wpl-2026`: WPL and the regenerated league index were unchanged. All 300 Python tests passed (one skip); all 87 frontend tests passed with one worker; lint and GitHub build passed.

Chromium and WebKit again passed all four combinations of 375/1280px and light/dark, including actual axe, overflow/text/target checks, real section navigation, menu search/Escape focus and theme persistence. No browser failures were recorded.

- [Post-hub Chromium results](../screenshots/verification-f1-post-hub/results.json)
- [Post-hub WebKit results](../screenshots/verification-f1-post-hub-webkit/results.json)
- [Post-hub phone, light](../screenshots/verification-f1-post-hub/chromium-f1-375-light.png)
- [Post-hub phone, dark](../screenshots/verification-f1-post-hub/chromium-f1-375-dark.png)
- [Post-hub desktop, light](../screenshots/verification-f1-post-hub/chromium-f1-1280-light.png)
- [Post-hub desktop, dark](../screenshots/verification-f1-post-hub/chromium-f1-1280-dark.png)

The local performance sample below predates this hub-only integration and remains explicitly labelled by its application commit. Final canonical-page and production performance are separate release checks.

## Browser evidence before hub integration

Chromium and WebKit each passed all four combinations of 375/1280px and light/dark. The harness ran actual axe, checked text/target sizes, page overflow and browser/network errors, clicked a section link while preserving the league query/base, exercised menu search and no-results state, restored focus with Escape, and checked theme persistence through reload. No confirmed failures were recorded.

- [Chromium results](../screenshots/verification-f1-final-rebased/results.json)
- [WebKit results](../screenshots/verification-f1-final-rebased-webkit/results.json)
- [Phone, light](../screenshots/verification-f1-final-rebased/chromium-f1-375-light.png)
- [Phone, dark](../screenshots/verification-f1-final-rebased/chromium-f1-375-dark.png)
- [Desktop, light](../screenshots/verification-f1-final-rebased/chromium-f1-1280-light.png)
- [Desktop, dark](../screenshots/verification-f1-final-rebased/chromium-f1-1280-dark.png)

## Local performance sample

A single Lighthouse 13.5 simulated mobile run on this local built page recorded:

| Metric | Result |
| --- | ---: |
| Performance score | 96 |
| First contentful paint | 1.666s |
| Largest contentful paint | 2.575s |
| Cumulative layout shift | 0.00057 |
| Total blocking time | 13ms |

[Full Lighthouse JSON](../performance/f1-final-rebased.json).

LCP **missed the 2.5s target by 75ms** in this sample. The LCP element was the real page strap describing six remaining races and 20,000 simulated seasons. This release does not include the separate static canonical-page preloads, so their improvement must be measured after integration rather than assumed. The earlier F1 sample was 2.540s; these two local runs do not establish a production percentile.

The Vite build reports the entry script at 1.83kB gzip, shared application chunk at 61.25kB gzip, and lazy F1 route at 4.66kB gzip. These are build estimates, separate from total transferred page resources.

This verification does not establish field INP, screen-reader usability, every synthetic data state, or production caching/deployment health. Refresh the evidence after the hub merge and final combined static build, and verify the deployed page before claiming the overall performance target is met.
