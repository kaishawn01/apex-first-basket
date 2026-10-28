"""Append-only prospective evidence and forecast journal. No scheduler is installed."""
import json,sqlite3,hashlib,uuid,math,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
import first_basket_engine as eng,dashboard_core as core,research_tools as rt
import phase3,phase2,simulation,outcome_data,updater
from phase4_data import canonical,digest

class Journal:
    def __init__(self,path=None,clock=None):
        self.path=Path(path or eng.DATA/'phase4'/'forward.sqlite3');self.path.parent.mkdir(parents=True,exist_ok=True)
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,key TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL,previous TEXT NOT NULL,hash TEXT NOT NULL,UNIQUE(kind,key));
            CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON entries BEGIN SELECT RAISE(ABORT,'Journal entries are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON entries BEGIN SELECT RAISE(ABORT,'Journal entries are immutable'); END;''')
    def connect(self):return sqlite3.connect(self.path,timeout=30)
    def rows(self,kind=None):
        previous='';result=[]
        with self.connect() as c:
            for ident,k,key,at,raw,prev,h in c.execute('SELECT * FROM entries ORDER BY id'):
                expected=digest({'kind':k,'key':key,'created_at':at,'payload':json.loads(raw),'previous':prev})
                if prev!=previous or h!=expected:raise ValueError('Journal integrity check failed; preserve file for review')
                previous=h
                if kind is None or kind==k:result.append({'id':ident,'kind':k,'key':key,'created_at':at,'payload':json.loads(raw),'hash':h})
        return result
    def append(self,kind,key,payload):
        self.rows();now=self.clock()
        if now.tzinfo is None:raise ValueError('Journal requires an aware UTC timestamp')
        at=now.astimezone(timezone.utc).isoformat()
        if kind in ('snapshot','prediction'):
            if not core.upcoming(payload['game'],now) or payload['game'].get('research_only'):raise ValueError('Append must occur before a real scheduled tip-off')
        if kind=='prediction':
            stamp=datetime.fromisoformat(payload['generated_at'])
            if stamp.tzinfo is None or stamp>now:raise ValueError('Invalid prediction generation time')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM entries WHERE kind=? AND key=?',(kind,key)).fetchone():return False
            last=c.execute('SELECT hash,created_at FROM entries ORDER BY id DESC LIMIT 1').fetchone()
            if last and datetime.fromisoformat(last[1])>now:raise ValueError('Clock moved backwards; append refused')
            prev=last[0] if last else '';h=digest({'kind':kind,'key':key,'created_at':at,'payload':payload,'previous':prev})
            c.execute('INSERT INTO entries(kind,key,created_at,payload,previous,hash) VALUES(?,?,?,?,?,?)',(kind,key,at,canonical(payload),prev,h))
        return True
    def latest_snapshot(self,gid):
        found=[r for r in self.rows('snapshot') if r['payload'].get('game',{}).get('gameId')==gid]
        return found[-1] if found else None

def snapshot(journal,game,lineups,rosters,provider,injuries,injury_time,failures=None,manual=None,raw_provider=None):
    now=journal.clock()
    if now.tzinfo is None or not core.upcoming(game,now) or game.get('research_only'):raise ValueError('Snapshot is not a real pre-tip game')
    ready=core.phase2_readiness(game,lineups,manual or {},provider,rosters,injuries,injury_time,now)
    previous=journal.latest_snapshot(game['gameId']);old=previous['payload'] if previous else {}
    sources=ready['sources'];labels={t:('officially confirmed' if v=='NBA feed confirmed' else 'manually confirmed' if v=='User confirmed' else 'projected' if len(lineups.get(t,[]))==5 else 'unknown') for t,v in sources.items()}
    roster_changes={t:{'removed':sorted({p['player_id'] for p in old.get('rosters',{}).get(t,[])}-{p['player_id'] for p in ps}),'added':sorted({p['player_id'] for p in ps}-{p['player_id'] for p in old.get('rosters',{}).get(t,[])})} for t,ps in rosters.items() if ps and old.get('rosters',{}).get(t)}
    changes={t:{'before':[p['player_id'] for p in old.get('lineups',{}).get(t,[])],'after':[p['player_id'] for p in ps]} for t,ps in lineups.items() if [p['player_id'] for p in old.get('lineups',{}).get(t,[])]!=[p['player_id'] for p in ps]}
    payload={'game':game,'lineups':lineups,'rosters':rosters,'lineup_evidence':provider,'statuses':labels,'readiness':ready,'injuries':injuries,'injury_retrieved_at':injury_time,'failures':failures or [],'changes':changes,'roster_changes':roster_changes,'availability_changed':injury_time is not None and old.get('injuries')!=injuries,'raw_provider':raw_provider,'raw_provider_hash':digest(raw_provider) if raw_provider else None,'retrieved_at':now.astimezone(timezone.utc).isoformat(),'timezone':'UTC','prior_snapshot_hash':previous['hash'] if previous else None,'prior_official_evidence_retained':any(x=='officially confirmed' for x in old.get('statuses',{}).values())}
    key=game['gameId']+':'+uuid.uuid4().hex;journal.append('snapshot',key,payload);return journal.latest_snapshot(game['gameId'])

