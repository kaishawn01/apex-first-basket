import sys
import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
import dashboard_core as core
import first_basket_engine as eng
import research_tools as research
from streamlit.testing.v1 import AppTest
players={t:[{'player_id':str(offset+i),'player':f'{t} Player {i}'} for i in range(6)] for t,offset in [('BOS',10),('NYK',20)]}
from test_research import game_rows
history=game_rows('old','2027-01-01')
game={'gameId':'espn_test','_date':'2027-01-02','start_time':'2027-01-02T23:00:00Z','gameStatus':1,'awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
with tempfile.TemporaryDirectory() as journal_dir,patch.object(eng,'DATA',Path(journal_dir)),patch.object(eng,'read_csv',return_value=history),patch.object(core,'fresh_schedule',return_value=[game]),patch.object(core,'roster',side_effect=lambda t:players[t]):
 at=AppTest.from_file(str(root/'app.py')).run()
 assert not at.exception,list(at.exception)
 with patch.object(core,'request',side_effect=AssertionError('Research export must not fetch APIs')):
  next(b for b in at.button if b.label=='Prepare research export').click().run()
 assert not at.exception,list(at.exception)
 assert any(d.label=='Download research ZIP' for d in at.get('download_button'))
 import io,zipfile
 with zipfile.ZipFile(io.BytesIO(at.session_state['research_export']['data'])) as archive:
  assert 'history.csv' in archive.namelist()
 indexed_game={'gameId':'espn_missing','_date':'2026-01-01','gameStatus':3,'awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
 with patch.object(research,'season_index',return_value=([indexed_game],['ATL: offline'])),patch.object(core,'request',side_effect=AssertionError('Use mocked schedule index')):
  next(b for b in at.button if b.label=='Check saved history against season schedule').click().run()
 assert not at.exception,list(at.exception)
 assert at.session_state['schedule_coverage']['counts']['Missing']==1
 assert any(d.label=='Download schedule coverage CSV' for d in at.get('download_button'))
 assert any('Partial schedule coverage' in x.value for x in at.warning)
 with patch.object(research,'season_index',side_effect=RuntimeError('Schedule unavailable')):
  next(b for b in at.button if b.label=='Check saved history against season schedule').click().run()
 assert any('Schedule unavailable' in x.value for x in at.error)
 assert not any(d.label=='Download schedule coverage CSV' for d in at.get('download_button'))
 with patch.object(research,'season_index',return_value=([indexed_game],[])):
  next(b for b in at.button if b.label=='Check saved history against season schedule').click().run()

 at.date_input[0].set_value(date(2027,1,2)).run()
 assert any('Check schedule coverage again' in x.value for x in at.info)
 assert not any(d.label=='Download schedule coverage CSV' for d in at.get('download_button'))
 assert any('Prepare a fresh research export' in x.value for x in at.info)
 assert not any(d.label=='Download research ZIP' for d in at.get('download_button'))
 retry_report={'season_end':2026,'added':0,'attempted':2,'remaining':14,'retry_attempted':2,'never_attempted_remaining':12,'schedule_warnings':[],
               'skipped':[{'game_id':'espn_a','date':'2026-01-01','reason':'Unavailable'},{'game_id':'espn_b','date':'2026-01-02','reason':'Unavailable'}]}
 with patch.object(research,'import_season',return_value=retry_report):
  next(b for b in at.button if b.label=='Import prior-season history').click().run()
 assert not at.exception,list(at.exception)
 assert any('retried 2 previously attempted games' in x.value for x in at.caption)
 assert any('12 indexed missing games have not been attempted yet' in x.value for x in at.caption)
 next(b for b in at.button if 'Load slate' in b.label).click().run()
 assert not at.exception,list(at.exception)
 assert len([m for m in at.multiselect if 'select five starters' in m.label])==2
 assert all(len(m.value)==5 for m in at.multiselect if 'select five starters' in m.label)
 for cb in at.checkbox:
  if cb.label.startswith('I verified'):cb.check()
 at.run()
 next(b for b in at.button if 'Run rankings' in b.label).click().run()
 assert not at.exception,list(at.exception)
 ranking=next(d.value for d in at.dataframe if 'Model %' in d.value.columns)
 assert len(ranking)==10
 leaders=next(d.value for d in at.dataframe if 'Top candidates' in d.value.columns)
 assert len(leaders)==1
 assert abs(leaders.iloc[0]['Each leader %']-max(r['_probability'] for r in at.session_state['results']['rows'])*100)<1e-10
 assert leaders.iloc[0]['Leader status']=='HOLD: SAMPLE'
 assert any(d.label=='Download top candidates CSV' for d in at.get('download_button'))
 assert all(ranking['Observed opening-shot starts']==1)
 assert all(ranking['Weighted observed shot starts']<1)
 assert all(ranking['Shot coverage note']=='Below 8 observed opening-shot starts')
 evidence_tables=[d.value for d in at.dataframe if 'Starts in recent recorded games' in d.value.columns]
 assert len(evidence_tables)==2
 assert all(sum(t['Selected'])==5 for t in evidence_tables)
 assert any('Use the NBA lineup button' in x.value for x in at.caption)
 assert any(d.label=='Download matchup model comparison CSV' for d in at.get('download_button'))
 model_table=next(d.value for d in at.dataframe if 'Range (percentage points)' in d.value.columns)
 assert len(model_table)==10
 assert abs(model_table['Lineup context %'].sum()-100)<1e-8
 assert set(ranking['Status'])=={'HOLD: SAMPLE'}
 with patch.object(core,'rank_game',side_effect=AssertionError('Saving must use displayed model forecasts')):
  next(b for b in at.button if b.label=='Save confirmed forecasts to journal').click().run()
 assert not at.exception,list(at.exception)
 assert len(research.journal_records())==1
 assert set(research.journal_records()[0]['snapshot']['model_forecasts'])=={'baseline','recent','lineup'}
 assert any(d.label=='Download forward model comparison CSV' for d in at.get('download_button'))
 next(b for b in at.button if b.label=='Save confirmed forecasts to journal').click().run()
 assert len(research.journal_records())==1
 assert any(d.label=='Download forward journal CSV' for d in at.get('download_button'))
 next(s for s in at.selectbox if s.label=='Journal scoring model').set_value('recent').run()
 assert not at.exception,list(at.exception)
 journal=next(d.value for d in at.dataframe if 'Saved before tip' in d.value.columns)
 assert set(journal['Model'])=={'recent'}
 assert any('Pick reliability will appear' in x.value for x in at.info)
 assert not any(d.label=='Download forward equal-chance evidence CSV' for d in at.get('download_button'))
 saved=research.journal_records()
 probabilities={r['_player_id']:r['_probability'] for r in saved[0]['snapshot']['rows']}
 import math
 saved[0]['outcome']={'winner_id':'10','winner':'BOS Player 0','winner_probability':probabilities['10'],
                      'outside_field':False,'top1_credit':research.top_k_credit(probabilities,'10',1),
                      'brier':sum((p-int(pid=='10'))**2 for pid,p in probabilities.items()),
                      'log_loss':-math.log(probabilities['10']),'lineup_matches':True}
 with patch.object(research,'journal_records',return_value=saved):
  at.run()
  assert not at.exception,list(at.exception)
  assert any(d.label=='Download forward pick reliability CSV' for d in at.get('download_button'))
  reliability=next(d.value for d in at.dataframe if 'Outside-field winners' in d.value.columns and 'Band' in d.value.columns)
  assert set(reliability['Model'])=={'baseline','recent','lineup'}
  assert all(reliability['Games']==1)
  assert any(d.label=='Download forward equal-chance evidence CSV' for d in at.get('download_button'))
  evidence=next(d.value for d in at.dataframe if 'Model minus equal' in d.value.columns)
  assert len(evidence)==12 and set(evidence['Games'])=={1}
  saved[0]['outcome']={**saved[0]['outcome'],'winner_id':'999','outside_field':True,'top1_credit':0.,'brier':1+sum(p*p for p in probabilities.values()),'log_loss':None,'lineup_matches':False}
  at.run()
  assert not at.exception,list(at.exception)
  evidence=next(d.value for d in at.dataframe if 'Model minus equal' in d.value.columns)
  assert all(evidence['Outside-field winners']==1)
  assert all(evidence[evidence['Metric']=='Log loss']['Reading'].str.startswith('Undefined difference'))
  assert any('No winner is dropped' in x.value for x in at.caption)

 print('Journal UI passed: all-model save, comparison export, model filter, duplicate prevention.')
 at.multiselect[0].set_value(['10','11','12','13','15']).run()
 assert not next(cb for cb in at.checkbox if cb.label.startswith('I verified BOS')).value
 assert any('Inputs changed' in x.value for x in at.info)
 assert not any('Range (percentage points)' in d.value.columns for d in at.dataframe)
 assert not any('Top candidates' in d.value.columns for d in at.dataframe)
 assert not any(d.label=='Download top candidates CSV' for d in at.get('download_button'))
 print('UI checks passed: launch, projected five, confirmations, ranking table, edit reset, stale-results guard.')

from datetime import timedelta
history2=[r for i in range(40) for r in game_rows(str(i),(date(2026,8,1)+timedelta(days=i)).isoformat())]
with patch.object(eng,'read_csv',return_value=history2):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(30).run()
 next(b for b in at.button if b.label=='Run walk-forward evaluation').click().run()
 assert not at.exception,list(at.exception)
 metrics=next(d.value for d in at.dataframe if 'Log loss' in d.value.columns)
 assert metrics.iloc[0]['Evaluated games']==10
 assert any(d.label=='Download game-by-game backtest' for d in at.get('download_button'))
 next(b for b in at.button if b.label=='Compare baseline vs recent form').click().run()
 assert not at.exception,list(at.exception)
 comparison=next(d.value for d in at.dataframe if 'Model' in d.value.columns and set(d.value['Model'])=={'baseline','recent'})
 assert list(comparison['Evaluated games'])==[10,10]
 assert 'Top-3 hit %' in comparison.columns
 assert any('95% lower' in d.value.columns for d in at.dataframe)
 assert any(d.label=='Download paired model comparison' for d in at.get('download_button'))
 next(b for b in at.button if b.label=='Compare baseline vs lineup context').click().run()
 assert not at.exception,list(at.exception)
 comparison=next(d.value for d in at.dataframe if 'Model' in d.value.columns and set(d.value['Model'])=={'baseline','lineup'})
 assert list(comparison['Evaluated games'])==[10,10]
 with patch.object(core,'request',side_effect=AssertionError('Calibration test must not fetch APIs')):
  next(b for b in at.button if b.label=='Test probability calibration').click().run()
 assert not at.exception,list(at.exception)
 calibration=at.session_state['temperature_comparison']
 assert len(calibration['summary'])==8
 assert calibration['learned_games']==0
 assert any('not learned adjustments' in x.value for x in at.info)
 assert any(d.label=='Download probability adjustment decisions CSV' for d in at.get('download_button'))
 next(b for b in at.button if b.label=='Run full model validation').click().run()
 assert not at.exception,list(at.exception)
 validation=next(d.value for d in at.dataframe if 'Period' in d.value.columns and 'Model' in d.value.columns)
 assert len(validation)==6
 assert list(validation[validation['Period']=='Newest quarter of dates']['Evaluated games'])==[3,3,3]
 assert any(d.label=='Download full validation CSV' for d in at.get('download_button'))
 assert any(d.label=='Download pick reliability CSV' for d in at.get('download_button'))
 assert at.session_state['validation_report']['pick_reliability']
 assert any(d.label=='Download scoring-stage diagnostics CSV' for d in at.get('download_button'))
 assert len(at.session_state['validation_report']['scoring_stages'])==6
 assert len(at.session_state['validation_report']['equal_benchmark_evidence'])==24
 assert any(d.label=='Download equal-chance evidence CSV' for d in at.get('download_button'))
 evidence=next(d.value for d in at.dataframe if 'Model minus equal' in d.value.columns)
 assert set(evidence['Games'])=={3,10}
 assert any('not bookmaker odds' in x.value for x in at.caption)
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(100).run()
 assert any('Run full model validation again' in x.value for x in at.info)
 assert not any('Period' in d.value.columns for d in at.dataframe)
 assert not any(d.label=='Download equal-chance evidence CSV' for d in at.get('download_button'))
 assert not any(d.label=='Download probability adjustment decisions CSV' for d in at.get('download_button'))
 assert any('Run the probability calibration test again' in x.value for x in at.info)
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(30).run()
 with patch.object(core,'request',side_effect=AssertionError('Signal experiment must not fetch APIs')):
  next(b for b in at.button if b.label=='Compare opening-shot vs first-score signals').click().run()
 assert not at.exception,list(at.exception)
 signal=at.session_state['signal_comparison']
 assert len(signal['summary'])==8
 assert signal['adaptive_learned_games']==0
 assert any(d.label=='Download adaptive signal decisions CSV' for d in at.get('download_button'))
 assert signal['model']=='baseline'
 assert next(b for b in at.button if b.label=='Compare 30 / 90 / 180-day decay').disabled
 assert next(s for s in at.selectbox if s.label=='Scoring model').value=='baseline'
 assert any(d.label=='Download signal comparison CSV' for d in at.get('download_button'))
 assert any(d.label=='Download signal predictions CSV' for d in at.get('download_button'))
 assert any('do not test learned choices yet' in x.value for x in at.info)
 long_history=[r for i in range(135) for r in game_rows(str(i),(date(2026,1,1)+timedelta(days=i)).isoformat())]
 at.session_state['signal_comparison']=research.compare_scoring_signals(long_history,30,'baseline')
 with patch.object(eng,'read_csv',return_value=long_history):
  at.run()
 assert not at.exception,list(at.exception)
 assert any(d.label=='Download active adaptive summary CSV' for d in at.get('download_button'))
 assert any(d.label=='Download active adaptive predictions CSV' for d in at.get('download_button'))
 assert at.session_state['signal_comparison']['active_selection']['games']==5

 next(s for s in at.selectbox if s.label=='Scoring model').set_value('recent').run()
 assert any('Run the signal comparison again' in x.value for x in at.info)
 assert not any(d.label=='Download signal comparison CSV' for d in at.get('download_button'))
 with patch.object(core,'request',side_effect=AssertionError('Recency test must not fetch APIs')):
  next(b for b in at.button if b.label=='Compare 30 / 90 / 180-day decay').click().run()
 assert not at.exception,list(at.exception)
 assert len(at.session_state['recency_comparison']['summary'])==6
 assert any(d.label=='Download recency comparison CSV' for d in at.get('download_button'))
 assert any(d.label=='Download recency predictions CSV' for d in at.get('download_button'))
 assert next(s for s in at.selectbox if s.label=='Scoring model').value=='recent'
 next(s for s in at.selectbox if s.label=='Scoring model').set_value('lineup').run()
 assert any('Run the recency comparison again' in x.value for x in at.info)
 assert not any(d.label=='Download recency comparison CSV' for d in at.get('download_button'))
 print('Backtest UI passed: full validation, recent-period counts, exports and stale-report reset.')

with tempfile.TemporaryDirectory() as journal_dir,patch.object(eng,'DATA',Path(journal_dir)),patch.object(eng,'read_csv',return_value=history),patch.object(core,'roster',side_effect=lambda t:players[t]),patch.object(core,'fresh_schedule',side_effect=AssertionError('Research mode must not request a live slate')):
 at=AppTest.from_file(str(root/'app.py')).run()
 at.date_input[0].set_value(date(2027,1,2)).run()
 next(r for r in at.radio if r.label=='Workspace').set_value('Research matchup').run()
 next(s for s in at.selectbox if s.label=='Research team A').set_value('BOS').run()
 next(s for s in at.selectbox if s.label=='Research team B').set_value('NYK').run()
 next(s for s in at.selectbox if s.label=='Scoring model').set_value('recent').run()
 next(b for b in at.button if 'Load slate' in b.label).click().run()
 assert not at.exception,list(at.exception)
 next(b for b in at.button if 'Run rankings' in b.label).click().run()
 assert not at.exception,list(at.exception)
 ranking=next(d.value for d in at.dataframe if 'Model %' in d.value.columns)
 assert len(ranking)==10 and set(ranking['Status'])=={'RESEARCH MATCHUP'}
 assert set(ranking['Model'])=={'recent'}
 assert next(b for b in at.button if b.label=='Fetch FanDuel first-basket odds').disabled
 assert next(b for b in at.button if b.label=='Save confirmed forecasts to journal').disabled
 assert research.journal_records()==[]
 print('Research mode UI passed: after-hours ranking, candidate model, no live slate request, odds and journal disabled.')

 next(s for s in at.selectbox if s.label=='Scoring model').set_value('lineup').run()
 next(b for b in at.button if 'Run rankings' in b.label).click().run()
 assert not at.exception,list(at.exception)
 ranking=next(d.value for d in at.dataframe if 'Model %' in d.value.columns)
 assert set(ranking['Model'])=={'lineup'}
 assert 'Similar-lineup starts' in ranking.columns
 assert ranking['Similar-lineup starts'].min()==1
 assert all(ranking['Other-lineup starts']==0)
 assert all(ranking['Weighted other-lineup starts']==0)
 assert next(b for b in at.button if b.label=='Save confirmed forecasts to journal').disabled
 print('Lineup context UI passed: research rankings, context counts, no forward saving.')

 original_results=at.session_state['results']['rows']
 next(b for b in at.button if b.label=='Compare starter change').click().run()
 assert not at.exception,list(at.exception)
 scenario=next(d.value for d in at.dataframe if 'Scenario role' in d.value.columns)
 assert len(scenario)==11
 assert abs(scenario['After %'].sum()-100)<1e-8
 assert any(d.label=='Download lineup scenario CSV' for d in at.get('download_button'))
 assert at.session_state['results']['rows']==original_results
 assert research.journal_records()==[]
 next(s for s in at.selectbox if s.label=='Replace starter').set_value('11').run()
 assert any('Scenario inputs changed' in x.value for x in at.info)
 assert not any('Scenario role' in d.value.columns for d in at.dataframe)
 print('Scenario UI passed: comparison, export, unchanged rankings, no journal writes, stale scenario hidden.')

 assert any(d.label=='Download player evidence CSV' for d in at.get('download_button'))
 evidence=next(d.value for d in at.dataframe if 'Opening-shot rate %' in d.value.columns)
 assert list(evidence['Starts'])==[1,1,1]
 inspect=next(s for s in at.selectbox if s.label=='Inspect ranked player')
 inspect.set_value((game_id:='research_BOS_NYK_2027-01-02','11')).run()
 assert not at.exception,list(at.exception)
 evidence=next(d.value for d in at.dataframe if 'Opening-shot rate %' in d.value.columns)
 assert evidence['Game first scores'].sum()==0
 assert at.session_state['results']['rows']==original_results
 print('Player evidence UI passed: history table, player switching, CSV export, rankings preserved.')

from test_research import ForwardJournalTests
fixture=ForwardJournalTests();fixture.setUp()
payload=fixture.payload()
payload['header']['competitions'][0]['date']='2025-10-25T23:00:00Z'
with tempfile.TemporaryDirectory() as repair_dir:
 folder=Path(repair_dir);path=folder/'history.csv'
 bad=game_rows('espn_123','2025-10-25');bad[1]['first_team_shot']=1
 eng.write_csv(path,eng.FIELDS,bad)
 with patch.object(eng,'DATA',folder),patch.object(eng,'HISTORY',path),patch.object(core,'request',return_value=payload):
  at=AppTest.from_file(str(root/'app.py')).run()
  assert not at.exception,list(at.exception)
  assert any(b.label=='Repair selected history games' for b in at.button)
  next(b for b in at.button if b.label=='Repair selected history games').click().run()
  assert not at.exception,list(at.exception)
  assert research.audit(eng.read_csv(path))[1]==[]
  assert any('Last repair: 1 of 1' in x.value for x in at.info)
  assert len(list(folder.glob('history_before_repair_*.csv')))==1
  assert not any(b.label=='Repair selected history games' for b in at.button)
  print('Repair UI passed: selected-game repair, backup, refreshed validation, success report.')

with tempfile.TemporaryDirectory() as folder,patch.object(eng,'DATA',Path(folder)),patch.object(eng,'read_csv',return_value=history),patch.object(core,'fresh_schedule',return_value=[game]),patch.object(core,'roster',side_effect=RuntimeError('Unavailable')):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.date_input if s.label=='Game date • Eastern time').set_value(date(2027,1,2)).run()
 next(b for b in at.button if 'Load slate' in b.label).click().run()
 assert not at.exception,list(at.exception)
 assert all(not m.value for m in at.multiselect if 'select five starters' in m.label)
 assert any('Current roster unavailable: no automatic' in w.value for w in at.warning)
 assert all(cb.disabled for cb in at.checkbox if cb.label.startswith('I verified'))
 print('Roster failure UI passed: no automatic selections or confirmations.')

with patch.object(eng,'read_csv',return_value=history2),patch.object(core,'request',side_effect=AssertionError('Lineup test must not fetch APIs')):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.date_input if s.label=='Game date • Eastern time').set_value(date(2026,10,25)).run()
 next(b for b in at.button if b.label=='Test starting-lineup projections').click().run()
 assert not at.exception,list(at.exception)
 report=at.session_state['lineup_validation']
 assert len(report['summary'])==4
 assert [r['Team lineups'] for r in report['summary'] if r['Period']=='All evaluated dates']==[70,70]
 assert any(d.label=='Download lineup projection details CSV' for d in at.get('download_button'))
 next(s for s in at.date_input if s.label=='Game date • Eastern time').set_value(date(2026,10,24)).run()
 assert not any(d.label=='Download lineup projection details CSV' for d in at.get('download_button'))
 assert any('Run the starting-lineup projection test again' in x.value for x in at.info)
 print('Lineup validation UI passed: counts, export, no API calls and stale-date hiding.')

