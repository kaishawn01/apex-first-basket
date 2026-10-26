import unittest
import tempfile
import math
from pathlib import Path
from unittest.mock import patch
import first_basket_engine as eng
import research_tools as rt


def game_rows(gid,day):
    rows=[]
    for team,opp,offset in [('BOS','NYK',10),('NYK','BOS',20)]:
        for i in range(5):
            rows.append({'game_id':gid,'date':day,'team':team,'opponent':opp,'player_id':str(offset+i),'player':f'{team} Player {i}',
                         'first_team_shot':int(i==0),'first_game_shot':int(team=='BOS' and i==0),'first_scorer':int(team=='BOS' and i==0),'first_fg_scorer':int(team=='BOS' and i==0),'team_scored_first':int(team=='BOS'),'tip_first_action':int(team=='BOS')})
    return rows


class ResearchTests(unittest.TestCase):
    def test_audit_accepts_and_detects_duplicate(self):
        rows=game_rows('one','2026-10-20')
        self.assertEqual(len(rt.audit(rows)[0]),10)
        rows[1]['player_id']=rows[0]['player_id']
        self.assertEqual(len(rt.audit(rows)[1]),1)
    def test_inconsistent_winning_team(self):
        rows=game_rows('one','2026-10-20');rows[-1]['team_scored_first']=1
        self.assertEqual(len(rt.audit(rows)[1]),1)
    def test_window_excludes_future_same_day_and_old(self):
        rows=[{'date':d} for d in ('2024-01-01','2026-10-24','2026-10-25','2026-10-26')]
        self.assertEqual(rt.history_window(rows,'2026-10-25'),[{'date':'2026-10-24'}])
    def test_walk_forward_no_same_day_leakage(self):
        rows=game_rows('a','2026-10-20')+game_rows('b','2026-10-21')+game_rows('c','2026-10-21')
        seen=[]
        original=eng.team_stats
        def spy(train):
            seen.append({r['date'] for r in train});return original(train)
        with patch.object(eng,'team_stats',side_effect=spy): result=rt.evaluate(rows,1)
        self.assertEqual(result['metrics']['Evaluated games'],2)
        self.assertEqual(seen,[{'2026-10-20'}])
    def test_equal_model_baseline_and_ties(self):
        rows=game_rows('a','2026-10-20')+game_rows('b','2026-10-21')
        def equal(history,players,team,shot_weight=.65):return [(p,.2,0,0,0) for p in players]
        with patch.object(eng,'first_team_probability',return_value=.5),patch.object(eng,'player_weights',side_effect=equal):
            result=rt.evaluate(rows,1)
        self.assertAlmostEqual(result['metrics']['Log loss'],math.log(10))
        self.assertAlmostEqual(result['metrics']['Brier'],.9)
        self.assertAlmostEqual(result['metrics']['Top-1 hit %'],10)
    def test_import_resume_and_preserve(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);path=folder/'history.csv'
            old=game_rows('espn_1','2025-11-01')
            eng.write_csv(path,eng.FIELDS,old)
            games=[{'gameId':f'espn_{i}','_date':f'2025-11-0{i}','gameStatus':3} for i in (1,2,3)]
            with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt,'season_index',return_value=(games,[])),patch.object(rt.core,'request',return_value={}),patch.object(eng,'validate_espn_summary'),patch.object(eng,'espn_game_payloads',return_value=({},{})),patch.object(eng,'extract_game',side_effect=lambda g,p,b:game_rows(g['gameId'],g['_date'])):
                first=rt.import_season(2026,1)
                second=rt.import_season(2026,1)
                third=rt.import_season(2026,1)
                self.assertEqual([first['added'],second['added'],third['added']],[1,1,0])
                self.assertEqual(len(eng.read_csv(path)),30)
                self.assertEqual(len(eng.read_csv(folder/'history_before_prior_season.csv')),10)
    def test_failed_import_preserves_history_and_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);path=folder/'history.csv';eng.write_csv(path,eng.FIELDS,game_rows('espn_1','2025-11-01'))
            before=path.read_bytes()
            with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt,'season_index',return_value=([{'gameId':'espn_2','_date':'2025-11-02','gameStatus':3}],[])),patch.object(rt.core,'request',side_effect=RuntimeError('Offline')):
                report=rt.import_season(2026,1)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(len(report['skipped']),1)
            self.assertEqual(report['remaining'],1)


class ForwardJournalTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime,timezone
        import dashboard_core as core
        self.now=datetime(2026,10,25,22,tzinfo=timezone.utc)
        self.game={'gameId':'espn_123','_date':'2026-10-25','start_time':'2026-10-25T23:00:00Z','gameStatus':1,'awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
        self.players={t:[{'player_id':str(offset+i),'player':f'{t} Player {i}'} for i in range(5)] for t,offset in [('BOS',10),('NYK',20)]}
        self.rows=core.rank_game([],self.game,self.players,{'BOS':True,'NYK':True},{},[])
    def save(self,path,**kwargs):
        return rt.save_forecast(self.game,self.rows,{'BOS':True,'NYK':True},'2.3.0','testhash',path=path,now=kwargs.get('now',self.now))
    def payload(self,winner='10',free=False,completed=True):
        teams=[{'homeAway':ha,'team':{'id':tid,'abbreviation':code}} for ha,tid,code in [('away','1','BOS'),('home','2','NYK')]]
        boxes=[]
        for tid,code in [('1','BOS'),('2','NYK')]:
            people=self.players[code]+([{'player_id':'99','player':'Bench Scorer'}] if code=='BOS' else [])
            boxes.append({'team':{'id':tid},'statistics':[{'athletes':[{'athlete':{'id':p['player_id'],'displayName':p['player']},'starter':p['player_id']!='99'} for p in people]}]})
        return {'header':{'id':'123','competitions':[{'id':'123','status':{'type':{'completed':completed}},'competitors':teams}]},'boxscore':{'players':boxes},'plays':[{'period':{'number':1},'sequenceNumber':'1','text':'Player makes free throw' if free else 'Player makes layup','shootingPlay':True,'scoringPlay':True,'scoreValue':1 if free else 2,'team':{'id':'1'},'participants':[{'athlete':{'id':winner}}]}]}
    def test_immutable_forecast_and_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.sqlite'
            self.assertTrue(self.save(path));self.rows[0]['Player']='Edited'
            self.assertFalse(self.save(path))
            record=rt.journal_records(path)[0]
            self.assertNotEqual(record['snapshot']['rows'][0]['Player'],'Edited')
            self.assertAlmostEqual(sum(r['_probability'] for r in record['snapshot']['rows']),1)
    def test_reject_after_tip(self):
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):self.save(Path(tmp)/'j',now=self.now+timedelta(hours=2))
    def test_require_confirmed_lineups(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):rt.save_forecast(self.game,self.rows,{},'2.3.0','hash',path=Path(tmp)/'j',now=self.now)
    def test_free_throw_counts_and_tie_credit(self):
        snapshot={'game_id':'espn_123','rows':self.rows}
        out=rt.outcome_from_summary(snapshot,self.payload(free=True))
        self.assertEqual(out['winner_id'],'10');self.assertEqual(out['score_type'],'Free throw')
        self.assertTrue(out['lineup_matches']);self.assertAlmostEqual(out['top1_credit'],.1)
    def test_nonstarter_winner_retained(self):
        out=rt.outcome_from_summary({'game_id':'espn_123','rows':self.rows},self.payload(winner='99'))
        self.assertTrue(out['outside_field']);self.assertEqual(out['top1_credit'],0)
        self.assertIsNone(out['log_loss']);self.assertAlmostEqual(out['brier'],1.1)
        stats=rt.journal_summary([{'outcome':out}])
        self.assertEqual(stats['Settled games'],1);self.assertIn('Infinite',stats['Log loss'])
    def test_not_final_stays_pending(self):
        self.assertIsNone(rt.outcome_from_summary({'game_id':'espn_123','rows':self.rows},self.payload(completed=False)))
    def test_wrong_game_rejected(self):
        with self.assertRaises(ValueError):rt.outcome_from_summary({'game_id':'espn_other','rows':self.rows},self.payload())
    def test_refresh_once_and_errors_preserve_pending(self):
        self.game['_date']='2025-10-25'
        self.game['start_time']='2025-10-25T23:00:00Z'
        self.now=self.now.replace(year=2025)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'j';self.save(path)
            with patch.object(rt.core,'request',side_effect=RuntimeError('Offline')):
                n,errors=rt.refresh_journal(path)
                self.assertEqual(n,0);self.assertEqual(len(errors),1)
            with patch.object(rt.core,'request',return_value=self.payload()) as req:
                self.assertEqual(rt.refresh_journal(path)[0],1)
                self.assertEqual(rt.refresh_journal(path)[0],0)
                self.assertEqual(req.call_count,1)