def collect_snapshots(day,history,journal=None,injury_key=None):
    journal=journal or Journal();now=journal.clock();failures=[]
    try:games=core.fresh_schedule(day)
    except Exception as e:
        journal.append('collection',uuid.uuid4().hex,{'date':day,'status':'failed','provider':'ESPN schedule','reason':type(e).__name__});return {'snapshots':0,'official_games':0,'failures':['Schedule provider unavailable']}
    games=[g for g in games if core.upcoming(g,now) and 0<(datetime.fromisoformat(g['start_time'].replace('Z','+00:00'))-now).total_seconds()<=24*3600]
    rosters={}
    for team in sorted({g[s]['teamTricode'] for g in games for s in ('awayTeam','homeTeam')}):
        try:rosters[team]=core.roster(team)
        except Exception as e:rosters[team]=[];failures.append(team+': roster provider unavailable ('+type(e).__name__+')')
    injuries=[];injury_time=None
    if injury_key:
        try:injuries=core.injury_reports(injury_key);injury_time=journal.clock().isoformat()
        except Exception as e:failures.append('BALLDONTLIE injuries unavailable ('+type(e).__name__+')')
    else:failures.append('No injury credential supplied; availability remains unchecked')
    raw=None;parsed={'entries':{},'messages':[]}
    if games:
        try:
            raw=core.request(core.NBA_LINEUP_URL.format(day=day.replace('-','')))
            parsed=core.parse_nba_confirmed_lineups(raw,day,games,rosters,journal.clock())
        except Exception as e:failures.append('NBA lineup provider unavailable ('+type(e).__name__+')')
    count=official=0
    for g in games:
        lineups={};warnings=list(failures)+parsed['messages'];entries=parsed['entries'].get(g['gameId'],{})
        for team in (g['awayTeam']['teamTricode'],g['homeTeam']['teamTricode']):
            projected=core.projection_evidence(history,team,day,rosters[team],bool(rosters[team]));warnings.extend(team+': '+s for s in projected['warnings'])
            ids=entries.get(team,{}).get('player_ids',projected['defaults'])
            lineups[team]=[p for p in rosters[team] if p['player_id'] in ids]
        try:
            saved=snapshot(journal,g,lineups,{t:rosters[t] for t in lineups},entries,injuries,injury_time,warnings,raw_provider=raw)
            count+=1;official+=int(saved['payload']['readiness']['provider_verified'])
        except ValueError:failures.append(g['gameId']+': game became ineligible during collection')
    report={'snapshots':count,'official_games':official,'failures':failures,'date':day,'monitoring':'manual; no unattended scheduler configured'}
    journal.append('collection',uuid.uuid4().hex,report);return report

def validate_probs(p,ids,other=True):
    expected=set(ids)|({'OTHER'} if other else set())
    if set(p)!=expected or any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<0 for x in p.values()) or abs(sum(p.values())-1)>1e-8:raise ValueError('Invalid forecast probabilities')

