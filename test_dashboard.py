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
