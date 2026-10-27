# Live Cricket: provider feasibility

Checked **23 October 2026** using public primary documentation, pricing pages and terms. Planning only: no account signup, purchase, key request, secret-value inspection or authenticated/paid provider API call. Prices below are public page observations, not quotes or signed rights. This is a product and integration assessment, not legal advice.

The requested product has three separate inputs: **scores/scorecards/deliveries**, **our own match-win model**, and **bookmaker prices**. No supplier reviewed establishes complete, equally detailed coverage of every match worldwide. Discovery coverage, live coverage, delivery detail, model support and bookmaker availability must be tracked independently.

## Recommendation

Evaluate **Sportmonks World/Enterprise for score data plus The Odds API for bookmaker quotes** as the practical first commercial shortlist. Require a named competition/feature entitlement matrix and approval for both the Cloudflare site and GitHub mirror before a purchase decision. Consider **Sportradar** when official competition rights, richer coverage levels or a negotiated service contract are priorities. CricketData remains a useful low-cost comparison because it is already integrated, but its published delay wording and detailed-feed coverage need resolving before treating it as the live foundation.

Start with a declared supported cohort, rather than claiming “all world cricket.” Allow any discovered match to have scores while its card, deliveries, prediction or market remains unavailable. ESPN's public internal endpoints do not establish a supported or licensed alternative. Roanuz is a relevant score/prediction alternative, but its AI-generated “odds” do not substitute for named bookmaker prices. The evidence and conditions follow below.

## What exists today