class RecentModelTests(unittest.TestCase):
    def setUp(self):
        self.players=[{'player_id':str(10+i),'player':f'BOS Player {i}'} for i in range(5)]
    def test_new_players_uniform_and_matchup_symmetric(self):
        shares=eng.recent_player_weights([],self.players,'BOS','2026-10-25')
        self.assertTrue(all(abs(r[1]-.2)<1e-12 for r in shares))
        stats={'BOS':{'first':.6},'NYK':{'first':.4}}
        self.assertAlmostEqual(eng.recent_first_team_probability('BOS','NYK',stats)+eng.recent_first_team_probability('NYK','BOS',stats),1)
    def test_recent_game_gets_more_weight(self):
        old=game_rows('old','2026-01-01');new=game_rows('new','2026-10-24')
        # Old game involved player 0; recent game involved player 1.
        for r in new:
            if r['team']=='BOS':
                r['first_team_shot']=int(r['player_id']=='11')
                r['first_scorer']=int(r['player_id']=='11')
        result={r[0]['player_id']:r for r in eng.recent_player_weights(old+new,self.players,'BOS','2026-10-25')}
        self.assertGreater(result['11'][1],result['10'][1])
        self.assertAlmostEqual(sum(r[1] for r in result.values()),1)
    def test_same_day_and_future_excluded(self):
        rows=game_rows('today','2026-10-25')+game_rows('future','2026-10-26')
        self.assertEqual(eng.recent_team_stats(rows,'2026-10-25'),{})
        self.assertTrue(all(r[5]==0 for r in eng.recent_player_weights(rows,self.players,'BOS','2026-10-25')))
    def test_score_share_is_conditional_on_team_first(self):
        rows=game_rows('a','2026-10-24')
        # Opponent-first games increase shot exposures but not team-first scoring opportunities.
        opponent=game_rows('b','2026-10-24')
        for r in opponent:
            r['team_scored_first']=int(r['team']=='NYK')
            r['first_scorer']=int(r['team']=='NYK' and r['player_id']=='20')
        before=eng.recent_player_weights(rows,self.players,'BOS','2026-10-25')[0][7]
        after=eng.recent_player_weights(rows+opponent,self.players,'BOS','2026-10-25')[0][7]
        self.assertAlmostEqual(before,after)
    def test_comparison_uses_identical_holdouts(self):
        from datetime import date,timedelta
        rows=[r for i in range(6) for r in game_rows(str(i),(date(2026,10,15)+timedelta(days=i)).isoformat())]
        base=rt.evaluate(rows,2,'baseline');recent=rt.evaluate(rows,2,'recent')
        self.assertEqual([r['Game'] for r in base['games']],[r['Game'] for r in recent['games']])
        self.assertEqual([r['Training games'] for r in base['games']],[r['Training games'] for r in recent['games']])
    def test_research_matchup_no_odds_no_journal(self):
        import dashboard_core as core
        from datetime import datetime,timezone
        game={'gameId':'research_test','_date':'2026-10-25','start_time':'2026-10-25T23:00:00Z','gameStatus':0,'research_only':True,'awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
        lineups={'BOS':self.players,'NYK':[{'player_id':str(20+i),'player':f'NYK Player {i}'} for i in range(5)]}
        rows=core.rank_game([],game,lineups,{}, {('research_test','bosplayer0'):(7.5,'650','test','')},[],model='recent')
        self.assertAlmostEqual(sum(r['_probability'] for r in rows),1)
        self.assertTrue(all(r['Status']=='RESEARCH MATCHUP' and r['Book odds']=='' and r['Model EV %'] is None for r in rows))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Research matchups'):
                rt.save_forecast(game,rows,{'BOS':True,'NYK':True},'2.4.0','hash',path=Path(tmp)/'j',now=datetime(2026,10,25,22,tzinfo=timezone.utc))

if __name__=='__main__':unittest.main()


class SharedPredictionTests(unittest.TestCase):
    def test_dashboard_matches_shared_engine_both_models(self):
        rows=game_rows('one','2026-10-20')
        lineups={t:[r for r in rows if r['team']==t] for t in ('NYK','BOS')}
        game={'gameId':'future','_date':'2026-10-21','awayTeam':{'teamTricode':'NYK'},'homeTeam':{'teamTricode':'BOS'}}
        for model in ('baseline','recent','lineup'):
            probs=eng.predict_first_score(rows,lineups,'2026-10-21',model)
            ranked=rt.core.rank_game(rows,game,lineups,{}, {},[],model)
            self.assertAlmostEqual(sum(probs.values()),1)
            for r in ranked:self.assertAlmostEqual(r['_probability'],probs[r['_player_id']])
    def test_shared_engine_ignores_same_day_future_and_old(self):
        history=game_rows('one','2026-10-20')
        lineups={t:[r for r in history if r['team']==t] for t in ('BOS','NYK')}
        contaminated=history+game_rows('same','2026-10-21')+game_rows('future','2026-10-22')+game_rows('old','2020-01-01')
        for model in ('baseline','recent','lineup'):
            self.assertEqual(eng.predict_first_score(history,lineups,'2026-10-21',model),eng.predict_first_score(contaminated,lineups,'2026-10-21',model))
    def test_backtest_probability_matches_shared_engine(self):
        history=game_rows('one','2026-10-20');next_game=game_rows('two','2026-10-21')
        lineups={t:[r for r in next_game if r['team']==t] for t in ('BOS','NYK')}
        for model in ('baseline','recent','lineup'):
            result=rt.evaluate(history+next_game,1,model)
            self.assertAlmostEqual(result['games'][0]['Winner probability'],eng.predict_first_score(history,lineups,'2026-10-21',model)['10'])
    def test_top_three_ties(self):
        self.assertAlmostEqual(rt.top_k_credit({str(i):.1 for i in range(10)},'0',3),.3)
        self.assertAlmostEqual(rt.top_k_credit({'a':.5,'b':.2,'c':.1,'d':.1,'e':.1},'c',3),1/3)
        self.assertEqual(rt.top_k_credit({'a':.5},'absent',3),0)
    def test_paired_intervals_identical_and_constant_difference(self):
        rows=[{'Game':str(i),'Date':f'2026-10-{20+i//2}','Log loss':2.,'Brier':.9,'Top-1 credit':0.,'Top-3 credit':0.} for i in range(6)]
        a={'games':rows}
        same=rt.compare_evaluations(a,a,100)
        self.assertEqual(same['dates'],3)
        self.assertTrue(all(m['95% lower']==m['95% upper']==0 for m in same['metrics']))
        b={'games':[{**r,'Log loss':1.5} for r in rows]}
        diff=rt.compare_evaluations(a,b,100)['metrics'][0]
        self.assertEqual(diff['Candidate minus baseline'],-.5)
        self.assertEqual(diff['95% lower'],-.5)
        self.assertEqual(diff['95% upper'],-.5)
        with self.assertRaises(ValueError):rt.compare_evaluations(a,{'games':rows[:-1]})
    def test_paired_one_date_has_no_interval(self):
        r={'Game':'x','Date':'2026-10-20','Log loss':2.,'Brier':.9,'Top-1 credit':0.,'Top-3 credit':0.}
        result=rt.compare_evaluations({'games':[r]},{'games':[r]},100)
        self.assertTrue(all(m['95% lower'] is None for m in result['metrics']))

class LineupContextTests(unittest.TestCase):
    def setUp(self):
        self.rows=game_rows('one','2026-10-20')
        self.players=[r.copy() for r in self.rows if r['team']=='BOS']
    def test_exact_five_and_four_player_context_weights(self):
        exact=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        self.assertTrue(all(r[8]==1 for r in exact))
        expected=2**(-1/90)
        self.assertAlmostEqual(exact[0][9],expected)
        changed=[dict(p) for p in self.players];changed[-1]['player_id']='new'
        four=eng.lineup_player_weights(self.rows,changed,'BOS','2026-10-21')
        self.assertAlmostEqual(four[0][9],expected/2)
        self.assertEqual(four[-1][8],0)
        self.assertEqual(four[-1][9],0)
    def test_unfamiliar_five_falls_back_to_recent(self):
        changed=[dict(p) for p in self.players]
        for i in (3,4):changed[i]['player_id']='new'+str(i)
        context=eng.lineup_player_weights(self.rows,changed,'BOS','2026-10-21')
        recent=eng.recent_player_weights(self.rows,changed,'BOS','2026-10-21')
        for a,b in zip(context,recent):
            self.assertAlmostEqual(a[1],b[1]);self.assertEqual(a[8],0)
    def test_exact_context_only_does_not_amplify_recent_evidence(self):
        recent=eng.recent_player_weights(self.rows,self.players,'BOS','2026-10-21')
        context=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        self.assertAlmostEqual(context[0][1],recent[0][1])
        self.assertGreater(context[0][1],context[1][1])
        self.assertTrue(all(r[10]==0 and r[11]==0 for r in context))
        self.assertAlmostEqual(sum(r[1] for r in context),1)
    def test_new_lineup_context_excludes_same_day_future_other_team(self):
        expected=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        added=self.rows+game_rows('same','2026-10-21')+game_rows('future','2026-10-22')+game_rows('old','2020-01-01')
        self.assertEqual(expected,eng.lineup_player_weights(added,self.players,'BOS','2026-10-21'))
    def test_order_independence(self):
        a=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        b=eng.lineup_player_weights(list(reversed(self.rows)),list(reversed(self.players)),'BOS','2026-10-21')
        self.assertEqual({r[0]['player_id']:r[1] for r in a},{r[0]['player_id']:r[1] for r in b})

    def test_disjoint_anchor_and_context_match_manual_formula(self):
        other=game_rows('other','2026-10-19')
        # Three current teammates: this game belongs only to the anchor.
        for row in other:
            if row['team']=='BOS' and row['player_id'] in ('13','14'):
                row['player_id']='8'+row['player_id']
        for row in other:
            if row['team']=='BOS':
                for field in ('first_team_shot','first_game_shot','first_scorer','first_fg_scorer'):
                    row[field]=int(row['player_id']=='11')
        anchor=eng.recent_player_weights(other,self.players,'BOS','2026-10-21')
        result=eng.lineup_player_weights(self.rows+other,self.players,'BOS','2026-10-21')
        w=2**(-1/90)
        expected=[]
        for i,a in enumerate(anchor):
            shot=(w*int(i==0)+10*a[6])/(w+10)
            score=(w*int(i==0)+5*a[7])/(w+5)
            expected.append(.65*shot+.35*score)
            self.assertAlmostEqual(result[i][6],shot)
            self.assertAlmostEqual(result[i][7],score)
            self.assertEqual(result[i][10],1 if i<3 else 0)
            self.assertEqual(result[i][2],result[i][8]+result[i][10])
        for row,weight in zip(result,expected):
            self.assertAlmostEqual(row[1],weight/sum(expected))
    def test_four_teammates_downweights_context_without_reusing_it(self):
        changed=[dict(p) for p in self.players];changed[-1]['player_id']='99'
        result=eng.lineup_player_weights(self.rows,changed,'BOS','2026-10-21')
        w=2**(-1/90)/2
        self.assertAlmostEqual(result[0][6],(w+2)/(w+10))
        self.assertAlmostEqual(result[0][7],(w+1)/(w+5))
        self.assertAlmostEqual(result[-1][6],.2)
        self.assertEqual(result[0][10],0)
    def test_no_context_keeps_full_recent_anchor_counts(self):
        changed=[dict(p) for p in self.players]
        for i in (3,4):changed[i]['player_id']='new'+str(i)
        result=eng.lineup_player_weights(self.rows,changed,'BOS','2026-10-21')
        self.assertEqual(result[0][10],1)
        self.assertAlmostEqual(result[0][11],2**(-1/90))
        self.assertEqual(result[0][8],0)

class LineupScenarioTests(unittest.TestCase):
    def setUp(self):
        self.history=game_rows('old','2026-10-20')
        self.lineups={t:[r.copy() for r in self.history if r['team']==t] for t in ('BOS','NYK')}
        self.roster=self.lineups['BOS']+[{'player_id':'99','player':'Replacement'}]
        self.game={'gameId':'test','_date':'2026-10-21','awayTeam':{'teamTricode':'BOS'},'homeTeam':{'teamTricode':'NYK'}}
    def test_scenario_normalization_immutability_and_model_parity(self):
        import copy
        saved=copy.deepcopy(self.lineups)
        for model in ('baseline','recent','lineup'):
            result=rt.core.compare_lineup_swap(self.history,self.game,self.lineups,'BOS','10','99',self.roster,[],model)
            self.assertTrue(result['research_only'])
            self.assertEqual(len(result['rows']),11)
            self.assertAlmostEqual(sum(r['Before %'] or 0 for r in result['rows']),100)
            self.assertAlmostEqual(sum(r['After %'] or 0 for r in result['rows']),100)
            self.assertEqual(self.lineups,saved)
            removed=next(r for r in result['rows'] if r['Scenario role']=='Removed starter')
            incoming=next(r for r in result['rows'] if r['Scenario role']=='Replacement')
            self.assertIsNone(removed['After %']);self.assertIsNone(incoming['Before %'])
            self.assertIsNone(incoming['Change (percentage points)'])
            self.assertFalse(any('odds' in k.lower() or 'ev' in k.lower() for r in result['rows'] for k in r))
            alternate=copy.deepcopy(self.lineups);alternate['BOS'][0]=self.roster[-1]
            expected=eng.predict_first_score(self.history,alternate,'2026-10-21',model)
            self.assertAlmostEqual(incoming['After %'],100*expected['99'])
    def test_invalid_swap_rejected(self):
        for outgoing,incoming in [('missing','99'),('10','20'),('10','11'),('10','unknown')]:
            with self.assertRaises(ValueError):rt.core.compare_lineup_swap(self.history,self.game,self.lineups,'BOS',outgoing,incoming,self.roster,[])
    def test_opponent_unchanged_and_injury_flag_retained(self):
        reports=[{'team':'BOS','player':'Replacement','status':'Out','description':'Test report'}]
        result=rt.core.compare_lineup_swap(self.history,self.game,self.lineups,'BOS','10','99',self.roster,reports,'lineup')
        for r in result['rows']:
            if r['Team']=='NYK':self.assertAlmostEqual(r['Change (percentage points)'],0)
        self.assertEqual(next(r['Injury'] for r in result['rows'] if r['Player']=='Replacement'),'Out')

class MultiModelJournalTests(unittest.TestCase):
    def setUp(self):
        import copy
        ForwardJournalTests.setUp(self)
        self.bundle={m:[{**copy.deepcopy(r),'Model':m} for r in self.rows] for m in ('baseline','recent','lineup')}
        for r in self.bundle['recent']:r['_probability']=.2 if r['_player_id']=='10' else .8/9
    def save_bundle(self,path,bundle=None):
        return rt.save_forecast(self.game,self.rows,{'BOS':True,'NYK':True},'2.8.0','history',path=path,now=self.now,model_forecasts=self.bundle if bundle is None else bundle)
    def record(self):
        return {'snapshot':{'game_id':'espn_123','model':'baseline','rows':self.rows,'model_forecasts':self.bundle,'model_version':'2.8.0','date':'2026-10-25','saved_at':self.now.isoformat()},'outcome':None}
    def test_atomic_immutable_bundle(self):
        import copy
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal';self.assertTrue(self.save_bundle(path))
            saved=copy.deepcopy(rt.journal_records(path))
            self.bundle['recent'][0]['Player']='Edited'
            self.assertFalse(self.save_bundle(path))
            self.assertEqual(saved,rt.journal_records(path))
            self.assertEqual(set(saved[0]['snapshot']['model_forecasts']),{'baseline','recent','lineup'})
    def test_bundle_identity_probability_and_primary_checks(self):
        import copy
        variants=[]
        bad=copy.deepcopy(self.bundle);bad.pop('lineup');variants.append(bad)
        bad=copy.deepcopy(self.bundle);bad['recent'][0]['_player_id']='wrong';variants.append(bad)
        bad=copy.deepcopy(self.bundle);bad['recent'][0]['_probability']=float('nan');variants.append(bad)
        bad=copy.deepcopy(self.bundle);bad['recent'][0]['_research_only']=True;variants.append(bad)
        bad=copy.deepcopy(self.bundle);bad['baseline'][0]['_probability']+=.01;bad['baseline'][1]['_probability']-=.01;variants.append(bad)
        with tempfile.TemporaryDirectory() as tmp:
            for bundle in variants:
                with self.assertRaises(ValueError):self.save_bundle(Path(tmp)/'journal',bundle)
            self.assertFalse((Path(tmp)/'journal').exists())
    def test_models_scored_from_saved_probabilities(self):
        record=self.record()
        record['outcome']=rt.outcome_from_summary(record['snapshot'],ForwardJournalTests.payload(self))
        with patch.object(eng,'predict_first_score',side_effect=AssertionError('Never rerun model to grade')):
            recent=rt.journal_model_records([record],'recent')[0]
            comparison=rt.forward_model_comparison([record])
        self.assertAlmostEqual(recent['outcome']['winner_probability'],.2)
        self.assertAlmostEqual(recent['outcome']['log_loss'],-math.log(.2))
        self.assertEqual(recent['outcome']['top1_credit'],1)
        self.assertEqual([r['Settled games'] for r in comparison['summary']],[1,1,1])
        self.assertEqual(len(comparison['details']),3)
    def test_old_records_not_backfilled_or_compared(self):
        old=self.record();old['snapshot'].pop('model_forecasts')
        self.assertEqual(rt.journal_model_records([old],'recent'),[])
        compared=rt.forward_model_comparison([old,self.record()])
        self.assertEqual(compared['matched_games'],1);self.assertEqual(compared['excluded_games'],1)
        self.assertEqual([r['Pending games'] for r in compared['summary']],[1,1,1])
    def test_outside_field_loss_retained_for_every_model(self):
        record=self.record();record['outcome']=rt.outcome_from_summary(record['snapshot'],ForwardJournalTests.payload(self,winner='99'))
        comparison=rt.forward_model_comparison([record])
        for r in comparison['summary']:
            self.assertEqual(r['Outside-field winners'],1)
            self.assertIn('Infinite',r['Log loss'])
            self.assertEqual(r['Top-1 hit %'],0)

    def test_forward_reliability_uses_saved_models_without_mutating_records(self):
        import copy
        record=self.record();record['outcome']=rt.outcome_from_summary(record['snapshot'],ForwardJournalTests.payload(self))
        original=copy.deepcopy(record)
        with patch.object(eng,'predict_matchups',side_effect=AssertionError('No prediction rerun')):
            result=rt.forward_model_comparison([record,self.record()])
        self.assertEqual(record,original)
        for model in ('baseline','recent','lineup'):
            bands=[r for r in result['pick_reliability'] if r['Model']==model and r['Group by']=='Top probability']
            self.assertEqual(sum(r['Games'] for r in bands),1)
        recent=next(r for r in result['pick_reliability'] if r['Model']=='recent' and r['Group by']=='Top probability')
        self.assertAlmostEqual(recent['Mean top probability %'],20)
        self.assertEqual(recent['Observed top-1 hit %'],100)
        baseline=next(r for r in result['pick_reliability'] if r['Model']=='baseline' and r['Group by']=='Top probability')
        self.assertEqual(baseline['Tied-leader games'],1)
        self.assertAlmostEqual(baseline['Observed top-1 hit %'],10)
    def test_forward_reliability_keeps_outside_winners_and_lineup_mismatches(self):
        record=self.record();record['outcome']=rt.outcome_from_summary(record['snapshot'],ForwardJournalTests.payload(self,winner='99'))
        record['outcome']['lineup_matches']=False
        for band in rt.forward_model_comparison([record])['pick_reliability']:
            self.assertEqual(band['Games'],1)
            self.assertEqual(band['Outside-field winners'],1)
            self.assertEqual(band['Lineup mismatches'],1)
            self.assertEqual(band['Observed top-1 hit %'],0)
    def test_forward_reliability_excludes_pending_and_legacy(self):
        old=self.record();old['snapshot'].pop('model_forecasts')
        old['outcome']=rt.outcome_from_summary(old['snapshot'],ForwardJournalTests.payload(self))
        self.assertEqual(rt.forward_model_comparison([old,self.record()])['pick_reliability'],[])
        self.assertEqual(rt.forward_model_comparison([])['pick_reliability'],[])

class PlayerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rows=game_rows('one','2026-10-20')
        self.five=[r for r in self.rows if r['team']=='BOS']
    def test_raw_counts_and_conditional_denominators(self):
        result=rt.player_evidence(self.rows,'2026-10-21','BOS','10',self.five)
        stats=result['summary'][-1]
        self.assertEqual(stats['Starts'],1);self.assertEqual(stats['Team opening shots'],1)
        self.assertEqual(stats['Game first scores'],1)
        self.assertEqual(stats['Share when team scored first %'],100)
        self.assertEqual(result['days_since_last_start'],1)
        nyk=[r for r in self.rows if r['team']=='NYK']
        stats=rt.player_evidence(self.rows,'2026-10-21','NYK','20',nyk)['summary'][-1]
        self.assertEqual(stats['First-score rate %'],0)
        self.assertIsNone(stats['Share when team scored first %'])
    def test_windows_and_no_future_leakage(self):
        from datetime import date,timedelta
        target=date(2026,10,21)
        rows=[r for i in range(1,36) for r in game_rows(str(i),(target-timedelta(days=i)).isoformat())]
        rows+=game_rows('same',target.isoformat())+game_rows('future',(target+timedelta(days=1)).isoformat())
        rows+=game_rows('old',(target-timedelta(days=401)).isoformat())
        result=rt.player_evidence(rows,target.isoformat(),'BOS','10',self.five)
        self.assertEqual([r['Starts'] for r in result['summary']],[10,30,35])
        self.assertEqual(len(result['games']),35)
        self.assertEqual(result['games'][0]['Date'],'2026-10-20')
    def test_empty_sample_rates_are_missing_not_zero(self):
        result=rt.player_evidence([],'2026-10-21','BOS','10',self.five)
        self.assertIsNone(result['last_start'])
        self.assertIsNone(result['summary'][0]['First-score rate %'])
        self.assertEqual(result['games'],[])
    def test_previous_team_starts_not_used(self):
        transferred=game_rows('other','2026-10-19')
        for r in transferred:
            if r['team']=='BOS':r['team']='CHI'
            if r['opponent']=='BOS':r['opponent']='CHI'
        result=rt.player_evidence(self.rows+transferred,'2026-10-21','BOS','10',self.five)
        self.assertEqual(result['other_team_starts'],1)
        self.assertEqual(result['summary'][-1]['Starts'],1)
    def test_similar_lineup_and_invalid_input(self):
        changed=[dict(p) for p in self.five];changed[-1]['player_id']='new'
        result=rt.player_evidence(self.rows,'2026-10-21','BOS','10',changed)
        self.assertEqual(result['games'][0]['Selected starters in this game'],4)
        self.assertEqual(result['summary'][0]['Similar-lineup starts'],1)
        changed[-2]['player_id']='new2'
        self.assertEqual(rt.player_evidence(self.rows,'2026-10-21','BOS','10',changed)['summary'][0]['Similar-lineup starts'],0)
        with self.assertRaises(ValueError):rt.player_evidence(self.rows,'2026-10-21','BOS','absent',self.five)
        bad=[dict(r) for r in self.rows];bad[0]['first_scorer']=0
        with self.assertRaises(ValueError):rt.player_evidence(bad,'2026-10-21','BOS','10',self.five)

class OpeningDataIntegrityTests(unittest.TestCase):
    def test_conflicting_opening_flags_rejected(self):
        mutations=[('first_team_shot',1),('first_game_shot',1),('first_fg_scorer',1),('tip_first_action',0)]
        for field,value in mutations:
            rows=game_rows('test','2026-10-20');rows[1][field]=value
            self.assertTrue(rt.audit(rows)[1],field)
        rows=game_rows('test','2026-10-20')
        for r in rows:r['tip_first_action']=1
        self.assertTrue(rt.audit(rows)[1])
    def test_game_shooter_requires_team_opening_flag(self):
        rows=game_rows('test','2026-10-20');rows[0]['first_team_shot']=0
        self.assertTrue(rt.audit(rows)[1])
    def test_absent_starter_shot_flags_and_unknown_proxy_are_allowed(self):
        rows=game_rows('test','2026-10-20')
        for r in rows:
            for field in ('first_team_shot','first_game_shot','first_fg_scorer','tip_first_action'):r[field]=0
        self.assertEqual(rt.audit(rows)[1],[])
    def test_unknown_proxy_not_counted_as_possession_loss(self):
        known=game_rows('known','2026-10-20')
        unknown=game_rows('unknown','2026-10-19')
        for r in unknown:r['tip_first_action']=0
        before=eng.team_stats(known);after=eng.team_stats(known+unknown)
        for team in ('BOS','NYK'):
            self.assertEqual(after[team]['n'],2)
            self.assertEqual(after[team]['proxy_games'],1)
            self.assertAlmostEqual(before[team]['tip_proxy'],after[team]['tip_proxy'])
            self.assertEqual(eng.team_stats(unknown)[team]['tip_proxy'],.5)
    def test_mismatched_summary_sync_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);history=folder/'history.csv'
            eng.write_csv(history,eng.FIELDS,game_rows('old','2026-10-19'))
            previous=history.read_bytes()
            game={'gameId':'espn_123','_date':'2026-10-20','gameStatus':3,'homeTeam':{'teamTricode':'BOS'},'awayTeam':{'teamTricode':'NYK'}}
            payload={'header':{'id':'wrong','competitions':[{'id':'wrong'}]}}
            with patch.object(eng,'HISTORY',history),patch.object(eng,'ODDS',folder/'odds.csv'),patch.object(eng,'schedule',return_value=[game]),patch.object(eng,'get_json',return_value=payload),patch.object(eng,'create_starter_template'):
                eng.sync(1)
            self.assertEqual(previous,history.read_bytes())

