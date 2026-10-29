"""Read-only live-readiness summary inside the existing research dashboard."""
import streamlit as st
from phase6_ui import View
from phase7_live import monitoring

def render():
    with st.expander('Phase 7 · genuine live collection readiness'):
        st.warning('Live activation is blocked until training/source permissions are established. No unattended NBA collector is claimed.')
        st.caption('Research only. V2.44 is unchanged. This panel makes no provider calls and does not enable scheduling.')
        saved=st.session_state.get('p6_archive')
        if not saved:
            st.info('Load a persisted cloud journal in Phase 6 to inspect genuine observations. Fixture records remain excluded.');return
        try:
            r=monitoring(View(saved[0]),saved[3]);st.metric('Genuine archived forecasts',r['real_forecasts']);st.metric('Verified pre-tip publications',r['published_pre_tip']);st.metric('Verified outcomes',r['verified_outcomes']);st.metric('Unresolved / pending',r['unresolved_or_pending'])
            st.caption('Latest persisted forecast: '+str(r['latest_persisted_forecast'])+' · remaining reserved-attempt allowance: '+str(r['remaining_reserved_attempt_allowance']))
            st.json(r['last_execution'] or {'status':'No genuine execution record'});st.caption(r['automation'])
        except (ValueError,KeyError,TypeError):st.error('Live archive unavailable or inconsistent; no successful collection claimed.')
