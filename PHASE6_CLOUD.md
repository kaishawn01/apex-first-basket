# APEX V3.0.5 — zero-cost cloud research

Development only on `v3/hybrid-monte-carlo`, draft PR #1. Main and V2.44 are unchanged. No dashboard deployment or live schedule is authorized by these files. Test forecasts are explicitly synthetic, not prospective NBA evidence.

## Architecture and scope

A standard public-repository GitHub Actions runner calls `phase6_cli.py`, which uses the existing Phase 4 forecast function, Phase 5 provider/evidence checks and existing Monte Carlo implementation. It does not start Streamlit or duplicate model mathematics. Manual, scheduled-window and validation modes share this implementation. Predictions and outcome versions are separate immutable events. The dashboard reads a compact public archive only when the user presses Load; rendering makes no paid/provider calls.

`apex-research-data` is a dedicated data branch, not a second application. Only compact derived forecasts, source hashes/times, expected starters, settings, warnings, outcomes, quota reservations and execution reports belong there. No credentials, raw provider responses, personal history or unrestricted training datasets are published. Fixtures live under `fixtures/<code SHA>/`; authorized live collection would use `live/`. Both have separate journal and derived report files. Existing historical data and Phase 4/5 journals are not migrated or overwritten.

Phase 5 experiment/model files remain frozen at 3.0.4. Its original collection intentionally rejects a different application version; archived monitoring still works. Phase 6 declares `apex-v3.0.5-cloud-01`, preserves its own protocol/source hashes before predictions and uses unchanged model parameters. To continue the original Phase 5 experiment, use its archived 3.0.4 code, not altered version guards. No interim outcome is used to retune either experiment.

## Verified free resources and unknown account settings

GitHub documents standard hosted runners as free for **public repositories**. This repository was verified public; workflows use `ubuntu-24.04`, never larger/GPU/self-hosted runners. Job conditions skip private repositories before allocating a runner. Each job has an eight-minute timeout; regression jobs have fifteen-minute timeouts. All archive writers share one workflow concurrency group, with cancellation disabled. No artifact uploads, Actions caches, LFS, Packages, purchases, billing changes or provider subscription changes are enabled.

GitHub Free's documented private-repository allowance is 2,000 minutes/month and 500 MB artifact storage, with 10 GB cache storage/repository. These are shared/account-sensitive limits, not verified remaining allowances. We avoid those storage features. Larger runners can charge even for public repos. Public standard-runner compute is the verified basis for this demonstration, not an assumption about the owner's credit card or spending budget. GitHub log retention is repository-managed; inspect it and set a short retention (suggested seven days) before ongoing operation. No account-wide setting was changed here.

The existing Odds API and BALLDONTLIE credentials/account portals were not available for account billing review. Their actual plan, remaining quota, renewal and overage settings are **unverified**. Published BALLDONTLIE All-Star rate limits do not establish this account's current entitlement. The Odds API exposes request-credit response headers, but no request was made merely to inspect them. Cloud collection blocks both providers and SportsDataIO even if environment keys exist. Existing local odds functionality remains intact. Odds remain null; injuries explicitly unchecked. No ROI or market advantage is calculated without valid timestamped odds.

Before approving any paid integration, the owner must independently inspect each provider's account dashboard: current plan and renewal amount, remaining monthly credits, per-minute limits, automatic upgrades/overages, and whether a hard spending block exists. In GitHub Settings → Billing and licensing/usage and budgets, verify public standard runners, cache/storage usage, no larger runners, and stop-usage controls rather than alerts alone. Do not raise limits or enable metered services. If hard bounds or usage rights cannot be verified, leave the provider disabled. Never paste secrets into an issue, public journal or chat.

## Schedules, DST and trigger limits

No `schedule` trigger is active. `.github/workflows/apex-cloud.yml` is an isolated fixture exercise on the V3 branch, triggered by relevant development pushes; it also declares `workflow_dispatch`. GitHub's UI/default-branch restrictions may prevent a brand-new branch-only manual dispatch. A manual rerun of the fixture job is an alternative controlled test; report which actually executed. This does not require merging V3. Never claim a push-triggered test is an unattended NBA collector.

