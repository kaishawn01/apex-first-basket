import copy,json,os,sqlite3,tempfile,unittest,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock,patch
from concurrent.futures import ThreadPoolExecutor
import requests
import phase5_store as storage,phase5_integrity as integrity,phase5_providers as providers,phase5_protocol as protocol,phase5_runner as runner
import phase4_data as data,phase4_forward as forward,outcome_data
import test_dashboard
from test_phase2 import sample_history
import test_research

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'ops.sqlite3';self.now=datetime(2027,1,2,21,tzinfo=timezone.utc);self.s=storage.Store(self.path,clock=lambda:self.now)
    def tearDown(self):self.tmp.cleanup()
    def test_append_survives_restart_and_duplicates_are_idempotent(self):
        a=self.s.append('a','1',{'v':1});self.assertEqual(a,self.s.append('a','1',{'v':1}));self.assertEqual(storage.Store(self.path).rows(),[a])
        with self.assertRaises(storage.Conflict):self.s.append('a','1',{'v':2})
    def test_update_delete_blocked(self):
        self.s.append('a','1',{})
        for q in ["UPDATE apex_events SET key='2'",'DELETE FROM apex_events']:
            with self.assertRaises(storage.StorageError):
                with self.s.transaction(True) as c:c.execute(q)
    def test_tampering_detected(self):
        self.s.append('a','1',{})
        with sqlite3.connect(self.path) as c:c.execute('DROP TRIGGER apex_no_update');c.execute("UPDATE apex_events SET payload='{}x'")
        with self.assertRaises((storage.StorageError,ValueError)):self.s.rows()
    def test_concurrent_writes_have_one_chain(self):
        with ThreadPoolExecutor(4) as pool:list(pool.map(lambda i:self.s.append('a',str(i),{'i':i}),range(20)))
        self.assertEqual(len(self.s.rows()),20)
    def test_concurrent_duplicate_is_single_record(self):
        with ThreadPoolExecutor(4) as pool:list(pool.map(lambda i:self.s.append('a','same',{}),range(10)))
        self.assertEqual(len(self.s.rows()),1)
    def test_stale_worker_cannot_save_after_lease_recovery(self):
        old=self.s.acquire('job',10);self.assertIsNone(self.s.acquire('job',10));self.now+=timedelta(seconds=11);new=self.s.acquire('job',10)
        with self.assertRaises(storage.LeaseLost):self.s.append('a','1',{},old)
        self.s.append('a','1',{},new);self.s.release(old);self.s.renew(new)
    def test_retry_budget_and_backoff(self):
        fence=self.s.acquire('runner',1000)
        for i in range(3):
            self.assertTrue(self.s.begin_job('job',fence));self.s.finish_job('job',fence,error='provider unavailable');self.assertFalse(self.s.job_due('job'));self.now+=timedelta(seconds=130)
        self.assertFalse(self.s.job_due('job'));self.assertFalse(self.s.begin_job('job',fence))
    def test_completed_job_not_repeated(self):
        fence=self.s.acquire('runner');self.s.begin_job('x',fence);self.s.finish_job('x',fence);self.assertFalse(self.s.begin_job('x',fence))
    def test_clock_reversal_and_naive_time_rejected(self):
        self.s.append('a','1',{});self.now-=timedelta(seconds=1)
        with self.assertRaises(storage.StorageError):self.s.append('a','2',{})
        self.now=self.now.replace(tzinfo=None)
        with self.assertRaises(ValueError):self.s.append('a','2',{})
    def test_backup_restore_exact_chain_empty_only(self):
        self.s.append('a','1',{});p=Path(self.tmp.name)/'backup.json';self.s.export(p);restored=storage.Store(Path(self.tmp.name)/'restored.db');self.assertEqual(restored.restore(p),1);self.assertEqual(restored.rows(),self.s.rows())
        with self.assertRaises(storage.Conflict):restored.restore(p)
        with self.assertRaises(FileExistsError):self.s.export(p)
    def test_backup_corruption_fails_before_any_insert(self):
        p=Path(self.tmp.name)/'backup.json';self.s.append('a','1',{});self.s.export(p);b=json.loads(p.read_text());b['head']='bad';p.write_text(json.dumps(b));other=storage.Store(Path(self.tmp.name)/'new.db')
        with self.assertRaises(storage.StorageError):other.restore(p)
        self.assertEqual(other.rows(),[])
    def test_remote_requires_authenticated_tls_and_errors_redacted(self):
        with self.assertRaises(storage.StorageError):storage.Store(dsn='postgresql://user:secret@cloud.invalid/db')
        s=storage.Store(dsn='postgresql://user:secret@127.0.0.1:1/db')
        with self.assertRaises(storage.StorageError) as e:s.rows()
        self.assertNotIn('secret',str(e.exception));self.assertNotIn('user:',str(e.exception))
    def test_interrupted_transaction_rolls_back(self):
        with self.assertRaises(storage.StorageError):
            with self.s.transaction(True) as c:c.execute("INSERT INTO apex_state VALUES('x','1')");raise RuntimeError('interrupted')
        self.assertIsNone(self.s.state('x'))

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'ledger';self.cache=Path(self.tmp.name)/'cache';self.cache.mkdir();f=test_research.OpeningResultEnrichmentTests();f.setUp();self.p=copy.deepcopy(f.payload);self.p['header']['season']={'year':2026,'type':2};self.g=outcome_data.game_from_payload(self.p);self.path=self.cache/(self.g['gameId']+'.json');self.path.write_text(json.dumps(self.p))
    def tearDown(self):self.tmp.cleanup()
    def test_incomplete_import_detected_then_repaired_idempotently(self):
        a=integrity.reconcile(self.root,[self.cache]);self.assertEqual(a['missing_before'],[self.g['gameId']]);self.assertFalse(a['healthy'])
        b=integrity.reconcile(self.root,[self.cache],True);self.assertTrue(b['healthy']);self.assertEqual(b['restored'],[self.g['gameId']]);self.assertTrue(integrity.reconcile(self.root,[self.cache])['healthy'])
    def test_bad_filename_and_conflicting_raw_not_silently_imported(self):
        other=Path(self.tmp.name)/'other';other.mkdir();changed=copy.deepcopy(self.p);changed['extra']=True;(other/self.path.name).write_text(json.dumps(changed));report=integrity.reconcile(self.root,[self.cache,other],True);self.assertFalse(report['healthy']);self.assertEqual(report['restored'],[])
        self.path.rename(self.cache/'espn_123.json');self.assertTrue(integrity.reconcile(self.root,[self.cache])['errors'])
    def test_identical_duplicate_cache_is_reported_not_duplicated(self):
        other=Path(self.tmp.name)/'other';other.mkdir();(other/self.path.name).write_text(self.path.read_text());r=integrity.reconcile(self.root,[self.cache,other],True);self.assertTrue(r['healthy']);self.assertEqual(r['duplicate_cache_copies'][0]['copies'],2)
    def test_insert_and_receipt_are_atomic(self):
        with data.connect(self.root) as c:c.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON import_receipts BEGIN SELECT RAISE(ABORT,'fixture crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):data.ingest(self.g,{'payload':self.p},self.root)
        self.assertEqual(data.coverage(self.root)['games'],0)
        with data.connect(self.root) as c:c.execute('DROP TRIGGER fail_receipt')
        self.assertTrue(integrity.reconcile(self.root,[self.cache],True)['healthy'])
    def test_process_killed_inside_transaction_recovers(self):
        with data.connect(self.root):pass
        script="import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute(\"INSERT INTO status VALUES('crash','1')\");os._exit(9)"
        r=subprocess.run([sys.executable,'-c',script,str(self.root/'history.sqlite3')]);self.assertEqual(r.returncode,9)
        with data.connect(self.root) as c:self.assertIsNone(c.execute("SELECT value FROM status WHERE key='crash'").fetchone())
        self.assertTrue(integrity.reconcile(self.root,[self.cache],True)['healthy'])
    def test_concurrent_same_import_and_receipt_single(self):
        with data.connect(self.root):pass
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:data.ingest(self.g,{'payload':self.p},self.root),range(2)))
        self.assertEqual(sum(results),1);self.assertEqual(integrity.reconcile(self.root,[self.cache])['receipted_games'],1)
    def test_sync_preserves_history_and_deduplicates(self):
        integrity.reconcile(self.root,[self.cache],True);s=storage.Store(Path(self.tmp.name)/'ops.db');self.assertEqual(integrity.sync_history(s,self.root)['added'],1);self.assertEqual(integrity.sync_history(s,self.root)['added'],0);h,seq,r=integrity.model_data(s);self.assertEqual(len(r),1);self.assertTrue(h);self.assertTrue(seq)

