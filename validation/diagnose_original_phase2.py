"""Known December sample: diagnostic ablations, never an untouched evaluation."""
import sys,json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import first_basket_engine as eng,opening_data,phase2,phase3,simulation,research_tools as rt
history=eng.read_csv(ROOT/'data/v3_validation/phase2_history.csv');sequences=opening_data.load(ROOT/'data/v3_validation/phase2_sequences.json')
groups=defaultdict(list)
for r in history:
 if '2025-12-01'<=r['date']<='2025-12-21':groups[r['game_id']].append(r)
rows=[]
for gid,target in sorted(groups.items()):
 day=target[0]['date'];train=rt.history_window(history,day);lineups={t:[r for r in target if r['team']==t] for t in sorted({r['team'] for r in target})}
 report=phase2.simulate(train,lineups,day,sequences,simulation.SimulationConfig(trials=2000,seed=3000));cache={}
 first=next((r['player_id'] for r in target if int(r['first_game_shot'])),None)
 if target[0]['opening_score_path'] not in ('opening_fg_made','opening_fg_missed'):first=None
 ablations={f'{mode}:{half}':phase3.selector(train,lineups,day,report['inputs'],mode,half,_cache=cache)[0] for mode in phase3.SELECTORS for half in (30,90,180)}
 rows.append({'Date':day,'Game':gid,'First shooter':first,'Phase 2 first shot':report['first_shot'],'First shot':report['inputs']['first_shot_reference'],'Ablations':ablations,'Target lineups':{t:[r['player_id'] for r in rs] for t,rs in lineups.items()},'Player teams':{r['player_id']:r['team'] for r in target}})
print('Original metrics',phase3.shot_metrics(rows,'Phase 2 first shot'),phase3.shot_metrics(rows,'First shot'),flush=True)
result={'purpose':'Descriptive diagnosis of the already-known Phase 2 test. No model selection or held-out claim.','games':len(rows),'ablations':phase3.ablation_report(rows),'diagnosis':phase3.diagnose(rows,history)}
(ROOT/'validation/PHASE3_ORIGINAL_ABLATION.json').write_text(json.dumps(result,indent=2)+'\n')
