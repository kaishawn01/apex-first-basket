"""Idempotent checkpoint runner. No scheduler or deployment is installed by this module."""
import json,uuid,os,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import dashboard_core as core,phase4_forward as forward,phase4_data as data
import phase5_protocol as protocol,phase5_integrity as integrity
from phase5_store import configured_store,utc,StorageError,LeaseLost
from phase5_providers import Providers,ProviderError,resolve,stamp
import research_tools as rt,simulation,outcome_data

def checkpoint(game,now,spec):
    if not core.upcoming(game,now):return None
    lead=(stamp(game['start_time'])-now).total_seconds()
    for minute in reversed(spec['checkpoint_minutes']):
        late=spec['final_lateness_seconds'] if minute==2 else spec['checkpoint_lateness_seconds']
        if max(spec['minimum_lead_seconds'],minute*60-late)<=lead<=minute*60:return minute
    return None

def job_key(game,minute):return protocol.EXPERIMENT+':'+game['gameId']+':'+game['start_time']+':'+str(minute)

def capture(store,providers,game,history,key,fence=None,manual=None):
    now=utc(store.clock())
    if not core.upcoming(game,now):raise ValueError('Cannot capture a started game')
    rosters={};roster_sources={};errors=[]
    for team in (game['awayTeam']['teamTricode'],game['homeTeam']['teamTricode']):
        try:rosters[team],roster_sources[team]=providers.roster(team)
        except ProviderError as exc:rosters[team]=[];errors.append(str(exc))
    try:injuries,injury_source=providers.injuries()
    except ProviderError as exc:injuries=[];injury_source={'retrieved_at':None};errors.append(str(exc))
    sources,failures=providers.lineups(game['_date']);errors.extend(failures)
    now=utc(store.clock());resolved=resolve(game,rosters,history,sources,injuries,injury_source['retrieved_at'],now,manual)
    if not core.upcoming(game,now):raise ValueError('Game started during evidence collection')
    prior=[r for r in store.rows('snapshot') if r['payload']['game']['gameId']==game['gameId']];old=prior[-1] if prior else None
    changes={t:{'before':[p['player_id'] for p in (old['payload']['lineups'].get(t,[]) if old else [])],'after':[p['player_id'] for p in ps]} for t,ps in resolved['lineups'].items()}
    changes={t:v for t,v in changes.items() if v['before']!=v['after']}
    roster_changes={t:{'removed':sorted({p['player_id'] for p in old['payload']['rosters'].get(t,[])}-{p['player_id'] for p in ps}),'added':sorted({p['player_id'] for p in ps}-{p['player_id'] for p in old['payload']['rosters'].get(t,[])})} for t,ps in rosters.items()} if old else {}
    payload={'game':game,'lineups':resolved['lineups'],'rosters':rosters,'statuses':resolved['statuses'],'lineup_evidence':resolved['evidence'],'source_responses':sources,'roster_sources':roster_sources,'injuries':injuries,'injury_source':injury_source,'injury_retrieved_at':injury_source['retrieved_at'],'manual_evidence':manual or {},'retrieved_at':now.isoformat(),'timezone':'UTC','changes':changes,'roster_changes':roster_changes,'availability_changed':bool(old and old['payload']['injuries']!=injuries),'prior_snapshot_hash':old['hash'] if old else None,'failures':errors,'cohort':resolved['cohort'],'valid_identities':resolved['valid_identities'],'readiness':{'provider_verified':resolved['provider_verified'],'sources':resolved['statuses'],'messages':resolved['warnings']+errors,'actionable':False,'status':'RESEARCH ONLY — verification is not evidence of predictive advantage'},'experiment':protocol.EXPERIMENT}
    return store.append('snapshot',key,payload,fence,deadline=stamp(game['start_time']))

