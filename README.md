APEX V2.26.0 — Export reproducible research data

A new Share research data section prepares a data-only ZIP on demand. It contains saved history in known history columns, a quality-issue CSV, valid team coverage for the selected date's 400-day window, engine/model/date metadata, a readme and SHA-256 checksums. Flagged rows remain included for diagnosis. Export does not modify or repair local history.

The exporter builds files in memory from the provided history and explicit settings. It does not read API-key files, environment variables, app configuration, odds or the forward journal. Extra history columns are omitted. No API request, upload, backtest or background job is triggered. The download becomes stale when history, analysis date, model or version changes. Review the archive before sharing it; it is a research dataset, not an app backup. Matching engine version and an explicit evaluation training minimum are needed for reproducible comparisons.

This makes it possible to review actual saved-game evidence before changing prediction formulas. It does not establish accuracy, validate betting returns or change the live model.

Validation: 159 unit tests and all Streamlit smoke checks passed. Added checks cover archive member allowlisting, SHA-256 checksums, CSV round trips, excluded extra fields, no file/API reads during export, preserved flagged rows, date-window coverage, empty data, invalid settings, download availability and stale-date invalidation. Windows execution was not tested here.

APEX V2.25.0 — Separate adaptive decisions from fallback performance

Signal comparison now includes an adaptive-performance section restricted to games where the selector had the required 100 earlier evaluated games within its 400-day window. Every fixed variant and the selector are measured on exactly that same subset. Eligibility is determined from prior sample size, never the current outcome. A learned decision to keep the current blend remains included; the report does not cherry-pick games where the selector switches.

The section shows matched metrics, selector-minus-current-blend date-bootstrap intervals, counts of each chosen signal, eligible dates and excluded fallback games. Summary and per-game CSV exports are available. If all games used fallback, the app explicitly says that learned choices have not yet been tested. Full-period and recent-period results continue to include fallback games so total performance stays visible. Intervals use already-produced forecasts and do not include all uncertainty from the selection process.

This adds no model tuning, prediction changes, live selection or API requests. The experimental selector remains in Backtest lab. Historical starter-selection bias, small samples and dependence across dates remain limitations.

Validation: 154 unit tests and all Streamlit smoke checks passed. Added checks cover identical eligible game sets, retained learned choices of the current blend, eligibility independent of current outcomes, all-fallback/empty cases, mismatch rejection, real walk-forward crossing of the selection threshold, and both fallback/active dashboard displays and exports. Windows execution and predictive improvement on user history were not tested here.

APEX V2.24.0 — Test selection learned from earlier forecasts

The signal-comparison experiment now includes Earlier-date selector. For each evaluation date it selects among the existing 65/35 blend, shot-only and score-only variants using their mean log loss on earlier evaluated games within the preceding 400 days. It requires at least 100 prior evaluated games, beyond the underlying model's training warmup. Before that it falls back to the current blend. Numerical ties prefer the current blend, then shot-only, then score-only. All games on one date receive the same selection before any outcomes from that date enter selection history.

This is a discrete, global selection for the chosen model, not player-specific or continuously fitted weights. The report lists daily decisions, selection sample sizes, earlier losses and fallback usage, with CSV export. It compares the adaptive candidate on the same games and newest-quarter dates as fixed variants. Bootstrap intervals resample already-produced forecasts; they do not refit the selector or capture all selection uncertainty. Historical observed-starter/nonstarter-selection bias remains.

The candidate runs only in Backtest lab. Live rankings and saved forward forecasts continue using the fixed 65/35 blend. The experiment makes no API calls and does not promote a model automatically. Predictive improvement must be measured on real history and then prospective data.

Validation: 149 unit tests and all Streamlit smoke checks passed. Added checks cover the 100-game fallback threshold, same-day/future outcome isolation, 400-day selection boundaries, deterministic ties, immutable inputs, selecting the actual earlier-chosen forecast, invalid/duplicate inputs and decision exports. Windows execution and predictive improvement on user history were not tested here.

APEX V2.23.0 — Compare the two player signals

Backtest lab now has Compare opening-shot vs first-score signals for the selected model. It evaluates the current 65/35 blend, opening-shot rates alone and first-score rates alone on identical historical games, with the same chronological 400-day training window, team probabilities, priors and lineup rules. Signal weights mix smoothed player rates before within-team normalization. The baseline first-score rate is unconditional; recent and lineup models use a conditional rate given the team scores first.

