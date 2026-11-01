## Offline first-event semantic checks — 2026-11-01

Official-source review (public documentation GET only, no authenticated calls):
- https://dunkapi.com/docs/get-plays
- https://mcp.dunkapi.com/openapi.json
- https://dunkapi.com/docs/get-shot-chart

The get-plays page lists the observed sequence, period, clock, team, shot, points
and actor fields. Its examples associate player_id with the shooter, including a
miss, and player2_id with an assister in two examples. This is example evidence,
not a universal actor-role guarantee. The OpenAPI specification confirms the data
wrapper and describes post-play scores, but permits arbitrary event object fields.
It supplies no exhaustive event-type/actor-role dictionary or jump-ball winner
contract. Shot filters include field goals/free throws and six named zones.
The documented shapes agree with the owner's aggregate audit. Real private events
have not been inspected in Work. Universal scoring-player credit, nonshot actor
roles and possession ownership remain evidence gaps.

Added `semantics-audit-local`, using the existing single-snapshot read-only cache
loader. Raw hashes, HTTP status, manifest matchup, request/reservation provenance,
box identities/starters and frozen-window checks precede interpretation. No Store
constructor, key, request, file write or new reservation is used. No live adapter,
model settings, training or ingestion gate is changed.

Checks: full terminal page/count; ordered event game/sequence/period/clock; score
continuity and final box score; primary player membership against EVENT TEAM
ABBREVIATION through cached box team IDs; known secondary identities without
assuming their role/team; shot boolean made, integer attempted points, awarded
points, zone consistency and literal event-type conflicts. Zone-value consistency
and the finite literal-type vocabulary are conservative APEX validation rules,
not a complete provider contract. Unknown types are counted in an unreviewed
bucket, never guessed. Secondary actors on opposing teams can be legitimate;
no assist/winner role is assigned. Score corrections, null/missing shot actors,
unknown teams/roles, nonshot scoring, conflicting zones/types and incomplete
pages produce blockers. Same-clock events retain sequence order; duplicate or
reversed sequences fail. No source text parsing or sorting occurs.

First score (including FT), first FG attempt and first made FG are selected
independently when the strict existing event checks can run. Output is privacy-safe:
aggregate literal-type/zone/category counts, contradiction counts, and candidate
kind/roster/starter flags only. No event descriptions, names, player IDs or raw
records. Candidate starter membership is a cached historical box fact conditional
on the actor role; it is not pre-tip lineup evidence. interpretation_validated,
model_compatible and training_enabled remain false even if numerical checks pass.
Opening tip and possession remain unresolved absent a documented participant,
winner and possession contract. Report blockers state exactly which facts are
unverified. Command exit zero denotes structural checks passing, not source or
model promotion. The user must review the local report before any next stage.

Owner reports before this patch: 595 events, 258 shot objects, 136 positive scoring
transitions, no score discrepancies, final box agreement and increasing sequences;
candidate first score is a field goal by a starter. These are owner-reported audit
findings, not independently inspected outcomes. Two original requests remain 15
reserved/spent credits and wallet 485 per owner. No additional requests authorized.

Windows (existing APEX_V3_Pilot checkout):
```powershell
Remove-Item Env:DUNKAPI_API_KEY -ErrorAction SilentlyContinue
git branch --show-current
git status --short
```
Require v3/hybrid-monte-carlo and no local edits. If edits exist, stop and preserve
them. Otherwise pull; stop on failure:
```powershell
git pull --ff-only origin v3/hybrid-monte-carlo
```
Then run offline:
```powershell
& .\.venv\Scripts\python.exe -m unittest test_phase10 test_updater -q
& .\.venv\Scripts\python.exe phase10_dunk.py semantics-audit-local
```
Expect 119 tests, unchanged 15 reserved credits/two reservations, raw integrity
PASS, zero requests/reservations and no database changes. Actual semantic checks
and blockers depend on the unseen cached data. Share only aggregate output. No
key entry, database upload, init-local, run-local or continue-one-local is needed.
Do not treat a candidate or a zero exit code as a verified first-basket result.

Validation: 108 Phase 10 + 11 updater tests pass locally. Thirteen new synthetic
regressions exercise FT-first versus first made FG, missed first attempts,
nonstarter preservation, missing/wrong actors/teams, zone/type/result conflicts,
unknown secondary identities/types, jump balls/turnovers/violations, clock ties,
score corrections, incomplete games and read-only/no-key local execution. These
fixtures are fabricated; no provider raw data is published. Existing GitHub CI
runs full regression/Streamlit/checksum tests on Python 3.11/3.14; final status is
reported with the patch. Native Windows/real-source execution remains owner-local.
PR #1 stays draft, V2.44 and frozen settings unchanged; no deployment or scheduling.

## Offline real-event schema discovery — 2026-11-01

Owner reports the controlled first get_plays succeeded: game 401809243, HTTP 200,
595 event objects in data.plays, integer data.count, null data.next_offset, raw
SHA-256 PASS, count matching get_game. Two calls/reservations total 15 credits;
wallet 485. These are OWNER-REPORTED findings. Work has not accessed or inspected
the private event contents. No further provider requests are made or authorized
by this patch. Original manifest and all frozen model settings remain unchanged.

