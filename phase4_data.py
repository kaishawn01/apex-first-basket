"""Resumable research collection. Separate SQLite checkpoint store; legacy CSVs untouched."""
import json,hashlib,sqlite3,threading,time,copy
from pathlib import Path
from datetime import datetime,timezone,date,timedelta
from concurrent.futures import ThreadPoolExecutor
import requests
import first_basket_engine as eng,outcome_data,opening_data,research_tools as rt

class RateLimited(RuntimeError):pass

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

def connect(root=None):
    root=Path(root or eng.DATA/'phase4');root.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(root/'history.sqlite3',timeout=30)
    c.executescript('''CREATE TABLE IF NOT EXISTS games(gid TEXT PRIMARY KEY,record TEXT NOT NULL,sequence TEXT,raw_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS failures(id INTEGER PRIMARY KEY,at TEXT,gid TEXT,stage TEXT,reason TEXT);
    CREATE TABLE IF NOT EXISTS attempts(gid TEXT PRIMARY KEY,n INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS status(key TEXT PRIMARY KEY,value TEXT);''')
    return c

class Client:
    def __init__(self,root=None,get=None,sleep=time.sleep):
        self.root=Path(root or eng.DATA/'phase4');(self.root/'raw').mkdir(parents=True,exist_ok=True)
        self.get=get or requests.get;self.sleep=sleep;self.stop=threading.Event()
    def fetch(self,url,params,cache_key):
        path=self.root/'raw'/(cache_key+'.json')
        if path.exists():
            cached=json.loads(path.read_text())
            if cached.get('sha256')!=digest(cached.get('payload')):raise ValueError('Cached source checksum mismatch')
            return cached
        cooldown=self.root/'rate_limit.json'
        if cooldown.exists() and datetime.fromisoformat(json.loads(cooldown.read_text())['until'])>datetime.now(timezone.utc):raise RateLimited('Provider cooldown is still active; no new request sent')
        if self.stop.is_set():raise RateLimited('Provider rate limit stopped this batch; retry after the provider window.')
        for attempt in range(2):
            self.sleep(.2)
            try:
                r=self.get(url,params=params,timeout=20)
                if r.status_code==429:
                    self.stop.set()
                    raw=r.headers.get('Retry-After','900')
                    try:
                        from email.utils import parsedate_to_datetime
                        until=datetime.now(timezone.utc)+timedelta(seconds=max(60,int(raw))) if str(raw).isdigit() else parsedate_to_datetime(raw)
                        if until.tzinfo is None:until=until.replace(tzinfo=timezone.utc)
                    except (ValueError,TypeError,OverflowError):until=datetime.now(timezone.utc)+timedelta(seconds=900)
                    (self.root/'rate_limit.json').write_text(canonical({'until':until.isoformat(),'provider':'ESPN'}))
                    raise RateLimited('HTTP 429; cooldown recorded until '+until.isoformat())
                r.raise_for_status();data=r.json()
                wrapper={'provider':'ESPN','retrieved_at':datetime.now(timezone.utc).isoformat(),'provider_date':r.headers.get('Date'),'url':url,'params':params,'payload':data,'sha256':digest(data)}
                tmp=path.with_suffix('.tmp');tmp.write_text(canonical(wrapper));tmp.replace(path);return wrapper
            except (requests.Timeout,requests.ConnectionError):
                if attempt:raise RuntimeError('Provider connection failed after two bounded attempts') from None
                self.sleep(1)
        raise RuntimeError('Provider unavailable')

def clean_box(payload):
    clean=copy.deepcopy(payload)
    for side in clean.get('boxscore',{}).get('players',[]):
        for stats in side.get('statistics',[]):
            stats['athletes']=[r for r in stats.get('athletes',[]) if str(r.get('athlete',{}).get('id','')).isdigit() and int(r['athlete']['id'])>0 and r['athlete'].get('displayName')]
    return clean

