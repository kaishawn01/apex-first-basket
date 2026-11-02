import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
import opening_data as od
import phase2 as p2
import simulation as sim
import dashboard_core as core
import first_basket_engine as eng
import test_dashboard
from test_research import game_rows,OpeningResultEnrichmentTests


def sample_history():
    history=[];records={}
    for i in range(12):
        rows=game_rows(str(i),f'2026-08-{i+1:02d}')
        for r in rows:r['opening_score_path']='opening_fg_made'
        history.extend(rows)
        records[str(i)]={'schema':1,'game_id':str(i),'date':rows[0]['date'],'start_time':rows[0]['date']+'T23:00:00Z',
            'history_identity':od.history_identity(rows),'starters':{r['player_id']:r['team'] for r in rows},
            'tip':{'winner':'BOS','jumpers':{'BOS':'10','NYK':'20'}},'events':[
                {'kind':'shot','team':'BOS','player':'10','value':2,'made':1,'category':'rim','first_team_shot':True,'second_chance':False},
                {'kind':'shot','team':'NYK','player':'20','value':3,'made':0,'category':'three','first_team_shot':True,'second_chance':False},
                {'kind':'rebound','team':'NYK','offensive':True},
                {'kind':'shot','team':'NYK','player':'21','value':2,'made':1,'category':'two_jump','first_team_shot':False,'second_chance':True},
                {'kind':'turnover','team':'BOS'},
                {'kind':'ft','team':'NYK','player':'21','made':1,'trip_start':True,'shots':2}],
            'lineup_verification':'unverified','substitution_before_first_score':False,'warnings':[]}
    lineups={t:[{'player_id':str(offset+i),'player':f'{t} Player {i}'} for i in range(5)] for t,offset in [('BOS',10),('NYK',20)]}
    return history,records,lineups


class OpeningSequenceTests(unittest.TestCase):
    def setUp(self):
        fixture=OpeningResultEnrichmentTests();fixture.setUp();self.payload=fixture.payload
        self.game={'gameId':'espn_401809955','_date':'2025-10-25','start_time':'2025-10-25T23:00:00Z','homeTeam':{'teamTricode':'ORL'},'awayTeam':{'teamTricode':'CHI'}}
        c=self.payload['header']['competitions'][0]
        sides={x['homeAway']:eng.espn_team(x['team']) for x in c['competitors']}
        for side in ('home','away'):self.game[side+'Team']['teamTricode']=sides[side]
    def test_recorded_fixture_has_explicit_tip_and_typed_shots(self):
        r=od.extract(self.game,self.payload)
        self.assertIsNotNone(r['tip']);self.assertEqual(set(r['tip']['jumpers']),{'CHI','ORL'})
        self.assertTrue(any(e['kind']=='shot' and e['value']==3 for e in r['events']))
        self.assertEqual(r['lineup_verification'],'unverified')
    def test_unknown_and_conflicting_types_are_not_guessed_from_distance(self):
        self.assertIsNone(od.shot_type({'text':'misses 25-foot jumper','scoringPlay':False,'scoreValue':0}))
        self.assertIsNone(od.shot_type({'text':'makes three point jumper','scoringPlay':True,'scoreValue':2}))
        self.assertEqual(od.shot_type({'text':'misses driving layup'}),2)
    def test_stop_before_substitution_and_outside_opening_window(self):
        self.payload['plays'][1]['type']['text']='Substitution';self.payload['plays'][1]['text']='Player enters the game for Other'
        r=od.extract(self.game,self.payload)
        self.assertEqual(r['events'],[]);self.assertTrue(r['substitution_before_first_score'])
    def test_unmatched_tip_recipient_stays_unknown(self):
        self.payload['plays'][0]['text']='A vs B (Unknown Person gains possession)'
        self.assertIsNone(od.extract(self.game,self.payload)['tip'])
    def test_validated_identity_and_malformed_sidecars(self):
        h,s,_=sample_history();self.assertTrue(od.valid_for_history(s['0'],h[:10]))
        for record in (None,{},[],{**s['0'],'events':[None]},{**s['0'],'tip':{'winner':'CLE'}}):self.assertFalse(od.valid_for_history(record,h[:10]))
        bad=copy.deepcopy(s['0']);bad['events'][0]['player']='999'
        self.assertFalse(od.valid_for_history(bad,h[:10]))
    def test_atomic_sidecar_round_trip(self):
        _,records,_=sample_history()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'sequence.json';od.write(records,path);loaded=od.load(path)
            self.assertEqual(set(loaded),set(records));self.assertEqual(loaded['0']['tip'],records['0']['tip'])
            path.write_text('{"schema":7,"games":{}}')
            with self.assertRaises(ValueError):od.load(path)
    def test_enrichment_preserves_history_and_avoids_reloading_complete_games(self):
        play,box=eng.espn_game_payloads(self.payload);history=eng.extract_game(self.game,play,box);before=copy.deepcopy(history)
        with tempfile.TemporaryDirectory() as d,patch.object(core,'request',return_value=self.payload) as request:
            path=Path(d)/'sequence.json';r=od.enrich(history,1,path);self.assertEqual(r['added'],1)
            self.assertEqual(od.enrich(history,1,path)['attempted'],0);self.assertEqual(request.call_count,1)
        self.assertEqual(before,history)


