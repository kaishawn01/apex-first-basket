"""Controlled live orchestration; reuses frozen model, provider, journal and grader."""
import json,os,uuid,hashlib,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
import phase6_cloud as cloud,phase6_metrics as metrics,phase6_git as archive
import phase4_forward as forward,phase5_runner as old_runner,research_tools as rt,simulation
from phase6_journal import Journal,compact_prediction
from phase5_store import Store
from phase5_providers import Providers,Transport,ProviderError,stamp
import phase7_training as training

EXPERIMENT='apex-v3.0.6-live-01'

def specification():
    s=cloud.specification();s.update(experiment=EXPERIMENT,version='3.0.6',primary_timing_unchanged=True,training_schema=2,manual_snapshot_policy='one immutable snapshot per game/start/invocation; identical invocation retries deduplicate')
    for name in ('phase7_live.py','phase7_training.py'):s['source_hashes'][name]=hashlib.sha256((cloud.eng.ROOT/name).read_bytes()).hexdigest()
    return s

def register(j):
    spec=specification();old=j.get('protocol',EXPERIMENT)
    if old:
        if old['payload']!=spec:raise ValueError('Phase 7 experiment source/settings drift')
        return old
    return j.append('protocol',EXPERIMENT,spec)

class Bridge(cloud.Bridge):
    def append(self,kind,key,payload):
        games,_=self.p.schedule(payload['game']['_date'],fresh=True);now=self.clock();g=payload['game'];fresh=next((x for x in games if x['gameId']==g['gameId']),None)
        if not fresh or fresh['start_time']!=g['start_time'] or not cloud.core.upcoming(fresh,now) or (stamp(g['start_time'])-now).total_seconds()<30:raise ValueError('Started/rescheduled game or lost minimum lead')
        snap=self.latest_snapshot(g['gameId'])
        if snap['hash']!=payload['snapshot_hash'] or not 0<=(now-stamp(snap['payload']['retrieved_at'])).total_seconds()<=300:raise ValueError('Snapshot changed or expired')
        if register(self.j)['hash']!=self.context['protocol_hash']:raise ValueError('Protocol drift')
        base=payload['forecasts']['Baseline'];mass=base['OTHER'];payload['forecasts']['Literal V2.44 Baseline']={k:v/(1-mass) if k!='OTHER' else 0. for k,v in base.items()}
        out=compact_prediction(payload,self.context)
        out['top_five']={model:sorted([{'player_id':pid,'probability':p} for pid,p in probs.items() if pid!='OTHER'],key=lambda x:(-x['probability'],x['player_id']))[:5] for model,probs in out['forecasts'].items()}
        return self.j.append('prediction',self.key,out)

def generate(j,store,providers,game,bundle,slot,run_id,test=False):
    reg=register(j);values=training.validate(bundle,game['_date'])
    if any(s.get('retrieved_at') and stamp(s['retrieved_at'])>j.clock() for s in bundle['provenance'].values()):raise ValueError('Training evidence has a future retrieval timestamp')
    # Distinct manual invocations retain changed evidence; retries reuse the same ID.
    key=EXPERIMENT+':'+game['gameId']+':'+game['start_time']+':'+slot+(':'+run_id if slot=='manual' else '')
    old=j.get('prediction',key)
    if old:return old,False
    history,sequences,records=values;prior=rt.history_window(history,game['_date'])
    snap=old_runner.capture(store,providers,game,prior,key+':'+uuid.uuid4().hex)
    if not snap['payload']['valid_identities']:raise ValueError('Missing valid current-team lineup identities')
    context={'experiment':EXPERIMENT,'protocol_hash':reg['hash'],'snapshot_type':slot,'test_only':test,'training_games':len({r['game_id'] for r in prior}),'training_cutoff_exclusive':game['_date'],'bundle_cutoff_exclusive':bundle['cutoff_exclusive'],'training_bundle_sha256':bundle['sha256'],'training_provenance_sha256':bundle['provenance_sha256'],'run_id':run_id,'actionable':False,'execution':'cloud' if os.environ.get('GITHUB_ACTIONS')=='true' else 'manual'}
    return forward.save_prediction(Bridge(store,j,providers,key,context),snap,prior,sequences,records,simulation.SimulationConfig(trials=2000,seed=3000),refresh=False),True

class PermittedProviders(Providers):
    def __init__(self,store,j,run_id,grant):
        allowed=grant.get('providers',{})
        if not allowed.get('ESPN',{}).get('permission_verified'):raise ValueError('No permitted schedule/roster source')
        self.nba=allowed.get('NBA',{}).get('permission_verified') is True and 'automated_collection' in allowed['NBA'].get('scopes',[]) and bool(allowed['NBA'].get('evidence_reference'))
        super().__init__(store,Transport(store,cloud.BudgetGet(j,store,run_id)),injury_key='',sports_key='',licensed=False)
    def lineups(self,day):
        if not self.nba:return [],['NBA confirmation source not authorized; history projections remain unverified']
        return super().lineups(day)

def readiness(bundle=None,grant=None,now=None):
    problems=[]
    if bundle is None:problems.append('No reviewed training candidate')
    else:
        try:training.validate(bundle);training.permission(bundle,grant or {},now)
        except (ValueError,KeyError,TypeError) as exc:problems.append(str(exc))
    return {'ready':not problems,'blockers':problems,'scheduled_enabled':False,'paid_providers_enabled':False}