class TransportTests(unittest.TestCase):
    setUp=StoreTests.setUp
    tearDown=StoreTests.tearDown
    def response(self,status=200,payload=None,headers=None):
        r=Mock(status_code=status,headers=headers or {});r.json.return_value=payload or {'ok':True};return r
    def test_timeout_exponential_backoff_bounded_redacted(self):
        get=Mock(side_effect=requests.Timeout('private-token'));sleep=Mock();t=providers.Transport(self.s,get,sleep)
        with self.assertRaises(providers.ProviderError) as e:t.fetch('NBA','https://example.test')
        self.assertEqual(get.call_count,3);self.assertEqual([x.args[0] for x in sleep.call_args_list],[1,2]);self.assertNotIn('private-token',str(e.exception));self.assertNotIn('private-token',json.dumps(self.s.rows()))
    def test_429_cooldown_survives_restart(self):
        get=Mock(return_value=self.response(429,headers={'Retry-After':'600'}));t=providers.Transport(self.s,get,lambda _:None)
        with self.assertRaises(providers.Cooldown):t.fetch('NBA','https://example.test')
        with self.assertRaises(providers.Cooldown):providers.Transport(storage.Store(self.path,clock=lambda:self.now),get).fetch('NBA','https://example.test')
        self.assertEqual(get.call_count,1)
    def test_cache_preserves_retrieval_time_and_no_key(self):
        get=Mock(return_value=self.response());t=providers.Transport(self.s,get);a=t.fetch('NBA','https://example.test',headers={'Authorization':'private-token'},ttl=30);self.now+=timedelta(seconds=10);b=t.fetch('NBA','https://example.test',ttl=30)
        self.assertEqual(a,b);get.assert_called_once();self.assertNotIn('private-token',json.dumps(self.s.rows()))
    def test_403_no_retry_and_malformed_json(self):
        get=Mock(return_value=self.response(403));t=providers.Transport(self.s,get)
        with self.assertRaises(providers.ProviderError):t.fetch('NBA','https://example.test')
        get.assert_called_once();r=self.response();r.json.side_effect=ValueError('bad');get.return_value=r
        with self.assertRaises(providers.ProviderError):t.fetch('NBA','https://example.test')

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f=test_dashboard.NBAConfirmedLineupTests();self.f.setUp();self.now=self.f.now;self.p=copy.deepcopy(self.f.payload)
        for side in ('homeTeam','awayTeam'):
            for row in self.p['games'][0][side]['players']:row['timestamp']=self.now.isoformat()
    def wrap(self,p=None,provider='NBA'):
        p=self.p if p is None else p;return {'provider':provider,'payload':p,'retrieved_at':self.now.isoformat(),'sha256':data.digest(p)}
    def resolve(self,p=None,injuries=None,manual=None):return providers.resolve(self.f.game,self.f.rosters,[],[self.wrap(p)],injuries or [],self.now.isoformat(),self.now,manual)
    def test_explicit_provider_confirmation_maps_current_roster(self):
        r=self.resolve();self.assertTrue(r['provider_verified']);self.assertEqual(r['cohort'],'provider-confirmed');self.assertFalse(r['actionable'])
    def test_expected_naive_old_and_duplicate_never_official(self):
        for field,value in [('lineupStatus','Expected'),('timestamp','2027-01-02T16:00:00'),('timestamp','2027-01-01T21:00:00Z'),('personId',101)]:
            p=copy.deepcopy(self.p);p['games'][0]['awayTeam']['players'][0][field]=value;self.assertFalse(self.resolve(p)['provider_verified'])
    def test_roster_trade_mismatch_duplicate_and_inactive(self):
        self.f.rosters['BOS'].pop(0);r=self.resolve();self.assertFalse(r['provider_verified']);self.assertTrue(r['warnings'])
        self.f.rosters['BOS'].append(self.f.rosters['NYK'][0]);self.assertFalse(self.resolve()['valid_identities'])
    def test_out_and_questionable_are_different(self):
        r=self.resolve(injuries=[{'team':'BOS','player':'BOS Player 0','status':'Out'}]);self.assertFalse(r['provider_verified']);self.assertEqual(r['cohort'],'incomplete')
        r=self.resolve(injuries=[{'team':'BOS','player':'BOS Player 0','status':'Questionable'}]);self.assertTrue(r['provider_verified']);self.assertTrue(any('Questionable' in x for x in r['warnings']))
    def test_stale_cache_and_unknown_timezone_withhold_confirmation(self):
        w=self.wrap();w['retrieved_at']=(self.now-timedelta(minutes=6)).isoformat()
        with self.assertRaises(ValueError):providers.nba_evidence(w,self.f.game,self.f.rosters,self.now)
        w=self.wrap();w['provider_age']='601'
        with self.assertRaises(ValueError):providers.nba_evidence(w,self.f.game,self.f.rosters,self.now)
    def test_late_lineup_change_detected_by_identity(self):
        a=self.resolve();p=copy.deepcopy(self.p);p['games'][0]['awayTeam']['players'][0].update(playerName='BOS Player 5',personId=105);b=self.resolve(p);self.assertNotEqual(a['lineups'],b['lineups']);self.assertTrue(b['provider_verified'])
    def sports_payload(self):
        p={'GameID':1,'Status':'Scheduled','DateTime':self.f.game['start_time'],'HomeTeam':'NYK','AwayTeam':'BOS','HomeTeamID':200,'AwayTeamID':100}
        for side,team,tid in [('Home','NYK',200),('Away','BOS',100)]:p[side+'Lineup']=[{'PlayerID':tid+i,'Team':team,'TeamID':tid,'FirstName':team,'LastName':'Player '+str(i),'Starting':True,'Confirmed':True,'LineupStatus':'Starting'} for i in range(5)]
        return [p]
    def test_sportsdata_explicit_status_and_duplicate_identity(self):
        p=self.sports_payload();r,_=providers.sports_evidence(self.wrap(p,'SportsDataIO'),self.f.game,self.f.rosters,self.now);self.assertEqual(r['BOS']['status'],'provider-confirmed')
        p[0]['AwayLineup'][0]['Confirmed']=False;r,_=providers.sports_evidence(self.wrap(p,'SportsDataIO'),self.f.game,self.f.rosters,self.now);self.assertEqual(r['BOS']['status'],'expected')
        p[0]['AwayLineup'][0]['PlayerID']=101;r,_=providers.sports_evidence(self.wrap(p,'SportsDataIO'),self.f.game,self.f.rosters,self.now);self.assertNotIn('BOS',r)
    def test_conflicting_providers_withhold_confirmation(self):
        p=self.sports_payload();p[0]['AwayLineup'][0].update(PlayerID=105,LastName='Player 5')
        r=providers.resolve(self.f.game,self.f.rosters,[],[self.wrap(),self.wrap(p,'SportsDataIO')],[],self.now.isoformat(),self.now);self.assertFalse(r['provider_verified']);self.assertEqual(r['cohort'],'incomplete')
    def test_missing_injuries_and_stale_manual(self):
        r=providers.resolve(self.f.game,self.f.rosters,[],[self.wrap()],[],None,self.now);self.assertFalse(r['injury_checked']);self.assertFalse(r['actionable'])
        r=providers.resolve(self.f.game,self.f.rosters,[],[],[],None,self.now,{'BOS':{'confirmed_at':'2020-01-01T00:00:00Z','game_id':'espn_1','start_time':self.f.game['start_time'],'player_ids':['10','11','12','13','14']}});self.assertNotEqual(r['statuses']['BOS'],'manual')