class Phase2ModelTests(unittest.TestCase):
    def setUp(self):self.history,self.records,self.lineups=sample_history();self.cfg=sim.SimulationConfig(trials=1000)
    def test_probability_conservation_and_distinct_outputs(self):
        r=p2.simulate(self.history,self.lineups,'2026-08-13',self.records,self.cfg)
        for key in ('baseline','simulation','hybrid','first_shot'):self.assertAlmostEqual(sum(r[key].values()),1)
        self.assertAlmostEqual(sum(r['first_opportunity'].values()),1)
        self.assertNotEqual(r['first_shot'],r['hybrid']);self.assertEqual(sum(r['wins'].values())+r['unresolved_trials'],1000)
        self.assertTrue(all(v>0 for v in r['hybrid'].values()))
    def test_empirical_tip_shot_types_defense_and_second_chances(self):
        inputs=p2.build_inputs(self.history,self.lineups,'2026-08-13',self.records,self.cfg)
        self.assertGreater(inputs['opening_team']['BOS'],.5)
        self.assertEqual(inputs['teams']['BOS']['tip_source'],'explicit jump-ball possession')
        self.assertGreater(inputs['teams']['NYK']['second_share']['21'],inputs['teams']['NYK']['second_share']['20'])
        self.assertGreater(inputs['teams']['BOS']['make_by_type']['10'][2],inputs['teams']['NYK']['make_by_type']['20'][3])
    def test_reproducible_with_order_independence(self):
        a=p2.simulate(self.history,self.lineups,'2026-08-13',self.records,self.cfg)
        b=p2.simulate(list(reversed(self.history)),{t:list(reversed(ps)) for t,ps in reversed(list(self.lineups.items()))},'2026-08-13',self.records,self.cfg)
        self.assertEqual(a['wins'],b['wins']);self.assertEqual(a['hybrid'],b['hybrid'])
    def test_same_day_future_and_mismatched_sidecars_do_not_train(self):
        original=p2.build_inputs(self.history,self.lineups,'2026-08-13',self.records,self.cfg)
        records=copy.deepcopy(self.records);records['future']={**records['0'],'date':'2026-08-14'}
        same=p2.build_inputs(self.history+game_rows('future','2026-08-14'),self.lineups,'2026-08-13',records,self.cfg)
        self.assertEqual(original,same)
        records['0']['date']='2026-08-13'
        reduced=p2.build_inputs(self.history,self.lineups,'2026-08-13',records,self.cfg)
        self.assertEqual(reduced['sequence_games'],11);self.assertIn('0',reduced['rejected_sequence_games'])
    def test_missing_data_exposes_neutral_tip_and_no_automatic_promotion(self):
        r=p2.simulate([],self.lineups,'2026-08-13',{},self.cfg)
        self.assertEqual(r['hybrid'],r['baseline']);self.assertEqual(r['inputs']['sequence_games'],0)
        self.assertEqual(set(r['inputs']['opening_team'].values()),{.5})
    def test_event_cap_and_forced_ft(self):
        from dataclasses import replace
        r=p2.simulate([],self.lineups,'2026-08-13',{},replace(self.cfg,turnover_rate=1,shooting_foul_rate=0,max_events=1))
        self.assertEqual(r['unresolved_trials'],1000)
        r=p2.simulate([],self.lineups,'2026-08-13',{},replace(self.cfg,turnover_rate=0,shooting_foul_rate=1,free_throw_rate=1))
        self.assertEqual(r['transitions']['free_throw_scores'],1000);self.assertEqual(sum(r['first_shot'].values()),0)
    def test_no_network_or_mutation(self):
        original=copy.deepcopy(self.records)
        with patch.object(core,'request',side_effect=AssertionError('Offline')):p2.simulate(self.history,self.lineups,'2026-08-13',self.records,self.cfg)
        self.assertEqual(self.records,original)


