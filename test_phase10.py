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

class ClarificationPreparationTests(unittest.TestCase):
    def test_exact_manifest_budget_and_window(self):
        m=json.loads((Path(__file__).parent/'validation/PHASE10_REQUEST_MANIFEST.json').read_text())
        self.assertEqual(len(m['games']),5)
        self.assertEqual(len({g['game_id'] for g in m['games']}),5)
        self.assertEqual(len(m['requests']),10)
        self.assertEqual(sum(q['credits_reserved_before_request'] for q in m['requests']),75)
        self.assertEqual(m['lifetime_cap'],100)
        self.assertTrue(m['live_authorized']);self.assertEqual(m['funding_source'],'existing_wallet')
        for g in m['games']:
            self.assertTrue(0<(datetime.fromisoformat(m['cutoff_exclusive'])-datetime.fromisoformat(g['date'])).days<=400)
        for g,(box,plays) in zip(m['games'],zip(m['requests'][::2],m['requests'][1::2])):
            self.assertEqual(box,{'method':'POST','endpoint':'get_game','body':{'game_id':g['game_id']},'credits_reserved_before_request':5})
            self.assertEqual(plays,{'method':'POST','endpoint':'get_plays','body':{'game_id':g['game_id'],'limit':1000,'offset':0},'credits_reserved_before_request':10})
    def test_missed_attempt_precedes_free_throw_first_score(self):
        b,p=fixture();rows=p[0]['plays']
        missed=copy.deepcopy(rows[2]);missed.update(seq=2,clock_seconds=715,points=0,home_score=0)
        missed['shot']={'made':False,'points_attempted':3}
        for row in rows[1:]:row['seq']+=1
        rows.insert(1,missed);b['plays']+=1;p[0]['count']+=1
        a=d.inspect_game(b,p,'2026-11-01')
        self.assertFalse(a['first_fg_attempt']['made'])
        self.assertEqual(a['first_fg_attempt']['seq'],2)
        self.assertEqual(a['first_score']['kind'],'free_throw')
    def test_nonshot_event_labels_preserved_without_role_inference(self):
        for label in ['jumpball','turnover','rebound','substitution']:
            with self.subTest(label=label):
                b,p=fixture();p[0]['plays'][0].update(type=label,player_id='1',player2_id='6')
                a=d.inspect_game(b,p,'2026-11-01');e=a['events'][0]
                self.assertEqual(e['source_type'],label)
                self.assertEqual(e['secondary_player_id'],'6')
                self.assertIsNone(e['kind'])
                self.assertFalse(a['model_compatible'])
    def test_unknown_secondary_identity_not_guessed(self):
        b,p=fixture();p[0]['plays'][0]['player2_id']='9999'
        self.assertIsNone(d.inspect_game(b,p,'2026-11-01')['events'][0]['secondary_player_id'])
    def test_clock_regression_rejected(self):
        b,p=fixture();p[0]['plays'][2]['clock_seconds']=719
        with self.assertRaises(ValueError):d.inspect_game(b,p,'2026-11-01')
    def test_final_score_mismatch_visible(self):
        b,p=fixture();b['game']['home']['score']=99
        self.assertIn('final_score_mismatch',d.inspect_game(b,p,'2026-11-01')['issues'])
    def test_starter_dnp_contradiction_rejected(self):
        b,p=fixture();b['players'][0]['did_not_play']=True
        with self.assertRaises(ValueError):d.inspect_game(b,p,'2026-11-01')

class WalletAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.m=json.loads((Path(__file__).parent/'validation/PHASE10_REQUEST_MANIFEST.json').read_text())
        self.session=Mock();self.now=datetime(2026,11,1,20,tzinfo=timezone.utc)
        self.s=Store(Path(self.tmp.name)/'wallet.db',clock=lambda:self.now)
    def transport(self,**kw):
        return d.WalletTransport(self.m,wallet_balance=500,session=self.session,**kw)
    def pilot(self,t):return d.Pilot(self.s,t.ids,wallet_transport=t)
    def test_default_disabled_before_reservation(self):
        p=self.pilot(self.transport())
        with self.assertRaisesRegex(ProviderError,'disabled'):p.fetch('get_game',p.ids[0])
        self.assertFalse(self.s.rows('dunk_attempt'));self.session.post.assert_not_called()
    def test_missing_key_before_reservation(self):
        p=self.pilot(self.transport(enabled=True,funding_confirmed=True))
        with patch.dict(d.os.environ,{},clear=True):
            with self.assertRaisesRegex(ProviderError,'unavailable'):p.fetch('get_game',p.ids[0])
        self.assertFalse(self.s.rows('dunk_attempt'));self.session.post.assert_not_called()
    def test_unconfirmed_funding_blocks(self):
        p=self.pilot(self.transport(enabled=True))
        with self.assertRaisesRegex(ProviderError,'funding'):p.fetch('get_game',p.ids[0])
        self.session.post.assert_not_called()
    def test_monthly_source_rejected(self):
        self.m['funding_source']='monthly_free'
        with self.assertRaises(ValueError):self.transport()
    def test_manifest_change_rejected(self):
        self.m['requests'][1]['body']['limit']=200
        with self.assertRaises(ValueError):self.transport()
    def test_no_purchase_lookup_or_pagination(self):
        t=self.transport(enabled=True,funding_confirmed=True);p=self.pilot(t)
        with patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'fixture-only'}):
            for endpoint,gid,offset in [('get_plays',p.ids[0],1000),('list_games',p.ids[0],0),('get_game','999',0)]:
                with self.assertRaises(ProviderError):p.fetch(endpoint,gid,offset)
            with self.assertRaises(ProviderError):t('https://mcp.dunkapi.com/v1/billing',json={})
        self.session.post.assert_not_called();self.assertFalse(self.s.rows('dunk_attempt'))
    def test_wallet_ten_calls_75_and_resume_no_extra_calls(self):
        t=self.transport(enabled=True,funding_confirmed=True);p=self.pilot(t)
        def respond(url,**kw):
            self.now+=timedelta(seconds=8)
            b,pages=fixture(kw['json']['game_id']);a=b if url.endswith('get_game') else pages[0]
            return Mock(status_code=200,iter_content=Mock(return_value=[json.dumps(a).encode()]))
        self.session.post.side_effect=respond
        with patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'fixture-only'}):
            for repeat in range(2):
                for gid in p.ids:p.fetch('get_game',gid);p.plays(gid)
        self.assertEqual(self.session.post.call_count,10)
        self.assertEqual(sum(x['payload']['cost'] for x in self.s.rows('dunk_attempt')),75)
        self.assertTrue(all(x['payload']['test_only'] is False for x in self.s.rows('dunk_attempt')))
        self.assertFalse(self.session.trust_env)
        for call in self.session.post.call_args_list:
            self.assertFalse(call.kwargs['allow_redirects'])
            self.assertIn('x-idempotency-key',call.kwargs['headers'])
        self.assertNotIn('fixture-only',json.dumps(self.s.rows()))
    def test_wallet_budget_includes_previous_reservations(self):
        t=self.transport(enabled=True,funding_confirmed=True);p=self.pilot(t)
        self.s.append('dunk_attempt','prior',{'cost':100})
        with patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'fixture-only'}):
            with self.assertRaisesRegex(ProviderError,'ceiling'):p.fetch('get_game',p.ids[0])
        self.session.post.assert_not_called()
    def test_timeout_no_retry_or_secret_in_error(self):
        t=self.transport(enabled=True,funding_confirmed=True);p=self.pilot(t)
        self.session.post.side_effect=requests.Timeout('fixture-secret')
        with patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'fixture-only'}):
            with self.assertRaisesRegex(ProviderError,'reservation retained') as e:p.fetch('get_game',p.ids[0])
            self.assertNotIn('fixture-secret',str(e.exception))
            self.now+=timedelta(seconds=8)
            with self.assertRaisesRegex(ProviderError,'unresolved'):p.fetch('get_game',p.ids[0])
        self.assertEqual(self.session.post.call_count,1)

class LocalCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'private'
    def args(self):
        from argparse import Namespace
        return Namespace(execute=True,confirm_wallet=500,confirm_no_replenishment=True,
                         confirm_exclusive_use=True,confirm_manifest=d.MANIFEST_SHA256)
    def init(self):
        with patch.object(d,'secure_acl'):d.initialize_local(self.root,True)
    def test_status_no_network(self):
        with patch('requests.Session') as session,patch('builtins.print'):
            self.assertEqual(d.main(['status']),0)
        session.assert_not_called()
    def test_live_rejected_on_nonwindows(self):
        with patch.object(d.os,'name','posix'),patch('requests.Session') as session:
            with self.assertRaises(ValueError):d.private_directory()
        session.assert_not_called()
    def test_funding_flags_before_network(self):
        for field in ['execute','confirm_no_replenishment','confirm_exclusive_use']:
            a=self.args();setattr(a,field,False)
            with patch('requests.Session') as session:
                with self.assertRaises(ValueError):d.execute_local(a,self.root)
            session.assert_not_called()
    def test_wrong_wallet_before_network(self):
        a=self.args();a.confirm_wallet=400
        with patch('requests.Session') as session:
            with self.assertRaises(ValueError):d.execute_local(a,self.root)
        session.assert_not_called()
    def test_manifest_hash_rejected(self):
        with self.assertRaises(ValueError):d.local_manifest('changed')
    def test_init_cannot_reset(self):
        self.init()
        with self.assertRaises(ValueError):d.initialize_local(self.root,True)
    def test_missing_database_cannot_reset(self):
        self.init();(self.root/'pilot.sqlite3').unlink()
        with patch.object(d,'secure_acl'),patch('requests.Session') as session:
            with self.assertRaises(ValueError):d.execute_local(self.args(),self.root)
        session.assert_not_called()
    def test_acl_failure_before_transport(self):
        self.init()
        with patch.object(d,'secure_acl',side_effect=ValueError('ACL')),patch('requests.Session') as session:
            with self.assertRaises(ValueError):d.execute_local(self.args(),self.root)
        session.assert_not_called()
    def test_acl_subprocess_never_gets_key(self):
        with patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'PRIVATE'}),patch.object(d.subprocess,'run',return_value=Mock(returncode=0)) as run:
            d.secure_acl(self.root,True)
        self.assertNotIn('DUNKAPI_API_KEY',run.call_args.kwargs['env'])
        self.assertTrue(run.call_args.kwargs['capture_output'])
    def test_sanitizer_excludes_source_text_and_secrets(self):
        report={'test_only':True,'reserved_credits':5,'games':[{'game_id':'1','status':'invalid',
            'diagnostic':'PRIVATE','audit':{'events':['RAW'],'raw_base64':'PRIVATE',
            'first_score':{'kind':'free_throw','text':'RAW','player_id':'PRIVATE'},'issues':['PRIVATE']}}]}
        out=json.dumps(d.sanitized_report(report))
        self.assertNotIn('PRIVATE',out);self.assertNotIn('RAW',out)
    def test_end_to_end_cli_with_synthetic_session(self):
        self.init();m=d.local_manifest(d.MANIFEST_SHA256);session=Mock()
        def respond(url,**kwargs):
            gid=kwargs['json']['game_id'];g=next(x for x in m['games'] if x['game_id']==gid)
            b,p=fixture(gid);b['game'].update(date=g['date'],starts_at=g['date']+'T23:00:00Z')
            b['game']['home']['abbrev']=g['home'];b['game']['away']['abbrev']=g['away']
            for row in p[0]['plays']:row['team']=g['home']
            data=b if url.endswith('get_game') else p[0]
            return Mock(status_code=200,iter_content=Mock(return_value=[json.dumps(data).encode()]))
        session.post.side_effect=respond
        now=datetime(2026,11,1,20,tzinfo=timezone.utc)
        with patch.object(d,'secure_acl'),patch.object(d,'datetime',wraps=datetime) as dt,patch('requests.Session',return_value=session),patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'fixture-only'}),patch('builtins.print'):
            dt.now.return_value=now
            # Advance the store clock instead of sleeping; no real network/time waits.
            original=Store
            tick=[now]
            def make_store(path):
                def clock():tick[0]+=timedelta(seconds=8);return tick[0]
                return original(path,clock=clock)
            with patch.object(d,'Store',side_effect=make_store):
                self.assertEqual(d.execute_local(self.args(),self.root),0)
        result=json.loads((self.root/'sanitized_results.json').read_text())
        self.assertEqual(session.post.call_count,10);self.assertEqual(result['reserved_credits'],75)
        self.assertEqual([g['starter_counts'] for g in result['games']],[[5,5]]*5)
        self.assertFalse(result['model_compatibility_established'])

