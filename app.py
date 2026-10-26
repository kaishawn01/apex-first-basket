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
            games=core.fresh_schedule(day)
            roster_map={}; errors=[]
            for team in sorted({g[s]['teamTricode'] for g in games for s in ('awayTeam','homeTeam')}):
                try: roster_map[team]=core.roster(team)
                except (RuntimeError,KeyError,ValueError) as exc:
                    errors.append(f'{team}: roster unavailable; only historical starters are available.')
                    roster_map[team]=[{'player_id':r['player_id'],'player':r['player']} for r in eng.recent_starters([r for r in hist if r['date']<day],team)]
            st.session_state['slate']={'day':day,'games':games,'rosters':roster_map,'loaded':datetime.now().isoformat(timespec='seconds'),'errors':errors}
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
if not slate or slate['day']!=day:
    st.markdown('### Get started')
    st.write('Sync your history, then load the slate. Projected lineups will appear below automatically.')
else:
    for warning in slate['errors']: st.warning(warning)
    games=[g for g in slate['games'] if core.upcoming(g)]
    st.caption('Slate loaded: '+slate['loaded']+' • Games that have started are excluded.')
    if not games: st.info('No unstarted regular-season games for this date.')
    choices={}; confirmations={}
    for g in games:
        gid=g['gameId']; away,home=(g[s]['teamTricode'] for s in ('awayTeam','homeTeam'))
        start=datetime.fromisoformat(g['start_time'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
        with st.expander(f'{away} @ {home} · {start:%I:%M %p} ET',expanded=True):
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
                    confirmed=st.checkbox(f'I verified {team}’s announced starters for this game',key=f'confirm:{day}:{gid}:{team}:{st.session_state.get("revision",0)}:{",".join(sorted(selected))}',disabled=len(selected)!=5)
                    confirmations[gid][team]=confirmed and len(selected)==5
                    st.caption('USER CONFIRMED' if confirmations[gid][team] else 'PROJECTED / UNCONFIRMED')
    st.markdown('### Market & rankings')
    st.caption('Refresh odds shortly before running rankings. Prices expire after 10 minutes in this dashboard.')
    if st.button('Fetch FanDuel first-basket odds',disabled=not games):
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
    st.caption(f'{len(prices)} current player prices available. Rankings can run without prices; EV stays blank.')
    signature=json.dumps({'day':day,'choices':choices,'confirmed':confirmations,'odds_time':prices_state.get('fetched') if prices else None,'injury_time':inj.get('time'),'history':research.fingerprint(hist)},sort_keys=True)
    if st.button('3 · Run rankings',type='primary',disabled=not games):
        st.session_state.pop('results',None)
        try:
            fresh={g['gameId']:g for g in core.fresh_schedule(day)}
            rows=[]
            for g in games:
                current=fresh.get(g['gameId'])
                if not current or not core.upcoming(current):
                    st.warning(f"{g['gameId']}: started or no longer scheduled; skipped."); continue
                rows.extend(core.rank_game(hist,current,choices[g['gameId']],confirmations[g['gameId']],prices,reports))
            st.session_state['results']={'rows':rows,'signature':signature,'time':datetime.now().isoformat(timespec='seconds')}
        except (RuntimeError,ValueError,KeyError) as exc:
            st.error(str(exc) if isinstance(exc,(RuntimeError,ValueError)) else 'Unexpected data response. Reload slate.')
    result=st.session_state.get('results')
    if result and result['signature']==signature:
        st.caption('Rankings generated: '+result['time']+' • Model EV uses uncalibrated estimates, not proven value.')
        frame=pd.DataFrame(result['rows'])
        st.dataframe(frame,hide_index=True,use_container_width=True)
        st.download_button('Download rankings CSV',frame.to_csv(index=False).encode('utf-8'),f'apex_rankings_{day}.csv','text/csv')
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
    elif hist:
        st.success('All saved games passed starter-count, ID, date, opponent, and scoring-consistency checks.')
        st.caption(f"History: {min(r['date'] for r in valid)} through {max(r['date'] for r in valid)}")
    else: st.info('Sync or import history to see coverage.')
    active=research.history_window(valid,day)
    coverage=[]
    for team in sorted(eng.TEAMS):
        rows=[r for r in active if r['team']==team]
        coverage.append({'Team':team,'Games in 400-day window':len({r['game_id'] for r in rows}),'Latest game':max((r['date'] for r in rows),default='None')})
    st.dataframe(pd.DataFrame(coverage),hide_index=True,use_container_width=True)

with st.expander('Backtest lab · test the model before trusting it'):
    st.write('Walk-forward testing predicts each game using earlier dates only. The 400-day window matches dashboard rankings. Same-day results never enter training.')
    warmup=st.selectbox('Minimum training games before evaluation',[30,100,250],index=1)
    if st.button('Run walk-forward evaluation'):
        with st.spinner('Evaluating historical games…'):
            st.session_state['evaluation']=research.evaluate(hist,warmup)
    evaluation=st.session_state.get('evaluation')
    if evaluation and evaluation['fingerprint']==research.fingerprint(hist) and evaluation['min_training']==warmup:
        m=evaluation['metrics'];n=m['Evaluated games']
        if not n: st.info('Not enough eligible dates after the training period. Import more history or lower the minimum training size.')
        else:
            st.caption(f'{n} games evaluated. Lower log loss and Brier score are better. Top-1 credit is split equally when model probabilities tie.')
            compare=pd.DataFrame([{'Model':'APEX',**m},{'Model':'Equal 10-player baseline','Evaluated games':n,'Top-1 hit %':10.0,'Log loss':2.302585093,'Brier':0.9}])
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