from test_dashboard import NBAConfirmedLineupTests
fixture=NBAConfirmedLineupTests();fixture.setUp()
provider_game={**game,'gameId':fixture.game['gameId']}
parsed=core.parse_nba_confirmed_lineups(fixture.payload,'2027-01-02',[provider_game],players)
with tempfile.TemporaryDirectory() as folder,patch.object(eng,'DATA',Path(folder)),patch.object(eng,'read_csv',return_value=history),patch.object(core,'fresh_schedule',return_value=[provider_game]),patch.object(core,'roster',side_effect=lambda t:players[t]),patch.object(core,'fetch_nba_confirmed_lineups',return_value=parsed):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.date_input if s.label=='Game date • Eastern time').set_value(date(2027,1,2)).run()
 next(b for b in at.button if 'Load slate' in b.label).click().run()
 next(b for b in at.button if b.label=='Load NBA-confirmed starters · resets selections').click().run()
 assert not at.exception,list(at.exception)
 assert sum(x.value=='NBA FEED CONFIRMED' for x in at.caption)==2
 assert all(not cb.value for cb in at.checkbox if cb.label.startswith('I verified'))
 next(b for b in at.button if b.label=='3 · Run rankings').click().run()
 assert not at.exception,list(at.exception)
 next(b for b in at.button if b.label=='Save confirmed forecasts to journal').click().run()
 assert not at.exception,list(at.exception)
 saved=research.journal_records()
 assert len(saved)==1
 assert {v['method'] for v in saved[0]['snapshot']['lineup_evidence'].values()}=={'NBA feed confirmed'}
 assert 'NBA feed confirmed' in research.journal_table(saved)[0]['Lineup verification']
 assert research.journal_table(saved)[0]['NBA lineup retrieval UTC']
 next(m for m in at.multiselect if m.label.startswith('BOS')).set_value(['10','11','12','13','15']).run()
 assert sum(x.value=='NBA FEED CONFIRMED' for x in at.caption)==1
 assert any('Inputs changed' in x.value for x in at.info)
 with patch.object(core,'fetch_nba_confirmed_lineups',side_effect=RuntimeError('Network unavailable')):
  next(b for b in at.button if b.label=='Load NBA-confirmed starters · resets selections').click().run()
 assert not at.exception,list(at.exception)
 assert not any(x.value=='NBA FEED CONFIRMED' for x in at.caption)
 assert any('Provider confirmations were cleared' in x.value for x in at.warning)
 print('NBA confirmed-lineup UI passed: load, automatic confirmation, journal provenance, edit and failure invalidation.')