class ForecastBridge:
    """Reuse Phase 4 model generation; Phase 5 controls persistence and experiments."""
    def __init__(self,store,providers,key,fence,registered,training_games,checkpoint_minute):
        self.store=store;self.providers=providers;self.key=key;self.fence=fence;self.registered=registered;self.training_games=training_games;self.minute=checkpoint_minute;self.clock=store.clock
    def latest_snapshot(self,gid):
        rows=[r for r in self.store.rows('snapshot') if r['payload']['game']['gameId']==gid]
        return rows[-1] if rows else None
    def append(self,kind,key,payload):
        if kind!='prediction':raise ValueError('Unexpected bridge record')
        game=payload['game'];now=utc(self.clock())
        games,_=self.providers.schedule(game['_date'],fresh=True)
        fresh=next((g for g in games if g['gameId']==game['gameId']),None)
        now=utc(self.clock())
        if not fresh or fresh['start_time']!=game['start_time'] or not core.upcoming(fresh,now) or (stamp(fresh['start_time'])-now).total_seconds()<30:raise ValueError('Fresh schedule changed, started, or minimum lead time passed')
        latest=self.latest_snapshot(game['gameId'])
        if not latest or latest['hash']!=payload['snapshot_hash']:raise ValueError('Lineup changed during forecast generation')
        if not 0<=(now-stamp(latest['payload']['retrieved_at'])).total_seconds()<=300:raise ValueError('Evidence expired during model generation')
        if protocol.active(self.store)['hash']!=self.registered['hash']:raise ValueError('Protocol changed')
        base=payload['forecasts']['Baseline'];mass=base['OTHER']
        payload['forecasts']['Literal V2.44 Baseline']={k:(v/(1-mass) if k!='OTHER' else 0.) for k,v in base.items()}
        payload.update(experiment=protocol.EXPERIMENT,protocol_hash=self.registered['hash'],checkpoint_minutes=self.minute,training_games=self.training_games,cohort=payload['snapshot']['cohort'],saved_at=now.isoformat(),last_training_date=payload['game']['_date']+' exclusive',baseline_label='Baseline = V2.44 conditional model with explicit Other; literal model reported separately')
        for probs in payload['forecasts'].values():forward.validate_probs(probs,payload['first_shot_proxy'])
        return self.store.append('prediction',self.key,payload,self.fence,deadline=stamp(game['start_time'])-timedelta(seconds=30))

def predict(store,providers,snapshot,history,sequences,records,key,minute,fence):
    registered=protocol.active(store)
    existing=store.get('prediction',key)
    if existing:return existing
    if not snapshot['payload']['valid_identities']:raise ValueError('Incomplete current-team identities; snapshot retained without forecast')
    day=snapshot['payload']['game']['_date'];prior=rt.history_window(history,day)
    bridge=ForecastBridge(store,providers,key,fence,registered,len({r['game_id'] for r in prior}),minute)
    return forward.save_prediction(bridge,snapshot,prior,sequences,records,simulation.SimulationConfig(**registered['payload']['specification']['simulation']),refresh=False)