The report includes all-date and newest-quarter metrics, team/player error decomposition, paired recent differences with date-bootstrap intervals, and summary/per-game CSV exports. Changing history, model or training minimum invalidates the display. No weights are fitted, selected or applied to live rankings; the default remains 65/35. The newest period is a rolling diagnostic, not an untouched final test set. Existing historical starter-selection bias and small-sample limitations remain. No extra API calls are required.

Validation: 143 unit tests and all Streamlit smoke checks passed. Added checks cover pure-signal effects, unchanged team probabilities and default blend, identical evaluation sets, chronological exclusions, invalid weights, empty history, exports, model-change invalidation and no API calls during comparison. Windows execution and predictive improvement on user history were not tested here.

APEX V2.22.0 — Reject ambiguous opening scorers

The ESPN adapter now orders first-period plays by sequence, collapses identical duplicates and rejects conflicting entries at the same sequence. Before accepting the first scoring play it checks consistent scoring flags/point values, a scorer identified in that team's box score, and a supported free-throw or field-goal type. An unreadable first scorer raises an error instead of letting a later basket become the apparent first score.

When opening scoreboard totals are supplied, both must be valid nonnegative integers. Plays before the first score must show 0–0; the first score must show only that team's stated points. Nonzero earlier totals, partial totals and inconsistent first-score totals are rejected. Totals omitted entirely remain supported; this does not prove a feed is complete, and checks stop at the first scoring play. Non-scoring gaps and later score corrections are not certified.

The shared adapter applies these checks to history sync, prior-season imports, explicit repair and forward-journal grading. Import failures remain retryable; invalid journal outcomes stay pending. Already saved history and settled journal outcomes are not automatically changed. Scoring formulas are unchanged.

Validation: 137 unit tests and all Streamlit smoke checks passed, including the recorded ESPN fixture, unreadable first scorers, contradictory scoreboard totals, valid free throws, play ordering, duplicate handling, invalid metadata and pending journal outcomes. Windows execution and a live-provider download were not tested for this release.

APEX V2.21.0 — Diagnose team versus player scoring errors

Full model validation now separates each historical prediction into the probability of the winning team scoring first and the winner's conditional share within that team. The two log losses add to the original ten-player log loss. Stage summaries compare team loss with a 50/50 baseline and within-team loss with an equal-five baseline, on both all evaluated dates and the newest quarter, for all three models.

Team hit rate and conditional player hit rate use fractional tie credit. Conditional player accuracy is evaluated within the actual winning team on every evaluated game, not just games where the model picked the right team; it is a retrospective diagnostic, not independently achievable live accuracy. Raw losses have different baselines and should not be compared as if both tasks had the same difficulty. The new scoring-stage CSV and expanded game-by-game CSV support inspection. Empty history returns empty diagnostics.

The report reuses the same chronological predictions, with no additional API requests, model tuning, probability changes or automated model promotion. Historical observed-starter and nonstarter-exclusion limitations remain. These diagnostics can identify which component needs work, but do not establish a profitable edge.

Validation: 130 unit tests and all Streamlit smoke checks passed. Added tests cover equal baselines, ties, correct-team/wrong-player and wrong-team/right-conditional-player cases, exact log-loss decomposition, identical period counts, invalid probability rejection and dashboard export. Windows execution was not tested here.

APEX V2.20.0 — Warn on thin usable shot history

Dashboard rankings now mark HOLD: SHOT COVERAGE when the existing lineup, injury and total-sample checks pass but a player has fewer than eight observed opening-shot starts. Recent-form and lineup models also require at least eight decayed observed starts, using their 90-day half-life. These are heuristic sample safeguards, not statistically validated accuracy thresholds. The lineup model's coverage safeguard uses overall observed-start decay; it does not imply sufficient similar-lineup evidence, which remains separately displayed.

Rankings/export include weighted observed shot starts and a shot-coverage explanation, including for hypothetical research matchups and rows already held for another reason. Holds use full precision, never rounded display values. Higher-priority lineup, injury and sample holds remain intact. Saved journal rows retain the displayed status; new coverage holds count in the journal's sample-hold total. Existing journal snapshots remain unchanged. Model probabilities and first-score calculations are unchanged in this release. This guard applies to the Streamlit dashboard; the legacy command-line tool retains its older total-start sample checks.

Validation: 125 unit tests and all Streamlit smoke checks passed. Added checks cover sparse shot data despite sufficient total starts, raw-versus-decayed sample boundaries, warning priority, research-mode explanations, unchanged probabilities, and journal hold counts. Windows execution was not tested here.