def ingest(game,wrapper,root=None):
    p=wrapper['payload']
    if wrapper.get('sha256') and wrapper['sha256']!=digest(p):raise ValueError('Source checksum mismatch')
    eng.validate_espn_summary(game,p)
    if p['header'].get('season',{}).get('type')!=2:raise ValueError('Not a verified regular-season game')
    record=outcome_data.extract(game,p)
    record.update(source={'provider':'ESPN','retrieved_at':wrapper.get('retrieved_at'),'provider_date':wrapper.get('provider_date'),'raw_hash':digest(p)},season_end=p['header']['season']['year'])
    if record['rows']:
        from collections import Counter
        teams=Counter(row['team'] for row in record['rows'])
        expected={game['homeTeam']['teamTricode'],game['awayTeam']['teamTricode']}
        if set(teams)!=expected or any(n!=5 for n in teams.values()):
            record['warnings'].append('Starter model unavailable: exactly five per matchup team required')
            record['rows']=[]
    seq=None
    if record['status']=='resolved' and record['rows']:
        try:seq=opening_data.extract(game,clean_box(p),allow_nonstarter=True)
        except (ValueError,KeyError,TypeError,IndexError) as e:record['warnings'].append('Opening sequence unavailable: '+str(e))
    # Keep full source events separately; no fabricated jump, possession or substitutions.
    firstq=[x for x in p.get('plays',[]) if x.get('period',{}).get('number')==1]
    record['source_opening_metadata']={'first_quarter_events':len(firstq),'substitution_events':sum('substitution' in str(x.get('type',{}).get('text','')).lower() or ' enters the game for ' in str(x.get('text','')).lower() for x in firstq),'first_scorer_starter_flag_source':'ESPN postgame boxscore; never pre-tip verification'}
    with connect(root) as c:
        exists=c.execute('SELECT raw_hash FROM games WHERE gid=?',(game['gameId'],)).fetchone()
        if exists:
            if exists[0]!=digest(p):raise ValueError('Conflicting source for existing game; original checkpoint preserved')
            return False
        c.execute('INSERT INTO games VALUES(?,?,?,?)',(game['gameId'],canonical(record),canonical(seq) if seq else None,digest(p)))
    return True

def failure(root,gid,stage,reason):
    with connect(root) as c:c.execute('INSERT INTO failures(at,gid,stage,reason) VALUES(?,?,?,?)',(datetime.now(timezone.utc).isoformat(),gid,stage,str(reason)))

def collect(start,end,root=None,limit=100,workers=2,progress=lambda s:None,client=None):
    if not 1<=limit<=500 or workers not in (1,2):raise ValueError('Choose 1–500 games and one or two workers')
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if a>b or (b-a).days>45 or b>=datetime.now(timezone.utc).date():raise ValueError('Choose up to 46 completed past dates')
    client=client or Client(root);games={};day=a
    while day<=b:
        try:
            wrapper=client.fetch(eng.ESPN_BASE+'/scoreboard',{'dates':day.strftime('%Y%m%d'),'limit':1000},'schedule_'+day.isoformat())
            for g in eng.parse_espn_schedule(wrapper['payload']):
                if g['gameStatus']==3 and start<=g['_date']<=end:games[g['gameId']]=g
        except Exception as e:
            failure(root,day.isoformat(),'schedule',type(e).__name__+': '+str(e))
            if isinstance(e,RateLimited):break
        day+=timedelta(days=1)
    with connect(root) as c:
        existing={r[0] for r in c.execute('SELECT gid FROM games')};attempts=dict(c.execute('SELECT gid,n FROM attempts'))
    pending=sorted((g for gid,g in games.items() if gid not in existing),key=lambda g:(attempts.get(g['gameId'],0),g['_date'],g['gameId']))[:limit]
    def fetch(g):
        try:return g,client.fetch(eng.ESPN_BASE+'/summary',{'event':g['gameId'].removeprefix('espn_')},g['gameId']),None
        except Exception as e:return g,None,e
    # Bound attempts and checkpoint attempts BEFORE requests; failed games remain retryable.
    with connect(root) as c:
        for g in pending:c.execute('INSERT INTO attempts VALUES(?,1) ON CONFLICT(gid) DO UPDATE SET n=n+1',(g['gameId'],))
    added=0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for g,w,error in pool.map(fetch,pending):
            try:
                if error:raise error
                added+=int(ingest(g,w,root))
            except Exception as e:failure(root,g['gameId'],'summary',type(e).__name__+': '+str(e))
            progress(f"Checkpoint {g['gameId']} · {added} new games")
    status={'start':start,'end':end,'scheduled_completed':len(games),'attempted':len(pending),'added':added,'remaining':max(0,len(set(games)-existing)-len(pending)),'finished_at':datetime.now(timezone.utc).isoformat()}
    with connect(root) as c:c.execute('INSERT OR REPLACE INTO status VALUES(?,?)',('last_collection',canonical(status)))
    return status