Added `events-audit-local`: no key, transport, writable Store, initialization,
reservation or report-file write. Reads one consistent read-only SQLite snapshot;
checks hash chain, original raw hashes, HTTP status, request/reservation linkage,
manifest matchup/date/game, historical identities and five starters per side.
Strict offline get_plays envelope recognition is separate from live transport:
only data object with plays list of objects, matching integer count (not bool),
and explicit next_offset of null or positive integer. Missing/mixed/nested
wrappers fail closed. Extra envelope metadata blocks a completeness conclusion
until reviewed; null cursor and count agreement are evidence of completeness,
not proof that every source event is present.

Output contains aggregate field paths, types, event coverage/missing counts,
null occurrences, conditional sequence/clock/score/identity consistency checks,
timezone-aware timestamp parsing counts and explicit blockers. Nested arrays are
inventoried without copying values; caps (250 paths, depth 5, first 50 array
members) report truncation. Sensitive or non-identifier keys are withheld. Values,
raw events, descriptions, player names/IDs, credentials and response hashes are
not printed. Schema paths are shown so the operator can review actual field names.

Checks on literal game_id/player_id/team_id, sequence fields, period/clock_seconds,
home_score/away_score/points are CONDITIONAL on their names, not an approved
provider mapping. Unknown nested clocks, alternative score names or event codes
remain unresolved; source order is never sorted or repaired. No numeric event-code
mapping, free-text scorer extraction or inference of first possession from the
first shot is performed. Existing synthetic-contract interpretation runs only
if every required field exists and pagination agrees; even then its outputs are
explicitly UNVERIFIED candidates and cannot activate training or predictions.
Provider event semantics and identity roles still require review. Opening tip,
first possession, first attempt, first made field goal, first score (including
FT), scorer identity and starter classification remain listed as unresolved
verified findings until supported by source-specific evidence. A successful
command exit means the envelope audit ran, not that model compatibility passed.

Windows offline instructions, in existing APEX_V3_Pilot:

```powershell
Remove-Item Env:DUNKAPI_API_KEY -ErrorAction SilentlyContinue
git branch --show-current
git status --short
```

Require branch v3/hybrid-monte-carlo and no local changes. Stop if edits are listed.
Then pull, stopping on any pull failure:

```powershell
git pull --ff-only origin v3/hybrid-monte-carlo
```

```powershell
& .\.venv\Scripts\python.exe -m unittest test_phase10 test_updater -q
& .\.venv\Scripts\python.exe phase10_dunk.py events-audit-local
```

Expect 106 tests passing. The actual report should retain reserved_credits 15 and
reservations 2, raw_integrity PASS, events_received 595, and new_requests and
new_reserved_credits 0. Fields/blockers depend on the actual unseen event schema.
Share ONLY the printed aggregate report. Do not upload SQLite, raw records or keys.
Do not run init-local, continue-one-local, run-local or any authenticated request.
No additional collection or retry is needed to inspect these cached events.

Validation: 95 Phase 10 plus 11 updater tests pass locally (106 total). Thirteen
new tests cover strict wrappers, fabricated nested event shapes, privacy,
free-throw-first candidate outcomes, missing/null fields, ordering, score
corrections, final-score mismatch, actor/game mismatch, timestamps, incomplete
and contradictory pagination, inventory caps and unchanged SQLite bytes with
network transport blocked. These are synthetic regressions, not observations of
real play semantics. Existing full regression/Streamlit/checksum CI is run on
Python 3.11/3.14 after publication; final status is reported with the patch.
Native Windows audit execution and source interpretation require the owner's
local report. V2.44, draft PR #1, frozen model, deployment and scheduling unchanged.

## Controlled one-request continuation — 2026-11-01

Owner confirms Windows replay and prior 84 tests passed; original cache remains
one get_game response/reservation (5 credits), wallet balance 495. No private
response was transferred to Work. No provider requests are executed by this patch.

New `continue-one-local` is opt-in with --execute, exact manifest hash, current
495-credit wallet attestation, no replenishment and exclusive account use. It
requires the existing private marker/database/ACL, valid original box and exactly
one real response/reservation totaling five credits. It holds the existing local
run lease, reuses the get_game cache, reserves ten and calls ONLY
get_plays(401809243, limit=1000, offset=0). It never calls the orchestration or
pagination loops. Transport independently restricts endpoint/body and permits
one HTTP invocation, consumed before dispatch. There are no automatic retries.
Subsequent execution fails closed when the original inventory has changed,
including an unresolved ten-credit attempt. Original evidence and configuration
remain unchanged. Lifetime cap is still 100; expected cumulative reservation is
15 and provider wallet should be 485 if billed exactly ten (verify locally).

