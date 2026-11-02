"""Headless execution around the existing V3 model. No Streamlit import/paid APIs."""
import copy,json,os,uuid,tempfile,hashlib,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import requests
import first_basket_engine as eng,dashboard_core as core,research_tools as rt
import phase4_forward as forward,phase4_data as data,outcome_data,simulation
import phase5_runner as runner,phase5_protocol as old_protocol
from phase5_store import Store
from phase5_providers import Providers,Transport,ProviderError,stamp
from phase6_journal import Journal,compact_prediction

EXPERIMENT='apex-v3.0.5-cloud-01'
ET=ZoneInfo('America/New_York')

def specification():
    spec=old_protocol.specification()
    spec.update(experiment=EXPERIMENT,version='3.0.5',snapshot_types=['morning','updated','evening','checkpoint-60','checkpoint-30','checkpoint-10','checkpoint-2','manual'],primary_selection='Latest generated 30–600 seconds before unchanged provider scheduled tip, durable Git commit also before tip minus 30 seconds, one per game without looking at outcomes',durability='Git fast-forward commit containing immutable forecast; fail closed without receipt',scheduled_enabled=False,paid_providers=False)
    spec['source_hashes'].update({n:hashlib.sha256((eng.ROOT/n).read_bytes()).hexdigest() for n in ('phase6_cloud.py','phase6_journal.py','phase6_metrics.py')})
    return spec

def register(journal):
    spec=specification();old=journal.get('protocol',EXPERIMENT)
    if old:
        if old['payload']!=spec:raise ValueError('Frozen cloud experiment drift; declare a new experiment')
        return old
    return journal.append('protocol',EXPERIMENT,spec)

def due_slots(now,game):
    """UTC instants converted with zoneinfo; missed windows never backfilled."""
    if not core.upcoming(game,now):return []
    local=now.astimezone(ET);slots=[]
    if game['_date']==local.date().isoformat():
        for label,h,m in [('morning',10,0),('updated',17,30),('evening',18,30)]:
            target=local.replace(hour=h,minute=m,second=0,microsecond=0)
            if 0<=(local-target).total_seconds()<=900:slots.append(label)
    minute=runner.checkpoint(game,now,old_protocol.specification())
    if minute is not None:slots.append('checkpoint-'+str(minute))
    return slots

def next_targets(now,games):
    targets=[]
    for g in games:
        for minute in [60,30,10,2]:
            at=stamp(g['start_time'])-timedelta(minutes=minute)
            if at>now:targets.append({'at':at.isoformat(),'type':'checkpoint-'+str(minute),'game':g['gameId']})
    return sorted(targets,key=lambda x:x['at'])[:12]

def reserve_budget(journal,run_id,limit=80):
    key='reservation:'+run_id;old=journal.get('budget',key)
    if old:return old
    day=journal.clock().astimezone(ET).date().isoformat();reserved=sum(r['payload']['requests_reserved'] for r in journal.rows('budget') if r['payload']['day']==day)
    limit=min(limit,80)
    if reserved+limit>400:raise ProviderError('Daily request reservation limit reached')
    return journal.append('budget',key,{'day':day,'requests_reserved':limit,'policy':'Count maximum attempts even if a job crashes or makes fewer calls'})

class BudgetGet:
    """Credential-free allowlist. Cloud CLI publishes the reservation BEFORE network."""
    def __init__(self,journal,store,run_id,get=None,limit=80):
        self.j=journal;self.s=store;self.run=run_id;self.get=get or requests.get;self.used=0
        self.reservation=reserve_budget(journal,run_id,limit);self.limit=self.reservation['payload']['requests_reserved']
    def __call__(self,url,**kwargs):
        host=urlparse(url).hostname
        if urlparse(url).scheme!='https' or host not in ('site.api.espn.com','cdn.nba.com'):raise ProviderError('Provider blocked by no-cost policy')
        if any(k.lower() in ('authorization','ocp-apim-subscription-key') for k in kwargs.get('headers',{})):raise ProviderError('Credentials forbidden in cloud collector')
        if kwargs.get('params') and any('key' in k.lower() for k in kwargs['params']):raise ProviderError('API keys forbidden')
        if self.used>=self.limit:raise ProviderError('Per-run request budget reached')
        self.used+=1
        return self.get(url,allow_redirects=False,**kwargs)

