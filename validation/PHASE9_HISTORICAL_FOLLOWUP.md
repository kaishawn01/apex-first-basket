# Phase 9 follow-up: opening-event sources
Reviewed October 29, 2026 (America/New_York). Documentation-only investigation; no account checks, sports API requests, registrations, trials, downloads or paid services.

The user completed local BALLDONTLIE authentication. Account access is no longer the authentication blocker. This records the user's local evidence, not a repeated cloud inspection. Private account dates and responses are intentionally omitted. Existing Phase 9 results remain an accurate record of the earlier run.

## Decision
A genuine empirical pre-tip forecast is **not yet feasible through an authorized, validated replacement path**. No source has passed permission, recent-game coverage, identity mapping and unchanged-model input validation together. No model code, weights, experiment rules, V2.44 installation or scheduler was changed.

## New candidate: DunkAPI — investigate, not cleared
Official terms allow stored data, research/model training and derived products, including on Free, but prohibit standalone dataset redistribution. They reserve third-party restrictions and do not establish NBA-specific upstream clearance. Free accounts receive a balance top-up to 500 credits monthly, not accumulating monthly allocations. No account was created.
Sources: https://dunkapi.com/terms and https://dunkapi.com/docs/timing-and-rights

The provider advertises play-by-play from 2003–04, including recent seasons, with IDs and scoring events. Per-game plays cost 10 credits. A per-game-only import therefore gets at most 50 calls from 500 credits before any other work; pagination may reduce games obtained. Seasonal/team queries exist, so this is not a proven global maximum for all possible retrieval strategies. Bulk query limits and completeness are untested.
Source: https://dunkapi.com/data/nba-play-by-play

The published response includes sequence, period, clock, scorer/player IDs, points, score and shot result. FT attempts are supported. Validate all event types and pagination; do not use shots-only filtering for a complete opening sequence. Game box scores are another 5-credit call; historical starter completeness must be checked. One plays call plus one box-score call per game implies at most 33 such pairs per 500 credits, before lookup/pagination overhead. This is planning arithmetic, not observed throughput.
Sources: https://dunkapi.com/docs/get-plays and https://dunkapi.com/docs/get-game

Compatibility risks: expected_points uses later seasons and must be excluded from chronological features. The provider overwrites corrections without record revision history, so APEX would need its own immutable retrieval/hash archive. Daily updates do not replace fresh pre-tip status/lineup evidence. A source list per dataset is not published.
Source: https://dunkapi.com/docs/timing-and-rights

## Other routes
- SportsDataIO Discovery: documented free prior-season personal/noncommercial access; public-facing products need a different scoped license. The fetched dynamic endpoint page did not establish whether free NBA access includes complete opening play-by-play. This is an unresolved coverage question, not a confirmed refusal. Request a no-cost research arrangement covering events and cloud use; no registration, trial or inquiry was performed.
  Sources: https://sportsdata.io/help/data-rights-and-licensing-questions and https://discoverylab.sportsdata.io/developers/api-documentation/nba
- Aalto / Zenodo Temporal Networks: university metadata labels CC BY 4.0, describes 1,101 NBA games from 2014–15 and disclaims ownership/correctness of underlying data. It may support a separate reproducibility investigation, but cannot supply the frozen current 400-day window. Detailed event identities and upstream scope were not validated; no archive downloaded.
  Sources: https://research.aalto.fi/en/datasets/temporal-networks-football-handball-basketball/ and https://zenodo.org/records/160509
- NBA/ESPN-derived mirrors remain the same upstream permission question, not independent new permission. The earlier Phase 8/9 audit is preserved. No mirror was used to bypass that boundary.
- Existing All-Star aggregates cannot reconstruct event order, opening misses or free throws. No upgrade or endpoint probe was made.

## Exact input acceptance requirements
1. A permitted dataset or provider arrangement covering automated retrieval, retained private cloud processing, model training/evaluation and derived forecast publication. Keep any provider-restricted source bundle out of the public Git data branch.
2. Recent completed regular-season games inside the strictly earlier 400-day window. The registered primary evaluation requires at least 100 prior training games; this is an eligibility floor, not a claim of adequate accuracy. Older academic history cannot substitute without changing frozen rules.
3. Stable game identity, scheduled time/date, both teams and historical observed starter identities; ordered events sufficient to distinguish first FG attempt, first made FG and first points including FT. Preserve bench/unknown outcomes, missing events and exclusions. Opening jump-ball/possession, rebounds, turnovers and substitutions require explicit evidence or the existing documented fallback, never invented observations.
4. Independently reconciled native player/team/game namespaces. Matching integer IDs or names is insufficient. Confirm event actor roles and historical team ownership; current trades must not rewrite history.
5. A source-native adapter and like-for-like probability/input tests. The current phase7_training.py explicitly checks ESPN provenance; relabeling another source to bypass it is prohibited. This integration is not yet implemented, and no frozen mathematics may change.

Resolving history alone also does not prove current roster mapping, fresh unstarted game status or successful pre-tip remote publication. Projected fives can remain projected research inputs; postgame starters cannot become pre-tip confirmations.

## Proposed inquiry — not sent
For DunkAPI or another willing provider: can you confirm the source and applicable upstream restrictions for NBA opening events, and permit no-cost automated private cloud research plus public derived probabilities? Can a no-card, non-trial arrangement supply at least 100 recent complete games with historical starters, IDs, FTs, opening attempts and all intervening events? Please specify query/page limits, correction handling, retention, cross-provider ID evidence and any additional restrictions. No payment, trial, subscription or paid overage is authorized.

Recommendation: clarify DunkAPI's NBA-specific provenance and feasible free retrieval volume first; in parallel consider a scoped SportsDataIO no-cost research grant. These are inquiry candidates, not obtained licenses. Sending a provider message requires separate user instruction. No genuine prediction or new accuracy claim is made.