APEX V2.19.0 — Separate unknown opening shots from observed misses

New history imports record whether the team's first recorded field-goal attempt has an identified shooter in the box score, including bench players. All three models now use only observed opening-shot starts in their shot-rate denominators. First-score rates and total start counts retain all valid games. Lineup-context shot updates apply the same coverage rule with their context weights.

Older files remain readable. A legacy team/game with a starter opening-shot flag is known; an all-zero group without the new flag is ambiguous and excluded only from the shot-rate denominator. This cannot recover whether a bench player or missing shooter caused old zero flags. Explicit observed bench shots in new data count as known misses for all starters. Mixed, invalid or contradictory coverage flags fail data-quality validation. Import/checkpoint writes preserve optional legacy blanks; no bulk migration or automatic history deletion occurs.

Rankings show observed opening-shot starts. Player evidence shows observed/unknown counts and leaves unknown shot outcomes blank instead of false. This fixes treatment of missing inputs; it does not establish better predictive accuracy. Provider play-by-play completeness remains a limitation: identifying the first recorded shooter cannot prove no earlier event was omitted. Re-run full model validation, and compare forward-journal results within software versions.

Validation: 120 unit tests and all Streamlit smoke checks passed. Added checks cover legacy CSV round trips, explicit bench/unknown/starter imports, invalid coverage flags, neutral shot priors with preserved scoring evidence, model denominators, and visible coverage counts. Windows execution and predictive improvement on user history were not tested here.

APEX V2.18.0 — Count lineup evidence once

The experimental lineup model now uses disjoint history for its anchor and context update. Starts with four or five of the selected players enter the lineup update only; other starts supply the player's recent-form anchor. Exact fives retain full decay weight and four-of-five matches half weight. With no other-lineup starts the anchor is neutral; with no similar-lineup starts the model falls back to recent form. Previously, context games also contributed to the anchor, reinforcing the same observations twice.

Rankings now show other-lineup starts and their decayed weight beside the similar-lineup counts. Total starts and existing sample guards retain their meaning. Baseline and recent-form formulas are unchanged. This is a correction to the experimental model's evidence accounting, not a demonstrated accuracy gain. Re-run full model validation on your saved history to compare it. Old journal probabilities remain frozen; filter by software version when comparing prospective results.

Validation: 113 unit tests and all Streamlit smoke checks passed. Tests cover manual disjoint-anchor arithmetic, exact-five and four-of-five weights, recent-form fallback, chronological exclusions, normalized probabilities and displayed evidence counts. Windows execution and predictive improvement on user history were not tested here.

APEX V2.17.0 — Reliability of saved pregame picks

The forward-testing journal now reports top-pick reliability by probability and leader margin for all three models, using the same settled games with three-model forecasts saved before tip-off. It reads frozen probabilities and recorded outcomes without rerunning predictions. Pending games and older single-model snapshots do not enter this comparison. Ties receive fractional hit credit; outside-field winners and incorrect lineups remain in every relevant band and have explicit counts. The version filter applies before comparison. A separate CSV export is available after outcomes are recorded.

This complements historical validation with prospective saved-game evidence. It does not require additional API calls to display the report, place wagers, tune models, or establish improved accuracy. The journal remains a user-selected sample, not an all-slate benchmark; local timestamps are not independently certified. Small bands can be noisy. Unlike the historical starter-only backtest, nonstarter winners remain included here.

Validation: 110 unit tests and all Streamlit smoke checks passed, including pending/settled reliability display and export, frozen probabilities, fractional ties, legacy exclusion and retained outside-field misses. Windows execution was not tested here.

APEX V2.16.0 — Top-pick reliability diagnostics

Full model validation now compares predicted leader probabilities with observed top-1 hit rates for all three models, on both all evaluated dates and the newest quarter. Fixed probability bands and leader-to-runner-up margin bands show game/date counts, fractional tie credit, tied-leader counts, and observed-minus-predicted percentage points. Each game counts once per grouping. Empty bands are omitted; boundaries include the lower end and exclude the upper end. Download pick reliability CSV for inspection; per-game validation exports also include top probability, margin, and number of tied leaders.

These diagnostics use the existing chronological predictions and do not adjust scores or choose a model automatically. Small groups can be noisy. Historical observed-starter and nonstarter-exclusion bias still apply; the report is not a calibration correction, confidence interval, betting threshold or proof of predictive improvement.

