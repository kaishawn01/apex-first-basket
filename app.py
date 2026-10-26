"""APEX desktop dashboard. Run with START_APEX.bat."""
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import first_basket_engine as eng
import dashboard_core as core
import research_tools as research
import updater

st.set_page_config(page_title='APEX • First Basket',page_icon='🏀',layout='wide')
st.markdown('''<style>.stApp {background:#0d1420} [data-testid="stMetric"] {background:#172335;border:1px solid #2a3d53;border-radius:12px;padding:16px} .block-container {max-width:1350px} h1 {letter-spacing:-1px}</style>''',unsafe_allow_html=True)
st.caption('APEX / NBA RESEARCH DESK · V' + updater.current_version())
st.title('First basket. One workspace.')
st.write('Sync history, review projected starters, and compare first-score estimates with market prices.')
st.info('Experimental model • Free throws count • Projected lineups require confirmation • No validated betting edge')
settings_path=eng.ROOT/'.apex_keys.json'
if 'keys' not in st.session_state:
    try:
        st.session_state['keys']=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    except (OSError,ValueError):
        st.session_state['keys']={}
    st.session_state['keys'].setdefault('odds',os.environ.get('ODDS_API_KEY',''))
    st.session_state['keys'].setdefault('bdl',os.environ.get('BALLDONTLIE_API_KEY',''))
with st.sidebar:
    st.header('Settings')
    with st.form('keys_form'):
        odds_key=st.text_input('The Odds API key',value=st.session_state['keys'].get('odds',''),type='password')
        bdl_key=st.text_input('BALLDONTLIE All-Star key',value=st.session_state['keys'].get('bdl',''),type='password')
        remember=st.checkbox('Remember keys on this computer',value=settings_path.exists())
        st.caption('Optional local saving uses an unencrypted file. Keep the app folder private. Otherwise keys last only for this session.')
        if st.form_submit_button('Apply settings'):
            st.session_state['keys']={'odds':odds_key.strip(),'bdl':bdl_key.strip()}
            if remember:
                settings_path.write_text(json.dumps(st.session_state['keys']))
                try: settings_path.chmod(0o600)
                except OSError: pass
            elif settings_path.exists(): settings_path.unlink()
            st.success('Settings applied.')
    with st.expander('App updates'):
        auto_disabled=eng.ROOT/'.apex_auto_update_disabled'
        auto_enabled=st.checkbox('Install published updates when APEX starts',value=not auto_disabled.exists())
        if auto_enabled:
            auto_disabled.unlink(missing_ok=True)
        else:
            auto_disabled.touch()
        st.caption('Startup checks allow up to 90 seconds for downloading. If GitHub is unavailable, the installed app opens. Launch with START_APEX.bat.')
        st.caption('Updates come from kaishawn01/apex-first-basket on GitHub. New versions must be published there first.')
        if (eng.ROOT/'.apex_pending').exists():
            st.success('Update prepared. Close the APEX command window and reopen START_APEX.bat to install it.')
        elif st.button('Check for updates'):
            st.session_state.pop('release',None)
            try:
                with st.spinner('Checking GitHub…'):
                    st.session_state['release']=updater.check()
            except (RuntimeError,ValueError,KeyError,OSError) as exc:
                st.error(str(exc))
        release=st.session_state.get('release')
        if release and not (eng.ROOT/'.apex_pending').exists():
            if release['available']:
                st.write('Available: '+release['manifest']['version'])
                if st.button('Download update for next launch'):
                    try:
                        with st.spinner('Downloading and checking program files…'):
                            updater.stage(release)
                        st.success('Ready. Close the APEX command window, then reopen START_APEX.bat. Your history and keys stay in place.')
                    except (RuntimeError,ValueError,KeyError,OSError) as exc:
                        st.error(str(exc))
            else:st.success('You have the latest published version.')
    st.caption('API calls happen when you press a refresh button. Fetching odds can consume your API credits.')
    day=st.date_input('Game date • Eastern time',datetime.now(ZoneInfo('America/New_York')).date(),key='slate_date').isoformat()
    st.caption('Confirmations are specific to this session, date, game, and selected five. Changing players clears confirmation.')
    selected_model=st.selectbox('Scoring model',['baseline','recent','lineup'],format_func=lambda m:{'baseline':'Baseline (current default)','recent':'Recent form (experimental)','lineup':'Lineup context (experimental)'}[m],key='scoring_model')
    analysis_mode=st.radio('Workspace',['Upcoming slate','Research matchup'],key='workspace_mode')
    research_away=research_home=None
    if analysis_mode=='Research matchup':
        research_away=st.selectbox('Research team A',sorted(eng.TEAMS),key='research_a')
        research_home=st.selectbox('Research team B',[t for t in sorted(eng.TEAMS) if t!=research_away],key='research_b')
        st.caption('Compare hypothetical starting fives at any time. No odds or forward-journal saves. Current rosters are used; this is not a historical replay.')
    if selected_model=='lineup':st.caption('Lineup context emphasizes past starts with four or five of the selected teammates. Similar-lineup games are counted once, with other-lineup starts supplying the recent-form anchor. With no similar starts it falls back to recent form. It does not infer injury replacements or opening plays.')
    st.caption('Recent form uses a 90-day half-life, smoothed first-shot involvement, and scoring share conditional on the team scoring first. These settings have not been fitted or validated as better.')