class HistoryRepairTests(unittest.TestCase):
    def setUp(self):
        self.good=game_rows('espn_123','2025-10-25')
        self.bad=[dict(r) for r in self.good];self.bad[1]['first_team_shot']=1
        fixture=ForwardJournalTests();fixture.setUp()
        self.payload=fixture.payload()
        self.payload['header']['competitions'][0]['date']='2025-10-25T23:00:00Z'
    def test_repair_backups_and_preserves_other_games(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'history.csv'
            untouched=game_rows('espn_456','2025-10-26')
            eng.write_csv(path,eng.FIELDS,self.bad+untouched);before=path.read_bytes()
            with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt.core,'request',return_value=self.payload),patch.object(eng,'extract_game',return_value=self.good):
                result=rt.repair_history(['espn_123'])
            self.assertEqual(result['repaired'],1)
            self.assertEqual((folder/result['backup']).read_bytes(),before)
            loaded=eng.read_csv(path)
            self.assertEqual(rt.audit(loaded)[1],[])
            self.assertEqual([r for r in loaded if r['game_id']=='espn_456'],[{k:str(r.get(k,'')) for k in eng.FIELDS} for r in untouched])
    def test_wrong_id_and_offline_leave_original_bytes(self):
        import copy
        wrong=copy.deepcopy(self.payload);wrong['header']['id']='wrong'
        for failure in (RuntimeError('offline'),wrong):
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);path=folder/'history.csv';eng.write_csv(path,eng.FIELDS,self.bad);before=path.read_bytes()
                kwargs={'side_effect':failure} if isinstance(failure,Exception) else {'return_value':failure}
                with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt.core,'request',**kwargs):
                    result=rt.repair_history(['espn_123'])
                self.assertEqual(result['repaired'],0);self.assertEqual(len(result['errors']),1)
                self.assertEqual(path.read_bytes(),before);self.assertIsNone(result['backup'])
    def test_invalid_replacement_and_nonstarter_preserve_original(self):
        for failure in (ValueError('First scorer is not a starter'),self.bad):
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);path=folder/'history.csv';eng.write_csv(path,eng.FIELDS,self.bad);before=path.read_bytes()
                kwargs={'side_effect':failure} if isinstance(failure,Exception) else {'return_value':failure}
                with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt.core,'request',return_value=self.payload),patch.object(eng,'extract_game',**kwargs):
                    result=rt.repair_history(['espn_123'])
                self.assertEqual(result['repaired'],0);self.assertEqual(path.read_bytes(),before)
    def test_concurrent_changes_abort_before_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'history.csv';eng.write_csv(path,eng.FIELDS,self.bad)
            def download(*args,**kwargs):
                eng.write_csv(path,eng.FIELDS,self.bad+game_rows('espn_456','2025-10-26'))
                return self.payload
            with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt.core,'request',side_effect=download),patch.object(eng,'extract_game',return_value=self.good):
                with self.assertRaisesRegex(ValueError,'History changed'):rt.repair_history(['espn_123'])
            self.assertEqual(len(eng.read_csv(path)),20)
    def test_backup_failure_prevents_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'history.csv';eng.write_csv(path,eng.FIELDS,self.bad);before=path.read_bytes()
            with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt.core,'request',return_value=self.payload),patch.object(eng,'extract_game',return_value=self.good),patch('tempfile.mkstemp',side_effect=OSError('disk error')):
                with self.assertRaises(OSError):rt.repair_history(['espn_123'])
            self.assertEqual(path.read_bytes(),before)
    def test_valid_games_cannot_be_selected_for_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.csv';eng.write_csv(path,eng.FIELDS,self.good)
            with patch.object(eng,'HISTORY',path),patch.object(rt.core,'request') as request:
                with self.assertRaises(ValueError):rt.repair_history(['espn_123'])
                request.assert_not_called()

