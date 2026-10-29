import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
import requests
import first_basket_engine as eng,phase4_data as data,phase4_forward as fwd,phase4_research as research
import phase2,phase3,simulation,outcome_data,opening_data
from test_research import OpeningResultEnrichmentTests
from test_phase2 import sample_history
import test_dashboard

class CollectionTests(unittest.TestCase):
    def setUp(self):
        f=OpeningResultEnrichmentTests();f.setUp();self.p=copy.deepcopy(f.payload);self.p['header']['season']={'year':2026,'type':2};self.g=outcome_data.game_from_payload(self.p);self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_checkpoint_duplicate_and_original_history_is_untouched(self):
        original=self.root/'legacy.csv';original.write_text('original')
        self.assertTrue(data.ingest(self.g,{'payload':self.p},self.root));self.assertFalse(data.ingest(self.g,{'payload':self.p},self.root))
        self.assertEqual(original.read_text(),'original');self.assertEqual(data.coverage(self.root)['games'],1)
    def test_conflicting_source_preserves_checkpoint(self):
        data.ingest(self.g,{'payload':self.p},self.root);changed=copy.deepcopy(self.p);changed['extra']='changed'
        with self.assertRaises(ValueError):data.ingest(self.g,{'payload':changed},self.root)
        self.assertEqual(data.coverage(self.root)['games'],1)
    def test_nonregular_and_identity_mismatch_rejected(self):
        bad=copy.deepcopy(self.p);bad['header']['season']['type']=3
        with self.assertRaises(ValueError):data.ingest(self.g,{'payload':bad},self.root)
        with self.assertRaises(ValueError):data.ingest({**self.g,'gameId':'espn_1'},{'payload':self.p},self.root)
    def test_missing_unrelated_bench_id_does_not_remove_opening_sequence(self):
        self.p['boxscore']['players'][0]['statistics'][0]['athletes'].append({'athlete':{},'starter':False})
        data.ingest(self.g,{'payload':self.p},self.root)
        self.assertEqual(data.coverage(self.root)['usable_opening_sequences'],1)
    def test_ambiguous_first_score_is_stored_with_reason(self):
        first=next(p for p in self.p['plays'] if p.get('scoringPlay'));first['participants']=[]
        data.ingest(self.g,{'payload':self.p},self.root)
        report=data.coverage(self.root);self.assertEqual(report['outcomes']['ambiguous'],1);self.assertTrue(report['warnings'])
    def test_invalid_team_split_preserves_score_but_excludes_model(self):
        record={'status':'resolved','scorer_id':'1','starter_status':'starter','warnings':[],'rows':[{'team':'BOS'}]*6+[{'team':'NYK'}]*4}
        with patch.object(outcome_data,'extract',return_value=record):
            data.ingest(self.g,{'payload':self.p},self.root)
        h,sequences,records=data.dataset(self.root)
        self.assertFalse(h);self.assertFalse(sequences)
        self.assertEqual(next(iter(records.values()))['status'],'resolved')
        self.assertIn('exactly five',next(iter(records.values()))['warnings'][0])

    def test_bad_checksum_rejected(self):
        with self.assertRaises(ValueError):data.ingest(self.g,{'payload':self.p,'sha256':'bad'},self.root)
    def test_cache_preserves_source_timestamp_and_avoids_repeat_request(self):
        response=Mock(status_code=200,headers={'Date':'Wed, 28 Oct 2026 19:00:00 GMT'});response.json.return_value={'ok':1};get=Mock(return_value=response)
        c=data.Client(self.root,get=get,sleep=lambda n:None);a=c.fetch('https://example.test',{},'one');b=c.fetch('https://example.test',{},'one')
        self.assertEqual(a,b);get.assert_called_once();self.assertIsNotNone(a['retrieved_at']);self.assertEqual(a['provider_date'],response.headers['Date'])
    def test_cache_tampering_rejected(self):
        c=data.Client(self.root,get=Mock(),sleep=lambda n:None);(self.root/'raw'/'bad.json').write_text('{"payload":{},"sha256":"bad"}')
        with self.assertRaises(ValueError):c.fetch('x',{},'bad')
        c.get.assert_not_called()
    def test_timeout_retries_are_bounded(self):
        get=Mock(side_effect=requests.Timeout());c=data.Client(self.root,get=get,sleep=lambda n:None)
        with self.assertRaises(RuntimeError):c.fetch('x',{},'a')
        self.assertEqual(get.call_count,2)
    def test_rate_limit_survives_new_client(self):
        response=Mock(status_code=429,headers={'Retry-After':'600'});get=Mock(return_value=response)
        with self.assertRaises(data.RateLimited):data.Client(self.root,get=get,sleep=lambda n:None).fetch('x',{},'a')
        with self.assertRaises(data.RateLimited):data.Client(self.root,get=get,sleep=lambda n:None).fetch('x',{},'b')
        self.assertEqual(get.call_count,1)
    def test_failed_game_records_survive_restart(self):
        data.failure(self.root,'espn_1','summary','offline');self.assertEqual(data.coverage(self.root)['failures'][0]['reason'],'offline')
    def test_collection_range_and_concurrency_guards(self):
        with self.assertRaises(ValueError):data.collect('2025-01-01','2025-03-01',self.root)
        with self.assertRaises(ValueError):data.collect('2025-01-01','2025-01-02',self.root,workers=3)
    def test_background_job_is_manual_and_reports_completion(self):
        data.start_job('fixture',lambda:{'saved':1},self.root);data._jobs[str(self.root.resolve())].join(3)
        self.assertEqual(data.job_status(self.root)['state'],'completed');self.assertIn('Manual',data.job_status(self.root)['monitoring'])