Validation: 107 unit tests and all Streamlit smoke checks passed, including the new reliability table/export and existing ranking, journal, repair and stale-report guards. Windows execution was not tested here.

APEX V2.15.0 — Faster chronological prediction batches

Backtests now prepare date-specific team statistics once for all games on that date. Player calculations use the relevant team history instead of repeatedly scanning the entire league. The single-game predictor uses the same batch implementation. No persistent prediction cache is introduced: changing history or the target date rebuilds the inputs. Same-day and future results remain excluded. Model formulas and defaults are unchanged.

Validation: 103 unit tests and all Streamlit smoke checks passed. Exact probabilities matched the previous full-history implementation on a synthetic benchmark with 1,425 historical games, 15 matchups and all three models. Median batch time over three runs was 1.006 seconds before versus 0.105 seconds after (about 9.6x) in the Linux Python test environment. This measures the prediction batch, not end-to-end dashboard or full-season backtest time; Windows and real-history results will vary. This release improves computation speed, not established predictive accuracy.

APEX V2.14.0 — Eastern-date and fresh-schedule guards

Dashboard date queries now retain only games whose timezone-aware start actually falls on the chosen Eastern date. UTC midnight rollover is handled explicitly. Missing timezones, invalid matchups and conflicting duplicate game entries are rejected; identical duplicates are collapsed.

Dashboard and legacy command-line picks share a start guard: scheduled status, a coherent Eastern game date, an aware future start, and no cached/research marker. Postponed, canceled and started games cannot pass as upcoming. Fresh empty responses remain empty instead of falling back to an old slate. Legacy pregame queries now require a fresh schedule.

When historical sync cannot reach the schedule feed, cache fallback is restricted to completed games within that sync window, and each downloaded summary is still checked for completed status and correct identity before saving. This improves input correctness; it does not change scoring formulas or establish predictive improvement.

APEX V2.13.0 — Full chronological model validation

Backtest lab > Run full model validation evaluates baseline, recent form and lineup context on identical games. It reports overall results, the newest quarter of evaluation dates, monthly results, paired recent differences with date-bootstrap intervals, and game-by-game and summary CSV exports. The newest period is fixed at 25% of distinct evaluation dates rounded up; games on the same date remain together.

Every prediction still trains on earlier dates within the 400-day window. Training advances within the newest period, so this is a rolling recent-performance diagnostic, not a frozen or untouched test set. Compare top-one/top-three coverage, log loss and Brier. Negative loss differences beat equal probabilities on that historical sample. Few dates, correlated games, repeated comparisons and historical starter-selection bias limit conclusions. The app does not promote a model or change scoring formulas automatically. Changed history or training minimum invalidates the report. No new network requests or paid API credits are used by validation.

APEX V2.12.0 — Compare models before saving forecasts

Run rankings now computes baseline, recent form and lineup context together for the same matchup, date, history and five starters per team. Open Model comparison to see top estimates, per-player probabilities and ranks, sample counts, injury flags and model statuses. Download a matchup comparison CSV if needed. The selected model still controls the main ranking table. No extra API requests or paid credits are needed to calculate the other two estimates.

Ties use shared ranks. When every player ties, the app explicitly reports that there is no unique top estimate. Probability range measures differences among related heuristics; it is not an uncertainty interval or evidence of accuracy. No consensus score or betting recommendation is generated. Input changes hide all stale comparison results.

Forward journal saves now use the exact model probabilities displayed by the most recent ranking run, after checking fresh game status and the save deadline. The journal does not rerun models at save time. Existing snapshots remain immutable. Model formulas are unchanged.

APEX V2.11.0 — Repair flagged historical games

Open Data quality & coverage when validation flags games. Select up to 20 flagged ESPN games and click Repair selected history games. APEX re-downloads the summaries, verifies completed status, event ID and stored team matchup, uses the provider timestamp in Eastern time, then parses and validates all replacement starter records. Valid games cannot be selected. Ambiguous teams, unavailable data and nonstarter first scorers remain flagged for manual review.

Successful replacements are written together using the existing atomic history writer, after a unique byte-for-byte backup named data/history_before_repair_*.csv. Failed games and unselected games are retained. If history changes while downloads run, repair aborts before writing; stop other imports during repair. Backup failures prevent replacement. Reports list successes, failures and backup name. Rankings, scenarios and backtest caches reset after repair. Forecast journal snapshots remain unchanged.

This repairs stored records only when provider validation succeeds. It does not manufacture missing outcomes, remove hard-to-model games, change model formulas or establish prediction accuracy.

