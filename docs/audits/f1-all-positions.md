# F1 championship position forecasts

Local verification on 30 October 2026. This report describes the release candidate; deployment confirmation is recorded separately by the release workflow.

The default **All positions** view shows each driver's exact end-of-season championship position, P1 through the full field, and the equivalent constructor matrix. The current published season includes 23 championship drivers and 11 constructors. Drivers who have lost their seats retain their points and position distributions. The **Standings** control retains the points, wins, podiums and title/top-three summaries. On phones, scroll each table horizontally; participant names stay visible. Completed seasons show actual final standings and hide the forecast control.

The existing pace, car-development, driver-drift and retirement model still simulates 20,000 seasons. Each simulated championship's complete ranking now contributes to a position histogram. `analysis.positions` and `analysis.constructorPositions` contain percentages, index 0 meaning exactly P1. Every entrant and every position sum to 100% before two-decimal rounding. The current rounded payload differs from 100% by at most 0.02 percentage points. Existing title and top-three outputs use the same ranked trials. The generated `f1-2026.json` and league index were rebuilt through `venv/bin/python extract_table.py --league f1` using the existing free Jolpica source, with no source warnings.

Simulated countback compares all race finishes exactly, including both constructor cars; sprint finishes do not enter countback. Fully identical race records split randomly because qualifying tiebreaks remain unmodelled. The published model notes identify the old title/top-three backtests as historical; individual position probabilities have not been independently backtested or calibrated. No new accuracy guarantee is claimed.

Missing, incomplete, non-finite or wrongly normalised distributions are marked unavailable. Zero sampled finishes use the existing dash convention, with explicit text explaining finite sampling and rounding. Near-certain simulations keep the existing `>99.9%` formatting. Source HTML includes every F1 position on both hosting bases, using the same pure validator as the interactive page.

## Verification

- Python: 318 tests run, 1 skipped; Formula 1's 31 tests passed. Seven new backend regressions failed before implementation.
- Frontend: 211 tests in 26 files; lint, TypeScript and both hosting builds passed. New UI/validator and static-source tests failed before the corresponding implementation.
- Independent mathematical review checked lexicographic countback against 1,000 direct randomized comparisons and verified both-car constructor indexing. A 20,000-trial, 23-driver, 11-team, 29-event benchmark took 1.35 seconds with about 205 MiB peak process memory; it does not establish browser or production timing.
- Direct browser regression: 24 cases across Chromium/WebKit, both bases, 320/375/1280px and both themes passed 648 checks. Completed, legacy and malformed snapshots passed 23 additional checks.
- Settled-theme follow-up: eight WebKit cases passed, including actual theme toggles. Minimum sampled composited contrast was 5.81 in light mode and 6.83 in dark mode. These settled measurements supersede an initial transition-time screenshot and detached-canvas sampling concern.
- Updated mobile Lighthouse lab runs: root and mirror builds scored 97, with LCP 2.418/2.415s, CLS 0.029 each, and TBT 32/0ms. The earlier production reference scored 99, LCP 1.969s, CLS 0.029 and TBT 19ms. The reference used the public origin and the candidate used local previews, so these are not a controlled same-origin regression comparison. TBT is not real-user INP.

An initial mirror preview omitted its repository base, causing local asset errors. The preview configuration was repaired and all 12 mirror cases were rerun successfully; no deployed source repair was needed. Original failed/setup and transition evidence is retained separately. Installed gstack QA wrappers/templates were incomplete, so this is direct scoped evidence rather than full formal QA certification. No manual screen-reader assessment, continuous monitoring, production revision or real-user performance is established by these local checks.

## Screenshots

[Before: phone](../screenshots/f1-all-positions/before-phone.png) · [Before: desktop](../screenshots/f1-all-positions/before-desktop.png)

[After: phone](../screenshots/f1-all-positions/after-phone.png) · [After: desktop](../screenshots/f1-all-positions/after-desktop.png)