class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'forward.sqlite3'
        self.f=test_dashboard.NBAConfirmedLineupTests();self.f.setUp();self.now=self.f.now
        self.j=fwd.Journal(self.path,clock=lambda:self.now);self.lineups={t:ps[:5] for t,ps in self.f.rosters.items()};self.provider=self.f.parse()['entries']['espn_1']
        self.h,self.seq,_=sample_history()
    def tearDown(self):self.temp.cleanup()
    def snap(self,provider=None):return fwd.snapshot(self.j,self.f.game,self.lineups,self.f.rosters,self.provider if provider is None else provider,[],self.now.isoformat())
    def pred(self,snap=None):return fwd.save_prediction(self.j,snap or self.snap(),self.h,self.seq,{},simulation.SimulationConfig(trials=100),refresh=False)
    def test_snapshots_append_and_original_evidence_stays(self):
        first=self.snap();second=self.snap({});rows=self.j.rows('snapshot')
        self.assertEqual(len(rows),2);self.assertEqual(rows[0],first);self.assertTrue(second['payload']['prior_official_evidence_retained']);self.assertFalse(second['payload']['readiness']['provider_verified'])
    def test_projected_and_unknown_states_not_confirmed(self):
        self.lineups['BOS']=[];s=self.snap({});self.assertEqual(s['payload']['statuses']['BOS'],'unknown');self.assertFalse(s['payload']['readiness']['provider_verified'])
    def test_sql_updates_and_deletes_blocked(self):
        self.snap()
        for statement in ('UPDATE entries SET key="x"','DELETE FROM entries'):
            with self.j.connect() as c:
                with self.assertRaises(sqlite3.IntegrityError):c.execute(statement)
    def test_integrity_detection_even_after_trigger_removed(self):
        self.snap()
        with self.j.connect() as c:c.execute('DROP TRIGGER no_update');c.execute('UPDATE entries SET payload=?',('{"changed":true}',))
        with self.assertRaises(ValueError):self.j.rows()
    def test_no_retrospective_snapshot_or_prediction(self):
        self.now+=timedelta(days=1)
        with self.assertRaises(ValueError):self.snap()
    def test_expired_snapshot_cannot_generate_prediction(self):
        s=self.snap();self.now+=timedelta(minutes=6)
        with self.assertRaises(ValueError):self.pred(s)
    def test_newer_evidence_invalidates_old_snapshot(self):
        s=self.snap();self.snap({})
        with self.assertRaises(ValueError):self.pred(s)
    def test_saved_forecast_is_unique_complete_and_versioned(self):
        self.assertTrue(self.pred());self.assertFalse(self.pred());p=self.j.rows('prediction')[0]['payload']
        self.assertEqual(p['model_version'],'3.0.6');self.assertEqual(p['seed'],3000)
        for probs in p['forecasts'].values():self.assertAlmostEqual(sum(probs.values()),1);self.assertIn('OTHER',probs)
        self.assertAlmostEqual(sum(p['first_shot_proxy'].values()),1)
    def test_current_schedule_reschedule_blocks_save(self):
        s=self.snap();changed={**self.f.game,'start_time':'2027-01-03T01:00:00Z'}
        with patch.object(fwd.core,'fresh_schedule',return_value=[changed]):
            with self.assertRaises(ValueError):fwd.save_prediction(self.j,s,self.h,self.seq,{},simulation.SimulationConfig(trials=100))
    def test_roster_mismatch_or_duplicates_block_save(self):
        self.lineups['BOS'][1]=self.lineups['BOS'][0]
        with self.assertRaises(ValueError):self.pred()
    def test_clock_reversal_prevents_append(self):
        self.snap();self.now-=timedelta(minutes=1)
        with self.assertRaises(ValueError):self.snap()
    def test_provider_failure_is_archived_without_key_material(self):
        with patch.object(fwd.core,'fresh_schedule',side_effect=RuntimeError('secret-key-example')):
            result=fwd.collect_snapshots('2027-01-02',self.h,self.j,'private-key')
        self.assertEqual(result['snapshots'],0);raw=json.dumps(self.j.rows());self.assertNotIn('private-key',raw);self.assertNotIn('secret-key-example',raw)
    def test_empty_forward_report_does_not_claim_results(self):
        r=fwd.evaluation(self.j);self.assertEqual(r['graded_games'],0);self.assertIsNone(r['first_shot_accuracy'])