with patch.object(eng,'read_csv',return_value=history2),patch.object(core,'request',side_effect=AssertionError('Conversion comparison must not fetch APIs')):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(30).run()
 next(b for b in at.button if b.label=='Test opening-shot conversion model').click().run()
 assert not at.exception,list(at.exception)
 report=at.session_state['conversion_comparison']
 assert len(report['summary'])==4
 assert report['known_attempts']==0
 assert any('No evaluated games had conversion training data' in x.value for x in at.info)
 assert any(d.label=='Download opening-shot model predictions CSV' for d in at.get('download_button'))
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(100).run()
 assert not any(d.label=='Download opening-shot model predictions CSV' for d in at.get('download_button'))
 assert any('Run the opening-shot conversion test again' in x.value for x in at.info)
 print('Opening conversion UI passed: comparison, missing-data fallback, export and staleness.')

from test_research import OpeningResultEnrichmentTests
fixture=OpeningResultEnrichmentTests();fixture.setUp()
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'history.csv';eng.write_csv(path,list(fixture.rows[0]),fixture.rows)
 with patch.object(eng,'DATA',Path(folder)),patch.object(eng,'HISTORY',path),patch.object(core,'request',return_value=fixture.payload):
  at=AppTest.from_file(str(root/'app.py')).run()
  next(m for m in at.multiselect if m.label=='Saved games to enrich with opening-shot results').set_value(['espn_401809955']).run()
  next(b for b in at.button if b.label=='Enrich selected opening-shot results').click().run()
  assert not at.exception,list(at.exception)
  assert at.session_state['opening_enrichment']['enriched_games']==1
  assert list(Path(folder).glob('history_before_opening_results_*.csv'))
  assert sum(str(r['first_team_shot_made']) in ('0','1') for r in eng.read_csv(path))==fixture.known
  print('Opening enrichment UI passed: selected import, backup and saved outcomes.')

