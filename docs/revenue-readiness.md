# Revenue readiness

Implementation rechecked 26 October 2026, America/Los_Angeles; source/policy research was checked on 25 October. This is an implementation and source-rights inventory, not a claim of advertiser approval, legal compliance, guaranteed search placement or expected revenue. No advertising account, paid subscription, sponsor agreement or consent-service account was created by this work.

The owner selected **display ads and direct sponsorships** and confirmed that an AdSense account has not yet been established. The account, public publisher ID and approval are still prerequisites for display advertising. This does not block publication of the useful site and its trust pages.

## What is prepared

- Standalone, crawlable `/about/`, `/methodology/`, `/privacy/` and `/advertise/` documents with primary-site canonicals and deployment-base-aware links.
- A shared project footer, separate from each page's existing data/source/licence footer.
- A real public contact email can be supplied through `VITE_PUBLIC_CONTACT_EMAIL`. With no supplied address, the pages use the existing public project issue route. They explain that GitHub issues are public. No business address, private contact channel, audience number or sponsor is invented.
- Optional AdSense account verification metadata and a root `ads.txt` declaration are generated only for a supplied, format-valid public publisher ID. Examples and malformed identifiers are rejected. Verification does not serve ads or establish approval.
- Pure eligibility helpers for future advertising and supplied sponsorship details. The optional sponsorship notice renders only an explicitly supplied campaign on a fresh, successful, nonempty cricket lobby with reviewed sources and attribution; selection, pause, errors, overdue data and empty filters suppress it. It makes no requests, loads no network script, records no impression and does not create a consent banner.

**Advertising and sponsorship are not active in the default build.** An empty configuration emits no advertiser identifier or `ads.txt`. No AdSense loader or site-wide AutoAds code is included. The source-credit links are independent of paid placements and retain their required link treatment.

## Source-rights ledger

The source of a score or table and permission to monetize it are different questions. A free API response does not establish commercial permission. All sources used on a proposed commercial surface must be reviewed, including secondary credits and derived model inputs. A per-page gate is an engineering control, not a determination that the rest of a commercial website is automatically covered.

