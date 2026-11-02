"""Append-only evidence store: local SQLite or explicitly configured PostgreSQL.

No remote resources are provisioned. Credentials are read only from environment.
"""
import json, os, sqlite3, uuid, re
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from urllib.parse import urlsplit, parse_qs
from phase4_data import canonical, digest
import first_basket_engine as eng

class StorageError(RuntimeError): pass
class Conflict(StorageError): pass
class LeaseLost(StorageError): pass

def utc(value):
    if value.tzinfo is None: raise ValueError('Timezone-aware clock required')
    return value.astimezone(timezone.utc)

class Store:
    def __init__(self,path=None,dsn=None,clock=None,schema="public"):
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}",schema):raise StorageError("Invalid database schema")
        self.schema=schema
        self.dsn=dsn; self.remote=dsn is not None
        self.path=Path(path or eng.DATA/'phase5'/'operations.sqlite3') if not self.remote else None
        if self.remote:
            parts=urlsplit(dsn);query=parse_qs(parts.query)
            if parts.scheme not in ('postgresql','postgres'):raise StorageError('Only PostgreSQL URLs are supported')
            if parts.hostname not in ('localhost','127.0.0.1','::1') and query.get('sslmode')!=['verify-full']:
                raise StorageError('Remote database requires sslmode=verify-full and a trusted certificate')
        else:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            if not self.path.exists():self.initialize()
    @contextmanager
    def transaction(self,write=False):
        c=None
        try:
            if self.remote:
                import psycopg
                c=psycopg.connect(self.dsn,connect_timeout=5,options='-c statement_timeout=15000')
                c.execute('SET search_path TO "'+self.schema+'", pg_catalog')
                if write:c.execute('SELECT pg_advisory_xact_lock(51490304)')
            else:
                c=sqlite3.connect(self.path,timeout=15)
                c.execute('PRAGMA busy_timeout=15000');c.execute('PRAGMA synchronous=FULL')
                c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield c
            c.commit()
        except (StorageError,ValueError):
            if c:c.rollback()
            raise
        except Exception as exc:
            if c:c.rollback()
            raise StorageError('Storage operation failed ('+type(exc).__name__+'); original records retained') from None
        finally:
            if c:c.close()
    def sql(self,c,query,args=()):return c.execute(query.replace('?', '%s') if self.remote else query,args)
    def initialize(self):
        with self.transaction(True) as c:
            if self.remote:c.execute('CREATE SCHEMA IF NOT EXISTS "'+self.schema+'"')
            ident='BIGSERIAL PRIMARY KEY' if self.remote else 'INTEGER PRIMARY KEY'
            statements=[f'CREATE TABLE IF NOT EXISTS apex_events(id {ident},kind TEXT NOT NULL,key TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL,previous TEXT NOT NULL,hash TEXT NOT NULL,UNIQUE(kind,key))',
                'CREATE TABLE IF NOT EXISTS apex_leases(name TEXT PRIMARY KEY,token TEXT NOT NULL,until_epoch DOUBLE PRECISION NOT NULL)',
                'CREATE TABLE IF NOT EXISTS apex_jobs(key TEXT PRIMARY KEY,state TEXT NOT NULL,attempts INTEGER NOT NULL,next_epoch DOUBLE PRECISION NOT NULL,last_error TEXT)',
                'CREATE TABLE IF NOT EXISTS apex_state(key TEXT PRIMARY KEY,value TEXT NOT NULL)']
            for s in statements:c.execute(s)
            if self.remote:
                c.execute("CREATE OR REPLACE FUNCTION apex_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'APEX evidence is immutable'; END; $$")
                c.execute('DROP TRIGGER IF EXISTS apex_no_change ON apex_events')
                c.execute('CREATE TRIGGER apex_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON apex_events FOR EACH STATEMENT EXECUTE FUNCTION apex_immutable()')
                c.execute('REVOKE ALL ON apex_events,apex_leases,apex_jobs,apex_state FROM PUBLIC')
            else:
                c.execute("CREATE TRIGGER IF NOT EXISTS apex_no_update BEFORE UPDATE ON apex_events BEGIN SELECT RAISE(ABORT,'APEX evidence is immutable'); END")
                c.execute("CREATE TRIGGER IF NOT EXISTS apex_no_delete BEFORE DELETE ON apex_events BEGIN SELECT RAISE(ABORT,'APEX evidence is immutable'); END")
    @staticmethod
    def decode(row):
        ident,kind,key,at,raw,previous,h=row
        return {'id':ident,'kind':kind,'key':key,'created_at':at,'payload':json.loads(raw),'previous':previous,'hash':h}
    @staticmethod
    def verify(rows):
        previous='';last=None
        for r in rows:
            expected=digest({k:r[k] for k in ('kind','key','created_at','payload','previous')})
            stamp=datetime.fromisoformat(r['created_at'])
            if stamp.tzinfo is None or (last is not None and stamp<last) or r['previous']!=previous or r['hash']!=expected:raise StorageError('Evidence chain integrity failure')
            previous=r['hash'];last=stamp
        return previous
    def rows(self,kind=None):
        with self.transaction() as c:
            if not self.remote and c.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise StorageError('SQLite structural integrity failure; preserve file and restore a verified backup')
            rows=[self.decode(r) for r in c.execute('SELECT * FROM apex_events ORDER BY id')]
        self.verify(rows)
        return [r for r in rows if kind is None or r['kind']==kind]
    def get(self,kind,key):
        with self.transaction() as c:r=self.sql(c,'SELECT * FROM apex_events WHERE kind=? AND key=?',(kind,key)).fetchone()
        return self.decode(r) if r else None
    def check_fence(self,c,fence):
        if fence is None:return
        name,token=fence;r=self.sql(c,'SELECT token,until_epoch FROM apex_leases WHERE name=?',(name,)).fetchone()
        if not r or r[0]!=token or r[1]<=utc(self.clock()).timestamp():raise LeaseLost('Job lease expired; stale worker cannot save evidence')
    def append(self,kind,key,payload,fence=None,deadline=None):
        raw=canonical(payload);payload=json.loads(raw)
        with self.transaction(True) as c:
            self.check_fence(c,fence)
            moment=utc(self.clock());now=moment.isoformat()
            if deadline is not None and moment>=utc(deadline):raise ValueError('Archive deadline passed while waiting for storage')
            if kind in ('snapshot','prediction') and payload.get('game'):
                start=datetime.fromisoformat(payload['game']['start_time'].replace('Z','+00:00'))
                if moment>=utc(start):raise ValueError('Cannot archive pre-tip evidence after scheduled start')
            old=self.sql(c,'SELECT * FROM apex_events WHERE kind=? AND key=?',(kind,key)).fetchone()
            if old:
                if old[4]!=raw:raise Conflict('Idempotency key has different content; original record retained')
                return self.decode(old)
            last=c.execute('SELECT hash,created_at FROM apex_events ORDER BY id DESC LIMIT 1').fetchone()
            if last and datetime.fromisoformat(last[1])>datetime.fromisoformat(now):raise StorageError('Clock moved backwards; append refused')
            previous=last[0] if last else '';h=digest({'kind':kind,'key':key,'created_at':now,'payload':payload,'previous':previous})
            self.sql(c,'INSERT INTO apex_events(kind,key,created_at,payload,previous,hash) VALUES(?,?,?,?,?,?)',(kind,key,now,raw,previous,h))
            r=self.sql(c,'SELECT * FROM apex_events WHERE kind=? AND key=?',(kind,key)).fetchone()
        return self.decode(r)
    def state(self,key,default=None):
        with self.transaction() as c:r=self.sql(c,'SELECT value FROM apex_state WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else default
    def set_state(self,key,value):
        with self.transaction(True) as c:self.sql(c,'INSERT INTO apex_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,canonical(value)))
    def acquire(self,name,seconds=300):
        token=uuid.uuid4().hex
        with self.transaction(True) as c:
            now=utc(self.clock()).timestamp()
            old=self.sql(c,'SELECT until_epoch FROM apex_leases WHERE name=?',(name,)).fetchone()
            if old and old[0]>now:return None
            self.sql(c,'INSERT INTO apex_leases VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET token=excluded.token,until_epoch=excluded.until_epoch',(name,token,now+seconds))
        return (name,token)
    def renew(self,fence,seconds=300):
        with self.transaction(True) as c:
            self.check_fence(c,fence);self.sql(c,'UPDATE apex_leases SET until_epoch=? WHERE name=? AND token=?',(utc(self.clock()).timestamp()+seconds,*fence))
    def release(self,fence):
        if fence is None:return
        with self.transaction(True) as c:self.sql(c,'UPDATE apex_leases SET until_epoch=0 WHERE name=? AND token=?',fence)
    def job_due(self,key):
        with self.transaction() as c:r=self.sql(c,'SELECT state,attempts,next_epoch FROM apex_jobs WHERE key=?',(key,)).fetchone()
        return not r or (r[0]!='done' and r[1]<3 and r[2]<=utc(self.clock()).timestamp())
    def begin_job(self,key,fence):
        with self.transaction(True) as c:
            self.check_fence(c,fence)
            r=self.sql(c,'SELECT state,attempts,next_epoch FROM apex_jobs WHERE key=?',(key,)).fetchone()
            now=utc(self.clock()).timestamp()
            if r and (r[0]=='done' or r[1]>=3 or r[2]>now):return False
            self.sql(c,'INSERT INTO apex_jobs VALUES(?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET state=excluded.state,attempts=excluded.attempts,next_epoch=excluded.next_epoch,last_error=excluded.last_error',(key,'running',(r[1] if r else 0)+1,now+30,None))
        return True
    def finish_job(self,key,fence,error=None):
        with self.transaction(True) as c:
            self.check_fence(c,fence)
            r=self.sql(c,'SELECT attempts FROM apex_jobs WHERE key=?',(key,)).fetchone()
            if not r:raise ValueError('Unknown job')
            self.sql(c,'UPDATE apex_jobs SET state=?,next_epoch=?,last_error=? WHERE key=?',('failed' if error else 'done',utc(self.clock()).timestamp()+min(300,30*2**(r[0]-1)),error,key))
    def export(self,path):
        with self.transaction(True) as c:
            rows=[self.decode(r) for r in c.execute('SELECT * FROM apex_events ORDER BY id')]
            self.verify(rows)
            state=[list(x) for x in c.execute('SELECT key,value FROM apex_state ORDER BY key')]
            jobs=[list(x) for x in c.execute('SELECT key,state,attempts,next_epoch,last_error FROM apex_jobs ORDER BY key')]
        operational={'state':state,'jobs':jobs}
        bundle={'schema':2,'events':rows,'head':self.verify(rows),'count':len(rows),'operational':operational,'operational_hash':digest(operational)}
        path=Path(path)
        # Exclusive create: backups cannot accidentally replace earlier backups.
        with path.open('x',encoding='utf8') as stream:stream.write(canonical(bundle))
        return {'events':len(rows),'head':bundle['head']}
    def restore(self,path):
        bundle=json.loads(Path(path).read_text());rows=bundle['events']
        if bundle.get('schema')!=2 or len(rows)!=bundle['count'] or self.verify(rows)!=bundle['head'] or digest(bundle.get('operational'))!=bundle.get('operational_hash'):raise StorageError('Invalid backup')
        with self.transaction(True) as c:
            if any(c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('apex_events','apex_state','apex_jobs')):raise Conflict('Restore requires an empty destination')
            for r in rows:
                self.sql(c,'INSERT INTO apex_events(kind,key,created_at,payload,previous,hash) VALUES(?,?,?,?,?,?)',(r['kind'],r['key'],r['created_at'],canonical(r['payload']),r['previous'],r['hash']))
            for key,value in bundle['operational']['state']:
                self.sql(c,'INSERT INTO apex_state VALUES(?,?)',(key,value))
            for key,state,attempts,next_epoch,error in bundle['operational']['jobs']:
                if state=='running':state='failed';next_epoch=max(next_epoch,utc(self.clock()).timestamp()+60);error='Recovered interrupted job'
                self.sql(c,'INSERT INTO apex_jobs VALUES(?,?,?,?,?)',(key,state,attempts,next_epoch,error))
        return len(rows)

def configured_store(clock=None):
    dsn=os.environ.get('APEX_DATABASE_URL')
    return Store(dsn=dsn,clock=clock,schema=os.environ.get("APEX_DATABASE_SCHEMA","public")) if dsn else Store(clock=clock)