def free_providers(store,journal,run_id):
    get=BudgetGet(journal,store,run_id)
    return Providers(store,Transport(store,get=get),injury_key='',sports_key='',licensed=False)

class Bridge:
    def __init__(self,store,journal,providers,key,context):self.s=store;self.j=journal;self.p=providers;self.key=key;self.context=context;self.clock=store.clock
    def latest_snapshot(self,gid):
        rows=[r for r in self.s.rows('snapshot') if r['payload']['game']['gameId']==gid];return rows[-1] if rows else None
    def append(self,kind,key,payload):
        games,_=self.p.schedule(payload['game']['_date'],fresh=True);now=self.clock();g=payload['game']
        fresh=next((x for x in games if x['gameId']==g['gameId']),None)
        if not fresh or fresh['start_time']!=g['start_time'] or not core.upcoming(fresh,now):raise ValueError('Fresh game status changed or started')
        if (stamp(g['start_time'])-now).total_seconds()<30:raise ValueError('Minimum pre-tip lead lost')
        latest=self.latest_snapshot(g['gameId'])
        if latest['hash']!=payload['snapshot_hash'] or not 0<=(now-stamp(latest['payload']['retrieved_at'])).total_seconds()<=300:raise ValueError('Evidence changed or expired')
        if register(self.j)['hash']!=self.context['protocol_hash']:raise ValueError('Protocol drift')
        base=payload['forecasts']['Baseline'];mass=base['OTHER']
        payload['forecasts']['Literal V2.44 Baseline']={k:v/(1-mass) if k!='OTHER' else 0. for k,v in base.items()}
        return self.j.append('prediction',self.key,compact_prediction(payload,self.context))

def generate(journal,store,providers,game,training,slot,run_id,test=False):
    registered=register(journal);key=EXPERIMENT+':'+game['gameId']+':'+game['start_time']+':'+slot
    old=journal.get('prediction',key)
    if old:return old,False
    history,sequences,records=training
    prior=rt.history_window(history,game['_date'])
    snap=runner.capture(store,providers,game,prior,key+':'+uuid.uuid4().hex)
    if not snap['payload']['valid_identities']:raise ValueError('Incomplete current-roster identities; no forecast')
    context={'experiment':EXPERIMENT,'protocol_hash':registered['hash'],'snapshot_type':slot,'test_only':test,'training_games':len({r['game_id'] for r in prior}),'run_id':run_id,'actionable':False,'execution':'cloud' if os.environ.get('GITHUB_ACTIONS')=='true' else 'manual'}
    bridge=Bridge(store,journal,providers,key,context)
    return forward.save_prediction(bridge,snap,prior,sequences,records,simulation.SimulationConfig(trials=2000,seed=3000),refresh=False),True

def grade(journal,providers,test=False,limit=15):
    now=journal.clock();preds=[r for r in journal.rows('prediction') if r['payload']['test_only']==test];last={}
    for r in journal.rows('result'):last[r['payload']['prediction_hash']]=r
    report={'graded':0,'pending':0,'errors':[]};groups={}
    for r in preds:
        p=r['payload'];old=last.get(r['hash'])
        if stamp(p['game']['start_time'])>now:report['pending']+=1;continue
        if old and (now-stamp(old['created_at'])).total_seconds()<86400:continue
        groups.setdefault(p['game']['gameId'],[]).append(r)
    for gid,group in list(groups.items())[:limit]:
        try:
            source=providers.result(gid);raw=source['payload']
            if raw.get('header',{}).get('season',{}).get('type')!=2:raise ValueError('Not verified regular-season outcome')
            if not raw.get('header',{}).get('competitions',[{}])[0].get('status',{}).get('type',{}).get('completed'):report['pending']+=len(group);continue
            for pred in group:
                p=pred['payload'];result=outcome_data.extract(p['game'],raw)
                result['first_field_goal']=data.first_fg_fact(raw)
                eligible=result['status']=='resolved' and stamp(p['generated_at'])<stamp(result['start_time']) and p['game']['start_time']==result['start_time']
                compact={k:result.get(k) for k in ('game_id','start_time','status','scorer_id','starter_status','score_type','warnings','first_field_goal')}
                key=pred['hash']+':'+source['sha256']
                if not journal.get('result',key):
                    journal.append('result',key,{'prediction_hash':pred['hash'],'result':compact,'eligible_for_metrics':eligible,'reason':None if eligible else 'Ambiguous outcome or changed start time','retrieved_at':source['retrieved_at'],'source_hash':source['sha256'],'test_only':test});report['graded']+=1
        except (ValueError,ProviderError,KeyError,TypeError):report['errors'].append({'game':gid,'reason':'Result unavailable or inconsistent; retained pending'})
    return report

