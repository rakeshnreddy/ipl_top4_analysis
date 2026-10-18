# Playoff Pulse site analysis and redesign

Audit and baseline: 18 October 2026. Production: [Cloudflare](https://ipl-playoff-pulse.pages.dev/) · [GitHub Pages mirror](https://rakeshnreddy.github.io/ipl_top4_analysis/).

## Multi-agent analysis

Three independent read-only workers covered nine lenses in parallel, followed by a separate completeness pass. Their full reports preserve source evidence and distinguish observations from unverified hypotheses:

1. [Visual/brand, information design and inspiration](audits/visual-data-inspiration.md).
2. [UX/navigation, accessibility and content](audits/ux-accessibility-content.md).
3. [Performance, SEO/shareability and frontend code](audits/performance-seo-code.md).
4. [Completeness critic](audits/completeness-critic.md).

The site already has substantive advantages: real league rules, semantic tables, careful season-odds rounding, self-hosted fonts, honest model notes and distinct final-season views. The problem is presentation hierarchy: almost every surface receives the same green glass treatment, six football headlines occupy the landing feature, and a long unfiltered menu stands between fans and their league. Preserve the statistical work and make its consequences more immediate.

## Rendered baseline

Captured all six page families at 375, 768 and 1280px, in both themes: 36 production screenshots plus per-page browser logs in `screenshots/before/`. First impression: competent and readable, but every region has similar weight. The landing headline and large empty hero space dominate; the six textual race rows are less distinctive than the product deserves. On league pages, compact titles and properly aligned odds already work well.

![Before: landing at 1280px in dark theme](screenshots/before/landing-dark-1280.png)
![Before: football at 375px in light theme](screenshots/before/football-light-375.png)

## Priorities and disposition

| Priority | Finding | Resolution target |
| --- | --- | --- |
| P1 | Fixture segments clamp small outcomes to 6%; cricket tracks clamp even zero to 2%. Numbers and geometry disagree. | Exact tracks, external labels; no model changes. |
| P1 | Some 36/40px controls violate the owner's 44px requirement. | Shared control foundation, verify actual boxes. |
| P2 | Generic query-page metadata prevents league-specific social previews. | Static path-based HTML/content, data-backed social PNGs; retain query compatibility. |
| P2 | All page families load eagerly; full initial JS is 82.0 KiB gzip rather than only the 62.7 KiB shared chunk. | Lazy page-family imports and compare total initial transfer. |
| P2 | Uniform glass/green treatment has weak hierarchy and repeated mobile blur cost. | Night Signal, solid data planes, selective blur, sport identity. |
| P2 | Forty-four-entry menu and hub have no search. | Searchable picker with keyboard focus return; sport/search hub filters. |
| P2 | Position distributions have no visible scale and hide exact values behind hover. | Label scale and expose the values for touch/keyboard. |
| P2 | Landing copy claims every sport has strength ratings, labels pre-season as in progress, and calls priority-ordered features “biggest”. | Describe model differences, use honest active/featured language, spread sports. |
| P2 | Malformed team hashes can throw; fresh hydration hashes need browser checks; Share Kit back route goes to landing. | Shared safe hash handling and route-correct navigation. |
| P3 | Loading is a spinner; stale graphic context and sport-specific identity need polish. | Static skeletons, archive dates, F1 points-gap context and per-family refinements. |

## Direction comparison

Three genuinely different visual studies were rendered on real production screens/data: **Night Signal** (ink/citron/selective glass), **Season Ledger** (warm paper/editorial serif/open rules), and **Race Control** (coral/squared timing boards/condensed capitals). Each has 20 screenshots: five page families × two widths × two themes. See [direction specification](audits/visual-data-inspiration.md#three-distinct-visual-directions), the CSS in `design-directions/`, and the scores in [DESIGN.md](../DESIGN.md).

![Night Signal study](screenshots/directions/night-signal/landing-dark-1280.png)
![Season Ledger study](screenshots/directions/season-ledger/landing-dark-1280.png)
![Race Control study](screenshots/directions/race-control/landing-dark-1280.png)

Night Signal wins on evening use and recognisable multi-sport character. The final direction borrows disciplined data rules from Ledger and controlled sport accents from Race Control. Typography stays self-hosted Barlow Semi Condensed + IBM Plex Sans; no new font family download.

## Baseline measurements

A mobile Lighthouse 13.5.0 run on the primary production landing returned **performance 98, accessibility 96, LCP 1.8s, CLS 0, TBT 0ms**. The exact settings/environment and audit failures are in [before.json](performance/before.json). This is lab evidence, not field Core Web Vitals or an INP measurement. Initial production JS: 75,862-byte entry + 202,794-byte preloaded runtime/shared module, 84,014 bytes combined local gzip (82.0 KiB). The comparison uses total initial JS, not only the largest chunk.

## Delivery and evidence

Foundation and each page family ship as separate logical PRs, based on refreshed main, with local checks and independent reviews before each merge. Production evidence and final measurements will be recorded here after the actual deployment; pending work is not a pass.

## Next steps retained from the owner

- What-if outcomes in a worker or from the payload's conditional splits; no runtime server.
- Persist compact timestamped odds history before adding title-race timelines.
- Share Kit coverage beyond cricket.
- Cookieless analytics only after the owner enables Cloudflare Web Analytics in the dashboard.
- AFL and NRL before March 2027; rugby needs try counts absent from the current feed.
- Verify WBBL season discovery and summer cricket, current NBL/A-League finals assumptions, and the NWSL final venue per season.

No paid service, API key, DNS/dashboard change or publishing outside this site is part of this rollout.
