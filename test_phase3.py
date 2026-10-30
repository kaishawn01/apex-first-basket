import copy,json,math,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
import first_basket_engine as eng
import outcome_data as od,phase3,phase2,simulation
import test_dashboard
from test_phase2 import sample_history
from test_research import OpeningResultEnrichmentTests

class CompleteOutcomeTests(unittest.TestCase):
    def setUp(self):
        f=OpeningResultEnrichmentTests();f.setUp();self.payload=copy.deepcopy(f.payload);self.game=od.game_from_payload(self.payload)
    def first_score(self):return next(p for p in sorted(self.payload['plays'],key=lambda p:int(p['sequenceNumber'])) if p.get('period',{}).get('number')==1 and p.get('scoringPlay'))
    def bench_scorer(self):
        pid=self.first_score()['participants'][0]['athlete']['id']
        for side in self.payload['boxscore']['players']:
            for stats in side['statistics']:
                rows=stats.get('athletes',[])
                if any(r['athlete'].get('id')==pid for r in rows):
                    replacement=next(r for r in rows if r['athlete'].get('id')!=pid and r.get('starter') is False)
                    replacement['starter']=True
                    next(r for r in rows if r['athlete'].get('id')==pid)['starter']=False
        return str(pid)
    def test_actual_nonstarter_is_preserved(self):
        pid=self.bench_scorer();r=od.extract(self.game,self.payload)
        self.assertEqual(r['status'],'resolved');self.assertEqual(r['scorer_id'],pid);self.assertEqual(r['starter_status'],'bench')
        self.assertEqual(len(r['rows']),10);self.assertEqual(sum(x['first_scorer'] for x in r['rows']),0)
        p,b=eng.espn_game_payloads(self.payload)
        with self.assertRaisesRegex(ValueError,'not one'):eng.extract_game(self.game,p,b)
    def test_free_throw_nonstarter_preserved(self):
        pid=self.bench_scorer();s=self.first_score();s.update(scoreValue=1,text='Player makes free throw 1 of 2',shootingPlay=False)
        for key in ('homeScore','awayScore'):
            if s.get(key,0)>0:s[key]=1
        r=od.extract(self.game,self.payload);self.assertEqual(r['scorer_id'],pid);self.assertEqual(r['score_type'],'FT')
    def test_unknown_starter_status_not_invented(self):
        pid=self.first_score()['participants'][0]['athlete']['id']
        for side in self.payload['boxscore']['players']:
            for stats in side['statistics']:
                for row in stats.get('athletes',[]):
                    if row['athlete'].get('id')==pid:row.pop('starter',None)
        r=od.extract(self.game,self.payload);self.assertEqual(r['starter_status'],'unknown');self.assertEqual(r['status'],'resolved');self.assertFalse(r['rows'])
    def test_missing_unrelated_identity_does_not_discard_outcome(self):
        self.payload['boxscore']['players'][0]['statistics'][0]['athletes'].append({'athlete':{},'starter':False})
        r=od.extract(self.game,self.payload);self.assertEqual(r['status'],'resolved');self.assertTrue(r['warnings'])
    def test_missing_scoring_identity_kept_as_ambiguous(self):
        self.first_score()['participants']=[];r=od.extract(self.game,self.payload)
        self.assertEqual(r['status'],'ambiguous');self.assertIsNone(r['scorer_id']);self.assertTrue(r['warnings'])
    def test_conflicting_sequence_not_silently_deduplicated(self):
        p=copy.deepcopy(self.first_score());p['text']='different';self.payload['plays'].append(p)
        self.assertEqual(od.extract(self.game,self.payload)['status'],'ambiguous')
    def test_clock_reversal_detected(self):
        self.first_score()['clock']['displayValue']='12:01'
        self.assertEqual(od.extract(self.game,self.payload)['status'],'ambiguous')
    def test_wrong_game_and_date_rejected(self):
        with self.assertRaises(ValueError):od.extract({**self.game,'gameId':'espn_1'},self.payload)
        with self.assertRaises(ValueError):od.extract({**self.game,'_date':'2020-01-01'},self.payload)
    def test_separate_ledger_roundtrip(self):
        r=od.extract(self.game,self.payload)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'outcomes.json';od.write({r['game_id']:r},p);self.assertEqual(od.load(p)[r['game_id']]['scorer_id'],r['scorer_id'])
    def test_provider_failure_is_reported_not_confirmed(self):
        import dashboard_core as core
        with tempfile.TemporaryDirectory() as d,patch.object(core,'request',side_effect=RuntimeError('Unavailable')):
            with self.assertRaises(RuntimeError):od.collect_day('2025-10-25',Path(d)/'outcomes.json')
            self.assertFalse((Path(d)/'outcomes.json').exists())

