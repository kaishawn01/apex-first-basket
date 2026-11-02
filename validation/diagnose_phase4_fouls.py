"""Additional predeclared component check on known January; never selects a model."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import phase4_research as research,first_basket_engine as eng,outcome_data,opening_data
folder=ROOT/'data/phase3_validation';h=eng.read_csv(folder/'history.csv');s=opening_data.load(folder/'sequences.json');r=outcome_data.load(folder/'outcomes.json')
research.VARIANTS=('reference','neutral_foul_frequency')
report=research.ablate(h,s,r,'2026-01-01','2026-01-21',progress=lambda s:print(s,flush=True))
(ROOT/'validation/PHASE4_FOUL_DIAGNOSTIC.json').write_text(json.dumps(report,indent=2)+'\n')