def load_training(path):
    if not path:raise ValueError('Approved training bundle unavailable; live model execution disabled')
    p=Path(path)
    if p.stat().st_size>25_000_000:raise ValueError('Training bundle exceeds limit')
    d=json.loads(p.read_text())
    if d.get('schema')!=1 or d.get('test_only') is not False or not d.get('publication_reviewed'):raise ValueError('Training provenance/publication review missing')
    if d.get('sha256')!=data.digest(d['data']):raise ValueError('Training checksum mismatch')
    history=d['data']['history'];sequences=d['data']['sequences'];records=d['data']['records']
    # Preserve upstream validation and conditional starter training behavior.
    checked,errors=rt.audit(history)
    if errors:raise ValueError('Training identity validation failed')
    return history,sequences,records

def run(journal,action='manual',training=None,providers=None,store=None,day=None,enabled=False):
    if not enabled:raise ValueError('Global automation switch is off')
    if action not in ('manual','scheduled','validation'):raise ValueError('Unknown action')
    register(journal);run_id=os.environ.get('GITHUB_RUN_ID') or uuid.uuid4().hex
    day=day or journal.clock().astimezone(ET).date().isoformat()
    old=journal.get('run',run_id+':'+action)
    if old:return old['payload']
    if store is None:raise ValueError('Ephemeral operational store required')
    previous=journal.rows('run')
    if previous:
        for provider,until in previous[-1]['payload'].get('cooldowns',{}).items():store.set_state('cooldown:'+provider,until)
    providers=providers or free_providers(store,journal,run_id)
    report={'run_id':run_id,'action':action,'test_only':False,'started_at':journal.clock().isoformat(),'generated':0,'graded':0,'errors':[],'upcoming':[],'persistence':'not yet published','automation':'manually invoked' if action=='manual' else 'invoked; future scheduling not guaranteed'}
    try:
        if action=='validation':report.update(grade(journal,providers))
        else:
            if training is None:raise ValueError('Approved training bundle required')
            games,_=providers.schedule(day,fresh=True)
            report['upcoming']=[g for g in games if core.upcoming(g,journal.clock())]
            for g in report['upcoming'][:15]:
                slots=due_slots(journal.clock(),g) if action=='scheduled' else ['manual']
                for slot in slots:
                    try:_,added=generate(journal,store,providers,g,training,slot,run_id);report['generated']+=int(added)
                    except (ValueError,ProviderError):report['errors'].append({'game':g['gameId'],'reason':'Forecast blocked: missing/stale evidence or provider unavailable'})
            report['next_targets']=next_targets(journal.clock(),report['upcoming'])
        report['status']='partial' if report['errors'] else 'predictions generated' if report['generated'] else 'outcomes reconciled' if report['graded'] else 'completed without new predictions'
    except (ValueError,ProviderError):report['status']='failed';report['errors'].append({'reason':'Collection unavailable; check training, provider and budget diagnostics'})
    report['provider_health']={p:store.state('health:'+p) for p in ('ESPN','NBA')};report['cooldowns']={p:store.state('cooldown:'+p,0) for p in ('ESPN','NBA')}
    report['finished_at']=journal.clock().isoformat();journal.append('run',run_id+':'+action,report);return report
