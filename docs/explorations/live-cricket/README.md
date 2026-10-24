# Live Cricket exploration — planning packet

Prepared 23 October 2026. **Audit and planning only; implementation is not approved.**

The proposed expansion separates **Live Cricket** from **Season Odds**. Scores and scorecards lead the match center, with separate views for model win probabilities and bookmaker prices. An optional illustrative field guide explores depth without inventing tracking data.

- [Draft expansion plan](../../designs/live-cricket-expansion.md): product scope, data architecture alternatives, freshness/correction behavior, model work, future work units and open decisions.
- [Source feasibility](source-feasibility.md): existing contracts and the gap between season qualification and live match probability.
- [Provider research](provider-research.md): official coverage, public pricing/terms observations and unresolved entitlements.
- [Visual and 3D review](visual-3d-review.md): current six-family structure, proposed match hierarchy, actual captures and prototype limits.
- [Clickable concept](concept.html): historical IPL records, explicitly marked **Not live**. No live API, bookmaker feed or match model is connected.

No product source, infrastructure, account, subscription or deployment changed. No purchases, signups, authenticated provider calls, commit or push were performed. Planning documents and an isolated local concept are the deliverables.

The concept has local Chromium checks for responsive containment, controls, tabs, reduced motion and unavailable-data states. These do not validate a live feed, full accessibility, WebKit/devices or performance. Production tests were not rerun because application code was unchanged.

Before implementation, agree the initial competition/feature inventory, licensing for both hosts, bookmaker/settlement scope, monthly cap and whether a small shared data service may be added. Each model format needs independent validation. The current static publishing pipeline and qualification solver cannot provide live match probabilities by relabelling their outputs.

The next concrete owner input is five must-have competitions and an operating ceiling, using the coverage checklist in the plan. No implementation approval is inferred from this exploration.

<!-- gstack:office-hours:report:start -->
## Spec Review

Disposition: COMPLETED

Stop: PASS

| Round | Findings | Prior findings confirmed resolved | Quality score |
|---|---:|---:|---:|
| 1 | 1 | 0 | 9/10 |
| 2 | 0 | 1 | 10/10 |

Findings reported across rounds: 1 (sum of round inventories; recurrences count again).

Confirmed resolutions: 1 (sum of explicit later-reviewer resolved statuses).

Unresolved findings in the last completed inventory: 0.

Completed fix-and-review transitions: 1 (rounds, not edits).

No unresolved findings.
<!-- gstack:office-hours:report:end -->
