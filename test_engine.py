"""Run: py -m unittest -v test_engine.py (no internet required)."""
import unittest
import json
from pathlib import Path
import first_basket_engine as eng


class FirstBasketTests(unittest.TestCase):
    def test_fanduel_free_throw_scoring_and_first_fg(self):
        def a(n, typ, team, pid, desc, fg=0, result=""):
            return dict(period=1, actionId=n, actionType=typ, teamTricode=team,
                        personId=pid, description=desc, isFieldGoal=fg, shotResult=result)
        actions = [
            a(1, "period", "", 0, "Start of 1st Period"),
            a(2, "Jump Ball", "AAA", 1, "Jump ball"),
            a(3, "Missed Shot", "AAA", 1, "MISS One three", 1, "Missed"),
            a(4, "Missed Shot", "BBB", 6, "MISS Six layup", 1, "Missed"),
            a(5, "Free Throw", "BBB", 7, "MISS Seven Free Throw 1 of 2"),
            a(6, "Free Throw", "BBB", 7, "Seven Free Throw 2 of 2"),
            a(7, "Made Shot", "AAA", 2, "Two 3PT Jump Shot", 1, "Made"),
        ]
        play = {"game": {"actions": actions}}
        box = {"game": {
            "homeTeam": {"teamTricode": "AAA", "players": [{"personId": i, "name": f"AAA Player{i}", "starter": "1"} for i in range(1, 6)]},
            "awayTeam": {"teamTricode": "BBB", "players": [{"personId": i, "name": f"BBB Player{i}", "starter": True} for i in range(6, 11)]},
        }}
        history = eng.extract_game({"gameId": "0022600001", "_date": "2026-10-25"}, play, box)
        self.assertEqual(len(history), 10)
        self.assertEqual([(r["team"], r["player_id"]) for r in history if r["first_scorer"]], [("BBB", "7")])
        self.assertEqual([(r["team"], r["player_id"]) for r in history if r["first_fg_scorer"]], [("AAA", "2")])
        self.assertEqual([(r["team"], r["player_id"]) for r in history if r["first_team_shot"]], [("AAA", "1"), ("BBB", "6")])
        self.assertEqual(sum(r["first_game_shot"] for r in history), 1)
        self.assertEqual(sum(r["tip_first_action"] for r in history), 5)

    def test_live_cdn_action_types(self):
        base = dict(personId=1, teamTricode="AAA", period=1, isFieldGoal=1)
        for typ in ("2pt", "3pt"):
            made = dict(base, actionType=typ, shotResult="Made")
            missed = dict(base, actionType=typ, shotResult="Missed")
            self.assertTrue(eng.is_fg_attempt(made))
            self.assertTrue(eng.is_made_score(made))
            self.assertFalse(eng.is_made_score(missed))
            self.assertEqual(eng.first_offense_team([missed]), "AAA")
        free = dict(base, actionType="freethrow", isFieldGoal=0, shotResult="Made")
        self.assertTrue(eng.is_made_score(free))
        self.assertFalse(eng.is_fg_attempt(free))
        self.assertFalse(eng.is_made_score(dict(free, shotResult="Missed")))
        self.assertFalse(eng.is_made_score(dict(free, shotResult="")))

    def test_espn_real_game_adapter(self):
        payload = json.loads(Path(__file__).with_name("espn_test_fixture.json").read_text())
        play, box = eng.espn_game_payloads(payload)
        rows = eng.extract_game({"gameId": "espn_401809955", "_date": "2025-10-25"}, play, box)
        self.assertEqual(len(rows), 10)
        self.assertEqual([r["player"] for r in rows if r["first_scorer"]], ["Josh Giddey"])
        self.assertEqual(eng.espn_team({"abbreviation": "GS"}), "GSW")

    def test_odds_math(self):
        self.assertAlmostEqual(eng.american_to_decimal("+650"), 7.5)
        self.assertAlmostEqual(eng.american_to_decimal("-150"), 1.66666666667)
        self.assertIsNone(eng.american_to_decimal("NA"))
        self.assertAlmostEqual(0.20 * eng.american_to_decimal("+650") - 1, 0.50)

    def test_normalized_probability(self):
        stats = {"AAA": {"first": 0.55, "tip_proxy": 0.52}, "BBB": {"first": 0.45, "tip_proxy": 0.48}}
        p_team = eng.first_team_probability("AAA", "BBB", stats)
        starters = [{"player_id": str(i), "player": f"Player {i}"} for i in range(1, 6)]
        shares = eng.player_weights([], starters, "AAA")
        self.assertAlmostEqual(sum(p * p_team for _, p, *_ in shares), p_team, places=8)
        self.assertAlmostEqual(p_team + (1 - p_team), 1.0, places=8)

    def test_date_formats(self):
        self.assertEqual(eng.day_of_game({"gameDate": "10/25/2026 00:00:00"}), "2026-10-25")
        self.assertEqual(eng.day_of_game({"gameDate": "2026-10-25"}), "2026-10-25")


