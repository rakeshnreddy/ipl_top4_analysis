# Foundation independent review

18 October 2026. **No unresolved blockers in the final reviewed foundation diff.** Earlier review findings were repaired by the lead implementer and rechecked. This is a read-only specialist review using the gstack-review checklist, not a claim that this worker ran the complete release workflow.

## Scope and method

Read the full foundation diff and its consumers: theme tokens and HTML theme colors, shared App.css, SiteHeader, PageState, lazy Root routing, the updated landing tests, and the neutral distribution-bar fix. Applied the gstack-review checklist's safety, value completeness, error-path completeness and frontend checks. SQL, persistence, model and shell-injection categories have no changed runtime code in this diff. No application fixes, commits, unrelated files or model changes were made by this reviewer.

## Findings resolved during review

| Finding | Severity | Final evidence | Result |
| --- | --- | --- | --- |
| Lazy route rejection could escape Suspense and leave no UI | P1 | `src/Root.tsx:64–74`: RouteBoundary surrounds Suspense and renders an ErrorState. An isolated rejected-import probe against the actual Root rendered “This page could not load” and “Reload this page,” with zero uncaught root errors. | Resolved |
| Reload action initially used a same-document URL, which is insufficient on fragment deep links | P2 | `src/Root.tsx:70` passes `onRetry={() => window.location.reload()}`; `src/components/PageState.tsx:24` renders a real button. `src/App.css:68` gives that button a visible accent treatment and 44px minimum height. | Resolved |
| Changing theme action label conflicted with the added pressed state | P2 | `src/components/SiteHeader.tsx:24–26` now has stable accessible name “Dark theme” and `aria-pressed` reflecting the active theme. Existing persistence test was updated for the intentional accessible-name change. | Resolved |
| Neutral distribution bars used a border color below graphical contrast requirements | P1 | `src/sport/SportPage.css:171–172` now uses `--text-subtle`. On the new opaque panel surfaces, contrast is **6.35:1 light** (`#506175` / `#ffffff`) and **7.50:1 dark** (`#9eafc1` / `#151e28`), exceeding 3:1. | Resolved |

The review also confirmed that shared section links, segmented controls, menu rows, race-bar selectors and share actions now use the existing 44px tap token rather than their former 36/40px values. Search has an explicit label, an empty-result status, focus on opening and Escape restoration to the trigger. Native links and `aria-current` remain intact. The new loading geometry is hidden from assistive technology while the polite loading status remains available.

## Verification results

- **25/25 focused tests passed:** `npx vitest run src/landing/LandingPage.test.tsx src/hub/HubPage.test.tsx src/App.test.tsx`. This includes the new search/empty-state/Escape-focus regression and the updated theme persistence contract.
- **Rejected-import probe passed:** an isolated temporary Vitest fixture mocked the selected lazy page import to reject. The actual Root error boundary displayed recovery copy, with `onUncaughtError` count `0`. React's expected caught-error diagnostic was emitted by this deliberately injected failure; it is not a healthy-page console regression. Reload invocation itself was checked in source, not a simulated jsdom navigation.
- **Screenshot evidence inspected:** the captured football dark 375px screen and the lead capture logs under `docs/screenshots/foundation/`. The logs contain **36 viewport/theme captures**, zero page overflow flags, zero visible text-under-12px flags, and no console errors across all six page logs. These logs cover 375, 768 and 1280px in light/dark; they do not establish 320px behavior or WebKit behavior.
- **Representative text token contrast calculations:** light subtle text on surface-3 5.29:1; dark 5.75:1; light good text on good-soft 5.09:1; light accent on its soft surface 5.95:1. These deterministic solid-pair checks do not replace the lead auditor's rendered translucent-surface checks.

## Scope limits

This worker did not rerun the complete Python suite, lint, both deployment builds, Lighthouse, production verification or WebKit. Those remain part of the lead's merge/deploy gate. The lazy loading change introduces a request waterfall (index, selected view, then its payload), so its performance outcome must be judged from the measured before/after results rather than assumed from bundle splitting alone. No performance regression is asserted without that measurement.

The broader UX/accessibility findings in `ux-accessibility-content.md` remain the page-family redesign backlog; they are not newly introduced foundation regressions. The new `light-dark()` fallback and sport-accent selectors remain progressive presentation behavior, and their legacy-browser appearance is not certified here.

**Recommendation:** ship the foundation once the lead's full required checks pass; the final independently reviewed source has no unresolved foundation defect identified by this pass.
