# Live Cricket implementation

Verified locally on 24 October 2026, America/Los_Angeles. Branch: `codex/live-cricket`. The live website has not been changed by this work.

## Delivered scope

The separate `/cricket/` entry works with both Cloudflare's root base and the GitHub Pages `/ipl_top4_analysis/` base. Season Odds retains its existing pages and models. Live Cricket provides a searchable, filterable fixture lobby, selected-match bookmarks, source status and available scores. Match centers support independently timed scorecards, commentary, model estimates and bookmaker prices when those parts are supplied. Empty, stale and interrupted parts retain explicit labels rather than invented values.

Polling pauses in hidden tabs and can be paused by the reader. Refetches preserve the selection, filters and focus. Explicit match selection and Back reveal the appropriate heading below the sticky header. Corrections can lower scores; commentary updates are accepted explicitly. Theme persistence, keyboard navigation, phone layouts and reduced motion are supported.

The optional field guide uses a readable flat SVG with user-enabled CSS 3D tilt. It explains field positions; it does not claim to replay actual tracking data. It loads separately from the match's core information.

## What the free source currently supplies

The default browser adapter uses SportScore's keyless public API with its required visible, crawlable attribution. The verified anonymous snapshot contained **17 upcoming fixtures**, including a matching detail response. It contained no active match at that moment. The same source also succeeded through the local native Worker runtime.

This establishes a working integration for covered fixtures, supplied totals and source state. It does not establish every cricket match worldwide, a freshness SLA, full batting/bowling cards or a ball stream. The UI preserves missing capabilities. Provider collection time is not presented as the time of the last ball. See [SportScore developer documentation](https://sportscore.com/developers/) and its [API terms](https://sportscore.com/developers/terms/).

There is no verified keyless bookmaker source. The optional service includes an Odds API adapter with conservative event matching and a shared free-credit budget. It remains disabled until an authorized free key, current display rights and exact competition scopes are supplied. Optional CricketData and Sportmonks adapters also remain disabled pending actual account access and redisplay verification. No account, trial, purchase or authenticated provider request was made. [Service setup and limits](../services/live-cricket/README.md).

## Model status

The season qualification solver is not reused as a match-win model. A separate T20 chase research candidate was fitted and evaluated chronologically on local Cricsheet data. Its held-out Brier score is 0.1227 versus 0.1609 for the declared resource baseline, across 1,042 matches. These are research results, not a public accuracy claim.

The candidate remains `research_only`: the women's sample gate and several competition gates fail, independent model review and live replay are outstanding, and the free feed lacks required verified inference inputs. Public probabilities therefore remain unavailable. [Method, evaluation and release gates](../live_model/README.md).

## Verification

| Check | Result |
| --- | --- |
| Frontend unit/component tests | 148 passed |
| Python suite, including model tests | Passed; 313 tests, 1 skipped |
| Service unit / native Workers runtime tests | 22 / 9 passed |
| Frontend lint, TypeScript and both hosting builds | Passed |
| Service types, typecheck and Wrangler dry-run | Passed; no upload |
| Final affected browser matrices | 36 cases, 444 checks passed |
| Subsequent parent-score freshness browser recheck | 2 cases, 8 checks passed |
| Sampled composited contrast comparisons | 1,488 passed |
| Earlier legacy page regression | 48 cases passed |
| Mobile Lighthouse, Cloudflare / GitHub bases | 97 / 98; LCP 2.35s / 2.32s; CLS 0.040 each |

Browser coverage includes Chromium and WebKit, 320/375/1280px, both themes, selected deep links, lower-fixture navigation and Back, pause/resume, independent prediction/quote clocks, outages and recovery. Free-source data were anonymously verified and replayed unchanged in memory. Service UI tests use visibly synthetic contracts; they establish behavior, not actual bookmaker coverage or live model validity. [Detailed evidence and limits](qa/live-cricket/README.md).

The [loading investigation and reports](qa/live-cricket/performance/README.md) document the measured entry-page repair and lab limitations. No production revision, continuous provider coverage, real-user INP or manual screen-reader pass is asserted. Detailed keyed adapters require authorized real-source samples before activation.

## Local review and next release

Run the frontend from `frontend/ipl-analyzer-frontend` with `npm run dev`, then open `/cricket/`. Leave `VITE_LIVE_CRICKET_API_URL` unset for the free direct adapter. To review the coordinated backend locally, follow its README and set that public variable to its local origin. Provider credentials never belong in a frontend variable.

The static free-source section can be released through the existing frontend deployment flow. Backend provisioning and optional keyed-source activation are separate steps with their own configuration checks. No deployment has been run here.

The [multi-sport roadmap](designs/live-sports-roadmap.md) recommends football, then basketball, then tennis. It defines common event/provenance infrastructure while preserving sport-specific scoreboards, market settlement rules and validated models. Other sports are planned, not implemented.
