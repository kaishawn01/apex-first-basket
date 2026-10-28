"""Descriptive diagnostics only; never changes the frozen Phase 3 selection."""
import sys,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import phase3,phase2,research_tools as rt,first_basket_engine as eng,opening_data
folder=ROOT/'data/phase3_validation'
validation=json.loads((folder/'validation_forecasts.json').read_text());test=json.loads((folder/'test_forecasts.json').read_text());history=eng.read_csv(folder/'history.csv')
def first_comparison(rows):
 usable=[]
 for row in rows:
  if row['First shooter']:
   usable.append({**row,'Winner':row['First shooter'],'Simple first shot':row['Ablations']['simple:90']})
 a=phase2.metrics(usable,'Simple first shot');results=[]
 for label in ('Phase 2 first shot','First shot'):
  b=phase2.metrics(usable,label)
  results.append({'model':label,'simple_metrics':a['metrics'],'candidate_metrics':b['metrics'],'paired':rt.compare_evaluations(a,b,metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if all(math.isfinite(g['Log loss']) for x in (a,b) for g in x['games']) else ('Brier','Top-1 credit','Top-3 credit'))})
 return results
old=json.loads((ROOT/'data/v3_validation/phase2_report.json').read_text())
oldids={r['Game'] for r in old['details']};matched=[r for r in validation if r['Game'] in oldids];ids={r['Game'] for r in matched}
original={name:rt.evaluation_metrics([r for r in old['details'] if r['Model']==name and r['Game'] in ids]) for name in ('Baseline','Selected hybrid')}
selection=json.loads((ROOT/'validation/PHASE3_SELECTION.json').read_text())
report={'development_diagnosis':phase3.diagnose(validation,history),'test_diagnosis_descriptive_only':phase3.diagnose(test,history),'development_first_shot_intervals':first_comparison(validation),'test_first_shot_intervals':first_comparison(test),'comparable_known_december':{'games':len(matched),'original_phase2':original,'phase3_same_games':phase3.summarize(matched,selection),'note':'Same target games, expanded/repaired earlier training; not an untouched test or a controlled single-feature attribution.'}}
sequences=opening_data.load(folder/'sequences.json')
report['opening_exposure_groups']=[{'exposure':label,'simple':phase3.shot_metrics([r for r in test if phase3.opening_exposure(sequences.get(r['Game']))==label],'simple:90'),'phase2':phase3.shot_metrics([r for r in test if phase3.opening_exposure(sequences.get(r['Game']))==label],'Phase 2 first shot')} for label in sorted({phase3.opening_exposure(sequences.get(r['Game'])) for r in test})]
(ROOT/'validation/PHASE3_DIAGNOSTICS.json').write_text(json.dumps(report,indent=2)+'\n')
print('Diagnostics saved; no model settings changed')