class FullValidationTests(unittest.TestCase):
    def test_same_games_and_newest_full_dates(self):
        from datetime import date,timedelta
        start=date(2026,8,1)
        rows=[r for i in range(9) for r in game_rows(str(i),(start+timedelta(days=i)).isoformat())]
        rows+=game_rows('extra','2026-08-09')
        report=rt.validation_report(rows,2)
        self.assertEqual(report['evaluated_dates'],7)
        self.assertEqual(report['latest_dates'],2)
        newest=[r for r in report['summary'] if r['Period']=='Newest quarter of dates']
        self.assertEqual([r['Evaluated games'] for r in newest],[3,3,3])
        self.assertTrue(all(r['First date']=='2026-08-08' for r in newest))
        sets=[{r['Game'] for r in report['details'] if r['Model']==model} for model in ('baseline','recent','lineup')]
        self.assertEqual(sets[0],sets[1]);self.assertEqual(sets[0],sets[2])
        self.assertEqual(len(report['latest_comparisons']),8)
    def test_empty_and_one_date_reports(self):
        self.assertEqual(rt.validation_report([],2)['summary'],[])
        rows=game_rows('a','2026-08-01')+game_rows('b','2026-08-02')
        result=rt.validation_report(rows,1)
        self.assertEqual(result['latest_dates'],1)
        self.assertTrue(all(r['95% lower'] is None for r in result['latest_comparisons']))
    def test_metrics_are_game_weighted(self):
        games=[{'Top-1 credit':v,'Top-3 credit':v,'Log loss':v,'Brier':v} for v in (0.,0.,1.)]
        m=rt.evaluation_metrics(games)
        self.assertAlmostEqual(m['Log loss'],1/3)
        self.assertAlmostEqual(m['Top-1 hit %'],100/3)
    def test_month_counts_add_to_all_games(self):
        rows=game_rows('a','2026-08-30')+game_rows('b','2026-08-31')+game_rows('c','2026-09-01')+game_rows('d','2026-09-02')
        report=rt.validation_report(rows,1)
        for model in ('baseline','recent','lineup'):
            self.assertEqual(sum(r['Evaluated games'] for r in report['monthly'] if r['Model']==model),3)
    def test_comparison_rejects_mismatched_game_sets(self):
        first={'games':[{'Game':'a','Date':'2026-08-01'}],'excluded':[]}
        other={'games':[],'excluded':[]}
        with patch.object(rt,'evaluate',side_effect=[first,other,other]):
            with self.assertRaisesRegex(ValueError,'identical'):rt.validation_report([],1)

