# F1 independent visual review

19 October 2026. Candidate: `e47a2ff` plus foundation merge `0de3de2`. Compiled preview: `http://127.0.0.1:5221/ipl_top4_analysis/?league=f1-2026`.

**PASS.** Independently inspected eight rendered screenshots: the page top and points-gap section at 375px and 1280px, each in light and dark. The two-column championship layout remains readable at desktop; the phone view stacks the tables and shows four driver rows in its first screen. Points, title odds and constructor identity remain easy to distinguish. No visible overlap or escaped page overflow was found. This review does not certify measured contrast or real-user performance.

Browser evidence:

- All four viewport/theme cases reported `document.documentElement.scrollWidth <= innerWidth`.
- Reload, rendering and section navigation produced zero console errors and zero uncaught page errors.
- Clicking **Points gaps** preserved `?league=f1-2026` and the GitHub Pages subpath.
- Fresh navigation to `?league=f1-2026#gaps` placed the section at 71.8px, below the sticky header.
- The leader's gap bar measures **0px**, with a visible numeric zero.
- The current payload's driver gaps are ANT 0, RUS 102, HAM 111, VER 119 and LEC 125. Constructor gaps are MER 0, FER 134, MCL 239, RBR 246 and RB 478. These equal the leaders' actual points minus each displayed competitor's points. They are current standings, not simulated outcomes.

No blocking finding remains. A non-blocking refinement is to label the plots “Leading five”; the current plots intentionally show five entries rather than the entire field. Their exact values and “shorter is closer” text already explain the measurement.

Evidence directory: `docs/screenshots/f1-independent/`.

| View | Light | Dark |
| --- | --- | --- |
| Page, 375px | [light](../screenshots/f1-independent/f1-review-light-375.png) | [dark](../screenshots/f1-independent/f1-review-dark-375.png) |
| Page, 1280px | [light](../screenshots/f1-independent/f1-review-light-1280.png) | [dark](../screenshots/f1-independent/f1-review-dark-1280.png) |
| Gaps, 375px | [light](../screenshots/f1-independent/f1-gap-review-light-375.png) | [dark](../screenshots/f1-independent/f1-gap-review-dark-375.png) |
| Gaps, 1280px | [light](../screenshots/f1-independent/f1-gap-review-light-1280.png) | [dark](../screenshots/f1-independent/f1-gap-review-dark-1280.png) |
