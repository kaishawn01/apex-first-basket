"""Mobile research controls; no automatic network activity during rendering."""
import json
from pathlib import Path
from datetime import date,timedelta
import pandas as pd
import streamlit as st
import first_basket_engine as eng,phase4_data as data,phase4_forward as forward

@st.cache_data(show_spinner=False,max_entries=2)
def loaded(root,stamp):
    h,s,r=data.dataset(Path(root));coverage=data.coverage(Path(root));return h,s,r,coverage

def render(existing_history,injury_key=''):
    root=eng.DATA/'phase4';db=root/'history.sqlite3';journal_path=root/'forward.sqlite3'
    with st.expander('Phase 4 · historical coverage and forward validation'):
        st.caption('V2.44 remains the production default. Manual research collection only: no unattended monitoring is configured. Keep this computer/server running while a job is active.')
        h=s=r=coverage=None
        if db.exists():
            try:h,s,r,coverage=loaded(str(root),db.stat().st_mtime_ns)
            except (ValueError,OSError) as e:st.error('Phase 4 data unavailable: '+str(e))
        if coverage:
            st.write(f"Stored games: {coverage['games']} · usable opening sequences: {coverage['usable_opening_sequences']} · explicit jump balls: {coverage['explicit_tips']}")
            st.dataframe(pd.DataFrame([{'Season ending':year,'Games':n} for year,n in coverage['seasons'].items()]),hide_index=True,use_container_width=True)
            st.write('First-score outcome quality: '+json.dumps(coverage['outcomes']))
            with st.expander('Collection failures and missing-data diagnostics'):st.json({'warnings':coverage['warnings'],'failures':coverage['failures'],'last_collection':coverage['last_collection']})
        else:st.info('No separate Phase 4 dataset yet. Historical collection does not overwrite your existing CSV.')
        begin=st.date_input('Phase 4 collection start',date(2023,10,24),key='p4_history_start')
        end=st.date_input('Phase 4 collection end',date(2023,11,7),key='p4_history_end')
        if st.button('Start Phase 4 historical batch · up to 20 games'):
            try:
                if begin>end or (end-begin).days>45:raise ValueError('Choose a valid period up to 46 days')
                st.info(data.start_job('Historical collection',lambda:data.collect(begin.isoformat(),end.isoformat(),root,limit=20),root))
            except ValueError as e:st.error(str(e))
        st.json(data.job_status(root))
        st.button('Refresh Phase 4 job status')
        # Prefer the separate audited dataset; never mutate the old history.
        research_history=h if h else existing_history;sequences=s or {};records=r or {}
        st.caption('Prospective forecasts use the separate Phase 4 dataset when available; otherwise existing history. Snapshot warnings show missing current starters/injuries. API credentials stay in memory or existing settings; they are never written into journal evidence.')
        if st.button('Capture current pre-tip lineup evidence'):
            try:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
                st.info(data.start_job('Pre-tip snapshots',lambda:forward.collect_snapshots(today,research_history,forward.Journal(journal_path),injury_key),root))
            except ValueError as e:st.error(str(e))
        if st.button('Save eligible Phase 4 forward forecasts'):
            def save():
                j=forward.Journal(journal_path);saved=0;errors=[]
                for snap in j.rows('snapshot'):
                    if snap!=j.latest_snapshot(snap['payload']['game']['gameId']):continue
                    try:saved+=int(forward.save_prediction(j,snap,research_history,sequences,records))
                    except (ValueError,RuntimeError) as e:errors.append({'game':snap['payload']['game']['gameId'],'reason':str(e)})
                return {'saved':saved,'errors':errors}
            try:st.info(data.start_job('Prospective forecasts',save,root))
            except ValueError as e:st.error(str(e))
        if st.button('Grade completed Phase 4 forecasts'):
            try:st.info(data.start_job('Prospective grading',lambda:forward.refresh_results(forward.Journal(journal_path)),root))
            except ValueError as e:st.error(str(e))
        if journal_path.exists():
            try:
                j=forward.Journal(journal_path);snaps=j.rows('snapshot');preds=j.rows('prediction');report=forward.evaluation(j)
                official=sum(x['payload']['readiness']['provider_verified'] for x in snaps)
                st.write(f"Archived pre-tip snapshots: {len(snaps)} · with both provider-confirmed fives: {official} · forward forecasts: {len(preds)} · graded: {report['graded_games']}")
                if snaps:
                    st.dataframe(pd.DataFrame([{'Game':x['payload']['game']['gameId'],'Retrieved UTC':x['created_at'],'Statuses':json.dumps(x['payload']['statuses']),'Provider failures':len(x['payload']['failures'])} for x in snaps[-30:]]),hide_index=True,use_container_width=True)
                    with st.expander('Latest original snapshot and change history'):st.json(snaps[-1])
                if preds:
                    selected=st.selectbox('Saved Phase 4 game',[p['key'] for p in preds]);p=next(p['payload'] for p in preds if p['key']==selected)
                    model=st.selectbox('Saved Phase 4 research model',list(p['forecasts']))
                    probs=p['forecasts'][model];names={x['player_id']:x['player'] for ps in p['snapshot']['lineups'].values() for x in ps}
                    st.warning('Archived research forecast — not a current betting recommendation. '+p['warning'])
                    st.caption(f"Saved {p['generated_at']} · version {p['model_version']} · {p['trials']:,} trials · seed {p['seed']} · Other {probs['OTHER']:.2%}")
                    for rank,pid in enumerate(sorted(names,key=lambda pid:-probs[pid])[:5],1):
                        st.markdown(f'**{rank}. {names[pid]}**')
                        st.write(f"First score {probs[pid]:.1%} · first-shot proxy {p['first_shot_proxy'][pid]:.1%} · Baseline {p['forecasts']['Baseline'][pid]:.1%} · MC {p['forecasts']['Pure Monte Carlo'][pid]:.1%}")
                    with st.expander('Saved model assumptions and evidence'):st.json(p)
                if report['graded_games']:
                    st.dataframe(pd.DataFrame(report['summary']),hide_index=True,use_container_width=True)
                    bins=pd.DataFrame([x for x in report['calibration'] if x['Cohort']=='All' and x['Model']=='Pure Monte Carlo'])
                    if not bins.empty:st.line_chart(bins.set_index('Band')[['Predicted %','Observed %']])
                    st.caption('Calibration bins are descriptive; small prospective samples do not validate an edge.')
                    st.json(report['comparisons'])
                    if report['strata']:st.dataframe(pd.DataFrame(report['strata']),hide_index=True,use_container_width=True)
                else:st.info('No eligible prospective results yet. Historical predictions are never backfilled as live forecasts.')
                st.download_button('Download Phase 4 journal evidence',json.dumps(j.rows(),indent=2).encode(),'apex_phase4_journal.json','application/json')
                st.download_button('Download Phase 4 prospective evaluation',json.dumps(report,indent=2).encode(),'apex_phase4_forward_results.json','application/json')
            except (ValueError,OSError) as e:st.error('Journal verification failed: '+str(e))
        frozen=eng.ROOT/'validation'/'PHASE4_RESULTS.json'
        if frozen.exists():
            with st.expander('Phase 4 frozen historical evaluation'):
                review=json.loads(frozen.read_text());st.dataframe(pd.DataFrame(review['summary']),hide_index=True,use_container_width=True)
                st.caption('Frozen historical test, separate from prospective results. This period is now known and cannot be reused as untouched evidence for later tuning.')
                st.json({'protocol':review.get('protocol'),'exclusions':review.get('exclusions'),'comparisons':review.get('comparisons')})