class FakeProviders:
    def __init__(self,test):self.t=test;self.fail=False;self.schedule_calls=0
    def schedule(self,day,fresh=False):
        self.schedule_calls+=1
        if self.fail:raise providers.ProviderError('fixture outage')
        return [copy.deepcopy(self.t.f.game)],{'retrieved_at':self.t.now.isoformat()}
    def roster(self,team):return copy.deepcopy(self.t.f.rosters[team]),{'retrieved_at':self.t.now.isoformat(),'sha256':'fixture'}
    def injuries(self):raise providers.ProviderError('No injury credential; unchecked')
    def lineups(self,day):
        p=copy.deepcopy(self.t.f.payload)
        for side in ('homeTeam','awayTeam'):
            for row in p['games'][0][side]['players']:row['timestamp']=self.t.now.isoformat()
        return [{'provider':'NBA','payload':p,'retrieved_at':self.t.now.isoformat(),'sha256':data.digest(p)}],[]

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.f=test_dashboard.NBAConfirmedLineupTests();self.f.setUp();self.now=providers.stamp(self.f.game['start_time'])-timedelta(minutes=60);self.s=storage.Store(Path(self.tmp.name)/'ops.db',clock=lambda:self.now);self.p=FakeProviders(self);protocol.register(self.s);self.h,self.seq,_=sample_history()
    def tearDown(self):self.tmp.cleanup()
    def tick(self,observe=False):
        with patch.object(integrity,'model_data',return_value=(self.h,self.seq,{})):return runner.tick(self.s,self.p,self.f.game['_date'],mode='fixture',observe=observe)
    def test_checkpoint_boundaries_and_no_posttip(self):
        spec=protocol.specification();tip=providers.stamp(self.f.game['start_time'])
        for minute in [60,30,10,2]:self.assertEqual(runner.checkpoint(self.f.game,tip-timedelta(minutes=minute),spec),minute)
        self.assertIsNone(runner.checkpoint(self.f.game,tip-timedelta(seconds=20),spec));self.assertIsNone(runner.checkpoint(self.f.game,tip,spec))
    def test_duplicate_tick_and_multiple_checkpoint_forecasts(self):
        a=self.tick();self.assertEqual(a['predicted'],1);original=self.s.rows('prediction')[0];self.assertEqual(self.tick()['predicted'],0)
        self.now+=timedelta(minutes=30);self.assertEqual(self.tick()['predicted'],1);self.assertEqual(self.s.rows('prediction')[0],original)
        for r in self.s.rows('prediction'):
            for p in r['payload']['forecasts'].values():self.assertAlmostEqual(sum(p.values()),1)
    def test_concurrent_runner_and_expired_lease_recovery(self):
        self.s.acquire('phase5-collector',5);self.assertEqual(self.tick()['status'],'already running');self.now+=timedelta(seconds=6);self.assertEqual(self.tick()['predicted'],1)
    def test_protocol_drift_stops_before_provider_call(self):
        with patch.object(protocol,'specification',return_value={'changed':True}):
            with self.assertRaises(ValueError):self.tick()
        self.assertEqual(self.p.schedule_calls,0)
    def test_observe_archives_evidence_without_backfilled_forecast(self):
        self.f.game['start_time']=(providers.stamp(self.f.game['start_time'])+timedelta(minutes=20)).isoformat();r=self.tick(True);self.assertEqual(r['captured'],1);self.assertEqual(r['predicted'],0);self.assertFalse(self.s.rows('prediction'))
    def test_missed_windows_not_filled(self):
        self.now+=timedelta(minutes=15);r=self.tick();self.assertEqual(r['predicted'],0);self.assertEqual(len(self.s.rows('missed')),1)
    def test_outage_diagnostic_and_retry_without_overwrite(self):
        self.p.fail=True;r=self.tick();self.assertEqual(r['status'],'failed');self.p.fail=False;self.assertEqual(self.tick()['predicted'],1)
    def test_late_change_and_snapshot_history(self):
        self.tick();first=self.s.rows('snapshot')[0];self.now+=timedelta(minutes=30);self.f.payload['games'][0]['awayTeam']['players'][0].update(playerName='BOS Player 5',personId=105);self.tick();last=self.s.rows('snapshot')[-1];self.assertIn('BOS',last['payload']['changes']);self.assertEqual(self.s.rows('snapshot')[0],first)
    def test_schedule_change_before_save_blocks_forecast(self):
        old=self.p.schedule
        def changed(day,fresh=False):
            games,w=old(day,fresh)
            if self.p.schedule_calls>1:games[0]['start_time']='2027-01-03T00:00:00Z'
            return games,w
        self.p.schedule=changed;r=self.tick();self.assertEqual(r['predicted'],0);self.assertEqual(r['status'],'partial');self.assertTrue(self.s.rows('snapshot'))
    def test_past_game_and_insufficient_primary_history_not_eligible(self):
        self.now+=timedelta(minutes=50);self.tick();selected,excluded=protocol.primary_predictions(self.s);self.assertFalse(selected);self.assertTrue(excluded)
        self.now+=timedelta(hours=1);self.assertEqual(self.tick()['predicted'],0)
    def test_future_history_does_not_change_probabilities(self):
        self.tick();p=self.s.rows('prediction')[0]['payload'];base=p['forecasts'];self.now+=timedelta(minutes=30)
        future=copy.deepcopy(self.h)
        for r in future:r['date']='2027-01-03';r['game_id']='future_'+r['game_id']
        self.h+=future;self.tick();self.assertEqual(base,self.s.rows('prediction')[-1]['payload']['forecasts'])
    def test_primary_chooses_latest_eligible_without_results(self):
        self.now+=timedelta(minutes=50);self.tick();a=self.s.rows('prediction')[0]
        # Fixture-only synthetic registration-compatible forecast to test selection, not a live count.
        p=copy.deepcopy(a['payload']);p['training_games']=100;self.s.append('prediction','fixture_eligible',p)
        self.now+=timedelta(minutes=8);self.tick();b=self.s.rows('prediction')[-1];p=copy.deepcopy(b['payload']);p['training_games']=100;self.s.append('prediction','fixture_later',p)
        selected,_=protocol.primary_predictions(self.s);self.assertEqual(selected['espn_1']['key'],'fixture_later');self.assertEqual(protocol.evaluate(self.s)['graded_games'],0)

class GradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();f=test_research.OpeningResultEnrichmentTests();f.setUp();self.raw=copy.deepcopy(f.payload);self.raw['header']['season']={'year':2026,'type':2};self.game=outcome_data.game_from_payload(self.raw);self.game['gameStatus']=1;self.now=providers.stamp(self.game['start_time'])-timedelta(minutes=10)
        self.s=storage.Store(Path(self.tmp.name)/'ops.db',clock=lambda:self.now);protocol.register(self.s)
        result=outcome_data.extract(self.game,self.raw);lineups={t:[{'player_id':r['player_id'],'player':r['player']} for r in result['rows'] if r['team']==t] for t in {r['team'] for r in result['rows']}}
        self.p=Mock();self.p.schedule.side_effect=lambda day,fresh=False:([copy.deepcopy(self.game)],{'retrieved_at':self.now.isoformat()});self.p.result.side_effect=lambda gid:{'payload':self.raw,'sha256':data.digest(self.raw),'retrieved_at':self.now.isoformat()}
        payload={'game':self.game,'lineups':lineups,'rosters':lineups,'readiness':{'messages':[],'provider_verified':False,'actionable':False},'statuses':{t:'projected' for t in lineups},'cohort':'projected','valid_identities':True,'retrieved_at':self.now.isoformat()}
        self.snap=self.s.append('snapshot','fixture',payload);fence=self.s.acquire('fixture',1000);self.pred=runner.predict(self.s,self.p,self.snap,[],{}, {},'fixture_pred',10,fence)
        # A selection fixture with declared earlier training count; never exported as live evidence.
        x=copy.deepcopy(self.pred['payload']);x['training_games']=100;self.primary=self.s.append('prediction','fixture_primary',x)
    def tearDown(self):self.tmp.cleanup()
    def test_future_grade_makes_no_provider_request(self):
        self.assertEqual(runner.grade_tick(self.s,self.p)['graded'],0);self.p.result.assert_not_called()
    def test_completed_grade_preserves_original_and_one_primary_per_game(self):
        original=self.s.rows('prediction');self.now+=timedelta(hours=4);r=runner.grade_tick(self.s,self.p);self.assertEqual(r['graded'],2);self.assertEqual(self.s.rows('prediction'),original);report=protocol.evaluate(self.s);self.assertEqual(report['graded_games'],1);self.assertFalse(report['milestone_reached']);self.assertEqual(runner.grade_tick(self.s,self.p)['graded'],0)
        self.assertEqual(len(self.s.rows('history')),1)
    def test_bench_first_score_kept_and_literal_baseline_infinite_loss(self):
        first=next(x for x in self.raw['plays'] if x.get('scoringPlay'));team=str(first['team']['id']);box=next(x for x in self.raw['boxscore']['players'] if str(x['team']['id'])==team);bench=next(a for st in box['statistics'] for a in st['athletes'] if a.get('starter') is False);first['participants'][0]['athlete']['id']=bench['athlete']['id'];self.now+=timedelta(hours=4);runner.grade_tick(self.s,self.p);r=protocol.evaluate(self.s);self.assertEqual(r['graded_games'],1)
        legacy=next(x for x in r['summary'] if x['Model']=='Literal V2.44 Baseline' and x['Cohort']=='All');self.assertEqual(legacy['Log loss'],'Infinity');self.assertEqual(self.s.rows('result')[0]['payload']['result']['starter_status'],'bench')
    def test_ambiguous_result_is_excluded_and_preserved(self):
        next(x for x in self.raw['plays'] if x.get('scoringPlay'))['participants']=[];self.now+=timedelta(hours=4);runner.grade_tick(self.s,self.p);self.assertEqual(protocol.evaluate(self.s)['graded_games'],0);self.assertTrue(self.s.rows('result'));self.assertTrue(protocol.evaluate(self.s)['excluded'])
    def test_rescheduled_game_excluded_original_unchanged(self):
        self.raw['header']['competitions'][0]['date']=(providers.stamp(self.game['start_time'])+timedelta(minutes=20)).isoformat();self.now+=timedelta(hours=4);runner.grade_tick(self.s,self.p);self.assertEqual(protocol.evaluate(self.s)['graded_games'],0);self.assertEqual(self.s.get('prediction','fixture_pred'),self.pred)
    def test_nonregular_result_is_not_accepted(self):
        self.raw['header']['season']['type']=3;self.now+=timedelta(hours=4);r=runner.grade_tick(self.s,self.p);self.assertTrue(r['errors']);self.assertEqual(self.s.rows('result'),[])
    def test_result_provider_failure_does_not_erase_forecast(self):
        self.now+=timedelta(hours=4);self.p.result.side_effect=providers.ProviderError('ESPN unavailable');r=runner.grade_tick(self.s,self.p);self.assertTrue(r['errors']);self.assertEqual(self.s.get('prediction','fixture_pred'),self.pred)

    def test_known_nonselected_first_shooter_is_a_miss_not_excluded(self):
        shot=next(x for x in self.raw['plays'] if x.get('shootingPlay') is True and 'free throw' not in x.get('text','').lower());team=str(shot['team']['id']);box=next(x for x in self.raw['boxscore']['players'] if str(x['team']['id'])==team);bench=next(a for st in box['statistics'] for a in st['athletes'] if a.get('starter') is False);shot['participants'][0]['athlete']['id']=bench['athlete']['id'];self.now+=timedelta(hours=4);runner.grade_tick(self.s,self.p);r=protocol.evaluate(self.s);self.assertEqual(r['first_shot_games'],1);self.assertEqual(r['first_shot_accuracy']['proxy'],0)

