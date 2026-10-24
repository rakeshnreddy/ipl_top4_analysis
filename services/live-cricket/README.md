# Live Cricket data service

This is an optional, read-only application backend for Playoff Pulse. The static frontend also supports SportScore directly, so a Worker account or deployment is **not required** to use the free source. Nothing in this package has been deployed.

The default score adapter uses the free, keyless SportScore widget API. It discovers covered cricket fixtures and preserves available score totals and source status. It does not invent batting cards, delivery logs, bookmaker prices or match-win probabilities when those fields are absent. Every page using its data must show the visible, crawlable **Powered by SportScore** link already included in the frontend.

## Run and verify locally

Use Node 24 or a current Node version supported by Wrangler:

```sh
cd services/live-cricket
npm ci
npm test
npm run test:runtime
npm run types
npm run typecheck
npm run dry-run
npm run dev
```

`dev` runs Wrangler locally. `dry-run` creates an ignored local bundle without uploading it. Neither creates a provider account or purchases a plan. Set the frontend's public `VITE_LIVE_CRICKET_API_URL` to the local/approved service origin to use this backend; that setting must never contain a provider key. Without it, the site's free direct adapter remains usable.

The service imports the repository's provider-neutral TypeScript contract and pure SportScore normalizers; they are build-time source dependencies rather than an external runtime package.

## API

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Process/configuration health; explicitly does not assert upstream connectivity |
| `GET /v1/matches` | Current bounded registry, coverage and source state |
| `GET /v1/matches/:id` | Verified discovered match, independent scorecard/commentary/model/market parts |

GET, HEAD and CORS preflight are supported. There are no write, credential, raw upstream, arbitrary proxy, query, archive or download endpoints. Malformed IDs return 400; undiscovered IDs return 404 after a coalesced discovery attempt for the configured provider. The list and details use the same contract as the direct free adapter. Allowed origins default to the Cloudflare site, GitHub mirror, and local Vite port 5173.

Public reads have ten seconds of regional edge caching, response ETags, bounded paths and no request bodies. Edge caching improves fan-out; it does **not** coordinate provider requests. One SQLite-backed Durable Object owns the shared provider credential/quota domain and current snapshots. Its jobs reserve cadence and credits synchronously before external I/O, coalesce concurrent refreshes, persist before publishing state and allow at most two simultaneous upstream requests. Storage is trimmed when matches leave the bounded registry. Collection is demand-driven, so an empty site does not burn a free plan in the background.

Responses and state contain only normalized fields used by the application. Upstream bodies are limited to 2 MB, request timeouts to eight seconds, discovered matches to 200 and discovery pages to one through four. All upstream hosts and endpoint/query choices are fixed by source code. Provider-supplied pagination links are never followed. Keys stay in Worker secrets; errors never echo upstream URLs or bodies. Observability logs/traces have query-string redaction enabled because keyed providers authenticate in query parameters.

## Free budgets and optional keyed adapters

`wrangler.jsonc` keeps keyed access and redisplay flags false. Copy `.dev.vars.example` to `.dev.vars` only when using your own already-authorized free credentials. Local secret files are ignored; production credentials belong in Wrangler secrets. Changing a provider requires reviewing its current coverage, terms and actual account entitlement. No sample key is usable.

| Source | Default protection | Supplied fields / limitations |
| --- | --- | --- |
| SportScore | Keyless; at least 60 seconds per shared job; at most 9,000 calls per rolling 24 hours | Discovery, source state and supplied totals; 50-row upstream list cap; no verified full cricket card or ball stream |
| CricketData | Optional free key; 90 weighted credits per rolling 24 hours; minimum 30-minute refresh | `currentMatches`, `match_info`; optional `match_scorecard` only for eligible matches and separately enabled Fantasy access |
| Sportmonks | Optional entitlement; disabled by default; 90 calls per rolling 24 hours and a conservative hourly ceiling | Livescores plus bounded nearby fixture discovery, batting/bowling cards, ordered full-replacement delivery records where supplied; an ongoing free cricket entitlement was **not** established |
| The Odds API | Optional free key; 450 region×market credits per rolling **32 days**, minimum one-hour refresh and four-hour default | Named bookmaker `h2h`/`h2h_lay` decimal quotes for explicitly mapped cricket scopes; limited market coverage and frequent stale periods on a free budget |

