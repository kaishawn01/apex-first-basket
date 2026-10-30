"""Offline regression, statistical and leakage tests for the V3 development branch."""
import copy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import math
import unittest
from unittest.mock import patch
import simulation as sim
import research_tools as research
import dashboard_core as core
from test_research import game_rows
import test_dashboard


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.lineups={t:[{'player_id':str(offset+i),'player':f'{t} Player {i}'} for i in range(5)] for t,offset in [('BOS',10),('NYK',20)]}
        self.history=[r for i in range(12) for r in game_rows(str(i),f'2026-08-{i+1:02d}')]
        self.config=sim.SimulationConfig(trials=1000)
    def test_normalized_positive_hybrid_and_count_conservation(self):
        report=sim.simulate(self.history,self.lineups,'2026-08-13',self.config)
        for key in ('baseline','simulation','hybrid'):self.assertAlmostEqual(sum(report[key].values()),1)
        self.assertTrue(all(p>0 for p in report['hybrid'].values()))
        self.assertEqual(sum(report['wins'].values())+report['unresolved_trials'],1000)
        self.assertEqual(report['transitions']['field_goal_scores']+report['transitions']['free_throw_scores'],sum(report['wins'].values()))
        self.assertEqual(report['effective_hybrid_weight'],.35)
    def test_deterministic_across_row_and_lineup_order(self):
        a=sim.simulate(self.history,self.lineups,'2026-08-13',self.config)
        lineups={t:list(reversed(ps)) for t,ps in reversed(list(self.lineups.items()))}
        b=sim.simulate(list(reversed(self.history)),lineups,'2026-08-13',self.config)
        self.assertEqual(a,b)
    def test_no_history_falls_back_without_inventing_samples(self):
        r=sim.simulate([],self.lineups,'2026-08-13',self.config)
        self.assertEqual(r['hybrid'],r['baseline']);self.assertFalse(r['minimum_history_met'])
        self.assertTrue(all(row['Known opening outcomes']==0 for row in r['inputs']['evidence']))
    def test_zero_blend_exact_existing_model(self):
        r=sim.simulate(self.history,self.lineups,'2026-08-13',replace(self.config,hybrid_weight=0))
        self.assertEqual(r['hybrid'],r['baseline']);self.assertEqual(set(r['hybrid_mc_se'].values()),{0})
    def test_forced_turnovers_retain_all_unresolved_mass(self):
        r=sim.simulate(self.history,self.lineups,'2026-08-13',replace(self.config,turnover_rate=1,shooting_foul_rate=0,max_events=3))
        self.assertEqual(r['unresolved_trials'],1000);self.assertEqual(r['transitions']['turnovers'],3000)
        for pid,p in r['hybrid'].items():self.assertAlmostEqual(p,r['baseline'][pid])
    def test_forced_fouls_count_free_throws_as_first_score(self):
        r=sim.simulate(self.history,self.lineups,'2026-08-13',replace(self.config,turnover_rate=0,shooting_foul_rate=1,free_throw_rate=1))
        self.assertEqual(r['transitions']['free_throw_scores'],1000)
        self.assertEqual(r['transitions']['field_goal_attempts'],0);self.assertEqual(r['mean_events'],1)
    def test_rebounds_keep_or_switch_possession(self):
        inputs=sim.build_inputs(self.history,self.lineups,'2026-08-13')
        inputs['opening_team']={'BOS':1.0,'NYK':0.0}
        inputs['teams']['BOS']['make']={pid:0 for pid in inputs['teams']['BOS']['players']}
        inputs['teams']['NYK']['make']={pid:1 for pid in inputs['teams']['NYK']['players']}
        cfg=replace(self.config,turnover_rate=0,shooting_foul_rate=0,offensive_rebound_rate=0,max_events=3)
        with patch.object(sim,'build_inputs',return_value=inputs):r=sim.simulate([],self.lineups,'2026-08-13',cfg)
        self.assertEqual(sum(r['wins'][str(i)] for i in range(20,25)),1000)
        self.assertEqual(r['transitions']['defensive_rebounds'],1000)
        with patch.object(sim,'build_inputs',return_value=inputs):r=sim.simulate([],self.lineups,'2026-08-13',replace(cfg,offensive_rebound_rate=1))
        self.assertEqual(r['unresolved_trials'],1000);self.assertEqual(r['transitions']['offensive_rebounds'],3000)
    def test_symmetric_prior_monte_carlo_within_sampling_tolerance(self):
        cfg=replace(self.config,trials=20000,min_team_games=0,hybrid_weight=1)
        r=sim.simulate([],self.lineups,'2026-08-13',cfg)
        self.assertTrue(all(abs(p-.1)<.015 for p in r['simulation'].values()))
    def test_invalid_config_and_lineups_rejected(self):
        for kwargs in ({'trials':True},{'trials':0},{'seed':-1},{'hybrid_weight':float('nan')},{'max_events':0},{'turnover_rate':.8,'shooting_foul_rate':.5},{'free_throw_rate':2}):
            with self.assertRaises(ValueError):replace(self.config,**kwargs).validate()
        bad=copy.deepcopy(self.lineups);bad['NYK'][0]['player_id']='10'
        with self.assertRaises(ValueError):sim.simulate([],bad,'2026-08-13',self.config)
    def test_training_excludes_future_same_day_old_and_preserves_input(self):
        before=copy.deepcopy(self.history)
        a=sim.build_inputs(self.history,self.lineups,'2026-08-13')
        extra=game_rows('today','2026-08-13')+game_rows('future','2026-08-14')+game_rows('old','2024-01-01')
        b=sim.build_inputs(self.history+extra,self.lineups,'2026-08-13')
        self.assertEqual(a,b);self.assertEqual(before,self.history)
    def test_prior_invalid_history_fails_closed(self):
        bad=copy.deepcopy(self.history);bad[0]['first_scorer']='bad'
        with self.assertRaises(ValueError):sim.build_inputs(bad,self.lineups,'2026-08-13')
    def test_backtest_identical_baseline_and_date_leakage_guard(self):
        seen=[];original=sim.simulate
        def spy(history,lineups,target_day,config):
            self.assertTrue(all(r['date']<target_day for r in history));seen.append(target_day)
            return original(history,lineups,target_day,config)
        rows=self.history+game_rows('same-day','2026-08-12')
        with patch.object(sim,'simulate',side_effect=spy),patch.object(core,'request',side_effect=AssertionError('No APIs')):
            report=sim.backtest(rows,3,replace(self.config,trials=100))
        existing=research.evaluate(rows,3,'baseline')['games']
        baseline=[r for r in report['details'] if r['Model']=='Baseline']
        self.assertEqual({r['Game'] for r in baseline},{r['Game'] for r in existing})
        for row in baseline:
            old=next(r for r in existing if r['Game']==row['Game'])
            for metric in ('Log loss','Brier','Top-1 credit','Top-3 credit'):self.assertAlmostEqual(row[metric],old[metric])
        self.assertEqual(len(seen),len(existing));self.assertTrue(all(r['Last training date']<r['Date'] for r in report['diagnostics']))
    def test_backtest_empty_and_invalid_warmup(self):
        self.assertEqual(sim.backtest([],1,self.config)['summary'],[])
        with self.assertRaises(ValueError):sim.backtest([],True,self.config)
    def test_newest_quarter_keeps_entire_dates_and_fallback_visible(self):
        report=sim.backtest(self.history+game_rows('same-day','2026-08-12'),3,replace(self.config,trials=100))
        rows=[r for r in report['summary'] if r['Period']=='Newest quarter of dates']
        self.assertEqual({r['Dates'] for r in rows},{3})
        self.assertEqual({r['Evaluated games'] for r in rows},{4})
        self.assertTrue(any(r['Effective hybrid weight']==0 for r in report['diagnostics']))
    def test_probability_export_includes_noise_and_sources(self):
        r=sim.simulate(self.history,self.lineups,'2026-08-13',self.config)
        rows=sim.prediction_rows(r,self.lineups)
        self.assertEqual(len(rows),10);self.assertTrue(all(x['Monte Carlo SE pp']>=0 for x in rows))
        self.assertTrue(all('Foul-shooter proxy %' in x for x in rows))