class Phase2ValidationTests(unittest.TestCase):
    def setUp(self):self.history,self.records,self.lineups=sample_history();self.cfg=sim.SimulationConfig(trials=100)
    def test_small_validation_disables_fitting(self):
        validation,_=p2.forecast_history(self.history,self.records,self.cfg,2)
        selected=p2.select(validation)
        self.assertEqual((selected['weight'],selected['temperature']),(0,1));self.assertFalse(selected['calibration_sample_minimum_met'])
    def test_final_test_labels_cannot_change_selection_or_prior_predictions(self):
        a=p2.evaluate_holdout(self.history,self.records,'2026-08-10','2026-08-12',self.cfg,2)
        modified=copy.deepcopy(self.history)
        for row in modified:
            if row['date']>='2026-08-10' and row['team']=='BOS':
                row['first_scorer']=int(row['player_id']=='11');row['first_fg_scorer']=int(row['player_id']=='11');row['opening_score_path']=''
            elif row['date']>='2026-08-10':row['opening_score_path']=''
        b=p2.evaluate_holdout(modified,self.records,'2026-08-10','2026-08-12',self.cfg,2)
        self.assertEqual(a['selection'],b['selection'])
    def test_lock_callback_precedes_any_final_test_forecast(self):
        locked=[];original=p2.forecast_history
        def spy(*args,**kwargs):
            if kwargs.get('start'):self.assertTrue(locked)
            return original(*args,**kwargs)
        with patch.object(p2,'forecast_history',side_effect=spy):p2.evaluate_holdout(self.history,self.records,'2026-08-10','2026-08-12',self.cfg,2,on_lock=locked.append)
    def test_all_models_same_games_uniform_calibration_and_unverified_cohort(self):
        r=p2.evaluate_holdout(self.history,self.records,'2026-08-10','2026-08-12',self.cfg,2)
        allrows=[row for row in r['summary'] if row['Cohort']=='All test games']
        self.assertEqual({row['Evaluated games'] for row in allrows},{3})
        verified=[row for row in r['summary'] if row['Cohort']=='Verified historical lineups']
        self.assertEqual({row['Evaluated games'] for row in verified},{0})
        uniform=next(row for row in allrows if row['Model']=='Uniform')
        self.assertAlmostEqual(uniform['Log loss'],math.log(10));self.assertAlmostEqual(uniform['Brier'],.9)
        self.assertTrue(r['calibration']);self.assertEqual(r['first_shot']['Eligible games'],3)
    def test_verified_requires_archived_pretip_provider_evidence(self):
        fixture=test_dashboard.NBAConfirmedLineupTests();fixture.setUp();rows=game_rows('espn_1','2027-01-02')
        entries=fixture.parse()['entries']['espn_1'];snapshot={'game_id':'espn_1','date':'2027-01-02','start_time':fixture.game['start_time'],'saved_at':fixture.now.isoformat(),'lineup_evidence':{t:{'method':'NBA feed confirmed',**e} for t,e in entries.items()}}
        self.assertTrue(p2.verified_historical_lineup(snapshot,rows,fixture.game['start_time']))
        snapshot['saved_at']='2027-01-03T00:00:00Z';self.assertFalse(p2.verified_historical_lineup(snapshot,rows,fixture.game['start_time']))
        self.assertFalse(p2.verified_historical_lineup({'status':'verified'},rows))
    def test_invalid_period_and_empty_history(self):
        with self.assertRaises(ValueError):p2.evaluate_holdout([],{},'2026-08-12','2026-08-10',self.cfg)
        self.assertEqual(p2.evaluate_holdout([],{},'2026-08-10','2026-08-12',self.cfg)['evaluated_games'],0)