Hourly/daily buckets retain their entire boundary bucket, conservatively reserving slightly more than the requested rolling interval. Midnight, object eviction, extra visitors and the GitHub mirror cannot reset the shared budget. Failed network/parse requests still consume their reserved credits. Multiple views share one provider call rather than multiplying it by readers. These caps leave headroom below the published free allowances; they do not account for other apps using the same key or egress IP. They cannot be raised beyond free defaults through environment variables.

CricketData's free Fantasy policy has historically weighted a scorecard call at ten credits. This package charges **ten** locally and keeps it disabled by default. `CRICDATA_FANTASY_ENABLED=true` requires verified detailed access as well as `CRICDATA_ACCESS_ENABLED=true`, `CRICDATA_REDISPLAY_ALLOWED=true` and `CRICDATA_API_KEY`. Card identity (ID, competition and both teams) must match its separately verified info response; a wrong card is discarded while useful scores remain. A card outage preserves the last good card with its old time and a stale label.

For CricketData select `SCORE_PROVIDER=cricketdata`. For Sportmonks select `sportmonks`, set its own access/redisplay flags, and supply `SPORTMONKS_API_TOKEN`. The code never signs up for a free trial and never automatically converts to a paid plan. CricketData ball-by-ball remains disabled until its current detailed/correction contract is verified.

For bookmaker prices, enable `ODDS_ACCESS_ENABLED` and `ODDS_REDISPLAY_ALLOWED`, provide `ODDS_API_KEY`, choose at most two `ODDS_REGIONS`, and explicitly configure scopes such as:

```json
[
  {
    "sportKey": "cricket_ipl",
    "competitionIds": ["the-exact-score-provider-competition-id"],
    "format": "T20",
    "gender": "male"
  }
]
```

Set this serialized array in `ODDS_SCOPES_JSON`. It is an example mapping shape, not a verified competition entitlement. Missing format/category or an unknown competition suppresses quotes. Matching requires exact normalized team identities, explicit competition/format/category scope, a start within five minutes, and exactly one candidate. The resulting event-ID map persists. A conflicting or postponed mapping stays unavailable until reviewed rather than silently attaching another fixture's prices. No name-only/fuzzy fallback exists.

The service tracks the provider's `x-requests-remaining` header. When that value reaches zero it stops further paid-credit requests; recovery after an account reset currently requires an operator to verify entitlement and clear that provider's stored quota record. No public endpoint can reset a quota. A provider 429 or authentication failure creates persistent backoff. Do not delete the object or quota rows to bypass a daily/monthly allowance.

Markets retain their own bookmaker/market update times. A quote feed that does not explicitly report suspension leaves market state **unknown**, and absent cricket settlement rules remain null. Old quotes remain stale even next to a fresh score. Prices are never converted into Playoff Pulse model percentages. The normalized service is application transport, not a standalone licensed odds feed or a raw public repository/archive export.

## Corrections, timestamps and model integration

