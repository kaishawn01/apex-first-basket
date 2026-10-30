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