from test_research import PostMissModelTests
sequence_fixture=PostMissModelTests();sequence_fixture.setUp()
sequence_history=sequence_fixture.history()
with patch.object(eng,'read_csv',return_value=sequence_history),patch.object(core,'request',side_effect=AssertionError('No network for post-miss comparison')):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(30).run()
 # With twelve games the normal UI warmup excludes all evaluations, but data coverage stays visible.
 next(b for b in at.button if b.label=='Test post-miss scoring model').click().run()
 assert not at.exception,list(at.exception)
 assert at.session_state['post_miss_comparison']['path_counts']['opening_fg_missed']==12
 assert any('No games reached the sequence-data minimum' in x.value for x in at.info)
 report=research.compare_post_miss(sequence_history,1);report['min_training']=30
 with patch.object(research,'compare_post_miss',return_value=report):
  next(b for b in at.button if b.label=='Test post-miss scoring model').click().run()
 assert not at.exception,list(at.exception)
 assert any(d.label=='Download post-miss model predictions CSV' for d in at.get('download_button'))
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(100).run()
 assert not any(d.label=='Download post-miss model predictions CSV' for d in at.get('download_button'))
 assert any('Run the post-miss model test again' in x.value for x in at.info)
 print('Post-miss model UI passed: path counts, empty/active reports, exports and stale settings.')

