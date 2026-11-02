# Phase 8 — V3.0.7 data access review

Reviewed October 29, 2026. Development branch `v3/hybrid-monte-carlo`, draft PR #1. Production remains V2.44.0. This release adds access diagnostics, not a replacement model. **The first genuine forecast milestone is not met.** No new provider account, subscription, trial, dataset upload or live sports-data request was made.

## Findings and decisions

The key change from Phase 7 is BALLDONTLIE's current published permission for analytical/model use through its official API. This does not grant access to endpoints outside an account's tier and does not authorize the existing ESPN-derived ledger. A secure credential is not available in this workspace. The user's earlier All-Star subscription is context, not verified current entitlement.

| Candidate | Classification for APEX | Practical decision |
|---|---|---|
| BALLDONTLIE Free | Suitable under restrictions; incomplete coverage | Implement free-endpoint diagnostics only. No complete training/result source. |
| Existing BALLDONTLIE All-Star | Insufficient coverage | Inspect entitlement without changing the plan. Still lacks plays and lineups. |
| BALLDONTLIE GOAT | Potentially suitable under restrictions | Optional paid future consideration only; no upgrade or converting trial. |
| NBA feeds | Requires provider permission | Restricted for this use; no live access performed. |
| ESPN historical ledger | Requires provider permission | Preserve local records; no publication or newly authorized live use. |
| Basketball-Reference / Stathead | Not permitted under reviewed standard terms | Do not scrape or train; separate grant needed. |
| hoopR-nba-data | Unverified upstream authorization | CC BY package license documented, ESPN provenance also documented. Do not treat packaging as permission clearance. |
| Kaggle NBA Database | Unverified provenance clearance | Dataset license label is not independent verification of underlying rights. |
| Zenodo spatial basketball dataset | Insufficient coverage | Not current NBA identity/event data. |
| SportsDataIO Discovery / trial | Suitable only under restrictions | Free prior-season/personal option does not establish public live operation or free opening-event coverage. Scrambled values cannot grade actual results. |
| Sportradar | Requires scoped provider agreement | No verified permanent free entitlement. |
| The Odds API | Insufficient core-data coverage | Optional market prices only; existing integration preserved, no calls. |
| Independent user observations | Suitable under documented restrictions | Possible future input; no qualifying independent dataset supplied. |

See [the machine-readable audit](validation/PHASE8_SOURCE_AUDIT.json) for thirteen candidates, the twelve requested dimensions, URLs, prices, missing permissions and registration requirements. Classifications are operational decisions for this use, not legal opinions about every use of sports facts. No provider was contacted on the user's behalf.