class RecoveryDetailsTests(unittest.TestCase):
    def test_backup_preserves_cooldowns_and_recovers_running_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            now=datetime(2027,1,2,tzinfo=timezone.utc);s=storage.Store(Path(folder)/'a.db',clock=lambda:now);s.append('protocol','fixture',{});s.set_state('cooldown:NBA',now.timestamp()+600);f=s.acquire('run');s.begin_job('task',f);path=Path(folder)/'backup.json';s.export(path);r=storage.Store(Path(folder)/'b.db',clock=lambda:now);r.restore(path);self.assertEqual(r.state('cooldown:NBA'),now.timestamp()+600);self.assertFalse(r.job_due('task'));self.assertIsNotNone(r.acquire('run'))
    def test_real_credential_free_injury_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            p=providers.Providers(storage.Store(Path(folder)/'a.db'),injury_key='',sports_key='')
            with self.assertRaises(providers.ProviderError) as e:p.injuries()
            self.assertIn('unchecked',str(e.exception))
    def test_optional_paid_lineup_provider_disabled_without_live_license(self):
        with tempfile.TemporaryDirectory() as folder:
            t=Mock();t.fetch.return_value={'provider':'NBA'}
            with patch.dict(os.environ,{},clear=True):p=providers.Providers(storage.Store(Path(folder)/'a.db'),transport=t,sports_key='fixture-key',licensed=False);p.lineups('2027-01-02')
            self.assertEqual(t.fetch.call_count,1)
    def test_unknown_and_duplicate_cross_team_provider_id_rejected(self):
        f=EvidenceTests();f.setUp();f.p['games'][0]['homeTeam']['players'][0]['personId']=100;r=f.resolve();self.assertFalse(r['provider_verified']);self.assertFalse(r['valid_identities'])
    def test_storage_outage_does_not_trigger_provider_calls(self):
        s=Mock();s.get.side_effect=storage.StorageError('database offline');p=Mock()
        with self.assertRaises(storage.StorageError):runner.tick(s,p)
        p.schedule.assert_not_called()

    def test_concurrent_real_clock_receipts_are_ordered(self):
        with tempfile.TemporaryDirectory() as folder:
            s=storage.Store(Path(folder)/'db')
            with ThreadPoolExecutor(4) as pool:list(pool.map(lambda i:s.append('test',str(i),{}),range(40)))
            self.assertEqual(len(s.rows()),40)
    def test_storage_commit_time_guard_prevents_late_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            now=datetime(2027,1,2,tzinfo=timezone.utc);s=storage.Store(Path(folder)/'db',clock=lambda:now)
            with self.assertRaises(ValueError):s.append('prediction','late',{'game':{'start_time':now.isoformat()}})
            with self.assertRaises(ValueError):s.append('prediction','deadline',{},deadline=now-timedelta(seconds=1))
            self.assertEqual(s.rows(),[])

    def test_existing_store_open_does_not_run_schema_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db';s=storage.Store(path);s.append('test','one',{})
            with patch.object(storage.Store,'initialize',side_effect=AssertionError('unexpected schema write')):
                reopened=storage.Store(path);self.assertEqual(len(reopened.rows()),1)
    def test_corrupted_database_is_rejected_without_resetting_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db';s=storage.Store(path);s.append('test','one',{});raw=path.read_bytes();path.write_bytes(b'CORRUPT HEADER!!'+raw[16:]);before=path.read_bytes()
            with self.assertRaises(storage.StorageError):storage.Store(path).rows()
            self.assertEqual(path.read_bytes(),before)