class LineupVerificationV3Tests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_dashboard.NBAConfirmedLineupTests();self.fixture.setUp()
    def test_individual_update_timestamps_do_not_require_identical_batch(self):
        f=self.fixture;f.payload['games'][0]['awayTeam']['players'][0]['timestamp']='2027-01-02T15:58:00'
        self.assertIn('BOS',f.parse()['entries']['espn_1'])
        self.assertEqual(len(f.parse()['entries']['espn_1']['BOS']['source_timestamps']),2)
    def test_aware_future_timestamp_rejected(self):
        f=self.fixture;f.payload['games'][0]['awayTeam']['players'][0]['timestamp']='2027-01-02T23:00:00Z'
        self.assertNotIn('BOS',f.parse()['entries']['espn_1'])
    def test_aware_utc_midnight_uses_eastern_game_date(self):
        f=self.fixture;f.now=datetime(2027,1,3,1,tzinfo=timezone.utc);f.game['start_time']='2027-01-03T03:00:00Z'
        for p in f.payload['games'][0]['awayTeam']['players']:p['timestamp']='2027-01-03T00:30:00Z'
        self.assertIn('BOS',f.parse()['entries']['espn_1'])
    def test_accent_normalization_requires_unique_full_name(self):
        f=self.fixture;f.payload['games'][0]['awayTeam']['players'][0]['playerName']='Nikola Jokić';f.rosters['BOS'][0]['player']='Nikola Jokic'
        self.assertIn('BOS',f.parse()['entries']['espn_1'])
        f.rosters['BOS'].append({'player_id':'888','player':'Nikola Jokić'})
        self.assertNotIn('BOS',f.parse()['entries']['espn_1'])
    def test_duplicate_manual_ids_never_confirm(self):
        f=self.fixture;players=[f.rosters['BOS'][0]]*5
        self.assertEqual(core.lineup_confirmation_sources(f.game,{'BOS':players},{'BOS':True},{},f.now)['BOS'],'Unconfirmed')
    def test_wrong_team_provider_entry_not_reused(self):
        f=self.fixture;entry=f.parse()['entries']['espn_1']['BOS'];entry['team']='NYK'
        sources=core.lineup_confirmation_sources(f.game,{'BOS':f.rosters['BOS'][:5]},{},{'BOS':entry},f.now)
        self.assertEqual(sources['BOS'],'Unconfirmed')
    def test_malformed_player_gives_actionable_message(self):
        f=self.fixture;f.payload['games'][0]['awayTeam']['players'].append(None)
        result=f.parse();self.assertNotIn('BOS',result['entries']['espn_1'])
        self.assertTrue(any('Malformed player entry' in x for x in result['messages']))