def collect(j,store,providers,bundle,mode,run_id,publish,test=False,grant=None,day=None):
    if not test:
        training.permission(bundle,grant or {},j.clock())
    if mode not in ('manual','scheduled','validation'):raise ValueError('Invalid mode')
    register(j);old=j.get('run',EXPERIMENT+':'+run_id)
    if old:return old['payload']
    report={'experiment':EXPERIMENT,'run_id':run_id,'test_only':test,'mode':mode,'at':j.clock().isoformat(),'discovered':0,'generated':0,'published':0,'graded':0,'errors':[],'missed_windows':[],'persistence':'not verified'}
    before={r['hash'] for r in j.rows('prediction')}
    if mode=='validation':report.update(cloud.grade(j,providers,test=test))
    else:
        day=day or j.clock().astimezone(cloud.ET).date().isoformat()
        try:
            games,source=providers.schedule(day,fresh=True);report['discovered']=len(games);report['retrieval']='successful';report['slate_retrieved_at']=source['retrieved_at']
            for game in games[:15]:
                now=j.clock()
                if not cloud.core.upcoming(game,now):continue
                for minute in (60,30,10,2):
                    late=90 if minute==2 else 180
                    if now>stamp(game['start_time'])-timedelta(seconds=max(30,minute*60-late)) and not any(r['payload']['game']['gameId']==game['gameId'] and r['payload']['game']['start_time']==game['start_time'] and r['payload']['snapshot_type']=='checkpoint-'+str(minute) for r in j.rows('prediction')):report['missed_windows'].append({'game':game['gameId'],'minutes':minute})
                for slot in (cloud.due_slots(now,game) if mode=='scheduled' else ['manual']):
                    try:
                        _,added=generate(j,store,providers,game,bundle,slot,run_id,test)
                        if added:
                            report['generated']+=1
                            # Publish immediately after each forecast; batch completion must not delay it.
                            try:publish()
                            except Exception as exc:raise RuntimeError('Durable publication failed; stop collection and recover archive') from exc
                            report['published']+=1
                    except (ValueError,ProviderError) as exc:
                        report['errors'].append({'game':game['gameId'],'reason':str(exc)})
                        if 'Git' in str(exc) or 'publication' in str(exc).lower():raise
        except ProviderError as exc:report['retrieval']='failed';report['errors'].append({'reason':str(exc)})
    report['status']='partial' if report['errors'] else 'captured' if report['published'] else 'graded' if report['graded'] else 'no eligible forecasts'
    report['provider_health']={p:store.state('health:'+p) for p in ('ESPN','NBA')};report['cooldowns']={p:store.state('cooldown:'+p,0) for p in ('ESPN','NBA')}
    report['finished_at']=j.clock().isoformat();j.append('run',EXPERIMENT+':'+run_id,report);publish()
    return report

def monitoring(j,receipts,now=None):
    now=now or datetime.now(timezone.utc);day=now.astimezone(cloud.ET).date().isoformat();preds=[r for r in j.rows('prediction') if not r['payload']['test_only']];results={}
    for r in j.rows('result'):
        if not r['payload']['test_only']:results[r['payload']['prediction_hash']]=r['payload']
    persisted=[r for r in preds if r['hash'] in receipts and stamp(receipts[r['hash']]['verified_remote_at'])<=stamp(r['payload']['game']['start_time'])-timedelta(seconds=30)]
    runs=[r['payload'] for r in j.rows('run') if not r['payload'].get('test_only',True)]
    quota=sum(r['payload']['requests_reserved'] for r in j.rows('budget') if r['payload']['day']==day)
    return {'real_forecasts':len(preds),'published_pre_tip':len(persisted),'latest_persisted_forecast':persisted[-1]['created_at'] if persisted else None,'verified_outcomes':sum(r['eligible_for_metrics'] for r in results.values()),'unresolved_or_pending':sum(r['hash'] not in results or not results[r['hash']]['eligible_for_metrics'] for r in preds),'remaining_reserved_attempt_allowance':max(0,400-quota),'last_execution':runs[-1] if runs else None,'automation':'Not activated; job receipts do not prove an active schedule','evaluation':metrics.evaluate(j,receipts)}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['manual','scheduled','validation','readiness']);p.add_argument('--journal',required=True);p.add_argument('--training',required=True);p.add_argument('--permission',required=True);p.add_argument('--data-root');p.add_argument('--day');a=p.parse_args()
    if os.environ.get('APEX_AUTOMATION_DISABLED')=='true':raise SystemExit('Global disable is on')
    bundle=json.loads(Path(a.training).read_text());grant=json.loads(Path(a.permission).read_text())
    if a.mode=='readiness':print(json.dumps(readiness(bundle,grant),indent=2));raise SystemExit(0)
    if os.environ.get('APEX_LIVE_COLLECTION_APPROVED')!='true':raise SystemExit('Live collection approval absent')
    training.permission(bundle,grant);training.validate(bundle,a.day or datetime.now(cloud.ET).date().isoformat())
    if not a.data_root:raise SystemExit('Durable archive checkout required')
    if os.environ.get('GITHUB_RUN_ATTEMPT','1')!='1':raise SystemExit('Live rerun refused; use a new quota-reserved invocation')
    j=Journal(a.journal);run_id=os.environ.get('GITHUB_RUN_ID') or uuid.uuid4().hex
    publish=lambda:archive.publish(Path(a.data_root),str(Path(a.journal).resolve().relative_to(Path(a.data_root).resolve())))
    register(j);cloud.reserve_budget(j,run_id);publish()
    with tempfile.TemporaryDirectory() as tmp:
        s=Store(Path(tmp)/'ops.db')
        previous=j.rows('run')
        if previous:
            for provider,until in previous[-1]['payload'].get('cooldowns',{}).items():s.set_state('cooldown:'+provider,until)
        providers=PermittedProviders(s,j,run_id,grant)
        result=collect(j,s,providers,bundle,a.mode,run_id,publish,grant=grant,day=a.day)
    print(json.dumps(result,indent=2))
    if result['errors']:raise SystemExit(1)