class AblationTests(unittest.TestCase):
    def test_kernel_refactor_reproduces_existing_simulation(self):
        h,s,l=sample_history();cfg=simulation.SimulationConfig(trials=100)
        a=phase2.simulate(h,l,'2026-09-01',s,cfg);inputs=phase2.build_inputs(h,l,'2026-09-01',s,cfg)
        self.assertEqual(a,phase2._simulate_inputs(inputs,l,'2026-09-01',cfg))
    def test_variant_conserves_event_mass_and_neutralizes_only_requested_factor(self):
        h,s,l=sample_history();cfg=simulation.SimulationConfig(trials=100);a=phase2.build_inputs(h,l,'2026-09-01',s,cfg)
        old=copy.deepcopy(a);research.transform('no_turnovers',h,s,'2026-09-01')(a)
        for t,d in a['teams'].items():self.assertEqual(d['event_probs']['turnover'],0);self.assertAlmostEqual(sum(d['event_probs'].values()),1);self.assertEqual(d['make_by_type'],old['teams'][t]['make_by_type'])
    def test_opponent_removal_uses_only_earlier_sequences(self):
        h,s,l=sample_history();cfg=simulation.SimulationConfig(trials=100);a=phase2.build_inputs(h,l,'2026-09-01',s,cfg);b=copy.deepcopy(a)
        future=copy.deepcopy(s);future['future']={**s['0'],'date':'2026-09-02'}
        research.own_conversion(h,s,'2026-09-01')(a);research.own_conversion(h,future,'2026-09-01')(b);self.assertEqual(a,b)

class GradingTests(unittest.TestCase):
    def setUp(self):
        f=OpeningResultEnrichmentTests();f.setUp();self.payload=copy.deepcopy(f.payload);self.game=outcome_data.game_from_payload(self.payload);self.game['gameStatus']=1
        result=outcome_data.extract({**self.game,'gameStatus':3},self.payload)
        self.lineups={t:[{'player_id':r['player_id'],'player':r['player']} for r in result['rows'] if r['team']==t] for t in {r['team'] for r in result['rows']}}
        self.now=datetime.fromisoformat(self.game['start_time'].replace('Z','+00:00'))-timedelta(minutes=10);self.temp=tempfile.TemporaryDirectory();self.j=fwd.Journal(Path(self.temp.name)/'journal.sqlite3',clock=lambda:self.now)
        snap=fwd.snapshot(self.j,self.game,self.lineups,self.lineups,{},[],self.now.isoformat())
        fwd.save_prediction(self.j,snap,[],{}, {},simulation.SimulationConfig(trials=100),refresh=False);self.pred=self.j.rows('prediction')[0]
    def tearDown(self):self.temp.cleanup()
    def test_result_append_never_changes_original_forecast(self):
        self.now+=timedelta(hours=4);fwd.grade(self.j,self.pred,self.payload)
        self.assertEqual(self.j.rows('prediction')[0],self.pred);self.assertEqual(fwd.evaluation(self.j)['graded_games'],1)
        fwd.grade(self.j,self.pred,self.payload);self.assertEqual(len(self.j.rows('result')),1)
    def test_outside_selected_ten_is_scored_as_other(self):
        first=next(p for p in self.payload['plays'] if p.get('scoringPlay'));team=str(first['team']['id'])
        box=next(t for t in self.payload['boxscore']['players'] if str(t['team']['id'])==team)
        bench=next(r for stats in box['statistics'] for r in stats['athletes'] if r.get('starter') is False)
        first['participants'][0]['athlete']['id']=bench['athlete']['id']
        self.now+=timedelta(hours=4);graded=fwd.grade(self.j,self.pred,self.payload)
        self.assertEqual(graded['result']['starter_status'],'bench');report=fwd.evaluation(self.j)
        row=next(r for r in report['summary'] if r['Cohort']=='All' and r['Model']=='Baseline')
        self.assertAlmostEqual(row['Log loss'],-__import__('math').log(.01))
    def test_unresolved_results_are_not_silently_graded(self):
        next(p for p in self.payload['plays'] if p.get('scoringPlay'))['participants']=[]
        self.now+=timedelta(hours=4);fwd.grade(self.j,self.pred,self.payload)
        self.assertEqual(fwd.evaluation(self.j)['graded_games'],0);self.assertTrue(fwd.evaluation(self.j)['excluded'])
    def test_future_grading_and_forged_prediction_rejected(self):
        with self.assertRaises(ValueError):fwd.grade(self.j,self.pred,self.payload)
        self.now+=timedelta(hours=4);fake=copy.deepcopy(self.pred);fake['payload']['model_version']='fake'
        with self.assertRaises(ValueError):fwd.grade(self.j,fake,self.payload)
    def test_rescheduled_result_excluded_without_rewriting_prediction(self):
        start=datetime.fromisoformat(self.game['start_time'].replace('Z','+00:00'))+timedelta(minutes=30)
        self.payload['header']['competitions'][0]['date']=start.isoformat()
        self.now+=timedelta(hours=4);result=fwd.grade(self.j,self.pred,self.payload)
        self.assertFalse(result['eligible_for_metrics']);self.assertEqual(self.j.rows('prediction')[0],self.pred)
