# APEX First Basket Dashboard V2.2.0

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