class BatchPredictionTests(unittest.TestCase):
    def setUp(self):
        self.history=game_rows('old','2026-10-20')+game_rows('older','2026-10-19')
        self.five={t:[dict(r) for r in self.history[:10] if r['team']==t] for t in ('BOS','NYK')}
    def reference(self,history,lineups,target,model):
        prior=rt.history_window(history,target)
        a,b=sorted(lineups)
        stats=eng.team_stats(prior) if model=='baseline' else eng.recent_team_stats(prior,target)
        pa=eng.first_team_probability(a,b,stats) if model=='baseline' else eng.recent_first_team_probability(a,b,stats)
        result={}
        for team,pt in ((a,pa),(b,1-pa)):
            weights=eng.player_weights(prior,lineups[team],team) if model=='baseline' else eng.recent_player_weights(prior,lineups[team],team,target) if model=='recent' else eng.lineup_player_weights(prior,lineups[team],team,target)
            result.update({p['player_id']:pt*w for p,w,*_ in weights})
        return result
    def test_matches_previous_full_history_calculation(self):
        import copy
        alt=copy.deepcopy(self.five);alt['BOS'][-1]['player_id']='99'
        history=self.history+game_rows('same','2026-10-21')+game_rows('future','2026-10-22')+game_rows('old','2020-01-01')
        for model in ('baseline','recent','lineup'):
            result=eng.predict_matchups(history,{'a':self.five,'b':alt},'2026-10-21',model)
            for gid,five in [('a',self.five),('b',alt)]:
                self.assertEqual(result[gid],self.reference(history,five,'2026-10-21',model))
                self.assertAlmostEqual(sum(result[gid].values()),1)
    def test_statistics_built_once_per_batch(self):
        with patch.object(eng,'team_stats',wraps=eng.team_stats) as stats:
            eng.predict_matchups(self.history,{'a':self.five,'b':self.five},'2026-10-21')
            self.assertEqual(stats.call_count,1)
    def test_history_changes_are_not_cached_between_calls(self):
        first=eng.predict_matchups([],{'a':self.five},'2026-10-21')
        second=eng.predict_matchups(self.history,{'a':self.five},'2026-10-21')
        self.assertNotEqual(first,second)
    def test_empty_batch_and_invalid_lineups(self):
        self.assertEqual(eng.predict_matchups([],{},'2026-10-21'),{})
        with self.assertRaises(ValueError):eng.predict_matchups([],{'a':{'BOS':[]}},'2026-10-21')


