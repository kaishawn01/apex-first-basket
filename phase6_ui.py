"""Existing dashboard extension: explicit refresh, no paid APIs or local worker."""
import os,json,re
from pathlib import Path
from datetime import datetime,timezone
import requests
import streamlit as st
import pandas as pd
from phase6_journal import Journal,validate,MAX_BYTES
from phase5_providers import stamp
from phase6_metrics import evaluate

REPO='kaishawn01/apex-first-basket'
BRANCH='apex-research-data'

def load_remote(path):
    if not re.fullmatch(r'(fixtures/[0-9a-f]{40}|live)/journal.json',path):raise ValueError('Invalid journal path')
    # Public read only; no credential, no arbitrary hosts, no provider requests.
    url=f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}'
    with requests.get(url,timeout=15,stream=True,allow_redirects=False) as r:
        if r.status_code!=200:raise ValueError('Public archive unavailable')
        chunks=[];size=0
        for chunk in r.iter_content(65536):
            size+=len(chunk)
            if size>MAX_BYTES:raise ValueError('Archive too large; stop and migrate')
            chunks.append(chunk)
    return validate(json.loads(b''.join(chunks)))

def load_report(path,doc):
    url=f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path.removesuffix("journal.json")}report.json'
    with requests.get(url,timeout=15,stream=True,allow_redirects=False) as r:
        if r.status_code!=200:raise ValueError('Publication report unavailable')
        chunks=[];size=0
        for chunk in r.iter_content(65536):
            size+=len(chunk)
            if size>MAX_BYTES:raise ValueError('Report exceeds limit')
            chunks.append(chunk)
    report=json.loads(b''.join(chunks))
    if report.get('journal_head')!=doc['head']:raise ValueError('Archive/report changed during read; refresh again')
    return report

class View:
    def __init__(self,doc):self.doc=validate(doc)
    def rows(self,kind=None):return [r for r in self.doc['events'] if kind is None or r['kind']==kind]

def render_document(doc,loaded_at,receipts=None):
    view=View(doc);preds=view.rows('prediction');test=bool(preds and all(r['payload']['test_only'] for r in preds))
    if test:st.warning('TEST FIXTURES ONLY — synthetic games/outcomes; not live NBA predictions.')
    st.caption('Archive read '+loaded_at+' · hash chain verified. Durable publication is separate from model execution. Current automation status: disabled pending approval.')
    report=evaluate(view,receipts,test=test)
    st.metric('Archived prediction snapshots',len(preds));st.metric('Graded snapshots',report['graded_snapshots']);st.metric('Pending outcomes',report['pending'])
    if not receipts and not test:st.info('Durable pre-tip commit receipts are not loaded in this view; live performance is withheld. Use the verified Git report.')
    for record in preds[-15:][::-1]:
        p=record['payload'];g=p['game'];now=datetime.now(timezone.utc);age=(now-stamp(p['generated_at'])).total_seconds()
        stale=age<0 or age>300 or now>=stamp(g['start_time'])
        with st.expander(g['awayTeam']['teamTricode']+' vs '+g['homeTeam']['teamTricode']+' · '+p['snapshot_type']):
            st.caption(p['generated_at']+' · model '+p['model_version']+' · '+p['cohort'])
            if stale:st.warning('STALE / historical snapshot — not current probabilities')
            st.write('Lineups: '+', '.join(t+': '+s for t,s in p['lineup_status'].items()))
            names={x['player_id']:x['player'] for ps in p['lineups'].values() for x in ps}
            ids=sorted(names,key=lambda pid:p['forecasts']['Baseline'][pid],reverse=True)[:5]
            st.dataframe(pd.DataFrame([{'Player':names[pid],'Baseline %':100*p['forecasts']['Baseline'][pid],'MC %':100*p['forecasts']['Pure Monte Carlo'][pid],'Hybrid %':100*p['forecasts']['Hybrid'][pid],'First shot %':100*p['first_shot_proxy'][pid]} for pid in ids]),hide_index=True,use_container_width=True)
            st.caption(f"Other {p['forecasts']['Baseline']['OTHER']:.2%} · {p['trials']} trials · seed {p['seed']} · {p['training_games']} prior games")
            if not p['minimum_history_met']:st.warning('Insufficient historical sample: model fallback applies')
            st.caption(p['odds_status']);st.json({'uncertainty':p['mc_sampling_se'],'evidence':p['evidence']})
    if report['primary_games']:st.dataframe(pd.DataFrame(report['summary']),hide_index=True,use_container_width=True)
    else:st.info('No eligible primary prospective results. Fixture or backtest accuracy is not live performance.')
    with st.expander('Cloud execution and validation details'):
        st.json({'runs':[r['payload'] for r in view.rows('run')][-10:],'evaluation':report})
    return report

def render():
    with st.expander('Phase 6 · cloud journal and automation health'):
        st.caption('Read-only research archive. No paid API requests. Cloud collection and mobile deployment require separate activation.')
        path=st.text_input('Cloud journal path',value=os.environ.get('APEX_PUBLIC_JOURNAL','live/journal.json'),key='p6_path')
        if st.button('Load persisted cloud journal'):
            try:
                doc=load_remote(path);report=load_report(path,doc)
                st.session_state['p6_archive']=(doc,datetime.now(timezone.utc).isoformat(),path,report['receipts'])
            except (ValueError,requests.RequestException):st.error('Archive unavailable or invalid; no current forecast claimed.');st.session_state.pop('p6_archive',None)
        saved=st.session_state.get('p6_archive')
        if saved and saved[2]==path:render_document(saved[0],saved[1],saved[3])
        else:st.info('No cloud archive loaded. Scheduling is not activated; local dashboard files are not permanent cloud storage.')
