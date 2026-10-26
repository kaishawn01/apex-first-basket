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
        self.assertEqual(seen,[{'2026-10-20'},{'2026-10-20'}])
    def test_equal_model_baseline_and_ties(self):
        rows=game_rows('a','2026-10-20')+game_rows('b','2026-10-21')
        def equal(history,players,team):return [(p,.2,0,0,0) for p in players]
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
            with patch.object(eng,'HISTORY',path),patch.object(eng,'DATA',folder),patch.object(rt,'season_index',return_value=(games,[])),patch.object(rt.core,'request',return_value={}),patch.object(eng,'espn_game_payloads',return_value=({},{})),patch.object(eng,'extract_game',side_effect=lambda g,p,b:game_rows(g['gameId'],g['_date'])):
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
    def test_context_favors_observed_opening_shooter(self):
        recent=eng.recent_player_weights(self.rows,self.players,'BOS','2026-10-21')
        context=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        self.assertGreater(context[0][1],recent[0][1])
        self.assertAlmostEqual(sum(r[1] for r in context),1)
    def test_new_lineup_context_excludes_same_day_future_other_team(self):
        expected=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        added=self.rows+game_rows('same','2026-10-21')+game_rows('future','2026-10-22')+game_rows('old','2020-01-01')
        self.assertEqual(expected,eng.lineup_player_weights(added,self.players,'BOS','2026-10-21'))
    def test_order_independence(self):
        a=eng.lineup_player_weights(self.rows,self.players,'BOS','2026-10-21')
        b=eng.lineup_player_weights(list(reversed(self.rows)),list(reversed(self.players)),'BOS','2026-10-21')
        self.assertEqual({r[0]['player_id']:r[1] for r in a},{r[0]['player_id']:r[1] for r in b})

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
