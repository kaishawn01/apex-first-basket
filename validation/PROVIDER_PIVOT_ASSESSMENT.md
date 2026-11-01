> 2026-11-01 clarification: the owner has now supplied Noah/DunkAPI's permission response summary. Earlier “unsent/unresolved response” statements below describe the prior assessment. See ../PHASE10_DUNK_PILOT.md for current evidence status, manifest and remaining balance/authorization gates. NBA rights are not independently cleared.

# Historical provider pivot assessment

Reviewed 2026-11-01. Documentation-only assessment against development commit `34ee5cee8af36671a0b112964d72139870e5c5f2`, V3.0.9, existing draft PR #1. No account diagnostics, provider API requests, credits, subscriptions, source downloads, model changes or scheduling activation. Phase 10 fixtures were not repeated. Public documentation establishes advertised capabilities, not actual account coverage or upstream clearance.

## Decision and ranking

**Recommended combination: retain BALLDONTLIE for pregame context; pursue DunkAPI permission clarification for historical events. Treat Discovery Lab as a conditional fallback, not a verified replacement. No route yet establishes an operational, authorized frozen-model forecast.**

| Priority | Route and useful role | Decision |
|---|---|---|
| 1 | A: existing BALLDONTLIE All-Star, pregame backbone | Authentication already resolved. It cannot fill the historical event gap. |
| 2 | B: DunkAPI, closest documented historical format | Preserve existing five-game preparation and unsent inquiry. Permission, pagination, mapping and sample scale remain gates. |
| 3 | C: Discovery Lab, possible personally licensed historical alternative | Starter fields are documented, but complete free play-by-play and a named available season are unverified. Obtain feed-specific confirmation before integration. |

These rank practical roles, not prediction accuracy. None demonstrates a betting edge.

## Ten-point comparison

| Requirement | A: BALLDONTLIE All-Star | B: DunkAPI Free | C: SportsDataIO Discovery Lab |
|---|---|---|---|
| Permission | Terms permit lawful analytics/model use, subject to third-party rights and feed-substitution restrictions [A2]. No new rights to old ESPN records. | Research/retention permissions coexist with upstream restrictions; NBA-specific scope remains unresolved. Account creation date determines applicable terms transition [B1]. | Free prior-season personal/noncommercial research is advertised; public-facing/business use needs separate commercial scope [C1,C2]. |
| Frozen 400-day coverage | General game history advertised; All-Star lacks plays. Dates alone do not satisfy event training. | Advertised history since 2003–04 includes recent seasons [B5]; actual eligible coverage untested. | “Last season” advertised, not a verified numeric NBA season. If 2025–26, it overlaps the current window; 2024–25 regular season does not. |
| Ordered opening events | Plays are GOAT-only [A1]; unavailable under this route. | Sequence, clock, scores and actors documented; paging and missing opening events require validation [B3]. | Free ordered play feed not established. Commercial play-by-play documentation cannot prove free entitlement. |
| Historical five | Dedicated lineups are GOAT-only and post-start [A1]. | Box-score starter flags documented [B4]; must obtain five distinct players per side. | Dictionary includes single-game Started flags [C3]; actual endpoint access/completeness untested. |
| FT / first score | Aggregate stats cannot establish scoring order. | FTs and shot results documented; derive first positive score change and preserve unknown/nonstarter identities. | Box-score totals cannot establish which FT or basket occurred first; ordered feed required. |
| ID mapping | Native game/player/team IDs. No assumption that they equal ESPN IDs. | Source-native IDs require evidenced crosswalk, even when numeric values resemble ESPN. | Stable career PlayerID documented [C3]; separate namespace and game/team mapping required. |
| Model schema | Supports context adapter, not missing sequence fields. | Closest field-level candidate; Phase 10 deliberately reports model_compatible=false. | Starter/identity fields are partial support; no verified sequence mapping. |
| Current/pre-tip | Games support discovery/status. Active players and injuries are documented All-Star benefits; projected rosters are not official starters. No calls made. | Daily historical refresh is useful for results, not reliable last-minute starter confirmation [B6]. | Free historical access does not establish current-season status or pre-tip confirmation. |
| Cost / limits | Published All-Star $9.99/month, 60 requests/minute [A1]; existing subscription, no added purchase. Remaining quota/overage settings not established by prior authentication. | Published $0, 500 monthly free credits. get_game=5, get_plays=10. Actual remaining free balance unverified [B2–B4]. Pilot remains capped at 100. | Free prior-season offer verified; exact free NBA request limits, complete endpoint inventory and account entitlement unresolved. No signup/trial initiated. |
| Smallest permissible next check | Documentation and existing local schemas now. If owner later permits requests: one bounded game-date query using free Games endpoint; separately approve All-Star-only injury/active-player refresh. No reauthentication needed. | Written applicable permission evidence first, then owner approval of exact five IDs, requests, storage and free-only budget. No live request now. | Obtain named season, free endpoint catalog, limits and personal retention/model-use scope; then approve a single completed-game starter-plus-play sample if actually free. |

## Minimum data and compatibility work

For a 2026-11-01 prediction, the strict earlier-date 400-day window is 2025-09-27 through 2026-10-31. Recalculate for each forecast date; same-day outcomes are excluded. A five-game pilot tests source structure only. It does not satisfy the registered 100-prior-game primary evaluation eligibility criterion, team/player sample reliability or establish accuracy. That criterion should not be confused with mathematical ability to emit prior-based probabilities.