class Phase3ModelTests(unittest.TestCase):
    def setUp(self):self.h,self.s,self.lineups=sample_history();self.cfg=simulation.SimulationConfig(trials=100)
    def test_probability_mass_with_other(self):
        r=phase3.forecast(self.h,self.lineups,'2026-09-01',self.s,{},self.cfg)
        for p in r['complete'].values():self.assertAlmostEqual(sum(p.values()),1);self.assertGreater(p[phase3.OTHER],0)
        self.assertEqual(r['other_mass'],.01)
    def test_seed_reproducibility(self):
        a=phase3.forecast(self.h,self.lineups,'2026-09-01',self.s,{},self.cfg)
        b=phase3.forecast(self.h,self.lineups,'2026-09-01',self.s,{},self.cfg)
        self.assertEqual(a,b)
    def test_other_excludes_same_day_and_future(self):
        records={str(i):{'date':d,'status':'resolved','scorer_id':'999','rows':self.h[:10]} for i,d in enumerate(['2026-08-01','2026-09-01','2026-09-02'])}
        p,e=phase3.other_prior(records,'2026-09-01',self.lineups);self.assertEqual(e['games'],1);self.assertEqual(e['other_outcomes'],1);self.assertGreater(p,.01)
    def test_all_selectors_normalized(self):
        inputs=phase2.build_inputs(self.h,self.lineups,'2026-09-01',self.s,self.cfg)
        for method in phase3.SELECTORS:
            for half in (30,90,180):
                p,_=phase3.selector(self.h,self.lineups,'2026-09-01',inputs,method,half);self.assertAlmostEqual(sum(p.values()),1);self.assertEqual(len(p),10)
    def test_bad_selection_rejected(self):
        with self.assertRaises(ValueError):phase3.selector([],self.lineups,'2026-09-01',{},'bogus')
    def test_invalid_probability_rejected(self):
        for p,m in [({'x':.5},.1),({'x':1},-1),({'x':float('nan')},.1)]:
            with self.assertRaises(ValueError):phase3.with_other(p,m)
    def test_legacy_zero_for_nonstarter_is_not_reassigned(self):
        r={'Date':'2026-01-01','Game':'1','Winner':'OTHER','Legacy Baseline':{'10':1.,'OTHER':0.}}
        result=phase2.metrics([r],'Legacy Baseline');self.assertTrue(math.isinf(result['metrics']['Log loss']))
    def test_sparse_selection_keeps_simple(self):
        result=phase3.lock_selection([]);self.assertEqual(result['selector'],'simple');self.assertFalse(result['selector_promotion']);self.assertEqual(result['weight'],0)
    def test_selector_ignores_future_history(self):
        inputs=phase2.build_inputs(self.h,self.lineups,'2026-09-01',self.s,self.cfg)
        future=[{**r,'date':'2026-09-02'} for r in self.h]
        self.assertEqual(phase3.selector(self.h,self.lineups,'2026-09-01',inputs),phase3.selector(self.h+future,self.lineups,'2026-09-01',inputs))

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f=test_dashboard.NBAConfirmedLineupTests();self.f.setUp();self.lineups={t:ps[:5] for t,ps in self.f.rosters.items()}
    def archive(self,path,provider=None,now=None):
        f=self.f;return od.archive_lineup(f.game,self.lineups,{},provider or {},f.rosters,[],f.now.isoformat(),path,now or f.now)
    def test_projected_is_not_provider_verified(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.archive(Path(d)/'archive.jsonl');self.assertFalse(r['provider_verified']);self.assertTrue(all(x=='Unconfirmed' for x in r['sources'].values()))
    def test_provider_source_timestamp_preserved_append_only(self):
        provider=self.f.parse()['entries']['espn_1']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'archive.jsonl';r=self.archive(p,provider);self.archive(p)
            self.assertTrue(r['provider_verified']);self.assertEqual(len(p.read_text().splitlines()),2)
            self.assertEqual(r['lineup_evidence']['BOS']['method'],'NBA feed confirmed')
    def test_after_tip_and_naive_time_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for now in (self.f.now+timedelta(days=1),self.f.now.replace(tzinfo=None)):
                with self.assertRaises(ValueError):self.archive(Path(d)/'a.jsonl',now=now)
    def test_roster_failure_prevents_archive(self):
        self.f.rosters={}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.archive(Path(d)/'a.jsonl')

class ChronologyTests(unittest.TestCase):
    def test_forecasts_use_only_earlier_dates_and_keep_actual_other_label(self):
        h,s,lineups=sample_history();records={}
        for i in range(12):
            rows=h[i*10:(i+1)*10];records[str(i)]={'date':rows[0]['date'],'status':'resolved','scorer_id':'999' if i==11 else next(r['player_id'] for r in rows if int(r['first_scorer'])),'starter_status':'bench' if i==11 else 'starter','rows':rows,'warnings':[]}
        original=phase3.forecast;seen=[]
        def spy(history,lineups,day,*args,**kwargs):
            self.assertTrue(all(r['date']<day for r in history));seen.append(day)
            return original(history,lineups,day,*args,**kwargs)
        with patch.object(phase3,'forecast',side_effect=spy):
            forecasts,_=phase3.forecasts(h,s,records,simulation.SimulationConfig(trials=100),start='2026-08-12',min_training=2)
        self.assertEqual(seen,['2026-08-12']);self.assertEqual(forecasts[0]['Winner'],'OTHER');self.assertEqual(forecasts[0]['Legacy Baseline']['OTHER'],0)
    def test_future_outcomes_do_not_change_validation_selection(self):
        h,sequences,_=sample_history();records={}
        for i in range(12):
            rows=h[i*10:(i+1)*10];records[str(i)]={'date':rows[0]['date'],'status':'resolved','scorer_id':next(r['player_id'] for r in rows if int(r['first_scorer'])),'starter_status':'starter','rows':rows,'warnings':[]}
        changed=copy.deepcopy(records)
        for r in changed.values():
            if r['date']>'2026-08-10':r['scorer_id']='999'
        cfg=simulation.SimulationConfig(trials=100)
        a,_=phase3.forecasts(h,sequences,records,cfg,start='2026-08-09',end='2026-08-10',min_training=2)
        b,_=phase3.forecasts(h,sequences,changed,cfg,start='2026-08-09',end='2026-08-10',min_training=2)
        self.assertEqual(phase3.lock_selection(a),phase3.lock_selection(b))
    def test_small_sample_cannot_promote_challenger(self):
        result=phase3.lock_selection([])
        self.assertEqual(result['weight'],0);self.assertEqual(result['temperature'],1);self.assertEqual(result['baseline_temperature'],1)

class CalibrationTests(unittest.TestCase):
    def test_eleven_outcome_temperature_conserves_mass_and_order(self):
        p={str(i):.099 for i in range(10)};p['OTHER']=.01
        q=phase3.temper(p,1.25);self.assertAlmostEqual(sum(q.values()),1);self.assertLess(q['OTHER'],q['0'])
        with self.assertRaises(ValueError):phase3.temper(p,float('nan'))
        with self.assertRaises(ValueError):phase3.temper({str(i):.1 for i in range(10)},1)
    def test_cached_ablation_is_identical(self):
        h,s,lineups=sample_history();inputs=phase2.build_inputs(h,lineups,'2026-09-01',s,simulation.SimulationConfig(trials=100));cache={}
        for method in phase3.SELECTORS:
            for half in (30,90,180):
                self.assertEqual(phase3.selector(h,lineups,'2026-09-01',inputs,method,half),phase3.selector(h,lineups,'2026-09-01',inputs,method,half,_cache=cache))
    def test_corrupt_ledger_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.json'
            for data in ([],{'schema':True,'games':{}},{'schema':1,'games':{'x':{}}}):
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):od.load(p)

