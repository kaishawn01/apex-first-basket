# Phase 8 — controlled operations, V3.0.7

**Live NBA collection is not activated.** The only cloud exercise in this phase uses synthetic fixtures. The existing Phase 7 prediction configuration, primary pre-tip window, source files and model weights remain frozen. `main`, the V2.44 installation and existing journals are preserved.

## What is implemented

`phase8_access.py` is a read-only, local diagnostic client for BALLDONTLIE's official interface. It can inspect plans/subscriptions and parse free game/player pages. It cannot change billing, register accounts, start trials, fetch paid plays/lineups/injuries, or call arbitrary URLs. It is not connected to `phase7_live.py`: replacing an ESPN adapter with another provider requires lawful history, compatible events and reviewed identity mapping first.

The client uses GET-only endpoint allowlists, refuses redirects, omits raw credentials/account metadata from diagnostic output, bounds response size to 2 MB, and applies a 15-second transport timeout. Every attempt is counted before HTTP. It makes no automatic retries; 429 cooldowns persist, including Retry-After. Free quota changes or missing/stale entitlement checks stop data reads. It uses a conservative local ceiling of 20 attempts per Eastern day and 13 seconds between requests, shared through one Store file and a request lease. Do not reset that file to bypass limits or run different state files against the same key. These local limits are not a durable multi-runner quota system; cloud activation of this client is intentionally not implemented.

Plan inspection is GET `/account/v1/plans/nba`; subscription inspection is GET `/account/v1/subscriptions`. Account authentication uses Bearer while NBA data requests use the documented key header. No GET `/me` is used because that response can expose credentials. Only selected NBA plan/status fields are printed. Billing renewal/overage settings and remaining account-wide quota are not inferred from the subscription response.

`validate_source_evidence` verifies scope, timestamps, upstream-review status and fixture/live separation. It does not magically verify a provider's legal grant. Do not populate approval fields with invented evidence. BDL analytical permission does not satisfy the Phase 7 ESPN bundle gate.

## Safe manual account inspection

Use the existing securely configured environment variable `BALLDONTLIE_API_KEY`. Do not put the key in a command argument, repository file, screenshot or chat. No key was available to perform these account calls during development.

```sh
python phase8_access.py plans --state data/phase8/access.sqlite3 --enable-read-only
# Wait at least 13 seconds; use the same state file.
python phase8_access.py subscriptions --state data/phase8/access.sqlite3 --enable-read-only
```

These commands do not authorize a forecast, subscription change or automatic collection. If disabled globally, missing credentials, blocked by quota, malformed response or account failure, they stop. Investigate locally; never automatically follow a payment link or switch to a paid endpoint. `APEX_AUTOMATION_DISABLED=true` blocks this client as well as the existing cloud jobs.

## Synthetic acceptance and frozen configuration

```sh
python phase8_fixture.py generate --journal /tmp/apex-phase8-test/journal.json
python phase8_fixture.py grade --journal /tmp/apex-phase8-test/journal.json
python phase6_smoke.py /tmp/apex-phase8-test/journal.json
python -m unittest discover -v
python ui_smoke.py
```

The Phase 8 wrapper calls the unchanged Phase 7 fixture/model, with an explicit **test-only model-version pin to 3.0.6**; the application release is 3.0.7. No model is retuned. Its fixed synthetic timestamp, synthetic game and test-only flag must never be used as a genuine prospective observation. All sports HTTP calls are disabled in the fixture. Trials remain 2,000, seed 3,000, selector and calibration unchanged. The registered Phase 7 protocol remains `apex-v3.0.6-live-01`.

`.github/workflows/apex-phase8.yml` runs the fixture in three isolated jobs: generation/publication, separate-runner grading/publication, and fresh-runner read/integrity/dashboard verification. A relevant V3 push may trigger it; this is an isolated test, not production scheduling. It uses standard public-repository Ubuntu runners, eight-minute job limits, a shared non-overlapping archive-writer group, no paid provider keys, no artifacts/cache service and no active cron. Fixture records are written only to `fixtures/<code SHA>/` on `apex-research-data`. All previous fixtures remain intact. No genuine `live/` journal is created.

Remote Git publication is verified independently of local generation. Original forecast entries are immutable and grading appends separate results. The existing report preserves first observed remote timestamps; Git commit timestamps alone are not external notarization. A post-tip receipt cannot retroactively qualify a prediction. Existing prefix/hash checks and fast-forward-only writes remain unchanged. Corruption, collisions and missing receipts fail rather than overwrite evidence.

## Real-game procedure — blocked until prerequisites exist

The dispatcher template remains disabled and pinned to reviewed Phase 7 implementation commit `95e4a736bb72d64012d6af9688ba857bffcb380d`. It was not installed on main. Use the exact registered model code/version for a future live run; do not mask a genuine version with the fixture's mock or merely run the latest application under an older experiment ID.

Before a real run: establish source rights, approve the exact training/provenance hashes and storage, verify current team identities, confirm fresh game status, and satisfy the existing owner/live gates. The frozen runner refreshes status before committing a forecast. Predictions need at least 30 seconds lead at append and valid cloud receipts. Outside-primary observations stay secondary; no timing-rule change is permitted to gain a result.

After publication, another runner must retrieve the same immutable forecast/hash and original timestamps. After completion, a permitted source must provide the correct game and first-scoring identity. First points (including free throws), first made FG and first attempted FG remain different facts. Ambiguous or missing outcomes stay pending. No first-result record has been created for a genuine Phase 8 game.

## Recovery, permissions and cost boundary

The user has not authorized dispatcher installation, live scheduling or a public dashboard deployment. Preserve the existing template until a separate decision. No new infrastructure or trial was created. BDL GOAT and commercial NBA feeds are optional future considerations, not enabled fallbacks. Account spending settings remain unverified.

If the local diagnostic fails, retain its state file and respect cooldowns. If publication fails, preserve the journal, clone the data branch afresh and run `phase6_git.py verify`; do not force-push or replace evidence with an empty archive. Global disable stops subsequent jobs; an already running job must be canceled separately. Capacity limits still stop collection rather than delete forecasts. Returning to V2.44 requires no deployment rollback because production never changed.

See `validation/PHASE8_RESULTS.json` and the Phase 8 section of `V3_REVIEW.md` for actual test and cloud observations. A synthetic workflow pass demonstrates mechanics only, not permission clearance, live reliability or predictive advantage.
