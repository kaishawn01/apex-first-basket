# Phase 5 operations — development only

V3.0.4 remains on `v3/hybrid-monte-carlo`, draft PR #1. V2.44 production and the main-branch updater are unchanged. **No scheduler, cloud database, paid resource or development preview is deployed by this PR.** An isolated development deployment requires the owner's explicit authorization. Do not enable this on the existing V2.44 installation.

## Storage and credentials

The configured backend is PostgreSQL when `APEX_DATABASE_URL` is present; otherwise it is a local SQLite database in `data/phase5/operations.sqlite3`. Local SQLite is suitable for a persistent personal computer, not ephemeral Streamlit Community Cloud storage. An unconfigured cloud connection does not silently fall back to local storage. Remote PostgreSQL connections require `sslmode=verify-full`; configure the host's trusted CA certificate as required. Never disable certificate verification to make it connect.

Provide a separate development PostgreSQL database, persistent volumes, restricted network access, automated backups/PITR and an operator recovery test. The application cannot establish the host's durability or backup policy itself. `APEX_DATABASE_SCHEMA` can select a dedicated schema (default `public`). Store the database URL, optional `BALLDONTLIE_API_KEY`, and optional licensed `SPORTSDATAIO_API_KEY` in the host's secret manager or a restricted environment file. Do not commit values or print them in logs. No Odds API calls are added to the collector.

Initialize the schema once with a schema-owner migration account:

```text
python -m pip install -r requirements.txt
python phase5_runner.py init
```

Use a separate least-privilege runtime account afterward. For a dedicated schema named `apex_research`, the administrator can grant the following, substituting an already-created runtime role:

```sql
GRANT USAGE ON SCHEMA apex_research TO apex_runtime;
GRANT SELECT, INSERT ON apex_research.apex_events TO apex_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA apex_research TO apex_runtime;
GRANT SELECT, INSERT, UPDATE ON apex_research.apex_leases,
  apex_research.apex_jobs, apex_research.apex_state TO apex_runtime;
```

Do not grant the runtime account schema ownership, CREATE, UPDATE/DELETE/TRUNCATE on evidence, or permission to disable triggers. PostgreSQL append-only triggers, unique keys and transaction-scoped advisory locks protect evidence and concurrent writers. SQLite uses full synchronous transactions, unique keys and equivalent update/delete guards. Hash chains detect modification; they are not external notarization and cannot stop a database owner replacing the entire store. Restrict the Streamlit preview to the operator; public hosting is not authorized.

## Initialization and historical reconciliation

Keep the Phase 3 raw caches and Phase 4 `data/phase4` dataset in the separate development checkout. Do not copy over existing user history. The preserved research archives can be extracted into a new checkout for this purpose.

```text
python phase5_runner.py reconcile
python phase5_runner.py sync-history
python phase5_runner.py register
python phase5_runner.py status
```

Reconciliation compares raw cache IDs, content hashes, player identities and import receipts. Missing games can be inserted by `sync-history`; conflicting sources are never overwritten. Every new Phase 4 import and its receipt commit together. Earlier imported games have no retroactive receipts and are labeled legacy. Each reconciliation report is retained separately. Completed results subsequently enter training history for later dates; same-day and future information remain excluded.

The original eight-game Phase 4 discrepancy is **not explained**. A separate Phase 5 local SQLite structural-corruption incident was observed during overlapping import/dashboard work in this session. Registration failed closed before any Phase 5 forecasts were created. The damaged file was retained; all 1,110 history records were reconstructed from intact sources, exported and restored with a matching chain hash. A separate overlapping SQLite writer/reader probe did not reproduce the corruption, so no causal attribution is justified. Existing-store reads no longer run schema initialization; structural checks and post-sync manifest verification were added. Investigate this host/workflow issue before trusting unattended local operation. All 1,110 sources import cleanly in a new isolated replay, and interruption/concurrency tests pass. Old logs and the original ledger disagree; the earlier process had no transaction-level import receipts or independent database snapshot. Do not rewrite the original February evaluation or attribute a cause without evidence.