class Phase2ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_dashboard.NBAConfirmedLineupTests();self.fixture.setUp();f=self.fixture
        self.lineups={t:ps[:5] for t,ps in f.rosters.items()}
    def readiness(self,rosters=None,reports=None,time=None):
        f=self.fixture
        return core.phase2_readiness(f.game,self.lineups,{},f.parse()['entries']['espn_1'],rosters or f.rosters,reports or [],time or f.now.isoformat(),f.now)
    def test_verified_is_still_research_only_never_actionable(self):
        r=self.readiness();self.assertTrue(r['provider_verified']);self.assertFalse(r['actionable']);self.assertTrue(r['status'].startswith('RESEARCH ONLY'))
    def test_roster_change_and_duplicates_rejected(self):
        rosters=copy.deepcopy(self.fixture.rosters);rosters['BOS'].pop(0)
        self.assertTrue(any('no longer' in m for m in self.readiness(rosters)['messages']))
        self.lineups['BOS'][1]=self.lineups['BOS'][0]
        self.assertTrue(any('identit' in m for m in self.readiness()['messages']))
    def test_stale_injury_and_selected_injury_report_hold(self):
        self.assertTrue(any('Injury report' in m for m in self.readiness(time=(self.fixture.now-timedelta(hours=1)).isoformat())['messages']))
        reports=[{'team':'BOS','player':'BOS Player 0','status':'Out','description':'Unavailable'}]
        self.assertTrue(any('Out' in m for m in self.readiness(reports=reports)['messages']))

