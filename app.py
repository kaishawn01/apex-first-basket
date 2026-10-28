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
import simulation
import phase2
import opening_data

st.set_page_config(page_title='APEX • First Basket',page_icon='🏀',layout='wide')
st.markdown('''<style>.stApp {background:#0d1420} [data-testid="stMetric"] {background:#172335;border:1px solid #2a3d53;border-radius:12px;padding:16px} .block-container {max-width:1350px} h1 {letter-spacing:-1px}</style>''',unsafe_allow_html=True)
st.caption('APEX / NBA RESEARCH DESK · V' + updater.current_version() + ' · V3 DEVELOPMENT PREVIEW')
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


with st.sidebar.expander('V3 simulation settings'):
    mc_trials=st.selectbox('Monte Carlo trials',[1000,5000,20000],index=1)
    mc_weight=st.slider('Hybrid simulation weight',0.0,0.8,0.35,0.05)
    mc_seed=int(st.number_input('Simulation seed',min_value=0,max_value=2147483647,value=3000,step=1))
    st.caption('Scenario assumptions below are not learned from your saved opening-event data.')
    mc_turnover=st.number_input('Turnover probability per event',0.0,0.5,0.13,0.01)
    mc_foul=st.number_input('Two-shot foul probability per event',0.0,0.5,0.10,0.01)
    mc_rebound=st.number_input('Offensive rebound probability after a miss',0.0,1.0,0.24,0.01)
    mc_ft=st.number_input('Free-throw make probability',0.0,1.0,0.77,0.01)
mc_config=simulation.SimulationConfig(trials=mc_trials,seed=mc_seed,hybrid_weight=mc_weight,
    turnover_rate=mc_turnover,shooting_foul_rate=mc_foul,offensive_rebound_rate=mc_rebound,free_throw_rate=mc_ft)
mc_settings=simulation.asdict(mc_config)