def dataset(root=None):
    records={};sequences={};history=[]
    with connect(root) as c:
        for gid,raw,seq in c.execute('SELECT gid,record,sequence FROM games ORDER BY gid'):
            r=json.loads(raw);records[gid]=r
            if seq:sequences[gid]=json.loads(seq)
            if r['status']=='resolved' and r['rows'] and sum(int(x['first_scorer']) for x in r['rows'])==1:
                valid,issues=rt.audit(r['rows'])
                if not issues:history.extend(valid)
    return history,sequences,records

def coverage(root=None):
    from collections import Counter
    h,s,r=dataset(root)
    with connect(root) as c:
        errors=[{'at':a,'game':g,'stage':st,'reason':reason} for a,g,st,reason in c.execute('SELECT at,gid,stage,reason FROM failures ORDER BY id')]
        status=c.execute("SELECT value FROM status WHERE key='last_collection'").fetchone()
    return {**outcome_data.audit(r),'usable_opening_sequences':len(s),'explicit_tips':sum(x.get('tip') is not None for x in s.values()),'seasons':dict(Counter(x['season_end'] for x in r.values())),'failures':errors,'last_collection':json.loads(status[0]) if status else None}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--start',required=True);parser.add_argument('--end',required=True);parser.add_argument('--limit',type=int,default=100);parser.add_argument('--root',type=Path);args=parser.parse_args()
    print(json.dumps(collect(args.start,args.end,args.root,args.limit,progress=lambda s:print(s,flush=True)),indent=2))

# One background job per folder in this local app process. No unattended scheduling.
_jobs={}
_jobs_lock=threading.Lock()

def start_job(name,work,root=None):
    root=Path(root or eng.DATA/'phase4');key=str(root.resolve())
    with _jobs_lock:
        if key in _jobs and _jobs[key].is_alive():raise ValueError('A Phase 4 job is already running in this app')
        def run():
            status={'job':name,'state':'running','started_at':datetime.now(timezone.utc).isoformat()}
            with connect(root) as c:c.execute('INSERT OR REPLACE INTO status VALUES(?,?)',('background',canonical(status)))
            try:status.update(state='completed',result=work())
            except Exception as e:status.update(state='failed',error=type(e).__name__+': '+str(e))
            status['finished_at']=datetime.now(timezone.utc).isoformat()
            with connect(root) as c:c.execute('INSERT OR REPLACE INTO status VALUES(?,?)',('background',canonical(status)))
        thread=threading.Thread(target=run,daemon=True,name='apex-phase4');_jobs[key]=thread;thread.start()
    return 'Started manual background job'

def job_status(root=None):
    root=Path(root or eng.DATA/'phase4');key=str(root.resolve())
    if not (root/'history.sqlite3').exists():return {'state':'idle','monitoring':'No unattended scheduler configured'}
    with connect(root) as c:row=c.execute("SELECT value FROM status WHERE key='background'").fetchone()
    status=json.loads(row[0]) if row else {'state':'idle'}
    with _jobs_lock:alive=key in _jobs and _jobs[key].is_alive()
    if alive:status['state']='running'
    elif status['state']=='running':status['state']='interrupted or another process; inspect before resuming'
    status['monitoring']='Manual jobs only; server must remain running'
    return status

def first_fg_fact(payload):
    """Observed first FG identity even if outside the recorded ten. Unknown stays unknown."""
    try:
        competitors=payload['header']['competitions'][0]['competitors'];teams={str(c['team']['id']):eng.espn_team(c['team']) for c in competitors}
        ordered=sorted((p for p in payload['plays'] if p.get('period',{}).get('number')==1),key=lambda p:int(p['sequenceNumber']))
        score=next(i for i,p in enumerate(ordered) if p.get('scoringPlay') and p.get('scoreValue',0)>0)
        index,play=next((i,p) for i,p in enumerate(ordered) if p.get('shootingPlay') is True and 'free throw' not in p.get('text','').lower())
        tid=str(play.get('team',{}).get('id',''));pid=str(play.get('participants',[{}])[0].get('athlete',{}).get('id',''))
        owners={str(side['team']['id']) for side in payload.get('boxscore',{}).get('players',[]) for stat in side.get('statistics',[]) for r in stat.get('athletes',[]) if str(r.get('athlete',{}).get('id',''))==pid}
        known=pid.isdigit() and int(pid)>0 and owners=={tid} and tid in teams
        return {'player_id':pid if known else None,'team':teams.get(tid),'before_first_score':index<=score,'identity_known':bool(known),'sequence':play['sequenceNumber']}
    except (KeyError,TypeError,ValueError,StopIteration,IndexError):return {'player_id':None,'identity_known':False,'before_first_score':None}