class CompleteEvaluationTests(unittest.TestCase):
    def test_eleven_outcome_report_preserves_nonstarter_loss_and_cohorts(self):
        p={str(i):.099 for i in range(10)};p['OTHER']=.01
        row={'Date':'2026-01-01','Game':'one','Winner':'OTHER','First shooter':None,'Active':True,'Ablations':{},'Legacy Baseline':{**{str(i):.1 for i in range(10)},'OTHER':0},'Baseline + Other':p,'Simple proxy':p,'Monte Carlo':p,'Phase 2 hybrid':p,'Uniform':{k:1/11 for k in p}}
        report=phase3.summarize([row],{'weight':.5,'temperature':1.25,'baseline_temperature':1.25})
        self.assertEqual(report['games'],1)
        legacy=next(x for x in report['summary'] if x['cohort']=='All resolved modeled games' and x['model']=='Legacy Baseline')
        self.assertTrue(math.isinf(legacy['Log loss']))
        complete=next(x for x in report['summary'] if x['cohort']=='Other outcomes' and x['model']=='Selected hybrid')
        self.assertEqual(complete['Evaluated games'],1);self.assertTrue(math.isfinite(complete['Log loss']))
    def test_ambiguous_later_play_does_not_erase_known_first_scorer(self):
        f=OpeningResultEnrichmentTests();f.setUp();payload=copy.deepcopy(f.payload)
        first=next(p for p in payload['plays'] if p.get('scoringPlay'))
        later=copy.deepcopy(first);later['sequenceNumber']='9999999';later['participants']=[{'athlete':{}}];payload['plays'].append(later)
        record=od.extract(od.game_from_payload(payload),payload)
        self.assertEqual(record['status'],'resolved');self.assertEqual(record['scorer_id'],str(first['participants'][0]['athlete']['id']))
        self.assertFalse(record['rows']);self.assertTrue(record['warnings'])

