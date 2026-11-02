"""Reserved February evaluation with already-frozen Phase 3 settings; no refitting."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import phase4_data as data,phase3,simulation,research_tools as rt
folder=ROOT/'data/phase4';protocol=json.loads((ROOT/'validation/PHASE4_LOCK.json').read_text());selection=json.loads((ROOT/'validation/PHASE3_SELECTION.json').read_text())
assert (selection['weight'],selection['temperature'],selection['baseline_temperature'],selection['selector'],selection['half_life'])==(.5,1.25,1.25,'simple',90)
start,end=protocol['final_test']
# All settings and sample boundaries were persisted before any request for this period.
collection=data.collect(start,end,folder,limit=150,progress=lambda s:print(s,flush=True));print('Reserved collection',collection,flush=True)
h,s,r=data.dataset(folder)
forecasts,exclusions=phase3.forecasts(h,s,r,simulation.SimulationConfig(trials=protocol['trials'],seed=protocol['seed']),start,end,protocol['minimum_prior_games'],progress=lambda s:print(s,flush=True))
(folder/'frozen_forecasts.json').write_text(json.dumps(forecasts))
report=phase3.summarize(forecasts,selection);report.update(protocol=protocol,selection_source='Previously frozen Phase 3, no Phase 4 fitting',collection=collection,coverage=data.coverage(folder),exclusions=exclusions,dataset_fingerprint=rt.fingerprint(r),training_audit=[{'Game':x['Game'],'Date':x['Date'],'Last training date':x['Last training date'],'Training games':x['Training games']} for x in forecasts])
(ROOT/'validation/PHASE4_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
print('FROZEN EVALUATION COMPLETE',len(forecasts),flush=True)
