# Live sports expansion roadmap

Date: 24 October 2026 · Status: proposed future work.

The current authorized implementation is Live Cricket. The owner also wants other sports eventually, using free sources where practical. This roadmap prepares that extension; it does not enable another sport, approve subscriptions, or establish worldwide coverage. Read it alongside the [cricket design](live-cricket-expansion.md) and [current service contract](../../services/live-cricket/README.md).

## Recommended order

Finish and verify cricket, then add **football**, followed by **basketball**. Both already have season pages in this repository and appear in the current free provider's documented sports. Tennis follows as a distinct scoring and participant design. American football, baseball, ice hockey and Formula 1 require a new live-source assessment before their order is committed.

Launch each sport with verified scores and match status first. Detailed statistics, event logs, bookmaker prices and our own probabilities become separate capabilities when supported. A missing market or model must not hide a useful score. Do not advertise “all sports” or every match worldwide from the existence of a provider sport parameter.

## What exists, and what still needs design

The cricket implementation under review has a provider-neutral **cricket v1** read contract, free SportScore normalization, a polling client, pause/resume, independent optional data parts, and an optional coordinated Worker service. Its endpoint names, score shape, state union, provider configuration and market mapping remain cricket-specific. They are a foundation for reuse, not a completed multi-sport platform.

Existing `SportPayload` contains season standings, fixtures, results, brackets and qualification/title simulations for team sports. `F1Payload` contains championship standings, calendars, podium results and race favourites. Neither is a live match or timing contract. Existing season probabilities must retain their meaning; they cannot be relabelled as in-play win chances. FixtureDownload and Jolpica integrations in the repository establish existing season ingestion, not verified live-feed rights, latency or detail coverage.

Source anchors: [live types](../../frontend/ipl-analyzer-frontend/src/live/types.ts), [free normalization](../../frontend/ipl-analyzer-frontend/src/data/freeCricketNormalize.ts), [season sport types](../../frontend/ipl-analyzer-frontend/src/data/sportData.ts), [F1 types](../../frontend/ipl-analyzer-frontend/src/f1/f1Data.ts), [collector](../../services/live-cricket/src/collector.ts), [routing](../../frontend/ipl-analyzer-frontend/src/data/leagues.ts).

## Free-source evidence and boundaries

Checked against primary documentation on **24 October 2026**:

- SportScore documents football, basketball, cricket and tennis, a keyless JSON API, an approximately 10,000-request daily allowance per IP and 60-second edge caching. The match-list endpoint accepts up to 50 rows. These are provider statements, not measured ground-to-screen freshness or proof of complete competition coverage. [Developer API](https://sportscore.com/developers/).
- Its free terms require a visible, crawlable attribution link on every surface using its data. They permit application caching and derived dashboards, prohibit competing raw-feed mirroring, bulk redistribution and rate-limit evasion, and provide no SLA. Preserve attribution in static entry HTML as well as the rendered view; an application API is not permission to publish a provider dataset. [API terms](https://sportscore.com/developers/terms/).
- No new sport's detailed response, sustained availability, category coverage, spatial tracking or bookmaker rights has been verified by this roadmap. The documented tracker endpoint alone is insufficient evidence for a factual 3D replay. No new account, key or paid entitlement was obtained.

The current optional Odds API adapter is cricket-scoped and disabled without credentials and explicit access/redisplay settings. Other sports require their own verified event/market scopes and budget. Free bookmaker allowance does not imply continuous prices, every bookmaker, every region, or any particular competition. Recheck [current quota rules](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs) and [display terms](https://the-odds-api.com/terms-and-conditions.html) before activation. There is no verified keyless bookmaker source in this implementation.

## Capabilities, not one universal scoreboard

Publish a runtime inventory by sport, competition, category and event. For each part record `available`, `unavailable`, `stale` or `error`, plus a reason, provenance and clocks. Unknown coverage remains unknown; a provider-wide marketing claim must not turn every event's capability on.

| Sport | Current repository foothold | First future live scope | Sport-owned details and release conditions |
| --- | --- | --- | --- |
| Cricket | Live section under implementation; season solver | Supplied totals and source state | Innings, legal balls, interruptions, revised targets and super overs; cards/deliveries and models gated separately |
| Football | Season tables, results, brackets and simulations; documented free-provider sport | Verified competition allowlist, score, source phase and clock | Added time, half-time, VAR corrections, extra time, aggregate ties and shootouts; distinguish 90-minute result from qualification |
| Basketball | Existing NBA/WNBA/NBL/WNBL season views; documented free-provider sport | Verified leagues, score, period and supplied clock | Competition-specific quarters or halves, overtime, postponed/suspended games; box scores only when supplied |
| Tennis | Documented free-provider sport; no existing season view | Separate later pilot for verified tournaments/categories | Singles/doubles participants, sets/games, point strings, tie-breaks, serving, retirement and walkover; format-specific rules |
| American football | Existing NFL season view | Source/rights discovery first | Possession, down/distance, clock, periods, competition-specific overtime and ties |
| Baseball | Existing MLB season view | Source/rights discovery first | Innings/half-innings, outs, bases, doubleheaders, suspension/resumption, shortened games and extra innings |
| Ice hockey | Existing NHL season view | Source/rights discovery first | Periods, clock, penalties, overtime and shootout; regulation-only versus final result |
| Motorsport / F1 | Existing championship view and calendar | Separate timing-source assessment | Session type, many entrants, laps, classification, gaps, red flags, penalties and provisional versus official results |

The sequence is a recommendation based on verified repository reuse and documented provider sports. Exact leagues, women's/youth categories, historical depth and latency remain unapproved until sampled and measured.

## Contract evolution without breaking cricket

Keep `/cricket/?match=<existing-public-id>` and the existing `/v1/matches` responses working. Do not change `schemaVersion: 1` in place or reinterpret its `teams`, `innings` or cricket states. First add a compatible adapter around the existing implementation; extract shared code only when the football caller proves the common behavior.

Proposed v2 discovery uses a bounded, allowlisted `/v2/events?sport=football` and `/v2/events/:id`, with an inventory endpoint describing enabled sports and coverage. These are proposed routes, not implemented endpoints. Unknown sports, fields and IDs fail explicitly; query parameters cannot select arbitrary upstream hosts or reset limits.

Use a **sport-discriminated union**, rather than one object with dozens of optional score fields:

- Common envelope: schema version, public event ID, sport, competition/season/category IDs, participants and roles, scheduled time, coarse lifecycle, source status, content revision, capabilities and provenance.
- Sport variant: cricket innings and legal balls; football match phase/goals/clock and shootout; basketball period/clock/points; tennis sets/games/points/serving; F1 session/entrants/classification. A common participant is a team, player, doubles pair or driver as appropriate. Do not require two home/away teams for every event.
- Independent parts: summary, detailed card/statistics, event log, model and market snapshots. Each keeps its own provider observation time, fetch time and revision. Include publication time separately; models add computation time and their parent score revision. Missing provider clocks stay null and are described as “checked.”
- Explicit units: elapsed versus remaining clock, period identifier, legal-ball count, points or goals. Keep source display text when parsing is uncertain. A tennis score such as advantage is not an integer; a cricket over is not a decimal fraction.

Event IDs belong to the registry. Persist provider mappings through reschedules and naming changes; retain aliases for old cricket links. Identity matching includes sport, competition/category, participant IDs, scheduled instance and format/session. Doubleheaders, two-leg ties, repeated opponents and F1 sprint/race sessions require distinct identities. Conflicts stay unmatched; no fuzzy name-only fallback attaches quotes to another event.

## Shared operational behavior

```text
Allowed provider adapters -> sport-owned normalization -> event registry/revisions
                                                       -> optional sport model
Credential/quota owner -> bounded collection            -> independent market data
                                                       -> versioned application API
                                                       -> sport-specific match view
```

Reuse bounded reads, response validation, source attribution, hidden-tab pause, reader pause/resume, backoff, ETags, correction handling and accessible loading/error states. Keep each sport view lazy-loaded. Updates preserve focus, selected period/innings and reading position; automatic score changes do not repeatedly announce whole tables. Never infer that a match is live or completed merely because its scheduled time passed or it disappeared from discovery.

The optional service must reserve quota across **all sports sharing the same provider credential or provider allowance**. Adding `/football/`, another Worker, mirror hostname or provider account alias must not create a fresh budget. For keyless SportScore, plan around its per-IP policy and actual egress behavior; never rotate IPs to evade limits. The current direct browser mode has no application-wide quota authority, and readers behind one network may share an IP. Its traffic cannot be described as globally coordinated.

Allocate headroom to discovery, selected details, retries and corrections. For illustration, four sports each fetched once per minute for 24 hours cost **5,760 list requests/day**; one continuously selected detail adds 1,440 before failures or additional views. This arithmetic is not a measured workload or provider guarantee. The current service's 9,000-call conservative daily cap is shared, not multiplied per sport. Introduce a fair scheduler, per-sport allocations and visible throttling before expanding sustained collection. Demand-driven refresh can reduce idle cost; caching must respect source terms and cannot manufacture newer observations.

Maintain last known good parts with their original times, accept valid downward score corrections and reject older observations. Cross-sport outages degrade the affected adapter/part rather than blanking every sport. Add operator visibility for source lag, parse failures, budget reservations, exhausted quotas and mismatched event IDs without logging credentials.

## Odds and model rules

Bookmaker quotes retain bookmaker, market key, outcome identities, line/handicap, currency if relevant, region, quote time, suspension state and settlement scope. Preserve unknown settlement or suspension rather than assuming an open market. Suppress current comparisons when paused, stale, suspended or ambiguously joined. Market labels must say whether they include extra time, overtime, shootouts, retirement or a tie/draw outcome as applicable. Do not silently convert a football three-way market into a two-way contest or compare 90-minute prices with a qualification model.

Playoff Pulse estimates remain distinct from prices and implied probabilities. Every new sport needs match-level chronological holdouts, appropriate baselines, calibration/Brier/log-loss evaluation, supported-state checks and competition/category drift assessment. Prevent leakage across snapshots of the same event. Tie model output to the accepted event revision; corrected scores invalidate dependent predictions. Each model declares its result horizon and rules. Season simulations and the cricket research model do not authorize another sport's in-play model.

3D remains optional and sport-owned. Flat scoreboards and odds tables stay primary. Pitch/court/circuit explainers may be illustrative with clear labels; factual positioning or replay requires verified spatial coordinates, timing and display rights. Retain accessible text/2D equivalents, reduced-motion support and render-on-demand behavior.

## Phased work and exit gates

| Phase | Concrete work | Evidence required before enabling it |
| --- | --- | --- |
| 0: Finish cricket | Complete current review, free-source verification and regressions | Honest unavailable states; correct clocks/corrections; phone/desktop, both themes and both hosting bases; no exposed key or invented probability |
| 1: Prove common contract | Add v2 envelope/registry compatibility around cricket, then football adapter | Existing cricket URL/IDs and v1 fixtures unchanged; sport-discrimination rejects wrong payloads; shared quota survives sport switches and restart |
| 2: Football pilot | A declared competition/category allowlist; scores/status first | Primary terms checked again; bounded real samples and measured lag; added time, VAR reduction, postponement, shootout and outage fixtures; browser/keyboard checks |
| 3: Basketball pilot | Verified leagues with sport-specific period/clock renderer | Quarter/half/overtime cases, source corrections, missing clocks and resumed games; combined provider budget remains within allowance |
| 4: Tennis pilot | New participant/score renderer and verified tournament inventory | Singles/doubles, tie-break formats, retirement/walkover and unknown-detail cases; no unsupported rules inferred from display strings |
| 5: Remaining sports | One source/rights and data-quality discovery brief per sport | Field-level coverage, sustainable free budget, identity contract and sport-rule fixtures; F1 timing treated as a separate project from calendar/results |
| Per-sport extensions | Details, markets, models and optional spatial view | Separate feed rights and supported fields; market identity/settlement checks; independent model validation; accessible/performance-safe spatial fallback |

Roll out one sport and a small explicit inventory at a time, using an independently disableable adapter. Preserve earlier sports when an adapter is turned off. New API/storage versions need a backward-compatible migration and rollback path; do not delete quota records to reset allowances. Reuse meaningful contract/runtime/browser tests for shared behavior and add sport-specific regression fixtures, rather than copying cricket tests with renamed teams.

## Navigation and pending decisions

When a second sport is ready, promote **Live Cricket** to **Live Sports** in the shared navigation, with an all-sports lobby and enabled-sport filters. Proposed static entries are `/live/`, `/football/`, `/basketball/` and later `/tennis/`; confirm collisions before choosing final names. Generate actual entry HTML under both base paths so GitHub Pages deep links work. Keep `/cricket/?match=...`, all `/league/.../` season links, query/hash compatibility and Share Kit links intact. Keep **Live Sports** and **Season Odds** distinct; a seasonal competition marked “In season” is not a live score.

Before the football implementation, settle its competition/category inventory, acceptable freshness, source retention/display rules, direct-browser versus shared-service deployment and measured free-budget capacity. Before markets or models, settle their own supply and validation gates. Recheck sources on the implementation date. This roadmap proposes those later decisions; it neither purchases coverage nor claims the future features are already available.
