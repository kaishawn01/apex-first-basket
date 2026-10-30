"""Frozen Phase 3 experiment; public requests are cached, bounded and stop on 429.
Run from repo root. Existing data/ CSVs are never replaced. Test fetch follows lock.
"""
import sys,json,time,threading,concurrent.futures
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import requests
import first_basket_engine as eng
import outcome_data as od,opening_data,phase3,simulation,research_tools as rt
folder=ROOT/'data'/'phase3_validation';folder.mkdir(parents=True,exist_ok=True)
lock=json.loads((ROOT/'validation/PHASE3_LOCK.json').read_text());errors=[];stop=threading.Event()
def dump(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def get(url,params,path):
 if path.exists():return json.loads(path.read_text())
 if stop.is_set():raise ValueError('Provider rate limit: collection stopped; retry later')
 time.sleep(.15)
 r=requests.get(url,params=params,timeout=25)
 if r.status_code==429:stop.set()
 r.raise_for_status();p=r.json();dump(path,p);return p

def fetch_period(start,end):
 games={};day=date.fromisoformat(start)
 while day<=date.fromisoformat(end):
  try:
   p=get(eng.ESPN_BASE+'/scoreboard',{'dates':day.strftime('%Y%m%d'),'limit':1000},folder/('schedule_'+day.isoformat()+'.json'))
   for g in eng.parse_espn_schedule(p):
    if g['gameStatus']==3 and start<=g['_date']<=end:games[g['gameId']]=g
  except Exception as e:errors.append({'date':day.isoformat(),'reason':str(e)})
  day+=timedelta(days=1)
 def fetch(g):
  try:return g,get(eng.ESPN_BASE+'/summary',{'event':g['gameId'].removeprefix('espn_')},folder/(g['gameId']+'.json')),None
  except Exception as e:return g,None,str(e)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for g,p,error in pool.map(fetch,sorted(games.values(),key=lambda g:(g['_date'],g['gameId']))):
   if error:errors.append({'game':g['gameId'],'reason':error})
   else:ingest(g,p)
 return len(games)
records={};hist=[];sequences={}
def ingest(g,p):
 gid=g['gameId']
 if gid in records:return
 try:
  rec=od.extract(g,p);records[gid]=rec
  # Legacy conditional models retain their audited rows; complete labels stay in independent ledger.
  if rec['status']=='resolved' and rec['rows'] and sum(int(r['first_scorer']) for r in rec['rows'])==1:
   valid,bad=rt.audit(rec['rows'])
   if bad:raise ValueError(bad[0]['reason'])
   hist.extend(valid)
   try:sequences[gid]=opening_data.extract(g,p)
   except Exception as e:errors.append({'game':gid,'scope':'opening sidecar','reason':str(e)})
 except Exception as e:errors.append({'game':gid,'reason':str(e)})
for path in sorted((ROOT/'data/v3_validation').glob('espn_*.json')):
 try:
  p=json.loads(path.read_text());g=od.game_from_payload(p)
  if g['_date']<=lock['development_end']:ingest(g,p)
 except Exception as e:errors.append({'game':path.stem,'reason':str(e)})
print('Cached development outcomes',len(records),flush=True)
earlier=fetch_period(lock['earlier_training_start'],lock['earlier_training_end'])
print('Earlier scheduled',earlier,'total ledger',len(records),flush=True)
od.write(records,folder/'development_outcomes.json');opening_data.write(sequences,folder/'development_sequences.json');eng.write_csv(folder/'development_history.csv',eng.FIELDS,hist)
cfg=simulation.SimulationConfig(trials=lock['trials'],seed=lock['seed'])
validation,excluded=phase3.forecasts(hist,sequences,records,cfg,start='2025-11-01',end=lock['development_end'],min_training=lock['minimum_prior_games'],progress=lambda s:print(s,flush=True))
dump(folder/'validation_forecasts.json',validation)
selection=phase3.lock_selection(validation)
selection['development_fingerprint']=rt.fingerprint(records)
path=ROOT/'validation/PHASE3_SELECTION.json'
if path.exists():
 if json.loads(path.read_text())!=selection:raise ValueError('Locked selection changed: stop rather than retune on known test data')
else:dump(path,selection)
dump(folder/'validation_forecasts.json',validation)
dump(ROOT/'validation/PHASE3_DEVELOPMENT.json',{'selection':selection,'audit':od.audit(records),'excluded':excluded,'errors':list(errors),'ablations':phase3.ablation_report(validation),'known_december_comparison':phase3.summarize([r for r in validation if '2025-12-01'<=r['Date']<='2025-12-21'],selection)})
print('SELECTION LOCKED',selection['weight'],selection['temperature'],flush=True)
# First access to the genuinely reserved test period comes after the selection lock above.
test_scheduled=fetch_period(lock['test_start'],lock['test_end'])
od.write(records,folder/'outcomes.json');opening_data.write(sequences,folder/'sequences.json');eng.write_csv(folder/'history.csv',eng.FIELDS,hist)
test,excluded=phase3.forecasts(hist,sequences,records,cfg,start=lock['test_start'],end=lock['test_end'],min_training=lock['minimum_prior_games'],progress=lambda s:print(s,flush=True))
dump(folder/'test_forecasts.json',test)
report=phase3.summarize(test,selection)
report.update(selection=selection,ledger_audit=od.audit(records),test_audit=od.audit({g:r for g,r in records.items() if lock['test_start']<=r['date']<=lock['test_end']}),scheduled_test_games=test_scheduled,exclusions=excluded,errors=errors,fingerprint=rt.fingerprint(records),protocol=lock)
dump(ROOT/'validation/PHASE3_RESULTS.json',report)
print('DONE',len(test),'test games',flush=True)