def save_prediction(journal,snap,history,sequences,records,config=None,refresh=True):
    now=journal.clock();s=snap['payload'];g=s['game'];lineups=s['lineups'];ids=[p['player_id'] for ps in lineups.values() for p in ps]
    if not core.upcoming(g,now) or not 0<=(now-datetime.fromisoformat(s['retrieved_at'])).total_seconds()<=300:raise ValueError('Snapshot expired or game started')
    latest=journal.latest_snapshot(g['gameId'])
    if not latest or latest!=snap:raise ValueError('Newer snapshot exists; refresh predictions from current evidence')
    if len(ids)!=10 or len(set(ids))!=10 or any(not isinstance(pid,str) or not pid.isdigit() or int(pid)<=0 for pid in ids) or any(len(ps)!=5 for ps in lineups.values()):raise ValueError('Exactly five valid players per team required')
    if any(p['player_id'] not in {x['player_id'] for x in s['rosters'].get(t,[])} for t,ps in lineups.items() for p in ps):raise ValueError('Roster mismatch')
    if any('roster' in message.lower() or 'identit' in message.lower() for message in s['readiness']['messages']):raise ValueError('Snapshot has unresolved roster or identity diagnostics')
    if refresh:
        fresh=next((x for x in core.fresh_schedule(g['_date']) if x['gameId']==g['gameId']),None)
        if not fresh or not core.upcoming(fresh,journal.clock()) or fresh['start_time']!=g['start_time']:raise ValueError('Schedule changed or game started')
    cfg=(config or simulation.SimulationConfig(trials=2000,seed=3000)).validate()
    report=phase3.forecast(history,lineups,g['_date'],sequences,records,cfg)
    base=report['complete']['Baseline + Other'];mc=report['complete']['Monte Carlo']
    weight=.5 if report['minimum_history_met'] else 0.
    forecasts={'Baseline':base,'Calibrated Baseline':phase3.temper(base,1.25),'Simple proxy':report['complete']['Simple proxy'],'Pure Monte Carlo':mc,'Hybrid':phase3.temper({pid:(1-weight)*p+weight*mc[pid] for pid,p in base.items()},1.25),'Uniform':phase3.with_other({pid:.1 for pid in ids},report['other_mass'])}
    for p in forecasts.values():validate_probs(p,ids)
    validate_probs(report['first_shot_proxy'],ids,False)
    if not core.upcoming(g,journal.clock()):raise ValueError('Game started during simulation; nothing saved')
    payload={'game':g,'source_hashes':{name:hashlib.sha256((eng.ROOT/name).read_bytes()).hexdigest() for name in ('first_basket_engine.py','simulation.py','phase2.py','phase3.py','phase4_forward.py')},'model_version':updater.current_version(),'generated_at':journal.clock().isoformat(),'snapshot_hash':snap['hash'],'snapshot':s,'forecasts':forecasts,'first_shot_proxy':report['first_shot_proxy'],'simulated_first_shot':report['first_shot'],'first_shot_condition':'FG attempt before first score, selected-starter scope','trials':cfg.trials,'seed':cfg.seed,'derived_seed':report['derived_seed'],'settings':report['config'],'assumptions':report['inputs']['assumptions'],'other_evidence':report['other_evidence'],'unresolved_trials':report['unresolved_trials'],'no_fg_before_score_fraction':report['no_field_goal_fraction'],'minimum_history_met':report['minimum_history_met'],'effective_hybrid_weight':weight,'team_sample_sizes':{t:d['games'] for t,d in report['inputs']['teams'].items()},'mc_sampling_se':{pid:(1-report['other_mass'])*math.sqrt(max(0,(report['wins'].get(pid,0)+report['unresolved_trials']*report['baseline'][pid]**2)/cfg.trials-report['simulation'][pid]**2)/cfg.trials) for pid in report['baseline']},'unresolved_policy':'Baseline fallback within ten starters before explicit Other allocation','history_fingerprint':rt.fingerprint(history),'sequence_fingerprint':rt.fingerprint(sequences),'warning':'Research only, no validated edge; projected/manual states are not official confirmation','baseline_algorithm':'V2.44 conditional probabilities, expanded with Other','selection':'Frozen Phase 3 research settings; not fitted prospectively'}
    return journal.append('prediction',g['gameId'],payload)

def grade(journal,prediction,payload):
    if prediction not in journal.rows('prediction'):raise ValueError('Prediction does not match an immutable saved entry')
    p=prediction['payload'];g=p['game']
    if core.upcoming(g,journal.clock()):raise ValueError('Cannot grade a future game')
    result=outcome_data.extract(g,payload)
    from phase4_data import first_fg_fact
    result['first_field_goal']=first_fg_fact(payload)
    actual_start=datetime.fromisoformat(result['start_time'].replace('Z','+00:00'));generated=datetime.fromisoformat(p['generated_at'])
    eligible=generated<actual_start and p['game']['start_time']==result['start_time']
    outcome={'game_id':g['gameId'],'prediction_hash':prediction['hash'],'result':result,'eligible_for_metrics':eligible and result['status']=='resolved','reason':None if eligible else 'Reschedule or prediction not before provider-reported start','source_hash':digest(payload),'retrieved_at':journal.clock().isoformat()}
    # Result versions append; earlier grades remain auditable. No forecast is overwritten.
    journal.append('result',prediction['hash']+':'+digest(payload),outcome);return outcome

def refresh_results(journal=None,limit=20):
    journal=journal or Journal();done=0;errors=[]
    for pred in journal.rows('prediction'):
        if done>=limit:break
        if core.upcoming(pred['payload']['game'],journal.clock()):continue
        try:
            p=core.request(eng.ESPN_BASE+'/summary',{'event':pred['payload']['game']['gameId'].removeprefix('espn_')});grade(journal,pred,p);done+=1
        except Exception as e:errors.append({'game':pred['key'],'reason':type(e).__name__})
    journal.append('grading_run',uuid.uuid4().hex,{'graded':done,'errors':errors});return {'graded':done,'errors':errors}

