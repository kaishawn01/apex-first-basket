import unittest
from unittest.mock import patch
from datetime import datetime,timezone
import dashboard_core as c

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.game={'gameId':'espn_1','_date':'2026-10-25','start_time':'2026-10-25T23:00:00Z','gameStatus':1,'awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
        self.lineups={t:[{'player_id':str(i+offset),'player':f'{t} Player {i}'} for i in range(5)] for t,offset in [('BOS',10),('NYK',20)]}
    def test_game_start_guard(self):
        self.assertTrue(c.upcoming(self.game,datetime(2026,10,25,22,tzinfo=timezone.utc)))
        self.assertFalse(c.upcoming(self.game,datetime(2026,10,25,23,tzinfo=timezone.utc)))
    def test_probability_and_lineup_hold(self):
        rows=c.rank_game([],self.game,self.lineups,{}, {},[])
        self.assertAlmostEqual(sum(r['Model %'] for r in rows),100)
        self.assertTrue(all(r['Status']=='HOLD: LINEUP' for r in rows))
        self.assertTrue(all(r['Model EV %'] is None for r in rows))
    def test_injury_blocks_entire_matchup(self):
        reports=[{'team':'BOS','player':'BOS Player 0','status':'Out'}]
        rows=c.rank_game([],self.game,self.lineups,{'BOS':True,'NYK':True},{},reports)
        self.assertTrue(all(r['Status']=='HOLD: INJURY REVIEW' for r in rows))
        self.assertIsNone(c.injury_for(reports,'NYK','BOS Player 0'))
    def test_duplicate_starters_rejected(self):
        self.lineups['BOS'][1]=self.lineups['BOS'][0]
        with self.assertRaises(ValueError): c.rank_game([],self.game,self.lineups,{}, {},[])
    def test_injury_pagination(self):
        responses=[{'data':[{'id':1,'abbreviation':'BOS'}]},
                   {'data':[{'player':{'first_name':'Test','last_name':'One','team_id':1},'status':'Out'}],'meta':{'next_cursor':5}},
                   {'data':[],'meta':{'next_cursor':None}}]
        with patch.object(c,'request',side_effect=responses) as req,patch.object(c.time,'sleep'):
            rows=c.injury_reports('fake')
            self.assertEqual(rows[0]['team'],'BOS')
            self.assertEqual(req.call_args_list[-1].args[1]['cursor'],5)
    def test_error_does_not_expose_key(self):
        import requests
        with patch.object(c.requests,'get',side_effect=requests.ConnectionError('secret-key')):
            with self.assertRaisesRegex(RuntimeError,'Could not reach') as err: c.request('https://example.com',{'apiKey':'secret-key'})
        self.assertNotIn('secret-key',str(err.exception))
    def test_odds_yes_only(self):
        events=[{'id':'x','home_team':'New York Knicks','away_team':'Boston Celtics','commence_time':self.game['start_time']}]
        payload={'bookmakers':[{'key':'fanduel','markets':[{'key':'player_first_basket','outcomes':[{'name':'Yes','description':'BOS Player 0','price':650},{'name':'No','description':'BOS Player 0','price':-900}]}]}]}
        with patch.object(c,'request',side_effect=[events,payload]):
            prices,_=c.live_prices('fake',[self.game])
        self.assertEqual(prices[('espn_1','bosplayer0')][0],7.5)

if __name__=='__main__': unittest.main()

class ModelComparisonTests(unittest.TestCase):
    def setUp(self):
        fixture=DashboardTests();fixture.setUp()
        self.bundle={m:c.rank_game([],fixture.game,fixture.lineups,{}, {},[],m) for m in ('baseline','recent','lineup')}
    def test_cold_start_ties_not_a_unique_pick(self):
        result=c.compare_model_forecasts(self.bundle)
        self.assertTrue(result['all_tied']);self.assertEqual(len(result['shared_top']),10)
        for row in result['rows']:
            self.assertEqual(row['Baseline rank'],1)
            self.assertAlmostEqual(row['Range (percentage points)'],0)
            self.assertEqual(row['Models ranking player top (ties included)'],3)
            self.assertEqual(row['Recorded starts'],0)
    def test_different_leaders_and_probability_spread(self):
        for model,pid in [('baseline','10'),('recent','11'),('lineup','12')]:
            for r in self.bundle[model]:r['_probability']=.2 if r['_player_id']==pid else .8/9
        result=c.compare_model_forecasts(self.bundle)
        self.assertEqual(result['shared_top'],[]);self.assertFalse(result['all_tied'])
        for row in result['rows']:
            self.assertLessEqual(row['Models ranking player top (ties included)'],1)
        top=next(r for r in result['rows'] if r['Player']=='BOS Player 0')
        self.assertEqual(top['Baseline rank'],1)
        self.assertEqual(top['Recent form rank'],2)
        self.assertAlmostEqual(top['Range (percentage points)'],100*(.2-.8/9))
    def test_mismatched_game_players_and_bad_probability_rejected(self):
        import copy
        for field,value in [('_game_id','other'),('_player_id','other'),('_probability',float('nan')),('Model','baseline')]:
            bundle=copy.deepcopy(self.bundle);bundle['recent'][0][field]=value
            with self.assertRaises(ValueError):c.compare_model_forecasts(bundle)
    def test_full_precision_and_no_mutation(self):
        import copy
        self.bundle['baseline'][0]['_probability']+=.000001
        self.bundle['baseline'][1]['_probability']-=.000001
        original=copy.deepcopy(self.bundle)
        result=c.compare_model_forecasts(self.bundle)
        self.assertEqual(result['leaders'][0]['Players tied at top'],1)
        self.assertEqual(self.bundle,original)

class ShotCoverageGuardTests(unittest.TestCase):
    def setUp(self):
        from test_research import game_rows
        from datetime import date,timedelta
        fixture=DashboardTests();fixture.setUp()
        self.game=fixture.game;self.lineups=fixture.lineups
        self.history=[r for i in range(12) for r in game_rows(str(i),(date(2026,10,24)-timedelta(days=i)).isoformat())]
    def make_unknown(self,keep):
        for row in self.history:
            if row['team']=='BOS' and int(row['game_id'])>=keep:
                row['first_team_shot']=0;row['first_game_shot']=0;row['opening_shot_observed']=0
    def rank(self,model='baseline',confirmed=None,reports=None,game=None):
        return c.rank_game(self.history,game or self.game,self.lineups,{'BOS':True,'NYK':True} if confirmed is None else confirmed,{},reports or [],model)
    def test_many_starts_with_sparse_shots_are_held_in_all_models(self):
        self.make_unknown(2)
        for model in ('baseline','recent','lineup'):
            rows=self.rank(model)
            bos=[r for r in rows if r['Team']=='BOS']
            self.assertTrue(all(r['Status']=='HOLD: SHOT COVERAGE' for r in bos))
            self.assertTrue(all(r['Starts']==12 and r['Observed opening-shot starts']==2 for r in bos))
            self.assertTrue(all(r['Status']=='NO PRICE' for r in rows if r['Team']=='NYK'))
    def test_raw_eight_passes_baseline_but_decayed_eight_does_not(self):
        self.make_unknown(8)
        baseline=self.rank();recent=self.rank('recent')
        self.assertTrue(all(r['Status']=='NO PRICE' for r in baseline))
        for row in recent:
            if row['Team']=='BOS':
                self.assertEqual(row['Status'],'HOLD: SHOT COVERAGE')
                self.assertLess(row['Weighted observed shot starts'],8)
                self.assertIn('decayed',row['Shot coverage note'])
    def test_higher_priority_holds_and_research_notes_preserved(self):
        self.make_unknown(0)
        self.assertTrue(all(r['Status']=='HOLD: LINEUP' for r in self.rank(confirmed={})))
        reports=[{'team':'NYK','player':'NYK Player 0','status':'Out'}]
        self.assertTrue(all(r['Status']=='HOLD: INJURY REVIEW' for r in self.rank(reports=reports)))
        rows=self.rank(game={**self.game,'research_only':True})
        self.assertTrue(all(r['Status']=='RESEARCH MATCHUP' for r in rows))
        self.assertTrue(all('Below 8' in r['Shot coverage note'] for r in rows if r['Team']=='BOS'))
    def test_guard_never_changes_probabilities(self):
        import first_basket_engine as eng
        self.make_unknown(2)
        for model in ('baseline','recent','lineup'):
            expected=eng.predict_first_score(self.history,self.lineups,self.game['_date'],model)
            self.assertEqual({r['_player_id']:r['_probability'] for r in self.rank(model)},expected)
    def test_coverage_holds_count_in_journal_without_regrading(self):
        import research_tools as rt
        self.make_unknown(2)
        for model in ('baseline','recent','lineup'):
            rows=self.rank(model)
            record={'snapshot':{'game_id':self.game['gameId'],'date':self.game['_date'],'model_version':'2.20.0','model':model,'saved_at':'test','rows':rows},'outcome':None}
            self.assertEqual(rt.journal_table([record])[0]['Sample holds'],5)