APEX V2.10.0 — Opening-data integrity and neutral unknown possessions

Historical validation now rejects multiple team-opening shooters, conflicting game-opening shooters or first field-goal scorers, a game-opening shooter lacking their team-opening flag, inconsistent within-team possession-proxy flags, and both teams marked as the first opening action. Zero flags remain valid when a nonstarter was involved or the proxy is unknown. Existing rows are never silently deleted; issues appear in Data quality. Invalid games are excluded from backtests and block affected rankings.

The baseline possession-proxy denominator now uses only games with a known opening-action proxy. Missing proxy data no longer counts as a loss. Team first-score rates still use all valid games. Recent-form and lineup-context formulas are unchanged. The proxy remains an opening-action approximation, not a verified jump-ball outcome. Data quality displays proxy coverage separately.

Both current-season sync and prior-season import verify the requested ESPN event ID, completed status, and home/away matchup before accepting rows. Current-season sync also audits extracted rows before checkpointing. Mismatched or invalid downloads leave saved history intact and remain retryable. Stored old forecasts are not recomputed; use the version filter for comparisons. Live Windows and provider availability remain user-environment checks.

APEX V2.9.0 — Player evidence explorer

After Run rankings, open Player evidence and choose a ranked player. Inspect the last 10 and 30 recorded starts and the full 400-day model window: team opening-shot attempts, game first scores, conditional share when the team scores first, similar-lineup counts, and a game-by-game CSV. The view shows the last recorded same-team start and how many other-team starts were excluded.

Only valid, earlier-date same-team history is used. Missing opportunities produce blank rates, not zeros. Opening shots refer to field-goal attempts; first points include free throws. The game log separately identifies the first field-goal scorer. These are raw observed rates, not smoothed predictions or causal explanations. Recorded starts may omit games and retain historical starter-selection bias. Inspecting evidence does not change model formulas, lineups, rankings or journal forecasts.

APEX V2.8.0 — Compare models on future games

Save confirmed forecasts to journal now atomically stores baseline, recent form and lineup context probabilities for the same ten starters before tip-off. It uses the same history, software version and save timestamp. No extra provider requests are needed for comparison estimates. Existing first-save protection applies to the entire bundle. Research matchups remain ineligible.

After games finish, Check completed games for journal resolves the actual first scorer. Forward model comparison grades each model from its saved probabilities, without rerunning a current model or creating hindsight forecasts. All three rows use exactly the same saved games; pending games stay pending. Nonstarter winners, wrong predicted fives and sample/injury holds remain in results. Outside-field winners retain infinite log loss. CSV export includes one row per model per game.

Old single-model records are preserved and excluded from the matched comparison; they are never backfilled. Choose a software version to compare consistent formulas. The model filter includes saved challenger forecasts where available; All models retains the one original selected forecast per game. No betting ROI or automatic model promotion is claimed. Local timestamps are not independently certified.

APEX V2.7.0 — Lineup what-if comparisons

Run rankings, then open Lineup what-if > compare one starter change. Choose a matchup, team, outgoing starter and an alternative from the loaded team roster. Compare starter change shows all players before/after, probability-point changes for retained starters, top estimates, sample counts and injury flags. Export a scenario CSV if needed. It works with baseline, recent form and lineup context.

Scenarios are hypothetical, use no market prices or paid API calls, and do not modify main selections, confirmations, ranking results or the forward journal. A changed input hides the old scenario. Removed/incoming players have blank probabilities outside their respective five, not zero probabilities. Team-first probability stays fixed; this is a model sensitivity calculation, not a causal injury/absence estimate. Roster and injury reports are only as fresh as the last refresh. Predictive improvement remains unproven.

APEX V2.6.0 — Experimental lineup-context scoring

Select Scoring model > Lineup context (experimental), review the five starters, then Run rankings. The default remains baseline. Backtest lab > Compare baseline vs lineup context evaluates the candidate on the same historical games and displays paired uncertainty intervals. No paid API is needed for research rankings using saved history.

The candidate uses recent-form team-first probabilities. Player opening-shot and conditional first-score rates emphasize past same-team starts with at least four of the selected five. Exact fives get weight 1, four-player matches weight 0.5, multiplied by a 90-day recency half-life. A player must have started in the matched game. Shot rates shrink toward recent-form rates with strength 10; conditional scoring rates use strength 5 and team-first opportunities. Their 65/35 mixture is normalized across the selected five. Zero context falls back to recent form. Context counts and weighted counts appear in rankings.

