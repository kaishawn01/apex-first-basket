# Phase 9 — V3.0.8: entitlement diagnostics and source decision

**Live acceptance remains blocked.** Continued the existing branch and draft PR #1. No account credential was accessible; zero account/sports API requests, zero new historical games and zero genuine forecasts/results. Main remains V2.44.0. No subscription, trial, paid endpoint, scheduler, dashboard or training-bundle deployment was activated.

Extended `phase8_access.py` with a two-read local `inspect` command, hidden key entry, sanitized NBA subscription/renewal observations and documented quota reporting. Expired/malformed/inactive evidence fails closed. A failed entitlement refresh now revokes the previous in-memory grant. Unknown response values cannot leak through diagnostic output. Paid endpoints remain disabled regardless of the reported tier; existing budgets, cooldowns, official paths and GET-only transport are preserved.

The material provider finding is that BDL lineups are documented as available only after game start. They cannot certify pre-tip starters. Existing All-Star access is unverified and would not provide Plays. The source follow-up did not establish a compatible permitted zero-new-cost replacement. The new migration document is a design, not a speculative importer or a completed source mapping. No alternative provider is mislabeled as ESPN.

Local regression: 601 tests, 593 passed, eight PostgreSQL-only tests skipped locally; 21 new Phase 9 tests. Full Streamlit smoke passed. GitHub CI passed on Python 3.11 and 3.14 with PostgreSQL, full Streamlit smoke and checksum verification (runs 40913328519 and 40913335824). The existing synthetic cloud workflow passed on three fresh runners (run 40913328521; 84 total job-seconds). One synthetic forecast and result survived independent retrieval; prediction/protocol hashes exactly match the prior fixture. Earlier data-branch files remain byte-identical. Exact evidence and the remote receipt are in `validation/PHASE9_RESULTS.json`.

The 1,110-game ledger passes a read-only SQLite integrity check; 1,106 resolved outcomes and the prior 780-game training candidate are preserved. Model source, frozen evaluations, Phase 7 registered protocol/settings and dispatcher remain unchanged. No accuracy optimization or new independent performance claim is made.

Acceptance: **A blocked** (credential unavailable); **B blocked** (no verified complete source); **C not attempted** (no authorized sample to migrate); **D blocked** (data prerequisites); **E not attempted** (no genuine pre-tip publication). Synthetic cloud success cannot satisfy these levels.

See `PHASE9_ENTITLEMENTS.md` for the trusted-computer command, `PHASE9_HISTORICAL_SOURCES.md` for ranked sources and an unsent permission inquiry, and `PHASE9_DATA_MIGRATION.md` for source-native requirements. These boundaries are the next task, not additional simulator complexity.

---

# Phase 8 — V3.0.7: data access and controlled live readiness

**Status: no genuine NBA forecast yet.** The existing V3 branch/PR is continued, not rebuilt. Main/V2.44 is untouched, the dispatcher remains a disabled template, and no paid service or trial is enabled.

The source audit covers thirteen options. BALLDONTLIE now documents analytical/model permission, but Free and the reported All-Star tier do not provide the plays needed to replace the ESPN-derived history. The actual account/key is unavailable in this workspace. Open dataset labels do not establish a separate upstream grant; no complete zero-new-cost replacement was verified. See `PHASE8_DATA_ACCESS.md` and `validation/PHASE8_SOURCE_AUDIT.json` for sources and exact scope/coverage gaps.

Implemented `phase8_access.py`: read-only account inspection, zero-cost endpoint allowlist, persisted 20-attempt daily limit, 13-second spacing, explicit 429 cooldown, no automatic retries/redirects/billing mutations, redacted diagnostics, and separate provider identity parsing. Source-review evidence and cross-provider mapping validators reject missing/stale/ambiguous evidence. This diagnostic client is not a complete replacement live provider adapter; it does not authorize ESPN training or enable a paid BDL endpoint. The new mobile-friendly Phase 8 panel performs no provider calls.

The model, Phase 5 frozen hashes, Phase 7 source files and registered configuration are unchanged. A V3.0.7 test wrapper exercises the existing 3.0.6 model protocol with explicitly synthetic fixtures. It must never be used to disguise a genuine prediction's version. No historical or prospective accuracy claim is added. The October 28 training candidate remains unapproved: 782 records, 780 usable training games, two ambiguous outcomes. No additional historical data was collected, uploaded or silently remapped.

Local validation: **580 tests, 572 passed, eight PostgreSQL-only tests skipped; 26 new Phase 8 tests**. Full Streamlit smoke and the new no-network panel test passed. The resumed environment initially lacked dependencies; a fresh isolated environment installed unchanged requirements before the successful regression run. GitHub CI on Python 3.11/3.14 passed with PostgreSQL, full Streamlit smoke and checksum validation (runs 40908959780 and 40908949696).

Remaining: permitted opening-event history, secure existing account inspection, validated current-roster/ID mapping, genuine pre-tip remote publication and later verified outcome. No real forecast, live outcome, unattended scheduler or public dashboard is claimed. The earlier integrity root cause remains unresolved. Next phase should resolve these data prerequisites and perform one controlled observation rather than retune the model.

