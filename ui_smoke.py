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
 at.date_input[0].set_value(date(2027,1,2)).run()
 next(b for b in at.button if 'Load slate' in b.label).click().run()
 assert not at.exception,list(at.exception)
 assert len(at.multiselect)==2
 assert all(len(m.value)==5 for m in at.multiselect)
 for cb in at.checkbox:
  if cb.label.startswith('I verified'):cb.check()
 at.run()
 next(b for b in at.button if 'Run rankings' in b.label).click().run()
 assert not at.exception,list(at.exception)
 ranking=next(d.value for d in at.dataframe if 'Model %' in d.value.columns)
 assert len(ranking)==10
 assert all(ranking['Observed opening-shot starts']==1)
 assert all(ranking['Weighted observed shot starts']<1)
 assert all(ranking['Shot coverage note']=='Below 8 observed opening-shot starts')
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
 print('Journal UI passed: all-model save, comparison export, model filter, duplicate prevention.')
 at.multiselect[0].set_value(['10','11','12','13','15']).run()
 assert not next(cb for cb in at.checkbox if cb.label.startswith('I verified BOS')).value
 assert any('Inputs changed' in x.value for x in at.info)
 assert not any('Range (percentage points)' in d.value.columns for d in at.dataframe)
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
 next(b for b in at.button if b.label=='Run full model validation').click().run()
 assert not at.exception,list(at.exception)
 validation=next(d.value for d in at.dataframe if 'Period' in d.value.columns)
 assert len(validation)==6
 assert list(validation[validation['Period']=='Newest quarter of dates']['Evaluated games'])==[3,3,3]
 assert any(d.label=='Download full validation CSV' for d in at.get('download_button'))
 assert any(d.label=='Download pick reliability CSV' for d in at.get('download_button'))
 assert at.session_state['validation_report']['pick_reliability']
 assert any(d.label=='Download scoring-stage diagnostics CSV' for d in at.get('download_button'))
 assert len(at.session_state['validation_report']['scoring_stages'])==6
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(100).run()
 assert any('Run full model validation again' in x.value for x in at.info)
 assert not any('Period' in d.value.columns for d in at.dataframe)
 next(s for s in at.selectbox if s.label=='Minimum training games before evaluation').set_value(30).run()
 with patch.object(core,'request',side_effect=AssertionError('Signal experiment must not fetch APIs')):
  next(b for b in at.button if b.label=='Compare opening-shot vs first-score signals').click().run()
 assert not at.exception,list(at.exception)
 signal=at.session_state['signal_comparison']
 assert len(signal['summary'])==8
 assert signal['adaptive_learned_games']==0
 assert any(d.label=='Download adaptive signal decisions CSV' for d in at.get('download_button'))
 assert signal['model']=='baseline'
 assert next(s for s in at.selectbox if s.label=='Scoring model').value=='baseline'
 assert any(d.label=='Download signal comparison CSV' for d in at.get('download_button'))
 assert any(d.label=='Download signal predictions CSV' for d in at.get('download_button'))
 next(s for s in at.selectbox if s.label=='Scoring model').set_value('recent').run()
 assert any('Run the signal comparison again' in x.value for x in at.info)
 assert not any(d.label=='Download signal comparison CSV' for d in at.get('download_button'))
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
