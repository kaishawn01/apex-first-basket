"""Real PostgreSQL integration in CI; no public cloud service or live credentials."""
import os,uuid,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import phase5_store as storage

@unittest.skipUnless(os.environ.get('APEX_TEST_DATABASE_URL'),'Isolated PostgreSQL CI service not configured')
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        dsn=os.environ['APEX_TEST_DATABASE_URL'];parsed=urlsplit(dsn)
        if parsed.hostname not in ('localhost','127.0.0.1') or parsed.path!='/apex_phase5_ci':raise RuntimeError('Tests require the explicitly named local fixture database')
        self.schema='fixture_'+uuid.uuid4().hex;self.now=datetime.now(timezone.utc);self.s=storage.Store(dsn=dsn,schema=self.schema,clock=lambda:self.now);self.s.initialize();self.tmp=tempfile.TemporaryDirectory()
    def tearDown(self):
        with self.s.transaction(True) as c:c.execute('DROP SCHEMA "'+self.schema+'" CASCADE')
        self.tmp.cleanup()
    def test_reconnect_persistence_and_idempotence(self):
        a=self.s.append('a','one',{'v':1});other=storage.Store(dsn=self.s.dsn,schema=self.schema,clock=lambda:self.now);self.assertEqual(other.rows(),[a]);self.assertEqual(other.append('a','one',{'v':1}),a)
        with self.assertRaises(storage.Conflict):other.append('a','one',{'v':2})
    def test_concurrent_writers_preserve_chain(self):
        with ThreadPoolExecutor(4) as pool:list(pool.map(lambda n:self.s.append('a',str(n),{'v':n}),range(20)))
        self.assertEqual(len(self.s.rows()),20)
    def test_update_delete_truncate_prevented(self):
        self.s.append('a','one',{})
        for query in ["UPDATE apex_events SET key='changed'",'DELETE FROM apex_events','TRUNCATE apex_events']:
            with self.assertRaises(storage.StorageError):
                with self.s.transaction(True) as c:c.execute(query)
        self.assertEqual(len(self.s.rows()),1)
    def test_stale_fencing_and_lease_recovery(self):
        old=self.s.acquire('runner',5);self.assertIsNone(self.s.acquire('runner'));self.now+=timedelta(seconds=6);new=self.s.acquire('runner')
        with self.assertRaises(storage.LeaseLost):self.s.append('a','old',{},old)
        self.s.append('a','new',{},new)
    def test_interrupted_transaction_is_rolled_back(self):
        with self.assertRaises(storage.StorageError):
            with self.s.transaction(True) as c:c.execute("INSERT INTO apex_state VALUES('partial','1')");raise RuntimeError('fixture interruption')
        self.assertIsNone(self.s.state('partial'))
    def test_backup_recovery_cross_backend(self):
        self.s.append('a','one',{});self.s.append('a','two',{'n':2});p=Path(self.tmp.name)/'backup.json';self.s.export(p);local=storage.Store(Path(self.tmp.name)/'restore.db');local.restore(p);self.assertEqual(local.rows(),self.s.rows())
    def test_job_attempts_survive_reconnect(self):
        fence=self.s.acquire('runner');self.assertTrue(self.s.begin_job('task',fence));self.s.finish_job('task',fence,error='fixture timeout');other=storage.Store(dsn=self.s.dsn,schema=self.schema,clock=lambda:self.now);self.assertFalse(other.job_due('task'));self.now+=timedelta(seconds=31);self.assertTrue(other.job_due('task'))
    def test_append_receipts_and_forecast_payload_stay_immutable(self):
        a=self.s.append('prediction','game:10min',{'probabilities':{'1':.5,'OTHER':.5}});b=self.s.append('prediction','game:2min',{'probabilities':{'1':.6,'OTHER':.4}});self.assertNotEqual(a['hash'],b['hash']);self.s.append('result','outcome',{'prediction_hash':a['hash'],'actual':'OTHER'});self.assertEqual(self.s.get('prediction','game:10min'),a)