This is a hand-specified heuristic, not a trained or validated improvement. Similar-lineup observations also appear in the recent-form anchor, so the weighting intentionally reuses them; it is not an independent Bayesian posterior or a confidence interval. No causal teammate/injury effect or opening-play knowledge is claimed. Same-day, future and more-than-400-day-old observations are excluded. Starter-selection bias in historical data remains. Forward journal identifies this model separately as lineup.

APEX V2.5.0 — Shared scoring engine and paired validation

Dashboard and backtests now use one prediction function, with a 400-day window and same-day/future exclusion. Rankings show within-team share and sort on full-precision probabilities. Model formulas and default baseline are unchanged; this release does not claim better prediction accuracy.

In Backtest lab, Compare baseline vs recent form now shows top-three coverage (fractional tie credit) and paired differences in log loss, Brier, top-one and top-three accuracy. Approximate 95% intervals use 1,000 bootstrap resamples of whole dates, retaining all games on each sampled date. The same games must appear in both models. Fewer than two dates produces no interval; fewer than 30 dates displays a caution. These intervals do not account for all across-date dependence or repeated model selection. Historical starter-selection bias still applies. Import more history for useful evaluation, and validate changes with the forward journal.

APEX V2.4.1 — Automatic startup updates

Launch with START_APEX.bat. Published updates are checked, verified, backed up and installed before the dashboard opens. The startup download has a 90-second timeout; network failures leave the installed app available. Disable this in App updates if desired. RESTORE_APEX.bat restores the previous programs and pauses automatic updates. Direct streamlit launches do not run the startup updater.

To upgrade from V2.3 or V2.4, use Check for updates, Download update for next launch, then close the command window and reopen START_APEX.bat once. Future published updates install at startup. History and keys are preserved. Includes the V2.4 research workspace and experimental recent-form engine.

# APEX First Basket Dashboard V2.4.0

A local Streamlit dashboard powered by the existing Python first-score model.

## Windows quick start

1. Extract the ZIP into a new folder.
2. Copy the `data` folder from your previous engine into this new app folder to reuse downloaded games. Keep your old copy as a backup. The ZIP contains no historical database.
3. Double-click **START_APEX.bat**. First launch creates a local Python environment and installs the packages. Python 3.11 or newer must already be installed.
4. Leave the command window open. Your browser should open at http://localhost:8501. If it does not, open that address manually.
5. Enter your keys in the sidebar and click **Apply settings**.
6. **Sync history**, then **Load slate & projected starters**.
7. **Refresh injury reports**, review the five selected players per team, and confirm the announced starting five. Use the searchable dropdown to replace a player.
8. **Fetch FanDuel first-basket odds**, then **Run rankings**. Download the table as CSV if wanted.

The dashboard replaces manual starter CSV editing. The original numbered command-line tools remain available, but their starter CSV is separate from the dashboard's session selections.

## Automatic starters

The app preselects each team's last recorded starting five, filtered against its current ESPN roster. A missing roster or lack of history is shown explicitly; you may need to choose players yourself. Injury reports flag selected players but do not silently choose replacements. Confirmations are user-entered, never represented as provider-verified. They reset with a changed lineup, slate reload, date, or new session.

## Data and keys

- ESPN: schedules, current rosters, completed-game play-by-play and starters. Public feeds can change or fail. History sync covers up to 45 recent days of the current season and preserves older saved records.
- BALLDONTLIE All-Star: injury reports via /v1/player_injuries. Pagination is handled. Players match on normalized full name plus team; unmatched names cannot establish availability.
- The Odds API: FanDuel player_first_basket via event-specific odds endpoints, subject to plan and bookmaker coverage. Requests occur only on button clicks, and can consume credits. No prices returned is not treated as a zero price.
- Keys stay in the browser session's server memory by default. The optional Remember keys setting stores them unencrypted in `.apex_keys.json` on your computer. Never share that file or upload a configured app folder. Environment variables ODDS_API_KEY and BALLDONTLIE_API_KEY are also supported.
- The launcher binds the server to 127.0.0.1. This app is intended for one local user, not public hosting.
- Fresh game status is required when ranking. Started games are excluded. Odds cached in the dashboard expire after ten minutes. Lineup or input changes hide previous results until rerun.

## Model limits

This is an uncalibrated heuristic. Model EV and fair odds are mathematical outputs of that heuristic, not evidence of a profitable edge. All results remain research-only. No wagers are placed.

