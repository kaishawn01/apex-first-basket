"""Compact public research archive: append-only JSON, atomic replace, bounded size.
Git fast-forward publication provides cross-run concurrency control. No raw feeds.
"""
import json, os, tempfile, math
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from phase4_data import canonical, digest
from phase5_providers import stamp

MAX_BYTES=10_000_000
MAX_RECORDS=10000
KINDS={'protocol','prediction','result','run','budget'}

def validate(document):
    if document.get('schema')!=1 or not isinstance(document.get('events'),list):raise ValueError('Invalid cloud journal schema')
    previous='';keys=set()
    for r in document['events']:
        if set(r)!={'kind','key','created_at','payload','previous','hash'}:raise ValueError('Invalid record fields')
        if r['kind'] not in KINDS or (r['kind'],r['key']) in keys:raise ValueError('Duplicate or unknown record')
        keys.add((r['kind'],r['key']));stamp(r['created_at'])
        expected=digest({k:v for k,v in r.items() if k!='hash'})
        if r['previous']!=previous or r['hash']!=expected:raise ValueError('Cloud journal integrity failure')
        previous=r['hash']
    if document.get('head')!=previous:raise ValueError('Cloud journal head mismatch')
    if len(document['events'])>MAX_RECORDS or len(canonical(document).encode())>MAX_BYTES:raise ValueError('Archive capacity reached: stop and migrate; do not delete forecasts')
    return document

@contextmanager
def locked(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            f.seek(0);f.write(b'0');f.flush();f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX)
        try:yield
        finally:
            if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f,fcntl.LOCK_UN)

class Journal:
    def __init__(self,path,clock=None):self.path=Path(path);self.clock=clock or (lambda:datetime.now(timezone.utc))
    def read(self):
        if not self.path.exists():return {'schema':1,'events':[],'head':''}
        if self.path.stat().st_size>MAX_BYTES:raise ValueError('Archive exceeds size limit')
        return validate(json.loads(self.path.read_text()))
    def rows(self,kind=None):return [r for r in self.read()['events'] if kind is None or r['kind']==kind]
    def get(self,kind,key):return next((r for r in self.rows(kind) if r['key']==key),None)
    def append(self,kind,key,payload):
        # Deliberate allowlist rather than exporting the operational database.
        if kind not in KINDS:raise ValueError('Raw/provider/private records cannot be published')
        with locked(self.path.with_suffix('.lock')):
            doc=self.read();old=next((r for r in doc['events'] if r['kind']==kind and r['key']==key),None)
            if old:
                if old['payload']!=payload:raise ValueError('Immutable journal conflict')
                return old
            now=self.clock()
            if now.tzinfo is None:raise ValueError('UTC-aware clock required')
            now=now.astimezone(timezone.utc)
            if doc['events'] and stamp(doc['events'][-1]['created_at'])>now:raise ValueError('Clock reversal')
            if kind=='prediction':
                generated=stamp(payload['generated_at']);tip=stamp(payload['game']['start_time'])
                if generated>now or (tip-now).total_seconds()<30:raise ValueError('Late or future-dated prediction rejected')
                ids=payload['first_shot_proxy']
                from phase4_forward import validate_probs
                for p in payload['forecasts'].values():validate_probs(p,ids)
                validate_probs(ids,ids,False)
            record={'kind':kind,'key':key,'created_at':now.isoformat(),'payload':payload,'previous':doc['head']}
            record['hash']=digest(record);doc['events'].append(record);doc['head']=record['hash'];validate(doc)
            self.path.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix='.apex-',dir=self.path.parent)
            try:
                with os.fdopen(fd,'w') as f:f.write(canonical(doc)+'\n');f.flush();os.fsync(f.fileno())
                os.replace(tmp,self.path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            return record

def compact_prediction(p,context):
    """Publish derived estimates and provenance, never unrestricted provider bodies."""
    fields=('game','model_version','generated_at','source_hashes','forecasts','first_shot_proxy','simulated_first_shot','trials','seed','derived_seed','settings','assumptions','other_evidence','unresolved_trials','no_fg_before_score_fraction','minimum_history_met','effective_hybrid_weight','team_sample_sizes','mc_sampling_se','unresolved_policy','history_fingerprint','sequence_fingerprint','warning')
    out={k:p[k] for k in fields};s=p['snapshot']
    out['lineups']={t:[{k:x[k] for k in ('player_id','player')} for x in ps] for t,ps in s['lineups'].items()}
    out['lineup_status']=s['statuses'];out['cohort']=s.get('cohort','projected')
    out['evidence']={'retrieved_at':s['retrieved_at'],'injury_retrieved_at':s.get('injury_retrieved_at'),'failures':s.get('failures',[]),'messages':s['readiness']['messages'],'sources':[{'provider':x.get('provider'),'retrieved_at':x.get('retrieved_at'),'sha256':x.get('sha256'),'provider_date':x.get('provider_date')} for x in s.get('source_responses',[])],'rosters':{t:{k:w.get(k) for k in ('retrieved_at','sha256')} for t,w in s.get('roster_sources',{}).items()}}
    out['market_odds']=None;out['odds_status']='Not collected: paid providers disabled; no ROI calculation'
    out.update(context);return out