The disabled template `deployment/cloud-live.yml.example` shows a bounded live invocation but requires approval and a reviewed training bundle. Do not copy it into active workflows yet. If a minimal dispatcher on main is needed, review and authorize that separate change without replacing V2.44; all research checkout/run targets remain the V3 SHA. The template's next-morning validation routing is intentionally marked for activation review; it must route to `validation`, not forecast mode.

The runner converts aware UTC clocks with `zoneinfo('America/New_York')`. Proposed morning/updated/evening slots are 10:00am, 5:30pm and 6:30pm Eastern, with at most fifteen minutes lateness. Each game also has 60/30/10/2-minute targets using the existing strict windows. Reschedules create new snapshot keys; started games and lost minimum lead time are rejected. Fixed slots alone cannot cover every early/late game or reach the primary evaluation window. `next_targets` exposes game-specific UTC checkpoints for future schedule planning. A bounded active-slate polling design may be preferable after measuring request needs. GitHub triggers can be delayed or dropped and are not reliable to the minute; missed opportunities must stay missed, never reconstructed as pregame forecasts. Do not enable a high-frequency all-day poll merely to increase simulation counts.

Set repository variable `APEX_AUTOMATION_DISABLED=true` to stop subsequent fixture/live jobs; cancel an already running job separately. Live mode additionally requires `APEX_LIVE_COLLECTION_APPROVED=true`, absent by default. No paid-feature switch exists: enabling paid providers needs a separately reviewed implementation and explicit approval.

## Quotas, storage and recovery

Only credential-free HTTPS ESPN and NBA hosts are allowed. Redirects are refused. At most 80 HTTP attempts/run and 400 reserved attempts/Eastern calendar day are permitted; each timeout/retry consumes one attempt. Cloud live runs publish the full 80-attempt reservation before any provider request. Crashes do not refund it. Live reruns with the same GitHub run ID are refused; use a new approved run and reservation. A failed reservation push stops before network use. Existing transport allows at most three attempts with exponential delay, never retries 403, and stores 429 Retry-After cooldowns. Final run records preserve cooldowns for the next run; if final publication fails, require operator recovery before more live runs because recent cooldowns may be missing. Paid hosts remain blocked regardless.

The compact journal uses process locks, atomic file replacement and SHA-256 chains. Publication requires the data branch, verifies the previous journal is an exact prefix, stages only the designated file, and uses a normal fast-forward push. A conflicting writer fails; do not force-push/rebase evidence or retry an old snapshot as a new forecast. Fetch the new data head, preserve both attempts for diagnosis, and run again only if still pre-tip. Git commits provide version recovery; a repository owner can still rewrite history, so this is accident protection, not external notarization. Protect the data branch against force pushes/deletion if settings permit; do not disable protections to make a test pass.

Each journal stops at 10 MB or 10,000 events. The data checkout's Git objects stop at 50 MB, and total current archive files at 25 MB. No old forecasts are deleted to free space. Reports can be regenerated; raw caches remain ephemeral and are not archived. At a ceiling: stop collection, export/verify all hashes and receipts, retain the branch read-only, then review year-partitioned compact files or an explicitly approved durable service. GitHub recommends small repositories and blocks very large individual files; our limits are deliberately much lower. Do not activate LFS or paid storage as a workaround.

A successful model process is not successful persistence. The publisher verifies the remote ref after pushing, records the first observed remote-publication timestamp and commit, then publishes a derived dashboard report. An interrupted first push without a receipt stays ineligible until reconciled; a receipt observed after tip cannot qualify retrospectively. A report/journal hash mismatch makes the dashboard stop and request refresh. Independent clones and Git history are used in the integration tests. For recovery, clone the data branch to a new folder and run `phase6_git.py verify`; never replace an existing journal with an empty one.

## Execution and monitoring

Local fixture demonstration (no provider traffic):

```sh
python phase6_cli.py fixture-generate --journal /tmp/apex-fixture/journal.json
python phase6_cli.py fixture-grade --journal /tmp/apex-fixture/journal.json
python phase6_smoke.py /tmp/apex-fixture/journal.json
```

