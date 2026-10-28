# V3 Phase 2 review — VERSION 3.0.1, development only

## Decision: retain V2.44 Baseline

The Phase 2 hybrid does **not** demonstrate a meaningful, repeatable improvement. Its first-basket hit rate and first-shot selection are worse on the declared final test. The small log-loss improvement is statistically inconclusive, Brier is slightly worse, and Uniform beats both models on proper scores. Keep Baseline as the existing default. No merge, deployment, automatic promotion, or betting-edge claim is authorized by this report.

## Changes and preserved behavior

`opening_data.py` validates completed ESPN summaries against saved game/player identities and stores empirical opening sequences separately. It extracts explicit jump-ball winners, first-team shot categories, 2PT/3PT results, free-throw trips, turnovers, and rebounds. Collection stops after the first three minutes or before the first substitution/nonstarter action. Rebounds are assigned to the preceding shooting team, so defensive rebounds count as that team's failed possession retention. Unknown shot types and ambiguous tips remain unknown. Atomic checkpoints, bounded requests, retry ordering, concurrent-file guards and readable failures preserve existing history.

`phase2.py` separates first field-goal selection, first scoring opportunity (FG or FT), and first-score probability. Inputs combine existing lineup/recent-role predictors with decayed observed opening categories, later-shot and second-chance selection, explicit tip evidence, type-specific conversion, team event tendencies, and opponent-team defensive aggregates. Sparse inputs shrink toward stated priors. Reproducible simulations include turnovers, two/three-point shots, one/two/three-shot foul trips, offensive/defensive rebounds and second chances. Trial count and seed are configurable; unresolved trials retain explicit baseline fallback mass.

The mobile research panel shows five vertical candidate cards, Baseline/MC/Hybrid probabilities, conditional first-shot estimates, first-opportunity estimates, sample evidence, MC sampling error and lineup diagnostics. First-shot probabilities are conditional on a field-goal attempt occurring before first score; the no-FG fraction is separate. The new panel never provides actionable recommendations. It refreshes rosters, checks injury freshness, expires results and clears failed-refresh output. Live ranking Model EV is now hidden for every HOLD status, including lineup, injury and sample holds. Existing models, API settings, odds display, imports, journal and Phase 1 panels remain available.

Starter checks retain exact identities, unique current-team roster membership, provider/manual source distinctions, selected-five binding, schedule/time checks and expiry. Provider failures cannot establish confirmation. Historical provider verification requires an archived pre-tip snapshot, actual game start metadata, matching selected five and valid source evidence; retrospective boxscore starters alone remain unverified.

## Locked chronological experiment and actual results

The experiment boundaries and candidate grid were recorded in `validation/PHASE2_LOCK.json` before the December final-test data was fetched. Development: 296 accepted games from October 21–November 30, 2025, with 296 matching opening sidecars and 5,835 early-sequence events. After 100 prior games, 193 validation games across 26 dates selected the blend and calibration. Validation selected **50% Baseline / 50% MC, temperature 1.25** from weights 0/.15/.35/.5 and temperatures .8/1/1.25. Temperature fitting requires at least 100 validation games and 20 dates; smaller samples retain stricter defaults.

Selection was persisted before fetching the final test: **December 1–21, 2025, 120 accepted games across 21 dates**, from 124 scheduled completed games. Four summaries failed missing-ID validation and are listed in the results artifact. There are 416 accepted history/sequence games overall. All features use strictly earlier dates within 400 days, excluding same-day outcomes. Earlier test games may train later test dates under the declared rolling evaluation; blend and temperature never refit on test results. Training fingerprints and latest dates are exported. Test outcomes are now known: any further tuning needs another untouched sample.

| Final-test model | Top-1 % | Top-3 % | Log loss | Brier | Calibration ECE, pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| V2.44 Baseline | 15.00 | 37.08 | 2.32969 | 0.902729 | 1.82 |
| Pure Monte Carlo | 8.33 | 34.58 | 2.35766 | 0.911237 | 1.96 |
| Selected calibrated hybrid | 12.50 | 35.83 | 2.32021 | 0.902799 | 1.50 |
| Smoothed scorer frequency | 10.56 | 30.36 | 2.47305 | 0.929885 | 5.38 |
| Uniform | 10.00 | 30.00 | 2.30259 | 0.900000 | 0.00 |