- Provider observation time, collection time and content revision stay distinct. A source that omits observation time gets `observedAt: null`; the application can say checked, not a freshly bowled ball.
- The last good snapshot survives upstream errors. A source outage cannot finish an ongoing match. Missing active matches are retained for up to 48 hours with their previous clocks, bounded by the registry cap.
- Scores may decrease on a valid correction. Older provider observations are rejected; equal-time corrections are accepted. Unchanged content does not acquire a new revision from its collection clock.
- Cricket notation is converted to integer legal balls only for six-ball formats. Hundred notation remains unconverted. Wides and no-balls with duplicate ball notation keep distinct stable delivery IDs. Sportmonks fixture delivery arrays replace earlier arrays, allowing source deletions and revisions.
- Card, commentary and bookmaker freshness are evaluated independently. Optional parts remain unavailable when not supplied. A refetch does not re-date old provider observations. Incompatible or missing market scopes stay unavailable.
- Model output is deliberately unavailable. The research artifact in `live_model/` has not passed all release gates, and currently verified free score responses do not supply all inference inputs (confirmed target revision, scheduled balls, interruption/super-over flags). A future released model resolver belongs at `Collector.detail` after normalized score acceptance, must consume verified provider state and its score revision, and must return the public `Part<ModelSnapshot>` contract. There is no environment flag to expose research-only predictions.

## Verified contracts and remaining limits

Public source documentation was inspected on 23 October 2026. Unit fixtures are synthetic adaptations of documented shapes and contain no captured live keys. Tests cover normalization, real pagination shape, independent staleness, identity mismatches, lower-score corrections, older observations, outages, bounded responses, cold deep links, concurrent readers, rolling budgets and actual SQLite recovery after Durable Object eviction. Offline runtime tests retain the native Workers fetch receiver/redirect validation path while mocking network responses. No authenticated provider requests were made.

A real keyless local smoke check on 24 October 2026 returned 17 SportScore fixtures through Wrangler and opened a matching normalized detail with HTTP 200. This caught two Workers-specific constraints missed by ordinary Node mocks: assigning native `fetch` as a class method changes its receiver, and Workers does not support `redirect: "error"`. The service now invokes native fetch through a global wrapper and uses `manual` redirects with a non-2xx rejection. Both defects have failing-before/passing-after runtime regressions. The temporary diagnostic was removed; failure logging emits fixed category codes without upstream exception text.

- [SportScore developer API](https://sportscore.com/developers/) and [free-tier terms/attribution](https://sportscore.com/developers/terms/).
- [CricketData basic contract](https://cricketdata.org/how-to-use-cricket-data-api.aspx), [Fantasy scorecard contract](https://cricketdata.org/how-to-use-fantasy-cricket-api.aspx), [pricing](https://cricketdata.org/pricing/). The browser-text service intermittently fails, but the official page's embedded public examples were retrieved directly. Key placeholders from those pages were not reused.
- [Sportmonks live discovery](https://docs.sportmonks.com/v2/cricket-api/our-api/livescores-and-fixtures/get-all-livescores), [fixtures](https://docs.sportmonks.com/v2/cricket-api/our-api/fixtures/get-all-fixtures), [scoreboards/balls](https://docs.sportmonks.com/v2/cricket-api/relationships/scoreboards), [official Postman catalogue and sample schemas](https://cricket-postman.sportmonks.com/).
- [The Odds API v4](https://the-odds-api.com/liveapi/guides/v4/), [cricket coverage](https://the-odds-api.com/sports/cricket-odds.html), [terms](https://the-odds-api.com/terms-and-conditions.html).
- [Durable Object coordination rules](https://developers.cloudflare.com/durable-objects/best-practices/rules-of-durable-objects/), [SQLite storage](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/), [RPC](https://developers.cloudflare.com/durable-objects/best-practices/create-durable-object-stubs-and-send-requests/), [runtime test APIs](https://developers.cloudflare.com/workers/testing/vitest-integration/test-apis/), [query-string redaction setting](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/settings/methods/get/).

No source promises every match around the world. No test establishes a ground-to-feed SLA, verifies private account rights, validates every provider format, or establishes production Cloudflare account eligibility/cost. SportScore's public list has no documented pagination; that limit is reported rather than bypassed with scraping. Keyed adapters need a real authorized free sample before production activation. Source fees and optional infrastructure quotas remain separate; no infrastructure has been provisioned by this implementation.