Complete bounded response bytes are stored before JSON interpretation. The
one-request path also retains complete bounded non-200 response bodies privately;
no body is printed. A timeout, stream failure or response-size limit may prevent
saving a complete response, but the reservation persists and prevents a retry.
Cached HTTP errors cannot be reused as successful responses. No API key or headers
are archived. No shape inference activates a get_plays adapter.

New `plays-report-local` is offline, read-only and key-free. It verifies the event
chain, raw SHA-256 and request/reservation linkage and reports recognized field
types at top-level/data locations, list length, count agreement, null-next-offset
and additional-page indicators. It compares list length to cached get_game's
reported count without declaring completeness. Unrecognized schemas remain
unvalidated. No raw keys/records/player identities/source values are printed.
Never upload the database or raw provider responses. Share only this report.

Windows procedure (existing APEX_V3_Pilot checkout):

1. Clear process key; confirm branch and a clean checkout. Stop on local edits or
   pull errors. Never initialize or delete private storage again.

```powershell
Remove-Item Env:DUNKAPI_API_KEY -ErrorAction SilentlyContinue
git branch --show-current
git status --short
git pull --ff-only origin v3/hybrid-monte-carlo
& .\.venv\Scripts\python.exe -m unittest test_phase10 test_updater -q
& .\.venv\Scripts\python.exe phase10_dunk.py replay-local
```

Branch must be v3/hybrid-monte-carlo. Expect 93 tests passing and unchanged replay:
one response, one reservation, five credits, integrity PASS. Confirm no automatic
wallet replenishment and no other account users/jobs. No new authorization of the
original request manifest is needed. Local execution below is the explicit opt-in.
Do NOT use the older run-local command for this stage.

2. Enter the key hidden. This block executes only the controlled command and clears
   its process-local environment variable in finally. No setx, key file or command
   history containing the key. Closing PowerShell also destroys this environment.

```powershell
$secret = Read-Host "DunkAPI key (hidden; local only)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:DUNKAPI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    & .\.venv\Scripts\python.exe phase10_dunk.py continue-one-local --execute --confirm-wallet 495 --confirm-no-replenishment --confirm-exclusive-use --confirm-manifest c4309436dcae82adc9ee435f33a81acefa94385d32f9541b17a458428c72e905
} finally {
    Remove-Item Env:DUNKAPI_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    $secret.Dispose()
    Remove-Variable secret,ptr -ErrorAction SilentlyContinue
}
```

3. Whether saved or stopped, do NOT retry the live command. Run only:

```powershell
& .\.venv\Scripts\python.exe phase10_dunk.py plays-report-local
```

Expected after dispatch: cumulative reservation 15. A completed successful HTTP
response normally gives response_present true and raw_integrity PASS; a timeout
can give false. A next page or unfamiliar wrapper requires review; never fetch
another page automatically. Check wallet in the provider dashboard without making
API balance requests. Share sanitized report and balance only.

Validation: 82 Phase 10 + 11 updater tests passed locally (93). Nine new regressions
cover exact one-call stop, repeat block, timeout/429/invalid JSON retention, opt-in
and funding gates, missing DB/key, read-only diagnostics, transport rejection of
other games/pages and second calls. Existing GitHub CI runs full regression,
Streamlit smoke and checksum verification on Python 3.11/3.14; final run status is
reported with the patch. Native Windows key-entry/ACL execution is owner-local;
no new live-provider observations are claimed. V2.44, model parameters, pinned
manifest, draft PR, scheduling and deployment remain unchanged.

## Verified get_game wrapper correction — 2026-11-01

Owner-reported first real response for 401809243 has a `data` envelope containing
`game`, `players`, integer `plays`, and optional odds/team statistics/win probability.
The original private database is not accessible in Work. Owner reports one saved
response, SHA-256 PASS, one 5-credit reservation, 27 players, five starters per team,
and 595 reported plays. This is not evidence that 595 events were downloaded.

Changes: endpoint-specific get_game normalization after exact raw-response storage;
strict rejection of malformed, mixed and nested wrappers; legacy top-level synthetic
fixtures retained. No generic get_plays unwrapping. The same normalization applies
on cache hits, before any new reservation. Cache keys, raw bytes/hash, existing
pilot registration, game manifest, budget and retry/pagination controls are unchanged.
Shared historical box validation is reused by the event auditor and offline replay.

`python phase10_dunk.py replay-local` reads the original fixed private database in
SQLite URI mode=ro with query_only enabled. It checks database/hash-chain/raw checksums,
reservation/request provenance, identity/matchup/date/final/regular-season status and
historical starters. It prints only sanitized counts and checks. It creates no Store,
transport, lease, report file or reservation; no API key is needed. PASS does not
authorize or launch continuation. Native Windows ACL behavior and the owner's real
cache require the local check; Linux fixtures cannot establish those results.

Windows offline procedure (PowerShell, in the existing V3 Git checkout):

1. Close any pilot process. Keep the original private directory intact. Never run
   init-local again or delete/recreate pilot.sqlite3. Remove any process-local key:
   `Remove-Item Env:DUNKAPI_API_KEY -ErrorAction SilentlyContinue`.