Actual cloud observation: [Phase 8 run 40908949521](https://github.com/kaishawn01/apex-first-basket/actions/runs/40908949521) passed on three fresh runners: generation/publication 26 seconds, reconciliation 30 seconds, independent read/dashboard verification 32 seconds (88 job-seconds, excluding queue/CI). Exactly one **synthetic** forecast and one synthetic result were durably saved under `fixtures/69aacf22d699b0436c026fc72885f8a76957c0d6/`. Original timestamp and forecast hash are identical to the Phase 7 fixture, confirming unchanged fixture mathematics/settings. The remote publication receipt was independently retrieved. This is not an actual NBA forecast and remains excluded from prospective metrics.

The existing local ledger was checked read-only: SQLite integrity OK, 1,110 games, 1,106 resolved outcomes. Genuine forecasts, genuine graded outcomes, new historical imports and sports/account API requests in Phase 8 are all **zero**. No scheduler or deployment was activated.

Operations: `PHASE8_LIVE_OPERATIONS.md`. Machine-readable evidence: `validation/PHASE8_RESULTS.json`.

---

# V3 Phase 7 review — development VERSION 3.0.6

**Not technically complete for live NBA acceptance.** Phase 7 implements and tests the controlled live path, but permissible historical/source access has not been established, so no genuine live forecast was generated. No schedule, public dashboard, paid provider or V3 merge was activated. Main/V2.44 remains unchanged; PR #1 stays draft.

## Findings and implemented changes

The existing Phase 6 cloud fixture was independently rechecked and manually rerun again (run 40809534434, attempt 3); all three jobs passed and the original single synthetic forecast/result remained unchanged. The existing historical ledger contains 1,110 games, 1,106 validated first scores. Frozen Phase 5/6 model/experiment files and the February artifacts are preserved.

The source-rights audit found no recorded permission covering the ESPN-derived training data or automated live collection. Disney's published terms explicitly restrict automated extraction and model-related use. No new live sports-provider requests were made under this uncertainty. A private repository or encryption would not resolve licensing. No paid-source account entitlement was assumed.

`phase7_training.py` builds a deterministic allowlisted candidate from read-only SQLite and validates identities, complete outcomes, source hashes, typed sequences and exclusive 400-day cutoffs. The October 28 candidate contains **782 window records, 780 validated training games / 7,800 rows, 780 sequences and two retained ambiguous outcomes**; 328 older records are excluded. It is **7,936,079 bytes / 547,793 compressed** and was not published. Only aggregate audit metadata/hashes are committed. The builder remains reproducible for owner/provider review.

An offline serialization-parity check used the existing model on the original and compact training data with the same settings: **maximum probability difference 0.0; first-shot vectors identical**. This is a data-format test, not a genuine forecast or new accuracy evaluation. See `validation/PHASE7_PARITY.json` and `validation/PHASE7_TRAINING_AUDIT.json`.

`phase7_live.py` reuses the existing forecast function, simulator, provider transport, immutable journal, Git publication and outcome grader. It declares `apex-v3.0.6-live-01`, keeps all model weights/trials/seeds and primary timing rules unchanged, binds permission evidence to the candidate hash and expires stale grants. Paid providers remain blocked. Each generated forecast is published immediately; any publication failure stops the batch. New manual invocation IDs produce new snapshots, while retries deduplicate. Cutoffs, bundle/provenance hashes and top-five candidates are archived.

The dispatcher under `deployment/phase7-dispatcher.yml.example` is review-only, pins the reviewed implementation SHA, accepts no arbitrary code ref, uses public standard Ubuntu runners, limited permissions/timeouts/concurrency, and requires separate global/live/data-permission decisions. It is not installed on main. Four proposed Eastern wakeups reserve at most 320 of the unchanged 400 attempts/day; precise near-tip capture is not guaranteed. Early forecasts remain secondary observations instead of weakening the primary experiment.

The existing dashboard gains a read-only live-readiness summary. It separates real forecasts, verified pre-tip publication, outcomes, pending records, execution failures and quota allowance. No provider calls or deployment occur when rendering it.

## Validation and remaining acceptance boundary

Local regression suite: **554 discovered; 546 passed; eight PostgreSQL integration tests reserved for GitHub CI**. Full existing Streamlit smoke suite is preserved. Phase 7 adds 23 tests for training integrity/permissions, original protocol preservation, new snapshots versus retries, missing lineups, delayed/start/rescheduled games, failed publication, source failures and separate grading. An incidental midnight rollover in legacy fixtures was isolated with a fixed test clock rather than modifying frozen provider code.

Observed cloud result: [Phase 7 workflow 40815545939](https://github.com/kaishawn01/apex-first-basket/actions/runs/40815545939) passed all three jobs on separate standard Ubuntu runners: forecast 30 seconds, reconciliation 25 seconds, verification 30 seconds (85 runner-seconds total, excluding queue time and regression CI). It persisted exactly one synthetic forecast and one separate synthetic result, verified probability/timestamp integrity and rendered the archive in the dashboard. The fixture uses a declared fixed clock (`2027-01-02T21:00:00Z`), never masquerades as real evidence and makes zero sports-provider requests. Phase 6's original execution timestamps remain unchanged.

All **554 automated tests passed on Python 3.11 and 3.14 in GitHub CI**, including the eight PostgreSQL tests skipped locally. Full Streamlit smoke and updater-manifest checks passed. [Push CI](https://github.com/kaishawn01/apex-first-basket/actions/runs/40815545868) and [PR CI](https://github.com/kaishawn01/apex-first-basket/actions/runs/40815552804) cover implementation `95e4a736bb72d64012d6af9688ba857bffcb380d`. The dispatcher is pinned literally to that reviewed code revision; it remains outside active workflows. Final evidence-only revision CI is recorded on PR #1.

[Persisted synthetic archive](https://github.com/kaishawn01/apex-first-basket/blob/apex-research-data/fixtures/95e4a736bb72d64012d6af9688ba857bffcb380d/journal.json) head: `28e3efa780c9c312ffbc3ade987c7a0f020dc4bf605e94b804f7747b8607bfa0`. See `validation/PHASE7_RESULTS.json` for observed counts, resource measurements and unresolved live acceptance criteria. No training dataset, permission grant, private credential or live record was published.

**Zero genuine Phase 7 forecasts, zero genuine outcomes, zero unattended live runs.** The required permitted training dataset and real pregame demonstration are missing, so autonomous-operation and live technical acceptance are not claimed. Original integrity-incident causes and reliable officially confirmed pre-tip coverage remain unresolved. No model superiority or betting advantage is established.

Exact next decisions: establish applicable provider permission; review/approve the dataset and permitted private/public storage arrangement; approve the narrowly pinned dispatcher separately without merging V3; run a controlled real pregame test; only then approve a modest schedule and verify an actual unattended pre-tip publication. No spending is authorized by any of these steps. See `PHASE7_LIVE.md` for commands, evidence schema, private-data alternative and rollback.

---

## Preserved Phase 6 and earlier review

# V3 Phase 6 review — development VERSION 3.0.5

Continue existing draft PR #1 on `v3/hybrid-monte-carlo`. **Do not merge, activate production scheduling, or deploy the dashboard.** Main/V2.44, the 1,110-game historical ledger and all prior frozen evaluations/journals remain unchanged.

## Implementation

Phase 6 adds a headless batch entry point around the existing Phase 4 forecast function and Monte Carlo simulator, without changing weights or replacing the engine. It separates manual, schedule-window and validation execution. A compact append-only JSON journal preserves probabilities, Other, first-shot vectors, lineup status, provenance hashes/timestamps, model settings, uncertainty, separate outcome versions and diagnostics. Original forecasts are never rewritten.

A dedicated `apex-research-data` branch provides repository-native persistence. Publication verifies prefix integrity and fast-forward updates, confirms the remote ref, records the first observed publication time, then publishes derived dashboard metrics. Hash chains, atomic replacement, locks, explicit capacity stops and fresh-clone recovery tests protect against accidental corruption. It does not claim to diagnose Phase 5's unexplained SQLite incident or prevent a privileged owner from rewriting Git history.

The isolated cloud fixture workflow uses standard Ubuntu runners in the verified public repository, bounded eight-minute jobs and a common concurrency group. No artifact uploads, paid providers, cache upgrades, purchases, deployment or schedule are enabled. Fixtures are explicitly synthetic and cannot enter real prospective results. A separate disabled live-workflow template documents activation; default-branch trigger limitations and GitHub scheduling delays remain explicit.

The cloud provider wrapper allows credential-free ESPN/NBA only, blocks paid hosts/keys/redirects, reserves at most 80 attempts per run and 400 per Eastern day, and preserves cooldown diagnostics. Actual Odds API/BALLDONTLIE account quotas and billing settings could not be verified; those services remain disabled in the collector. Existing local odds functionality is preserved.

A Phase 6 dashboard panel reads compact persisted forecasts and derived publication reports, exposes stale/unconfirmed/missing-data labels and displays top-five baseline/MC/hybrid candidates, first-shot probabilities, Other and uncertainty. Page rendering makes no paid requests. Mobile hosting instructions are prepared; no Streamlit service is connected or deployed.

## Experiment and data boundary

`apex-v3.0.5-cloud-01` is a new declared experiment with unchanged model parameters and its own source hashes. Phase 5's frozen 3.0.4 protocol is preserved, including its version guard; continuing that original experiment requires its original code. No frozen February evaluation is rerun or represented as a result of corrected data.

Primary prospective metrics require a qualifying forecast and verified remote publication before tip-off; log loss/Brier and paired date-bootstrap comparisons remain primary. Top-1/3/5, first-shot accuracy, calibration, confidence, snapshot type, lineup cohort and model version are descriptive. Repeated snapshots do not increase the one-game primary sample. Test forecasts and retrospective outcomes remain segregated. No odds means no ROI. There are no new live prospective results in Phase 6.

Live cloud forecasting still needs an explicitly reviewed, appropriately licensed training bundle; existing personal history is not silently published. Schedules/default-branch routing and mobile publication require approval. Reliable near-tip official lineup coverage, the original eight-game discrepancy and local storage incident causes remain unresolved.

## Validation status

Initial local suite: 531 tests discovered, 523 passed, eight PostgreSQL integration tests reserved for CI. Local fixture forecast/reconciliation, fresh Git clone, immutable timestamp, duplicate prevention, competing-writer rejection and dashboard rendering passed. Full UI and GitHub cloud evidence are recorded below after execution; implementation alone is not proof of operational automation.

## Observed cloud acceptance results

Implementation commit `642b6fbc3d80c4d94bb983ceaab584b70fa8ecb6` ran successfully in GitHub Actions workflow [40809534434](https://github.com/kaishawn01/apex-first-basket/actions/runs/40809534434). The initial trigger was a V3 development push. The forecast job was then **manually rerun**, and its dependent reconciliation/verification jobs passed again (attempt 2). This is an observed manual cloud invocation, not a claim that branch-only UI workflow_dispatch or an unattended NBA schedule was activated.

Three separate standard Ubuntu runners generated a labeled fixture, saved it to `apex-research-data`, reloaded it after the first runner ended, reconciled the fixture outcome, published a separate result and rendered the saved data through the existing dashboard extension. The archive contains exactly **one test forecast and one test result** after both attempts; the manual rerun generated zero duplicates. Forecast creation time remains `2026-10-29T02:59:36.313150+00:00` (October 28, 10:59:36 p.m. Eastern). Its first remote publication was verified at `02:59:38.027197+00:00`. Grading uses a deliberately advanced fixture clock and synthetic completed outcome; it is not an observed NBA result.

The final test journal hash is `76835a04c4aa206a36e39a0bc98f89d64b830b13c4e4ecda41df9cedfebc097c`. [Persisted fixture](https://github.com/kaishawn01/apex-first-basket/blob/apex-research-data/fixtures/642b6fbc3d80c4d94bb983ceaab584b70fa8ecb6/journal.json) and [derived report](https://github.com/kaishawn01/apex-first-basket/blob/apex-research-data/fixtures/642b6fbc3d80c4d94bb983ceaab584b70fa8ecb6/report.json) survive runner shutdown. The test made **zero external sports-provider requests**, used no API secrets, and activated no paid service.

All **531 tests passed in GitHub CI on Python 3.11 and 3.14**, including eight real PostgreSQL integration tests. Local Python 3.12 passed 523 with those eight skipped. The 36 added tests cover no-cost host/quota gates, DST, early/late games, frozen settings, failed providers, duplicate forecasts, outcome matching, interrupted atomic writes, capacity limits, fresh-clone durability and competing Git writers. Full existing Streamlit smoke tests and the cloud persisted-journal smoke test passed. Test data now uses an isolated temporary directory; no user history is used as mutable smoke-test state. Updater manifest/allowlist verification passed. CI evidence: [push](https://github.com/kaishawn01/apex-first-basket/actions/runs/40809534316), [PR](https://github.com/kaishawn01/apex-first-basket/actions/runs/40809538736). Final documentation-only revision CI status is shown on PR #1.

**Technical fixture acceptance is demonstrated. Live activation is not complete.** Phase 6 produced zero genuine NBA forecasts, zero real grades and zero new genuine lineup snapshots. No prospective accuracy, calibration superiority or betting advantage can be reported. Main was read directly and remains VERSION 2.44.0. No Streamlit deployment or schedule was made. `validation/PHASE6_RESULTS.json` records the evidence and blockers.

Recommended next work: approve/review the training-data publication strategy, design the smallest authorized dispatcher/active-slate schedule, verify genuine pre-tip source coverage, then collect independently timestamped live forecasts. Resolve operational integrity questions and audit outcomes before considering model changes or production promotion. Keep all paid providers disabled until account quotas, rights and explicit spending authorization are verified.

See `PHASE6_CLOUD.md` for architecture, verified public-runner cost basis, unknown billing settings, safeguards, scheduling/retention limitations, deployment instructions and exact approval boundaries.

---

## Preserved Phase 5 and earlier review

# V3 Phase 5 review — development VERSION 3.0.4

**Continue draft PR #1 on `v3/hybrid-monte-carlo`. Do not merge or deploy. V2.44 remains the production default.** Phase 5 adds operational infrastructure and prospective experiment controls; it does not change the prediction weights or claim a validated advantage.

## Implemented behavior

- Transaction-level historical import receipts commit atomically with each game. Insert-only historical guards, raw-cache reconciliation, source/record/sequence hashes, identity checks, explicit missing/conflicting-game reports and post-sync manifests make future omissions detectable. Existing history, journals and frozen evaluations are preserved.
- A provider evidence layer distinguishes Expected, projected, manual, provider-confirmed and unknown/contradictory states. It cross-checks current roster identities, home/away game identity, scheduled start, timestamps, unavailable/questionable players, stale caches and provider disagreement. Late changes append a new snapshot. Unverified evidence never becomes an actionable recommendation.
- The checkpoint runner targets 60, 30, 10 and 2 minutes before scheduled tip-off with bounded lateness. Global leases, idempotency keys, retry budgets, cooldowns and fenced writes prevent duplicate jobs and late workers from overwriting evidence. Deadline checks occur inside the storage transaction. Missed windows are recorded without backfilling.
- Forecasts at successive checkpoints remain immutable and separately timestamped. The runner reuses Phase 4 model generation, stores original source/model hashes and all seven probability vectors (six full-support models plus literal V2.44), checks the fresh schedule immediately before saving, and requires at least 30 seconds of remaining lead. Grading is separate, preserves result versions and maps actual nonselected scorers to Other.
- The append-only evidence store supports local SQLite and an explicitly configured PostgreSQL backend. It stores historical identifiers/features, raw provider evidence, snapshots, protocols, forecasts, outcomes and execution receipts. PostgreSQL transaction advisory locks and SQLite transactions serialize writes; immutable triggers and hash chains protect originals. Backups preserve evidence, cooldowns and retry state; empty-destination restoration is atomic. No cloud resources are provisioned.
- The mobile monitoring area displays cached slate age, latest evidence, archived forecast timestamps, top-five candidates, first-shot/first-score comparisons, Other, uncertainty, provider failures, missed windows, pending results, cohorts and proper-score comparisons. Stale/superseded forecasts are clearly labeled. Page rendering makes no paid-provider requests. Existing odds, research, settings and updater protections remain intact.

## Historical integrity findings

The reconciled ledger remains **1,110 games**, **1,106 validated first-score outcomes** and **1,106 usable opening sequences**. Phase 5 did not add historical games or rerun February as a new test.

An isolated replay imported all **1,110 raw-source game identities** with **1,110 matching atomic import receipts**, no missing records and no receipt conflicts. Raw manifests match the existing ledger. The real older ledger has legacy entries without transaction receipts; no receipts were retroactively fabricated. Tests cover incomplete imports, a process terminated within a transaction, deliberate receipt-insert failure, duplicate concurrent imports, conflicting source versions and recovery.

**The original eight-game discrepancy is not explained.** Preserved Phase 4 logs say 690 seeded plus 420 added, while the original Phase 4 inventory had 1,102 records. The eight caches were intact and had already been restored in Phase 4. No deletion path was found in the collector, and the current replay does not reproduce an omission. Earlier per-import receipts and independent database snapshots do not exist, so a specific cause cannot responsibly be assigned. See `validation/PHASE5_INTEGRITY_AUDIT.json`.

The original frozen February files were not modified. SHA-256:

- `validation/PHASE4_RESULTS.json`: `ae2d19da96cb73f2d694686cc2b40e272ba0e5d211c78ff941e7fb7ad3ee240b`
- `data/phase4/frozen_forecasts.json`: `203c9235fca78027b06a79e29d07bd884331e14d77d2c854486e3d1989536496`

Those February metrics continue to describe the original 1,102-record inventory. They are not a result for the repaired inventory, and February is not an untouched sample for later experiments.

## New local-storage incident and recovery

During Phase 5 work, the local operational SQLite file became structurally inconsistent while historical synchronization and dashboard testing overlapped. The import log reported 1,110 copies; the damaged file exposed only a prefix and invalid index-page references. Registration/collection failed closed before any Phase 5 forecasts were created. The damaged file was retained, not silently reset.

A separate overlapping standard-SQLite writer/reader probe completed 2,000 rows without corruption, so overlap alone is not an established cause. The damaged file and logs do not explain the original eight-game issue either. Current evidence supports an unresolved local host/workflow integrity incident, not a claim that SQLite or the prior collector has been conclusively diagnosed.

All 1,110 history records were reconstructed from intact source records into a new store, exported and restored with the identical evidence-chain head. Structural checks and post-sync manifest verification were added, and opening an existing store no longer runs schema initialization. A subsequent live observation completed with a valid chain. This is recovery evidence, not proof that the originating failure cannot recur. Resolve the host/workflow issue before unattended local deployment; retain independently stored backups and prefer a properly managed database for cloud operation.

## Live lineup-provider observations

The NBA daily feed returned HTTP 200 on October 28, 2026 with 12 games and 120 **Expected** player entries. Announcement timestamps lacked timezone offsets. Expected is never confirmed; Phase 5 also withholds verification of a claimed confirmation when its announcement timezone cannot be established. No genuinely provider-confirmed starting fives were observed, and reliable near-tip confirmation has not been demonstrated.

BALLDONTLIE's documented lineup endpoint starts supplying data only once games begin, so it cannot verify a pre-tip starting five. Its injury integration remains available, but no credential was supplied here. SportsDataIO documents projected/confirmed NBA lineups and a three-minute call interval. An adapter is fixture-tested; live access, nonscrambled data, timezone semantics and licensing must be confirmed before enabling it. No paid subscription was bought or live paid API called. Links and exact configuration are in `PHASE5_OPERATIONS.md`.

## Actual prospective evidence

The Phase 5 protocol was registered on **October 28, 2026 at 21:35:10 UTC / 5:35:10 p.m. Eastern**, before its new live evidence collection. Registration hash: `4fa5b126d81497c82b2cc1acf20575c683903bf483f8073b16019d62c015fbf7`. Its immutable specification and exact model/feature source hashes are in `validation/PHASE5_PROTOCOL.json`.

A manual Phase 5 observation run captured **12 genuine pre-tip snapshots** from 21:35:25 through 21:37:06 UTC. All were Expected/unverified; **zero had both fives officially verified**. Injury evidence was explicitly unchecked. The run saved **zero forecasts** because observation does not fabricate checkpoint forecasts and the registered windows had not opened.

Together with Phase 4, **36 pre-tip snapshots** and **12 older Phase 4 forecasts** are preserved; none are graded at this review. The 12 Phase 4 forecasts predate registration and are not counted in the Phase 5 prospective experiment. Fixture-generated snapshots and forecasts are never included in these live counts. See `validation/PHASE5_LIVE_REPORT.json` for the final inventory.

## Frozen prospective evaluation

Model settings remain Phase 3/4 research settings: simple first-shot selector, 90-day decay, 400-day strictly earlier training, 2,000 trials, seed 3000 with the existing deterministic derivation, hybrid weight .5 when minimum history is met, temperature 1.25, and the existing Beta(.5,49.5) Other prior. Same-day/future rows are excluded. Registered model/feature code or settings drift stops collection until a new experiment is explicitly declared.

The primary sample selects the latest valid saved forecast 30–600 seconds before the unchanged scheduled start, without consulting outcomes, exactly once per game. At least 100 earlier training games and a resolved actual first scorer are required. Incorrect projected starters are not removed after the fact. Missing/ambiguous results, incomplete identities, reschedules and missed windows remain explicit exclusions. Provider-confirmed, manual, projected and incomplete/contradictory evidence cohorts are reported separately.

Log loss and Brier are primary; pure MC versus Baseline + Other is the main paired comparison. Calibrated baseline, selected hybrid, simple proxy and uniform are secondary comparisons. Literal V2.44 is additionally shown; a true Other outcome gives it infinite log loss rather than a fabricated starter or epsilon floor. Top-1/top-3, first-shot accuracy and calibration are secondary. Known nonselected first shooters count as misses; unknown identities are documented separately. Intervals reuse the paired game-date bootstrap, with sample sizes and over-time reporting.

The initial research milestone is **300 eligible games across at least 30 dates**, with further reviews at 600 and 1,000 if needed. A 15% hit rate at n=300 has an approximate independent-game reference half-width of four percentage points; date clustering can increase uncertainty. Interim displays and repeated milestones are not independent tests. No model fitting or promotion uses interim results.

**There are no Phase 5 prospective accuracy results yet.** The prior 72-game February point estimates—V2.44 15.28% top-1 / 2.30122 log loss, MC 18.06% / 2.28995, hybrid 16.67% / 2.28551—remain historical and inconclusive. Their paired intervals included no improvement. Phase 5 provides no new evidence that MC genuinely outperforms the baseline or uniform benchmark.

## Tests, infrastructure and disposition

Local automated testing: **495 tests discovered, 487 passed and 8 PostgreSQL integration tests reserved for CI**. The existing regression suite and full Streamlit smoke suite are preserved. New tests cover checkpoint boundaries, duplicate jobs, late worker fencing, multiple immutable forecasts, source/roster disagreement, missing injuries, timeouts/429, bounded backoff, historical leakage, pre-tip persistence, separate completed-game grading, nonstarter outcomes, backup recovery and corrupted/cloud-unavailable storage. The dedicated Phase 5 suite has 62 tests; eight additional tests use a real disposable PostgreSQL 17 service in CI.

GitHub push and PR CI run Python 3.11 and 3.14 with the PostgreSQL service, full unit tests, Streamlit smoke checks and manifest verification. The initial Phase 5 implementation passed both versions; final revision status is recorded in PR #1. Fixture tests establish code behavior in an isolated environment, not live cloud-provider durability, real near-tip lineup confirmation or unattended NBA monitoring.

**No unattended scheduler is configured or verified. No durable cloud account is connected. No preview or production deployment was made.** PostgreSQL credentials, a persistent authorized development host, backup policy and scheduler/monitoring configuration remain external setup. GitHub schedules were not enabled on main. No alerts are configured; nonzero exits, stored diagnostics and the dashboard provide operator visibility. See `PHASE5_OPERATIONS.md` for exact setup, least-privilege grants, scheduler templates and recovery procedures.

Phase 6 should focus on resolving the local integrity incident, authorizing and verifying isolated durable infrastructure, obtaining genuinely usable pre-tip lineup/injury evidence, and collecting the frozen prospective sample. Keep model weights fixed and avoid extra simulation complexity until unseen-game probability scores and uncertainty justify a change. Deployment remains blocked by those operational gaps, unverified confirmed-lineup coverage, insufficient prospective results and the owner's explicit deployment decision.

---

## Preserved Phase 4 and earlier review

# V3 Phase 4 review — development VERSION 3.0.3

**Draft PR #1, branch `v3/hybrid-monte-carlo`. Do not merge or deploy. V2.44 remains the production default. No demonstrated repeatable advantage or betting edge.**

## Completed functionality

Phase 4 extends the existing engine, simulation, historical evaluation and Streamlit research panels. It adds a separate SQLite historical ledger with insert-only game checkpoints, raw-response checksums and retrieval/provider timestamps, bounded two-worker collection, at most two connection attempts, persistent HTTP 429 cooldowns, explicit failures and resumable batches. Existing user CSVs, keys, journals and legacy predictions are not overwritten. An invalid five-per-team split cannot enter the starter model; its actual score remains in the outcome ledger.

The append-only forward journal retains successive lineup snapshots, raw NBA evidence, current roster membership, roster/lineup changes, injury status and retrieval time, provider failures, game identity and scheduled start. Official, manual, projected and unknown states remain distinct. Postgame starters never establish historical pre-tip verification. Failed refreshes append evidence and do not erase earlier official snapshots. Predictions require the latest snapshot, no more than five minutes old, valid current-roster identities and a refreshed upcoming-game schedule. Unverified snapshots can generate explicitly labeled research forecasts, not actionable betting recommendations.

Each forecast stores model/source hashes, version, UTC timestamps, archived evidence, six probability vectors, first-shot probabilities, Other mass, trials, seeds, assumptions, sample sizes, unresolved mass handling and data fingerprints. SQL triggers prevent updates/deletes; a SHA-256 chain detects changes. This protects against accidents, not a privileged owner replacing/truncating the whole database or changing the clock; no external timestamp authority is configured. Actual results append separately, including corrections. Reschedules, unresolved identities and non-pre-tip forecasts are excluded explicitly. First-shot misses outside the selected ten count as misses, not silent exclusions.

Manual background jobs keep collection off the Streamlit rendering thread. The mobile research area shows coverage, diagnostics, snapshots, top-five cards, first-shot/first-score differences, Other, baseline/MC/hybrid, simulation uncertainty, calibration, historical reports and prospective exports. Results are stratified by provider confirmation; prospective month/team/opening-context summaries require at least 30 games. No paid API requests occur on page rendering. Credentials remain in existing settings/environment controls and are not journaled.

## Historical expansion and source audit

420 additional unique completed regular-season games were collected: 103 from October 24–November 7, 2023; 117 from November 6–20, 2024; 74 from December 22–31, 2025; 53 from October 21–27, 2026; and 73 from the reserved February 1–10, 2026 period. These are bounded windows, **not complete seasons**.

The reconciled ledger contains **1,110 games**, **1,106 validated first-score outcomes**, **1,106 usable opening-sequence sidecars**, **1,071 explicit jump outcomes**, and **100 free-throw first scores**. Season-ending-year counts are 2024:103, 2025:225, 2026:729, 2027:53. All 1,110 raw-response hashes reconcile. All sources contain explicit bench-player rows, yet all raw first scorers are marked as starters by ESPN. One source has a substitution before its first score. Four games remain ambiguous because of event clock ordering. See `validation/PHASE4_AUDIT.json` for counts and warnings.

This supports the observed zero-bench count in this sample without proving bench first scores impossible. Single-provider flags can be wrong; missing/ambiguous sequences, bounded windows and earlier conditional feature construction can still bias the sample. Other/nonstarter probability remains explicit, estimated from earlier data with the existing fixed prior. No named bench or substitution forecasts were added. Full raw play-by-play is retained; modeled opening sidecars stop at the first substitution or early-window boundary, so “usable” does not mean complete possession coverage. Unknown tip information is not manufactured.

**Inventory limitation:** final reconciliation found eight intact Phase 3 cached games absent from the Phase 4 ledger despite a seed log reporting 690. Cause is not established. They were restored by insert-only import; no old cache or user history was deleted. The original February evaluation used 1,102 ledger records and is preserved unchanged in `PHASE4_RESULTS.json` and the frozen forecast artifact. It was not rerun after seeing outcomes. The reconciled dataset has 1,110 records; results below are NOT claimed to evaluate that revised inventory. See `PHASE4_INVENTORY_AUDIT.json`. Resolve this collection/checkpoint discrepancy before deployment.

## January diagnosis — exploratory, never untouched

The known 159-game January 1–21 sample and original Phase 3 training data were reused only for diagnosis. Sixteen one-factor scenarios include opening possession, role/simple first-shot assignment, conversion, foul frequency and shooter allocation, FT conversion, turnovers, offensive rebounds, opponent conversion, shrinkage, recency and two additional fixed seeds. Results and paired date-bootstrap intervals are in `PHASE4_JANUARY_DIAGNOSTIC.json` and `PHASE4_FOUL_DIAGNOSTIC.json`.

Pure MC top-1 ranged from **8.81% to 11.95%** across seeds 3000–3002; the originally reported 11.95% is therefore sensitive to simulation noise. Neutral tips gave 9.43%, role selection 8.18%, no turnovers 8.81%, no offensive rebounds 9.43%, uniform foul shooters 9.43%, and neutral foul frequency 11.64%. These components may help this sample, but this is not causal proof or independent validation. Neutral conversion gave 12.58% while log loss was essentially unchanged; removing opponent conversion slightly improved log loss. Thirty-day decay had lower January log loss but was not selected. Strong/weak shrinkage scenarios also remove the opponent adjustment and must be compared with that ablation, not interpreted as isolated shrinkage effects. Multiple comparisons are exploratory and unadjusted. No parameter, seed or production default was changed based on January.

## Reserved historical evaluation

`PHASE4_LOCK.json` fixed February 1–10, 2026 and unchanged Phase 3 settings before fetching that period: simple selector, 90-day decay, hybrid weight .5, temperature 1.25, 2,000 trials, seed 3000, 100 prior games. Outcomes from this period were not used for fitting or model selection in this work. Same-day and later information are excluded; each forecast records its last training date. Current-season October 2026 games cannot inform February forecasts.

Of 73 completed games, **72** were evaluated across ten dates; `espn_401810559` was excluded for clock-order conflict. All historical lineup evidence is unverified pre-tip: observed boxscore starters are an oracle-lineup limitation. The period is now known and cannot be reused as an untouched final test. Results apply to the original inventory noted above.

| Model | Top-1 | Top-3 | Log loss | Brier | Calibration ECE (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Literal V2.44 baseline | 15.28% | 37.50% | 2.30122 | .89915 | 1.20 |
| Baseline + Other | 15.28% | 37.50% | 2.30191 | .89914 | 1.17 |
| Calibrated baseline | 15.28% | 37.50% | 2.29240 | .89720 | 1.11 |
| Simple proxy | 15.28% | 38.89% | 2.30919 | .90077 | 1.60 |
| Pure Monte Carlo | 18.06% | 34.72% | 2.28995 | .89637 | .48 |
| Selected hybrid | 16.67% | 40.28% | 2.28551 | .89579 | .55 |
| Uniform starters + same Other | 10.00% | 30.00% | 2.30327 | .90000 | .01 |

Top-k uses fractional tie credit. ECE is descriptive pooled binning, not proof of calibrated individual-player probabilities. Other mass is the same earlier-data estimate for comparable models. Literal uniform over eleven outcomes is also retained in the JSON report. The calibrated baseline temperature was frozen in Phase 3.

Paired date-bootstrap hybrid-minus-Baseline+Other log-loss difference is **−.01640**, 95% interval **[−.04369, +.01082]**; MC difference **−.01196**, interval **[−.03812, +.01882]**. Hybrid top-1 difference is +1.39 percentage points, interval [−3.39,+5.88]; MC +2.78, interval [−4.92,+9.21]. All include no improvement. MC top-3 is lower. First-shot evaluation has 65 eligible games: simple proxy 16.92%, Phase 2 MC selector 15.38%, simple-selector MC 13.85%. Small samples, ten date clusters, oracle lineups, unresolved outcomes and inventory issues prevent a strong accuracy claim. V3 has **not demonstrated repeatable superiority**.

## Actual prospective collection and manual operation

Two manual live runs on October 28, 2026 captured **24 pre-tip snapshots** between 20:13:46 and 20:16:04 UTC, covering 12 games. **Zero snapshots contained two genuinely provider-confirmed fives.** Twelve immutable forecasts were saved before scheduled tip-off; zero have graded outcomes at this review. Injury credentials were unavailable, explicitly recorded as unchecked. These are genuine timestamped projected/unverified research forecasts, not fabricated backfills or confirmed-lineup recommendations. Source hashes identify the prepublication development code used. No prospective accuracy is claimed.

In a separate development checkout, use the Phase 4 dashboard buttons or:

```text
python phase4_data.py --start 2024-11-21 --end 2024-12-05 --limit 100
python phase4_forward.py capture
python phase4_forward.py predict
python phase4_forward.py grade
python phase4_forward.py status
```

Capture and predict before tip-off, within five minutes of each other. Capture repeatedly to preserve lineup changes; the first saved forecast per game remains immutable. The CLI uses `BALLDONTLIE_API_KEY` from the environment; the dashboard uses its existing applied settings. Grading is a separate manual action after completion. Back up `data/phase4` while no job is running. A repeated historical collection resumes missing games; failures and cooldowns remain visible. Do not run the frozen evaluation script again and label its reused period untouched.

No unattended collector has been configured or verified. Local background threads require the app process to remain running; interrupted jobs are shown and must be resumed manually. The only repository workflow is regression CI. GitHub schedules run from the default branch, while this task prohibits merging; Streamlit Community Cloud local-file persistence is not guaranteed. No external durable database/secrets setup was available. References: https://docs.github.com/en/actions/how-tos/troubleshoot-workflows and https://docs.streamlit.io/develop/concepts/connections/connecting-to-data . A deployment decision, persistent store and monitored scheduler are required before claiming reliable unattended capture.

## Validation and deployment disposition

38 Phase 4 tests cover immutable journal timestamps, roster/identity validation, stale/latest snapshots, schedule changes, provider redaction/failures, cache checksums, retries and cooldowns, preserved nonstarter/FT scores, invalid team splits, probability conservation, exact simulator-kernel equivalence and chronological leakage. Full unit/regression and Streamlit smoke results are recorded on PR #1. Existing updater allowlists/checksums and protected data remain enforced; no updater bridge or deployment restriction was bypassed.

Phase 5 should prioritize **prospective data collection and operational reliability**: resolve the ledger discrepancy, independently verify official lineups and injuries near tip-off, persist and monitor collection, pre-register a sufficiently large forward evaluation with frozen models, and compare paired probability scores against uniform/calibrated baselines. Reserve new historical data before further experiments. Do not increase simulator complexity or promote MC based on these small point-estimate gains. Windows launcher behavior, durable hosting, true confirmed-slate capture and sustained prospective scoring remain unverified.

---

## Preserved Phase 3 and earlier review

# V3 Phase 3 review — development VERSION 3.0.2

**Continue draft PR #1 on `v3/hybrid-monte-carlo`. Do not merge or deploy. V2.44 remains the production default.** The Phase 3 research path retains the simple first-shot selector; none of the analytical challengers improved both first-shot accuracy and log loss in both validation halves. There is no automatic promotion or betting-edge claim.

## What changed

- Added a separate complete first-score ledger (`outcome_data.py`). Actual starters, bench scorers and unknown starter status are distinct. Legitimate free throws count. Missing scoring identities, conflicting sequences, clock reversals and inconsistent score totals remain explicit unresolved records/errors. Unrelated missing bench IDs no longer discard a known first score. An unparseable later play can block starter features without erasing the known first scorer.
- Legacy CSV imports and existing research/odds/journal features retain their behavior. `extract_game(..., allow_nonstarter=True)` is an opt-in research bridge; the default still requires one starter scorer. Full outcomes are not forced into a starter row. The complete ledger is separate and raw source caches are not published.
- Added eleven-outcome probability support: ten selected players plus `OTHER`. Complete models scale conditional starter probabilities by (1 − Other mass). The literal legacy baseline has zero Other support; a real Other outcome gives it infinite log loss rather than a fabricated starter winner. A separate Baseline + Other wrapper allows comparable full-support evaluation.
- Other mass uses only earlier resolved games with valid modeling lineups, a 400-day window and a fixed Beta(0.5, 49.5) prior (1% prior mean). This prior is an assumption, not an estimated NBA rate. Conditional player models still train on starter-scorer rows; first-shot feature selection bias may remain. Named bench-player/substitution forecasts are not supported.
- Reused the existing Phase 2 possession simulator via an optional input transform; did not build a competing engine. The simple challenger removes category-conditioned first-shooter assignment. First attempts retain team category mix; later/second-chance shots retain player-specific mix. Tips, turnovers, foul trips, type-specific conversion and rebounds are retained. This simplified independence assumption is explicitly disclosed.
- Added role, empirical, 50/50 role blend, category/tip bundle, neutral-possession and opponent-history ablations at 30/90/180-day half-lives, with shrinkage and sample diagnostics. First-team attempt proxies are distinct from actual first FG before first score and later scoring opportunities.
- Added append-only timestamped pre-tip snapshots for Phase 2 research runs, preserving projected/manual/provider sources, game/start identity, selected five, source evidence and injury time. Existing journal evidence remains intact. Failed roster checks prevent snapshots; provider failures/staleness cannot establish confirmation. Historical verified cohorts require an archived provider snapshot matching the recorded start and selected IDs. Box scores never establish pre-tip verification.
- Added mobile Phase 3 candidate cards, Other mass, assumptions, sample warnings, complete-outcome import/audit, frozen performance reporting and JSON exports. New panels remain research-only, with no odds/EV recommendation. Stale Phase 2 verification gates the Phase 3 panel too.

## Why Phase 2's first-shot selection weakened

A replay of the original 120-game December sample reproduced the original 115 eligible first-shot results exactly: simple proxy **23/115 (20.00%)**, Phase 2 simulated first-shot **18/115 (15.65%)**. The Phase 2 category/tip input bundle, before possession simulation, hit **19/115 (16.52%)**. Most of the drop therefore appeared before simulation; simulation/exposure conditioning and random sampling account for the remaining difference in these predictions, not necessarily a causal effect.

On those same known games, role-only, empirical, 50/50 role blend and opponent adjustments each hit 22/115 (19.13%). Minor log-loss changes did not justify a replacement. The 78 games with fewer than five prior exact-lineup appearances had simple/Phase 2 accuracy 21.79%/16.67%; the 16 low-start cases had 6.25%/0%. All five net lost hits were among players with prior first-team-shot frequency at least 20%. These are descriptive, overlapping, small-sample groups—not a discovery of stable player types or individual defensive causes. Actual positions/defender assignments were unavailable.

Unresolved hypotheses include correlated role/lineup predictors, sparse category and tip samples, shrinkage strength, team-possession estimation, and conditioning first-shot probability on a FG occurring before the first score. Category and tip effects remain bundled; this study does not identify their individual causal contributions. The original December results are known development diagnostics, never reused as an untouched final test.

## Selection-bias and coverage audit

Development ledger: **531 games**, including **108 completed games from October 22–November 5, 2024**, plus the cached October–December 2025 period. Of these, 529 outcomes resolved as starter scorers; two clock-order conflicts remained ambiguous. Seven summaries formerly rejected for missing unrelated player IDs were recovered. All scheduled/summary/sequence failures and unresolved records are retained in the artifacts.

Combined ledger after the final test: **690 games**; outcome counts **{'starter': 688, 'ambiguous': 2}**; **63 free-throw first scores**. Final-test audit: **159 fetched summaries**, counts **{'starter': 159}**, from **159 scheduled completed games**. Full warning lists are in PHASE3_RESULTS.json. No observed resolved bench scorer means the real-world impact of nonstarter inclusion cannot be estimated from this sample; synthetic tests establish correct handling, not empirical validation of the Other prior. Unknown outcomes are not silently treated as starters.

## Frozen chronological evaluation

Protocol: `validation/PHASE3_LOCK.json`. Development ends December 21, 2025. **342 chronological validation games** select parameters; they use strictly earlier dates, including the expanded prior-season sample where it lies within 400 days. No same-day outcome trains another forecast. Validation chooses the **simple selector, 90-day decay, 50% MC blend, temperature 1.25**. The separately calibrated baseline also selects temperature 1.25. Selection was written before any January summary was fetched. Temperature scaling has a dedicated eleven-outcome path; the legacy ten-outcome helper is unchanged.

The genuinely reserved evaluation was **January 1–21, 2026: 159 modeled games**. December 22–31 was not collected, leaving a documented training gap. During this rolling test, earlier January outcomes can train later January dates; selection settings never change. The final test is now known and must not be used to tune a future model. No public sample has archived provider-verified pre-tip lineups: verified cohort is zero, all modeled games have unverified pre-tip evidence and retrospective observed starting fives.

| Model | Top-1 % | Top-3 % | Log loss | Brier | ECE pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy Baseline | 8.81 | 30.82 | 2.36412 | 0.912288 | 2.50 |
| Baseline + Other | 8.81 | 30.82 | 2.36504 | 0.912264 | 2.49 |
| Simple proxy | 9.43 | 30.82 | 2.35252 | 0.911299 | 1.93 |
| Monte Carlo | 11.95 | 32.70 | 2.31468 | 0.902439 | 0.91 |
| Phase 2 hybrid | 8.81 | 28.30 | 2.35268 | 0.909799 | 2.01 |
| Selected hybrid | 8.81 | 30.19 | 2.32101 | 0.903360 | 1.28 |
| Calibrated baseline | 8.81 | 30.82 | 2.34304 | 0.907571 | 1.87 |
| Uniform | 9.09 | 27.27 | 2.39790 | 0.909091 | 0.00 |
| Uniform + Other | 10.00 | 30.00 | 2.30351 | 0.900001 | 0.02 |


On this single reserved test, the selected hybrid improves log loss and Brier relative to Baseline + Other, with paired intervals excluding zero. Top-1 does not improve, top-3 is slightly lower, and Uniform + Other has better point estimates on both proper scores. This is limited probability-score improvement, not demonstrated overall superiority or a deployment case. The Phase 2 hybrid row is the uncalibrated exploratory 35% blend, not its old validation-selected calibrated forecast.

Lower log loss/Brier/ECE is better. Top-k ties get fractional credit. The eleven-way Uniform benchmark gives Other the same mass as each player; Uniform + Other uses equal probabilities within the ten-player field and the same earlier-data Other prior as the complete models. A zero aggregate calibration bin error for uniform probabilities is mechanical, not discrimination. ECE uses fixed bins and is uncertain in a small sample. This study includes eleven outcome categories, so ECE is comparable within this table, not directly to the old ten-player Phase 2 ECE.

Final-test first-shot diagnostics: eligible **146**; simple proxy **15.75%**, Phase 2 simulated first-shot **14.73%**, simple-selector simulation **16.44%**. Analytical proxy and simulation differ in conditioning/exposure; they should not be conflated. First-shot ablation log loss uses a declared numerical floor of 1e-15; paired metric diagnostics retain non-finite raw simulation losses and withhold undefined log-loss intervals.

Paired approximate date-bootstrap 95% intervals, candidate minus **Baseline + Other** (hit-rate differences in percentage points):

- Selected hybrid: Log loss -0.04403 [-0.06805, -0.02347]; Brier -0.00890 [-0.01238, -0.00589]; Top-1 hit percentage points +0.00000 [-2.54777, +2.35294]; Top-3 hit percentage points -0.62893 [-5.26316, +5.55556]
- Calibrated baseline: Log loss -0.02200 [-0.03535, -0.01076]; Brier -0.00469 [-0.00677, -0.00275]; Top-1 hit percentage points +0.00000 [+0.00000, +0.00000]; Top-3 hit percentage points +0.00000 [+0.00000, +0.00000]
- Monte Carlo: Log loss -0.05037 [-0.07833, -0.02725]; Brier -0.00983 [-0.01418, -0.00602]; Top-1 hit percentage points +3.14465 [-0.69930, +6.70732]; Top-3 hit percentage points +1.88679 [-3.97351, +8.97436]

Dates can remain dependent. These intervals and calibration tables do not establish profitable bets. No historical prices/ROI were evaluated.

## Comparable before/after check on known games

The original Phase 2 baseline/hybrid results on the 120 common December games are recorded in PHASE3_DIAGNOSTICS.json. Original published values: Baseline top-1 15.00%, log loss 2.32969; hybrid top-1 12.50%, log loss 2.32021. Phase 3 on exactly the common target games:

| Model | Top-1 % | Top-3 % | Log loss | Brier | ECE pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| Phase 3 Legacy Baseline | 16.67 | 36.25 | 2.31999 | 0.900985 | 1.81 |
| Phase 3 Selected hybrid | 15.83 | 38.33 | 2.30533 | 0.899215 | 0.33 |
| Phase 3 Calibrated baseline | 16.67 | 36.25 | 2.30886 | 0.899065 | 1.44 |


Training was expanded/repaired, so this comparison is not a controlled attribution to one feature and is not a fresh test. The January table above is the relevant held-out check.

## Tests, reproducibility and deployment limits

Local automated validation: **387 unit/regression tests**, including nonstarter and FT outcomes, identity errors, probability conservation, eleven-outcome calibration, cached/uncached ablation equality, strict chronological inputs, future-outcome perturbation, provider failures and archive timestamp/reschedule checks. Full Streamlit smoke checks include legacy features, Other probability mass, the simple selector, warnings, pre-tip snapshots and result invalidation. GitHub CI checks Python 3.11 and 3.14, UI and manifest integrity; see the PR for actual published-commit results.

Reproduce: `python validation/run_public_sample.py`, `python validation/run_phase2.py`, then `python validation/run_phase3.py`. The last command caches public responses under ignored `data/phase3_validation`, uses at most two request workers, stops on rate limits, records failures, freezes selection before fetching test data, and refuses a changed existing selection. `python validation/diagnose_original_phase2.py` replays the known Phase 2 diagnostic. `python validation/analyze_phase3.py` adds descriptive patterns and paired intervals without changing model settings. Public provider revisions may change fingerprints and must be reviewed rather than bypassing a lock.

In the dashboard, import complete outcomes for a prior date into the separate ledger, then run Phase 2 research and expand Phase 3. A fresh checkout includes frozen validation reports; updater program manifests intentionally exclude raw data and research datasets. Existing personal files, API keys and installed environments are preserved.

Remaining gates: prospective verified lineup/injury archives; more complete seasons and rare nonstarter examples; resolve clock-order ambiguities; validate current jumper and individual defensive assignments; improve opening shot-type/selector dependence; support bench/substitution modeling only with evidence; independently validate calibration and any candidate improvement. Live Windows/provider checks and an updater allowlist bridge for `phase3.py`, `outcome_data.py`, `test_phase3.py` (plus the earlier V3 modules) remain required before rollout. Do not weaken hashes or protected-file rules.

**Phase 4 recommendation: prioritize data collection and prospective validation, with targeted model work guided by ablations. Controlled deployment is not yet justified.**

---

# Previous phase reviews (historical record)

# V3 Phase 2 review — VERSION 3.0.1, development only

## Decision: retain V2.44 Baseline

The Phase 2 hybrid does **not** demonstrate a meaningful, repeatable improvement. Its first-basket hit rate and first-shot selection are worse on the declared final test. The small log-loss improvement is statistically inconclusive, Brier is slightly worse, and Uniform beats both models on proper scores. Keep Baseline as the existing default. No merge, deployment, automatic promotion, or betting-edge claim is authorized by this report.

## Changes and preserved behavior

`opening_data.py` validates completed ESPN summaries against saved game/player identities and stores empirical opening sequences separately. It extracts explicit jump-ball winners, first-team shot categories, 2PT/3PT results, free-throw trips, turnovers, and rebounds. Collection stops after the first three minutes or before the first substitution/nonstarter action. Rebounds are assigned to the preceding shooting team, so defensive rebounds count as that team's failed possession retention. Unknown shot types and ambiguous tips remain unknown. Atomic checkpoints, bounded requests, retry ordering, concurrent-file guards and readable failures preserve existing history.

`phase2.py` separates first field-goal selection, first scoring opportunity (FG or FT), and first-score probability. Inputs combine existing lineup/recent-role predictors with decayed observed opening categories, later-shot and second-chance selection, explicit tip evidence, type-specific conversion, team event tendencies, and opponent-team defensive aggregates. Sparse inputs shrink toward stated priors. Reproducible simulations include turnovers, two/three-point shots, one/two/three-shot foul trips, offensive/defensive rebounds and second chances. Trial count and seed are configurable; unresolved trials retain explicit baseline fallback mass.

The mobile research panel shows five vertical candidate cards, Baseline/MC/Hybrid probabilities, conditional first-shot estimates, first-opportunity estimates, sample evidence, MC sampling error and lineup diagnostics. First-shot probabilities are conditional on a field-goal attempt occurring before first score; the no-FG fraction is separate. The new panel never provides actionable recommendations. It refreshes rosters, checks injury freshness, expires results and clears failed-refresh output. Live ranking Model EV is now hidden for every HOLD status, including lineup, injury and sample holds. Existing models, API settings, odds display, imports, journal and Phase 1 panels remain available.

Starter checks retain exact identities, unique current-team roster membership, provider/manual source distinctions, selected-five binding, schedule/time checks and expiry. Provider failures cannot establish confirmation. Historical provider verification requires an archived pre-tip snapshot, actual game start metadata, matching selected five and valid source evidence; retrospective boxscore starters alone remain unverified.

## Locked chronological experiment and actual results

The experiment boundaries and candidate grid were recorded in `validation/PHASE2_LOCK.json` before the December final-test data was fetched. Development: 296 accepted games from October 21–November 30, 2025, with 296 matching opening sidecars and 5,835 early-sequence events. After 100 prior games, 193 validation games across 26 dates selected the blend and calibration. Validation selected **50% Baseline / 50% MC, temperature 1.25** from weights 0/.15/.35/.5 and temperatures .8/1/1.25. Temperature fitting requires at least 100 validation games and 20 dates; smaller samples retain stricter defaults.

Selection was persisted before fetching the final test: **December 1–21, 2025, 120 accepted games across 21 dates**, from 124 scheduled completed games. Four summaries failed missing-ID validation and are listed in the results artifact. There are 416 accepted history/sequence games overall. All features use strictly earlier dates within 400 days, excluding same-day outcomes. Earlier test games may train later test dates under the declared rolling evaluation; blend and temperature never refit on test results. Training fingerprints and latest dates are exported. Test outcomes are now known: any further tuning needs another untouched sample.

| Final-test model | Top-1 % | Top-3 % | Log loss | Brier | Calibration ECE, pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| V2.44 Baseline | 15.00 | 37.08 | 2.32969 | 0.902729 | 1.82 |
| Pure Monte Carlo | 8.33 | 34.58 | 2.35766 | 0.911237 | 1.96 |
| Selected calibrated hybrid | 12.50 | 35.83 | 2.32021 | 0.902799 | 1.50 |
| Smoothed scorer frequency | 10.56 | 30.36 | 2.47305 | 0.929885 | 5.38 |
| Uniform | 10.00 | 30.00 | 2.30259 | 0.900000 | 0.00 |

Top-k ties receive fractional credit. Lower log loss, Brier and ECE are better. Uniform's zero aggregate binned ECE is mechanical (one winner among ten equal probabilities), not evidence of discrimination. Calibration bins are descriptive and uncertain in this small sample.

Paired approximate date-bootstrap 95% intervals, hybrid minus Baseline: log loss **-0.00949 [-0.03472, +0.01411]**; Brier **+0.000070 [-0.004699, +0.004815]**; Top-1 **-2.50 percentage points [-6.19, 0.00]**; Top-3 **-1.25 pp [-6.10, +3.70]**. Dates may remain dependent; these are not proof of superiority or an economic edge.

First-shot diagnostic: 115 games with an eligible observed FG before first score. Phase 2 Top-1 **15.65%**, simpler recent-shot/opening proxy **20.00%**, Uniform **10.00%**. The more complex selector did not improve this metric.

**Verified historical cohort: 0 games. Unverified pre-tip evidence cohort: 120 games.** These forecasts condition on retrospective observed starters, not proven pre-tip availability. This does not mean those players were incorrect starters. The sample contains no observed substitution before first score, which is not evidence that substitution modeling is unnecessary in general.

## Tests and review

Local validation: **349 unit/regression tests passed**, including all existing tests. Full Streamlit smoke suite passed, including previous features, new mobile candidate cards, first-shot distinction, HOLD warnings, roster-failure clearing, chronological comparison, small-sample fitting guards, cohort reporting, exports and changed-input invalidation.

Tests cover probability conservation, seeded reproducibility, explicit tips/types, empirical second chances, free throws and capped trials, invalid identities and sidecars, atomic enrichment/retries/concurrent writes, provider failure and injury freshness, pre-tip archive timing/reschedules, same-day exclusion, final-test label independence of selection, and lock callbacks before test prediction. GitHub's Python 3.11/3.14 workflow runs these tests, UI checks and manifest checks for the published commit; consult the PR checks for their actual status.

## Reproduce and limitations before deployment

Run `python -m unittest discover -v` and `python ui_smoke.py`. Public-data experiment: first `python validation/run_public_sample.py`, then `python validation/run_phase2.py`. It uses public ESPN data, no paid keys, and writes raw/history caches only beneath ignored `data/v3_validation/`. The locked selection file prevents silent retuning. Public feeds can change; recorded fingerprints make differences visible. The user's private laptop history is not available here.

For local research, use a separate branch checkout. Enrich next 20 opening sequences in the dashboard, then run the Phase 2 research panel or chronological test controls in Backtest lab. Fetches happen only on requested actions. The ordinary research-panel blend follows sidebar settings; the historical selected/calibrated blend is reported separately and never silently promoted to live rankings.

Remaining limitations: inherited exclusion of nonstarter first scorers; no independent pre-tip lineup/injury archive; inferred current jumper from past appearances; shot categories rather than verified designed plays; team-level defense rather than individual matchups; fixed ten starters because pregame bench/substitution evidence is missing; simplified technical/and-one/violation handling; fixed shrinkage and missing-data assumptions; MC standard errors measure simulation noise, not total model uncertainty. Short public sample, no historical market prices/ROI, and no demonstrated superiority over Uniform. Live provider confirmation on Windows and deployment/rollback still need operational validation.

Before promotion, collect prospective pre-tip snapshots and richer opening data, evaluate a newly locked independent period/season against Uniform and a calibrated Baseline, and require repeatable gains with uncertainty estimates. The V2.44 updater needs a reviewed allowlist bridge for `simulation.py`, `test_simulation.py`, `V3_REVIEW.md`, `opening_data.py`, `phase2.py`, and `test_phase2.py`. Do not weaken integrity checks or publish this manifest directly to old clients. No bridge or Streamlit deployment is included.

---

# Phase 1 review (historical record; Phase 2 above supersedes current version/results)

# V3 development review — not deployed

Base: published APEX V2.44.0, commit `babec35666c3da1ccdbe2202c68fde2695a14e67`.
Development branch: `v3/hybrid-monte-carlo`. The unfinished local V2.45 experiment is not included.

## Behavior and scope

The new opt-in simulation panel combines the existing Baseline forecast with empirical Monte Carlo first-score frequencies. The fixed default blend is 65% Baseline / 35% simulation. Both teams need ten earlier saved games for the simulation component to activate; otherwise the hybrid returns Baseline. This is a review minimum, not validated sample sufficiency. Existing rankings, model selectors, odds, starter editing, history enrichment, research tools and the forward journal retain their prior behavior. Simulations are exported separately and are not silently inserted into the existing three-model journal.

The simulator draws an opening team, then repeats turnover, field-goal or two-shot-foul events. A made field goal or the first made free throw terminates the trial. A miss can retain possession through an offensive rebound or transfer it through a defensive rebound. The ten selected starters remain on court. This is a first-points model, conditional on those starters, not a first-field-goal or full basketball game simulator.

Historical inputs use only earlier dates in the preceding 400 days. Opening-action shares use the recorded first-action proxy, with 90-day decay and a symmetric strength-20 prior; this is not verified jump-ball data. Player shot shares and make rates reuse existing smoothed opening-shot evidence. Later attempts reuse opening-shot selection shares. Foul shooters use conditional first-score shares as a proxy, not observed foul-drawing rates.

Per-event turnover (0.13), two-shot foul (0.10), offensive rebound after a miss (0.24), and free-throw make (0.77) probabilities are exposed scenario assumptions. These values have not been estimated from the user's data or asserted to be league averages. Three-shot fouls, technicals, and-ones, violations, substitutions, clock effects, rebounder identity, opponent-specific defensive matchups and play design are absent.

Each game uses a reproducible seed derived from the user seed, date, teams and sorted selected player IDs. Reordering history or lineup display cannot alter a forecast. Trials capped after 60 events remain explicitly unresolved; their probability mass goes to Baseline rather than being discarded or assigned a fabricated scorer. Monte Carlo standard errors describe sampling noise only, not uncertainty about the model or assumptions.

## Lineup review and fixes

- Refresh ESPN rosters when requesting NBA confirmation; failed roster refreshes cannot produce provider confirmation for that team.
- Allow individually updated timestamps for the five confirmed players; identical timestamps are not a reliable requirement.
- Check timezone-aware timestamps against the Eastern game date and reject timestamps more than five minutes in the future. The live NBA feed omits timezone offsets: such timestamps retain calendar-date-only validation and are explicitly labeled unspecified, not assumed UTC.
- Normalize accents conservatively while requiring a unique full-name match on that team's roster. No fuzzy matches, suffix stripping or mixing NBA IDs with ESPN IDs.
- Reject duplicate NBA identities across teams, malformed players, duplicate mapped IDs, missing evidence and duplicate manual selections. A malformed lineup on one team does not discard an independently valid other team unless the game identity itself is conflicting.
- Retain exact selected-five, date, matchup, start time, pregame status and five-minute retrieval-expiry checks. Expiry, edits, failed refreshes and reschedules invalidate confirmation. Expected players and generic confirmed roster members without starting positions are never promoted to confirmed starters.
- Scheduled-game simulations require both lineups confirmed, a fresh schedule and a second confirmation check at execution. Research matchups remain hypothetical. Manual confirmation is labeled separately from NBA confirmation.

A live request to the NBA daily feed for 2026-10-28 returned 12 games. Positioned entries were Expected; the parser accepted zero confirmations from that payload. Confirmed-lineup mapping, mixed timestamps, accents, expiry and failure paths are tested with fixtures. This live probe does not prove future provider availability or validate every provider schema.

## Backtest review

Both forecasts use identical evaluation games and target starting fives. Whole dates are withheld until all games on the date are evaluated; no same-day outcome can train another same-day forecast. All settings remain fixed during a run. Training fingerprints, latest training date, effective blend and unresolved counts are exported per game. Baseline metrics are regression-tested against the preexisting evaluator.

Reports include top-1/top-3 fractional hit credit, log loss, Brier, paired approximate date-bootstrap differences, newest-quarter diagnostics and active-hybrid-only results. Non-finite pure-Monte-Carlo losses remain in the sample; undefined log-loss intervals are withheld, not repaired with a result-dependent floor. No automated parameter tuning, model promotion or profitability claim is made.

Observed historical starting fives are used; historical lineup-announcement timing and pregame injuries are unavailable. The inherited database excludes nonstarter first scorers, creating selection bias. The newest quarter is not an untouched holdout, and repeated experiments can overfit it. Adjacent dates can also be dependent. A user's local historical database is not accessible from this workspace; public-sample validation must be distinguished from testing that user's saved history.

## Deployment gate

This branch is a development preview with numeric VERSION 3.0.0 for compatibility with existing version parsing. Do not merge or deploy automatically based on its version number. Main and the installed Streamlit app are unchanged.

The V2.44 updater intentionally rejects new filenames. A reviewed bridge release adding `simulation.py`, `test_simulation.py` and `V3_REVIEW.md` to the allowlist must reach installed V2 clients before publishing a V3 manifest that includes them. Alternatively, test a fresh checkout of this branch in a separate folder. Do not weaken the allowlist or checksum checks. This upgrade-path issue blocks a one-step automatic deployment from V2.44; no bridge release is published by this PR.

Before production: review the validation results below, validate with the user's own exported history, verify a real pregame confirmed slate on Windows, and decide whether the simulator should remain opt-in. Keep Baseline as the default pending independent forward validation. No Streamlit hosting deployment is configured or changed.

## Local preview

Use a separate checkout/folder to protect the installed app and its database. Install `requirements.txt`, then run `python -m streamlit run app.py --server.address 127.0.0.1`. The existing localhost-only behavior is preserved. Do not upload API-key files, data, virtual environments or a configured local folder.

In the app, load and confirm a slate, run existing rankings, then expand **V3 hybrid Monte Carlo · possession simulation**. Configure the explicitly labeled assumptions in the sidebar. In Backtest lab, use **Backtest V3 hybrid vs baseline**.

Offline command: `python simulation.py --history data/history_espn.csv --output data/v3_report.json --trials 2000 --min-training 100`. This command never fetches APIs. Optional reproducible public sample: `python validation/run_public_sample.py`; it makes public ESPN requests and caches only under `data/v3_validation`.

## Validation results

- 314 unit tests passed locally, including the 288 existing tests and 26 V3 regression/statistical checks.
- The complete Streamlit AppTest smoke suite passed, including existing journal/lineup/history/model tools and new simulation, confirmation, export and stale-settings checks.
- Live NBA feed/schema probe succeeded; no Expected lineup was falsely confirmed. Confirmed live pregame mapping still requires a real confirmed slate check.
- Public ESPN validation fetched 299 completed games from 2025-10-21 through 2025-11-30; 296 passed extraction/audit. Three provider summaries lacked an expected ID field and were excluded with IDs/reasons in `validation/V3_BACKTEST_SUMMARY.json`.
- A fixed 2,000-trial, seed-3000, 35%-simulation configuration evaluated 193 games across 26 dates after the 100-game training warmup. 141 games activated the simulation blend; remaining games used the documented minimum-history fallback. No trials hit the event cap. Settings were not tuned after viewing this sample.

| Metric (193 identical games) | Existing Baseline | Hybrid MC |
| --- | ---: | ---: |
| Top-1 hit rate | 11.40% | 10.88% |
| Top-3 fractional hit rate | 30.31% | 29.53% |
| Log loss (lower is better) | 2.39022 | 2.37747 |
| Brier (lower is better) | 0.91731 | 0.91542 |

The approximate date-bootstrap log-loss difference was -0.01275 with interval [-0.02120, -0.00495]. Top-1 difference was -0.52 percentage points with interval [-1.69, 0.00]. These exploratory intervals are unadjusted for multiple comparisons and do not remove temporal dependence or data-selection bias. Newest-quarter top-1 accuracy was also lower: 9.09% hybrid versus 10.91% Baseline over 55 games. Equal 10% probabilities have log loss 2.30259 and Brier 0.9, better than either model here. Thus the probability-error change relative to Baseline is not evidence of an edge or justification to promote the hybrid.

Review disposition: suitable for opt-in development testing, **not approved for production promotion**. Keep the existing default. Required before rollout: the updater bridge, user-history evaluation, Windows launcher check and live confirmed-slate check. GitHub Actions is configured for regression tests; its result must be checked on the PR rather than inferred from local tests.
