import copy,json,os,tempfile,unittest,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
from concurrent.futures import ThreadPoolExecutor
import requests
import phase6_cloud as cloud,phase6_journal as journal,phase6_git as archive,phase6_metrics as metrics
from phase6_fixture import FixtureProviders,exercise
from phase5_store import Store
from phase5_providers import ProviderError

class CloudTests(unittest.TestCase):
    def setUp(self):
        self.legacy_version=patch('updater.current_version',return_value='3.0.5');self.legacy_version.start();self.addCleanup(self.legacy_version.stop)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=datetime(2027,1,2,21,tzinfo=timezone.utc);self.j=journal.Journal(self.root/'journal.json',clock=lambda:self.now);self.s=Store(self.root/'ops.db',clock=lambda:self.now);self.p=FixtureProviders(lambda:self.now)
    def tearDown(self):self.tmp.cleanup()
    def forecast(self,slot='checkpoint-10',test=True):return cloud.generate(self.j,self.s,self.p,self.p.game,([],{},{}),slot,'test-run',test)
    def test_same_existing_model_probabilities_and_ids(self):
        r,added=self.forecast();p=r['payload'];self.assertTrue(added);self.assertEqual(p['model_version'],'3.0.5');self.assertEqual(len(p['forecasts']),7)
        for v in p['forecasts'].values():self.assertAlmostEqual(sum(v.values()),1)
        self.assertEqual(p['trials'],2000);self.assertIn('OTHER',p['forecasts']['Baseline']);self.assertFalse(p['actionable'])
    def test_multiple_snapshots_preserve_original(self):
        first,_=self.forecast('morning');self.now+=timedelta(seconds=1);second,_=self.forecast('updated');self.assertNotEqual(first['hash'],second['hash']);self.assertEqual(self.j.rows('prediction')[0],first)
    def test_retry_idempotent(self):
        first,_=self.forecast();before=self.j.read();again,added=self.forecast();self.assertFalse(added);self.assertEqual(first,again);self.assertEqual(before,self.j.read())
    def test_concurrent_append_serializes(self):
        with ThreadPoolExecutor(4) as pool:list(pool.map(lambda i:self.j.append('run',str(i),{'v':i}),range(12)))
        self.assertEqual(len(self.j.rows()),12)
    def test_conflicting_duplicate_rejected(self):
        self.j.append('run','x',{'v':1})
        with self.assertRaises(ValueError):self.j.append('run','x',{'v':2})
    def test_tampered_chain_detected(self):
        self.j.append('run','x',{});d=self.j.read();d['events'][0]['payload']['x']=1;self.j.path.write_text(json.dumps(d))
        with self.assertRaises(ValueError):self.j.read()
    def test_atomic_failure_preserves_previous(self):
        self.j.append('run','x',{});before=self.j.path.read_bytes()
        with patch('os.replace',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):self.j.append('run','y',{})
        self.assertEqual(before,self.j.path.read_bytes())
    def test_capacity_stops_without_delete(self):
        self.j.append('run','x',{});before=self.j.path.read_bytes()
        with patch.object(journal,'MAX_RECORDS',1):
            with self.assertRaises(ValueError):self.j.append('run','y',{})
        self.assertEqual(before,self.j.path.read_bytes())
    def test_raw_provider_kind_forbidden(self):
        with self.assertRaises(ValueError):self.j.append('provider_response','x',{})
    def test_export_has_no_raw_roster_or_secret(self):
        r,_=self.forecast();s=json.dumps(r);self.assertNotIn('source_responses',s);self.assertNotIn('boxscore',s);self.assertNotIn('Authorization',s);self.assertIsNone(r['payload']['market_odds'])
    def test_paid_host_and_redirect_credentials_blocked(self):
        get=Mock();b=cloud.BudgetGet(self.j,self.s,'x',get=get)
        for url in ['https://api.balldontlie.io/v1/teams','https://api.the-odds-api.com/v4/sports','http://cdn.nba.com/x']:
            with self.assertRaises(ProviderError):b(url)
        with self.assertRaises(ProviderError):b('https://cdn.nba.com/x',headers={'Authorization':'secret'})
        get.assert_not_called()
    def test_budget_limits_attempts_and_no_redirects(self):
        get=Mock();b=cloud.BudgetGet(self.j,self.s,'x',get=get,limit=2)
        for _ in range(2):b('https://cdn.nba.com/x')
        with self.assertRaises(ProviderError):b('https://cdn.nba.com/x')
        self.assertEqual(get.call_count,2);self.assertFalse(get.call_args.kwargs['allow_redirects'])
    def test_no_provider_call_when_disabled(self):
        with self.assertRaises(ValueError):cloud.run(self.j,store=self.s,providers=Mock())
    def test_missing_training_stops_without_api(self):
        p=Mock();r=cloud.run(self.j,store=self.s,providers=p,enabled=True);self.assertEqual(r['status'],'failed');p.schedule.assert_not_called()
    def test_missing_lineup_no_forecast(self):
        self.p.rosters={t:[] for t in self.p.rosters}
        with self.assertRaises(ValueError):self.forecast()
        self.assertFalse(self.j.rows('prediction'))
    def test_pretip_deadline(self):
        self.p.game['start_time']=(self.now+timedelta(seconds=15)).isoformat()
        with self.assertRaises(ValueError):self.forecast()
    def test_fresh_schedule_reschedule_rejects(self):
        original=self.p.schedule
        self.p.schedule=lambda day,fresh=False:([{**self.p.game,'start_time':(self.now+timedelta(hours=1)).isoformat()}],{})
        with self.assertRaises(ValueError):self.forecast()
    def test_frozen_drift_rejected(self):
        cloud.register(self.j)
        with patch.object(cloud,'specification',return_value={}):
            with self.assertRaises(ValueError):cloud.register(self.j)
    def test_utc_dst_morning(self):
        for month,hour in [(1,15),(7,14)]:
            now=datetime(2027,month,2,hour,tzinfo=timezone.utc);g={**self.p.game,'_date':now.date().isoformat(),'start_time':(now+timedelta(hours=6)).isoformat()}
            self.assertIn('morning',cloud.due_slots(now,g));self.assertNotIn('morning',cloud.due_slots(now+timedelta(minutes=16),g))
    def test_game_specific_early_and_late(self):
        for hour in [3,16]:
            now=self.now.replace(hour=hour);g={**self.p.game,'_date':now.astimezone(cloud.ET).date().isoformat(),'start_time':(now+timedelta(minutes=10)).isoformat()};self.assertIn('checkpoint-10',cloud.due_slots(now,g));self.assertEqual(cloud.due_slots(now+timedelta(minutes=11),g),[])
    def test_grade_after_completed_only_and_idempotent(self):
        r,_=self.forecast();self.assertEqual(cloud.grade(self.j,self.p,test=True)['graded'],0);self.now+=timedelta(hours=4)
        self.p.raw['header']['competitions'][0]['status']['type']['completed']=False;self.assertEqual(cloud.grade(self.j,self.p,test=True)['graded'],0)
        self.p.raw['header']['competitions'][0]['status']['type']['completed']=True;self.assertEqual(cloud.grade(self.j,self.p,test=True)['graded'],1);self.assertEqual(cloud.grade(self.j,self.p,test=True)['graded'],0);self.assertEqual(self.j.rows('prediction'),[r])
    def test_unavailable_result_pending(self):
        self.forecast();self.now+=timedelta(hours=4);self.p.result=Mock(side_effect=ProviderError('failure'));r=cloud.grade(self.j,self.p,test=True);self.assertTrue(r['errors']);self.assertFalse(self.j.rows('result'))
    def test_wrong_game_result_rejected(self):
        self.forecast();self.now+=timedelta(hours=4);self.p.raw['header']['id']='999';self.assertEqual(cloud.grade(self.j,self.p,test=True)['graded'],0)
    def test_fixture_never_in_live_metrics(self):
        self.forecast();self.now+=timedelta(hours=4);cloud.grade(self.j,self.p,test=True);self.assertEqual(metrics.evaluate(self.j)['predictions'],0);self.assertEqual(metrics.evaluate(self.j,test=True)['graded_snapshots'],1)
    def test_live_missing_durable_receipt_excluded(self):
        self.forecast(test=False);self.now+=timedelta(hours=4);cloud.grade(self.j,self.p);r=metrics.evaluate(self.j);self.assertEqual(r['graded_snapshots'],0);self.assertTrue(r['excluded'])
    def test_late_publication_excluded(self):
        r,_=self.forecast(test=False);self.now+=timedelta(hours=4);cloud.grade(self.j,self.p);receipts={r['hash']:{'committed_at':r['created_at'],'verified_remote_at':self.now.isoformat()}};self.assertEqual(metrics.evaluate(self.j,receipts)['graded_snapshots'],0)
    def test_empty_run_not_prediction_success(self):
        self.p.game['start_time']=(self.now+timedelta(hours=5)).isoformat();r=cloud.run(self.j,'scheduled',([],{},{}),self.p,self.s,enabled=True);self.assertEqual(r['status'],'completed without new predictions')
    def test_legacy_protocol_unchanged(self):
        self.assertEqual(cloud.old_protocol.EXPERIMENT,'apex-v3.0.4-prospective-01');self.assertEqual(cloud.specification()['experiment'],'apex-v3.0.5-cloud-01')
    def test_training_requires_publication_review(self):
        p=self.root/'training.json';p.write_text('{}')
        with self.assertRaises(ValueError):cloud.load_training(p)

    def test_daily_quota_reservations_survive_restart(self):
        for i in range(5):cloud.reserve_budget(self.j,str(i))
        restarted=journal.Journal(self.j.path,clock=lambda:self.now)
        with self.assertRaises(ProviderError):cloud.reserve_budget(restarted,'sixth')
        self.assertEqual(len(restarted.rows('budget')),5)
    def test_fixture_cloud_no_live_service_required(self):
        with patch.dict(os.environ,{'BALLDONTLIE_API_KEY':'do-not-use','SPORTSDATAIO_API_KEY':'do-not-use','APEX_SPORTSDATAIO_LICENSED_LIVE':'1'}):
            p=cloud.free_providers(self.s,self.j,'free')
            with self.assertRaises(ProviderError):p.injuries()
            self.assertFalse(p.injury_key);self.assertFalse(p.sports_key)
    def test_current_run_no_forecast_leaves_report(self):
        p=Mock();p.schedule.side_effect=ProviderError('timeout');r=cloud.run(self.j,'manual',([],{},{}),p,self.s,enabled=True)
        self.assertEqual(r['status'],'failed');self.assertEqual(len(self.j.rows('run')),1)