2. Run `git branch --show-current` (must be v3/hybrid-monte-carlo) and
   `git status --short`. If local edits are listed, stop and preserve them before
   pulling. Otherwise `git pull --ff-only origin v3/hybrid-monte-carlo`.
3. `.gitattributes` pins only the request JSON to LF on Windows. The manifest bytes
   and hardcoded SHA-256 are unchanged; CRLF is rejected, never normalized by the
   validator. If an existing clean checkout retains CRLF, force checkout of this
   one tracked file: `git checkout-index --force -- validation/PHASE10_REQUEST_MANIFEST.json`.
   Do this only after confirming no local/staged edits. Check:
   `(Get-FileHash validation/PHASE10_REQUEST_MANIFEST.json -Algorithm SHA256).Hash.ToLower()`
   must equal `c4309436dcae82adc9ee435f33a81acefa94385d32f9541b17a458428c72e905`.
4. Using the Python environment that ran the pilot, run
   `python -m unittest test_phase10 test_updater -q`, then
   `python phase10_dunk.py replay-local`. No installation/key entry/live flags needed.
5. Expect integrity PASS, one response, one reservation, reserved credits 5,
   new requests/credits 0, game 401809243, starter counts [5,5], 27 player records,
   reported plays 595. opening_events_validated and continuation_enabled remain false.
   If anything differs or STOPPED appears, stop and share only the sanitized output.
   Do not upload SQLite, raw responses, identity files, headers or credentials.

Next stage is a separate reviewed local run, not part of these commands. It must use
the same database and unchanged manifest. Cached get_game costs no additional five
credits; the next approved uncached request is get_plays(401809243, limit=1000,
offset=0), reserving ten. Remaining original requests total 70 credits (75 lifetime
expected including the existing five); ceiling remains 100. Unknown get_plays shape
or pagination stops execution with bytes/reservation retained, not automatically
retried. No get_plays wrapper is inferred here. Existing wallet funding, no top-up,
exclusive account use and secure local-key checks still apply. --confirm-wallet 500
represents the originally authorized wallet baseline, not a claim that its current
remaining balance is still 500. Provider debit is not independently measured.

Validation: 73 Phase 10 tests + 11 updater tests pass locally (84 total), including
wrapped and malformed payloads, read-only byte preservation, live-path synthetic
cache reuse, failed wrapper retention and rejection of CRLF manifest bytes.
Existing GitHub CI runs the full regression suite and Streamlit smoke on Python
3.11/3.14 after branch publication; final run status is reported separately.
No authenticated provider calls, raw-data publishing, model changes, deployment,
scheduling or main-branch changes are part of this patch.

# Phase 10 — opt-in Windows local CLI

Default status remains offline. Existing ten-request wallet authorization persists. No authenticated requests executed from Work. The new run-local command can activate only on Windows outside CI after local preflight. No scheduling, model changes or PR merge.

Local tests: 65 Phase 10 tests plus 11 updater tests passed. Includes synthetic end-to-end ten requests/75 credits, missing database refusal, manifest pin, default disable, funding flags, Windows/cloud gate, ACL failure before transport and report sanitization. Windows ACL calls were mocked in Linux, not natively executed here. Runtime verifies them and fails closed. Existing GitHub CI covers regression/smoke/checksums on Python 3.11/3.14.

## Local storage and limits

Fixed private location: %LOCALAPPDATA%\APEX\DunkPilotPhase10. This is independent of the source checkout. Initialization sets a protected current-user-only Windows ACL; every run rechecks ownership, allowed principals, links and Git overlap. Identity marker and original pilot.sqlite3 are required. Never delete, move, replace or reinitialize that directory to retry a run; interrupted reservations count for life. Protect this directory with your normal encrypted Windows backups. It contains original provider records and must never be uploaded to GitHub or shared. It is access-controlled, not application-encrypted.

run-local requires --execute, --confirm-wallet 500, --confirm-no-replenishment, --confirm-exclusive-use and the pinned manifest hash. These confirm execution conditions, not new authorization. Enter them only after observing the approved existing wallet/account and verifying no automatic replenishment/overage mechanism or other account consumer. Provider funding is server-selected; there is no API-side wallet-selector guarantee. If uncertain, stop. The runner has no purchase or subscription routes.

The complete manifest bytes are pinned to c4309436dcae82adc9ee435f33a81acefa94385d32f9541b17a458428c72e905. Changing the manifest blocks execution. All five dates must still fall within 400 earlier calendar days at execution. No pagination beyond offset=0 is approved. A missing terminal signal, required extra page, contradictory data or audit issue stops further games. No automatic retry. A changed wire schema may stop after one charged call; preserve its response for private analysis. The pilot does not claim full model compatibility or possession-role interpretation solely from source labels.

## Windows PowerShell: isolated checkout

Keep your existing V2.44 folder untouched. Git for Windows and Python must be installed. This command stops if Git/Python are missing or the target folder has local changes.

