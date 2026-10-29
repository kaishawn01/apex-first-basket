import unittest,tempfile,json,copy,os,sqlite3
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
import phase7_training as training,phase7_live as live,phase7_fixture as fixture
from phase6_fixture import FixtureProviders
from phase6_journal import Journal
from phase5_store import Store
from phase5_providers import ProviderError
from phase4_data import digest

class Phase7Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=datetime(2027,1,2,21,tzinfo=timezone.utc);self.j=Journal(self.root/'journal.json',clock=lambda:self.now);self.s=Store(self.root/'ops.db',clock=lambda:self.now);self.p=FixtureProviders(lambda:self.now);self.b=fixture.empty_bundle(self.p.game['_date'])
    def tearDown(self):self.tmp.cleanup()
    def generate(self,run='one',slot='manual'):return live.generate(self.j,self.s,self.p,self.p.game,self.b,slot,run,True)
    def test_schema_hash_tampering_rejected(self):
        b=copy.deepcopy(self.b);b['data']['history']=[{}]
        with self.assertRaises(ValueError):training.validate(b)
    def test_cutoff_future_rejected(self):
        with self.assertRaises(ValueError):training.validate(self.b,'2027-01-01')
    def test_unknown_top_level_data_rejected(self):
        b=copy.deepcopy(self.b);b['private_key']='secret'
        with self.assertRaises(ValueError):training.validate(b)
    def test_private_row_fields_rejected(self):
        from test_phase2 import sample_history
        h,s,l=sample_history();b=copy.deepcopy(self.b);h[0]['private_note']='secret';b['data']['history']=h;b['sha256']=digest(b['data'])
        with self.assertRaises(ValueError):training.validate(b)
    def test_unreviewed_rights_blocks_before_network(self):
        p=Mock()
        with self.assertRaises(ValueError):live.collect(self.j,self.s,p,self.b,'manual','x',Mock())
        p.schedule.assert_not_called();self.assertFalse(self.j.rows())
    def test_fixture_cannot_authorize_live(self):
        with self.assertRaises(ValueError):training.permission(self.b,{'owner_approved':True},self.now)
    def test_missing_provider_permission_rejected(self):
        b=copy.deepcopy(self.b);b['test_only']=False;g={'schema':1,'test_only':False,'data_sha256':b['sha256'],'provenance_sha256':b['provenance_sha256'],'owner_approved':True,'reviewed_at':self.now.isoformat(),'expires_at':(self.now+timedelta(days=1)).isoformat(),'providers':{}}
        with self.assertRaises(ValueError):training.permission(b,g,self.now)
    def test_permission_expiry_and_hash_bound(self):
        b=copy.deepcopy(self.b);b['test_only']=False;g={'schema':1,'test_only':False,'data_sha256':b['sha256'],'provenance_sha256':b['provenance_sha256'],'owner_approved':True,'reviewed_at':self.now.isoformat(),'expires_at':(self.now+timedelta(days=1)).isoformat(),'providers':{'ESPN':{'permission_verified':True,'scopes':['private_model_use','automated_collection','public_forecasts'],'evidence_reference':'SYNTHETIC TEST ONLY'}}}
        self.assertEqual(training.permission(b,g,self.now),g)
        with self.assertRaises(ValueError):training.permission(b,g,self.now+timedelta(days=2))
        g['data_sha256']='different'
        with self.assertRaises(ValueError):training.permission(b,g,self.now)
    def test_changed_manual_invocation_new_snapshot_same_retry_not(self):
        first,_=self.generate();_,added=self.generate();self.assertFalse(added);self.now+=timedelta(seconds=1);_,added=self.generate('two');self.assertTrue(added);self.assertEqual(self.j.rows('prediction')[0],first)
    def test_complete_probability_mass_and_top_five(self):
        r,_=self.generate();p=r['payload'];self.assertEqual(p['model_version'],'3.0.6');self.assertEqual(p['experiment'],live.EXPERIMENT)
        for model,probs in p['forecasts'].items():self.assertAlmostEqual(sum(probs.values()),1);self.assertEqual(len(p['top_five'][model]),5)
        self.assertEqual(p['training_cutoff_exclusive'],self.p.game['_date'])
    def test_missing_starters_rejected(self):
        self.p.rosters={t:[] for t in self.p.rosters}
        with self.assertRaises(ValueError):self.generate()
    def test_started_game_rejected(self):
        self.p.game['gameStatus']=2
        with self.assertRaises(ValueError):self.generate()
    def test_rescheduled_during_generation_rejected(self):
        self.p.schedule=lambda day,fresh=False:([{**self.p.game,'start_time':(self.now+timedelta(hours=1)).isoformat()}],{})
        with self.assertRaises(ValueError):self.generate()
    def test_publication_failure_stops_next_game(self):
        callback=Mock(side_effect=ValueError('offline'))
        with self.assertRaises(RuntimeError):live.collect(self.j,self.s,self.p,self.b,'manual','x',callback,test=True)
        callback.assert_called_once();self.assertEqual(len(self.j.rows('prediction')),1)
    def test_no_games_not_successful_capture(self):
        self.p.schedule=lambda day,fresh=False:([],{'retrieved_at':self.now.isoformat()});r=live.collect(self.j,self.s,self.p,self.b,'manual','x',Mock(),test=True);self.assertEqual(r['status'],'no eligible forecasts');self.assertEqual(r['published'],0)
    def test_delayed_checkpoint_not_backfilled(self):
        self.now+=timedelta(minutes=9,seconds=40);r=live.collect(self.j,self.s,self.p,self.b,'scheduled','x',Mock(),test=True);self.assertEqual(r['generated'],0);self.assertTrue(r['missed_windows'])
    def test_provider_failure_explicit(self):
        self.p.schedule=Mock(side_effect=ProviderError('HTTP 429 cooldown'));r=live.collect(self.j,self.s,self.p,self.b,'manual','x',Mock(),test=True);self.assertEqual(r['status'],'partial');self.assertTrue(r['errors'])
    def test_fixture_excluded_from_real_monitoring(self):
        self.generate();r=live.monitoring(self.j,{},self.now);self.assertEqual(r['real_forecasts'],0);self.assertEqual(r['remaining_reserved_attempt_allowance'],400)
    def test_old_experiments_preserved(self):
        self.assertEqual(live.cloud.EXPERIMENT,'apex-v3.0.5-cloud-01');self.assertEqual(live.cloud.old_protocol.EXPERIMENT,'apex-v3.0.4-prospective-01')
    def test_fixture_restart_separate_grader(self):
        path=self.root/'restart.json';fixture.exercise(path,'generate');original=Journal(path).rows('prediction');self.assertEqual(fixture.exercise(path,'grade')['graded'],1);self.assertEqual(Journal(path).rows('prediction'),original)
    def test_recorded_outcome_preserves_forecast(self):
        p,_=self.generate();self.now+=timedelta(hours=4);r=live.cloud.grade(self.j,self.p,test=True);self.assertEqual(r['graded'],1);self.assertEqual(self.j.rows('prediction'),[p])
    def test_training_builder_deterministic_and_read_only(self):
        import test_research,phase4_data,outcome_data
        f=test_research.OpeningResultEnrichmentTests();f.setUp();f.payload['header']['season']={'year':2026,'type':2};g=outcome_data.game_from_payload(f.payload);root=self.root/'history';phase4_data.ingest(g,{'payload':f.payload},root)
        path=root/'history.sqlite3';before=path.read_bytes();a,report=training.build(path,'2025-10-26');b,again=training.build(path,'2025-10-26');self.assertEqual(a,b);self.assertEqual(report,again);self.assertEqual(before,path.read_bytes());self.assertEqual(report['training_games'],1)
    def test_no_same_day_training(self):
        import test_research,phase4_data,outcome_data
        f=test_research.OpeningResultEnrichmentTests();f.setUp();f.payload['header']['season']={'year':2026,'type':2};root=self.root/'history';phase4_data.ingest(outcome_data.game_from_payload(f.payload),{'payload':f.payload},root)
        b,r=training.build(root/'history.sqlite3','2025-10-25');self.assertEqual(r['training_games'],0)

if __name__=='__main__':unittest.main()