class GitTests(unittest.TestCase):
    def setUp(self):
        # Fixed legacy fixture clock avoids an incidental midnight game-date rollover.
        fixed=datetime(2027,1,2,21,tzinfo=timezone.utc)
        clock_patch=patch('phase6_fixture.datetime');mock_clock=clock_patch.start();mock_clock.now.return_value=fixed;self.addCleanup(clock_patch.stop)
        journal_patch=patch('phase6_fixture.Journal',side_effect=lambda path:journal.Journal(path,clock=lambda:fixed));journal_patch.start();self.addCleanup(journal_patch.stop)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.bare=self.root/'remote.git';self.work=self.root/'work';subprocess.run(['git','init','--bare',str(self.bare)],check=True,capture_output=True);subprocess.run(['git','clone',str(self.bare),str(self.work)],check=True,capture_output=True);archive.git(self.work,'checkout','-b',archive.BRANCH);(self.work/'README.md').write_text('fixture');archive.git(self.work,'add','README.md');archive.git(self.work,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','init');archive.git(self.work,'push','origin','HEAD');self.rel='fixtures/'+'a'*40+'/journal.json'
    def tearDown(self):self.tmp.cleanup()
    def test_forecast_survives_new_clone_grading_and_duplicate_publish(self):
        exercise(self.work/self.rel,'generate');receipt=archive.publish(self.work,self.rel);self.assertTrue(receipt['persisted']);clone=self.root/'fresh';subprocess.run(['git','clone','--branch',archive.BRANCH,str(self.bare),str(clone)],check=True,capture_output=True)
        original=journal.Journal(clone/self.rel).rows('prediction');r=exercise(clone/self.rel,'grade');self.assertEqual(r['graded'],1);archive.publish(clone,self.rel);self.assertEqual(journal.Journal(clone/self.rel).rows('prediction'),original);self.assertFalse(archive.publish(clone,self.rel)['changed'])
    def test_wrong_branch_refused(self):
        archive.git(self.work,'checkout','-b','main')
        with self.assertRaises(ValueError):archive.publish(self.work,self.rel)
    def test_non_fast_forward_rejected(self):
        clone=self.root/'other';subprocess.run(['git','clone','--branch',archive.BRANCH,str(self.bare),str(clone)],check=True,capture_output=True);exercise(self.work/self.rel,'generate');archive.publish(self.work,self.rel);exercise(clone/self.rel,'generate')
        with self.assertRaises(ValueError):archive.publish(clone,self.rel)
    def test_truncation_rejected(self):
        exercise(self.work/self.rel,'generate');archive.publish(self.work,self.rel);p=self.work/self.rel;p.write_text(json.dumps({'schema':1,'events':[],'head':''}))
        with self.assertRaises(ValueError):archive.publish(self.work,self.rel)

if __name__=='__main__':unittest.main()
