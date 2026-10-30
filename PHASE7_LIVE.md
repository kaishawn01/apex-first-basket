# Phase 7 — V3.0.6 controlled live research readiness

**Status: implementation and fixture testing only. A permissible live training/source arrangement is not established. No genuine forecast or autonomous operation is claimed.** Keep PR #1 draft, main/V2.44 unchanged, no public dashboard deployment and no paid services.

## Audit and shortest safe path

Phase 6 actually passed a three-runner GitHub fixture pipeline and manual rerun: exactly one synthetic forecast and one synthetic result persisted with no duplicates. The data branch is `apex-research-data`; code remains `v3/hybrid-monte-carlo`. Its prior protocol and files remain unchanged. Phase 7 declares `apex-v3.0.6-live-01` because the orchestration/version changes; simulation parameters, selection weights, Other handling and original primary timing conditions are unchanged. Phase 5's frozen source files and February evaluation artifacts are also preserved.

The shortest remaining path is permission and data access, not a new model. Before live requests, obtain a permission arrangement covering historical model use, automated collection and the intended forecast publication. A working URL or a research label does not establish those permissions. Owner approval cannot substitute for provider permission.

## Data-rights findings

The ESPN-derived ledger lacks a recorded redistribution or automated-use grant. Disney's published U.S. terms apply to ESPN and restrict automated extraction and AI/model-related uses without permission. We did not establish that these research feeds have a separate applicable license allowing this pipeline. No new live ESPN request was made under this uncertainty. NBA source permission also remains unverified. This is an operational rights blocker, not a legal opinion about every possible use or jurisdiction.

Sources reviewed:
- https://disneytermsofuse.com/english/
- https://disneytermsofuse.com/english-united-states-email-notice/
- https://www.nba.com/termsofuse

No paid data alternative was activated. Account-level Odds API, BALLDONTLIE and SportsDataIO quotas/rights remain unverified. Their hosts and keys stay blocked. A private repository, encrypted blob or secret changes confidentiality, not underlying usage rights.

## Reproducible training candidate

`phase7_training.py` opens the existing ledger read-only, verifies SQLite integrity and source identities, applies an exclusive cutoff and 400-day window, and allowlists fields rather than exporting the whole database. It retains model-required historical flags, IDs/teams, typed opening events, explicit tip facts, complete outcome identities/Other support and provenance hashes/times. Unknown personal fields, source URLs with possible credentials, raw responses, freeform source payloads and unrelated database state are omitted.

The candidate uses schema 2: `cutoff_exclusive`, `window_days`, `test_only`, `publication_approved`, `rights_status`, `data` (history/sequences/records), `provenance`, and independent canonical SHA-256 digests. A deterministic build has no new build-time timestamp. Game/provider source timestamps remain original. Validation checks exact field sets, inventory/IDs, duplicate rows, provenance, sequence linkage, size and cutoff. No same-day/future records enter the model. The model still independently filters its 400-day prior window at inference.

October 28 exclusive-cutoff audit: **1,110 source games; 782 window records; 780 valid training games / 7,800 player rows; 780 sequences; two ambiguous outcomes retained; 328 older records excluded by window**. Candidate canonical size **7,936,079 bytes**, compressed **547,793 bytes**. Unknown/private row-field count was zero in this inventory. The current dataset is sparse in parts of the year; count alone does not establish current player-role reliability. No database was overwritten and no candidate dataset was committed to GitHub.

```sh
python phase7_training.py --database data/phase4/history.sqlite3 --cutoff 2026-10-28 --output /private/path/training-candidate.json
```

Output must be a new file. Inspect `validation/PHASE7_TRAINING_AUDIT.json` for exact hashes and schema fields. The locally generated candidate is unapproved and is not a live credential/data grant. The reviewed specification/builder is reproducible; actual publication requires owner approval plus established rights.

## Private-data alternative

If permitted private model use can be established but public raw training publication cannot, a small compressed encrypted bundle on the existing data branch can avoid a paid/private compute service. Keep only the passphrase in a repository secret and decrypt to the runner's temporary directory. The disabled dispatcher includes a bounded decompression step. This keeps standard compute in the public repository; it does not require a paid database, a private-repository minute allowance, or artifact uploads.

This alternative is **prepared, not configured**. No encryption key/secret or encrypted bundle was uploaded. Rights must specifically permit the chosen storage and cloud-processing arrangement. Review all workflows with secret access and pin the worker code; encryption does not protect against malicious authorized workflow code. A public derived forecast also requires appropriate publication rights. If no permitted arrangement exists at zero new cost, stop live activation rather than substituting synthetic history.

## Permission evidence and controlled runner

The live command requires a separately reviewed permission JSON, tied to both the training data and provenance SHA-256, with `schema:1`, `test_only:false`, `owner_approved:true`, UTC `reviewed_at` and `expires_at`, and `providers.ESPN` containing `permission_verified:true`, an actual `evidence_reference`, and scopes `private_model_use`, `automated_collection`, `public_forecasts`. These fields are a fail-closed record of a human review, not automatic legal verification. Do not fill them with invented grants. NBA confirmation requests require a separate NBA permission entry; otherwise the collector explicitly uses unverified projections from available history/current rosters.