Top-k ties receive fractional credit. Lower log loss, Brier and ECE are better. Uniform's zero aggregate binned ECE is mechanical (one winner among ten equal probabilities), not evidence of discrimination. Calibration bins are descriptive and uncertain in this small sample.

Paired approximate date-bootstrap 95% intervals, hybrid minus Baseline: log loss **-0.00949 [-0.03472, +0.01411]**; Brier **+0.000070 [-0.004699, +0.004815]**; Top-1 **-2.50 percentage points [-6.19, 0.00]**; Top-3 **-1.25 pp [-6.10, +3.70]**. Dates may remain dependent; these are not proof of superiority or an economic edge.

First-shot diagnostic: 115 games with an eligible observed FG before first score. Phase 2 Top-1 **15.65%**, simpler recent-shot/opening proxy **20.00%**, Uniform **10.00%**. The more complex selector did not improve this metric.

**Verified historical cohort: 0 games. Unverified pre-tip evidence cohort: 120 games.** These forecasts condition on retrospective observed starters, not proven pre-tip availability. This does not mean those players were incorrect starters. The sample contains no observed substitution before first score, which is not evidence that substitution modeling is unnecessary in general.

## Tests and review

Local validation: **349 unit/regression tests passed**, including all existing tests. Full Streamlit smoke suite passed, including previous features, new mobile candidate cards, first-shot distinction, HOLD warnings, roster-failure clearing, chronological comparison, small-sample fitting guards, cohort reporting, exports and changed-input invalidation.

Tests cover probability conservation, seeded reproducibility, explicit tips/types, empirical second chances, free throws and capped trials, invalid identities and sidecars, atomic enrichment/retries/concurrent writes, provider failure and injury freshness, pre-tip archive timing/reschedules, same-day exclusion, final-test label independence of selection, and lock callbacks before test prediction. GitHub's Python 3.11/3.14 workflow runs these tests, UI checks and manifest checks for the published commit; consult the PR checks for their actual status.

## Reproduce and limitations before deployment

Run `python -m unittest discover -v` and `python ui_smoke.py`. Public-data experiment: first `python validation/run_public_sample.py`, then `python validation/run_phase2.py`. It uses public ESPN data, no paid keys, and writes raw/history caches only beneath ignored `data/v3_validation/`. The locked selection file prevents silent retuning. Public feeds can change; recorded fingerprints make differences visible. The user's private laptop history is not available here.

For local research, use a separate branch checkout. Enrich next 20 opening sequences in the dashboard, then run the Phase 2 research panel or chronological test controls in Backtest lab. Fetches happen only on requested actions. The ordinary research-panel blend follows sidebar settings; the historical selected/calibrated blend is reported separately and never silently promoted to live rankings.

Remaining limitations: inherited exclusion of nonstarter first scorers; no independent pre-tip lineup/injury archive; inferred current jumper from past appearances; shot categories rather than verified designed plays; team-level defense rather than individual matchups; fixed ten starters because pregame bench/substitution evidence is missing; simplified technical/and-one/violation handling; fixed shrinkage and missing-data assumptions; MC standard errors measure simulation noise, not total model uncertainty. Short public sample, no historical market prices/ROI, and no demonstrated superiority over Uniform. Live provider confirmation on Windows and deployment/rollback still need operational validation.

Before promotion, collect prospective pre-tip snapshots and richer opening data, evaluate a newly locked independent period/season against Uniform and a calibrated Baseline, and require repeatable gains with uncertainty estimates. The V2.44 updater needs a reviewed allowlist bridge for `simulation.py`, `test_simulation.py`, `V3_REVIEW.md`, `opening_data.py`, `phase2.py`, and `test_phase2.py`. Do not weaken integrity checks or publish this manifest directly to old clients. No bridge or Streamlit deployment is included.

---

# Phase 1 review (historical record; Phase 2 above supersedes current version/results)

# V3 development review — not deployed

Base: published APEX V2.44.0, commit `babec35666c3da1ccdbe2202c68fde2695a14e67`.
Development branch: `v3/hybrid-monte-carlo`. The unfinished local V2.45 experiment is not included.

## Behavior and scope