Required historical evidence: unique game/date/team identities; ten distinct historical starters; first FGA/shooter; actual first score including FTs; ordered opening possessions with the shot, turnover, rebound and foul semantics consumed by the existing simulator; explicit unknown/nonstarter outcomes; source retrieval timestamps and provenance. Missing jump-ball or other evidence must remain missing under existing assumptions, not be invented. Preserve exclusion reasons and probability mass.

Crosswalk games using scheduled time, season/type and both teams; resolve postponements explicitly. Map players with source-bound IDs and corroborating identity/team-at-game evidence, never name-only or numeric-ID equality. Record ambiguous matches for review. Historical team membership differs from today's roster.

Inspection of `phase7_training.py` shows schema-2 provenance accepts ESPN specifically and checks an ESPN permission grant. `phase7_live.py` also has source-specific pregame gates. A reviewed provider-aware adapter, truthful provenance permissions and equivalence checks are required before another source can enter the frozen engine. Do not relabel records ESPN or bypass the gate. This assessment changes no adapter, model weight, trial count, calibration or protocol.

Historical box-score starters are retrospective observations, not evidence of pre-tip confirmation. Exclude provider expected-points models, postgame totals, retrospectively fitted ratings and win probabilities from chronological features. DunkAPI documents retrospective modeling and overwritten revisions [B6]; a newly retrieved historical record is not an original pregame snapshot.

## Pilot and larger-sample economics

Five initial get_game/get_plays pairs cost **75 credits** at published prices. Two extra plays pages yield 95; a further 10-credit call must stop. Lookup calls, failures and retries must fit the same lifetime 100-credit cap, not a renewed budget. The documented default plays page is 200; a larger requested limit is not proof of completeness. Verify terminal pagination, event counts and opening/score continuity. A cap hit may leave fewer than five complete games.

For this per-game plan, 500 free credits cover at most 33 initial pairs before extra pages/lookups. One hundred initial pairs require 1,500 credits; pagination increases this. Thus the allowance can test compatibility but cannot quickly fund that sample using this plan. Bulk-query efficiency is unverified. Published Starter is $19/month for 10,000 credits and Pro $49 for 30,000, with wallet-rate overages [B2]; these are comparisons only, neither authorized nor activated. ChatGPT Work credits do not add provider credits. Free monthly replenishment is not permission to repeat the pilot or accumulate unapproved calls.

## Shortest safe path and owner decisions

1. Resolve the existing **unsent** DunkAPI inquiry in `PHASE10_DUNK_PILOT.md`: NBA upstream restrictions, applicable terms, private originals/hashes retention, model research/derived output scope, complete-game pagination and free-only billing. Owner may send it or explicitly authorize sending; no message has been sent here.
2. In parallel, ask Discovery Lab for the exact free NBA season/feed list, whether full ordered plays including FTs and starter flags are included, and retention/model-use terms. A dictionary alone is insufficient. No trial is needed merely to ask.
3. If DunkAPI clears those gates, obtain owner approval for five named, in-window completed games, at most 100 free credits, and permitted private storage. Verify balance without exposing the key. Do not interpret general approval of this assessment as request authorization.
4. Only after permitted samples demonstrate compatibility, scope the small provider adapter/crosswalk review and a separately approved eligible training inventory. Reusing existing history requires rights for that source; a new API subscription does not retroactively authorize it.
5. Use existing BALLDONTLIE game discovery/identity context; separately authorize any entitled injury/active-player calls under the current no-paid-only-endpoint constraint. Preserve timestamps and label projections honestly. Current team/availability and a fresh not-started check must precede saving a real forecast.
6. Save the first private, timestamped research forecast using the unchanged frozen model only after authorized training and source integration gates pass. Unconfirmed lineups remain a research cohort, never provider-confirmed or actionable by implication. Keep existing eligibility and timing rules intact; no automatic scheduling or public deployment.

No independently licensed alternative with verified recent ordered NBA events was established by this review. Public mirrors, software licenses and old academic datasets are not substitutes for verified dataset provenance and in-window coverage. This is not proof no alternative exists.

**Remaining blocker:** a permitted, sufficiently populated and semantically validated opening-event training source, plus reviewed source/ID integration. Pregame context alone and five synthetic games cannot remove it. No genuine new pre-tip forecast is claimed. V2.44, the frozen model, existing data and deployment controls remain unchanged.

## Sources

Public documents reviewed 2026-11-01; published prices are not account balance or billing-control verification.

- [A1 BALLDONTLIE NBA documentation](https://docs.balldontlie.io/)
- [A2 BALLDONTLIE terms](https://www.balldontlie.io/terms.html)
- [B1 DunkAPI terms](https://dunkapi.com/terms)
- [B2 DunkAPI pricing](https://dunkapi.com/pricing)
- [B3 get_plays](https://dunkapi.com/docs/get-plays)
- [B4 get_game](https://dunkapi.com/docs/get-game)
- [B5 NBA historical coverage](https://dunkapi.com/data/nba-play-by-play)
- [B6 Timing and rights](https://dunkapi.com/docs/timing-and-rights)
- [C1 Discovery Lab](https://discoverylab.sportsdata.io/)
- [C2 SportsDataIO rights](https://sportsdata.io/help/data-rights-and-licensing-questions)
- [C3 Discovery NBA dictionary](https://discoverylab.sportsdata.io/developers/data-dictionary/nba)
- [C4 Discovery NBA endpoint documentation](https://discoverylab.sportsdata.io/developers/api-documentation/nba): retrieved page contained unresolved template placeholders; do not infer access denial or full entitlement from that rendering.
