# T20 chase model research

This is a separately trained in-play model candidate. **It is research only and does not publish live probabilities.** The existing season qualification solver is not reused. Scores and bookmaker prices do not depend on this model being available.

Reproduce from the repository root, using the existing Python environment with NumPy and locally cached Cricsheet archives:

```sh
venv/bin/python -m live_model.pipeline --cache .cache/cricsheet --output live_model --cutoff 2026-10-23
venv/bin/python -m unittest tests.test_live_model -v
```

No network requests, provider credentials, installations or paid services are used. The pipeline writes a compact `candidate.json` and detailed `evaluation.json`; neither contains delivery records or player identities. Source archive hashes identify the exact local inputs. A source archive update can change the results, even with the same cutoff. The filename `wbb` denotes Women's Big Bash in this cache.

## Outcome and input contract

The target is the probability the **chasing team wins a standard, unreduced club T20**, conditional on completion with a non-tied regulation winner. This does not estimate the chance of rain/no result, a tie or super-over victory. Training data cannot establish whether a full-length historical match had a temporary weather stoppage; matches with a recorded result method, shortened allocation or revised target are excluded.

Only second innings with the full 120 legal-ball allocation are researched. Required live fields are `format: 'T20'`, `innings: 2`, `scheduledBalls: 120`, integer `runs`, `wickets`, `legalBalls`, `target`, `gender`, a supported `competition` key, `status: 'live'`, and a nonempty `scoreRevision`. The provider adapter must independently verify `targetRevised: false`, `interruption: false` and `superOver: false`; an omitted flag is unknown and suppresses inference. The adapter must not infer an unrevised target from first-innings runs alone.

`17.5` overs means 107 legal balls, never 17.5 or 105 balls. Wides and no-balls change the score without advancing legal balls. Terminal states, unknown targets, first innings, revised targets, unsupported categories/competitions, ODI/Test/Hundred/T10 and super overs return unavailable. No probability history is reconstructed from these offline outcomes.

`inference.mjs` exports `predictChase(state, artifact, options)`. Its production default refuses an artifact whose release status is not `released`. `allowResearch: true` exists for explicit shadow tests only. An available shadow output carries `researchOnly: true`, `inputScoreRevision`, the version, both complementary probabilities and the outcome conditioning. Never pass the research override in a public route. The live service currently lacks the verified input contract, independently of the model's statistical gates.

## Method and leakage controls

The fixed features use runs needed, balls remaining, wickets remaining, required rate, target rate, a gender indicator, resource/rate interactions and quadratic terms. They do not use final score, winner information, player identity, future deliveries, market prices or the season solver. Features are standardized using the training partition only.

A ridge logistic regression is fitted using deterministic weighted Newton optimization, followed by a one-dimensional Platt calibration fitted only on 2023 matches. Each match contributes total weight one, shared across its sampled states, so long chases do not dominate. The state sample is innings start plus every six legal balls, excluding terminal states. Performance at every individual delivery, including intermediate illegal-delivery states, remains unverified.

Splits are fixed whole-match chronological periods. A match ID is globally deduplicated during load and duplicate IDs are rejected by the splitter. No delivery can cross a partition. No random ball-level split is used:

| Partition | Dates | Matches | Men | Women |
| --- | --- | ---: | ---: | ---: |
| Training | 18 Apr 2008–31 Dec 2022 | 2,437 | 2,112 | 325 |
| Calibration | 1 Jan–31 Dec 2023 | 395 | 321 | 74 |
| Held-out test | 1 Jan 2024–16 Sep 2026 | 1,042 | 914 | 128 |

The cutoff is **23 October 2026**, not the execution host's date. Records dated after it are excluded. The cached corpus supplies 11 club competitions across men's and women's cricket. There is no claim of international, associate or worldwide model coverage. IPL, BBL, BPL, CPL, PSL and LPL appear in training; ILT20, SA20, MLC and WPL begin in later partitions and therefore provide transfer evidence rather than in-competition training evidence.

## Recorded evaluation

These results describe this candidate and its exact archive hashes. Lower scores are better. Brier score is mean squared probability error, log loss penalizes confident errors, and ECE is the weighted absolute difference between forecasts and observed outcomes in ten fixed probability bins. ECE is not an accuracy percentage or an uncertainty interval.

| Held-out predictor | Brier | Log loss | ECE, ten bins |
| --- | ---: | ---: | ---: |
| Constant 50% | 0.2500 | 0.6931 | 0.0576 |
| Training match chase-win prior | 0.2471 | 0.6873 | 0.0204 |
| Training-only coarse resource buckets | 0.1609 | 0.4956 | 0.0840 |
| Calibrated logistic candidate | **0.1227** | **0.3793** | **0.0379** |

The resource baseline uses gender, coarse innings phase, required-rate and wicket buckets with smoothing toward the training prior. The model beats all declared baselines on aggregate Brier and log loss. A constant prior can have a low aggregate calibration error while providing little state discrimination; calibration alone is insufficient.

| Held-out group | Matches | Brier | ECE |
| --- | ---: | ---: | ---: |
| Men | 914 | 0.1223 | 0.0355 |
| Women | 128 | 0.1253 | 0.0546 |
| Powerplay (0–36 legal balls) | 1,042 | 0.1607 | 0.0611 |
| Middle (37–90 legal balls) | 1,037 | 0.1074 | 0.0321 |
| Death (91–119 legal balls) | 886 | 0.0701 | 0.0192 |

Snapshots of a match are correlated. Match counts, match-balanced scores and complete calibration bins are reported; independent-delivery standard errors would misstate confidence. The current report does not supply bootstrap confidence intervals. Per-competition results and all sample counts are in `evaluation.json`.

## Release gates and current decision

The thresholds were written before the first candidate evaluation. There was no search over features or hyperparameters using this test set. After viewing these results, this held-out set becomes development evidence; a later candidate needs a new untouched holdout before release.

The aggregate gates pass: at least 500 test matches, improved Brier versus 50%/prior/resource baselines, improved log loss versus the resource baseline, ECE at most 0.05, and phase ECE at most 0.08 with at least 200 matches per phase. **The candidate fails the gender coverage gate:** at least 200 held-out matches per gender are required, but women have 128. Women's ECE is below the 0.07 gender limit; insufficient independent matches remain a blocker.

A competition also needs at least 100 test matches, ECE at most 0.08, and Brier no worse than the resource baseline before becoming a shadow inference candidate. Only **BPL** meets all three in this dataset. IPL has 205 matches but ECE 0.0847; PSL has 103 but ECE 0.0846; WPL has 65 and ECE 0.1035. Other competitions have fewer than 100 held-out matches. These are descriptive support filters, not a production approval and not evidence of broad women's model support.

**Independent model review and live provider replay/correction validation have not passed.** Together with the failed cohort gate, this keeps `release.status` set to `research_only`. Editing that string to publish the model would bypass the release process. There are currently no released competition probabilities.

Further release work requires new held-out data, stronger cohort evidence, per-delivery/score-correction replay, verified live target/allocation/weather inputs, independent model review and a decision on uncertainty and drift monitoring. First-innings, DLS, international and other-format models remain separate research.

## Data attribution

Historical JSON data are from [Cricsheet](https://cricsheet.org/), used under the [Open Data Commons Attribution License](https://cricsheet.org/using/). Source format: [Cricsheet JSON](https://cricsheet.org/format/json/). The artifact and report retain attribution and archive SHA-256 hashes. No raw archives or delivery data are copied into this module.