Live modes require explicit activation and a reviewed training bundle. `--training-file` must contain schema 1, `test_only:false`, `publication_reviewed:true`, data with history/sequences/records, and SHA-256 of canonical data. Existing user history is not automatically uploaded. Check collection rights and remove personal fields before publication; review sample quality and provenance. Without this bundle, live forecasts fail closed. Do not train from synthetic cloud fixtures. The 1,110-game historical ledger remains available locally/in its prior backup but is not assumed present on an Actions runner.

```sh
# Only after the stated activation/training review:
python phase6_cli.py manual --journal cloud-data/live/journal.json --training-file cloud-data/bootstrap/training.json --data-root cloud-data
python phase6_cli.py scheduled --journal cloud-data/live/journal.json --training-file cloud-data/bootstrap/training.json --data-root cloud-data
python phase6_cli.py validation --journal cloud-data/live/journal.json --data-root cloud-data
```

Cloud run reports distinguish generated predictions, no eligible games/windows, partial failures, execution completion and remote persistence. They retain source health, missing/stale lineups, upcoming games and next target times. These times are targets, not confirmed scheduler appointments. Forecast cards show original timestamps, top five, baseline/MC/hybrid, first-shot probabilities, Other, trial/seed settings and uncertainty. Stale forecasts remain historical. Results unavailable or inconsistent remain pending. No alerts are configured; use Actions failures and the monitoring panel. A no-forecast run is explicitly labeled, not advertised as a successful prediction capture.

## Prospective methodology

Fixture data is always `test_only:true` and excluded from real metrics. Historical, retrospective walk-forward and prospective results remain separate. The primary prospective sample selects one latest forecast/game, generated 30–600 seconds pre-tip, published at least 30 seconds pre-tip, with 100 earlier training games and unchanged provider scheduled start. Forecast choice is made without consulting the result. Missing, contradictory or rescheduled outcomes are explicit exclusions; wrong projected fives are not removed for being wrong. Reliable actual wall-clock tip can be unavailable, so eligibility uses refreshed game status and provider scheduled start conservatively; it is not proof of an official jump-ball timestamp.

Baseline (with Other), calibrated baseline, simple proxy, pure MC, hybrid and uniform are compared; literal V2.44 is additionally reported. Log loss and Brier are primary. Top-1/3/5, first-shot accuracy, calibration, date/cohort/model-version/confidence summaries are descriptive. Date-cluster paired bootstrap intervals reuse the existing framework. Snapshot cohorts can count one game multiple times and are not independent samples; primary sample uses one per experiment/game. Initial milestone remains 300 games over at least 30 dates. No promotion or interim tuning. Zero probability on a real Other outcome gives literal baseline infinite loss, not a fabricated score. No valid odds means no ROI/market comparison.

## Mobile deployment — prepared, not published

Streamlit Community Cloud is documented as free, with resource limits/sleep behavior. Treat it as a dashboard, never an always-on collector. After owner approval, connect only this repository's V3 branch (prefer a reviewed SHA), entry `app.py`, preserving V2.44's existing deployment. Set `APEX_PUBLIC_JOURNAL` to the approved archive path. No provider keys or database password are required to read public research records. Never upload `.apex_keys.json`, personal data directories or raw licensed feeds. Keep existing local interactive features, but public users must not receive private settings; a publication/access review is required before hosting the full dashboard. No third-party service was connected here.

## Approval checklist and rollback

Still requiring an explicit decision: activate a default-branch dispatcher/schedule, publish a reviewed training bundle, approve live credential-free collection/retention terms, and deploy the separate mobile dashboard. Paid provider access is a separate cost/rights decision, not implied. Original Phase 5 integrity root causes and reliable near-tip official lineup coverage remain unresolved. For rollback, set the global disable variable, cancel active jobs, leave data branch/history intact, and return to the reviewed V3 or V2.44 code. Do not merge PR #1 or use updater bypasses.

## Primary documentation checked October 28, 2026

- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/knowledge-base/deploy/resource-limits
- https://docs.balldontlie.io/
- https://the-odds-api.com/liveapi/guides/v4/
- https://the-odds-api.com/manage/troubleshoot-unexpected-usage.html
