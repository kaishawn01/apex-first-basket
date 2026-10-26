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