```sh
python phase7_live.py readiness --journal cloud-data/live/journal.json --training /private/path/training.json --permission /private/path/permission.json
# Only after evidence and owner approval:
python phase7_live.py manual --journal cloud-data/live/journal.json --training /private/path/training.json --permission /private/path/permission.json --data-root cloud-data
python phase7_live.py scheduled --journal cloud-data/live/journal.json --training /private/path/training.json --permission /private/path/permission.json --data-root cloud-data
python phase7_live.py validation --journal cloud-data/live/journal.json --training /private/path/training.json --permission /private/path/permission.json --data-root cloud-data
```

A durable checkout, global enable decision, live approval, current permission evidence and a valid training bundle are required before live provider access. Quota reservations publish before HTTP. Every successful forecast publishes immediately, rather than waiting for the whole slate. A publication error stops collection. Started/rescheduled games, invalid or stale lineups, missing sources and minimum lead-time loss cannot become current forecasts. Later manual invocations save new snapshots; the same invocation ID is idempotent. Morning/updated/evening and checkpoint labels remain distinct.

The same existing model calculates Baseline, MC, Hybrid and reference vectors; there is no new prediction engine. Stored payloads add cutoff/bundle/provenance hashes and top-five lists. Outcome collection reuses the prior checked-summary parser and separate append-only grading. Free throws count as first score; first FG attempt is distinct. Unresolved results stay pending; result corrections append without changing the forecast.

## Dispatcher, scheduling and costs

`deployment/phase7-dispatcher.yml.example` is a review-only template, not installed on main. It checks out one literal reviewed SHA, accepts no arbitrary ref, checks VERSION 3.0.6, uses the dedicated data branch and an eight-minute standard Ubuntu job, and requires both live and permission-review approval variables. Global disable, public-repository visibility and exact repository identity gates apply. It refuses live job retries with reused quota reservations. No V2.44 application file is changed by the proposed dispatcher.

Proposed wakeups are 10am, 5:30pm, 6:30pm and 9am next-day validation in America/New_York. The documented timezone field handles DST; Python independently converts UTC evidence to Eastern. Morning validation explicitly routes to validation mode. Four invocations reserve at most 320 attempts/day, leaving one 80-attempt invocation under the unchanged 400 daily limit. Dependencies and scheduling overhead are bounded by the timeout. Missing/delayed triggers are normal limitations: do not assert reliable 60/30/10/2-minute coverage. Fixed modest wakeups produce mostly secondary observations; later active-slate scheduling needs a separate reviewed request budget. Missed primary windows are reported, never backfilled.

The public standard-runner free-compute basis was verified in Phase 6 and rechecked against repository visibility. Actual account billing settings are not accessible here; no potentially billable feature is enabled. No larger runners, artifacts, caches, LFS, paid APIs, subscriptions or database resources are provisioned. Existing 10 MB/10,000-event journal and 50 MB Git-object limits remain. A billing alert is not treated as a spending restriction. If account visibility or the free-runner basis changes, the job guard skips allocation. Verify billing and retention settings independently before activation.

## Monitoring and science

`phase7_live.monitoring` separates real forecasts, remote pre-tip publication, graded versus unresolved results, quota allowance and execution/provider failures. `last_execution` is not labeled successful collection when zero predictions were published. The existing read-only Phase 6 dashboard can display the preserved format, source warnings and top-five predictions; no public deployment is prioritized or performed.

The primary protocol remains latest eligible 30–600-second forecast with remote verification at least 30 seconds before unchanged scheduled start, one forecast per game/experiment and 100 earlier training games. Log loss/Brier are primary; paired date-bootstrap comparisons, top-1/3/5, first-shot accuracy, calibration and lineup/version/snapshot cohorts remain descriptive. Earlier observations are retained as secondary data, not promoted by weakening the timing window. Keep 300 games across 30 dates as the initial milestone. No new live performance or superiority claim is available.

## Activation and rollback checklist

1. Establish applicable historical/live source permissions and record verifiable evidence. Owner approval alone is insufficient.
2. Review the candidate hash, cutoff, missing-data coverage and privacy scan; approve only the permitted storage arrangement.
3. If using encrypted storage, review secret access and upload only the authorized encrypted bundle plus nonsecret permission metadata. None has been uploaded here.
4. Review the concrete pinned dispatcher diff separately. Explicitly approve installation/activation on main; do not merge V3 or PR #1.
5. Enable `APEX_LIVE_COLLECTION_APPROVED` and `APEX_DATA_PERMISSION_VERIFIED` only after review. Keep `APEX_AUTOMATION_DISABLED=true` until a controlled manual real-data run is approved and succeeds.
6. Verify a genuine forecast's remote timestamp and an independent fresh-runner read. Only then consider enabling the modest schedule.
7. Observe at least one unattended run saving a genuine pre-tip forecast before claiming autonomous operation.
8. Roll back by disabling the global switch and cancelling in-progress runs. Retain journals/data branch unchanged, disable the dispatcher and leave V2.44 running. Never force-push evidence or bypass updater checks.

The original eight-game omission and local SQLite corruption causes remain unresolved. This phase validates a different durable archive path; it does not claim those causes have been explained. All frozen historical experiments remain preserved.

## Observed Phase 7 validation

554 tests passed in GitHub CI on Python 3.11 and 3.14, including PostgreSQL; locally 546 passed and eight PostgreSQL tests were skipped. Full Streamlit and manifest checks passed. Workflow 40815545939 ran generation, fresh-runner reconciliation and display verification in 30/25/30 seconds. Its one synthetic forecast and result are explicitly test-only and use a fixed fixture clock. No real provider requests, live NBA forecasts, real outcome grades or unattended live jobs were observed. This demonstrates the controlled code path, not completion of the real-data acceptance criteria.
