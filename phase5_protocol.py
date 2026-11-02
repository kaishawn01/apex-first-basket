"""Prospective experiment registration and one-forecast-per-game evaluation."""
import math,hashlib,json
from pathlib import Path
from datetime import datetime,timedelta
from dataclasses import asdict
import phase2,simulation,research_tools as rt
from phase4_data import digest
from phase5_store import utc
import first_basket_engine as eng

EXPERIMENT='apex-v3.0.4-prospective-01'
MODEL_FILES=('first_basket_engine.py','dashboard_core.py','research_tools.py','simulation.py','phase2.py','phase3.py','phase4_forward.py','phase5_providers.py','phase5_protocol.py','phase5_runner.py')

def specification():
    return {'experiment':EXPERIMENT,'version':'3.0.4','models':['Baseline','Calibrated Baseline','Simple proxy','Pure Monte Carlo','Hybrid','Uniform'],'literal_baseline_supplement':True,
        'simulation':asdict(simulation.SimulationConfig(trials=2000,seed=3000)),'selected_weight':.5,'temperature':1.25,'baseline_temperature':1.25,'selector':'simple','selector_half_life_days':90,'history_window_days':400,'same_day_training':False,'minimum_prior_games':100,
        'first_shot_target':'First FG attempt before first score; known nonselected shooters count as misses','other_prior':[.5,49.5],'unresolved_policy':'Existing baseline fallback followed by explicit Other allocation',
        'checkpoint_minutes':[60,30,10,2],'checkpoint_lateness_seconds':180,'final_lateness_seconds':90,'minimum_lead_seconds':30,
        'primary_selection':'Latest archived forecast generated 30–600 seconds before the unchanged scheduled start; one per game, chosen without results',
        'inclusion':'Real NBA regular-season completed games; immutable forecast after registration and before tip; 10 valid current-roster identities; at least 100 earlier training games; resolved actual scorer. All lineup evidence cohorts retained and reported separately.',
        'unverified_policy':'Include as research in projected/manual/incomplete cohorts; no actionable recommendation. Missing injuries are flagged, not silently treated as healthy.',
        'exclusions':'No primary-window forecast, source/model drift, insufficient training, invalid identity, rescheduled start, incomplete/nonregular result, unresolved scoring identity. No exclusion based on forecast correctness.',
        'cohorts':['provider-confirmed','manual','projected','incomplete'],'primary_metrics':['Log loss','Brier'],'primary_comparison':'Pure Monte Carlo minus Baseline + Other','secondary_metrics':['Top-1 credit','Top-3 credit','first-shot accuracy','calibration ECE'],'secondary_comparisons':'Calibrated baseline, simple proxy, hybrid and uniform versus Baseline + Other; exploratory and unadjusted',
        'intervals':'Paired bootstrap of game-date clusters, 1000 draws, existing compare_evaluations fixed seed; report sample sizes and zero-probability outcomes without epsilon smoothing',
        'milestone_games':300,'milestone_min_dates':30,'review_milestones':[300,600,1000],'interim_policy':'Operational/descriptive only. No promotion or refitting at interim looks; continued looks are not independent tests.',
        'precision_plan':'At 300 games and 15% accuracy, normal-reference half-width is about 4.0 percentage points. Paired score precision depends on observed variance and date clustering. Continue if uncertainty remains; do not treat 300 as sufficient evidence of an edge.',
        'evaluation_timing':'Grade only provider-completed games after scheduled start; preserve result versions; primary forecast selected independently of results. No retrospective backfills.',
        'source_hashes':{name:hashlib.sha256((eng.ROOT/name).read_bytes()).hexdigest() for name in MODEL_FILES}}

def register(store):
    import updater
    if updater.current_version()!='3.0.4':raise ValueError('Version differs from the registered Phase 5 model')
    current=specification();old=store.get('protocol',EXPERIMENT)
    if old:
        if old['payload']['specification']!=current:raise ValueError('Frozen experiment differs from current code/settings; declare a new experiment')
        return old
    return store.append('protocol',EXPERIMENT,{'specification':current,'registered_at':utc(store.clock()).isoformat(),'historical_phase4_test_modified':False})

def active(store):
    import updater
    if updater.current_version()!='3.0.4':raise ValueError('Version differs from frozen experiment')
    saved=store.get('protocol',EXPERIMENT)
    if not saved:raise ValueError('Register the prospective experiment before collecting forecasts')
    if saved['payload']['specification']!=specification():raise ValueError('Frozen model/feature code changed; collection stopped until a new experiment is declared')
    return saved