The new opt-in simulation panel combines the existing Baseline forecast with empirical Monte Carlo first-score frequencies. The fixed default blend is 65% Baseline / 35% simulation. Both teams need ten earlier saved games for the simulation component to activate; otherwise the hybrid returns Baseline. This is a review minimum, not validated sample sufficiency. Existing rankings, model selectors, odds, starter editing, history enrichment, research tools and the forward journal retain their prior behavior. Simulations are exported separately and are not silently inserted into the existing three-model journal.

The simulator draws an opening team, then repeats turnover, field-goal or two-shot-foul events. A made field goal or the first made free throw terminates the trial. A miss can retain possession through an offensive rebound or transfer it through a defensive rebound. The ten selected starters remain on court. This is a first-points model, conditional on those starters, not a first-field-goal or full basketball game simulator.

Historical inputs use only earlier dates in the preceding 400 days. Opening-action shares use the recorded first-action proxy, with 90-day decay and a symmetric strength-20 prior; this is not verified jump-ball data. Player shot shares and make rates reuse existing smoothed opening-shot evidence. Later attempts reuse opening-shot selection shares. Foul shooters use conditional first-score shares as a proxy, not observed foul-drawing rates.

Per-event turnover (0.13), two-shot foul (0.10), offensive rebound after a miss (0.24), and free-throw make (0.77) probabilities are exposed scenario assumptions. These values have not been estimated from the user's data or asserted to be league averages. Three-shot fouls, technicals, and-ones, violations, substitutions, clock effects, rebounder identity, opponent-specific defensive matchups and play design are absent.

Each game uses a reproducible seed derived from the user seed, date, teams and sorted selected player IDs. Reordering history or lineup display cannot alter a forecast. Trials capped after 60 events remain explicitly unresolved; their probability mass goes to Baseline rather than being discarded or assigned a fabricated scorer. Monte Carlo standard errors describe sampling noise only, not uncertainty about the model or assumptions.

## Lineup review and fixes

- Refresh ESPN rosters when requesting NBA confirmation; failed roster refreshes cannot produce provider confirmation for that team.
- Allow individually updated timestamps for the five confirmed players; identical timestamps are not a reliable requirement.
- Check timezone-aware timestamps against the Eastern game date and reject timestamps more than five minutes in the future. The live NBA feed omits timezone offsets: such timestamps retain calendar-date-only validation and are explicitly labeled unspecified, not assumed UTC.
- Normalize accents conservatively while requiring a unique full-name match on that team's roster. No fuzzy matches, suffix stripping or mixing NBA IDs with ESPN IDs.
- Reject duplicate NBA identities across teams, malformed players, duplicate mapped IDs, missing evidence and duplicate manual selections. A malformed lineup on one team does not discard an independently valid other team unless the game identity itself is conflicting.
- Retain exact selected-five, date, matchup, start time, pregame status and five-minute retrieval-expiry checks. Expiry, edits, failed refreshes and reschedules invalidate confirmation. Expected players and generic confirmed roster members without starting positions are never promoted to confirmed starters.
- Scheduled-game simulations require both lineups confirmed, a fresh schedule and a second confirmation check at execution. Research matchups remain hypothetical. Manual confirmation is labeled separately from NBA confirmation.

A live request to the NBA daily feed for 2026-10-28 returned 12 games. Positioned entries were Expected; the parser accepted zero confirmations from that payload. Confirmed-lineup mapping, mixed timestamps, accents, expiry and failure paths are tested with fixtures. This live probe does not prove future provider availability or validate every provider schema.

## Backtest review

Both forecasts use identical evaluation games and target starting fives. Whole dates are withheld until all games on the date are evaluated; no same-day outcome can train another same-day forecast. All settings remain fixed during a run. Training fingerprints, latest training date, effective blend and unresolved counts are exported per game. Baseline metrics are regression-tested against the preexisting evaluator.

Reports include top-1/top-3 fractional hit credit, log loss, Brier, paired approximate date-bootstrap differences, newest-quarter diagnostics and active-hybrid-only results. Non-finite pure-Monte-Carlo losses remain in the sample; undefined log-loss intervals are withheld, not repaired with a result-dependent floor. No automated parameter tuning, model promotion or profitability claim is made.

