"""Optional public ESPN validation sample, 2025-10-21 through 2025-11-30.
Uses no paid API keys. Caches raw responses and writes only data/v3_validation.
Run from the repository root; network access required, no retry bypass.
"""
import sys,json,requests,concurrent.futures
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import first_basket_engine as eng
import research_tools as research
import simulation
folder=ROOT/'data'/'v3_validation';folder.mkdir(parents=True,exist_ok=True)
def get(url,params):
 r=requests.get(url,params=params,timeout=20);r.raise_for_status();return r.json()
def schedule(day):
 try:return eng.parse_espn_schedule(get(eng.ESPN_BASE+'/scoreboard',{'dates':day.replace('-',''),'limit':1000})),None
 except Exception as e:return [],{'date':day,'reason':str(e)}
days=[(date(2025,10,21)+timedelta(days=i)).isoformat() for i in range(41)]
games={};errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for found,error in pool.map(schedule,days):
  if error:errors.append(error)
  for g in found:
   if g['gameStatus']==3 and g['_date'] in days:games[g['gameId']]=g
print('Schedule games',len(games),'errors',len(errors),flush=True)
def load_game(g):
 cache=folder/(g['gameId']+'.json')
 try:
  p=json.loads(cache.read_text()) if cache.exists() else get(eng.ESPN_BASE+'/summary',{'event':g['gameId'].removeprefix('espn_')})
  if not cache.exists():cache.write_text(json.dumps(p))
  eng.validate_espn_summary(g,p)
  c=p['header']['competitions'][0]
  actual=eng.datetime.fromisoformat(c['date'].replace('Z','+00:00')).astimezone(eng.ZoneInfo('America/New_York')).date().isoformat()
  if actual!=g['_date']:raise ValueError('Summary date mismatch')
  play,box=eng.espn_game_payloads(p);rows=eng.extract_game(g,play,box);valid,bad=research.audit(rows)
  if bad:raise ValueError(bad[0]['reason'])
  return valid,None
 except Exception as e:return [],{'game':g['gameId'],'date':g['_date'],'reason':str(e)}
history=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for i,(rows,error) in enumerate(pool.map(load_game,sorted(games.values(),key=lambda g:(g['_date'],g['gameId']))),1):
  history.extend(rows)
  if error:errors.append(error)
  if i%25==0:print('Imported',i,'games; accepted',len(history)//10,flush=True)
eng.write_csv(folder/'history.csv',eng.FIELDS,history)
(folder/'import_report.json').write_text(json.dumps({'scheduled_games':len(games),'accepted_games':len(history)//10,'errors':errors},indent=2))
report=simulation.backtest(history,100,simulation.SimulationConfig(trials=2000))
(folder/'backtest.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'scheduled':len(games),'accepted':len(history)//10,'errors':len(errors),'evaluated':report['evaluated_games'],'summary':report['summary']},indent=2),flush=True)