| Source / current use | Evidence checked | Commercial activation decision |
| --- | --- | --- |
| SportScore / default Live Cricket | [API terms](https://sportscore.com/developers/terms/) allow attributed early-stage commercial apps and monetized derived products; prohibit competing raw feeds, bulk redistribution and rate-limit evasion | Only source in the code allowlist; preserve visible, crawlable required credit, usage limits and original analytical context |
| CricketData / some season ingestion and optional live adapter | [Terms](https://cricketdata.org/terms-of-use/) describe non-commercial access and require purchased API credits for commercial use; current account entitlement is not verified | Not commercially enabled; verify account/contract or replace affected source before monetization |
| Jolpica / F1 season data | [Official terms](https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md) specify CC BY-NC-SA 4.0 and require contacting the provider for commercial usage | Not commercially enabled; obtain permission or replace affected source |
| MLB / season data | [Terms](https://www.mlb.com/official-information/terms-of-use) restrict commercial use. API-specific commercial permission remains unverified | Not commercially enabled |
| Cricsheet / historical cricket and research | Repository source attribution records ODC-By 1.0; preserve the source/licence notices and review the exact transformed data use | Not automatically allowlisted; complete a surface-specific rights review first |
| FixtureDownload, ESPN, NHL and UEFA services / other seasons | Existing source credits document ingestion, not a complete current commercial grant; several integrations are unofficial | Not commercially enabled; verify current relevant source terms and all secondary inputs |
| The Odds API / optional bookmaker adapter | Adapter is disabled without actual access and redisplay configuration. [Terms](https://the-odds-api.com/terms-and-conditions.html) and selected scopes need account-specific review | Not commercially enabled by these new helpers; bookmaker promotions are a distinct future decision |

The ledger deliberately distinguishes a documented restriction from an unverified grant. It does not assert that copyright in factual scores or a general website agreement settles every possible legal question. The site owner must resolve the actual provider contracts before a commercial launch changes how restricted material is used.

## Public configuration

All settings below are public build inputs. They must never contain passwords, access tokens, payment information or private API keys. See [the frontend environment example](../frontend/ipl-analyzer-frontend/.env.example).

| Setting | Default / meaning |
| --- | --- |
| `VITE_PUBLIC_CONTACT_EMAIL` | Empty; only a supplied valid email is published |
| `VITE_ADSENSE_PUBLISHER_ID` | Empty; accepts the real public `pub-` or `ca-pub-` identifier followed by 16 digits; validation is not ownership verification |
| `VITE_ADS_ENABLED` | `false`; a readiness switch, not an ad loader |
| `VITE_ADSENSE_SITE_APPROVED` | `false`; operator assertion only after actual Google site approval |
| `VITE_ADSENSE_CMP_READY` | `false`; operator assertion only after the applicable real consent configuration has been tested |
| `VITE_SPONSOR_NAME`, `VITE_SPONSOR_URL`, `VITE_SPONSOR_MESSAGE` | Empty; every field must be supplied, and destinations must be HTTPS without embedded credentials |

The ad eligibility helper requires **all** of the explicit approval flags, a valid publisher ID, the exact primary HTTPS origin, the `/cricket/` document, non-empty source IDs consisting only of `sportscore`, substantive ready content and visible attribution. Unknown sources, mixed feeds, alternate hosts, mirror paths, loading/error-only content and missing credit fail closed.

The sponsor helper requires supplied campaign details plus the same commercial surface checks. `SponsorshipNotice` uses the disclosure `Advertisement` and `rel="sponsored noopener noreferrer"`, escapes supplied text through React and reserves placement space away from scores and controls. With empty configuration it renders nothing. The SportScore attribution is not a paid campaign link and must keep its required dofollow treatment.

## Exact activation prerequisites

1. **Resolve the source ledger.** Confirm rights for the actual proposed commercial activity, scope and secondary sources. Keep restricted surfaces unmonetized and resolve any broader site-level contractual implications. Do not switch on a global ad loader.
2. **Supply actual owner-controlled details.** A real public publisher ID and preferred public contact channel are still required. The selected approach is display ads plus direct sponsorships. Account signup, identity, payment and tax settings cannot be manufactured by the code. Do not put account secrets into public build variables.
3. **Request actual site approval.** Google reviews the whole site and original publisher content. The public verification meta tag or `ads.txt` can connect the site without loading an ad script. A build succeeding is not an approval. [Google's connection and review process](https://support.google.com/adsense/answer/7584263?hl=en), [site readiness](https://support.google.com/adsense/answer/7299563?hl=en).
4. **Check the primary root declaration.** When the real ID is supplied, the Cloudflare root build emits `/ads.txt` with the owner's exact seller declaration. Verify the public file after deployment. The GitHub repository-path mirror intentionally emits neither advertiser verification nor `ads.txt`; its project path is not the origin root. [ads.txt guide](https://support.google.com/adsense/answer/12171612?hl=en).
5. **Configure actual privacy/consent controls.** Before serving ads, update the privacy notice for the actual vendors and cookie use, select the appropriate certified CMP/TCF configuration where required, publish the correct messages and test acceptance, refusal, withdrawal and region behavior. A local-storage flag or homemade banner is not evidence of CMP certification. Google offers its own CMP option through account setup. [Consent requirements](https://support.google.com/adsense/answer/13554116?hl=en), [required privacy content](https://support.google.com/adsense/answer/1348695?hl=en).
6. **Implement and verify serving separately.** This change has no third-party ad-network loader. Adding one requires the real approved slot/account configuration and a working consent flow, with source/page eligibility enforced before requests. Use an isolated review with test-safe network handling; never generate live automated ad impressions or click ads while testing. [Program policies](https://support.google.com/adsense/answer/48182?hl=en).
7. **Measure real results.** Use actual observed visits, search performance and approved advertiser reports. Do not publish invented audience claims, guarantee earnings or treat a search-engine submission as indexing/ranking evidence. Empty, error or unfinished screens are not ad inventory. [Publisher-content requirements](https://support.google.com/publisherpolicies/answer/11112688?hl=en).

Bookmaker affiliate arrangements, payments and premium accounts are not included. Informational sports probabilities are not silently converted into gambling promotions. Google's [online gambling publisher restriction](https://support.google.com/publisherpolicies/answer/10437963?hl=en) has content and regional distinctions; any future promotional betting destination needs its own provider, advertiser and jurisdiction review.

## Verification and integration

Focused tests cover default-off behavior, explicit prerequisites, mixed/unapproved sources, host/path spoofing, supplied public IDs, safe sponsor URLs, static page content/canonicals on both bases, absent placeholder ads, real root declarations and contact-input escaping.

`trustPagesPlugin()` from `build/trust-pages.ts` is registered in the Vite build. The shared `SiteFooter` renders once after routed application content, outside the existing per-page source footers. The primary sitemap includes all four trust pages. Both hosting builds use the Cloudflare primary canonical identity while keeping asset and navigation URLs compatible with their served base. These pages add no dependency or third-party client script; no public account submission has been made.
