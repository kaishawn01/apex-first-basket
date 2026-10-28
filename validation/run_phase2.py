"""Reproduce the predeclared Phase 2 experiment. Public ESPN; no paid API keys.
First run python validation/run_public_sample.py for the development sample.
The final December sample is fetched only AFTER validation settings are locked.
"""
import sys,json,concurrent.futures
from pathlib import Path
from datetime import date,timedelta,datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import requests
import first_basket_engine as eng
import research_tools as rt
import simulation,phase2,opening_data
folder=ROOT/'data'/'v3_validation';lock=json.loads((ROOT/'validation/PHASE2_LOCK.json').read_text())
old=eng.read_csv(folder/'history.csv');old=[r for r in old if r['date']<lock['final_test_start']]
if not old:raise SystemExit('Development history missing; run validation/run_public_sample.py first.')
groups={}
for r in old:groups.setdefault(r['game_id'],[]).append(r)
sequences={};errors=[]
def game_from_payload(gid,p):
 c=p['header']['competitions'][0];sides={x['homeAway']:eng.espn_team(x['team']) for x in c['competitors']}
 day=datetime.fromisoformat(c['date'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
 return {'gameId':gid,'_date':day,'start_time':c['date'],'homeTeam':{'teamTricode':sides['home']},'awayTeam':{'teamTricode':sides['away']}}
for gid,rows in groups.items():
 try:
  p=json.loads((folder/(gid+'.json')).read_text());record=opening_data.extract(game_from_payload(gid,p),p)
  if not opening_data.valid_for_history(record,rows):raise ValueError('Historical identity mismatch')
  sequences[gid]=record
 except Exception as e:errors.append({'game':gid,'reason':str(e)})
print('Development sequences',len(sequences),'events',sum(len(r['events']) for r in sequences.values()),flush=True)
cfg=simulation.SimulationConfig(trials=lock['trials'],seed=lock['seed'])
validation,_=phase2.forecast_history(old,sequences,cfg,lock['minimum_prior_games'])
selected=phase2.select(validation,lock['weights'],lock['temperatures'])
selection_path=ROOT/'validation/PHASE2_SELECTION.json'
if selection_path.exists():
 previous=json.loads(selection_path.read_text())
 if selected!=previous:raise ValueError('Locked settings changed. Do not silently retune after test inspection.')
else:selection_path.write_text(json.dumps(selected,indent=2)+'\n')
print('LOCKED VALIDATION SELECTION',selected['weight'],selected['temperature'],selected['validation_games'],flush=True)
def get(url,params):
 r=requests.get(url,params=params,timeout=20);r.raise_for_status();return r.json()
def schedule(day):
 try:return eng.parse_espn_schedule(get(eng.ESPN_BASE+'/scoreboard',{'dates':day.replace('-',''),'limit':1000})),None
 except Exception as e:return [],{'date':day,'reason':str(e)}
start=date.fromisoformat(lock['final_test_start']);end=date.fromisoformat(lock['final_test_end'])
days=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)];games={}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for found,error in pool.map(schedule,days):
  if error:errors.append(error)
  for g in found:
   if g['gameStatus']==3 and g['_date'] in days:games[g['gameId']]=g
print('Final test scheduled games',len(games),flush=True)
def fetch_game(g):
 try:
  path=folder/(g['gameId']+'.json');p=json.loads(path.read_text()) if path.exists() else get(eng.ESPN_BASE+'/summary',{'event':g['gameId'].removeprefix('espn_')})
  if not path.exists():path.write_text(json.dumps(p))
  record=opening_data.extract(g,p);play,box=eng.espn_game_payloads(p);rows=eng.extract_game(g,play,box)
  valid,bad=rt.audit(rows)
  if bad:raise ValueError(bad[0]['reason'])
  if not opening_data.valid_for_history(record,rows):raise ValueError('Sequence identity mismatch')
  return rows,record,None
 except Exception as e:return [],None,{'game':g['gameId'],'reason':str(e)}
history=list(old)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for i,(rows,record,error) in enumerate(pool.map(fetch_game,sorted(games.values(),key=lambda g:(g['_date'],g['gameId']))),1):
  history.extend(rows)
  if record:sequences[record['game_id']]=record
  if error:errors.append(error)
  if i%25==0:print('Test games processed',i,flush=True)
eng.write_csv(folder/'phase2_history.csv',eng.FIELDS,history);opening_data.write(sequences,folder/'phase2_sequences.json')
def check_lock(result):
 for k,v in selected.items():
  if result[k]!=v:raise ValueError('Selection changed before test evaluation')
report=phase2.evaluate_holdout(history,sequences,start.isoformat(),end.isoformat(),cfg,lock['minimum_prior_games'],on_lock=check_lock)
report['source']={'development_games':len(old)//10,'scheduled_test_games':len(games),'accepted_test_games':(len(history)-len(old))//10,'sequence_games':len(sequences),'errors':errors,'archived_pre_tip_confirmations':0,'early_substitution_before_first_score_games':sum(bool(r.get('substitution_before_first_score')) for r in sequences.values())}
(folder/'phase2_report.json').write_text(json.dumps(report,indent=2))
small={k:v for k,v in report.items() if k not in ('details','diagnostics')}
(ROOT/'validation/PHASE2_RESULTS.json').write_text(json.dumps(small,indent=2)+'\n')
print(json.dumps({'selection':selected,'summary':report['summary'],'first_shot':report['first_shot'],'source':report['source']},indent=2),flush=True)