class PickReliabilityTests(unittest.TestCase):
    def test_uniform_ties_are_one_game_with_fractional_credit(self):
        result=rt.evaluate(game_rows('a','2026-08-01'),0)
        game=result['games'][0]
        self.assertEqual(game['Tied leaders'],10)
        self.assertAlmostEqual(game['Top probability'],.1)
        self.assertEqual(game['Top margin'],0)
        for band in rt.pick_reliability(result['games']):
            self.assertEqual(band['Games'],1)
            self.assertEqual(band['Tied-leader games'],1)
            self.assertAlmostEqual(band['Observed minus predicted pp'],0)
    def test_band_boundaries_and_weighting(self):
        games=[{'Date':'2026-08-01','Top probability':p,'Top margin':m,'Tied leaders':1,'Top-1 credit':hit}
               for p,m,hit in ((.15,.02,1),(.19,.049,0),(.30,.10,0))]
        result=rt.pick_reliability(games)
        band=next(r for r in result if r['Group by']=='Top probability' and r['Band']=='15–20%')
        self.assertEqual(band['Games'],2);self.assertEqual(band['Dates'],1)
        self.assertAlmostEqual(band['Mean top probability %'],17)
        self.assertEqual(band['Observed top-1 hit %'],50)
        self.assertAlmostEqual(band['Observed minus predicted pp'],33)
        self.assertEqual(next(r for r in result if r['Band']=='10 pp+')['Games'],1)
    def test_each_game_counted_once_per_group_and_period(self):
        rows=sum((game_rows(str(i),f'2026-08-{i+1:02d}') for i in range(8)),[])
        report=rt.validation_report(rows,1)
        for summary in report['summary']:
            for dimension in ('Top probability','Top margin'):
                bands=[r for r in report['pick_reliability'] if r['Model']==summary['Model'] and r['Period']==summary['Period'] and r['Group by']==dimension]
                self.assertEqual(sum(r['Games'] for r in bands),summary['Evaluated games'])
    def test_empty_report(self):
        self.assertEqual(rt.pick_reliability([]),[])
        self.assertEqual(rt.validation_report([],1)['pick_reliability'],[])

class OpeningShotCoverageTests(unittest.TestCase):
    def setUp(self):
        self.rows=game_rows('a','2026-10-20')
        self.five=[r.copy() for r in self.rows if r['team']=='BOS']
    def unknown(self, flag=None):
        rows=[dict(r) for r in self.rows]
        for r in rows:
            if r['team']=='BOS':
                r['first_team_shot']=0;r['first_game_shot']=0
                if flag is not None:r['opening_shot_observed']=flag
        return rows
    def test_legacy_known_and_ambiguous_groups(self):
        self.assertIn(('a','BOS'),eng.opening_shot_games(self.rows))
        self.assertNotIn(('a','BOS'),eng.opening_shot_games(self.unknown()))
        self.assertNotIn(('a','BOS'),eng.opening_shot_games(self.unknown(0)))
        self.assertIn(('a','BOS'),eng.opening_shot_games(self.unknown(1)))
    def test_unknown_shots_leave_neutral_shot_prior_but_keep_scores(self):
        rows=self.unknown()
        recent=eng.recent_player_weights(rows,self.five,'BOS','2026-10-21')
        context=eng.lineup_player_weights(rows,self.five,'BOS','2026-10-21')
        for model in (recent,context):
            self.assertTrue(all(abs(r[6]-.2)<1e-12 for r in model))
            self.assertGreater(model[0][7],.2)
            self.assertEqual(model[0][2],1)
        baseline=eng.player_weights(rows,self.five,'BOS')
        raw=[.65*.2+.35*((int(i==0)+.5)/6) for i in range(5)]
        for r,w in zip(baseline,raw):self.assertAlmostEqual(r[1],w/sum(raw))
    def test_confirmed_bench_shot_is_an_observed_miss(self):
        weight=2**(-1/90)
        for model in (eng.recent_player_weights,eng.lineup_player_weights):
            result=model(self.unknown(1),self.five,'BOS','2026-10-21')
            for r in result:self.assertAlmostEqual(r[6],2/(weight+10))
    def test_coverage_validation(self):
        for value in ('bad',2):
            self.assertTrue(rt.audit(self.unknown(value))[1])
        mixed=self.unknown(1);mixed[0]['opening_shot_observed']=0
        self.assertTrue(rt.audit(mixed)[1])
        contradicted=[dict(r,opening_shot_observed=0) for r in self.rows]
        self.assertTrue(rt.audit(contradicted)[1])
        self.assertFalse(rt.audit(self.unknown(1))[1])
    def test_legacy_csv_roundtrip_and_prediction(self):
        rows=self.rows+self.unknown()
        for r in rows[10:]:r['game_id']='b';r['date']='2026-10-19'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.csv'
            eng.write_csv(path,[f for f in eng.FIELDS if f!='opening_shot_observed'],rows)
            old=eng.read_csv(path)
            eng.write_csv(path,eng.FIELDS,old)
            new=eng.read_csv(path)
            self.assertFalse(rt.audit(new)[1])
            lineups={t:[r for r in self.rows if r['team']==t] for t in ('BOS','NYK')}
            for model in ('baseline','recent','lineup'):
                self.assertEqual(eng.predict_first_score(old,lineups,'2026-10-21',model),eng.predict_first_score(new,lineups,'2026-10-21',model))
    def test_player_evidence_unknowns_are_not_false(self):
        evidence=rt.player_evidence(self.unknown(),'2026-10-21','BOS','10',self.five)
        stats=evidence['summary'][-1]
        self.assertEqual(stats['Observed opening-shot starts'],0)
        self.assertEqual(stats['Unknown opening-shot starts'],1)
        self.assertIsNone(stats['Opening-shot rate %'])
        self.assertIsNone(evidence['games'][0]['Took team first shot'])
        self.assertEqual(stats['Game first scores'],1)
    def test_import_distinguishes_bench_missing_and_starter_shooters(self):
        fixture=ForwardJournalTests();fixture.setUp()
        for pid,expected in [('99',1),('999',0),('10',1)]:
            payload=fixture.payload()
            payload['plays'].insert(0,{'period':{'number':1},'sequenceNumber':'0','text':'Player misses layup','shootingPlay':True,'scoringPlay':False,'scoreValue':0,'team':{'id':'1'},'participants':[{'athlete':{'id':pid}}]})
            play,box=eng.espn_game_payloads(payload)
            rows=eng.extract_game(fixture.game,play,box)
            self.assertEqual({r['opening_shot_observed'] for r in rows if r['team']=='BOS'},{expected})
            self.assertEqual({r['opening_shot_observed'] for r in rows if r['team']=='NYK'},{0})
            self.assertFalse(rt.audit(rows)[1])
            self.assertEqual(sum(r['first_team_shot'] for r in rows),int(pid=='10'))