Registration freezes the exact version, model/feature source hashes, probability calibration, simulation configuration, seed policy, 400-day strictly-earlier training window, Other prior, cohorts and evaluation rules. Any registered model/feature code or setting drift stops forecasting. Do not edit a frozen protocol or select a new experiment using interim outcomes without declaring that change. A new experiment needs a new identifier and review, not deletion of the old registration.

## Manual workflow

```text
python phase5_runner.py observe
python phase5_runner.py collect
python phase5_runner.py grade
python phase5_runner.py status
```

`observe` archives evidence but never invents a scheduled forecast. `collect` runs only due target windows: approximately 60, 30, 10 and 2 minutes before the latest scheduled start. Early windows allow up to three minutes of lateness; the final window ends 30 seconds before the scheduled start. Missed windows are recorded, not backfilled. Schedule delays that have not been reflected in the provider's scheduled start are not used as permission to forecast after that timestamp.

Each checkpoint has its own immutable forecast key. Changed scheduled starts form new keys and preserve old evidence. A fresh schedule check and minimum 30-second lead are required immediately before saving. Source retrieval is bounded and cached briefly: slate 30 seconds (save check forces refresh), NBA lineup 30 seconds, rosters/injuries five minutes, SportsDataIO at least three minutes. Snapshots and their original retrieval timestamps remain intact. Failed providers do not promote projections to confirmations.

The first completed historical result is saved separately from every original forecast. Ambiguous outcomes remain excluded with reasons. Completed grades can be checked for corrections no more than daily; unresolved results can retry after 15 minutes. Grading never changes an original prediction. No bets are placed.

## Unattended execution — template, not installed

A suitable option is a separately authorized persistent development VM/container with the V3 branch pinned to a reviewed commit and the external PostgreSQL store above. Keep it separate from V2.44. An external scheduler can invoke these commands:

```text
# Every minute, using the scheduler's protected environment:
/srv/apex-v3/.venv/bin/python /srv/apex-v3/phase5_runner.py collect --scheduled
# Every five minutes, separately:
/srv/apex-v3/.venv/bin/python /srv/apex-v3/phase5_runner.py grade
```

Use the development checkout as the working directory. The account needs write access to that checkout's `data` folder for local diagnostics and temporary imports, but durable evidence resides in PostgreSQL. Keep the environment file outside the repository and readable only by the service account. Bound each scheduler invocation to a reasonable runtime (for example 10 minutes) and collect its exit status. The process uses a five-minute renewable lease and fenced appends; an expired worker cannot commit after another worker takes over. Duplicate invocations return without duplicate forecasts.

A schedule command is only a template until installed and observed. Verify a real scheduled invocation, provider responses, pre-tip evidence timestamps, cloud database receipts and recovery after process/host restart. A `--scheduled` flag records the invocation's claimed origin; it does not independently prove a host scheduler is installed or will run again. Fixture CI runs never count as live unattended evidence.

GitHub schedule triggers run on the default branch and can be delayed; no schedule workflow was added and V3 must not be merged merely to enable one. Streamlit rendering is not a reliable scheduler. An external scheduler or a separately authorized development environment remains necessary.

## Provider findings and limitations

- **NBA daily lineup feed:** live HTTP 200 observed on October 28, 2026. The inspected response had 12 games and 120 Expected players, with naive announcement timestamps. Expected is not Confirmed. Phase 5 requires current roster mapping, unique IDs/teams, explicit pregame state, five positioned active players and usable announcement times before provider-confirmed classification. A claimed confirmation whose timestamp timezone cannot be established is withheld. No live confirmed-slate reliability has been established, and no public feed SLA is assumed. NBA use terms: https://www.nba.com/termsofuse . Public accessibility does not establish unrestricted redistribution rights.
- **BALLDONTLIE:** supports injury information subject to access; its documented lineup data starts only once the game begins, so it is not a source of pre-tip confirmation. No paid key was available here. https://docs.balldontlie.io/ . Missing or questionable status is not treated as proof of health.
- **SportsDataIO:** documents projected and confirmed lineups, with team announcements typically around 30 minutes pre-tip and a three-minute call interval. A defensive adapter is implemented but live access is unverified. Set `APEX_SPORTSDATAIO_LICENSED_LIVE=1` only after confirming the account provides live, nonscrambled starting-lineup data and the intended storage/modeling use is licensed. A key alone does not enable it. Confirm the account's DateTime timezone; if naive Eastern timestamps are documented for that feed, set `APEX_SPORTSDATAIO_TIMEZONE=America/New_York`. No timezone is silently inferred. Provider assertions without announcement timestamps retain that limitation. Free/scrambled trial data cannot verify real starters. Documentation: https://sportsdata.io/developers/workflow-guide/nba ; https://sportsdata.io/developers/api-documentation/nba ; https://sportsdata.io/developers/data-dictionary/nba ; licensing: https://sportsdata.io/help/data-rights-and-licensing-questions . No subscription was purchased.