def tick(store,providers=None,day=None,mode='manual',observe=False):
    if mode not in ('manual','scheduled','fixture'):raise ValueError('Invalid execution mode')
    registered=protocol.active(store);spec=registered['payload']['specification'];providers=providers or Providers(store)
    day=day or utc(store.clock()).astimezone(ZoneInfo('America/New_York')).date().isoformat()
    lease=store.acquire('phase5-collector',300)
    if not lease:return {'status':'already running','captured':0,'predicted':0}
    run={'started_at':utc(store.clock()).isoformat(),'mode':mode,'observe_only':observe,'day':day,'captured':0,'predicted':0,'upcoming':0,'missed':0,'errors':[],'status':'running','storage':'PostgreSQL' if store.remote else 'local SQLite'}
    run_id=uuid.uuid4().hex
    try:
        store.rows() # Verify evidence chain before any collection.
        store.append('run_start',run_id,run,lease)
        games,slate=providers.schedule(day,fresh=True);now=utc(store.clock())
        store.set_state('slate',{'day':day,'retrieved_at':slate['retrieved_at'],'games':games})
        history,sequences,records=integrity.model_data(store)
        for game in games:
            store.renew(lease,300);now=utc(store.clock())
            if core.upcoming(game,now):run['upcoming']+=1
            # Record missed target windows without backfilling forecasts.
            for minute in spec['checkpoint_minutes']:
                late=spec['final_lateness_seconds'] if minute==2 else spec['checkpoint_lateness_seconds'];key=job_key(game,minute)
                if now>stamp(game['start_time'])-timedelta(seconds=max(30,minute*60-late)) and not store.get('prediction',key) and not store.get('missed',key):
                    store.append('missed',key,{'game':game,'checkpoint_minutes':minute,'reason':'No forecast saved in target window','recorded_at':now.isoformat()},lease);run['missed']+=1
            minute=checkpoint(game,now,spec)
            if observe:
                if not core.upcoming(game,now) or (stamp(game['start_time'])-now).total_seconds()>24*3600:continue
                key=job_key(game,'observe:'+run_id)
            elif minute is None:continue
            else:key=job_key(game,minute)
            if not observe and store.get('prediction',key):continue
            if not store.begin_job(key,lease):continue
            try:
                snap=capture(store,providers,game,history,key+':attempt:'+uuid.uuid4().hex,lease);run['captured']+=1
                if not observe:
                    predict(store,providers,snap,history,sequences,records,key,minute,lease);run['predicted']+=1
                store.finish_job(key,lease)
            except (ValueError,ProviderError) as exc:
                reason=str(exc);store.finish_job(key,lease,error=reason);run['errors'].append({'game':game['gameId'],'reason':reason})
        run['status']='completed' if not run['errors'] else 'partial'
    except (ProviderError,ValueError) as exc:run['status']='failed';run['errors'].append({'reason':str(exc)})
    finally:
        run['finished_at']=utc(store.clock()).isoformat()
        try:
            store.append('run',run_id,run,lease);store.set_state('last_collection',run)
        finally:store.release(lease)
    return run

def grade_tick(store,providers=None,limit=20):
    protocol.active(store);providers=providers or Providers(store);lease=store.acquire('phase5-grader',300)
    if not lease:return {'status':'already running','graded':0}
    report={'at':utc(store.clock()).isoformat(),'graded':0,'games_requested':0,'errors':[]};latest={}
    try:
        for r in store.rows('result'):latest[r['payload']['prediction_hash']]=r
        grouped={}
        for pred in store.rows('prediction'):
            p=pred['payload'];old=latest.get(pred['hash']);now=utc(store.clock())
            if p.get('experiment')!=protocol.EXPERIMENT or core.upcoming(p['game'],now):continue
            # Completed grades are immutable; corrected sources can be checked once daily.
            if old and (now-stamp(old['created_at'])).total_seconds()<(86400 if old['payload']['eligible_for_metrics'] else 900):continue
            grouped.setdefault(p['game']['gameId'],[]).append(pred)
        for gid,preds in list(grouped.items())[:limit]:
            store.renew(lease,300)
            try:
                source=providers.result(gid);report['games_requested']+=1;p=source['payload']
                if p.get('header',{}).get('season',{}).get('type')!=2:raise ValueError('Not a verified regular-season result')
                for pred in preds:
                    game=pred['payload']['game'];result=outcome_data.extract(game,p);result['first_field_goal']=data.first_fg_fact(p)
                    actual_start=stamp(result['start_time']);generated=stamp(pred['payload']['generated_at']);eligible=result['status']=='resolved' and generated<actual_start and game['start_time']==result['start_time']
                    reason=None if eligible else 'Unresolved outcome, changed scheduled start, or forecast not pre-tip'
                    payload={'prediction_hash':pred['hash'],'game_id':gid,'result':result,'eligible_for_metrics':eligible,'reason':reason,'source_hash':source['sha256'],'retrieved_at':source['retrieved_at']}
                    key=pred['hash']+':'+source['sha256']
                    if not store.get('result',key):store.append('result',key,payload,lease);report['graded']+=1
                # Add completed observations for FUTURE dates only; never update old forecasts.
                if not store.get('history',gid):
                    with tempfile.TemporaryDirectory() as folder:
                        game=outcome_data.game_from_payload(p);data.ingest(game,source,Path(folder));integrity.sync_history(store,Path(folder))
            except (ProviderError,ValueError,KeyError,TypeError) as exc:report['errors'].append({'game':gid,'reason':str(exc) if isinstance(exc,(ProviderError,ValueError)) else type(exc).__name__})
        store.append('grading_run',uuid.uuid4().hex,report,lease);store.set_state('last_grading',report)
    finally:store.release(lease)
    return report