if __name__ == "__main__":
    unittest.main()

class SummaryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.game={'gameId':'espn_123','homeTeam':{'teamTricode':'BOS'},'awayTeam':{'teamTricode':'NYK'}}
        self.payload={'header':{'id':'123','competitions':[{'id':'123','status':{'type':{'completed':True}},'competitors':[{'homeAway':'home','team':{'abbreviation':'BOS'}},{'homeAway':'away','team':{'abbreviation':'NY'}}]}]}}
    def test_completed_matching_event_and_alias(self):
        eng.validate_espn_summary(self.game,self.payload)
    def test_wrong_event_incomplete_and_reversed_sides(self):
        import copy
        variants=[]
        p=copy.deepcopy(self.payload);p['header']['id']='999';variants.append(p)
        p=copy.deepcopy(self.payload);p['header']['competitions'][0]['id']='999';variants.append(p)
        p=copy.deepcopy(self.payload);p['header']['competitions'][0]['status']['type']['completed']=False;variants.append(p)
        p=copy.deepcopy(self.payload)
        for c in p['header']['competitions'][0]['competitors']:c['homeAway']='away' if c['homeAway']=='home' else 'home'
        variants.append(p)
        for payload in variants:
            with self.assertRaises(ValueError):eng.validate_espn_summary(self.game,payload)
    def test_trimmed_fixture_without_identity_is_rejected(self):
        payload=json.loads(Path(__file__).with_name('espn_test_fixture.json').read_text())
        competitors=payload['header']['competitions'][0]['competitors']
        game={'gameId':'espn_401809955'}
        for c in competitors:game[c['homeAway']+'Team']={'teamTricode':eng.espn_team(c['team'])}
        with self.assertRaises(ValueError):eng.validate_espn_summary(game,payload)