class ScoringStageTests(unittest.TestCase):
    def setUp(self):
        self.teams={str(i):'BOS' if i<5 else 'NYK' for i in range(10)}
    def test_uniform_baselines_and_ties(self):
        result=rt.scoring_stage_metrics({str(i):.1 for i in range(10)},self.teams,'0')
        self.assertAlmostEqual(result['Team top-1 credit'],.5)
        self.assertAlmostEqual(result['Within-winning-team top-1 credit'],.2)
        self.assertAlmostEqual(result['Team log loss'],math.log(2))
        self.assertAlmostEqual(result['Within-team log loss'],math.log(5))
        summary=rt.scoring_stage_summary([result])
        self.assertAlmostEqual(summary['Team loss minus 50/50'],0)
        self.assertAlmostEqual(summary['Within-team loss minus equal five'],0)
    def test_correct_team_wrong_player_and_exact_loss_decomposition(self):
        probs={str(i):.05 for i in range(10)}
        probs['0']=.45;probs['1']=.15
        result=rt.scoring_stage_metrics(probs,self.teams,'1')
        self.assertEqual(result['Team top-1 credit'],1)
        self.assertEqual(result['Within-winning-team top-1 credit'],0)
        self.assertAlmostEqual(result['Winning team probability'],.75)
        self.assertAlmostEqual(result['Winner share within team'],.2)
        self.assertAlmostEqual(result['Team log loss']+result['Within-team log loss'],-math.log(.15))
    def test_wrong_team_still_evaluates_actual_winning_team_player(self):
        probs={str(i):.05 for i in range(10)};probs['0']=.45;probs['5']=.15
        result=rt.scoring_stage_metrics(probs,self.teams,'5')
        self.assertEqual(result['Team top-1 credit'],0)
        self.assertEqual(result['Within-winning-team top-1 credit'],1)
        self.assertAlmostEqual(result['Winner share within team'],.15/.35)
    def test_all_models_periods_preserve_total_loss_and_counts(self):
        rows=sum((game_rows(str(i),f'2026-08-{i+1:02d}') for i in range(8)),[])
        report=rt.validation_report(rows,1)
        for stage in report['scoring_stages']:
            summary=next(r for r in report['summary'] if r['Model']==stage['Model'] and r['Period']==stage['Period'])
            self.assertEqual(stage['Games'],summary['Evaluated games'])
            self.assertAlmostEqual(stage['Team log loss']+stage['Within-team log loss'],summary['Log loss'])
        for game in report['details']:
            self.assertAlmostEqual(game['Team log loss']+game['Within-team log loss'],game['Log loss'])
    def test_invalid_inputs_and_empty_history(self):
        probs={str(i):.1 for i in range(10)}
        for bad in ({**probs,'0':0},{**probs,'0':float('nan')},{**probs,'0':.2}):
            with self.assertRaises(ValueError):rt.scoring_stage_metrics(bad,self.teams,'0')
        with self.assertRaises(ValueError):rt.scoring_stage_metrics(probs,self.teams,'outside')
        with self.assertRaises(ValueError):rt.scoring_stage_metrics(probs,{k:'BOS' for k in probs},'0')
        self.assertEqual(rt.scoring_stage_summary([]),{})
        self.assertEqual(rt.validation_report([],1)['scoring_stages'],[])

class OpeningPlayIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture=ForwardJournalTests();self.fixture.setUp()
        self.payload=self.fixture.payload()
    def test_unreadable_first_scorer_cannot_be_skipped_for_later_basket(self):
        import copy
        first=copy.deepcopy(self.payload['plays'][0]);first['sequenceNumber']='0';first['participants']=[]
        self.payload['plays'].insert(0,first)
        with self.assertRaisesRegex(ValueError,'identifiable scorer'):eng.espn_game_payloads(self.payload)
        with self.assertRaisesRegex(ValueError,'identifiable scorer'):
            rt.outcome_from_summary({'game_id':'espn_123','rows':self.fixture.rows},self.payload)
    def test_score_totals_detect_missing_earlier_basket(self):
        import copy
        variants=[]
        bad=copy.deepcopy(self.payload);bad['plays'][0].update(homeScore=2,awayScore=2);variants.append(bad)
        bad=copy.deepcopy(self.payload);bad['plays'][0].update(homeScore=0,awayScore=4);variants.append(bad)
        bad=copy.deepcopy(self.payload)
        before=copy.deepcopy(bad['plays'][0]);before.update(sequenceNumber='0',scoringPlay=False,scoreValue=0,homeScore=0,awayScore=2,text='Player misses shot')
        bad['plays'].insert(0,before);variants.append(bad)
        for payload in variants:
            with self.assertRaisesRegex(ValueError,'scoreboard'):eng.espn_game_payloads(payload)
    def test_valid_free_throw_field_goal_and_optional_totals(self):
        for free,points in ((False,2),(True,1)):
            payload=self.fixture.payload(free=free);payload['plays'][0].update(homeScore=0,awayScore=points)
            play,box=eng.espn_game_payloads(payload)
            self.assertTrue(eng.is_made_score(play['game']['actions'][0]))
        play,box=eng.espn_game_payloads(self.payload)
        self.assertEqual(play['game']['actions'][0]['personId'],10)
    def test_conflicting_duplicates_rejected_identical_duplicates_collapsed(self):
        import copy
        first=copy.deepcopy(self.payload['plays'][0]);self.payload['plays'].append(first)
        self.assertEqual(len(eng.espn_game_payloads(self.payload)[0]['game']['actions']),1)
        first['participants']=[{'athlete':{'id':'11'}}]
        with self.assertRaisesRegex(ValueError,'Conflicting'):eng.espn_game_payloads(self.payload)
    def test_input_order_does_not_change_first_scorer(self):
        import copy
        later=copy.deepcopy(self.payload['plays'][0]);later['sequenceNumber']='2';later['participants']=[{'athlete':{'id':'11'}}]
        self.payload['plays'].insert(0,later)
        plays=eng.espn_game_payloads(self.payload)[0]['game']['actions']
        self.assertEqual(plays[0]['personId'],10)
    def test_first_score_flags_identity_type_and_totals_checked(self):
        import copy
        changes=[{'scoringPlay':False},{'scoreValue':0},{'shootingPlay':False},
                 {'participants':[{'athlete':{'id':'20'}}]},
                 {'homeScore':0},{'homeScore':0,'awayScore':True},
                 {'sequenceNumber':'bad'},{'sequenceNumber':1.2},{'sequenceNumber':True},{'scoreValue':2.5},{'text':'MISS layup'}]
        for change in changes:
            payload=copy.deepcopy(self.payload);payload['plays'][0].update(change)
            with self.assertRaises(ValueError):eng.espn_game_payloads(payload)
    def test_refresh_keeps_invalid_outcome_pending(self):
        self.payload['plays'][0]['participants']=[]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal'
            self.fixture.save(path)
            with patch.object(rt.core,'request',return_value=self.payload):
                updated,errors=rt.refresh_journal(path)
            self.assertEqual(updated,0);self.assertEqual(len(errors),1)
            self.assertIsNone(rt.journal_records(path)[0]['outcome'])

class SignalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.history=game_rows('a','2026-10-20')
        for row in self.history:
            row['first_team_shot']=int(row['player_id'] in ('11','21'))
            row['first_game_shot']=int(row['player_id']=='11')
        self.lineups={t:[dict(r) for r in self.history if r['team']==t] for t in ('BOS','NYK')}
    def test_pure_signals_change_player_leader_but_preserve_team_mass(self):
        for model in ('baseline','recent','lineup'):
            results={w:eng.predict_first_score(self.history,self.lineups,'2026-10-21',model,shot_weight=w) for w in (0.,.65,1.)}
            for w,probs in results.items():
                self.assertAlmostEqual(sum(probs.values()),1)
                self.assertAlmostEqual(sum(probs[p['player_id']] for p in self.lineups['BOS']),sum(results[.65][p['player_id']] for p in self.lineups['BOS']))
            self.assertGreater(results[1.]['11'],results[1.]['10'])
            self.assertGreater(results[0.]['10'],results[0.]['11'])
            self.assertEqual(eng.predict_first_score(self.history,self.lineups,'2026-10-21',model),results[.65])
    def test_baseline_default_matches_original_rate_blend(self):
        rows=eng.player_weights(self.history,self.lineups['BOS'],'BOS')
        raw=[.65*(int(i==1)+1)/6+.35*(int(i==0)+.5)/6 for i in range(5)]
        for row,w in zip(rows,raw):self.assertAlmostEqual(row[1],w/sum(raw))
    def test_experiment_matches_regular_evaluation_and_keeps_same_games(self):
        from datetime import date,timedelta
        history=[r for i in range(8) for r in game_rows(str(i),(date(2026,8,1)+timedelta(days=i)).isoformat())]
        for model in ('baseline','recent','lineup'):
            report=rt.compare_scoring_signals(history,1,model)
            regular=rt.evaluate(history,1,model)
            blend=[{k:v for k,v in r.items() if k not in ('Signal variant','Shot weight','Newest quarter')} for r in report['details'] if r['Signal variant']=='Current blend']
            self.assertEqual(blend,regular['games'])
            groups=[{(r['Game'],r['Date']) for r in report['details'] if r['Signal variant']==label} for label in ('Current blend','Opening shot only','First score only')]
            self.assertEqual(groups[0],groups[1]);self.assertEqual(groups[1],groups[2])
            self.assertEqual(len(report['summary']),8)
            self.assertEqual(len(report['recent_comparisons']),12)
    def test_all_signal_variants_exclude_same_day_future_and_old_history(self):
        extra=game_rows('same','2026-10-21')+game_rows('future','2026-10-22')+game_rows('old','2020-01-01')
        for model in ('baseline','recent','lineup'):
            for w in (0.,1.):
                self.assertEqual(eng.predict_first_score(self.history,self.lineups,'2026-10-21',model,w),eng.predict_first_score(self.history+extra,self.lineups,'2026-10-21',model,w))
    def test_invalid_weights_and_empty_history(self):
        for w in (-.1,1.1,float('nan'),float('inf'),True,'0.5'):
            with self.assertRaises(ValueError):eng.predict_matchups([],{},'2026-10-21',shot_weight=w)
            with self.assertRaises(ValueError):rt.evaluate([],1,shot_weight=w)
        self.assertEqual(rt.compare_scoring_signals([],1)['summary'],[])
    def test_mismatched_games_rejected(self):
        first={'games':[{'Game':'a','Date':'2026-10-20'}],'excluded':[]}
        other={'games':[],'excluded':[]}
        with patch.object(rt,'evaluate',side_effect=[first,other,other]):
            with self.assertRaisesRegex(ValueError,'identical'):rt.compare_scoring_signals([],1)

class AdaptiveSignalTests(unittest.TestCase):
    def results(self,dated_losses):
        labels=('Current blend','Opening shot only','First score only')
        return {label:{'games':[{'Date':day,'Game':gid,'Log loss':losses[i]} for day,gid,losses in dated_losses]} for i,label in enumerate(labels)}
    def test_default_100_game_threshold_and_fallback(self):
        from datetime import date,timedelta
        values=[((date(2026,1,1)+timedelta(days=i)).isoformat(),str(i),(2.,1.,3.)) for i in range(101)]
        games,decisions=rt.adaptive_signal_games(self.results(values))
        self.assertTrue(all(r['Selected signal']=='Current blend' for r in games[:100]))
        self.assertEqual(games[-1]['Selected signal'],'Opening shot only')
        self.assertEqual(games[-1]['Selection training games'],100)
        self.assertEqual(sum(r['Selection learned'] for r in games),1)
    def test_same_date_and_future_outcomes_cannot_change_selection(self):
        import copy
        values=[('2026-10-01','a',(2.,1.,3.)),('2026-10-02','b',(.1,9.,2.)),('2026-10-02','c',(.1,9.,2.)),('2026-10-03','d',(5.,.1,4.))]
        results=self.results(values);original=copy.deepcopy(results)
        games,decisions=rt.adaptive_signal_games(results,1)
        self.assertEqual([r['Selected signal'] for r in games[1:3]],['Opening shot only']*2)
        self.assertEqual([r['Selection training games'] for r in games[1:3]],[1,1])
        changed=copy.deepcopy(results)
        for result in changed.values():
            for row in result['games']:
                if row['Date']>='2026-10-02':row['Log loss']=100.
        new_games,new_decisions=rt.adaptive_signal_games(changed,1)
        self.assertEqual(decisions[:2],new_decisions[:2])
        self.assertEqual(results,original)
        self.assertEqual(games[-1]['Selected signal'],'Current blend')
    def test_expired_selection_history_dropped_and_boundary_included(self):
        from datetime import date,timedelta
        start=date(2025,1,1)
        for age,expected in [(400,1),(401,0)]:
            values=[(start.isoformat(),'old',(2.,1.,3.)),((start+timedelta(days=age)).isoformat(),'new',(2.,1.,3.))]
            games,decisions=rt.adaptive_signal_games(self.results(values),1)
            self.assertEqual(games[-1]['Selection training games'],expected)
            self.assertEqual(games[-1]['Selection learned'],bool(expected))
    def test_ties_prefer_current_blend(self):
        values=[('2026-10-01','a',(1.,1.,1.)),('2026-10-02','b',(1.,1.,1.))]
        games,_=rt.adaptive_signal_games(self.results(values),1)
        self.assertTrue(games[-1]['Selection learned'])
        self.assertEqual(games[-1]['Selected signal'],'Current blend')
    def test_selector_returns_the_chosen_forecast_not_best_current_outcome(self):
        values=[('2026-10-01','a',(2.,1.,3.)),('2026-10-02','b',(.1,9.,2.))]
        games,_=rt.adaptive_signal_games(self.results(values),1)
        self.assertEqual(games[-1]['Log loss'],9.)
        self.assertEqual(games[-1]['Selected shot weight'],1.)
    def test_empty_invalid_and_duplicate_inputs(self):
        self.assertEqual(rt.adaptive_signal_games(self.results([])),([],[]))
        results=self.results([('2026-10-01','a',(2.,1.,3.))])
        for minimum in (0,True,1.5):
            with self.assertRaises(ValueError):rt.adaptive_signal_games(results,minimum)
        results['Current blend']['games'][0]['Log loss']=float('nan')
        with self.assertRaises(ValueError):rt.adaptive_signal_games(results)
        results=self.results([('2026-10-01','a',(2.,1.,3.))])
        results['Current blend']['games']*=2
        with self.assertRaisesRegex(ValueError,'identical'):rt.adaptive_signal_games(results)