from test_research import OpeningEnrichmentBatchTests
batch_fixture=OpeningEnrichmentBatchTests();batch_fixture.setUp()
with tempfile.TemporaryDirectory() as folder:
 path=batch_fixture.prepare(folder)
 with patch.object(eng,'DATA',Path(folder)),patch.object(eng,'HISTORY',path),patch.object(core,'request',side_effect=lambda url,params:batch_fixture.payloads[params['event']]):
  at=AppTest.from_file(str(root/'app.py')).run()
  assert next(s for s in at.selectbox if s.label=='Opening-data batch size').value==20
  next(b for b in at.button if b.label=='Enrich next batch of saved games').click().run()
  assert not at.exception,list(at.exception)
  report=at.session_state['opening_enrichment']
  assert report['enriched_games']==3 and report['remaining']==0
  assert any('0 eligible games still need opening data' in x.value for x in at.caption)
  assert len(list(Path(folder).glob('history_before_opening_results_*.csv')))==1
  with patch.object(core,'request',side_effect=AssertionError('Completed queue must not fetch')):
   next(b for b in at.button if b.label=='Enrich next batch of saved games').click().run()
  assert not at.exception,list(at.exception)
  assert at.session_state['opening_enrichment']['attempted']==0
  print('Opening batch UI passed: defaults, automatic selection, checkpointing, shared backup and completed queue.')

