"""Descriptive prospective metrics; fixtures excluded unless explicitly requested."""
from datetime import timedelta
import math
import phase2,research_tools as rt
from phase5_providers import stamp
from phase5_protocol import safe_json

def evaluate(journal,receipts=None,test=False):
    receipts=receipts or {};preds=[r for r in journal.rows('prediction') if r['payload']['test_only']==test];results={}
    for r in journal.rows('result'):
        if r['payload']['test_only']==test:results[r['payload']['prediction_hash']]=r['payload']
    eligible=[];excluded=[];pending=0;chosen={};registered={r['hash']:r for r in journal.rows('protocol')}
    for r in preds:
        p=r['payload'];tip=stamp(p['game']['start_time']);generated=stamp(p['generated_at']);receipt=receipts.get(r['hash']);reg=registered.get(p['protocol_hash'])
        if not test and (not receipt or max(stamp(receipt['committed_at']),stamp(receipt['verified_remote_at']))>tip-timedelta(seconds=30)):
            excluded.append({'forecast':r['hash'],'reason':'No verified durable pre-tip Git receipt'});continue
        if not reg or generated<stamp(reg['created_at']) or p['model_version']!=reg['payload']['version'] or generated>stamp(r['created_at']) or stamp(r['created_at'])>tip-timedelta(seconds=30):
            excluded.append({'forecast':r['hash'],'reason':'Protocol/version/timestamp mismatch'});continue
        # Primary selection happens BEFORE consulting outcomes.
        lead=(tip-generated).total_seconds()
        if 30<=lead<=600 and p['training_games']>=100:
            key=(p['experiment'],p['game']['gameId'])
            if key not in chosen or generated>stamp(chosen[key]['payload']['generated_at']):chosen[key]=r
        result=results.get(r['hash'])
        if not result:pending+=1;continue
        if not result['eligible_for_metrics']:
            excluded.append({'forecast':r['hash'],'reason':result['reason']});continue
        winner=result['result']['scorer_id'];winner=winner if winner in p['first_shot_proxy'] else 'OTHER'
        eligible.append({'Game':p['game']['gameId'],'Date':p['game']['_date'],'Winner':winner,'hash':r['hash'],'Snapshot':p['snapshot_type'],'Version':p['model_version'],'Cohort':p['cohort'],'first_fg':result['result'].get('first_field_goal',{}),'first_shot':p['first_shot_proxy'],**p['forecasts']})
    primary={r['hash'] for r in chosen.values()};rows=[r for r in eligible if r['hash'] in primary]
    labels=['Baseline','Calibrated Baseline','Simple proxy','Pure Monte Carlo','Hybrid','Uniform','Literal V2.44 Baseline']
    summary=[];calibration=[];comparisons=[]
    groups=[('Primary','All',rows)]
    for dim in ['Snapshot','Version','Cohort']:
        for value in sorted({r[dim] for r in eligible}):groups.append((dim,value,[r for r in eligible if r[dim]==value]))
    for label in ['below 15%','15–25%','above 25%']:
        groups.append(('Baseline confidence',label,[r for r in rows if ('below 15%' if max(r['Baseline'].values())<.15 else '15–25%' if max(r['Baseline'].values())<=.25 else 'above 25%')==label]))
    for month in sorted({r['Date'][:7] for r in rows}):groups.append(('Month',month,[r for r in rows if r['Date'].startswith(month)]))
    for dim,value,subset in groups:
        for label in labels:
            m=phase2.metrics(subset,label);metrics=m['metrics'];metrics['Top-5 %']=100*sum(rt.top_k_credit(r[label],r['Winner'],5) for r in subset)/len(subset) if subset else None
            summary.append({'Dimension':dim,'Group':value,'Model':label,**metrics})
            if dim=='Primary':calibration.extend({'Model':label,**b} for b in m['calibration'])
    if rows:
        b=phase2.metrics(rows,'Baseline')
        for label in labels[1:]:
            c=phase2.metrics(rows,label);finite=all(math.isfinite(r['Log loss']) for r in b['games']+c['games'])
            comparisons.append({'Model':label,**rt.compare_evaluations(b,c,metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if finite else ('Brier','Top-1 credit','Top-3 credit'))})
    first=[r for r in rows if r['first_fg'].get('identity_known') and r['first_fg'].get('before_first_score')]
    return safe_json({'test_only':test,'predictions':len(preds),'graded_snapshots':len(eligible),'primary_games':len(rows),'pending':pending,'summary':summary,'calibration':calibration,'paired_intervals':comparisons,'excluded':excluded,'first_shot_games':len(first),'first_shot_accuracy':sum(rt.top_k_credit(r['first_shot'],r['first_fg']['player_id'],1) if r['first_fg']['player_id'] in r['first_shot'] else 0 for r in first)/len(first) if first else None,'milestone_reached':len(rows)>=300 and len({r['Date'] for r in rows})>=30,'roi':None,'warning':'Fixture demonstration only' if test else 'Descriptive research. Snapshot groups can repeat games; primary uses one forecast per game. No validated betting edge.'})
