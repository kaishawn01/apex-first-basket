# Phase 9 — source-native migration design, not an implemented importer

**Level C is not attempted:** no authorized compatible sample exists. Adding a guessed provider parser would create false confidence. The existing ESPN-specific `phase7_training.validate` remains strict. Do not relabel BDL or another provider as ESPN to pass it. No schema gate, source hash, experiment weight, trial count, seed, decay, calibration or Other handling is weakened.

## Required contract before implementation

1. Quarantine the permitted sample outside user history. Bind a source review to its exact bytes/hash, retrieval timestamp, permitted scopes, original URL/version and provider namespace. A license label alone cannot satisfy an unresolved upstream restriction.
2. Preserve native game/team/player/event IDs. Validate scheduled UTC timestamp and provider date against the game's Eastern date. Keep raw ordering metadata; reject duplicated or contradictory event IDs/order. Never order by a text clock alone.
3. Establish an independently reviewed game/team/player crosswalk. Numeric equality and name similarity are not identity evidence. Current roster mapping and historical game membership are different checks. Trades must not rewrite historic ownership. Save mapping evidence/version with transformed records.
4. Preserve distinct facts: opening jump-ball participants/winner, first possession, first FG attempt, first made FG, and first points (including free throws). Identify actor roles explicitly; the first listed participant is not universally the shooter. A missing first-score event stays unresolved, never assigned to a starter. Preserve nonstarter/unknown scorer categories and substitutions.
5. Record missing intervals, ambiguous identities, event corrections and source completeness. Do not infer absent turnovers/rebounds/free throws as zero or use later games to fill earlier gaps. Fail incomplete records out of empirical sequence training with a retained exclusion reason.
6. Only then extend the existing schema with an explicit versioned source adapter and matching provenance validator. Keep original records immutable, migration outputs separately named and import checkpoints transactional/idempotent. Do not alter frozen registered source files to disguise an experiment change; review integration separately.
7. Test like-for-like mapped fixtures against the unchanged baseline/simulator with the registered settings. Check player/category probabilities and total mass, including Other. Report actual input-coverage differences. No like-for-like authorized sample exists in Phase 9, so no new source parity is claimed.

## Feature gaps and readiness

The unchanged model needs correctly identified starter histories and first-score/shot flags to estimate empirical shares. Opening sequences support possession, conversion, FT, turnover and rebound estimates. Schedules and box-score aggregates cannot recover those facts. Current roster and fresh start/status evidence are required for a controlled genuine forecast. Pre-tip provider confirmation is a separate evidence requirement; postgame starter flags cannot supply it. Projected fives remain research projections.

## Existing tests reused

Phase 3–7 tests already cover missing/bench/free-throw first scores, sequence ordering, invalid identities, source hash mismatch, immutable journals, duplicate retries, failed publication and rollback. Phase 9 adds account-state/redaction and explicit numeric-ID-collision tests. These are synthetic regression evidence, not proof that a new provider dataset has been migrated.

After an authorized dataset exists: implement this contract on a small quarantined sample, review exclusions and parity, approve exact storage/input hashes, then use the existing Phase 7 collector and Phase 6 publication receipt path. Until then, no genuine forecast, primary experiment change, dispatcher installation or public training upload is justified.