class WrapperReplayTests(unittest.TestCase):
    def test_observed_wrapper_shape(self):
        box,_=fixture();box.update(odds=[],team_stats=[],win_probability=[])
        self.assertEqual(d.response_payload('get_game',{'data':box}),box)
        self.assertEqual(d.response_payload('get_game',box),box)
    def test_malformed_wrappers(self):
        box,_=fixture()
        for bad in [None,[],{'data':None},{'data':[]},{'data':box,'game':{}},
                    {'data':{'data':box}},{'data':{'game':{},'players':[]}},
                    {'data':dict(box,plays=True)},{'data':dict(box,players=[None])}]:
            with self.subTest(shape=type(bad).__name__):
                with self.assertRaises(ValueError):d.response_payload('get_game',bad)
    def test_plays_wrapper_not_assumed(self):
        wrapped={'data':{'plays':[],'count':0,'next_offset':None}}
        self.assertIs(d.response_payload('get_plays',wrapped),wrapped)
    def test_cache_replay_preserves_bytes_reservation_and_never_calls_network(self):
        import hashlib
        import base64
        manifest=d.local_manifest(d.MANIFEST_SHA256)
        first=manifest['games'][0];box,_=fixture(first['game_id'])
        box['game']['home']['abbrev']=first['home'];box['game']['away']['abbrev']=first['away']
        box['game']['date']=first['date'];box['game']['starts_at']=first['date']+'T23:00:00Z'
        box['plays']=595
        raw=json.dumps({'data':box},indent=3).encode()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pilot.sqlite3';store=Store(path)
            ids=[g['game_id'] for g in manifest['games']]
            transport=Mock();response=Mock(status_code=200)
            response.iter_content.return_value=[raw];transport.return_value=response
            pilot=d.Pilot(store,ids,free_balance=500,test_transport=transport)
            self.assertEqual(pilot.fetch('get_game',ids[0]),box)
            saved=store.rows('dunk_response')[0]['payload']
            self.assertEqual(base64.b64decode(saved['raw_base64']),raw)
            self.assertEqual(saved['sha256'],hashlib.sha256(raw).hexdigest())
            # Second fetch uses the original cache and does not reserve again.
            self.assertEqual(pilot.fetch('get_game',ids[0]),box)
            self.assertEqual(transport.call_count,1)
            before=path.read_bytes()
            with patch.object(d,'WalletTransport',side_effect=AssertionError('No transport')), patch.object(d.requests,'Session',side_effect=AssertionError('No network')):
                report=d.replay_database(path,manifest,'2026-11-01')
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(report['reserved_credits'],5)
            self.assertEqual(report['reservations'],1)
            self.assertEqual(report['saved_responses'],1)
            self.assertEqual(report['games'][0]['reported_plays'],595)
            self.assertFalse(report['continuation_enabled'])
            # No provider/player/raw data escapes the safe output.
            self.assertNotIn('raw_base64',json.dumps(report))
            self.assertNotIn('player_id',json.dumps(report))
    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'missing.sqlite3'
            with self.assertRaises(ValueError):d.replay_database(path,{},'2026-11-01')
            self.assertFalse(path.exists())
    def test_crlf_is_rejected_not_normalized(self):
        raw=(Path(d.__file__).parent/'validation/PHASE10_REQUEST_MANIFEST.json').read_bytes()
        self.assertNotIn(b'\r',raw)
        with patch.object(Path,'read_bytes',return_value=raw.replace(b'\n',b'\r\n')):
            with self.assertRaises(ValueError):d.local_manifest(d.MANIFEST_SHA256)

    def test_live_cache_reuse_retains_original_five_credit_attempt(self):
        import os
        manifest=d.local_manifest(d.MANIFEST_SHA256)
        box,_=fixture(manifest['games'][0]['game_id'])
        raw=json.dumps({'data':box}).encode()
        response=Mock(status_code=200);response.iter_content.return_value=[raw]
        session=Mock();session.post.return_value=response
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'DUNKAPI_API_KEY':'SYNTHETIC-ONLY'}):
            store=Store(Path(folder)/'pilot.sqlite3')
            transport=d.WalletTransport(manifest,wallet_balance=500,funding_confirmed=True,enabled=True,session=session)
            pilot=d.Pilot(store,transport.ids,wallet_transport=transport)
            pilot.fetch('get_game',transport.ids[0])
            events=store.rows()
            self.assertEqual(pilot.fetch('get_game',transport.ids[0]),box)
            self.assertEqual(store.rows(),events)
            self.assertEqual(session.post.call_count,1)
            self.assertEqual(sum(r['payload']['cost'] for r in store.rows('dunk_attempt')),5)

    def test_invalid_cached_wrapper_fails_without_replacement_or_new_charge(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'pilot.sqlite3')
            response=Mock(status_code=200);response.iter_content.return_value=[b'{"data": null}']
            transport=Mock(return_value=response)
            pilot=d.Pilot(store,['100','101','102','103','104'],free_balance=500,test_transport=transport)
            with self.assertRaises(ProviderError):pilot.fetch('get_game','100')
            before=store.rows()
            with self.assertRaises(ValueError):pilot.fetch('get_game','100')
            self.assertEqual(store.rows(),before)
            self.assertEqual(transport.call_count,1)
            self.assertEqual(len(store.rows('dunk_response')),1)

class OneRequestTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        import base64,hashlib
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.manifest=d.local_manifest(d.MANIFEST_SHA256)
        (self.root/'identity.json').write_text(json.dumps({'pilot':'phase10-five-games','manifest_sha256':d.MANIFEST_SHA256}))
        self.store=Store(self.root/'pilot.sqlite3')
        ids=[g['game_id'] for g in self.manifest['games']]
        self.store.append('dunk_pilot','phase10-five-games',{'game_ids':ids,'ceiling':100,'test_only':False,'costs':d.COSTS,'funding_source':'existing_wallet'})
        expected=self.manifest['games'][0];box,_=fixture(ids[0])
        box['game'].update(date=expected['date'],starts_at=expected['date']+'T23:00:00Z')
        box['game']['home']['abbrev']=expected['home'];box['game']['away']['abbrev']=expected['away']
        raw=json.dumps({'data':box}).encode();params={'game_id':ids[0]}
        key=digest({'endpoint':'get_game','params':params})
        self.store.append('dunk_attempt',key,{'cost':5,'endpoint':'get_game','params':params,'test_only':False})
        self.store.append('dunk_response',key,{'provider':'DunkAPI','test_only':False,'endpoint':'get_game','request':params,'retrieved_at':datetime.now(timezone.utc).isoformat(),'raw_base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()})
        self.original=self.store.rows()
        self.args=SimpleNamespace(execute=True,confirm_wallet=495,confirm_no_replenishment=True,confirm_exclusive_use=True,confirm_manifest=d.MANIFEST_SHA256)
        self.session=Mock();self.response=Mock(status_code=200)
        self.response.iter_content.return_value=[b'{"data":{"plays":[],"count":0,"next_offset":1000}}']
        self.session.post.return_value=self.response
        for patcher in [patch.object(d,'secure_acl'),patch.object(d.requests,'Session',return_value=self.session),patch.dict(d.os.environ,{'DUNKAPI_API_KEY':'SYNTHETIC-ONLY'}),patch('builtins.print')]:
            patcher.start();self.addCleanup(patcher.stop)
    def run_one(self):return d.execute_one(self.args,self.root)
    def assert_stopped_once(self):
        self.assertEqual(self.session.post.call_count,1)
        self.assertEqual(self.store.rows()[:len(self.original)],self.original)
        self.assertEqual(sum(r['payload']['cost'] for r in self.store.rows('dunk_attempt')),15)
        with self.assertRaises(ValueError):self.run_one()
        self.assertEqual(self.session.post.call_count,1)
    def test_one_call_even_with_next_page_and_rerun_blocked(self):
        self.assertEqual(self.run_one(),0);self.assert_stopped_once()
        call=self.session.post.call_args
        self.assertEqual(call.args[0],d.HOST+'get_plays')
        self.assertEqual(call.kwargs['json'],{'game_id':'401809243','limit':1000,'offset':0})
    def test_timeout_reservation_survives_no_retry(self):
        self.session.post.side_effect=requests.Timeout('SYNTHETIC-SECRET')
        with self.assertRaises(ProviderError):self.run_one()
        self.assert_stopped_once()
    def test_http_failure_preserved_no_retry(self):
        self.response.status_code=429
        with self.assertRaises(ProviderError):self.run_one()
        self.assert_stopped_once()
        self.assertEqual(len(self.store.rows('dunk_response')),2)
    def test_invalid_json_preserved_no_retry(self):
        self.response.iter_content.return_value=[b'not-json-fixture']
        with self.assertRaises(ProviderError):self.run_one()
        self.assert_stopped_once()
        self.assertEqual(len(self.store.rows('dunk_response')),2)
        self.assertFalse(d.plays_structure(self.root)['json_valid'])
    def test_no_execute_no_wallet_no_funding_no_requests(self):
        for field,value in [('execute',False),('confirm_wallet',500),('confirm_no_replenishment',False),('confirm_exclusive_use',False),('confirm_manifest','changed')]:
            args=copy.copy(self.args);setattr(args,field,value)
            with self.assertRaises(ValueError):d.execute_one(args,self.root)
        self.session.post.assert_not_called();self.assertEqual(self.store.rows(),self.original)
    def test_missing_original_cache_blocks_without_fetch(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(Exception):d.execute_one(self.args,Path(folder))
            self.assertFalse((Path(folder)/'pilot.sqlite3').exists())
        self.session.post.assert_not_called()
    def test_diagnostic_read_only_safe_and_pagination_not_accepted(self):
        self.run_one();before=(self.root/'pilot.sqlite3').read_bytes()
        report=d.plays_structure(self.root)
        self.assertEqual((self.root/'pilot.sqlite3').read_bytes(),before)
        self.assertEqual(self.session.post.call_count,1)
        self.assertEqual(report['reserved_credits'],15)
        self.assertTrue(report['locations'][1]['additional_page_indicated'])
        self.assertFalse(report['interpretation_validated'])
        self.assertNotIn('raw_base64',json.dumps(report))
    def test_transport_rejects_second_call_other_game_and_pagination(self):
        t=d.WalletTransport(self.manifest,wallet_balance=495,enabled=True,funding_confirmed=True,session=self.session,one_request=True)
        for endpoint,body in [('get_game',{'game_id':'401809243'}),('get_plays',{'game_id':'401809236','limit':1000,'offset':0}),('get_plays',{'game_id':'401809243','limit':1000,'offset':1000})]:
            with self.assertRaises(ProviderError):t(d.HOST+endpoint,json=body)
        self.session.post.assert_not_called()
        params={'game_id':'401809243','limit':1000,'offset':0}
        t(d.HOST+'get_plays',json=params)
        with self.assertRaises(ProviderError):t(d.HOST+'get_plays',json=params)
        self.assertEqual(self.session.post.call_count,1)
    def test_missing_key_blocks_without_new_reservation(self):
        with patch.dict(d.os.environ,{},clear=True):
            with self.assertRaises(ProviderError):self.run_one()
        self.assertEqual(self.store.rows(),self.original);self.session.post.assert_not_called()