class Phase2SafetyTests(unittest.TestCase):
    def test_calibration_requires_both_game_and_date_minimums(self):
        ids=[str(i) for i in range(10)]
        rows=[{'Date':f'2026-08-{i%20+1:02d}','Game':str(i),'Winner':'0','Active':True,'Baseline':{p:.2 if p=='0' else .8/9 for p in ids},'Monte Carlo':{p:.1 for p in ids}} for i in range(100)]
        selected=p2.select(rows);self.assertTrue(selected['calibration_sample_minimum_met']);self.assertEqual(len(selected['candidates']),12)
        for row in rows:row['Date']='2026-08-01'
        self.assertFalse(p2.select(rows)['calibration_sample_minimum_met'])
    def test_same_day_forecasts_never_train_on_one_another(self):
        h,s,_=sample_history();h+=game_rows('same-day','2026-08-12');original=p2.simulate
        seen=[]
        def spy(history,lineups,day,*args):
            self.assertTrue(all(r['date']<day for r in history));seen.append(day)
            return original(history,lineups,day,*args)
        with patch.object(p2,'simulate',side_effect=spy):p2.forecast_history(h,s,sim.SimulationConfig(trials=100),2)
        self.assertEqual(seen.count('2026-08-12'),2)
    def test_retry_queue_reaches_unattempted_games(self):
        fixture=OpeningResultEnrichmentTests();fixture.setUp()
        play,box=eng.espn_game_payloads(fixture.payload);base=eng.extract_game({'gameId':'espn_401809955','_date':'2025-10-25'},play,box)
        rows=base+[{**r,'game_id':'espn_401809956','date':'2025-10-26'} for r in base]
        calls=[]
        def fail(url,params):calls.append(params['event']);raise RuntimeError('Offline')
        with tempfile.TemporaryDirectory() as d,patch.object(core,'request',side_effect=fail):
            path=Path(d)/'sequence.json';od.enrich(rows,1,path);od.enrich(rows,1,path)
        self.assertEqual(calls,['401809955','401809956'])
    def test_invalid_cache_or_tracker_blocks_network(self):
        h,_,_=sample_history()
        with tempfile.TemporaryDirectory() as d,patch.object(core,'request') as request:
            path=Path(d)/'sequence.json';path.write_text('[]')
            with self.assertRaises(ValueError):od.enrich(h,1,path)
            path.unlink();path.with_name('sequence_attempts.json').write_text('{"attempts": {"bad": true}}')
            with self.assertRaises(ValueError):od.enrich(h,1,path)
            request.assert_not_called()
    def test_concurrent_cache_write_does_not_get_overwritten(self):
        fixture=OpeningResultEnrichmentTests();fixture.setUp();play,box=eng.espn_game_payloads(fixture.payload)
        rows=eng.extract_game({'gameId':'espn_401809955','_date':'2025-10-25'},play,box)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'sequence.json'
            def response(*args):path.write_text('external change');return fixture.payload
            with patch.object(core,'request',side_effect=response):report=od.enrich(rows,1,path)
            self.assertEqual(report['added'],0);self.assertEqual(path.read_text(),'external change')
    def test_future_missing_and_naive_injury_timestamps_are_holds(self):
        f=test_dashboard.NBAConfirmedLineupTests();f.setUp();lineups={t:ps[:5] for t,ps in f.rosters.items()}
        for stamp in (None,'bad','2027-01-02T21:00:00',(f.now+timedelta(minutes=1)).isoformat()):
            r=core.phase2_readiness(f.game,lineups,{},f.parse()['entries']['espn_1'],f.rosters,[],stamp,f.now)
            self.assertFalse(r['actionable']);self.assertTrue(any('Injury report' in m for m in r['messages']))

class Phase2ReviewTests(unittest.TestCase):
    def test_priced_unverified_or_injured_matchups_have_no_model_ev(self):
        f=test_dashboard.DashboardTests();f.setUp()
        prices={(f.game['gameId'],eng.norm(p['player'])):(20,'+1900','Book','now') for ps in f.lineups.values() for p in ps}
        for confirmed,reports in (({},[]),({'BOS':True,'NYK':True},[{'team':'BOS','player':'BOS Player 0','status':'Out'}])):
            rows=core.rank_game([],f.game,f.lineups,confirmed,prices,reports)
            self.assertTrue(all(r['Status'].startswith('HOLD:') and r['Model EV %'] is None for r in rows))
            self.assertTrue(all(r['Book odds']=='+1900' for r in rows))
    def test_phase2_manifest_requires_both_new_runtime_modules(self):
        import updater
        manifest={'version':'3.0.1','files':{name:'a'*64 for name in updater.REQUIRED|{'simulation.py'}}}
        with self.assertRaisesRegex(ValueError,'Phase 2'):updater.validate_manifest(manifest)
        manifest['files']['phase2.py']='a'*64
        with self.assertRaises(ValueError):updater.validate_manifest(manifest)
        manifest['files']['opening_data.py']='a'*64
        self.assertEqual(updater.validate_manifest(manifest),manifest)
    def test_archived_confirmation_needs_matching_actual_start(self):
        f=test_dashboard.NBAConfirmedLineupTests();f.setUp();rows=game_rows('espn_1','2027-01-02')
        entries=f.parse()['entries']['espn_1'];snap={'game_id':'espn_1','date':'2027-01-02','start_time':f.game['start_time'],'saved_at':f.now.isoformat(),'lineup_evidence':{t:{'method':'NBA feed confirmed',**e} for t,e in entries.items()}}
        self.assertFalse(p2.verified_historical_lineup(snap,rows))
        self.assertFalse(p2.verified_historical_lineup(snap,rows,'2027-01-02T22:00:00Z'))