Free throws count as first score. The model combines smoothed team first-score rates, an opening-action possession proxy, player first-shot rates and first-score rates. It does not model verified jump-ball outcomes or opening play design.

HOLD: SAMPLE requires at least ten team games per side and eight starts for the player. HOLD: LINEUP applies until both fives are confirmed. Any selected player's matched injury report causes HOLD: INJURY REVIEW for the entire matchup; review the report manually. An absent injury flag does not prove a player is healthy.

History excludes games in which the first scorer was not one of the ten starters; the resulting selection bias remains a limitation. Chronological backtesting avoids same-day leakage, but uses observed historical starting fives and cannot measure betting ROI without historical odds.

## Validation

20 unit tests cover scoring, odds arithmetic, normalization, game-start guards, injury pagination and matching, duplicate selections, redacted failures, and yes-only first-basket odds. Streamlit AppTest exercises launch, automatic projections, confirmation, ranking output, and reset after a lineup change. ESPN roster access was tested live. Paid integrations were tested with mocked responses; your private API keys are needed for live verification. Windows batch execution was not available in the Linux test environment.

Run tests: `py -m unittest discover -v`. To launch manually after installing dependencies: `py -m streamlit run app.py --server.address 127.0.0.1`.

Sources: https://nba.balldontlie.io/ ; https://the-odds-api.com/sports-odds-data/betting-markets.html ; https://docs.streamlit.io/

## V2.1 — Deeper history and validation

- **Build deeper history** loads prior regular seasons using ESPN team-season schedules. Seasons are labeled by start/end year; API queries use the ending year. Per-event season metadata is checked because the endpoint's top-level season can refer to the current year.
- Import 100, 250, 500, or up to 1,500 missing games at a time. Latest missing games come first. Repeating an import resumes through missing games without duplicate saved games. Failures remain retryable and are listed in the import report. Partial schedule coverage is reported explicitly.
- Existing history is backed up to `data/history_before_prior_season.csv` on the first prior-season import. Every successful game checkpoints with an atomic file replacement. No invalid rows are silently deleted.
- Dashboard rankings and the new Backtest lab use a 400-day window before each game date. A player's history remains specific to that team. Current-season starts are a separate column; adding older games can meet sample thresholds without proving current-season performance.
- Data quality checks validate dates, ten unique starter IDs, five players per side, team/opponent consistency, binary fields, and exactly one first scorer. Team coverage and last observed dates are visible.
- The Backtest lab reports evaluated games, top-1 accuracy with fractional tie credit, log loss, Brier score, calibration bins, and downloadable per-game metrics. Same-day outcomes never enter training. Equal probabilities are the comparison baseline; no historical odds or ROI are claimed. Binned calibration is descriptive, not a fitted correction.
- The original command-line backtest remains available as a legacy tool and uses all prior history; use the dashboard Backtest lab for validation matching the 400-day dashboard model.

### Upgrade from the previous dashboard

Close the APEX command window. Extract the new ZIP, then copy the files inside its `APEX_First_Basket_Engine` folder into the existing folder that contains `START_APEX.bat`. Replace matching program files. The ZIP contains no `data` folder, `.venv`, or `.apex_keys.json`, so these local items are preserved. Relaunch `START_APEX.bat`; the page header should show V2.1.

In the dashboard expand **Build deeper history**, choose the prior season and a 250-game batch, then import. After it finishes, open **Backtest lab** and run evaluation. A better score on a historical sample is not proof of a profitable betting edge.

Validation for this upgrade: 20 unit tests passed; Streamlit smoke tests covered ranking controls and the new backtest output/export. A live 82-game historical team schedule parsed and one live completed prior-season game imported successfully in an isolated test folder. A full league-season download was not executed here.

## V2.2.0 — GitHub updater

The sidebar now checks `kaishawn01/apex-first-basket` on branch `main`. Read GITHUB_SETUP.txt for one-time publication and installation steps. New versions must still be published by the maintainer; this is not automatic code generation or publishing.

Updates resolve main to a commit SHA, fetch the manifest and all files from that exact revision, verify SHA-256 checksums, and stage only allowlisted program files. Data, API keys, odds.csv, and virtual environments cannot be included in an update. A newer three-part VERSION is required. The launcher holds a process lock for the running app, applies pending updates on next launch, backs up replaced program files, and reinstalls dependencies when requirements.txt changes. File watching is disabled to avoid reloading a partially changed program.