```powershell
$ErrorActionPreference = 'Stop'
Get-Command git, py | Out-Null
$pilotCode = Join-Path $env:USERPROFILE 'Desktop\APEX_V3_Pilot'
if (!(Test-Path $pilotCode)) {
    git clone --single-branch --branch v3/hybrid-monte-carlo https://github.com/kaishawn01/apex-first-basket.git $pilotCode
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
} else {
    if (!(Test-Path (Join-Path $pilotCode '.git'))) { throw 'Folder exists but is not the pilot Git checkout' }
    $dirty = git -C $pilotCode status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Stop: checkout has local changes; do not overwrite them' }
    git -C $pilotCode switch v3/hybrid-monte-carlo
    if ($LASTEXITCODE -ne 0) { throw 'Branch switch failed' }
    git -C $pilotCode pull --ff-only origin v3/hybrid-monte-carlo
    if ($LASTEXITCODE -ne 0) { throw 'Update failed' }
}
Set-Location $pilotCode
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe -m unittest test_phase10 test_updater -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed: do not execute pilot' }
& .\.venv\Scripts\python.exe phase10_dunk.py status
```

## Initialize once, no API requests

Only if no previous local Phase 10 execution/storage exists. If the command says the directory exists, STOP and inspect it; never delete it to get past this safeguard.

```powershell
& .\.venv\Scripts\python.exe phase10_dunk.py init-local --confirm-no-prior-pilot
if ($LASTEXITCODE -ne 0) { throw 'Initialization stopped; preserve existing storage' }
```

## Run once with a hidden process-local key

Check your dashboard manually first: approved existing wallet 500; no automatic replenishment/overage; exclusive account use for this run. No account changes are authorized. If any condition is unknown, stop here. The following flags explicitly attest those conditions. Do not run from a transcript-recording session, put the key in chat, use setx or commit a credential file.

```powershell
$secureDunkKey = Read-Host 'DunkAPI key (hidden; stays in this PowerShell session)' -AsSecureString
try {
    $env:DUNKAPI_API_KEY = [System.Net.NetworkCredential]::new('', $secureDunkKey).Password
    & .\.venv\Scripts\python.exe phase10_dunk.py run-local --execute --confirm-wallet 500 --confirm-no-replenishment --confirm-exclusive-use --confirm-manifest c4309436dcae82adc9ee435f33a81acefa94385d32f9541b17a458428c72e905
    $pilotExit = $LASTEXITCODE
} finally {
    Remove-Item Env:DUNKAPI_API_KEY -ErrorAction SilentlyContinue
    if ($secureDunkKey) { $secureDunkKey.Dispose() }
    Remove-Variable secureDunkKey -ErrorAction SilentlyContinue
}
if ($pilotExit -ne 0) { Write-Warning 'Pilot stopped. Do not automatically rerun or delete its database.' }
```

The environment variable is process-local plaintext memory inherited only by child processes; hidden entry prevents screen/history exposure, not all administrator-level access. Closing PowerShell also removes it. Do not rerun after a failure without reviewing reserved attempts. Keys are not passed to the Windows ACL subprocess.

## Inspect/share only the sanitized output

```powershell
& .\.venv\Scripts\python.exe phase10_dunk.py report-local
$pilotReport = Join-Path $env:LOCALAPPDATA 'APEX\DunkPilotPhase10\sanitized_results.json'
if (Test-Path $pilotReport) { notepad $pilotReport }
```

Upload only sanitized_results.json to this chat. It contains game IDs, status, starter counts, event counts, first-score category, first-attempt make/miss and whitelisted integrity flags. It excludes names, player IDs, raw text/events, credentials and original headers. Never upload pilot.sqlite3, identity.json, the entire private folder or raw responses. If no report exists, share only the generic STOPPED message. Existing reports can predate a failed new attempt; preserve storage and report that context. reserved_credits is a conservative reservation total, not independently verified provider debit. Manually compare wallet before/after and tell us the observed debit; no refund is presumed. Native filesystem failure and first live provider schema remain unverified until local execution.

---

# Phase 10 — existing-wallet authorization update

2026-11-01: The owner explicitly authorizes the existing wallet for the five-game manifest: ten initial requests, expected 75 credits, absolute lifetime maximum 100 including failures and separately approved pagination. Monthly-free-only restrictions below are historical and superseded. No purchases, subscriptions, new games, lookups or automatic retries are authorized. Pagination is not currently authorized. No need to obtain the same request authorization again.

The original provider email and verification note have been inspected and retained privately; neither original nor headers are published here. Saved email authentication results were observed, not independently cryptographically verified. Provider permission covers private research/retention and derived probabilities; independent NBA rights clearance is not established.

**Execution status: BLOCKED before requests.** DUNKAPI_API_KEY is absent from the execution environment. Owner wallet authorization is accepted; it is not an API-authentication credential. The wallet transport is implemented but defaults disabled, with no automatic CLI activation. No live calls/reservations occurred and actual pilot consumption is zero. Starters, first shot, first score, opening-possession integrity and model compatibility remain unmeasured on real responses.

## Transport and funding boundary