Primary documentation:
- [BALLDONTLIE terms](https://www.balldontlie.io/terms.html), [NBA endpoint matrix](https://docs.balldontlie.io/), [account inspection API](https://www.balldontlie.io/account/).
- [Sports Reference data use](https://www.sports-reference.com/data_use.html) and [terms](https://www.sports-reference.com/termsofuse.html).
- [ESPN/Disney terms](https://disneytermsofuse.com/english/) and [NBA terms](https://www.nba.com/termsofuse).
- [hoopR data license](https://github.com/sportsdataverse/hoopR-nba-data/blob/main/LICENSE.md) and [provenance README](https://github.com/sportsdataverse/hoopR-nba-data/blob/main/README.md).
- [Kaggle publisher metadata](https://www.kaggle.com/wyattowalsh/basketball), [Zenodo research metadata](https://zenodo.org/records/12698090).
- [SportsDataIO rights](https://sportsdata.io/help/data-rights-and-licensing-questions), [access products](https://sportsdata.io/developers), [scrambled data](https://sportsdata.io/help/scrambled-data).
- [Sportradar NBA API](https://developer.sportradar.com/basketball/reference/nba-overview), [account limits](https://developer.sportradar.com/getting-started/docs/your-account), [official media addendum](https://developer.sportradar.com/sportradar-updates/page/official-media-data-addendum).
- [The Odds API terms](https://the-odds-api.com/terms-and-conditions.html). This is not the similarly named `theoddsapi.com` service.

## Minimum input analysis of the unchanged model

| Class | Inputs | Missing-data behavior |
|---|---|---|
| Essential for calculation | Target date, two NBA teams, five distinct positive player IDs per team, valid schema for supplied prior rows | Invalid identities/rows fail, not silently repaired. |
| Essential for a genuine archived run | Real game ID, aware start time, fresh not-started status, current-team roster evidence, lawful input provenance, valid training cutoff, immutable journal and pre-tip remote receipt | Stop if missing or contradictory. A local output is not evidence of remote publication. |
| Historical empirical foundation | Starter opening flags and first outcomes; rows within the strictly earlier 400-day window | Empty history can mathematically produce priors, but Phase 8 uses this only for synthetic acceptance. It is not the requested trained live milestone. |
| Quality-enhancing | Opening sequences, explicit jump-ball information, known shot results/categories, reliable injury reports, provider-confirmed starters | Existing shrinkage and documented assumptions remain. Missing injuries are unchecked; projections stay projections. |
| Optional | Timestamped bookmaker odds, comparison-market information, advanced secondary statistics | No odds calls needed for model calculation. No ROI without prices. |

The engine already permits **unconfirmed but valid current-team projected fives** as research. It does not require pretending they are official. However, schedule + player names + old starters alone cannot prove today's team membership or resolve different providers' ID namespaces. The new general BDL player parser explicitly does not claim active-roster verification. Free player IDs must not be copied into ESPN historical rows merely because both are integers.

Reduced-data configurations:
1. Valid authorized history, current roster, projected fives, no injuries or official confirmations: mathematically supported research configuration, warnings retained, not actionable.
2. Valid history without detailed sequences: existing empirical fallbacks/assumptions apply; less evidence, not equivalent to the full sequence model.
3. No valid current roster/five or no safe start-time/status: do not generate.
4. Empty history: fixture-only here. This does not establish an empirical NBA forecast.
5. New licensed source: requires an explicit reviewed identity mapping, a real schema migration and coverage/parity audit before connection to the live runner. The Phase 8 diagnostic parser is not that migration.

## Existing training candidate

The Phase 7 audit is preserved, not relabeled as newly collected data: 1,110 source games, 1,106 validated outcomes in the full ledger; October 28 exclusive cutoff selected 782 records, 780 training games / 7,800 rows / 780 sequences, and retained two ambiguous records. The candidate remains unapproved and was not published. No permission allowing private automated use of that source was established in this phase. Compression/encryption does not resolve that issue.

`phase7_training.py` remains unchanged, including deterministic hashes and the 400-day window. Its schema is ESPN-specific; no alternative source is disguised as ESPN. The prior 0.0 compact/original parity result remains an offline format check, not a new performance result. No replacement dataset was imported and no frozen evaluation was rerun or tuned.

## Exact next steps without spending

1. On the user's trusted machine, inspect the existing BDL account using the safe read-only commands in `PHASE8_LIVE_OPERATIONS.md`. Keep the key in the existing environment/secret store, never chat or GitHub source.
2. Establish permitted historical opening-event data. Options are an actual source grant, an independently licensed compatible dataset with reviewed provenance, or documented independent observations. Existing All-Star alone does not fill this gap.
3. Validate current roster and cross-provider identities; retain the projected label unless genuine pre-tip provider evidence exists.
4. Review a concrete data-storage arrangement and perform one manual genuine forecast with the unchanged Phase 7 model. Independently verify publication before tip-off; grade later only from a permitted result source.
5. Only then request the separate dispatcher installation/scheduling decision. No approval is being inferred from this document.

There is no demonstrated end-to-end zero-new-cost live source today. This is a recorded limitation, not a reason to invent a forecast, reuse restricted data through another host, or purchase a subscription.