Observed historical starting fives are used; historical lineup-announcement timing and pregame injuries are unavailable. The inherited database excludes nonstarter first scorers, creating selection bias. The newest quarter is not an untouched holdout, and repeated experiments can overfit it. Adjacent dates can also be dependent. A user's local historical database is not accessible from this workspace; public-sample validation must be distinguished from testing that user's saved history.

## Deployment gate

This branch is a development preview with numeric VERSION 3.0.0 for compatibility with existing version parsing. Do not merge or deploy automatically based on its version number. Main and the installed Streamlit app are unchanged.

The V2.44 updater intentionally rejects new filenames. A reviewed bridge release adding `simulation.py`, `test_simulation.py` and `V3_REVIEW.md` to the allowlist must reach installed V2 clients before publishing a V3 manifest that includes them. Alternatively, test a fresh checkout of this branch in a separate folder. Do not weaken the allowlist or checksum checks. This upgrade-path issue blocks a one-step automatic deployment from V2.44; no bridge release is published by this PR.

Before production: review the validation results below, validate with the user's own exported history, verify a real pregame confirmed slate on Windows, and decide whether the simulator should remain opt-in. Keep Baseline as the default pending independent forward validation. No Streamlit hosting deployment is configured or changed.

## Local preview

Use a separate checkout/folder to protect the installed app and its database. Install `requirements.txt`, then run `python -m streamlit run app.py --server.address 127.0.0.1`. The existing localhost-only behavior is preserved. Do not upload API-key files, data, virtual environments or a configured local folder.

In the app, load and confirm a slate, run existing rankings, then expand **V3 hybrid Monte Carlo · possession simulation**. Configure the explicitly labeled assumptions in the sidebar. In Backtest lab, use **Backtest V3 hybrid vs baseline**.

Offline command: `python simulation.py --history data/history_espn.csv --output data/v3_report.json --trials 2000 --min-training 100`. This command never fetches APIs. Optional reproducible public sample: `python validation/run_public_sample.py`; it makes public ESPN requests and caches only under `data/v3_validation`.

## Validation results

- 314 unit tests passed locally, including the 288 existing tests and 26 V3 regression/statistical checks.
- The complete Streamlit AppTest smoke suite passed, including existing journal/lineup/history/model tools and new simulation, confirmation, export and stale-settings checks.
- Live NBA feed/schema probe succeeded; no Expected lineup was falsely confirmed. Confirmed live pregame mapping still requires a real confirmed slate check.
- Public ESPN validation fetched 299 completed games from 2025-10-21 through 2025-11-30; 296 passed extraction/audit. Three provider summaries lacked an expected ID field and were excluded with IDs/reasons in `validation/V3_BACKTEST_SUMMARY.json`.
- A fixed 2,000-trial, seed-3000, 35%-simulation configuration evaluated 193 games across 26 dates after the 100-game training warmup. 141 games activated the simulation blend; remaining games used the documented minimum-history fallback. No trials hit the event cap. Settings were not tuned after viewing this sample.

| Metric (193 identical games) | Existing Baseline | Hybrid MC |
| --- | ---: | ---: |
| Top-1 hit rate | 11.40% | 10.88% |
| Top-3 fractional hit rate | 30.31% | 29.53% |
| Log loss (lower is better) | 2.39022 | 2.37747 |
| Brier (lower is better) | 0.91731 | 0.91542 |

The approximate date-bootstrap log-loss difference was -0.01275 with interval [-0.02120, -0.00495]. Top-1 difference was -0.52 percentage points with interval [-1.69, 0.00]. These exploratory intervals are unadjusted for multiple comparisons and do not remove temporal dependence or data-selection bias. Newest-quarter top-1 accuracy was also lower: 9.09% hybrid versus 10.91% Baseline over 55 games. Equal 10% probabilities have log loss 2.30259 and Brier 0.9, better than either model here. Thus the probability-error change relative to Baseline is not evidence of an edge or justification to promote the hybrid.

Review disposition: suitable for opt-in development testing, **not approved for production promotion**. Keep the existing default. Required before rollout: the updater bridge, user-history evaluation, Windows launcher check and live confirmed-slate check. GitHub Actions is configured for regression tests; its result must be checked on the PR rather than inferred from local tests.
