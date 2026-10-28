"""Read-only monitoring until an operator explicitly starts a manual research action."""
import os,json
from datetime import datetime,timezone
import streamlit as st
import pandas as pd
import first_basket_engine as eng,phase4_data as background
import phase5_store as storage,phase5_runner as runner,phase5_protocol as protocol,phase5_integrity as integrity
from phase5_providers import Providers,stamp

def render(injury_key=''):
    root=eng.DATA/'phase5';exists=(root/'operations.sqlite3').exists() or bool(os.environ.get('APEX_DATABASE_URL'))
    with st.expander('Phase 5 · live intelligence and prospective monitoring'):
        st.caption('Research only. V2.44 remains the production default. Opening this panel makes no paid provider requests. A scheduler and persistent cloud database require separate setup.')
        if st.button('Register frozen Phase 5 experiment'):
            try:
                s=storage.configured_store();protocol.register(s);st.success('Experiment registered. Settings and feature code are frozen; no live collector was installed.')
                exists=True
            except (ValueError,storage.StorageError) as e:st.error(str(e))
        if not exists:
            st.info('Phase 5 is not initialized here. Read V3_REVIEW.md and PHASE5_OPERATIONS.md before enabling collection.');return
        try:
            s=storage.configured_store();health=runner.health(s);rows=s.rows();snaps=[r for r in rows if r['kind']=='snapshot'];preds=[r for r in rows if r['kind']=='prediction'];prospective=health['prospective']
            st.write(health['storage']);st.write('Integrity: '+health['integrity'])
            st.write(f"Snapshots {health['counts']['snapshot']} · both fives provider-confirmed {health['counts']['both_provider_confirmed']} · forecasts {health['counts']['prediction']} · graded primary games {prospective['graded_games']}")
            st.write(f"Forecasts awaiting a result: {health['counts']['awaiting_grading_forecasts']}")
            st.caption(health['automation_note']);st.write(f"Recorded successful scheduled invocations: {health['scheduled_invocation_receipts']}")
            st.write('Last successful collection: '+str(health['last_successful_collection']))
            slate=health.get('slate') or {};now=datetime.now(timezone.utc)
            if slate:
                age=(now-stamp(slate['retrieved_at'])).total_seconds();st.caption(f"Slate last retrieved {slate['retrieved_at']} · {'STALE — refresh required' if age>300 or age<0 else 'recent snapshot'}")
                st.dataframe(pd.DataFrame([{'Game':g['gameId'],'Matchup':g['awayTeam']['teamTricode']+' at '+g['homeTeam']['teamTricode'],'Scheduled UTC':g['start_time'],'Provider status':g.get('gameStatus')} for g in slate['games']]),hide_index=True,use_container_width=True)
            def start(name,func):
                try:st.info(background.start_job(name,func,root))
                except ValueError as e:st.error(str(e))
            if st.button('Reconcile and sync Phase 5 training history'):
                def sync():
                    store=storage.configured_store();source=eng.DATA/'phase4';audit=integrity.reconcile(source,[source/'raw',eng.DATA/'phase3_validation',eng.DATA/'v3_validation'],repair=True);store.set_state('historical_integrity',audit)
                    if not audit['healthy']:raise ValueError('Inventory conflicts require review; cloud sync refused')
                    return integrity.sync_history(store,source)
                start('Phase 5 history sync',sync)
            if st.button('Observe current Phase 5 pre-tip evidence'):
                start('Phase 5 manual observation',lambda:runner.tick(storage.configured_store(),Providers(storage.configured_store(),injury_key=injury_key),observe=True))
            if st.button('Run due Phase 5 forecast checkpoints'):
                start('Phase 5 manual checkpoint',lambda:runner.tick(storage.configured_store(),Providers(storage.configured_store(),injury_key=injury_key)))
            if st.button('Grade completed Phase 5 forecasts'):
                start('Phase 5 manual grading',lambda:runner.grade_tick(storage.configured_store()))
            st.button('Refresh Phase 5 monitoring')
            st.json(background.job_status(root))
            if preds:
                options={r['hash']:r for r in preds};key=st.selectbox('Saved Phase 5 forecast',list(options),format_func=lambda h:options[h]['payload']['game']['gameId']+' · '+options[h]['payload']['generated_at'])
                p=options[key]['payload'];game=p['game'];age=(now-stamp(p['generated_at'])).total_seconds();latest=next((r for r in reversed(snaps) if r['payload']['game']['gameId']==game['gameId']),None)
                fresh=0<=age<=300 and now<stamp(game['start_time']) and latest and latest['hash']==p['snapshot_hash']
                st.warning(('Recent archived research forecast — check current game status.' if fresh else 'STALE / historical forecast — not current probabilities.')+' No validated betting advantage.')
                st.caption(f"{p['cohort']} · saved {p['generated_at']} · {p['trials']:,} trials · seed {p['seed']} · Other {p['forecasts']['Hybrid']['OTHER']:.2%}")
                names={x['player_id']:x['player'] for ps in p['snapshot']['lineups'].values() for x in ps};hybrid=p['forecasts']['Hybrid']
                for rank,pid in enumerate(sorted(names,key=lambda x:-hybrid[x])[:5],1):
                    st.markdown(f"**{rank}. {names[pid]}**");st.write(f"Baseline {p['forecasts']['Baseline'][pid]:.1%} · MC {p['forecasts']['Pure Monte Carlo'][pid]:.1%} · Hybrid {hybrid[pid]:.1%} · first shot {p['first_shot_proxy'][pid]:.1%}")
                with st.expander('Saved Phase 5 uncertainty and original evidence'):st.json(p)
            st.info(prospective['status']);st.write(f"Eligible primary forecasts {prospective['eligible_primary_forecasts']} · pending {prospective['pending']} · initial milestone 300 games across at least 30 dates")
            if prospective['graded_games']:
                st.dataframe(pd.DataFrame(prospective['summary']),hide_index=True,use_container_width=True);st.json(prospective['comparisons'])
                bins=pd.DataFrame([x for x in prospective['calibration'] if x['Cohort']=='All' and x['Model']=='Pure Monte Carlo'])
                if not bins.empty:st.line_chart(bins.set_index('Band')[['Predicted %','Observed %']])
            with st.expander('Phase 5 failures, providers and missed windows'):st.json(health)
            st.download_button('Download Phase 5 monitoring report',json.dumps(health,indent=2).encode(),'apex_phase5_monitoring.json','application/json')
        except (ValueError,storage.StorageError) as e:st.error('Phase 5 unavailable: '+str(e))
