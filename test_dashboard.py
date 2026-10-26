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

class MatchupLeaderBoardTests(unittest.TestCase):
    def setUp(self):
        fixture=DashboardTests();fixture.setUp()
        self.rows=c.rank_game([],fixture.game,fixture.lineups,{}, {},[])
    def test_all_ten_tied_and_holds_preserved(self):
        board=c.matchup_leader_board(self.rows)
        self.assertEqual(len(board),1)
        self.assertEqual(board[0]['Tied leaders'],10)
        self.assertAlmostEqual(board[0]['Each leader %'],10)
        self.assertEqual(board[0]['Gap to runner-up pp'],0)
        self.assertEqual(board[0]['Leader status'],'HOLD: LINEUP')
        for row in self.rows:self.assertIn(row['Player'],board[0]['Top candidates'])
    def test_full_precision_beats_display_rounding(self):
        self.rows[0]['_probability']+=.000001
        self.rows[1]['_probability']-=.000001
        board=c.matchup_leader_board(self.rows)[0]
        self.assertEqual(board['Tied leaders'],1)
        self.assertIn(self.rows[0]['Player'],board['Top candidates'])
        self.assertAlmostEqual(board['Gap to runner-up pp'],.0001)
    def test_tied_leaders_keep_distinct_flags_without_promoting_other_player(self):
        for i,row in enumerate(self.rows):row['_probability']=.2 if i<2 else .6/8
        self.rows[0]['Status']='HOLD: SHOT COVERAGE';self.rows[1]['Status']='HOLD: SAMPLE'
        self.rows[0]['Injury']='Questionable';self.rows[1]['Injury']='Out'
        board=c.matchup_leader_board(self.rows)[0]
        self.assertEqual(board['Tied leaders'],2)
        self.assertAlmostEqual(board['Each leader %'],20)
        self.assertEqual(board['Gap to runner-up pp'],0)
        self.assertIn('HOLD: SHOT COVERAGE',board['Leader status'])
        self.assertIn('Out',board['Leader injury review'])
    def test_multiple_games_sorted_and_no_input_mutation(self):
        import copy
        other=copy.deepcopy(self.rows)
        for i,row in enumerate(other):
            row['_game_id']='espn_2';row['Matchup']='Other matchup';row['_probability']=.2 if i==0 else .8/9
        rows=self.rows+other;original=copy.deepcopy(rows)
        board=c.matchup_leader_board(rows)
        self.assertEqual(board[0]['Game'],'espn_2')
        self.assertEqual(len(board),2)
        self.assertEqual(rows,original)
    def test_invalid_groups_and_empty(self):
        import copy
        self.assertEqual(c.matchup_leader_board([]),[])
        variants=[self.rows[:-1]]
        for field,value in [('_player_id',self.rows[1]['_player_id']),('_probability',float('nan')),('_probability',.5),('Model','other'),('Team','ATL')]:
            rows=copy.deepcopy(self.rows);rows[0][field]=value;variants.append(rows)
        for rows in variants:
            with self.assertRaises(ValueError):c.matchup_leader_board(rows)


class StartingProjectionEvidenceTests(unittest.TestCase):
    def setUp(self):
        from test_research import game_rows
        self.make=game_rows
        self.players=[{'player_id':str(i),'player':f'Player {i}'} for i in range(10,17)]
    def test_recent_counts_and_latest_defaults(self):
        history=self.make('old','2026-10-20')+self.make('new','2026-10-24')
        for r in history:
            if r['game_id']=='new' and r['player_id']=='14':r['player_id']='15'
        result=c.projection_evidence(history,'BOS','2026-10-25',self.players)
        self.assertEqual(set(result['defaults']),{'10','11','12','13','15'})
        byid={r['Player ID']:r for r in result['players']}
        self.assertEqual(byid['10']['Starts in recent recorded games'],2)
        self.assertEqual(byid['14']['Selection basis'],'Review candidate')
        self.assertFalse(byid['14']['Started last recorded game'])
    def test_no_same_day_future_or_other_team_leakage(self):
        history=self.make('old','2026-10-24')+self.make('today','2026-10-25')+self.make('future','2026-10-26')
        result=c.projection_evidence(history,'BOS','2026-10-25',self.players)
        self.assertEqual(result['reviewed_games'],1)
        self.assertEqual(result['last_game_date'],'2026-10-24')
        self.assertEqual(result['history_age_days'],1)
    def test_stale_and_missing_roster_withhold_defaults(self):
        history=self.make('old','2026-09-24')
        result=c.projection_evidence(history,'BOS','2026-10-25',self.players)
        self.assertEqual(result['defaults'],[])
        self.assertTrue(any('31 days old' in w for w in result['warnings']))
        recent=self.make('new','2026-10-24')
        self.assertEqual(c.projection_evidence(recent,'BOS','2026-10-25',self.players,False)['defaults'],[])
        self.assertEqual(len(c.projection_evidence(history,'BOS','2026-10-24',self.players)['defaults']),5)
    def test_departed_player_not_replaced_silently(self):
        result=c.projection_evidence(self.make('old','2026-10-24'),'BOS','2026-10-25',self.players[1:])
        self.assertEqual(len(result['defaults']),4)
        self.assertNotIn('15',result['defaults'])
        self.assertTrue(any('absent from the loaded roster' in w for w in result['warnings']))
    def test_corrupt_latest_game_ignored(self):
        old=self.make('old','2026-10-23');bad=self.make('bad','2026-10-24')[:-1]
        result=c.projection_evidence(old+bad,'BOS','2026-10-25',self.players)
        self.assertEqual(result['last_game_date'],'2026-10-23')
        self.assertEqual(result['reviewed_games'],1)
    def test_last_five_and_sixty_day_window(self):
        history=[r for i in range(7) for r in self.make(str(i),f'2026-10-{i+1:02d}')]+self.make('ancient','2025-10-01')
        result=c.projection_evidence(history,'BOS','2026-10-25',self.players)
        self.assertEqual(result['reviewed_games'],5)
        self.assertEqual(result['players'][0]['Starts in recent recorded games'],5)
        older=c.projection_evidence(self.make('old','2026-08-01'),'BOS','2026-10-25',self.players)
        self.assertEqual(older['reviewed_games'],0)
    def test_empty_and_duplicate_roster(self):
        self.assertEqual(c.projection_evidence([],'BOS','2026-10-25',self.players)['defaults'],[])
        with self.assertRaises(ValueError):c.projection_evidence([],'BOS','2026-10-25',self.players+self.players[:1])
    def test_deterministic_no_input_mutation(self):
        import copy
        history=self.make('old','2026-10-24');before=copy.deepcopy(history)
        first=c.projection_evidence(history,'BOS','2026-10-25',self.players)
        second=c.projection_evidence(list(reversed(history)),'BOS','2026-10-25',list(reversed(self.players)))
        self.assertEqual(first['players'],second['players'])
        self.assertEqual(history,before)
        self.assertEqual(set(c.projections(history,'BOS','2026-10-25',self.players)),set(first['defaults']))