## Prospective interpretation

The primary forecast is the latest qualifying saved forecast generated 30–600 seconds before the unchanged scheduled start, selected without looking at results. Exactly one per game enters primary metrics. Earlier checkpoints remain available as original evidence but do not inflate the primary sample. At least 100 strictly earlier training games and a resolved official outcome are required; wrong projected starters are not excluded simply because they were wrong. All eligible evidence cohorts are reported: provider-confirmed, manual, projected (including provider Expected) and incomplete/contradictory evidence. Structurally incomplete ten-player identities cannot produce forecasts and remain explicit missed/excluded observations.

Primary metrics are log loss and Brier score; the main paired comparison is pure MC versus Baseline + Other. Literal V2.44 is additionally reported: a true Other result gives that conditional model infinite log loss, not an epsilon-smoothed substitute. Calibrated baseline, hybrid, simple proxy and uniform comparisons are secondary. Top-1/top-3, first-shot accuracy and calibration are descriptive secondary measures. Intervals use the existing paired game-date bootstrap. Unknown first-shot identities are counted separately; known nonselected shooters count as misses.

Review at 300 eligible games across at least 30 dates, then 600 and 1,000 if needed. At 300 games, a 15% hit rate has an approximate independent-game reference margin of ±4 percentage points; clustering can make uncertainty larger. Use actual paired-score intervals for model comparisons. Interim displays and repeated milestones are not independent final tests. No automatic promotion, fitted recalibration or betting-edge claim is made. Market-price evaluation would be required for any betting-value claim.

## Monitoring, backup and recovery

The Phase 5 dashboard reads stored data without provider requests on render. It shows cached slate age, original snapshot/forecast timestamps, model comparisons, verification cohorts, provider failures, missed windows, last successful collection, result status and storage/chain health. Old or superseded forecasts are explicitly labeled stale/historical. Operational jobs return a nonzero status for failed/partial runs. No email, Slack, SMS or webhook alert destination has been configured; inspect the dashboard and scheduler logs or connect an operator-approved alert service later.

```text
python phase5_runner.py backup --file /secure-backups/apex-phase5-unique-timestamp.json
# Restore ONLY to a newly initialized empty destination:
python phase5_runner.py restore --file /secure-backups/apex-phase5-unique-timestamp.json
python phase5_runner.py status
```

Backups use exclusive-create files, preserve the exact evidence chain, operational cooldowns and job attempts, and verify integrity before restoring atomically. Active leases are not restored; interrupted jobs retain attempts and a recovery delay. Keep backups private. Also configure the PostgreSQL host's native backups/PITR and test restoration independently; application JSON exports do not prove cloud-host disaster recovery. PostgreSQL documentation: https://www.postgresql.org/docs/current/backup-dump.html .

After a process crash, wait for the old lease to expire and rerun the same command. Retry keys preserve originals; each checkpoint permits at most three attempts with bounded exponential cooldown. HTTP 429 records the provider's retry window; temporary connection/server errors allow three bounded attempts with 1- and 2-second delays. Do not clear cooldowns to force requests. If a job exhausts its budget, retain the failed checkpoint and use a later checkpoint; do not overwrite evidence. Investigate source conflicts instead of deleting historical rows.

A full-database privileged replacement can evade an internal hash chain. For stronger provenance, use host snapshots, restricted administrator access and externally retained backup heads. Windows launchers, a live cloud account, scheduled near-tip capture, paid injury access and provider-confirmed lineups still require live verification.
