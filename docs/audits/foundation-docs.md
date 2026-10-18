# Foundation documentation audit

18 October 2026. Independent, read-only documentation pass using the gstack-document-release coverage and cross-document consistency checklist. Reviewed README.md, rewritten DESIGN.md and docs/site-analysis.md against the complete foundation diff and the relevant existing page/model consumers. Only this report was edited by the reviewer.

**Status: factual documentation corrections requested before calling the documentation current.** The implementation review found no unresolved foundation blocker; this pass found existing README inaccuracies and ambiguity between implemented foundation behavior and planned page-family requirements.

## Required corrections

| Document / evidence | Finding | Required correction |
| --- | --- | --- |
| `README.md:30`; `extract_table.py:1144–1149,1164–1169`; football/F1 sections of README | “Probabilities use exact all-combinations” is stated as a site-wide rule. Cricket also uses Monte Carlo for long schedules, groups and bonus-point formats; the other sports use their documented rating-based simulations. | Scope the rule to cricket qualification and name its exact/Monte Carlo branches; point to the separate sport-model sections. This is a documentation correction, not a model change. |
| `README.md:31`; `extract_table.py:1774–1778`; `README.md:87` | The top Data Rules claim `--source cricketdata` is the default, while argparse and the later README explanation correctly say `auto`. | State that `auto` selects CricketData when configured and Cricsheet otherwise. Scope NRR statements to cricket. |
| `DESIGN.md:15,36,54–59,70`; unchanged page-family code | The new design system mixes current foundation descriptions with future page-family behavior without an explicit rollout distinction. For example it says hub cards do not blur, but `src/hub/HubPage.css:30–31` still blurs every card. It describes exact track geometry while `src/sport/SportPage.tsx:612` still applies a 6% minimum and `src/App.tsx:538` a 2% minimum. Hub filters, F1 points gaps, touch-inspectable distribution values, correct Share Kit return routing and per-league HTML/social images remain pending. | Add a visible implementation-status note: current foundation delivers tokens/shared surfaces/header search/theme semantics/lazy routes/recovery; composition and data-viz bullets are requirements for the following family PRs. Change “final implementation” to clearly refer to the intended completed rollout. Qualify the hub-blur claim until its family change ships. |
| `DESIGN.md:36`; `src/App.css:196–198` | Glass is described with a 10px blur, but the floating league menu still explicitly uses 24px. | Document the menu exception or align the implementation. Do not describe one global blur value as universal while the exception exists. |

The all-targets-44px and all-simulated-formatting statements in DESIGN.md should be read as acceptance requirements until the family rollout is complete, not a certification of the entire current site. Existing inline/footer links and page-specific formatting were outside the foundation's complete behavior change.

## Verified current documentation

- The Night Signal token table matches `src/index.css`: ground, solid data planes, ink, citron and outcome colors all agree in light and dark. The selected font families/weights are the actual self-hosted imports in `src/fonts.ts`; no new font download is claimed.
- README's landing/hub/query routes, theme persistence, static hosting and frontend command names remain correct. `package.json` still provides the documented root and GitHub-subpath builds. The foundation adds no runtime server, service/API key or model dependency.
- DESIGN correctly documents the searchable picker, sport/name/season search, Escape focus return, stable theme pressed state, static skeleton geometry, progressive View Transitions and motion preference. The shared lazy route error boundary now exposes an explicit reload button.
- Site analysis is clearly a baseline and plan: its priority table uses “resolution target,” and production/final measurement evidence is explicitly pending (`docs/site-analysis.md:54`). Its references to eager page loading are baseline findings, not stale assertions about the new foundation.
- The saved Lighthouse evidence supports the stated **13.5.0, performance 98, accessibility 96, LCP 1.8s, CLS 0, TBT 0ms**: `docs/performance/before.json` records LCP 1800.2335ms and separates lab metrics from real-user INP. Its mobile simulated-throttling settings and environment are preserved.
- There are **36 baseline PNGs** and **60 direction PNGs** at the documented paths. The three direction comparisons each cover five page families, two widths and two themes. The initial JS total is correctly distinguished from only the shared chunk, with supporting asset figures in `docs/audits/performance-seo-code.md`.
- No backend/model/config/payload files are part of the foundation diff. Existing detailed model/backtest sections were not silently rewritten, and the audit does not claim that future prerendered HTML, PWA features or page-family changes have shipped.

## Coverage map

| Changed surface | Reference | How-to | Explanation | Disposition |
| --- | --- | --- | --- | --- |
| Tokens, type, solid panels, sport accents | DESIGN token/component sections | DESIGN composition rules | Direction comparison | Covered, with rollout/blur corrections above |
| Searchable league disclosure and theme toggle | DESIGN components | Visible control labels and existing route documentation | UX audit and synthesis | Covered |
| Lazy page families and chunk recovery | DESIGN data/delivery and loading rules | On-screen Reload action; unchanged dev/build commands | Foundation review / performance audit | Covered |
| New verification and evidence | DESIGN verification | Existing README test/build commands | Site analysis + linked audit and baseline artifacts | Covered; final deployment evidence intentionally pending |

No new tutorial is required for these presentation changes. No VERSION file or versioned release scheme was introduced, so no version/changelog update is warranted. No architecture diagram was changed or invalidated.

Optional discoverability improvement: turn README's plain “see DESIGN.md” into a Markdown link and add a link to `docs/site-analysis.md`, so the redesign evidence is reachable directly from the repository front door.

The four required corrections above were sent to the lead implementer. This report must not be treated as a clean documentation sign-off until they are applied and rechecked.