hist=eng.read_csv(eng.HISTORY)
a,b,c=st.columns(3)
a.metric('Historical games',len({r['game_id'] for r in hist}))
b.metric('Teams in history',len({r['team'] for r in hist}))
c.metric('Model status','Research only')

def job(command):
    output=st.empty(); lines=[]
    with st.spinner('Working… keep this window open.'):
        proc=subprocess.Popen([sys.executable,'-u',str(eng.ROOT/'first_basket_engine.py'),*command],cwd=str(eng.ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        for line in proc.stdout:
            lines.append(line.rstrip()); output.code('\n'.join(lines[-18:]),language='text')
        code=proc.wait()
    if code: st.error('Task failed. Review the log above and retry.')
    else: st.success('Task completed.')
    return code

sync_col,slate_col,inj_col=st.columns(3)
if sync_col.button('1 · Sync history',use_container_width=True):
    if job(['sync'])==0:
        st.session_state.pop('results',None)
        st.rerun()
if slate_col.button('2 · Load slate & projected starters',type='primary',use_container_width=True):
    try:
        with st.spinner('Loading today’s games and team rosters…'):
            if analysis_mode=='Research matchup':
                games=[{'gameId':f'research_{research_away}_{research_home}_{day}','_date':day,'gameStatus':0,'research_only':True,'start_time':day+'T23:00:00Z','awayTeam':{'teamTricode':research_away},'homeTeam':{'teamTricode':research_home}}]
            else:
                games=core.fresh_schedule(day)
            roster_map={}; errors=[]
            for team in sorted({g[s]['teamTricode'] for g in games for s in ('awayTeam','homeTeam')}):
                try: roster_map[team]=core.roster(team)
                except (RuntimeError,KeyError,ValueError) as exc:
                    errors.append(f'{team}: roster unavailable; only historical starters are available.')
                    roster_map[team]=[{'player_id':r['player_id'],'player':r['player']} for r in eng.recent_starters([r for r in hist if r['date']<day],team)]
            st.session_state['slate']={'day':day,'games':games,'rosters':roster_map,'loaded':datetime.now().isoformat(timespec='seconds'),'errors':errors,'mode':analysis_mode,'research_teams':[research_away,research_home]}
            st.session_state['revision']=st.session_state.get('revision',0)+1
            st.session_state.pop('results',None)
            st.session_state.pop('prices',None)
    except (RuntimeError,KeyError,ValueError):
        st.error('Could not load the slate. No cached schedule is used for new rankings. Please retry.')
if inj_col.button('Refresh injury reports',use_container_width=True):
    st.session_state.pop('injuries',None)
    st.session_state.pop('results',None)
    try:
        with st.spinner('Checking BALLDONTLIE…'):
            reports=core.injury_reports(st.session_state['keys'].get('bdl',''))
        st.session_state['injuries']={'reports':reports,'time':datetime.now().isoformat(timespec='seconds')}
        st.success('Injury reports refreshed.')
    except (RuntimeError,ValueError,KeyError) as exc:
        st.error(str(exc) if isinstance(exc,(RuntimeError,ValueError)) else 'Unexpected injury response.')

inj=st.session_state.get('injuries',{})
reports=inj.get('reports',[])
if inj:
    st.caption('Injury reports fetched: '+inj['time']+' • Name + team matching; absence from this list does not confirm availability.')
    with st.expander('View injury report'):
        st.dataframe(pd.DataFrame(reports),hide_index=True,use_container_width=True)
else:
    st.warning('Injuries have not been checked. Refresh reports or review availability yourself.')

slate=st.session_state.get('slate')
if not slate or slate['day']!=day or slate.get('mode','Upcoming slate')!=analysis_mode or (analysis_mode=='Research matchup' and slate.get('research_teams')!=[research_away,research_home]):
    st.markdown('### Get started')
    st.write('Sync your history, then load the slate. Projected lineups will appear below automatically.')
else:
    for warning in slate['errors']: st.warning(warning)
    games=[g for g in slate['games'] if g.get('research_only') or core.upcoming(g)]
    st.caption('Loaded: '+slate['loaded'])
    if analysis_mode=='Upcoming slate':
        counts={status:sum(g['gameStatus']==status for g in slate['games']) for status in (1,2,3)}
        st.caption(f"Schedule: {counts[1]} scheduled · {counts[2]} live/other · {counts[3]} completed · {len(games)} eligible for pregame rankings")
        if not games: st.info('No unstarted regular-season games are available for this date. Choose a future date or use Research matchup to work on the scoring model now. Odds API access does not control this filter.')
    else:
        st.warning('RESEARCH MATCHUP — hypothetical lineups, not a live game or a pregame forecast.')
    choices={}; confirmations={}
    for g in games:
        gid=g['gameId']; away,home=(g[s]['teamTricode'] for s in ('awayTeam','homeTeam'))
        start=datetime.fromisoformat(g['start_time'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
        with st.expander(f'{away} vs {home} · RESEARCH' if g.get('research_only') else f'{away} @ {home} · {start:%I:%M %p} ET',expanded=True):
            choices[gid]={}; confirmations[gid]={}
            for col,team in zip(st.columns(2),(away,home)):
                with col:
                    players=slate['rosters'][team]; byid={p['player_id']:p for p in players}
                    defaults=core.projections(hist,team,day,players)
                    selected=st.multiselect(f'{team} · select five starters',list(byid),default=defaults,
                        format_func=lambda pid,byid=byid:byid[pid]['player'],max_selections=5,
                        key=f'five:{day}:{gid}:{team}:{st.session_state.get("revision",0)}')
                    choices[gid][team]=[byid[pid] for pid in selected]
                    st.caption('Projection: last recorded starting five, limited to the current roster. Injured players are flagged, not silently replaced.')
                    for pid in selected:
                        report=core.injury_for(reports,team,byid[pid]['player'])
                        if report: st.warning(f"{report['player']}: {report['status']} — {report['description']}")
                    if g.get('research_only'):
                        confirmations[gid][team]=False
                        st.caption('HYPOTHETICAL STARTING FIVE')
                    else:
                        confirmed=st.checkbox(f'I verified {team}’s announced starters for this game',key=f'confirm:{day}:{gid}:{team}:{st.session_state.get("revision",0)}:{",".join(sorted(selected))}',disabled=len(selected)!=5)
                        confirmations[gid][team]=confirmed and len(selected)==5
                        st.caption('USER CONFIRMED' if confirmations[gid][team] else 'PROJECTED / UNCONFIRMED')
    st.markdown('### Market & rankings')
    st.caption('Refresh odds shortly before running rankings. Prices expire after 10 minutes in this dashboard.')
    if st.button('Fetch FanDuel first-basket odds',disabled=not games or analysis_mode=='Research matchup'):
        st.session_state.pop('prices',None); st.session_state.pop('results',None)
        try:
            with st.spinner('Fetching prices…'):
                prices,messages=core.live_prices(st.session_state['keys'].get('odds',''),games)
            st.session_state['prices']={'day':day,'values':prices,'fetched':datetime.now().timestamp()}
            for message in messages: st.warning(message)
            st.success(f'Loaded {len(prices)} player prices.')
        except (RuntimeError,ValueError,KeyError) as exc:
            st.error(str(exc) if isinstance(exc,(RuntimeError,ValueError)) else 'Unexpected odds response.')
    prices_state=st.session_state.get('prices',{})
    prices=prices_state.get('values',{}) if prices_state.get('day')==day and datetime.now().timestamp()-prices_state.get('fetched',0)<600 else {}
    if analysis_mode=='Research matchup':prices={}
    st.caption(f'{len(prices)} current player prices available. Rankings can run without prices; EV stays blank.')
    signature=json.dumps({'day':day,'choices':choices,'confirmed':confirmations,'odds_time':prices_state.get('fetched') if prices else None,'injury_time':inj.get('time'),'history':research.fingerprint(hist),'model':selected_model,'workspace':analysis_mode},sort_keys=True)
    if st.button('3 · Run rankings',type='primary',disabled=not games):
        st.session_state.pop('results',None)
        try:
            fresh={g['gameId']:g for g in games} if analysis_mode=='Research matchup' else {g['gameId']:g for g in core.fresh_schedule(day)}
            rows=[];model_bundles={}
            for g in games:
                current=fresh.get(g['gameId'])
                if not current or (not current.get('research_only') and not core.upcoming(current)):
                    st.warning(f"{g['gameId']}: started or no longer scheduled; skipped."); continue
                bundle={m:core.rank_game(hist,current,choices[g['gameId']],confirmations[g['gameId']],prices if m==selected_model else {},reports,model=m) for m in ('baseline','recent','lineup')}
                model_bundles[g['gameId']]=bundle
                rows.extend(bundle[selected_model])
            st.session_state['results']={'rows':rows,'model_bundles':model_bundles,'signature':signature,'time':datetime.now().isoformat(timespec='seconds')}
        except (RuntimeError,ValueError,KeyError) as exc:
            st.error(str(exc) if isinstance(exc,(RuntimeError,ValueError)) else 'Unexpected data response. Reload slate.')
    result=st.session_state.get('results')
    if result and result['signature']==signature:
        st.caption('Rankings generated: '+result['time']+' • Model EV uses uncalibrated estimates, not proven value.')
        frame=pd.DataFrame([{k:v for k,v in r.items() if not k.startswith('_')} for r in result['rows']])
        st.dataframe(frame,hide_index=True,use_container_width=True)
        if selected_model=='lineup':st.caption('Similar-lineup starts include past games with at least four selected starters. Exact fives receive full weight; four-player matches receive half, with a 90-day recency half-life. Zero context uses recent-form rates. These are historical counts, not confidence guarantees.')
        st.caption('First-score probability combines team-first probability and within-team share. These are model estimates, not verified opening plays. A top-three hit is a coverage measure, not betting profit.')
        st.download_button('Download rankings CSV',frame.to_csv(index=False).encode('utf-8'),f'apex_rankings_{day}.csv','text/csv')
        with st.expander('Model comparison · same matchup, three estimates'):
            bundles=result.get('model_bundles',{})
            if bundles:
                compare_gid=st.selectbox('Compare models for matchup',list(bundles),format_func=lambda gid:bundles[gid]['baseline'][0]['Matchup'])
                compared=core.compare_model_forecasts(bundles[compare_gid])
                st.dataframe(pd.DataFrame(compared['leaders']),hide_index=True,use_container_width=True)
                if compared['all_tied']:st.info('All three models tie all ten players. There is no unique top estimate; inspect the available history.')
                elif compared['shared_top']:st.write('Shared top-ranked players (ties included): '+', '.join(compared['shared_top']))
                else:st.info('The models have no shared top-ranked player for this matchup.')
                comparison_frame=pd.DataFrame(compared['rows'])
                st.dataframe(comparison_frame,hide_index=True,use_container_width=True)
                st.caption('Range measures disagreement between these three related heuristics; it is not a confidence interval. Agreement does not establish accuracy. Review starts, injury reports and each model’s status before interpreting the estimates. Rank 1 can include ties.')
                st.download_button('Download matchup model comparison CSV',comparison_frame.to_csv(index=False).encode(),'apex_matchup_models.csv','text/csv')
        with st.expander('Player evidence · inspect the history behind a ranking'):
            evidence_rows={(r['_game_id'],r['_player_id']):r for r in result['rows']}
            if evidence_rows:
                evidence_key=st.selectbox('Inspect ranked player',list(evidence_rows),format_func=lambda key:evidence_rows[key]['Player']+' · '+evidence_rows[key]['Matchup'])
                picked=evidence_rows[evidence_key]
                try:
                    evidence=research.player_evidence(hist,day,picked['Team'],picked['_player_id'],choices[picked['_game_id']][picked['Team']])
                    st.write(f"Selected model: {selected_model} · First-score estimate: {picked['Model %']:.2f}% · Team-first estimate: {picked['Team first %']:.2f}% · Within-team share: {picked['Within-team share %']:.2f}%")
                    st.caption('Raw historical rates below are not forecast probabilities. Last 10 and last 30 mean recorded starts in the 400-day window, not all appearances or necessarily every game played. Only earlier dates and this team are used.')
                    if evidence['last_start']:
                        st.write(f"Last recorded start for this team: {evidence['last_start']} ({evidence['days_since_last_start']} days before the analysis date).")
                    else:st.warning('No recorded starts for this player on this team in the model window. The estimate relies on model priors and the selected five.')
                    if evidence['other_team_starts']:st.caption(f"{evidence['other_team_starts']} starts on other teams are excluded from this player’s model history.")
                    st.dataframe(pd.DataFrame(evidence['summary']),hide_index=True,use_container_width=True)
                    st.caption('Shot coverage: '+picked['Shot coverage note']+'. Recent-form and lineup safeguards use 90-day decay across observed starts; lineup-specific counts remain separate. Rounded display values do not determine the hold.')
                    st.caption('Opening-shot rates use only starts with an identified team opening shooter. Older all-zero records are ambiguous and excluded from that denominator; confirmed bench opening shots count as observed misses for starters. First-score history still uses all valid starts.')
                    st.caption('Team opening shots count field-goal attempts, not free throws. Game first points include free throws. Conditional scoring share divides by games in which the team scored first; a blank rate means no such opportunities. Similar lineups contain at least four selected starters.')
                    if evidence['games']:
                        evidence_frame=pd.DataFrame(evidence['games'])
                        st.dataframe(evidence_frame,hide_index=True,use_container_width=True)
                        st.download_button('Download player evidence CSV',evidence_frame.to_csv(index=False).encode(),'apex_player_evidence.csv','text/csv')
                    st.caption('History excludes games whose first scorer was not a starter. These observed rates inherit that selection bias and do not establish a betting edge.')
                except (ValueError,KeyError) as exc:st.error(str(exc))
        with st.expander('Lineup what-if · compare one starter change'):
            st.caption('Hypothetical research only. This does not change your selected five, confirmations, rankings or journal. The model holds team-first probability fixed; this is not an estimate of the full causal impact of an absence.')
            eligible=[g for g in games if g['gameId'] in {r['_game_id'] for r in result['rows']}]
            if eligible:
                by_game={g['gameId']:g for g in eligible}
                scenario_gid=st.selectbox('Scenario matchup',list(by_game),format_func=lambda gid:by_game[gid]['awayTeam']['teamTricode']+' vs '+by_game[gid]['homeTeam']['teamTricode'])
                scenario_game=by_game[scenario_gid]
                scenario_team=st.selectbox('Scenario team',sorted(choices[scenario_gid]))
                original={p['player_id']:p for p in choices[scenario_gid][scenario_team]}
                outgoing=st.selectbox('Replace starter',list(original),format_func=lambda pid:original[pid]['player'])
                chosen_ids={p['player_id'] for players in choices[scenario_gid].values() for p in players}
                alternatives={p['player_id']:p for p in slate['rosters'][scenario_team] if p['player_id'] not in chosen_ids}
                if alternatives:
                    incoming=st.selectbox('Alternative starter',list(alternatives),format_func=lambda pid:alternatives[pid]['player'])
                    scenario_signature=json.dumps([signature,scenario_gid,scenario_team,outgoing,incoming],sort_keys=True)
                    if st.button('Compare starter change'):
                        st.session_state.pop('lineup_scenario',None)
                        try:
                            comparison=core.compare_lineup_swap(hist,scenario_game,choices[scenario_gid],scenario_team,outgoing,incoming,slate['rosters'][scenario_team],reports,selected_model)
                            st.session_state['lineup_scenario']={'signature':scenario_signature,'comparison':comparison}
                        except (ValueError,KeyError) as exc:st.error(str(exc))
                    scenario=st.session_state.get('lineup_scenario')
                    if scenario and scenario['signature']==scenario_signature:
                        comparison=scenario['comparison']
                        st.write('Top estimate before: '+', '.join(comparison['before_top']))
                        st.write('Top estimate after: '+', '.join(comparison['after_top']))
                        scenario_frame=pd.DataFrame(comparison['rows'])
                        st.dataframe(scenario_frame,hide_index=True,use_container_width=True)
                        st.caption('Blank values mean the player is outside that selected five, not a predicted zero chance of scoring. Changes are shown only for players in both scenarios. Injury flags do not confirm availability.')
                        st.download_button('Download lineup scenario CSV',scenario_frame.to_csv(index=False).encode(),'apex_lineup_scenario.csv','text/csv')
                    elif scenario:st.info('Scenario inputs changed. Compare starter change again.')
                else:st.info('No unselected players are available in the loaded roster. Refresh the roster or choose another team.')
        st.caption('Saving records all three models with the same confirmed five, date and history before tip-off. The first saved forecast is permanent; later lineup edits do not change it. Comparison estimates need no extra API requests.')
        if st.button('Save confirmed forecasts to journal',disabled=analysis_mode=='Research matchup'):
            try:
                live={g['gameId']:g for g in core.fresh_schedule(day)}
                saved=0;duplicates=0
                for gid in sorted({r['_game_id'] for r in result['rows']}):
                    game=live.get(gid)
                    if not game or not core.upcoming(game):
                        st.warning(gid+': game started or is unavailable; not saved.');continue
                    rows=[r for r in result['rows'] if r['_game_id']==gid]
                    try:
                        bundle=result['model_bundles'][gid]
                        inserted=research.save_forecast(game,rows,confirmations.get(gid,{}),updater.current_version(),research.fingerprint(hist),inj.get('time'),model_forecasts=bundle)
                        saved+=int(inserted);duplicates+=int(not inserted)
                    except ValueError as exc:st.warning(str(exc))
                st.success(f'Saved {saved} new forecasts. {duplicates} already had a saved forecast and were left unchanged.')
            except (RuntimeError,ValueError,KeyError,OSError) as exc:st.error(str(exc))

    elif result:
        st.info('Inputs changed. Run rankings again to refresh results.')
with st.expander('Build deeper history · prior-season import'):
    st.write('Add prior-season games in resumable batches. Existing games are kept and skipped on future downloads. The first batch can take several minutes; keep this window open.')
    today_et=datetime.now(ZoneInfo('America/New_York')).date()
    current_end=today_et.year+1 if today_et.month>=10 else today_et.year
    season_end=st.selectbox('Prior season',list(range(current_end-1,max(2020,current_end-4),-1)),format_func=lambda y:f'{y-1}–{y}')
    batch=st.selectbox('Maximum new games per batch',[100,250,500,1500],index=1)
    st.caption('Latest missing games are loaded first. Rankings use only the 400 days before the game date. Historical sample counts can include last season; current-season starts are shown separately.')
    if st.button('Import prior-season history'):
        line=st.empty()
        try:
            report=research.import_season(season_end,batch,progress=line.info)
            st.session_state['import_report']=report
            st.session_state.pop('results',None)
            st.session_state.pop('evaluation',None)
            st.rerun()
        except (RuntimeError,ValueError,OSError) as exc:
            st.error(str(exc))
    report=st.session_state.get('import_report')
    if report:
        st.success(f"Added {report['added']} of {report['attempted']} attempted games; {report['remaining']} completed games remain missing.")
        for warning in report['schedule_warnings']: st.warning(warning)
        if report['skipped']:
            st.warning('Some games could not be imported. Games with a nonstarter first scorer remain excluded by this model.')
            st.dataframe(pd.DataFrame(report['skipped']),hide_index=True,use_container_width=True)

with st.expander('Data quality & coverage'):
    valid,issues=research.audit(hist)
    if issues:
        st.error(f'{len(issues)} game(s) failed data checks. They are excluded from backtests and block affected rankings/imports. No rows were deleted.')
        st.dataframe(pd.DataFrame(issues),hide_index=True,use_container_width=True)
        st.caption('Repair re-downloads only selected flagged games from ESPN. Validated replacements are saved together after a full history backup. Failed games remain untouched. Stop other imports while repairing.')
        repair_ids=st.multiselect('Flagged games to repair',[r['game_id'] for r in issues],default=[r['game_id'] for r in issues[:5]],max_selections=20)
        if st.button('Repair selected history games',disabled=not repair_ids):
            try:
                progress=st.empty()
                with st.spinner('Checking replacement game data…'):
                    st.session_state['repair_report']=research.repair_history(repair_ids,progress=progress.info)
                for key in ('results','evaluation','model_comparison','lineup_scenario','validation_report','signal_comparison'):st.session_state.pop(key,None)
                st.rerun()
            except (RuntimeError,ValueError,OSError) as exc:st.error(str(exc))

    elif hist:
        st.success('All saved games passed starter-count, ID, date, opponent, opening-shot, possession-proxy and scoring-consistency checks.')
        st.caption(f"History: {min(r['date'] for r in valid)} through {max(r['date'] for r in valid)}")
    else: st.info('Sync or import history to see coverage.')
    repaired=st.session_state.get('repair_report')
    if repaired:
        st.info(f"Last repair: {repaired['repaired']} of {repaired['attempted']} games replaced.")
        if repaired['backup']:st.caption('Original history backup: data/'+repaired['backup'])
        if repaired['errors']:st.dataframe(pd.DataFrame(repaired['errors']),hide_index=True,use_container_width=True)
    active=research.history_window(valid,day)
    proxy_coverage=eng.team_stats(active)
    st.caption('Opening-action proxy coverage is shown separately. Unknown proxies do not count as possession losses. The proxy is not a verified jump-ball winner.')
    coverage=[]
    for team in sorted(eng.TEAMS):
        rows=[r for r in active if r['team']==team]
        coverage.append({'Team':team,'Games in 400-day window':len({r['game_id'] for r in rows}),'Games with opening-action proxy':proxy_coverage.get(team,{}).get('proxy_games',0),'Latest game':max((r['date'] for r in rows),default='None')})
    st.dataframe(pd.DataFrame(coverage),hide_index=True,use_container_width=True)

with st.expander('Backtest lab · test the model before trusting it'):
    st.write('Walk-forward testing predicts each game using earlier dates only. The 400-day window matches dashboard rankings. Same-day results never enter training.')
    warmup=st.selectbox('Minimum training games before evaluation',[30,100,250],index=1)
    if st.button('Run walk-forward evaluation'):
        with st.spinner('Evaluating historical games…'):
            st.session_state['evaluation']=research.evaluate(hist,warmup,model=selected_model)
    if st.button('Compare opening-shot vs first-score signals'):
        progress=st.empty()
        with st.spinner('Testing fixed signals and earlier-date selection…'):
            st.session_state['signal_comparison']=research.compare_scoring_signals(hist,warmup,selected_model,progress.info)
    signals=st.session_state.get('signal_comparison')
    if signals and signals['fingerprint']==research.fingerprint(hist) and signals['min_training']==warmup and signals['model']==selected_model:
        st.markdown('**Which player signal helps? · '+selected_model+'**')
        if signals['summary']:
            st.dataframe(pd.DataFrame(signals['summary']),hide_index=True,use_container_width=True)
            st.caption('Same games, earlier-date training, team probabilities, priors and lineup rules. Only the player-signal blend changes: current 65% opening-shot / 35% first-score rates, opening-shot rates alone, or first-score rates alone. The weights mix smoothed rates before normalizing the five players; they are not shares of final win probability. The first-score signal is unconditional in baseline and conditional on the team scoring first in recent/lineup.')
            st.caption('Earlier-date selector chooses among those three fixed blends using average log loss from prior evaluated games within 400 days. It requires 100 such games; before that it uses the current blend. All matchups on a date share a decision made before that date’s results. This selects a discrete blend, not continuously fitted weights.')
            st.write(f"Adaptive decisions used sufficient earlier evidence for {signals['adaptive_learned_games']} evaluated games; remaining games used the fallback.")
            st.dataframe(pd.DataFrame(signals['selection_decisions']),hide_index=True,use_container_width=True)
            st.download_button('Download adaptive signal decisions CSV',pd.DataFrame(signals['selection_decisions']).to_csv(index=False).encode(),'apex_signal_decisions.csv','text/csv')
            st.dataframe(pd.DataFrame(signals['recent_comparisons']),hide_index=True,use_container_width=True)
            st.caption('Recent differences are candidate minus current blend, with approximate 95% intervals resampling whole dates. The newest quarter is a rolling diagnostic, not an untouched final test set. Intervals resample the already-produced forecasts; they do not retrain the selector or capture all selection uncertainty. This experiment does not change live rankings or establish profit. Historical starter-selection bias remains.')
            if signals['latest_dates']<30:st.warning('Fewer than 30 dates in the recent signal comparison. Differences can be unstable.')
            st.caption(f"Invalid historical games excluded: {signals['excluded_games']}.")
            st.download_button('Download signal comparison CSV',pd.DataFrame(signals['summary']).to_csv(index=False).encode(),'apex_signal_comparison.csv','text/csv')
            st.download_button('Download signal predictions CSV',pd.DataFrame(signals['details']).to_csv(index=False).encode(),'apex_signal_predictions.csv','text/csv')
        else:st.info('Not enough eligible history for the signal comparison. Import more games or lower the training minimum.')
    elif signals:st.info('History, model or training minimum changed. Run the signal comparison again.')
    if st.button('Run full model validation'):
        progress=st.empty()
        with st.spinner('Evaluating all three models…'):
            st.session_state['validation_report']=research.validation_report(hist,warmup,progress=progress.info)
    validation=st.session_state.get('validation_report')
    if validation and validation['fingerprint']==research.fingerprint(hist) and validation['min_training']==warmup:
        st.markdown('**Full model validation**')
        if not validation['summary']:st.info('No eligible evaluation dates yet. Import more history or lower the training minimum.')
        else:
            st.dataframe(pd.DataFrame(validation['summary']),hide_index=True,use_container_width=True)
            st.caption('All models use identical games. The newest period is the final 25% of distinct evaluation dates, rounded up; games on one date stay together. Training still advances using earlier dates. This is a recent-performance diagnostic, not an untouched final test set.')
            st.caption('Negative log-loss/Brier differences beat equal 10-player probabilities on that sample. Top-three accuracy measures coverage, not profit.')
            if validation['latest_dates']<30:st.warning('The newest period contains fewer than 30 evaluation dates. Recent estimates and uncertainty intervals can be unstable.')
            st.markdown('**Recent differences versus baseline**')
            st.dataframe(pd.DataFrame(validation['latest_comparisons']),hide_index=True,use_container_width=True)
            st.caption('Approximate 95% intervals resample whole dates. Crossing zero does not distinguish models on that metric; across-date dependence and repeated comparisons remain limitations.')
            st.markdown('**Where does the scoring error come from?**')
            st.dataframe(pd.DataFrame(validation['scoring_stages']),hide_index=True,use_container_width=True)
            st.caption('Team error measures which team scores first. Player error measures the scorer’s share within the actual winning team, regardless of which team the model favored; it is a diagnostic, not a separate live pick accuracy. Team log loss plus within-team log loss equals total player log loss. Compare each stage with its own equal-probability baseline: negative differences are better on this sample. Ties receive fractional credit. These results do not fit or promote a model.')
            st.download_button('Download scoring-stage diagnostics CSV',pd.DataFrame(validation['scoring_stages']).to_csv(index=False).encode(),'apex_scoring_stages.csv','text/csv')
            st.markdown('**Do stronger picks win more often?**')
            st.dataframe(pd.DataFrame(validation['pick_reliability']),hide_index=True,use_container_width=True)
            st.caption('Each game counts once within each grouping. Probability bands compare the leading estimate with its observed hit rate; margin bands compare the leader with the runner-up. Lower bounds are inclusive and upper bounds exclusive. Tied leaders receive fractional hit credit; ties have zero margin. Small groups can be noisy. These are descriptive diagnostics, not fitted corrections, confidence intervals or betting thresholds.')
            st.download_button('Download pick reliability CSV',pd.DataFrame(validation['pick_reliability']).to_csv(index=False).encode(),'apex_pick_reliability.csv','text/csv')
            st.markdown('**Results by month**')
            st.dataframe(pd.DataFrame(validation['monthly']),hide_index=True,use_container_width=True)
            st.caption(f"Invalid historical games excluded: {validation['excluded_games']}. Historical starting-five and nonstarter-selection limitations still apply. No model is promoted automatically.")
            st.download_button('Download full validation CSV',pd.DataFrame(validation['details']).to_csv(index=False).encode(),'apex_full_validation.csv','text/csv')
            st.download_button('Download validation summary CSV',pd.DataFrame(validation['summary']).to_csv(index=False).encode(),'apex_validation_summary.csv','text/csv')
    elif validation:st.info('History or training minimum changed. Run full model validation again.')
    st.caption('Evaluation model: '+selected_model)
    if st.button('Compare baseline vs recent form'):
        with st.spinner('Testing both models on identical chronological holdouts…'):
            compared={name:research.evaluate(hist,warmup,model=name) for name in ('baseline','recent')}
            st.session_state['model_comparison']={'fingerprint':research.fingerprint(hist),'warmup':warmup,'results':compared,'paired':research.compare_evaluations(compared['baseline'],compared['recent'])}
    if st.button('Compare baseline vs lineup context'):
        with st.spinner('Testing lineup context on identical chronological holdouts…'):
            compared={name:research.evaluate(hist,warmup,model=name) for name in ('baseline','lineup')}
            st.session_state['model_comparison']={'fingerprint':research.fingerprint(hist),'warmup':warmup,'results':compared,'paired':research.compare_evaluations(compared['baseline'],compared['lineup'])}
    comparison=st.session_state.get('model_comparison')
    if comparison and comparison['fingerprint']==research.fingerprint(hist) and comparison['warmup']==warmup:
        st.dataframe(pd.DataFrame([{'Model':name,**result['metrics']} for name,result in comparison['results'].items()]),hide_index=True,use_container_width=True)
        paired=comparison.get('paired')
        if paired and paired['games']:
            st.markdown('**How certain is the difference?**')
            st.dataframe(pd.DataFrame(paired['metrics']),hide_index=True,use_container_width=True)
            st.caption(f"{paired['games']} paired games across {paired['dates']} dates. Approximate 95% intervals resample whole dates. An interval crossing zero does not distinguish the models on that metric. Dates can still be correlated across a season; this is not proof of future performance.")
            if paired['dates']<30:st.warning('Fewer than 30 evaluation dates: uncertainty estimates are especially unstable. Import more history.')
            st.download_button('Download paired model comparison',pd.DataFrame(paired['metrics']).to_csv(index=False).encode(),'apex_model_comparison.csv','text/csv')
        st.caption('Same saved games and training dates for both models. This comparison does not select or tune a winner automatically. Use the forward journal for new-game validation.')
    evaluation=st.session_state.get('evaluation')
    if evaluation and evaluation['fingerprint']==research.fingerprint(hist) and evaluation['min_training']==warmup and evaluation.get('model','baseline')==selected_model:
        m=evaluation['metrics'];n=m['Evaluated games']
        if not n: st.info('Not enough eligible dates after the training period. Import more history or lower the minimum training size.')
        else:
            st.caption(f'{n} games evaluated. Lower log loss and Brier score are better. Top-1 credit is split equally when model probabilities tie.')
            compare=pd.DataFrame([{'Model':'APEX',**m},{'Model':'Equal 10-player baseline','Evaluated games':n,'Top-1 hit %':10.0,'Top-3 hit %':30.0,'Log loss':2.302585093,'Brier':0.9}])
            st.dataframe(compare,hide_index=True,use_container_width=True)
            if m['Log loss']>=2.302585093:
                st.warning('On this sample, the model does not beat equal probabilities on log loss.')
            else: st.info('Log loss is lower than the equal-probability baseline on this sample. That does not establish calibration, statistical significance, or profitable odds.')
            st.markdown('**Calibration check**')
            st.caption('Compare the average predicted probability with the observed first-score rate. These are player-level groups, not independent observations or a fitted correction.')
            st.dataframe(pd.DataFrame(evaluation['calibration']),hide_index=True,use_container_width=True)
            st.download_button('Download game-by-game backtest',pd.DataFrame(evaluation['games']).to_csv(index=False).encode(),f'apex_backtest_{day}.csv','text/csv')
    elif evaluation: st.info('History or training settings changed. Run evaluation again.')
    st.warning('Backtests use actual historical starting fives and exclude games where the first scorer was a nonstarter. These limitations can bias results. No historical odds are included, so this is not a profit/ROI backtest.')

with st.expander('Forward-testing journal · actual future results'):
    st.write('Save forecasts from the rankings table before tip-off, then refresh completed games here. This is a local research record, not a bet log. No wagers or profit estimates are involved.')
    if st.button('Check completed games for journal'):
        line=st.empty()
        try:
            with st.spinner('Checking first scorers…'):
                updated,errors=research.refresh_journal(progress=line.info)
            st.success(f'Updated {updated} completed games.')
            for error in errors:st.warning(error['game_id']+': '+error['reason'])
        except (OSError,ValueError) as exc:st.error(str(exc))
    try:
        records=research.journal_records()
        if not records:st.info('No saved forecasts yet. Run rankings, confirm the five starters for each team, and click Save confirmed forecasts to journal.')
        else:
            versions=sorted({r['snapshot']['model_version'] for r in records})
            chosen=st.selectbox('Journal model version',['All versions']+versions)
            selected=records if chosen=='All versions' else [r for r in records if r['snapshot']['model_version']==chosen]
            paired_forward=research.forward_model_comparison(selected)
            st.markdown('**Forward model comparison · identical saved games**')
            st.caption(f"{paired_forward['matched_games']} games have all three pre-tip forecasts. {paired_forward['excluded_games']} older or single-model games are excluded from this comparison, but remain in the journal.")
            if paired_forward['matched_games']:
                st.dataframe(pd.DataFrame(paired_forward['summary']),hide_index=True,use_container_width=True)
                st.download_button('Download forward model comparison CSV',pd.DataFrame(paired_forward['details']).to_csv(index=False).encode(),'apex_forward_models.csv','text/csv')
                st.caption('Compare within one software version for consistent model formulas. Small samples do not establish a better model; no default is changed automatically.')
                st.markdown('**Pregame pick reliability · settled games only**')
                if paired_forward['pick_reliability']:
                    st.dataframe(pd.DataFrame(paired_forward['pick_reliability']),hide_index=True,use_container_width=True)
                    st.download_button('Download forward pick reliability CSV',pd.DataFrame(paired_forward['pick_reliability']).to_csv(index=False).encode(),'apex_forward_pick_reliability.csv','text/csv')
                    st.caption('Uses only probabilities saved before tip-off, without recalculating predictions. All three models use the same settled games. Pending games are excluded; outside-field winners and lineup mismatches remain included. Each game counts once per grouping, with fractional credit for tied leaders. These descriptive bands do not tune probabilities or establish a betting edge. Unlike the historical backtest, this report retains nonstarter winners.')
                else:st.info('Pick reliability will appear after saved three-model forecasts have completed outcomes. Click Check completed games for journal after games finish.')
            journal_model=st.selectbox('Journal scoring model',['All models','baseline','recent','lineup'])
            if journal_model!='All models':selected=research.journal_model_records(selected,journal_model)
            st.caption('All models shows one selected forecast per game. Choosing a model also includes its saved comparison forecasts, when available.')
            metrics=research.journal_summary(selected)
            j1,j2,j3=st.columns(3)
            j1.metric('Saved forecasts',metrics['Saved games'])
            j2.metric('Completed forecasts',metrics['Settled games'])
            j3.metric('Top-1 hit rate',f"{metrics['Top-1 hit %']:.1f}%" if metrics['Top-1 hit %'] is not None else 'Pending')
            st.caption('Top ties receive fractional credit. Only saved games are measured; this is not an all-slate benchmark. System-clock timestamps are local records, not independently certified.')
            st.write(f"Outside-field winners: {metrics['Outside-field winners']} · Lineup mismatches: {metrics['Lineup mismatches']}")
            if metrics['Settled games']:
                st.write(f"Brier score: {metrics['Brier']:.4f} · Log loss: {metrics['Log loss']}")
            table=pd.DataFrame(research.journal_table(selected))
            st.dataframe(table,hide_index=True,use_container_width=True)
            st.download_button('Download forward journal CSV',table.to_csv(index=False).encode('utf-8'),'apex_forward_journal.csv','text/csv')
            st.warning('Forecasts with injury/sample holds and incorrect starting fives remain in the results. Winners outside the predicted ten are retained as misses, not dropped. Final results are recorded once; provider corrections are not automatically reapplied.')
    except (OSError,ValueError) as exc:st.error(str(exc))