with patch.object(eng,'read_csv',return_value=history2),patch.object(core,'request',side_effect=AssertionError('Scorecard must not fetch APIs')):
 at=AppTest.from_file(str(root/'app.py')).run()
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(30).run()
 next(b for b in at.button if b.label=='Compare all five scoring models').click().run()
 assert not at.exception,list(at.exception)
 card=at.session_state['scoring_scorecard']
 assert len(card['summary'])==10 and card['active_games']==0
 assert {r['Model'] for r in card['summary']}=={'baseline','recent','lineup','conversion','post_miss'}
 assert any(d.label=='Download scorecard predictions CSV' for d in at.get('download_button'))
 next(s for s in at.selectbox if s.label=='Scorecard evaluation period').set_value('Challenger-active games').run()
 assert any('No games satisfy this period yet' in x.value for x in at.info)
 next(s for s in at.selectbox if s.label=='Scorecard evaluation period').set_value('Newest quarter of dates').run()
 summary=next(d.value for d in at.dataframe if 'Top-1 difference pp' in d.value.columns)
 assert len(summary)==5 and set(summary['Evaluated games'])=={3}
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(100).run()
 assert not any(d.label=='Download scorecard predictions CSV' for d in at.get('download_button'))
 assert any('Compare all five scoring models again' in x.value for x in at.info)
 print('Scoring scorecard UI passed: five models, shared dates, active-data warning, exports and stale settings.')