RESTORE_APEX.bat restores the previous backed-up program set while retaining personal files. Ordinary write failures trigger rollback; if the process is interrupted during installation, run the restore command before continuing. Repository checksums establish integrity against the published manifest, not independent authenticity or a review of future code; only the trusted repository owner should publish releases.

This package has no personalized data or credentials. Never upload a configured local folder. GitHub web uploads do not honor .gitignore as an upload filter.

## V2.3.0 — Forward-testing journal

After generating rankings and confirming both starting fives, use **Save confirmed forecasts to journal**. The first saved forecast for each game is permanent within the app; rerunning, editing players, or changing prices does not overwrite it. The app checks fresh schedule status and the scheduled start time before saving. Snapshots retain full-precision probabilities, player IDs, odds shown, sample/injury flags, model version, history fingerprint, and local save timestamp. Local clock records are not independently certified.

Open **Forward-testing journal** and click **Check completed games for journal**. Completed games are resolved from ESPN play-by-play, including free throws. Nonstarter winners and winners outside the predicted ten remain misses. Incorrect predicted starting fives are flagged, not voided or excluded. Games that are in progress or have unreadable data stay pending. Final results are recorded once; later provider corrections require manual review.

The journal reports top-1 hit rate with fractional tie credit, Brier score, lineup mismatches and outside-field winners. An outside-field winner has zero predicted probability and therefore infinite log loss, shown explicitly. Results can be filtered by model version and exported as CSV. These are saved-forecast results, not all-slate performance or a wager/ROI log. Small samples remain inconclusive.

Journal data is stored only in `data/forward_journal.sqlite3` and is excluded from update packages. Back up the data folder with APEX closed. API keys are not saved in journal records.

The GitHub certificate fix is retained with certificate verification enabled. The release uses only filenames accepted by the published V2.2.0 updater. No new dependencies are required.

Validation: 35 unit tests passed, including pre-tip saves, confirmation requirements, duplicate protection, free-throw scoring, nonstarter winners, game-ID checks and pending/result handling. Streamlit UI tests cover saving, duplicate prevention and CSV export. Published-updater compatibility is tested with simulated downloads of the actual release bytes; live Windows installation remains to be verified.

## V2.4.0 — Core model research and after-hours analysis

**Why no rankings?** Pregame mode requires scheduled games whose start time has not passed. Once the slate has started, the eligible set can be empty. Odds API absence or failure is not supposed to prevent ranking; it leaves book prices and EV blank. The dashboard now shows scheduled, live/other, completed and eligible game counts. A screenshot of an actual error may still be needed to diagnose a particular failed run.

**Research matchup** in the sidebar lets you select any two teams and edit hypothetical fives at any time. Choose teams, load projected starters, then run rankings. It uses the chosen date as a training cutoff and the current roster where available. This is not a historical roster replay or a live game. It makes no schedule/odds request, though loading current rosters still uses ESPN (with a historical-starters fallback). Research outputs cannot be saved as pregame forward forecasts.

**Recent form (experimental)** is an optional scoring model; the baseline remains the default. It uses:
- A 400-day training window and 90-day exponential half-life. Same-day and future records are excluded.
- Team first-score frequency smoothed toward 50% with 20 prior games. The two teams' smoothed odds are combined symmetrically, capped at 25–75%.
- Player first-team-shot involvement smoothed toward 20% with ten prior starts.
- Player share of first scores *conditional on their team scoring first while they started*, smoothed toward 20% with five such opportunities.
- A fixed 65% first-shot / 35% conditional-score blend, normalized across the selected five, multiplied by team-first probability.

These are hand-chosen research settings, not fitted parameters. The model does not yet have verified tip winners, opening play calls, shot-location matchup effects, or first-shot conversion rates. It uses the existing history schema and inherits its nonstarter-scorer exclusion bias. Older data can become less representative after trades and role changes; weighted sample holds indicate limited recent evidence. Weighted starts mean the sum of recency weights, not a formal independent effective sample size.

The ranking table shows the selected model alongside baseline probability, team-first probability and weighted starts. The Backtest lab can compare both models on identical chronological holdouts. No model is automatically promoted based on these results. The journal records model identity; older journal records are treated as baseline.

Validation: 41 unit tests passed, including recency behavior, same-day/future exclusion, conditional opportunities, probability normalization, matching comparison holdouts, research-mode odds suppression and journal rejection. Streamlit tests cover research mode without a schedule request and both-model backtest comparison. No empirical accuracy improvement is claimed; run comparisons on your expanded history and continue forward testing.