def evaluation(journal):
    predictions={r['hash']:r for r in journal.rows('prediction')};latest={}
    for r in journal.rows('result'):latest[r['payload']['prediction_hash']]=r['payload']
    rows=[];excluded=[]
    for h,pred in predictions.items():
        result=latest.get(h)
        if not result or not result['eligible_for_metrics']:
            excluded.append({'game':pred['key'],'reason':'Pending result' if not result else result.get('reason') or 'Unresolved scoring identity'});continue
        p=pred['payload'];actual=result['result'];ids=set(p['first_shot_proxy']);winner=actual['scorer_id'] if actual['scorer_id'] in ids else 'OTHER'
        row={'Game':pred['key'],'Date':p['game']['_date'],'Winner':winner,'Verified':p['snapshot']['readiness']['provider_verified'],'Teams':[p['game'][side]['teamTricode'] for side in ('homeTeam','awayTeam')],'Opening context':actual.get('rows',[{}])[0].get('opening_score_path','Unknown') if actual.get('rows') else 'Unknown',**p['forecasts']}
        fact=actual.get('first_field_goal',{})
        row['First shooter']=fact.get('player_id') if fact.get('before_first_score') and fact.get('identity_known') else None
        row['First-shot probability']=p['first_shot_proxy'];rows.append(row)
    summary=[];calibration=[];comparisons=[]
    labels=('Baseline','Calibrated Baseline','Simple proxy','Pure Monte Carlo','Hybrid','Uniform')
    for cohort,subset in [('All',rows),('Provider verified',[r for r in rows if r['Verified']]),('Not provider verified',[r for r in rows if not r['Verified']])]:
        metrics={name:phase2.metrics([{**r,'Prediction':r[name]} for r in subset],'Prediction') for name in labels}
        for name,m in metrics.items():
            summary.append({'Cohort':cohort,'Model':name,**m['metrics']});calibration.extend({'Cohort':cohort,'Model':name,**x} for x in m['calibration'])
        if subset:
            for name in labels[1:]:
                finite=all(math.isfinite(x['Log loss']) for label in ('Baseline',name) for x in metrics[label]['games'])
                comparisons.append({'Cohort':cohort,'Model':name,**rt.compare_evaluations(metrics['Baseline'],metrics[name],metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if finite else ('Brier','Top-1 credit','Top-3 credit'))})
    first=[r for r in rows if r['First shooter'] is not None]
    strata=[]
    groups={('Month',month):[r for r in rows if r['Date'].startswith(month)] for month in sorted({r['Date'][:7] for r in rows})}
    groups.update({('Team',team):[r for r in rows if team in r['Teams']] for team in sorted({t for r in rows for t in r['Teams']})})
    groups.update({('Opening context',context):[r for r in rows if r['Opening context']==context] for context in sorted({r['Opening context'] for r in rows})})
    for (kind,label),subset in groups.items():
        if len(subset)<30:strata.append({'Dimension':kind,'Group':label,'Games':len(subset),'Status':'Fewer than 30 games; subgroup performance withheld'});continue
        for model in ('Baseline','Pure Monte Carlo','Hybrid','Uniform'):
            strata.append({'Dimension':kind,'Group':label,'Model':model,**phase2.metrics([{**r,'Prediction':r[model]} for r in subset],'Prediction')['metrics']})
    return {'strata':strata,'predictions':len(predictions),'graded_games':len(rows),'summary':summary,'calibration':calibration,'comparisons':comparisons,'excluded':excluded,'first_shot_games':len(first),'first_shot_accuracy':sum(rt.top_k_credit(r['First-shot probability'],r['First shooter'],1) if r['First shooter'] in r['First-shot probability'] else 0 for r in first)/len(first) if first else None}

if __name__=='__main__':
    import argparse,phase4_data
    from zoneinfo import ZoneInfo
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['capture','predict','grade','status']);parser.add_argument('--day',default=datetime.now(ZoneInfo('America/New_York')).date().isoformat());args=parser.parse_args()
    journal=Journal();history,sequences,records=phase4_data.dataset()
    if args.action=='capture':report=collect_snapshots(args.day,history,journal,os.environ.get('BALLDONTLIE_API_KEY'))
    elif args.action=='grade':report=refresh_results(journal)
    elif args.action=='status':report=evaluation(journal)
    else:
        saved=0;errors=[]
        for snap in journal.rows('snapshot'):
            if snap!=journal.latest_snapshot(snap['payload']['game']['gameId']):continue
            try:saved+=int(save_prediction(journal,snap,history,sequences,records))
            except (ValueError,RuntimeError) as e:errors.append(str(e))
        report={'saved':saved,'errors':errors}
    print(json.dumps(report,indent=2))
