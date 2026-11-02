"""Seed a separate immutable source ledger, expand development first; test fetched separately."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import phase4_data as data,outcome_data as od
folder=ROOT/'data/phase4';lock=json.loads((ROOT/'validation/PHASE4_LOCK.json').read_text())
seen=set()
for parent in ('data/v3_validation','data/phase3_validation'):
 for path in sorted((ROOT/parent).glob('espn_*.json')):
  if path.stem in seen:continue
  seen.add(path.stem)
  try:
   p=json.loads(path.read_text());data.ingest(od.game_from_payload(p),{'payload':p,'retrieved_at':None,'provider_date':None},folder)
  except Exception as e:data.failure(folder,path.stem,'seed',str(e))
print('Seeded',data.coverage(folder)['games'],flush=True)
for start,end in lock['development_periods']+ [lock['current_season_collection']]:
 print('Collect',start,end,flush=True);print(data.collect(start,end,folder,limit=150,progress=lambda s:print(s,flush=True)),flush=True)
(ROOT/'validation/PHASE4_DEVELOPMENT_COVERAGE.json').write_text(json.dumps(data.coverage(folder),indent=2)+'\n')
print('DEVELOPMENT COLLECTION COMPLETE',flush=True)