The repository's CricketData adapter uses configured seasons and `series`, `series_info` and `series_points`; series discovery examines at most four 25-row pages. It does not consume live detail endpoints. The scheduled season publishing workflow is twice daily, not live match ingestion. The current solver estimates season qualification from fixture outcomes; it is not a match-win predictor. In particular, `FixtureImpact.teamAWinProbability` is a selected team's qualification probability **conditional on** that fixture winner. See the separate [source/model feasibility audit](source-feasibility.md) and [adapter source](../../../extract_table.py#L195).

## Provider roles and coverage limits

| Candidate | Suitable role | What needs verification before selection |
| --- | --- | --- |
| CricketData / CricAPI | Low-cost fixture/score source; detailed cards on eligible matches | Complete discovery/pagination, `fantasyEnabled` coverage, delivery contract, actual delay, commercial display/cache rights |
| Sportmonks Cricket v2 | Broad commercial scores, cards and deliveries | Exact league tier and feature gaps, real freshness, two-domain pricing, cricket-specific licensing scope |
| Sportradar Cricket v2 | Contracted score feed with specified official partnerships | Competition/event coverage level, production price/quota/SLA, permitted properties and model/archive use |
| Roanuz v5 | Alternative score/delivery feed and optional supplier predictions | Full-live versus delayed metric group, cohort coverage, package endpoint access and redistribution terms |
| The Odds API v4 | Actual bookmaker quote comparison | Specific active competitions/books/markets, settlement mapping, acceptable public transport/archive design |
| ESPN public internal endpoints | Unsupported feasibility lead only | Working cricket route, permission, supported schema, coverage, quota and stability contract are not established |

### CricketData: inexpensive, but delay and detail are conditional

The public basic guide illustrates `currentMatches`/`match_info` with match IDs, formats, teams, status and innings runs/wickets/overs. A match's `fantasyEnabled` flag governs scorecard/squad/ball-by-ball availability. The Fantasy scorecard example includes batting, bowling, extras and totals. The technical audit did not verify a current complete delivery/correction contract; documentation examples are not a measured live feed. There is no public exhaustive, current entitlement matrix proving all international men/women, domestic and associate fixtures across every format. [Basic guide](https://cricketdata.org/how-to-use-cricket-data-api.aspx), [Fantasy guide](https://cricketdata.org/how-to-use-fantasy-cricket-api.aspx), [provider FAQ](https://cricketdata.org/some-frequently-asked-questions-about-the-cricket-data-api-and-cricapi/).

Published monthly plans are free **100 hits/day**, **$5.99 / 2,000**, **$12.99 / 10,000**, **$29.99 / 100,000**, and **$64.99 / “No Limit.”** The page defines one hit as one API use and primarily distinguishes volume. It describes data as a few minutes delayed; WebSockets remain labelled “in testing.” A linked 2022 policy says free Fantasy calls consume ten credits versus one on paid accounts; confirm current billing rather than treating that older post as a new quote. [Pricing](https://cricketdata.org/pricing/), [linked Fantasy trial policy](https://cricketdata.org/v1-0-launch-1st-may-2022/).

The terms instead describe a five-minute anonymous lag and **30 seconds with a registered key**. That conflict prevents a reliable latency promise. They provide a personal/non-commercial grant and require purchased credits/key for commercial use, while retaining broad material-use restrictions. No clear numeric cache-retention or unrestricted raw-export permission was established. Obtain written scope for public display, derived model use, storage and both domains; paid API access alone does not resolve those questions. Unlimited remains subject to fair use, including a ten-IP limit. [Terms of use](https://cricketdata.org/terms-of-use/).

**Assessment:** compare eligible detailed samples and actual timestamps first. Do not assume that a basic score implies a complete card, that paid access removes the delay, or that existing season snapshots establish match coverage.

### Sportmonks: the practical broad score-feed candidate

Discovery uses fixtures/leagues/seasons and a live-score collection. The documented includes provide innings runs, batting/bowling cards, lineups and balls; Test cards support four innings. Nested ball includes are needed beyond delivery IDs. This is a plausible complete scorecard/delivery adapter, subject to actual event coverage. [Fixtures](https://docs.sportmonks.com/v2/cricket-api/our-api/fixtures/get-all-fixtures), [scoreboards and balls](https://docs.sportmonks.com/v2/cricket-api/relationships/scoreboards), [official endpoint catalogue](https://cricket-postman.sportmonks.com/).

The coverage matrix, marked **22 October 2026**, lists men's/women's internationals, domestic competitions and associate-country examples such as ECS Vienna, Malaysian T10 and Nepal Premier League. Women's ODI/T20I/Test series, WBBL and Women's Hundred are explicitly represented. It also shows feature gaps. Its “over 150 leagues” headline is not a complete-world or every-delivery guarantee; a listed league may include archived seasons or missing features. Confirm exact current season IDs and live/detail flags, especially first-class, women and associate fixtures. [Coverage matrix](https://www.sportmonks.com/cricket-api/coverage/).

The dedicated pricing page shows **Major €29/month (20+ leagues)**, **World €75 (60+)**, and **Enterprise from €129 (100+, negotiated)**, excluding VAT. All advertise the same feature types and **2,000 calls/hour per endpoint**; World adds Tests/ODIs/World Cup. “Minute-to-minute” updates are published, but no numeric ground-to-feed delay commitment was found. The main product page instead presents 26/64 leagues and €125 Enterprise, so league counts and the Enterprise starting price require confirmation. [Dedicated pricing](https://www.sportmonks.com/cricket-api/plans-pricing/), [product page](https://www.sportmonks.com/cricket-api/).

Terms allow building monetized apps and storing/transferring data, but prohibit unapproved direct data resale. Pricing is **per domain**, with adjustments for multiple domains. Coverage/accuracy/availability are not guaranteed; logo/photo rights need separate permission. Confirm the proposed cache/export arrangement and both hosts explicitly. Buying this commercial feed does not itself establish official rights from every cricket organizer. [Terms](https://www.sportmonks.com/terms-of-service/).

**Assessment:** request the World-versus-Enterprise entitlement delta for the initial cohort. A successful trial sample would establish technical fit; only the agreed licence establishes the permitted deployment.

### Sportradar: stronger official-rights option, with contract-specific economics

Cricket v2 explicitly identifies official data for **ICC, ECB and Caribbean Premier League**, not universal official rights. It supplies schedules, player/team information, match statistics and detailed deliveries where available. Coverage is tiered: post-match, Core and Advanced. Core includes score/players/current-over data; Advanced adds richer shot/ball information. Drive detail availability from event coverage rather than assuming the richest schema everywhere. [Overview](https://developer.sportradar.com/cricket/reference/cricket-overview), [coverage FAQ](https://developer.sportradar.com/cricket/reference/cricket-faq).

Tournament metadata supports men/women/mixed and Test, ODI, T10, T20I, first-class, List A, T20 and Hundred types. These enums do not prove every competition or associate fixture is covered. The tournament catalogue and daily/live schedules support discovery within the supplied scope. Published live-schedule cache TTL is **10 seconds**; timeline delta returns five-minute increments with **300-second TTL**. Cache/update frequency is not an end-to-end latency SLA. [Tournament list](https://developer.sportradar.com/cricket/reference/cricket-tournament-list), [daily live schedule](https://developer.sportradar.com/cricket/reference/cricket-daily-live-schedule), [timeline delta](https://developer.sportradar.com/cricket/reference/cricket-match-timeline-delta).

Production cricket price and quotas were not publicly established. Generic trial defaults are **30 days, 1,000 requests per rolling 30 days and 1 QPS**; production limits are assigned per product/account. These are evaluation limits, not a production quote. [Account/quota documentation](https://developer.sportradar.com/getting-started/docs/your-account).

The current master terms (5 August 2026) distinguish internal non-commercial trials from production; the order form identifies products, authorized properties, fees and limits. Display, archiving, derivative products and advertising have restrictions, with product-specific addenda possible. Obtain explicit approval for our model inputs/outputs, retention, both domains and any public data access; do not infer broad rights from the overview. [Master terms](https://developer.sportradar.com/sportradar-updates/page/terms-and-conditions).

**Assessment:** ask for a media/informational-site contract and named coverage matrix if the budget supports a negotiated supplier. No public source reviewed settles its total production cost or all-associate coverage.

### Roanuz: useful alternative; supplier “odds” are predictions

Roanuz distinguishes **MG100 full live deliveries**, **MG101 interval scorecards** and **MG101B limited/uncertain-source scorecards**. The latter two carry a published **15-minute delay**, and do not expose the same odds/graph/stat endpoints. Broadcast availability can change a tournament's group. Do not interpret its broad international/domestic marketing as consistent full-live coverage, or use a curated featured-matches list as exhaustive discovery. [Coverage](https://sports.prod.roanuz.com/v5/coverage), [live-score solution](https://sports.prod.roanuz.com/v5/solution/livescore).

The v5 India-region pricing page shows **₹17,669/month: 100 matches/400,000 requests**, **₹34,999: 200/800,000**, and **₹59,999: unlimited matches/1.6 million requests**. PayGo is separately **₹16,999/month billed annually plus usage**, with per-endpoint/per-match charges; this is not an all-inclusive price. The page lists cache storage up to 24 hours. Confirm billing region, taxes and detailed endpoint access; no signed redisplay/raw-export licence was reviewed. Its “Privacy & Terms” footer leads to a privacy page rather than a clear data-redistribution contract. [Current v5 pricing](https://www.cricketapi.com/v5/pricing), [linked policy](https://www.cricketapi.com/legal/Privacy-Policy/).

Its Live Match Odds documentation explicitly describes **AI-powered** probabilities and decimal/fractional outputs, refreshed every **five seconds**. These lack a named bookmaker price source and must be labelled supplier predictions, not sportsbook quotes or our own model. Response cache freshness hints are distinct from storage expiry. [Live Match Odds](https://paygo-console.sports.roanuz.com/v5/docs/live-match-odds-rest-api), [cache concepts](https://www.cricketapi.com/v5/docs/auth-rest-api).

### The Odds API: actual bookmaker quotes, with narrower cricket availability

The cricket page advertises live/upcoming prices, **mainly match winner**. Its 16 listed keys include Tests, ODIs, international T20, IPL, Big Bash, PSL, CPL, T20 Blast, Asia Cup, Champions Trophy, men's/women's World Cups and T20 World Cups, and men's/women's Hundred. That establishes meaningful women's coverage, not every women's/domestic/associate event. A listed key does not guarantee a current market. The example includes bookmaker identity plus bookmaker/market update timestamps. [Cricket coverage and example](https://the-odds-api.com/sports/cricket-odds.html).

This feed discovers events **for which books have listed prices**, rather than every scheduled cricket match. Select bookmaker regions explicitly; UK/AU/EU/US and other regional groups have different books. A book appearing in the general catalogue does not prove cricket availability. Model market/outcome/period/line separately and preserve price and source time. Start-time-based in-play inference can be wrong during postponements; use `unknown` when not independently established. [V4 contract](https://the-odds-api.com/liveapi/guides/v4/), [bookmaker/region catalogue](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html).

Published featured-market refresh is **60 seconds pre-match / 40 seconds in-play**; exchanges are **20 / 10 seconds**. These are upstream update intervals, not delivery guarantees. Current plans are **free 500 credits/month**, **USD $30/20,000**, **$59/100,000**, **$119/5 million**, **$249/15 million**. Current sport/region/market entitlements still control returns. Paid burst limit is **30 requests/second**, with possible 429s below it. [Update intervals](https://the-odds-api.com/sports-odds-data/update-intervals.html), [plans](https://the-odds-api.com/), [rate limits](https://the-odds-api.com/guide/rate-limit.html).

The ordinary odds endpoint costs regions × markets per sport request, not one credit per individual bookmaker price. Sports/events discovery is quota-free; track returned usage headers. This is separate from billable polling volume, history and event-market endpoints. Scorecard/ball-by-ball completeness is not established by this quote feed. [Quota rules](https://the-odds-api.com/liveapi/guides/v4/).

Terms updated **31 August 2026** expressly allow commercial UI display, indefinite storage, derived values and statistical/ML use. They prohibit repackaging the data as a standalone API, raw feed or downloadable data product. Attribution is optional. A normal UI transport and a competing raw-data service are different cases: obtain confirmation before applying the site's public repository/archive pattern to bulk market history. The supplier is an independent aggregator, not a bookmaker or a guarantee of executable prices. [Terms](https://the-odds-api.com/terms-and-conditions.html).

**Settlement remains a blocker:** the reviewed cricket docs do not settle bookmaker-specific treatment of Test draws, ties, no-results, DLS, super overs, minimum overs or voids. Preserve unknown rules; do not compare incompatible markets. Decimal reciprocal is a market-implied quantity containing margin, not our calibrated match-win probability. A result label is not sufficient to infer how every bookmaker settled a quote.

### ESPN: no supported keyless production contract established

The plausible public internal route `https://site.api.espn.com/apis/site/v2/sports/cricket/0/scoreboard?dates=20261023` returned HTTP 502 during a single anonymous feasibility check. This neither proves permanent failure nor a working cricket integration. No supported cricket API specification, quota, latency/SLA, full worldwide coverage or redistribution licence was found. The public scoreboard page presented verification; it was not bypassed. Existing success with another ESPN sport would not establish cricket parity.

Disney's terms explicitly include ESPN and restrict automated extraction and business-related use absent an applicable permission. Anonymous HTTP availability therefore must not be treated as a public data licence. ESPN is not the recommended production fallback without a separate permitted integration. [ESPN scoreboard](https://www.espn.com/cricket/scoreboard), [Disney/ESPN terms, updated 24 May 2024](https://disneytermsofuse.com/english/).

## Budget and freshness implications

Illustrative arithmetic, not a supplier quote: one shared list poll every 30 seconds around the clock costs **2,880 requests/day**. Adding ten per-match detail polls at the same cadence makes **31,680/day**, before pages, retries or weighted Fantasy calls. CricketData's free 100/day cannot support that design; even paid tiers must be sized against concurrency and hours of play.

For The Odds API, one region × one market × one active sport key every 40 seconds for eight hours costs **720 credits/day**, approximately **21,600 per 30 days**. Eight simultaneous sport keys at that cadence would be **172,800**; two regions double the amount. Poll only active scopes and centrally reuse results. A $30 plan is not automatically enough merely because there is one website. Upstream quota cost is separate from the number of visitors. These calculations use the [published quota formula](https://the-odds-api.com/liveapi/guides/v4/) and [update intervals](https://the-odds-api.com/sports-odds-data/update-intervals.html), not measured account usage.

Maintain separate score, prediction and bookmaker-market clocks. Show actual provider update time when supplied and receipt/publication times separately. Missing, suspended or expired quotes must remain unavailable/stale even beside a fresh score. Polling a delayed source faster cannot create fresher information. End-to-end freshness and correction behaviour require measured samples, not API response-time marketing.

## Decision gates before implementation or purchase

1. **Coverage evidence:** obtain a current named season/competition matrix and a concurrent live fixture sample covering men's/women's international, domestic and associate cricket, plus T20, ODI, Test/first-class, T10 and Hundred. Record discovery/card/deliveries/market/model separately; include missing and delayed cases.
2. **Detailed state and corrections:** verify batting/bowling/extras/totals, active players, stable innings/player/delivery IDs, illegal balls, wickets, revised targets, reviews/corrections, interruptions, super overs and four-innings matches. A scorecard or format enum alone does not satisfy this gate.
3. **Rights in writing:** approve both site domains, cache/retention, derived-model use, attribution/logos, public UI transport and any archives/downloads. Keep commercial access pricing distinct from the agreed rights. No provider contact or purchase has been performed by this research.
4. **Operational budget:** agree monthly ceiling and freshness goal; measure provider age, round-trip time, corrections and concurrent-match costs. Confirm actual plan quotas and retry behaviour before a live pilot.
5. **Independent model validation:** build and calibrate a match-state model for each supported cohort. Keep bookmaker prices separately labelled; define outcome/settlement alignment before comparisons. Until validated, show scores and explicitly unavailable probabilities rather than borrow the season solver or relabel supplier AI.

The immediate blockers are **verified detailed-feed coverage and delay**, **authorized dual-domain display/retention**, **market settlement/event mapping**, an **approved operating budget**, and a **validated match-win model**. None is resolved by an existing API key, a pricing page's “all leagues” label or a provider's broad worldwide marketing.