class ScheduleIntegrityTests(unittest.TestCase):
    def event(self,gid='123',start='2026-10-27T02:00:00Z',status='STATUS_SCHEDULED'):
        return {'id':gid,'date':start,'season':{'type':2},'status':{'type':{'name':status,'completed':status=='STATUS_FINAL'}},'competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'BOS'}},{'homeAway':'away','team':{'abbreviation':'NY'}}]}]}
    def test_utc_rollover_and_eastern_filter(self):
        import dashboard_core as core
        from unittest.mock import patch
        payload={'events':[self.event('1','2026-10-27T02:00:00Z'),self.event('2','2026-10-27T15:00:00Z')]}
        with patch.object(core,'request',return_value=payload):games=core.fresh_schedule('2026-10-26')
        self.assertEqual([g['gameId'] for g in games],['espn_1'])
        self.assertEqual(games[0]['_date'],'2026-10-26')
        winter=eng.parse_espn_schedule({'events':[self.event('3','2027-01-02T04:30:00Z')]})[0]
        self.assertEqual(winter['_date'],'2027-01-01')
    def test_naive_time_and_conflicting_duplicates_rejected(self):
        with self.assertRaises(ValueError):eng.parse_espn_schedule({'events':[self.event(start='2026-10-26T19:00:00')]})
        with self.assertRaises(ValueError):eng.parse_espn_schedule({'events':[self.event(),self.event(start='2026-10-27T03:00:00Z')]})
        self.assertEqual(len(eng.parse_espn_schedule({'events':[self.event(),self.event()]})),1)
    def test_upcoming_rejects_incoherent_cached_or_started_game(self):
        from datetime import datetime,timezone
        now=datetime(2026,10,26,22,tzinfo=timezone.utc)
        g=eng.parse_espn_schedule({'events':[self.event()]})[0]
        self.assertTrue(eng.game_is_upcoming(g,now))
        for change in ({'_date':'2026-10-27'},{'_schedule_cached':True},{'start_time':'bad'},{'start_time':'2026-10-26T19:00:00'},{'research_only':True},{'gameStatus':2}):
            self.assertFalse(eng.game_is_upcoming({**g,**change},now))
        self.assertFalse(eng.game_is_upcoming(g,datetime(2026,10,27,2,tzinfo=timezone.utc)))
    def test_postponed_and_cancelled_not_upcoming(self):
        for status in ('STATUS_POSTPONED','STATUS_CANCELED','STATUS_IN_PROGRESS'):
            g=eng.parse_espn_schedule({'events':[self.event(status=status)]})[0]
            self.assertNotEqual(g['gameStatus'],1)
    def test_empty_response_does_not_reuse_cached_slate(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'schedule.json';cache.write_text(json.dumps(eng.parse_espn_schedule({'events':[self.event()]})))
            with patch.object(eng,'SCHEDULE_CACHE',cache),patch.object(eng,'get_json',return_value={'events':[]}):
                self.assertEqual(eng.schedule('2026-10-26'),[])
    def test_offline_pregame_schedule_never_falls_back(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'schedule.json';cache.write_text(json.dumps(eng.parse_espn_schedule({'events':[self.event()]})))
            with patch.object(eng,'SCHEDULE_CACHE',cache),patch.object(eng,'get_json',side_effect=eng.requests.ConnectionError()):
                with self.assertRaisesRegex(RuntimeError,'Cached games cannot'):eng.schedule('2026-10-26')
    def test_sync_cache_contains_only_completed_games_in_window(self):
        import tempfile
        from unittest.mock import patch
        today=eng.datetime.now(eng.ZoneInfo('America/New_York')).date().isoformat()
        cached=[{'gameId':'espn_1','_date':today,'gameStatus':3},{'gameId':'espn_2','_date':today,'gameStatus':1},{'gameId':'espn_3','_date':'2000-01-01','gameStatus':3}]
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'schedule.json';cache.write_text(json.dumps(cached))
            with patch.object(eng,'SCHEDULE_CACHE',cache),patch.object(eng,'get_json',side_effect=eng.requests.ConnectionError()):games=eng.schedule()
            self.assertEqual([g['gameId'] for g in games],['espn_1'])
            self.assertTrue(games[0]['_schedule_cached'])

class SharedCommandLineTests(unittest.TestCase):
    def run_picks(self,history,model='baseline',duplicate=False,live=False):
        import tempfile,io,contextlib
        from unittest.mock import patch
        from types import SimpleNamespace
        from test_research import game_rows
        game={'gameId':'espn_123','_date':'2027-01-02','start_time':'2027-01-02T23:00:00Z','gameStatus':1,
              'awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
        starters=[{**r,'confirmed':'YES'} for r in game_rows('lineup','2027-01-02')]
        if duplicate:starters[5]['player_id']=starters[0]['player_id']
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            folder=Path(tmp);hist=folder/'history.csv';five=folder/'starters.csv'
            eng.write_csv(hist,eng.FIELDS,history)
            eng.write_csv(five,eng.FIELDS+['confirmed'],starters)
            for attr,value in [('HISTORY',hist),('STARTERS',five),('DATA',folder)]:stack.enter_context(patch.object(eng,attr,value))
            stack.enter_context(patch.object(eng,'schedule',return_value=[game]))
            stack.enter_context(patch.object(eng,'game_is_upcoming',return_value=True))
            stack.enter_context(patch.object(eng,'local_prices',return_value={}))
            paid=stack.enter_context(patch.object(eng,'api_prices',side_effect=AssertionError('No paid call expected')))
            output=io.StringIO();stack.enter_context(contextlib.redirect_stdout(output))
            result=eng.show_picks(SimpleNamespace(date='2027-01-02',live_odds=live,model=model))
            saved=eng.read_csv(folder/'predictions_2027-01-02.csv')
            return result,saved,output.getvalue(),starters,game
    def test_cli_probabilities_match_dashboard_for_all_models(self):
        from test_research import game_rows
        import dashboard_core as core
        history=game_rows('recent','2027-01-01')+game_rows('old','2020-01-01')+game_rows('future','2027-01-03')
        for model in ('baseline','recent','lineup'):
            result,saved,output,starters,game=self.run_picks(history,model)
            lineups={team:[r for r in starters if r['team']==team] for team in ('BOS','NYK')}
            expected=core.rank_game(history,game,lineups,{'BOS':True,'NYK':True},{},[],model)
            self.assertEqual({r['player']:r['prob'] for r in result},{r['Player']:r['_probability'] for r in expected})
            self.assertEqual({r['player']:r['status'] for r in result},{r['Player']:r['Status'] for r in expected})
            self.assertEqual({r['starts'] for r in saved},{'1'})
            self.assertIn('Injuries have NOT been checked',output)
    def test_invalid_history_blocks_before_paid_calls(self):
        from test_research import game_rows
        rows=game_rows('bad','2027-01-01');rows[1]['player_id']=rows[0]['player_id']
        with self.assertRaisesRegex(ValueError,'validation'):self.run_picks(rows,live=True)
    def test_cross_team_duplicate_is_held_without_output(self):
        from test_research import game_rows
        result,saved,output,_,_=self.run_picks(game_rows('recent','2027-01-01'),duplicate=True)
        self.assertEqual(result,[]);self.assertEqual(saved,[])
        self.assertIn('HOLD:',output)
    def test_cli_shot_coverage_hold_matches_dashboard(self):
        from test_research import game_rows
        from datetime import date,timedelta
        history=[r for i in range(12) for r in game_rows(str(i),(date(2027,1,1)-timedelta(days=i)).isoformat())]
        for r in history:
            if r['team']=='BOS':r['first_team_shot']=0;r['first_game_shot']=0;r['opening_shot_observed']=0
        for model in ('baseline','recent','lineup'):
            result,_,_,_,_=self.run_picks(history,model)
            self.assertEqual({r['status'] for r in result if r['team']=='BOS'},{'HOLD: SHOT COVERAGE'})
    def test_cli_backtest_uses_same_metrics_and_fractional_ties(self):
        import io,contextlib
        from unittest.mock import patch
        from test_research import game_rows
        import research_tools as research
        history=game_rows('only','2027-01-01')
        for model in ('baseline','recent','lineup'):
            with patch.object(eng,'read_csv',return_value=history),contextlib.redirect_stdout(io.StringIO()):
                result=eng.backtest(0,model)
            self.assertEqual(result,research.evaluate(history,0,model))
            self.assertAlmostEqual(result['metrics']['Top-1 hit %'],10)
            self.assertAlmostEqual(result['metrics']['Top-3 hit %'],30)
    def test_model_argument_reaches_shared_backtest(self):
        from unittest.mock import patch
        for model in ('baseline','recent','lineup'):
            with patch('sys.argv',['engine','backtest','--model',model,'--min-training-games','100']),patch.object(eng,'backtest') as backtest:
                eng.main()
                backtest.assert_called_once_with(100,model)
