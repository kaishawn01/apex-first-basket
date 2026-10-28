"""Reconcile preserved raw sources against the ledger; never modify forecasts or sources."""
import json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import phase4_data as data,phase4_forward as forward
h,s,records=data.dataset(ROOT/'data/phase4');counts=Counter();issues=[]
for gid,r in records.items():
 paths=[ROOT/'data/phase4/raw'/(gid+'.json'),ROOT/'data/phase3_validation'/(gid+'.json'),ROOT/'data/v3_validation'/(gid+'.json')]
 path=next((p for p in paths if p.exists()),None)
 if not path:issues.append({'game':gid,'reason':'Raw source unavailable'});continue
 p=json.loads(path.read_text());p=p.get('payload',p)
 if data.digest(p)!=r['source']['raw_hash']:issues.append({'game':gid,'reason':'Raw hash mismatch'});continue
 counts['raw_sources_verified']+=1
 athletes=[a for t in p.get('boxscore',{}).get('players',[]) for st in t.get('statistics',[]) for a in st.get('athletes',[])]
 counts['sources_with_explicit_bench_rows']+=int(any(a.get('starter') is False for a in athletes))
 ordered=sorted((x for x in p.get('plays',[]) if x.get('period',{}).get('number')==1),key=lambda x:int(x['sequenceNumber']))
 index=next((i for i,x in enumerate(ordered) if x.get('scoringPlay') and x.get('scoreValue',0)>0),None)
 if index is None:issues.append({'game':gid,'reason':'No raw first score'});continue
 play=ordered[index];pid=str(play.get('participants',[{}])[0].get('athlete',{}).get('id',''))
 states={a.get('starter') for a in athletes if str(a.get('athlete',{}).get('id',''))==pid}
 counts['raw_first_scorer_starter' if states=={True} else 'raw_first_scorer_bench' if states=={False} else 'raw_first_scorer_unknown']+=1
 counts['substitution_before_first_score']+=int(any(' enters the game for ' in x.get('text','').lower() or 'substitution' in x.get('type',{}).get('text','').lower() for x in ordered[:index]))
 if r['status']=='resolved' and pid!=r['scorer_id']:issues.append({'game':gid,'reason':'Raw scorer mismatch'})
 counts['first_fg_identity_known']+=int(data.first_fg_fact(p)['identity_known'])
j=forward.Journal(ROOT/'data/phase4/forward.sqlite3');snaps=j.rows('snapshot');preds=j.rows('prediction')
report={'coverage':data.coverage(ROOT/'data/phase4'),'raw_audit':dict(counts),'issues':issues,'snapshots':len(snaps),'provider_confirmed_snapshots':sum(x['payload']['readiness']['provider_verified'] for x in snaps),'prospective_predictions':len(preds),'graded_games':forward.evaluation(j)['graded_games'],'snapshot_times':[min(x['created_at'] for x in snaps),max(x['created_at'] for x in snaps)] if snaps else [],'limitations':['One provider only; postgame starter flags are not independent confirmation.','Bounded seasonal windows, not complete seasons.','No resolved bench outcomes observed; four ambiguous outcomes remain. This does not establish that bench first scores are impossible.','Eight missing cached games restored after the original frozen run; see inventory audit.']}
(ROOT/'validation/PHASE4_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='coverage'},indent=2))