WalletTransport permits only the exact ten manifest URL/body pairs, fixes TLS verification through requests defaults, disallows redirects, disables environment proxy/netrc inheritance and HTTP retries, supplies deterministic idempotency keys, and redacts transport errors. Pilot reserves credits transactionally before transport and retains reservations on failure/interruption. A shared lease, cache and immutable configuration protect restarts and duplicate calls. Extra pages stop before any call; they need separate approval. The same original lifetime journal must be used, never replaced to reset spending.

Funding is selected by DunkAPI, not a documented request parameter. Published terms say plan credits are consumed first, then wallet credits (https://dunkapi.com/terms). The owner's current billing observation establishes the intended existing-wallet source. Local tests prove the runner cannot call purchase/top-up/subscription routes or exceed its reserved-cost limit; they cannot prove server billing correctness, guarantee current server balance or prevent another client spending the account. The future operator preflight must confirm the account/key matches the authorized wallet, no concurrent spending or automatic top-up/overage behavior, applicable per-call prices and sufficient existing balance. If these cannot be established, leave funding_confirmed false and stop. Do not make additional balance/account calls without authorization. Never infer a provider refund or erase a reservation.

The credential should be supplied only through a private process environment/approved secret channel, not chat or GitHub. Existing PowerShell hidden-input instructions below remain applicable. Credentials stored in a laptop Streamlit session are not automatically available to this execution environment. No key was printed or accessed.

## Tests

54 Phase 10 local fixture tests and 11 updater tests passed (65 total). Nine new wallet tests cover default disable, absent credential, unconfirmed funding, rejected monthly-only source/manifest mutation, forbidden purchases/lookups/pagination, 75-credit ten-call caching, prior-budget exhaustion and timeout redaction/no retry. The live transport was exercised only with a mocked session and synthetic key in disposable temporary stores. No fixture was published as a real observation. Existing GitHub regression CI runs on the branch push. Frozen model, production V2.44 and scheduling unchanged.

---

# Phase 10 clarification update — 2026-11-01

**NOT READY for authenticated requests.** Preparation only; no DunkAPI requests made. V2.44, frozen model, scheduling and draft PR status remain unchanged.

## Permission evidence update

The owner supplied a summary of written clarification from Noah at DunkAPI in this conversation. It reports permission for automated retrieval, private cloud storage, model training, publishing derived probabilities and retaining private historical/audit records; raw play-by-play dataset/feed republication is prohibited. It reports stable game/team/player IDs, historical starter flags, get_game costing 5 credits, and get_plays costing 10 credits with limit=1000 expected to cover an NBA game. These are **owner-supplied provider statements**, not independently authenticated correspondence or demonstrated API behavior. No accessible email connector/original message was available. Please supply the original .eml or full forwarded email for private archival verification; do not include credentials. Do not publish its headers, contact details or raw email in this public repository. Preserve original bytes, receipt date and SHA-256 in permitted private storage when received.

This supersedes the earlier statement that no provider response exists. The original unsent inquiry below is retained as historical preparation, not the current status. DunkAPI is independent; neither this email summary nor this assessment establishes independent NBA rights clearance. The applicable terms/acceptance version and any additional upstream restrictions remain review items. No need to ask again for permissions already explicitly addressed in the owner's summary; archive the evidence and resolve remaining technical ambiguities.

## Exact five-game manifest

See `validation/PHASE10_REQUEST_MANIFEST.json`. IDs appear in DunkAPI's published points/steals guide examples (URLs in manifest), not inferred from ESPN numeric equality. Matchups/date/final status must be checked against the first get_game response before any get_plays request. Selection uses published completed-game examples, not a statistical evaluation sample. Dates are inside the 2026-11-01 earlier-date 400-day window; recheck at execution.

| DunkAPI game ID | Date (Eastern) | Matchup | Selection purpose |
|---|---|---|---|
| 401809243 | 2025-10-21 | HOU at OKC | Long-game completeness / overtime |
| 401809236 | 2025-10-23 | OKC at IND | Overtime and free-throw handling |
| 401809943 | 2025-10-24 | ATL at ORL | Different matchup |
| 401809956 | 2025-10-25 | OKC at ATL | Repeated identity checks |
| 401809970 | 2025-10-27 | ATL at CHI | Repeated identities / different opponent |

No claim that these particular opening sequences include every desired event. Rare opening FT/nonstarter outcomes may remain untested after five games; fixtures cover edge cases without substituting for live evidence. Public game-page metadata was checked for completion; no play-by-play was ingested. NBA game 0022500005 corroborates the OKC/IND completed matchup. Public references are metadata evidence, not a dataset license.

Each game has exactly two proposed query-style POSTs to https://mcp.dunkapi.com/v1/: `get_game` with `{game_id}`, then `get_plays` with `{game_id, limit:1000, offset:0}`. No key appears in the manifest. Ten initial requests reserve **75 credits**. Lifetime ceiling **100**, including all failures, additional pages, retries and lookups; lookups and automatic retries are disabled. Two additional 10-credit pages could bring reservations to 95; the next would be refused. Additional calls require explicit approval within the same cap. Preserve the same journal across restarts; never reset reservations or assume provider refunds.

**Balance not confirmed.** A nominal 500-credit allowance is not a current balance. Before any authenticated request, the owner must provide a fresh dashboard observation of remaining *free* credits and confirmation no wallet/paid funding will be used. Require at least 75 for initial requests; at least 100 to authorize the entire contingency envelope. Record observation time privately; recheck if another consumer uses the account. Do not call an account endpoint to obtain this without approval. The current code has no live transport and therefore cannot spend against an unverified balance.

Stop on identity/date/type mismatch, expired window, unclear permission/balance, manifest change, missing starters, contradictory actor/score data, incomplete pagination, unexpected response envelope, unexpected credit cost, rate limit, transport failure or budget exhaustion. Never treat the reported typical 500-event length as proof of completeness. Require terminal-page semantics and reconcile count, opening boundary and final score. The reported limit=1000 does not yet verify the actual next_offset terminal representation or envelope.

## Source-native adapter design (not activated)

Use provider-qualified identities `(DunkAPI, entity_type, source_id)` and `dunk_<game_id>` game keys. Never reinterpret these as ESPN IDs. Keep source-to-internal numeric player IDs in an immutable bijective registry where existing numeric validation requires integers; reuse an internal ID only with reviewed identity evidence. Historical lineup membership comes from the game, not today's team. Store raw response hashes, manifest hash, retrieval time, source schema/version and original IDs alongside normalized records. Keep originals and mapping evidence private.

A future provider registry in phase7_training must validate each provider's actual provenance, identity namespace and evidence scopes, while preserving checksums, window/date exclusion, ten unique starters, outcome/sequence agreement and the existing 100-prior-game primary eligibility rule. Permission grants remain owner-approved, bundle-hash-bound and expiring; owner-reported correspondence must not masquerade as authenticated original evidence. The current ESPN-only gate stays closed to DunkAPI until reviewed implementation/tests pass. Existing ESPN history remains separate; no overwrite or implicit merge.

Normalize first FGA separately from first score, including FTs and nonstarters. Preserve unresolved mass. Current audit retains source event labels/secondary IDs but does **not** infer jump-ball winner, rebound possession, turnover owner or substitution direction from a label alone. Those semantics need permitted real samples. Final totals are audit checks, never pregame features. Preserve the opening-three-minute/first-substitution model rules and all frozen parameters. Adapter/protocol registration must be versioned because existing experiment hashes cover training/live source files.

## Local verification and remaining gates

45 isolated Phase 10 fixture tests passed: original 38 plus seven preparation/edge-case tests. Coverage includes lifetime budget/restart/cache behavior, historical starters, missed first attempt before FT first score, nonstarter/unknown outcomes, source jump-ball/rebound/turnover/substitution label preservation, ordering, final-score diagnostics, and exact manifest shape. Label preservation is not validated possession reconstruction. No synthetic result is a real NBA forecast. Existing GitHub CI is requested by the branch push; consult its run status rather than treating local success as remote success.

Remaining: original email archival verification; fresh free-only balance; explicit approval of this manifest; real response/pagination and event semantics; provider-aware model adapter and sufficient eligible history. Ask for authorization only for the concrete manifest above; no purchase, trial, scheduling, model change or merge is included.

---

# Phase 10 — DunkAPI Free Pilot preparation (development V3.0.9)

**Live ingestion is disabled.** This release prepares and fixture-tests a five-game audit. It does not claim five actual games were collected or mapped into the frozen Monte Carlo model. BALLDONTLIE authentication is already resolved; no account diagnostic is repeated.

## Permission decision

Reviewed October 29, 2026, America/New_York. [DunkAPI terms](https://dunkapi.com/terms) permit model training, retained data and derived outputs, prohibit standalone dataset redistribution, and preserve third-party restrictions. Terms differ for accounts created before October 17 until November 16. The user's applicable acceptance version has not been inspected. [Timing and rights](https://dunkapi.com/docs/timing-and-rights) does not identify upstream sources per dataset or grant league rights. NBA-specific provenance/restrictions remain unresolved. No account, trial, purchase, provider message or credit-consuming query was made.

This is a specific missing permission finding, not a claim that all sports facts are prohibited. Written clarification or equivalent applicable source evidence is required before this project's live ingestion gate changes. General API access is insufficient under the user's requested boundary.

Unsent clarification request: Please identify the applicable source restrictions for NBA historical opening-event and starter records. Does our existing Free account permit a five-game, at-most-100-credit pilot, local/private cloud retention of original responses and hashes, model research and publication of derived probabilities without redistributing records? Please confirm no paid balance, subscription, trial, replenishment or future payment commitment is needed, and clarify IDs, pagination terminal signals and complete-game event counts. No purchase or activation is authorized. Sending this requires a separate user instruction.

## Implemented and deliberately not implemented

`phase10_dunk.py` reuses the existing append-only Store. Its Pilot transport is dependency-injected **for synthetic fixtures only**. There is no default network transport, live CLI, permission override, or secret-reading network path. Normal fetch calls without fixture transport fail before any request. This is tested integration preparation, not an activated provider connector. The frozen model, existing live collector, dashboard and registered protocol are untouched.

The `status` command makes no network request and prints only credential presence, not its value:

```bat
.venv\Scripts\python.exe phase10_dunk.py status
```

The source-native inspector audits dates, strict chronological eligibility, completed regular-season identity, five starters per team, player/team membership, event order/clocks, score continuity, explicit pagination and total event count. It distinguishes FG attempts, made FGs and first points including FTs; nonstarter/unknown identities are retained. Source faults and skipped games remain explicit. A player crosswalk must bind independent evidence to the source hash; matching numeric IDs is never sufficient. Full game/team mapping and production adapter remain unapproved. `model_compatible` is always false in this preparation release.

## Budget and request design

Published [get_plays](https://dunkapi.com/docs/get-plays) costs 10 credits and [get_game](https://dunkapi.com/docs/get-game) costs 5. Five initial pairs would reserve 75; two further plays pages bring that to 95, and another plays request is blocked. This is not a promise of provider billing or complete retrieval. Prices and actual free-only balance must be confirmed before a future live release.

The lifetime pilot cap is min(100, supplied free balance), never a daily reset. Exactly five unique source-native game IDs are registered immutably. Calls reserve credits before transport. Failure/interruption never automatically refunds or retries; unfinished reservations block repeating the same request. Cached original responses cost no extra simulated credits. A shared request lease prevents overlapping local workers. Same state file is mandatory; no multi-account, state-reset or concurrent external consumer workaround. No subscription/top-up path exists.

Only the documented query-style POST paths get_game/get_plays are supported at the fixed official host. No redirects; response size/time limits; conservative seven-second spacing; 429 stops with a persistent cooldown and requires review before any manual resumption. Changing provider rate/cost rules requires review, not fallback. These controls are fixture-tested and not yet observed against the provider.

## Pagination and original evidence

The default documented plays page is 200 events. The prepared request asks for 1,000 but does not assume the server honors it. It follows strictly advancing next_offset values, requires an explicit null terminal cursor and reconciles all returned events against get_game's plays count. Missing terminal signals, loops, mismatched counts or exhausted budget leave the game incomplete. A real terminal representation differing from this assumption requires a reviewed parser update; never infer completeness from a short page.

Synthetic tests cover both one- and two-response games. **Whether one actual request returns a complete game is unverified.** An internally consistent provider event count is not independent proof that the source omitted no events. Opening boundary, missing score and unknown actor warnings remain visible.

The existing Store preserves exact response bytes as base64 plus SHA-256, request parameters, retrieval time and append-only hash-chain evidence. Responses are immutable, cached and recoverable through existing Store export/restore. Only synthetic originals are stored during tests. For any future permitted live pilot, use a private directory outside every Git checkout (for example `%LOCALAPPDATA%\APEX\DunkPilot`) with appropriate Windows user-only access and encrypted backup if needed. Never upload source records or their private audit bundle to the public research-data branch. Storage permission is not established merely by choosing a private path.

## Chronological and model compatibility limits

The inspector emits a narrow factual opening-event audit, not model inputs. It discards expected_points, win probabilities, ratings, final box-score totals as features, and market data. Final totals are used only for retrospective consistency checking. Historical starters are postgame observations, never pre-tip confirmations. The provider documents retrospectively fitted expected_points and overwritten corrections; preserve retrieval versions rather than claiming point-in-time source snapshots.

The existing training validator remains ESPN-specific. No source is relabeled ESPN. Full source-native mapping, jump-ball/possession semantics, substitutions and like-for-like frozen-model probability parity need genuine permitted samples. No model code, weight, calibration, seed, trial count, Other handling or training window changes. Five games can test format compatibility but cannot meet the registered 100-prior-game eligibility floor or establish predictive superiority.

## Set a key locally only when needed

No key is needed for fixtures, and setting it does not enable ingestion. In a **PowerShell** window, use a hidden prompt to set a process-local variable without putting the key into command history:

```powershell
$secureDunkKey = Read-Host 'DunkAPI key (hidden)' -AsSecureString
$env:DUNKAPI_API_KEY = [System.Net.NetworkCredential]::new('', $secureDunkKey).Password
Remove-Variable secureDunkKey
```

Do not echo the variable, use setx, place it in source files, or share it in chat. It exists as plaintext in that process environment and child processes, not encrypted secret storage. Clear it afterward:

```powershell
Remove-Item Env:DUNKAPI_API_KEY
```

## Validation and activation boundary

Run `python -m unittest test_phase10 -v` for synthetic five-game, pagination, cap, failure, immutability and recovery checks. Full regression and CI results are recorded in `validation/PHASE10_RESULTS.json` and `V3_REVIEW.md`.

Next prerequisites: applicable NBA permission evidence, verified free-only balance/cost boundary, private storage review, and five preselected completed games. Live transport remains unavailable until these are resolved and reviewed. No production schedule, Starter subscription, V3 merge, public deployment or real forecast is enabled.