class ArchiveEvaluationTests(unittest.TestCase):
    def test_projected_or_malformed_archive_cannot_verify_history(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'archive.jsonl';p.write_text('{bad json\n'+json.dumps({'game_id':'x','saved_at':'2025-01-01T00:00:00Z'})+'\n')
            verified,errors=od.archive_for_evaluation({'x':{'rows':[{'game_id':'x','date':'2025-01-01'}],'start_time':'2025-01-01T01:00:00Z'}},p)
            self.assertEqual(verified,{});self.assertEqual(len(errors),1)
    def test_provider_archive_requires_actual_matching_start_and_five(self):
        f=test_dashboard.NBAConfirmedLineupTests();f.setUp();lineups={t:ps[:5] for t,ps in f.rosters.items()}
        rows=[{**p,'team':t,'date':f.game['_date'],'game_id':'espn_1'} for t,ps in lineups.items() for p in ps]
        records={'espn_1':{'rows':rows,'start_time':f.game['start_time']}}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive.jsonl'
            od.archive_lineup(f.game,lineups,{},f.parse()['entries']['espn_1'],f.rosters,[],f.now.isoformat(),path,f.now)
            verified,errors=od.archive_for_evaluation(records,path);self.assertIn('espn_1',verified)
            records['espn_1']['start_time']='2027-01-03T00:00:00Z'
            self.assertEqual(od.archive_for_evaluation(records,path)[0],{})

class OpeningExposureTests(unittest.TestCase):
    def test_turnover_separates_opening_possession_from_first_fg(self):
        self.assertEqual(phase3.opening_exposure({'events':[{'kind':'turnover'},{'kind':'shot'}]}),'First FG after a possession change')
        self.assertEqual(phase3.opening_exposure({'events':[{'kind':'rebound','offensive':True},{'kind':'shot'}]}),'First FG on opening possession (event proxy)')
    def test_free_throw_path_is_not_a_first_field_goal(self):
        self.assertEqual(phase3.opening_exposure({'events':[{'kind':'ft','made':1},{'kind':'shot'}]}),'Free throw before first FG')
        self.assertEqual(phase3.opening_exposure(None),'Unavailable opening sequence')
