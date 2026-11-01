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