def primary_predictions(store):
    protocol=store.get('protocol',EXPERIMENT)
    if not protocol:return {},[]
    start=datetime.fromisoformat(protocol['created_at']);chosen={};excluded=[]
    for r in store.rows('prediction'):
        p=r['payload'];gid=p['game']['gameId']
        if p.get('experiment')!=EXPERIMENT:continue
        generated=datetime.fromisoformat(p['generated_at']);tip=datetime.fromisoformat(p['game']['start_time'].replace('Z','+00:00'));lead=(tip-generated).total_seconds()
        if datetime.fromisoformat(r['created_at'])>tip-timedelta(seconds=30) or generated<start or p.get('protocol_hash')!=protocol['hash'] or not 30<=lead<=600:
            excluded.append({'game':gid,'forecast':r['hash'],'reason':'Outside registered primary time window or protocol mismatch'});continue
        if p.get('training_games',0)<100:
            excluded.append({'game':gid,'forecast':r['hash'],'reason':'Fewer than 100 strictly earlier training games'});continue
        if gid not in chosen or generated>datetime.fromisoformat(chosen[gid]['payload']['generated_at']):chosen[gid]=r
    return chosen,excluded

def safe_json(value):
    if isinstance(value,float) and not math.isfinite(value):return 'Infinity' if value>0 else '-Infinity' if value<0 else None
    if isinstance(value,dict):return {k:safe_json(v) for k,v in value.items()}
    if isinstance(value,list):return [safe_json(x) for x in value]
    return value

def evaluate(store):
    selected,excluded=primary_predictions(store);results={}
    for r in store.rows('result'):results[r['payload']['prediction_hash']]=r['payload']
    rows=[];pending=0
    for gid,event in selected.items():
        p=event['payload'];result=results.get(event['hash'])
        if not result:pending+=1;continue
        if not result['eligible_for_metrics']:
            excluded.append({'game':gid,'forecast':event['hash'],'reason':result['reason']});continue
        actual=result['result'];winner=actual['scorer_id'] if actual['scorer_id'] in p['first_shot_proxy'] else 'OTHER'
        rows.append({'Game':gid,'Date':p['game']['_date'],'Winner':winner,'cohort':p['cohort'],'first_fg':actual.get('first_field_goal',{}),'proxy':p['first_shot_proxy'],'first_mc':p['simulated_first_shot'],**p['forecasts']})
    labels=specification()['models']+['Literal V2.44 Baseline'];summary=[];calibration=[];comparisons=[];over_time=[]
    for cohort,subset in [('All',rows)]+[(c,[r for r in rows if r['cohort']==c]) for c in specification()['cohorts']]:
        evaluated={label:phase2.metrics(subset,label) for label in labels}
        for label,result in evaluated.items():
            summary.append({'Cohort':cohort,'Model':label,**result['metrics']})
            calibration.extend({'Cohort':cohort,'Model':label,**b} for b in result['calibration'])
        if subset:
            for label in labels[1:]:
                finite=all(math.isfinite(x['Log loss']) for l in ('Baseline',label) for x in evaluated[l]['games'])
                comparisons.append({'Cohort':cohort,'Model':label,**rt.compare_evaluations(evaluated['Baseline'],evaluated[label],metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if finite else ('Brier','Top-1 credit','Top-3 credit')),'log_loss_interval_available':finite})
    for month in sorted({r['Date'][:7] for r in rows}):
        subset=[r for r in rows if r['Date'].startswith(month)]
        for label in labels[:6]:over_time.append({'Month':month,'Model':label,**phase2.metrics(subset,label)['metrics']})
    first=[r for r in rows if r['first_fg'].get('identity_known') and r['first_fg'].get('before_first_score')]
    shots={key:sum(rt.top_k_credit(r[key],r['first_fg']['player_id'],1) if r['first_fg']['player_id'] in r[key] else 0 for r in first)/len(first) if first else None for key in ('proxy','first_mc')}
    n=len(rows);dates=len({r['Date'] for r in rows})
    return safe_json({'experiment':EXPERIMENT,'eligible_primary_forecasts':len(selected),'graded_games':n,'dates':dates,'pending':pending,'summary':summary,'calibration':calibration,'comparisons':comparisons,'over_time':over_time,'first_shot_games':len(first),'first_shot_accuracy':shots,'excluded':excluded,'milestone_reached':n>=300 and dates>=30,'status':'Descriptive only; no promotion decision' if n>=300 else 'Below initial 300-game milestone; no accuracy claim','reference_accuracy_half_width_pp':1.96*math.sqrt(.15*.85/n)*100 if n else None})
