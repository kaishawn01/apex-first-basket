"""Entirely synthetic pilot; no credentials, network or provider data."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import requests
import phase10_dunk as d
from phase5_store import Store, Conflict, StorageError
from phase5_providers import ProviderError
from phase4_data import digest


def fixture(gid='100'):
    players=[{'player_id':str(i),'team_id':'1' if i<=5 else '2','starter':True,'did_not_play':False} for i in range(1,11)]
    b={'game':{'game_id':gid,'starts_at':'2026-10-21T23:00:00Z','date':'2026-10-21','season_type':'regular','status':'final',
       'home':{'team_id':'1','abbrev':'BOS','score':3},'away':{'team_id':'2','abbrev':'NYK','score':0}},'players':players,'plays':6}
    rows=[]
    for seq,period,clock,points,pid,shot,score in [(1,1,720,0,None,None,0),(2,1,710,1,'1',{'made':True,'points_attempted':1},1),(3,1,700,2,'2',{'made':True,'points_attempted':2,'expected_points':999},3),(4,2,0,0,None,None,3),(5,3,0,0,None,None,3),(6,4,0,0,None,None,3)]:
        rows.append({'game_id':gid,'seq':seq,'period':period,'clock_seconds':clock,'points':points,'player_id':pid,'team':'BOS','shot':shot,'home_score':score,'away_score':0,'home_win_prob':.99})
    return b,[{'plays':rows,'count':len(rows),'next_offset':None}]


class Phase10Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=datetime(2026,10,29,20,tzinfo=timezone.utc)
        self.path=Path(self.tmp.name)/'fixture.sqlite3'
        self.s=Store(self.path,clock=lambda:self.now)
        self.transport=Mock(side_effect=self.respond)
        self.p=d.Pilot(self.s,['100','101','102','103','104'],free_balance=500,test_transport=self.transport)
        self.b,self.pages=fixture()
    def respond(self,url,**kw):
        self.now+=timedelta(seconds=8)
        b,pages=fixture(kw['json']['game_id'])
        payload=b if url.endswith('get_game') else pages[0]
        return self.response(payload)
    def response(self,payload,status=200):
        r=Mock(status_code=status);r.iter_content.return_value=[json.dumps(payload).encode()];return r
    def inspect(self):return d.inspect_game(self.b,self.pages,'2026-10-29')
    def spent(self):return sum(x['payload']['cost'] for x in self.s.rows('dunk_attempt'))
    def test_five_game_fixture_cost_and_outcomes(self):
        for gid in self.p.ids:
            box=self.p.fetch('get_game',gid);pages=self.p.plays(gid)
            r=d.inspect_game(box,pages,'2026-10-29')
            self.assertEqual(r['first_score']['kind'],'free_throw')
            self.assertEqual(r['first_fg_attempt']['player_id'],'2')
            self.assertTrue(r['single_response_complete']);self.assertFalse(r['model_compatible'])
        self.assertEqual(self.spent(),75);self.assertEqual(self.transport.call_count,10)
    def test_live_has_no_transport_and_blocks(self):
        s=Store(Path(self.tmp.name)/'live.db')
        p=d.Pilot(s,self.p.ids,free_balance=100)
        with patch('requests.post') as post:
            with self.assertRaisesRegex(ProviderError,'upstream'):p.fetch('get_game','100')
            post.assert_not_called()
        self.assertFalse(s.rows('dunk_attempt'))
    def test_at_most_100_credits(self):
        for i in range(10):self.p.fetch('get_plays','100',i*1000)
        with self.assertRaisesRegex(ProviderError,'ceiling'):self.p.fetch('get_game','101')
        self.assertEqual(self.spent(),100);self.assertEqual(self.transport.call_count,10)
    def test_free_balance_lower_than_ceiling(self):
        p=d.Pilot(Store(Path(self.tmp.name)/'low.db'),self.p.ids,free_balance=4,test_transport=self.transport)
        with self.assertRaises(ProviderError):p.fetch('get_game','100')
        self.transport.assert_not_called()
    def test_config_cannot_reset_budget(self):
        with self.assertRaises(Conflict):d.Pilot(self.s,self.p.ids,free_balance=20,test_transport=self.transport)
    def test_exact_five_unique_ids(self):
        for ids in [['1']*5,['1','2'],['1','2','3','4',True]]:
            with self.assertRaises(ValueError):d.Pilot(self.s,ids,free_balance=100)
    def test_timeout_spends_and_blocks_repeat(self):
        self.transport.side_effect=requests.Timeout('private detail')
        with self.assertRaisesRegex(ProviderError,'reservation retained'):self.p.fetch('get_game','100')
        with self.assertRaisesRegex(ProviderError,'unresolved'):self.p.fetch('get_game','100')
        self.assertEqual(self.spent(),5);self.assertEqual(self.transport.call_count,1)
    def test_restart_uses_original_cached_bytes(self):
        a=self.p.fetch('get_game','100')
        p=d.Pilot(Store(self.path,clock=lambda:self.now),self.p.ids,free_balance=500,test_transport=self.transport)
        self.assertEqual(a,p.fetch('get_game','100'));self.assertEqual(self.transport.call_count,1)
    def test_interruption_reservation_not_refunded(self):
        self.transport.side_effect=KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):self.p.fetch('get_game','100')
        p=d.Pilot(Store(self.path,clock=lambda:self.now),self.p.ids,free_balance=500,test_transport=self.transport)
        with self.assertRaisesRegex(ProviderError,'unresolved'):p.fetch('get_game','100')
        self.assertEqual(self.spent(),5)
    def test_concurrent_request_lease(self):
        lease=self.s.acquire('phase10:requests',90)
        try:
            with self.assertRaises(ProviderError):self.p.fetch('get_game','100')
            self.transport.assert_not_called()
        finally:self.s.release(lease)
    def test_unknown_host_path_or_game_blocked(self):
        for endpoint,gid in [('https://evil.test','100'),('billing','100'),('get_game','200')]:
            with self.assertRaises(ProviderError):self.p.fetch(endpoint,gid)
        self.transport.assert_not_called()
    def test_http_403_body_never_exposed(self):
        self.transport.side_effect=lambda *a,**k:self.response({'api_key':'private'},403)
        with self.assertRaisesRegex(ProviderError,'body withheld'):self.p.fetch('get_game','100')
        self.assertEqual(self.spent(),5)
    def test_429_cooldown_persisted(self):
        self.transport.side_effect=lambda *a,**k:self.response({},429)
        with self.assertRaises(ProviderError):self.p.fetch('get_game','100')
        with self.assertRaisesRegex(ProviderError,'cooldown'):self.p.fetch('get_game','101')
        self.assertEqual(self.transport.call_count,1)
    def test_redirect_is_not_followed(self):
        self.p.fetch('get_game','100')
        kw=self.transport.call_args.kwargs
        self.assertFalse(kw['allow_redirects']);self.assertEqual(kw['timeout'],15)
        self.assertNotIn('DUNKAPI_API_KEY',json.dumps(kw))
    def test_response_size_cap(self):
        r=self.response({});r.iter_content.return_value=[b'x'*(d.MAX_BYTES+1)];self.transport.side_effect=lambda *a,**k:r
        with self.assertRaisesRegex(ProviderError,'bound'):self.p.fetch('get_game','100')
    def test_two_page_collection(self):
        rows=self.pages[0]['plays']; payloads=[{'plays':rows[:3],'count':3,'next_offset':3},{'plays':rows[3:],'count':3,'next_offset':None}]
        def send(*a,**k):self.now+=timedelta(seconds=8);return self.response(payloads.pop(0))
        self.transport.side_effect=send
        r=d.inspect_game(self.b,self.p.plays('100'),'2026-10-29')
        self.assertEqual(r['event_pages'],2);self.assertFalse(r['single_response_complete']);self.assertEqual(self.spent(),20)
    def test_missing_terminal_cursor_not_complete(self):
        del self.pages[0]['next_offset'];self.transport.side_effect=lambda *a,**k:self.response(self.pages[0])
        with self.assertRaises(ValueError):self.p.plays('100')
    def test_pagination_loop_rejected(self):
        self.pages[0]['next_offset']=0;self.transport.side_effect=lambda *a,**k:self.response(self.pages[0])
        with self.assertRaises(ValueError):self.p.plays('100')
    def test_event_count_mismatch(self):
        self.b['plays']+=1
        with self.assertRaises(ValueError):self.inspect()
    def test_order_not_silently_sorted(self):
        self.pages[0]['plays'].reverse()
        with self.assertRaises(ValueError):self.inspect()
    def test_free_throw_before_fg_distinguished(self):
        r=self.inspect();self.assertEqual(r['first_score']['seq'],2);self.assertEqual(r['first_made_fg']['seq'],3)
    def test_nonstarter_first_scorer_preserved(self):
        self.b['players'].append({'player_id':'11','team_id':'1','starter':False,'did_not_play':False})
        self.pages[0]['plays'][1]['player_id']='11'
        self.assertEqual(self.inspect()['first_scorer_status'],'nonstarter')
    def test_unknown_first_scorer_retained_unresolved(self):
        self.pages[0]['plays'][1]['player_id']=None
        r=self.inspect();self.assertIn('first_scorer_unresolved',r['issues']);self.assertEqual(r['first_scorer_status'],'unknown')
    def test_roster_mismatch_rejected(self):
        self.b['players'][0]['team_id']='3'
        with self.assertRaises(ValueError):self.inspect()
    def test_duplicate_player_rejected(self):
        self.b['players'].append(copy.deepcopy(self.b['players'][0]))
        with self.assertRaises(ValueError):self.inspect()
    def test_missing_starting_five(self):
        self.b['players'][0]['starter']=False
        with self.assertRaises(ValueError):self.inspect()
    def test_derived_feature_allowlist(self):
        self.b['odds']={'future':True};self.b['ratings']='future'
        raw=json.dumps(self.inspect())
        for field in ['expected_points','home_win_prob','odds','ratings']:self.assertNotIn(field,raw)
    def test_same_day_and_future_history_rejected(self):
        for day in ['2026-10-21','2026-10-20']:
            with self.assertRaises(ValueError):d.inspect_game(self.b,self.pages,day)
    def test_numeric_id_match_never_automatic(self):
        self.assertFalse(self.inspect()['player_crosswalk_reviewed'])
        with self.assertRaises(ValueError):d.inspect_game(self.b,self.pages,'2026-10-29',{'players':[{'source_id':'1','target_id':'1'}]})
    def test_mapping_bound_to_source_and_team(self):
        mapping={'source_namespace':'DunkAPI','target_namespace':'ESPN','source_game_id':'100','reviewed':True,'evidence_reference':'synthetic-only','source_hash':digest(self.b),'players':[{'source_id':p['player_id'],'target_id':str(1000+int(p['player_id'])),'source_team_id':p['team_id'],'target_team':'BOS' if p['team_id']=='1' else 'NYK','evidence_reference':'synthetic-only'} for p in self.b['players']]}
        self.assertTrue(d.inspect_game(self.b,self.pages,'2026-10-29',mapping)['player_crosswalk_reviewed'])
        mapping['players'][0]['source_team_id']='2'
        with self.assertRaises(ValueError):d.inspect_game(self.b,self.pages,'2026-10-29',mapping)
    def test_missing_opening_boundary_flagged(self):
        self.pages[0]['plays'][0]['clock_seconds']=719
        self.assertIn('opening_boundary_unverified',self.inspect()['issues'])
    def test_missing_first_score_flagged(self):
        for r in self.pages[0]['plays']:
            r['points']=0;r['home_score']=0
            if r['shot']:r['shot']['made']=False
        self.b['game']['home']['score']=0
        self.assertIn('first_scorer_unresolved',self.inspect()['issues'])
    def test_score_gap_rejected(self):
        self.pages[0]['plays'][1]['home_score']=2
        with self.assertRaises(ValueError):self.inspect()
    def test_global_disable(self):
        with patch.dict(d.os.environ,{'APEX_AUTOMATION_DISABLED':'true'}):
            with self.assertRaises(ProviderError):self.p.fetch('get_game','100')
        self.transport.assert_not_called()

    def test_five_game_orchestration_and_resume(self):
        a=self.p.run('2026-10-29');b=self.p.run('2026-10-29')
        self.assertEqual(a,b);self.assertTrue(a['test_only'])
        self.assertEqual([r['status'] for r in a['games']],['audited']*5)
        self.assertEqual(a['reserved_credits'],75);self.assertEqual(self.transport.call_count,10)
    def test_budget_stop_records_remaining_games(self):
        p=d.Pilot(Store(Path(self.tmp.name)/'limited.db',clock=lambda:self.now),self.p.ids,free_balance=5,test_transport=self.transport)
        r=p.run('2026-10-29')
        self.assertEqual([x['status'] for x in r['games']],['blocked']+['not_attempted']*4)
        self.assertEqual(r['reserved_credits'],5)
    def test_backup_recovery_preserves_budget_and_raw(self):
        self.p.fetch('get_game','100');backup=Path(self.tmp.name)/'backup.json';self.s.export(backup)
        restored=Store(Path(self.tmp.name)/'restored.db',clock=lambda:self.now);restored.restore(backup)
        p=d.Pilot(restored,self.p.ids,free_balance=500,test_transport=self.transport)
        p.fetch('get_game','100');self.assertEqual(self.transport.call_count,1)
        self.assertEqual(restored.rows('dunk_response'),self.s.rows('dunk_response'))
    def test_source_records_reject_mutation(self):
        self.p.fetch('get_game','100')
        with self.assertRaises(StorageError):
            with self.s.transaction(True) as c:c.execute("UPDATE apex_events SET hash='tampered' WHERE kind='dunk_response'")
        self.p.fetch('get_game','100')
        self.assertEqual(self.transport.call_count,1)