def health(store):
    rows=store.rows();counts={k:sum(r['kind']==k for r in rows) for k in ('snapshot','prediction','result','history','missed','run')};snaps=[r for r in rows if r['kind']=='snapshot']
    graded_hashes={r['payload']['prediction_hash'] for r in rows if r['kind']=='result'}
    counts['awaiting_grading_forecasts']=sum(r['kind']=='prediction' and r['hash'] not in graded_hashes for r in rows)
    counts['both_provider_confirmed']=sum(r['payload']['readiness']['provider_verified'] for r in snaps)
    runs=[r['payload'] for r in rows if r['kind']=='run'];successful=[r for r in runs if r['status']=='completed']
    return {'storage':'PostgreSQL configured; durability depends on host backup policy' if store.remote else 'Local SQLite only; NOT durable on ephemeral cloud hosts','integrity':'hash chain verified','counts':counts,'last_successful_collection':successful[-1]['finished_at'] if successful else None,'last_collection':store.state('last_collection'),'last_grading':store.state('last_grading'),'slate':store.state('slate'),'historical_reconciliation':store.state('historical_integrity'),'provider_health':{p:store.state('health:'+p) for p in ['ESPN','NBA','BALLDONTLIE','SportsDataIO']},'scheduled_invocation_receipts':sum(r['mode']=='scheduled' and r['status']=='completed' for r in runs),'automation_note':'No scheduler is installed by APEX; receipts prove invocations, not future availability','prospective':protocol.evaluate(store)}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['init','register','sync-history','reconcile','observe','collect','grade','status','backup','restore']);parser.add_argument('--day');parser.add_argument('--scheduled',action='store_true');parser.add_argument('--file');args=parser.parse_args()
    try:
        store=configured_store()
        if args.action=='init':store.initialize();report={'initialized':True,'remote':store.remote}
        elif args.action=='register':report=protocol.register(store)
        elif args.action in ('sync-history','reconcile'):
            root=data.eng.DATA/'phase4';report=integrity.reconcile(root,[root/'raw',data.eng.DATA/'phase3_validation',data.eng.DATA/'v3_validation'],repair=args.action=='sync-history');store.set_state('historical_integrity',report)
            if args.action=='sync-history':
                if not report['healthy']:raise ValueError('Historical reconciliation failed; sync refused')
                report['sync']=integrity.sync_history(store,root)
        elif args.action in ('observe','collect'):report=tick(store,day=args.day,mode='scheduled' if args.scheduled else 'manual',observe=args.action=='observe')
        elif args.action=='grade':report=grade_tick(store)
        elif args.action=='backup':report=store.export(args.file)
        elif args.action=='restore':report={'restored_events':store.restore(args.file)}
        else:report=health(store)
        print(json.dumps(protocol.safe_json(report),indent=2))
        if report.get('status') in ('failed','partial'):raise SystemExit(1)
    except (ValueError,StorageError) as exc:
        print('Phase 5 stopped: '+str(exc));raise SystemExit(1)