class AdditionalReviewTests(unittest.TestCase):
    def test_duplicate_nba_identity_across_sides_rejected(self):
        f=test_dashboard.NBAConfirmedLineupTests();f.setUp()
        f.payload['games'][0]['homeTeam']['players'][0]['personId']=100
        self.assertEqual(f.parse()['entries'],{})
    def test_empty_timestamp_evidence_cannot_confirm(self):
        f=test_dashboard.NBAConfirmedLineupTests();f.setUp()
        entry=f.parse()['entries']['espn_1']['BOS'];entry['source_timestamps']=[]
        self.assertFalse(core.nba_confirmation_matches(entry,f.game,f.rosters['BOS'][:5],f.now))
    def test_nonfinite_mc_loss_retained_and_undefined_interval_withheld(self):
        history=game_rows('a','2026-08-01')+game_rows('b','2026-08-02')
        ids=[r['player_id'] for r in history[:10]]
        fake={'baseline':{pid:.1 for pid in ids},'hybrid':{pid:0 if pid=='10' else 1/9 for pid in ids},
              'effective_hybrid_weight':1,'unresolved_trials':0,'inputs':{'last_training_date':'2026-08-01','history_fingerprint':'test'}}
        with patch.object(sim,'simulate',return_value=fake):report=sim.backtest(history,1,sim.SimulationConfig(trials=100,hybrid_weight=1))
        row=next(r for r in report['details'] if r['Model']=='Hybrid MC')
        self.assertEqual(row['Winner probability'],0);self.assertTrue(math.isinf(row['Log loss']))
        self.assertTrue(any('withheld' in r.get('Note','') for r in report['comparisons']))


class V3ManifestTests(unittest.TestCase):
    def test_v3_requires_simulator_without_weakening_legacy_or_protected_files(self):
        import updater
        manifest={'version':'3.0.0','files':{name:'a'*64 for name in updater.REQUIRED}}
        with self.assertRaisesRegex(ValueError,'simulation'):updater.validate_manifest(manifest)
        manifest['files']['simulation.py']='a'*64
        self.assertEqual(updater.validate_manifest(manifest),manifest)
        manifest['files']['data/history_espn.csv']='a'*64
        with self.assertRaises(ValueError):updater.validate_manifest(manifest)