hist=eng.read_csv(eng.HISTORY)
try:phase2_sequences=opening_data.load()
except (ValueError,OSError):
    phase2_sequences={}
    st.warning('Opening-sequence file is unreadable. Phase 2 will label missing empirical data explicitly.')
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
            roster_map={}; errors=[]; unavailable_rosters=[]
            for team in sorted({g[s]['teamTricode'] for g in games for s in ('awayTeam','homeTeam')}):
                try: roster_map[team]=core.roster(team)
                except (RuntimeError,KeyError,ValueError) as exc:
                    errors.append(f'{team}: roster unavailable; only historical starters are available.')
                    unavailable_rosters.append(team)
                    roster_map[team]=[{'player_id':r['player_id'],'player':r['player']} for r in eng.recent_starters([r for r in hist if r['date']<day],team)]
            st.session_state['slate']={'day':day,'games':games,'rosters':roster_map,'loaded':datetime.now().isoformat(timespec='seconds'),'errors':errors,'unavailable_rosters':unavailable_rosters,'mode':analysis_mode,'research_teams':[research_away,research_home]}
            st.session_state.pop('nba_lineups',None)
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
        st.session_state['injuries']={'reports':reports,'time':datetime.now(ZoneInfo('UTC')).isoformat(timespec='seconds')}
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
    if st.button('Load NBA-confirmed starters · resets selections',disabled=analysis_mode=='Research matchup' or not games):
        st.session_state.pop('nba_lineups',None)
        st.session_state.pop('results',None)
        st.session_state['revision']=st.session_state.get('revision',0)+1
        try:
            with st.spinner('Checking fresh schedule and NBA starting lineups…'):
                fresh_games=core.fresh_schedule(day)
                usable_rosters={}
                for team in slate['rosters']:
                    try:
                        usable_rosters[team]=core.roster(team)
                        slate['rosters'][team]=usable_rosters[team]
                    except (RuntimeError,ValueError,KeyError,TypeError):
                        st.warning(team+': roster refresh failed; NBA confirmation is unavailable for this team.')
                slate['unavailable_rosters']=[team for team in slate['rosters'] if team not in usable_rosters]
                st.session_state['nba_lineups']=core.fetch_nba_confirmed_lineups(day,fresh_games,usable_rosters)
        except (RuntimeError,ValueError,KeyError,TypeError):st.warning('NBA lineup check failed. Provider confirmations were cleared. Review projections or confirm the announced five manually.')
    nba_state=st.session_state.get('nba_lineups',{})
    nba_entries=nba_state.get('entries',{}) if nba_state.get('day')==day else {}
    if nba_state.get('day')==day:
        st.caption('NBA lineup check: '+nba_state['fetched_at']+' · Provider confirmation expires after five minutes and is checked again before rankings and saving.')
        for message in nba_state.get('messages',[]):st.info(message)
    choices={}; confirmations={}; manual_confirmations={}; confirmation_sources={}

    for g in games:
        gid=g['gameId']; away,home=(g[s]['teamTricode'] for s in ('awayTeam','homeTeam'))
        start=datetime.fromisoformat(g['start_time'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
        with st.expander(f'{away} vs {home} · RESEARCH' if g.get('research_only') else f'{away} @ {home} · {start:%I:%M %p} ET',expanded=True):
            choices[gid]={}; confirmations[gid]={}; manual_confirmations[gid]={}
            for col,team in zip(st.columns(2),(away,home)):
                with col:
                    players=slate['rosters'][team]; byid={p['player_id']:p for p in players}
                    projection=core.projection_evidence(hist,team,day,players,roster_verified=team not in slate.get('unavailable_rosters',[]))
                    defaults=projection['defaults']
                    nba_entry=nba_entries.get(gid,{}).get(team,{})
                    nba_players=[byid[pid] for pid in nba_entry.get('player_ids',[]) if pid in byid]
                    if core.nba_confirmation_matches(nba_entry,g,nba_players):defaults=[p['player_id'] for p in nba_players]
                    selected=st.multiselect(f'{team} · select five starters',list(byid),default=defaults,
                        format_func=lambda pid,byid=byid:byid[pid]['player'],max_selections=5,
                        key=f'five:{day}:{gid}:{team}:{st.session_state.get("revision",0)}')
                    choices[gid][team]=[byid[pid] for pid in selected]
                    st.caption('Projection: latest valid recorded five on the loaded roster, only when history is at most 30 days old. This review cutoff is a guardrail, not a validated accuracy threshold. Use the NBA lineup button to check for provider-confirmed starters. Injuries are flagged; replacements require your review.')
                    if projection['last_game_date']:st.caption(f"Last recorded team game: {projection['last_game_date']} · {projection['history_age_days']} days before the selected date.")
                    for warning in projection['warnings']:st.warning(warning)
                    st.markdown('**Recent starting-lineup evidence**')
                    evidence=[]
                    for item in projection['players']:
                        injury=core.injury_for(reports,team,byid[item['Player ID']]['player'])
                        evidence.append({**item,'Selected':item['Player ID'] in selected,'Injury report':injury['status'] if injury else 'No matched report; availability unverified'})
                    st.dataframe(pd.DataFrame(evidence),hide_index=True,use_container_width=True)
                    st.caption('Counts use up to five valid recorded games in the prior 60 days, excluding the selected date. Missing games and the history’s nonstarter-scorer exclusion can affect these counts. They are evidence for review, not starting probabilities. Reload the slate to refresh rosters and reset selections and confirmations.')
                    for pid in selected:
                        report=core.injury_for(reports,team,byid[pid]['player'])
                        if report: st.warning(f"{report['player']}: {report['status']} — {report['description']}")
                    if g.get('research_only'):
                        confirmations[gid][team]=False
                        manual_confirmations[gid][team]=False
                        st.caption('HYPOTHETICAL STARTING FIVE')
                    else:
                        confirmed=st.checkbox(f'I verified {team}’s announced starters for this game',key=f'confirm:{day}:{gid}:{team}:{st.session_state.get("revision",0)}:{",".join(sorted(selected))}',disabled=len(selected)!=5)
                        manual_confirmations[gid][team]=confirmed and len(selected)==5
                        provider_confirmed=core.nba_confirmation_matches(nba_entry,g,choices[gid][team])
                        confirmations[gid][team]=provider_confirmed or manual_confirmations[gid][team]
                        st.caption('NBA FEED CONFIRMED' if provider_confirmed else 'USER CONFIRMED' if confirmed else 'PROJECTED / UNCONFIRMED')
                        if nba_entry:
                            st.caption('NBA source timestamps: '+', '.join(nba_entry.get('source_timestamps',[nba_entry['source_timestamp']]))+' · timezone: '+nba_entry.get('source_timezone','unspecified'))
                            if not provider_confirmed:st.info('NBA confirmation is expired, does not match this five, or the game changed. Reload NBA starters or verify manually.')
            confirmation_sources[gid]=core.lineup_confirmation_sources(g,choices[gid],manual_confirmations[gid],nba_entries.get(gid,{}))
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
    signature=json.dumps({'day':day,'choices':choices,'confirmed':confirmations,'confirmation_sources':confirmation_sources,'nba_fetched':nba_state.get('fetched_at'),'odds_time':prices_state.get('fetched') if prices else None,'injury_time':inj.get('time'),'history':research.fingerprint(hist),'model':selected_model,'workspace':analysis_mode},sort_keys=True)
    if st.button('3 · Run rankings',type='primary',disabled=not games):
        st.session_state.pop('results',None)
        try:
            fresh={g['gameId']:g for g in games} if analysis_mode=='Research matchup' else {g['gameId']:g for g in core.fresh_schedule(day)}
            rows=[];model_bundles={}
            for g in games:
                current=fresh.get(g['gameId'])
                if not current or (not current.get('research_only') and not core.upcoming(current)):
                    st.warning(f"{g['gameId']}: started or no longer scheduled; skipped."); continue
                sources=core.lineup_confirmation_sources(current,choices[g['gameId']],manual_confirmations[g['gameId']],nba_entries.get(g['gameId'],{}))
                if sources!=confirmation_sources[g['gameId']]:raise ValueError('Lineup confirmation changed or expired. Refresh the lineup and run rankings again.')
                bundle={m:core.rank_game(hist,current,choices[g['gameId']],{t:v!='Unconfirmed' for t,v in sources.items()},prices if m==selected_model else {},reports,model=m) for m in ('baseline','recent','lineup')}
                model_bundles[g['gameId']]=bundle
                rows.extend(bundle[selected_model])
            st.session_state['results']={'rows':rows,'model_bundles':model_bundles,'signature':signature,'time':datetime.now(ZoneInfo('UTC')).isoformat(timespec='seconds')}
        except (RuntimeError,ValueError,KeyError) as exc:
            st.error(str(exc) if isinstance(exc,(RuntimeError,ValueError)) else 'Unexpected data response. Reload slate.')
    result=st.session_state.get('results')
    if result and result['signature']==signature:
        st.caption('Rankings generated: '+result['time']+' • Model EV uses uncalibrated estimates, not proven value.')
        leaders=core.matchup_leader_board(result['rows'])
        st.markdown('**Top first-score candidates · by matchup**')
        if leaders:
            leader_frame=pd.DataFrame(leaders)
            st.dataframe(leader_frame.drop(columns=['Game']),hide_index=True,use_container_width=True)
            st.caption('One row per matchup, ordered by its highest individual estimate. Every tied leader is included; Each leader % is an individual probability, not the chance that any listed player scores. A larger gap is not proof of confidence or value. Rankings use full precision, so close estimates can look equal after display rounding. Free throws count.')
            if any(r['Tied leaders']==10 for r in leaders):st.info('At least one matchup ties all ten players. The model has no unique top candidate for that game.')
            st.download_button('Download top candidates CSV',leader_frame.to_csv(index=False).encode(),'apex_top_candidates.csv','text/csv')
        else:st.info('No matchups produced rankings. Reload the slate and review the game status.')
        st.markdown('**Full player rankings**')
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
        with st.expander('V3 Phase 2 research · first shot and first score'):
            p2_games={g['gameId']:g for g in games if g['gameId'] in result.get('model_bundles',{})}
            if p2_games:
                p2_gid=st.selectbox('Phase 2 matchup',list(p2_games),format_func=lambda gid:result['model_bundles'][gid]['baseline'][0]['Matchup'])
                p2_key=json.dumps({'inputs':signature,'game':p2_gid,'config':mc_settings,'sequences':research.fingerprint(phase2_sequences)},sort_keys=True)
                if st.button('Run Phase 2 research simulation'):
                    st.session_state.pop('phase2_simulation',None)
                    try:
                        current=p2_games[p2_gid]
                        if not current.get('research_only'):
                            current=next((g for g in core.fresh_schedule(day) if g['gameId']==p2_gid),None)
                            if not current or not core.upcoming(current) or current['start_time']!=p2_games[p2_gid]['start_time']:raise ValueError('Game started or changed. Reload the slate.')
                        fresh_rosters={}
                        for team in choices[p2_gid]:
                            try:fresh_rosters[team]=core.roster(team)
                            except (RuntimeError,ValueError,KeyError):fresh_rosters[team]=[]
                        ready=core.phase2_readiness(current,choices[p2_gid],manual_confirmations[p2_gid],nba_entries.get(p2_gid,{}),fresh_rosters,reports,inj.get('time'))
                        if any('roster' in message or 'identit' in message for message in ready['messages']):raise ValueError('Current-team verification failed. Refresh the slate and correct the selected five.')
                        with st.spinner('Simulating empirical opening sequences…'):
                            p2_report=phase2.simulate(hist,choices[p2_gid],day,phase2_sequences,mc_config)
                        st.session_state['phase2_simulation']={'signature':p2_key,'report':p2_report,'readiness':ready,'checked_at':datetime.now(ZoneInfo('UTC')).isoformat()}
                    except (ValueError,RuntimeError,KeyError) as exc:st.error(str(exc))
                p2_saved=st.session_state.get('phase2_simulation')
                if p2_saved and p2_saved['signature']==p2_key and 0<=(datetime.now(ZoneInfo('UTC'))-datetime.fromisoformat(p2_saved['checked_at'])).total_seconds()<=300:
                    pr=p2_saved['report'];st.warning(p2_saved['readiness']['status'])
                    for message in p2_saved['readiness']['messages']:st.caption(message)
                    st.caption('Verification: '+', '.join(t+': '+v for t,v in p2_saved['readiness']['sources'].items()))
                    st.caption(f"Trials: {pr['config']['trials']:,} · empirical sequence games: {pr['inputs']['sequence_games']} · unresolved: {pr['unresolved_trials']} · effective blend: {pr['effective_hybrid_weight']:.0%}")
                    people={p['player_id']:(t,p['player']) for t,ps in choices[p2_gid].items() for p in ps}
                    for rank,pid in enumerate(sorted(pr['hybrid'],key=lambda pid:(-pr['hybrid'][pid],pid))[:5],1):
                        team,name=people[pid]
                        st.markdown(f'**{rank}. {name} · {team}**')
                        st.write(f"Hybrid {pr['hybrid'][pid]:.1%} · Baseline {pr['baseline'][pid]:.1%} · Monte Carlo {pr['simulation'][pid]:.1%}")
                        st.caption(f"First FG before first score (conditional): {pr['first_shot'][pid]:.1%} · First scoring opportunity: {pr['first_opportunity'][pid]:.1%} · MC sampling SE: {100*pr['hybrid_mc_se'][pid]:.2f} pp")
                    with st.expander('Phase 2 input evidence and assumptions'):
                        st.dataframe(pd.DataFrame(pr['inputs']['evidence']),hide_index=True,use_container_width=True)
                        st.json({'opening_tip_probabilities':pr['inputs']['opening_team'],'transitions':pr['transitions'],'no_FG_before_score_fraction':pr['no_field_goal_fraction'],'assumptions':pr['inputs']['assumptions']})
                    st.caption('All probabilities are research estimates, including unverified-lineup scenarios. No odds, EV or betting instruction is produced here. First-shot selection is separate from first-score conversion. Top five is a display limit; ties can extend beyond it. Monte Carlo SE is simulation noise, not full model uncertainty. This uses the sidebar exploratory blend; validation-selected calibration appears only in the held-out research report.')
                    st.download_button('Download Phase 2 research JSON',json.dumps(p2_saved,indent=2).encode(),'apex_phase2_research.json','application/json')
                elif p2_saved:st.info('Phase 2 inputs changed or verification expired. Run Phase 2 research simulation again.')
        with st.expander('V3 hybrid Monte Carlo · possession simulation'):
            sim_games={g['gameId']:g for g in games if g['gameId'] in result.get('model_bundles',{})}
            if sim_games:
                sim_gid=st.selectbox('Simulate matchup',list(sim_games),format_func=lambda gid:result['model_bundles'][gid]['baseline'][0]['Matchup'])
                sim_game=sim_games[sim_gid]
                sim_verified=all(confirmations[sim_gid].values())
                sim_key=json.dumps({'ranking':signature,'game':sim_gid,'config':mc_settings},sort_keys=True)
                if not sim_verified and not sim_game.get('research_only'):st.info('Confirm both starting fives before simulating a scheduled game. Manual and NBA verification remain distinct.')
                if st.button('Run hybrid possession simulation',disabled=not sim_verified and not sim_game.get('research_only')):
                    try:
                        if not sim_game.get('research_only'):
                            sim_current=next((g for g in core.fresh_schedule(day) if g['gameId']==sim_gid),None)
                            if not sim_current or not core.upcoming(sim_current) or sim_current['start_time']!=sim_game['start_time']:
                                raise ValueError('Game started or schedule changed. Reload the slate.')
                            current_sources=core.lineup_confirmation_sources(sim_current,choices[sim_gid],manual_confirmations[sim_gid],nba_entries.get(sim_gid,{}))
                            if current_sources!=confirmation_sources[sim_gid] or 'Unconfirmed' in current_sources.values():
                                raise ValueError('Starting-lineup verification expired or changed. Refresh and rerun rankings.')
                        with st.spinner('Simulating possessions until the first score…'):
                            simulated=simulation.simulate(hist,choices[sim_gid],day,mc_config)
                        st.session_state['hybrid_simulation']={'signature':sim_key,'report':simulated,'verification':confirmation_sources[sim_gid]}
                    except (ValueError,RuntimeError,KeyError) as exc:st.error(str(exc))
                sim_saved=st.session_state.get('hybrid_simulation')
                if sim_saved and sim_saved['signature']==sim_key:
                    sim_report=sim_saved['report']
                    st.dataframe(pd.DataFrame(simulation.prediction_rows(sim_report,choices[sim_gid])),hide_index=True,use_container_width=True)
                    st.write(f"Effective simulation weight: {sim_report['effective_hybrid_weight']:.0%} · unresolved trials: {sim_report['unresolved_trials']} / {mc_trials}")
                    if not sim_report['minimum_history_met']:st.warning('Fewer than ten earlier team games on at least one side: hybrid falls back to Baseline.')
                    if not any(r['Known opening outcomes'] for r in sim_report['inputs']['evidence']):st.warning('No known opening-shot outcomes for these players: make probabilities use the neutral prior.')
                    if sim_report['unresolved_fraction']>.01:st.warning('More than 1% of simulations reached the event cap. Review assumptions before interpreting results.')
                    st.write('Lineup verification: '+', '.join(t+': '+v for t,v in sim_saved['verification'].items()))
                    st.json({'opening_team_proxy':sim_report['inputs']['opening_team'],'transitions':sim_report['transitions'],'config':sim_report['config']})
                    st.download_button('Download hybrid simulation JSON',json.dumps(sim_saved,indent=2).encode(),'apex_hybrid_simulation.json','application/json')
                elif sim_saved:st.info('Simulation settings, matchup or ranking inputs changed. Run the simulation again.')
                st.caption('Hybrid combines the existing Baseline with simulated first-score frequencies. Free throws count. The opening-team input is a historical first-action proxy, not a verified jump-ball model. Later shot choices reuse opening-shot shares; foul shooters use conditional first-score shares. Turnovers, two-shot fouls, rebounds and free-throw accuracy are explicit assumptions. No substitutions, and-ones, technicals or full play design are modeled. Capped trials retain Baseline probability mass. Monte Carlo SE measures simulation noise only, not model uncertainty. Main rankings, odds and journal forecasts remain unchanged in this development preview.')
        with st.expander('Recent opening-shot role · prediction preview'):
            role_bundles=result.get('model_bundles',{})
            if role_bundles:
                role_gid=st.selectbox('Preview role inputs for matchup',list(role_bundles),format_func=lambda gid:role_bundles[gid]['baseline'][0]['Matchup'])
                role_rows=research.recent_role_preview(hist,choices[role_gid],day)
                st.dataframe(pd.DataFrame(role_rows),hide_index=True,use_container_width=True)
                st.caption('Experimental preview using your selected five. Each player’s last five recorded same-team starts within 60 days supply opening-shot evidence; at least three must have a known opening shooter. Unknown starts are excluded from the rate. Recent evidence is shrunk toward older, non-overlapping history with strength 10. These settings are unvalidated. Inactive inputs retain the Recent-form shot rate, although team normalization can still change their probability when a teammate is active.')
                st.caption('Team-first probability and conditional first-score history stay at Recent-form values. This preview does not replace live rankings, odds calculations or journal forecasts. Review lineup confirmations, injuries and sample holds in the main table. No extra API calls are made.')
                st.download_button('Download recent role inputs CSV',pd.DataFrame(role_rows).to_csv(index=False).encode(),'apex_recent_role_inputs.csv','text/csv')
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
                        sources=core.lineup_confirmation_sources(game,choices[gid],manual_confirmations[gid],nba_entries.get(gid,{}))
                        if sources!=confirmation_sources[gid]:raise ValueError('Lineup confirmation changed or expired; refresh and rerun rankings before saving.')
                        evidence={t:({'method':v,**nba_entries[gid][t]} if v=='NBA feed confirmed' else {'method':v}) for t,v in sources.items()}
                        inserted=research.save_forecast(game,rows,{t:v!='Unconfirmed' for t,v in sources.items()},updater.current_version(),research.fingerprint(hist),inj.get('time'),model_forecasts=bundle,lineup_evidence=evidence)
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
    st.caption('Unattempted games are loaded first, newest first. Failed games stay retryable after unattempted games, with fewer-attempted retries first. Rankings use only the 400 days before the game date. Historical sample counts can include last season; current-season starts are shown separately.')
    if st.button('Check saved history against season schedule'):
        st.session_state.pop('schedule_coverage',None)
        line=st.empty()
        try:
            with st.spinner('Comparing saved games with the season index…'):
                st.session_state['schedule_coverage']=research.check_season_coverage(hist,season_end,day,line.info)
        except (RuntimeError,ValueError,OSError,KeyError,TypeError) as exc:st.error(str(exc))
    coverage_report=st.session_state.get('schedule_coverage')
    if coverage_report and coverage_report['fingerprint']==research.fingerprint(hist) and coverage_report['season_end']==season_end and coverage_report['analysis_day']==day and coverage_report['checked_on']==datetime.now(ZoneInfo('America/New_York')).date().isoformat():
        st.markdown('**Saved history versus indexed completed games**')
        counts=coverage_report['counts']
        st.write(f"Indexed: {coverage_report['indexed_games']} · Usable: {counts['Saved valid']} · Missing: {counts['Missing']} · Invalid: {counts['Saved invalid']} · Schedule mismatch: {counts['Schedule mismatch']}")
        st.caption(f"Selected season only, from {coverage_report['window_start']} to before {coverage_report['end_exclusive']}. Completed games on or after today/the analysis date are excluded. Counts use the returned schedule index, which may be cached; they do not certify that the provider supplied every game.")
        for warning in coverage_report['schedule_warnings']:st.warning('Partial schedule coverage: '+warning)
        st.dataframe(pd.DataFrame(coverage_report['teams']),hide_index=True,use_container_width=True)
        if coverage_report['details']:
            st.dataframe(pd.DataFrame(coverage_report['details']),hide_index=True,use_container_width=True)
            st.download_button('Download schedule coverage CSV',pd.DataFrame(coverage_report['details']).to_csv(index=False).encode(),'apex_schedule_coverage.csv','text/csv')
        else:st.info('No indexed completed games fall in this season/date window.')
        st.caption('Use Import prior-season history for missing games, Data quality for invalid rows, and the research export to investigate schedule mismatches. Missing games can include prior failures or nonstarter first scorers excluded by the current model. This check does not import, repair or delete history.')
    elif coverage_report:st.info('History, season, analysis date or calendar day changed. Check schedule coverage again.')
    st.caption('Coverage checks use the public ESPN schedule index and may fetch team schedules. They do not call your paid odds or injury APIs.')
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
        if 'retry_attempted' in report:st.caption(f"This batch retried {report['retry_attempted']} previously attempted games. {report['never_attempted_remaining']} indexed missing games have not been attempted yet.")
        for warning in report['schedule_warnings']: st.warning(warning)
        if report['skipped']:
            st.warning('Some games could not be imported. Games with a nonstarter first scorer remain excluded by this model.')
            st.dataframe(pd.DataFrame(report['skipped']),hide_index=True,use_container_width=True)

with st.expander('Phase 2 empirical opening sequences'):
    st.write('Add explicit tip outcomes, typed shots, free throws, turnovers and rebounds from the first three minutes before the first substitution. This separate cache does not change your existing history.')
    st.caption(f'Saved sequence records: {len(phase2_sequences)}. Public ESPN requests run only when clicked; no paid API keys are used. Historical box-score starters do not establish pre-tip verification.')
    if st.button('Enrich next 20 opening sequences'):
        try:
            progress=st.empty()
            st.session_state['phase2_enrichment']=opening_data.enrich(hist,20,progress=progress.info)
            st.rerun()
        except (ValueError,OSError) as exc:st.error(str(exc))
    if st.session_state.get('phase2_enrichment'):st.json(st.session_state['phase2_enrichment'])

with st.expander('Opening-shot conversion · enrich saved history'):
    missing_results=sorted({r['game_id'] for r in hist if ((str(r.get('first_team_shot',''))=='1' and str(r.get('first_team_shot_made','')) not in ('0','1')) or r.get('opening_score_path','') not in ('free_throw_before_fg','opening_fg_made','opening_fg_missed')) and r.get('date','')<datetime.now(ZoneInfo('America/New_York')).date().isoformat()},reverse=True)
    st.caption('New imports record the opening field-goal result when explicit. Older missing results stay unknown. Enrichment also records whether scoring began before a field-goal attempt, on the opening make, or after the opening miss. Enrichment rechecks saved ESPN games and adds only missing shot outcomes; changed starters, dates or existing scoring facts block that game. A backup is created before writing. This uses public ESPN requests, not paid odds calls.')
    st.markdown('**Resume automatic game selection**')
    st.caption('Runs only when clicked. Unattempted games go first, newest first, then retries with fewer attempts. Each successful game is saved before the next request, with one backup per batch. Failed or unresolved games remain retryable. Stop other imports while this runs.')
    opening_batch_size=st.selectbox('Opening-data batch size',[10,20,50],index=1)
    if st.button('Enrich next batch of saved games'):
        try:
            progress=st.empty()
            with st.spinner('Enriching saved opening data… keep this window open.'):
                st.session_state['opening_enrichment']=research.enrich_opening_batch(opening_batch_size,progress.info)
            st.rerun()
        except (OSError,ValueError) as exc:st.error(str(exc))
    enrich_ids=st.multiselect('Saved games to enrich with opening-shot results',missing_results,max_selections=20)
    if st.button('Enrich selected opening-shot results',disabled=not enrich_ids):
        try:
            progress=st.empty()
            with st.spinner('Rechecking opening attempts…'):
                st.session_state['opening_enrichment']=research.enrich_opening_results(enrich_ids,progress.info)
            st.rerun()
        except (OSError,ValueError) as exc:st.error(str(exc))
    enrichment=st.session_state.get('opening_enrichment')
    if enrichment:
        st.write(f"Added {enrichment['added_results']} opening-shot outcomes across {enrichment['enriched_games']} games.")
        st.caption(f"Added scoring paths for {enrichment.get('added_paths',0)} games.")
        if 'remaining' in enrichment:
            st.caption(f"Batch attempted {enrichment['attempted']} games, including {enrichment['retry_attempted']} retries. {enrichment['remaining']} eligible games still need opening data; {enrichment['never_attempted_remaining']} have not been attempted by the batch queue.")
        if enrichment['backup']:st.caption('Backup: '+enrichment['backup'])
        if enrichment['errors']:st.dataframe(pd.DataFrame(enrichment['errors']),hide_index=True,use_container_width=True)

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
                for key in ('results','evaluation','model_comparison','lineup_scenario','validation_report','signal_comparison','research_export','recency_comparison'):st.session_state.pop(key,None)
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

with st.expander('Share research data · export for engine review'):
    st.write('Create a data-only ZIP containing your saved game history, quality issues, team coverage and engine version. It does not include API-key files, settings, odds or your forward journal. Preparing it makes no API calls and does not upload anything.')
    export_version=updater.current_version()
    export_signature=(research.fingerprint(hist),day,selected_model,export_version)
    if st.button('Prepare research export',disabled=not hist):
        with st.spinner('Packaging history and quality report…'):
            st.session_state['research_export']={'signature':export_signature,'data':research.research_export(hist,export_version,day,selected_model)}
    export=st.session_state.get('research_export')
    if export and export['signature']==export_signature:
        st.download_button('Download research ZIP',export['data'],f'apex_research_{day}.zip','application/zip')
        st.caption('Review the ZIP before sharing. Flagged rows remain included for diagnosis; your local history is unchanged. You can attach this ZIP in our chat when you want me to evaluate changes using your saved games.')
    elif export:st.info('History, date, model or version changed. Prepare a fresh research export.')
    elif not hist:st.info('Sync or import some history before preparing an export.')

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
            active=signals['active_selection']
            st.markdown('**Adaptive performance after enough selection history**')
            if active['games']:
                st.caption(f"{active['games']} identical games across {active['dates']} dates for every variant. {active['fallback_games']} fallback games are excluded from this section only; full-period results above still include them.")
                st.dataframe(pd.DataFrame(active['summary']),hide_index=True,use_container_width=True)
                st.dataframe(pd.DataFrame(active['comparison']),hide_index=True,use_container_width=True)
                st.caption('Differences are selector minus current blend on exactly the same games. Eligibility depends only on earlier sample size, not on the current result or whether the selector chose a different blend. A learned decision to retain the current blend is included.')
                st.dataframe(pd.DataFrame(active['choices']),hide_index=True,use_container_width=True)
                if active['dates']<30:st.warning('Fewer than 30 dates with enough selection history. Adaptive performance is still uncertain.')
                st.download_button('Download active adaptive summary CSV',pd.DataFrame(active['summary']).to_csv(index=False).encode(),'apex_active_adaptive_summary.csv','text/csv')
                st.download_button('Download active adaptive predictions CSV',pd.DataFrame(active['details']).to_csv(index=False).encode(),'apex_active_adaptive_predictions.csv','text/csv')
            else:st.info('No games yet had 100 earlier evaluated games available for selection. The adaptive results currently reflect fallback behavior; they do not test learned choices yet.')
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
    if st.button('Compare 30 / 90 / 180-day decay',disabled=selected_model=='baseline'):
        progress=st.empty()
        with st.spinner('Testing recency settings on the same historical games…'):
            st.session_state['recency_comparison']=research.compare_recency(hist,warmup,selected_model,progress.info)
    if selected_model=='baseline':st.caption('Select Recent form or Lineup context in the sidebar to test decay speed.')
    recency=st.session_state.get('recency_comparison')
    if recency and recency['fingerprint']==research.fingerprint(hist) and recency['min_training']==warmup and recency['model']==selected_model:
        st.markdown('**How quickly should old games lose weight?**')
        if recency['summary']:
            st.dataframe(pd.DataFrame(recency['summary']),hide_index=True,use_container_width=True)
            st.caption('Half-life is the number of days until a game carries half its original weight. Each experiment keeps the 400-day history window and 65/35 player-signal blend. Decay changes team rates, player rates and, for lineup context, both context evidence and its separate anchor. Faster decay also increases the relative influence of the unchanged priors.')
            st.dataframe(pd.DataFrame(recency['recent_comparisons']),hide_index=True,use_container_width=True)
            st.caption('Recent differences are candidate minus the current 90-day setting, using identical games. Approximate 95% intervals resample whole dates. This is an exploratory comparison, not a fitted or independently validated setting; no winner is applied to live rankings.')
            if recency['latest_dates']<30:st.warning('Fewer than 30 recent evaluation dates. Recency comparisons can be unstable.')
            st.download_button('Download recency comparison CSV',pd.DataFrame(recency['summary']).to_csv(index=False).encode(),'apex_recency_comparison.csv','text/csv')
            st.download_button('Download recency predictions CSV',pd.DataFrame(recency['details']).to_csv(index=False).encode(),'apex_recency_predictions.csv','text/csv')
        else:st.info('Not enough eligible history to compare decay settings.')
    elif recency:st.info('History, model or training minimum changed. Run the recency comparison again.')
    if st.button('Compare all five scoring models'):
        progress=st.empty()
        with st.spinner('Comparing live models and challengers on identical games…'):
            st.session_state['scoring_scorecard']=research.scoring_model_scorecard(hist,warmup,progress.info)
    scorecard=st.session_state.get('scoring_scorecard')
    if scorecard and scorecard['fingerprint']==research.fingerprint(hist) and scorecard['min_training']==warmup:
        st.markdown('**Scoring model scorecard**')
        st.caption('Baseline is the current default. Recent and Lineup are existing alternatives; Conversion and Post-miss are experimental challengers. This comparison runs all five regardless of the sidebar model.')
        st.dataframe(pd.DataFrame(scorecard['coverage']),hide_index=True,use_container_width=True)
        if scorecard['summary']:
            scorecard_period=st.selectbox('Scorecard evaluation period',['All evaluated dates','Newest quarter of dates','Challenger-active games'])
            selected_summary=[r for r in scorecard['summary'] if r['Period']==scorecard_period]
            if selected_summary:
                st.dataframe(pd.DataFrame(selected_summary),hide_index=True,use_container_width=True)
                st.dataframe(pd.DataFrame([r for r in scorecard['paired'] if r['Period']==scorecard_period]),hide_index=True,use_container_width=True)
                st.markdown('**What these results mean**')
                readings=research.scorecard_readings(scorecard,scorecard_period)
                st.dataframe(pd.DataFrame(readings)[['Model','Metric','Sample result','Evidence reading','Date coverage']],hide_index=True,use_container_width=True)
                st.caption('A better sample average can still have an uncertain difference. An interval favoring a model is exploratory evidence, not a probability that it will win or proof of future accuracy. Intervals are not adjusted for testing multiple models and metrics. Thirty dates is a display warning threshold, not a validation cutoff.')
                st.info('Next step: compare the newest dates with the full sample, enrich missing opening data, and collect pregame forecasts in the forward journal. Judge each metric separately; better probability errors do not necessarily mean more top picks hit.')
                st.download_button('Download scorecard interpretation CSV',pd.DataFrame(readings).to_csv(index=False).encode(),'apex_scorecard_interpretation.csv','text/csv')
                with st.expander('Monthly consistency · does the advantage hold?'):
                    consistency=research.scorecard_consistency(scorecard,scorecard_period)
                    st.dataframe(pd.DataFrame(consistency['summary']),hide_index=True,use_container_width=True)
                    st.dataframe(pd.DataFrame(consistency['monthly']),hide_index=True,use_container_width=True)
                    st.caption('Monthly averages compare identical games with Baseline. Better/worse month counts weight months equally; overall and excluded-month differences weight games equally. Removing a month only rescores the remaining saved predictions; it does not retrain the models. Partial and sparse months remain included with game/date counts. These descriptive checks are not confidence intervals or independent validation, and stable direction can also mean consistently worse performance.')
                    st.download_button('Download monthly consistency CSV',pd.DataFrame(consistency['monthly']).to_csv(index=False).encode(),'apex_monthly_consistency.csv','text/csv')
                    st.download_button('Download consistency summary CSV',pd.DataFrame(consistency['summary']).to_csv(index=False).encode(),'apex_consistency_summary.csv','text/csv')
                if selected_summary[0]['Dates']<30:st.warning('Fewer than 30 dates in this comparison. Estimates and intervals can be unstable.')
            else:st.info('No games satisfy this period yet. Enrich earlier opening-shot and sequence data, then rerun the scorecard.')
            st.caption('Challenger-active means at least one known earlier conversion attempt among the selected players and at least ten known sequence games for each team. It does not establish adequate samples for every player or model reliability. All five models use the same selected games in each period; other periods retain fallback games.')
            st.caption('Lower log loss and Brier mean better probability estimates on this sample. Higher hit rates mean more correct selections, with fractional credit for ties. Differences and approximate 95% date-bootstrap intervals compare each model with Baseline. The newest quarter is a diagnostic, not an untouched test set. Repeated comparisons, date dependence and historical lineup-selection bias remain. No model is promoted automatically and these results do not establish profit.')
            st.download_button('Download scoring scorecard CSV',pd.DataFrame(scorecard['summary']).to_csv(index=False).encode(),'apex_scoring_scorecard.csv','text/csv')
            st.download_button('Download scorecard comparisons CSV',pd.DataFrame(scorecard['paired']).to_csv(index=False).encode(),'apex_scorecard_comparisons.csv','text/csv')
            st.download_button('Download scorecard predictions CSV',pd.DataFrame(scorecard['details']).to_csv(index=False).encode(),'apex_scorecard_predictions.csv','text/csv')
        else:st.info('Not enough eligible history to compare the scoring models. Import more history or review the training minimum.')
        st.caption(f"Invalid historical games excluded: {scorecard['excluded_games']}.")
    elif scorecard:st.info('History or training minimum changed. Compare all five scoring models again.')
    st.markdown('**Phase 2 chronological selection and final test**')
    p2_start=st.date_input('Phase 2 final-test start',datetime(2025,12,1),key='p2_start').isoformat()
    p2_end=st.date_input('Phase 2 final-test end',datetime(2025,12,21),key='p2_end').isoformat()
    st.caption('Weights and calibration are selected only from out-of-sample forecasts before the test start. At least 100 validation games across 20 dates are required to fit temperature. Repeatedly changing the test window turns it into development data; reserve another untouched period. Missing archived pre-tip confirmations are unverified.')
    p2_archive={}
    if (eng.DATA/'forward_journal.sqlite3').exists():p2_archive={r['snapshot']['game_id']:r['snapshot'] for r in research.journal_records()}
    p2_eval_key=json.dumps({'archive':research.fingerprint(p2_archive),'history':research.fingerprint(hist),'sequences':research.fingerprint(phase2_sequences),'start':p2_start,'end':p2_end,'config':mc_settings,'warmup':warmup},sort_keys=True)
    if st.button('Run Phase 2 held-out comparison'):
        st.session_state.pop('phase2_evaluation',None)
        try:
            progress=st.empty();archive=p2_archive
            with st.spinner('Selecting on earlier validation dates, then evaluating the final test…'):
                p2_evaluation=phase2.evaluate_holdout(hist,phase2_sequences,p2_start,p2_end,mc_config,warmup,archive,progress.info)
            st.session_state['phase2_evaluation']={'signature':p2_eval_key,'report':p2_evaluation}
        except (ValueError,KeyError,OSError) as exc:st.error(str(exc))
    p2_eval=st.session_state.get('phase2_evaluation')
    if p2_eval and p2_eval['signature']==p2_eval_key:
        pr=p2_eval['report'];st.write(f"Held-out games: {pr['evaluated_games']} · selected weight: {pr['selection']['weight']:.0%} · temperature: {pr['selection']['temperature']}")
        st.dataframe(pd.DataFrame(pr['summary']),hide_index=True,use_container_width=True)
        with st.expander('Phase 2 calibration, uncertainty and training audit'):
            st.dataframe(pd.DataFrame(pr['calibration']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(pr['comparisons']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(pr['diagnostics']),hide_index=True,use_container_width=True)
            st.json(pr['first_shot'])
        st.caption('Verified and unverified cohorts are separate. Zero verified games means no verified-lineup performance claim is possible. Uniform and smoothed historical frequency are reference models. Calibration ECE is descriptive and bin-dependent. No automatic promotion or betting edge claim.')
        st.download_button('Download Phase 2 held-out metrics',pd.DataFrame(pr['details']).to_csv(index=False).encode(),'apex_phase2_holdout.csv','text/csv')
    elif p2_eval:st.info('Phase 2 data, dates or settings changed. Run Phase 2 held-out comparison again.')
    if st.button('Backtest V3 hybrid vs baseline'):
        try:
            progress=st.empty()
            with st.spinner('Running chronological hybrid simulations…'):
                st.session_state['hybrid_backtest']=simulation.backtest(hist,warmup,mc_config,progress.info)
        except ValueError as exc:st.error(str(exc))
    hybrid_test=st.session_state.get('hybrid_backtest')
    if hybrid_test and hybrid_test['fingerprint']==research.fingerprint(hist) and hybrid_test['config']==mc_settings and hybrid_test['min_training']==warmup:
        st.markdown('**V3 leakage-free historical comparison**')
        if hybrid_test['summary']:
            st.dataframe(pd.DataFrame(hybrid_test['summary']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(hybrid_test['comparisons']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(hybrid_test['diagnostics']),hide_index=True,use_container_width=True)
            st.download_button('Download hybrid backtest CSV',pd.DataFrame(hybrid_test['details']).to_csv(index=False).encode(),'apex_hybrid_backtest.csv','text/csv')
            st.download_button('Download hybrid training audit CSV',pd.DataFrame(hybrid_test['diagnostics']).to_csv(index=False).encode(),'apex_hybrid_training_audit.csv','text/csv')
        else:st.info('Not enough valid saved history for the hybrid backtest. Import history or review the training minimum.')
        st.caption(f"Excluded invalid games: {len(hybrid_test['excluded'])}. Both models use identical games and observed historical starting fives. Whole dates are withheld from training until evaluated; only the preceding 400 days are used. Settings stay fixed throughout a run. Newest-quarter and active-hybrid views are diagnostics, not untouched holdouts. Repeated setting changes can overfit these results; historical rosters/lineup announcement timing and nonstarter-scorer exclusion remain limitations. No automatic model promotion.")
    elif hybrid_test:st.info('History, training minimum or simulation settings changed. Backtest V3 hybrid again.')
    if st.button('Test recent opening-shot roles'):
        with st.spinner('Testing recent role inputs against Recent form…'):
            st.session_state['recent_role_comparison']=research.compare_recent_role(hist,warmup)
    role_report=st.session_state.get('recent_role_comparison')
    if role_report and role_report['fingerprint']==research.fingerprint(hist) and role_report['min_training']==warmup:
        st.markdown('**Recent opening-shot role validation**')
        if role_report['summary']:
            st.dataframe(pd.DataFrame(role_report['summary']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(role_report['comparisons']),hide_index=True,use_container_width=True)
            st.download_button('Download recent role backtest CSV',pd.DataFrame(role_report['details']).to_csv(index=False).encode(),'apex_recent_role_backtest.csv','text/csv')
        else:st.info('Not enough history to test recent opening-shot roles.')
        st.caption('Identical evaluation games; only earlier dates train each forecast. This includes fallback games. Five starts, 60 days, three observations and strength 10 are experimental settings. Newest dates and date-bootstrap intervals are diagnostics, not independent proof of accuracy; historical starter selection and repeated comparisons remain limitations.')
    elif role_report:st.info('History or training minimum changed. Test recent opening-shot roles again.')
    if st.button('Test post-miss scoring model'):
        with st.spinner('Comparing opening makes and post-miss recovery…'):
            st.session_state['post_miss_comparison']=research.compare_post_miss(hist,warmup)
    sequence=st.session_state.get('post_miss_comparison')
    if sequence and sequence['fingerprint']==research.fingerprint(hist) and sequence['min_training']==warmup:
        st.markdown('**Who scores after the opening attempt misses?**')
        path_labels={'free_throw_before_fg':'Free throw before a field-goal attempt','opening_fg_made':'Opening field-goal attempt made','opening_fg_missed':'First score after opening miss'}
        st.dataframe(pd.DataFrame([{'Opening scoring path':path_labels[path],'Recorded games':count} for path,count in sequence['path_counts'].items()]),hide_index=True,use_container_width=True)
        st.caption('The challenger separates free throws scored before any field-goal attempt, a made opening attempt, and eventual first scoring after an opening miss. Post-miss outcomes include later free throws. It learns recovery from recorded outcomes; it does not explicitly simulate rebounds, turnovers or each later possession.')
        st.caption('Both teams need ten earlier games with known scoring paths before this model activates; otherwise it reproduces Opening conversion. Evidence uses 90-day decay, a 400-day window and same-team player records. The early-free-throw prior is 1 event in 20, opening-team prior is 50/50 with strength 20, and recovery rates use strength-10 conversion-model anchors trained on games outside that recovery path. These are experimental assumptions, not validated league averages.')
        st.write(f"Games after sequence minimum: {sequence['eligible_games']}")
        if not sequence['eligible_games']:st.info('No games reached the sequence-data minimum. Enrich earlier saved games before assessing this challenger.')
        if sequence['summary']:
            st.dataframe(pd.DataFrame(sequence['summary']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(sequence['comparisons']),hide_index=True,use_container_width=True)
            st.caption('All comparisons use identical games. The after-minimum section separates active modeling from fallback. Differences are challenger minus Opening conversion; lower probability error is better. Date-bootstrap intervals do not remove selection bias, small-sample uncertainty or repeated-testing risk. Live defaults are unchanged; historical observed starters and excluded nonstarter scorers remain limitations.')
            st.download_button('Download post-miss model summary CSV',pd.DataFrame(sequence['summary']).to_csv(index=False).encode(),'apex_post_miss_summary.csv','text/csv')
            st.download_button('Download post-miss model predictions CSV',pd.DataFrame(sequence['details']).to_csv(index=False).encode(),'apex_post_miss_predictions.csv','text/csv')
    elif sequence:st.info('History or training minimum changed. Run the post-miss model test again.')
    if st.button('Test opening-shot conversion model'):
        with st.spinner('Comparing recent form with the conversion challenger…'):
            st.session_state['conversion_comparison']=research.compare_opening_conversion(hist,warmup)
    conversion=st.session_state.get('conversion_comparison')
    if conversion and conversion['fingerprint']==research.fingerprint(hist) and conversion['min_training']==warmup:
        st.markdown('**Opening-shot frequency × conversion**')
        st.write(f"Known opening-attempt outcomes in valid saved history: {conversion['known_attempts']} · Made: {conversion['known_makes']}.")
        st.caption('This compares against Recent form, regardless of the sidebar model. It multiplies opening-shot frequency by a player conversion factor, retaining the 65/35 blend with first-score history. Conversion uses a neutral prior of five makes and five misses, 90-day decay and a 400-day earlier-date window. Missing outcomes are not misses. With no conversion data, predictions reproduce Recent form.')
        st.caption('The prior and blend are experimental choices. This can change player order; it is not a full possession simulation. Free throws remain represented by the first-score signal. Shot type, rebounds, turnovers and later attempts are not explicitly simulated. Historical lineup and nonstarter-scorer selection bias remain.')
        if conversion['summary']:
            st.dataframe(pd.DataFrame(conversion['summary']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(conversion['comparisons']),hide_index=True,use_container_width=True)
            st.caption('Differences are challenger minus Recent form on identical games. Lower log loss/Brier and higher hit-rate differences are better. Approximate 95% date-bootstrap intervals and the newest-quarter diagnostic do not establish future accuracy or profit. Live defaults and journal forecasts are unchanged.')
            if not any(r['Games with conversion training data'] for r in conversion['summary']):st.info('No evaluated games had conversion training data. Enrich earlier saved games before treating this as a test of conversion skill.')
            st.download_button('Download opening-shot model summary CSV',pd.DataFrame(conversion['summary']).to_csv(index=False).encode(),'apex_conversion_summary.csv','text/csv')
            st.download_button('Download opening-shot model predictions CSV',pd.DataFrame(conversion['details']).to_csv(index=False).encode(),'apex_conversion_predictions.csv','text/csv')
        else:st.info('Not enough eligible history to evaluate the opening-shot model.')
    elif conversion:st.info('History or training minimum changed. Run the opening-shot conversion test again.')
    if st.button('Test starting-lineup projections'):
        with st.spinner('Replaying starting-five forecasts using earlier games…'):
            st.session_state['lineup_validation']=research.evaluate_starting_fives(hist,day)
    lineup_validation=st.session_state.get('lineup_validation')
    if lineup_validation and lineup_validation['fingerprint']==research.fingerprint(hist) and lineup_validation['as_of']==day:
        st.markdown('**Which starter projection matches the actual five?**')
        if lineup_validation['summary']:
            st.dataframe(pd.DataFrame(lineup_validation['summary']),hide_index=True,use_container_width=True)
            st.caption('Both methods predict the same team lineups using five earlier recorded team games within 60 days, with the latest at most 30 days old. Last recorded five copies the most recent game. Recent start frequency chooses the five most frequent starters; ties favor last-game starters, then latest start date, then player ID. No same-day or later information selects players.')
            st.caption('Exact five measures complete lineup matches. Starter slots matched measures the share of five positions correctly filled. First scorer covered measures whether the actual scorer was among the projected five, only for eligible winning-team lineups; it is not top-pick accuracy. A game can contribute one or two eligible team lineups.')
            st.caption('This tests history-only projections. Historical pregame rosters, injuries and announcements are unavailable, so no current roster or hindsight actual-lineup filter is applied. Missing games and exclusion of nonstarter first scorers bias coverage. The newest quarter is descriptive, not an untouched test set. Neither method is automatically promoted to live projections.')
            if lineup_validation['latest_dates']<30:st.warning('Fewer than 30 recent lineup-evaluation dates. Differences may be unstable.')
            st.download_button('Download lineup projection summary CSV',pd.DataFrame(lineup_validation['summary']).to_csv(index=False).encode(),'apex_lineup_projection_summary.csv','text/csv')
            st.download_button('Download lineup projection details CSV',pd.DataFrame(lineup_validation['details']).to_csv(index=False).encode(),'apex_lineup_projection_details.csv','text/csv')
        else:st.info('No eligible lineup tests yet. Each team needs five earlier recorded games within 60 days and a latest game within 30 days.')
        st.caption(f"Team lineups skipped for insufficient or stale history: {lineup_validation['skipped_team_lineups']}. Invalid historical games excluded: {lineup_validation['excluded_games']}.")
    elif lineup_validation:st.info('History or analysis date changed. Run the starting-lineup projection test again.')
    if st.button('Test probability calibration'):
        progress=st.empty()
        with st.spinner('Testing probability adjustments using earlier dates…'):
            st.session_state['temperature_comparison']=research.compare_temperature(hist,warmup,selected_model,progress.info)
    temperature_report=st.session_state.get('temperature_comparison')
    if temperature_report and temperature_report['fingerprint']==research.fingerprint(hist) and temperature_report['min_training']==warmup and temperature_report['model']==selected_model:
        st.markdown('**Are the probabilities too confident or too flat?**')
        if temperature_report['summary']:
            st.dataframe(pd.DataFrame(temperature_report['summary']),hide_index=True,use_container_width=True)
            st.caption('Unchanged uses temperature 1; softer uses 1.25; sharper uses 0.8. Every forecast still sums to 100%. These transformations preserve player order: they test probability quality, not a new top-player selection strategy. Tiny numerical ties can affect fractional tie credit.')
            st.caption('Earlier-date adjustment chooses the lowest earlier log loss from the three fixed options. It needs at least 100 earlier evaluated games across 30 distinct dates within 400 days; until then it keeps probabilities unchanged. All games on one date use the same decision before that date’s results. Numerical selection ties prefer unchanged probabilities.')
            st.write(f"Games after selection warmup: {temperature_report['learned_games']} across {temperature_report['learned_dates']} dates.")
            if not temperature_report['learned_games']:st.info('The selector has not reached its learning minimum. Its results currently reflect unchanged probabilities, not learned adjustments.')
            elif temperature_report['learned_dates']<30:st.warning('Fewer than 30 evaluation dates after selection warmup. Adjusted performance remains uncertain.')
            st.dataframe(pd.DataFrame(temperature_report['comparisons']),hide_index=True,use_container_width=True)
            st.caption('Compare log loss and Brier: lower is better. Differences are candidate minus unchanged on identical games. Approximate 95% intervals resample whole dates but do not retrain the selector. Repeated experiments, dependence across dates and historical lineup-selection bias limit conclusions. The newest quarter is a diagnostic, not an untouched test set. These are calibration candidates, not proof of calibrated probabilities. Live rankings and saved forecasts are unchanged.')
            st.download_button('Download probability calibration summary CSV',pd.DataFrame(temperature_report['summary']).to_csv(index=False).encode(),'apex_temperature_summary.csv','text/csv')
            st.download_button('Download probability calibration predictions CSV',pd.DataFrame(temperature_report['details']).to_csv(index=False).encode(),'apex_temperature_predictions.csv','text/csv')
            st.download_button('Download probability adjustment decisions CSV',pd.DataFrame(temperature_report['decisions']).to_csv(index=False).encode(),'apex_temperature_decisions.csv','text/csv')
        else:st.info('Not enough eligible history to test probability calibration.')
    elif temperature_report:st.info('History, model or training minimum changed. Run the probability calibration test again.')
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
            st.markdown('**Does the model beat equal chances?**')
            st.caption('The reference gives each of the ten starters a 10% chance: 10% top-one and 30% top-three credit. This is a simple reference, not bookmaker odds or a strong competing model. Log loss and Brier measure probability error; lower is better. Hit-rate differences are percentage points; higher is better.')
            evidence=validation.get('equal_benchmark_evidence',[])
            if evidence:
                st.dataframe(pd.DataFrame(evidence),hide_index=True,use_container_width=True)
                st.download_button('Download equal-chance evidence CSV',pd.DataFrame(evidence).to_csv(index=False).encode(),'apex_equal_chance_evidence.csv','text/csv')
            else:st.info('Run full model validation again to generate the equal-chance evidence report.')
            st.caption('Read each metric separately. Approximate 95% intervals resample whole dates using the same games for both forecasts. One date cannot produce an interval; few dates can produce unstable or misleadingly narrow intervals. Repeated comparisons, development on these data and dependence across dates limit the conclusions. Historical observed starters and the exclusion of nonstarter first scorers also limit these results. An interval favoring the model does not establish future accuracy, calibration or profit. No model or live ranking is changed by this report.')
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
                st.markdown('**Saved predictions versus equal chances**')
                if paired_forward['equal_benchmark_evidence']:
                    st.dataframe(pd.DataFrame(paired_forward['equal_benchmark_evidence']),hide_index=True,use_container_width=True)
                    st.download_button('Download forward equal-chance evidence CSV',pd.DataFrame(paired_forward['equal_benchmark_evidence']).to_csv(index=False).encode(),'apex_forward_equal_chance_evidence.csv','text/csv')
                    st.caption('The reference assigns 10% to each of the same ten saved players. If someone outside those ten scores first, both forecasts miss: reference top-one/top-three credit is zero and reference Brier is 1.1. Both log losses are infinite, so their difference and interval are undefined for the entire sample; those games stay in Brier and hit-rate comparisons. No winner is dropped to obtain a finite log-loss result.')
                    st.caption('Differences use the same settled saved games and frozen probabilities, with approximate 95% intervals resampling whole dates. Lower error is better; higher hit-rate percentage-point differences are better. One date has no interval; few dates can give unstable or deceptively narrow intervals. Only saved games are represented. Repeated comparisons, dependence across dates and mixed software versions limit interpretation. These results do not establish calibration or profit and do not change the live model.')
                else:st.info('Equal-chance evidence will appear after three-model saved forecasts have completed outcomes.')
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
