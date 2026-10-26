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
 assert set(ranking['Status'])=={'HOLD: SAMPLE'}
 next(b for b in at.button if b.label=='Save confirmed forecasts to journal').click().run()
 assert not at.exception,list(at.exception)
 assert len(research.journal_records())==1
 next(b for b in at.button if b.label=='Save confirmed forecasts to journal').click().run()
 assert len(research.journal_records())==1
 assert any(d.label=='Download forward journal CSV' for d in at.get('download_button'))
 print('Journal UI passed: save, duplicate prevention, table, CSV export.')
 at.multiselect[0].set_value(['10','11','12','13','15']).run()
 assert not next(cb for cb in at.checkbox if cb.label.startswith('I verified BOS')).value
 assert any('Inputs changed' in x.value for x in at.info)
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
 print('Backtest UI passed: evaluation, comparison table, CSV export.')
