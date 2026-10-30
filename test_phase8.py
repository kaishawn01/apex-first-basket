import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import requests
import phase8_access as access
import phase8_fixture as fixture
from phase5_store import Store
from phase5_providers import ProviderError
from phase6_journal import Journal


class Phase8AccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2027,1,2,21,tzinfo=timezone.utc)
        self.store = Store(Path(self.tmp.name)/'state.db', clock=lambda:self.now)
        self.get = Mock(return_value=self.response({'data':[]}))
        self.client = access.ReadOnlyBDL(self.store, 'synthetic-test-token', enabled=True, get=self.get)
        self.plans = {'data':{'sport':'nba','tiers':{'free':{'price':0,'rate_limit':5,'rate_limit_window_seconds':60}}}}
        self.subs = {'data':[{'sport':'nba','tier':'free','status':None}]}
        self.row = {'id':123,'date':'2027-01-02','datetime':'2027-01-02T21:10:00Z','status_state':'scheduled',
                    'postponed':False,'period':0,'home_team_score':0,'visitor_team_score':0,
                    'home_team':{'id':2,'abbreviation':'BOS'},'visitor_team':{'id':20,'abbreviation':'NYK'}}
    def response(self, payload, status=200, headers=None):
        r=Mock(status_code=status, headers=headers or {})
        r.iter_content.return_value=[json.dumps(payload).encode()];return r
    def auth(self):return self.client.verify_entitlement(self.plans,self.subs)
    def game(self):return access.scheduled_game(self.row,self.now.isoformat(),self.now)
    def test_account_summary_never_exports_credentials(self):
        self.subs.update(api_key='do-not-export',email='private');r=self.auth()
        self.assertNotIn('do-not-export',json.dumps(r));self.assertFalse(r['paid_endpoints_enabled'])
    def test_active_allstar_does_not_enable_paid_endpoints(self):
        self.subs['data'][0].update(tier='paid',status='active');self.auth()
        with self.assertRaises(ProviderError):self.client.page('/v1/plays')
        self.get.assert_not_called()
    def test_unknown_and_trial_plans_blocked(self):
        for tier,status in [('paid_plus','trialing'),('unknown','active'),('paid','past_due'),('paid',None)]:
            self.subs['data'][0].update(tier=tier,status=status)
            with self.assertRaises(ValueError):self.auth()
    def test_changed_free_price_or_quota_blocks(self):
        self.plans['data']['tiers']['free']['price']=.01
        with self.assertRaises(ValueError):self.auth()
        self.plans['data']['tiers']['free'].update(price=0,rate_limit=1)
        with self.assertRaises(ValueError):self.auth()
    def test_duplicate_subscription_rejected(self):
        self.subs['data']*=2
        with self.assertRaises(ValueError):self.auth()
    def test_no_fresh_entitlement_no_data_request(self):
        with self.assertRaises(ProviderError):self.client.page('/v1/games')
        self.auth();self.now+=timedelta(hours=2)
        with self.assertRaises(ProviderError):self.client.page('/v1/games')
        self.get.assert_not_called()
    def test_global_disable_and_missing_key(self):
        with patch.dict(os.environ,{'APEX_AUTOMATION_DISABLED':'true'}):
            with self.assertRaises(ProviderError):self.client.inspect_plans()
        self.client.key=''
        with self.assertRaises(ProviderError):self.client.inspect_plans()
        self.get.assert_not_called()
    def test_no_mutating_billing_endpoints(self):
        for path in ['/account/v1/me','/account/v1/billing/checkout','/account/v1/signup','/v1/players/active','https://evil.test']:
            with self.assertRaises(ProviderError):self.client._request(path)
        self.get.assert_not_called()
    def test_requests_are_get_only_no_redirects(self):
        self.client.inspect_plans();kwargs=self.get.call_args.kwargs
        self.assertFalse(kwargs['allow_redirects']);self.assertEqual(kwargs['timeout'],15)
        self.assertEqual(kwargs['headers']['Authorization'],'Bearer synthetic-test-token')
    def test_rate_budget_persists_across_instances(self):
        self.client.inspect_plans();other=access.ReadOnlyBDL(self.store,'synthetic',enabled=True,get=self.get)
        with self.assertRaises(ProviderError):other.inspect_plans()
        self.now+=timedelta(seconds=13);other.inspect_plans();self.assertEqual(self.get.call_count,2)
    def test_day_budget_stop_and_timeout_counted(self):
        self.get.side_effect=requests.Timeout('secret token must not escape')
        with self.assertRaises(ProviderError) as e:self.client.inspect_plans()
        self.assertNotIn('secret',str(e.exception));self.assertEqual(self.store.state('p8:bdl:budget')['attempts'],1)
        self.now+=timedelta(seconds=13)
        self.store.set_state('p8:bdl:budget',{'day':'2027-01-02','attempts':20})
        with self.assertRaises(ProviderError):self.client.inspect_plans()
        self.assertEqual(self.get.call_count,1)
    def test_429_cooldown_no_automatic_retries(self):
        self.get.return_value=self.response({},429,{'Retry-After':'120'})
        with self.assertRaises(ProviderError):self.client.inspect_plans()
        self.now+=timedelta(seconds=60)
        with self.assertRaises(ProviderError):self.client.inspect_plans()
        self.get.assert_called_once();self.get.return_value.close.assert_called_once()
    def test_redirect_and_auth_errors_never_upgrade(self):
        for status in (301,401,402,403,500):
            self.now+=timedelta(seconds=13);self.get.return_value=self.response({},status)
            with self.assertRaises(ProviderError):self.client.inspect_plans()
        self.assertEqual(self.get.call_count,5)
    def test_oversize_response_rejected(self):
        self.get.return_value.iter_content.return_value=[b'x'*(access.MAX_RESPONSE+1)]
        with self.assertRaises(ProviderError):self.client.inspect_plans()
    def test_partial_page_is_not_complete_roster(self):
        self.auth();self.get.return_value=self.response({'data':[],'meta':{'next_cursor':123}})
        r=self.client.page('/v1/players',{'team_ids[]':2});self.assertFalse(r['complete'])
    def test_invalid_params_rejected_before_request(self):
        self.auth()
        for params in ({'api_key':'secret'},{'per_page':1000},{'cursor':True},{'dates[]':'bad-date'}):
            with self.assertRaises((ProviderError,ValueError)):self.client.page('/v1/games',params)
        self.get.assert_not_called()
    def test_realistic_scheduled_game_identity_and_status(self):
        r=self.game();self.assertEqual(r['game_id'],'bdl_123');self.assertFalse(r['forecast_adapter_ready'])
        self.assertEqual(r['lineup_status'],'unknown');self.assertFalse(r['injuries_checked'])
    def test_postponed_started_delayed_unknown_rejected(self):
        for status in ('postponed','in_progress','final','delayed','unknown','suspended'):
            self.row['status_state']=status
            with self.assertRaises(ValueError):self.game()
    def test_conflicting_status_or_dates_rejected(self):
        original=copy.deepcopy(self.row)
        for field,value in [('period',1),('home_team_score',2),('postponed',True),('date','2027-01-03'),('datetime','2027-01-02')]:
            self.row=copy.deepcopy(original);self.row[field]=value
            with self.assertRaises(ValueError):self.game()
    def test_late_or_stale_evidence_rejected(self):
        self.now+=timedelta(minutes=10)
        with self.assertRaises(ValueError):self.game()
        with self.assertRaises(ValueError):access.scheduled_game(self.row,(self.now-timedelta(minutes=2)).isoformat(),self.now)
    def test_dst_dates_use_eastern_not_utc_day(self):
        self.now=datetime(2027,3,15,0,tzinfo=timezone.utc)
        self.row.update(date='2027-03-14',datetime='2027-03-15T00:10:00Z')
        self.assertEqual(self.game()['date'],'2027-03-14')
    def test_duplicate_team_or_player_identity(self):
        self.row['visitor_team']=self.row['home_team']
        with self.assertRaises(ValueError):self.game()
        r={'id':1,'first_name':'A','last_name':'B','team':{'id':2}}
        with self.assertRaises(ValueError):access.player_identities([r,r],2)
        with self.assertRaises(ValueError):access.player_identities([r],3)
        self.assertFalse(access.player_identities([r],2)[0]['active_roster_verified'])
    def test_cross_provider_ids_require_explicit_mapping(self):
        with self.assertRaises(ValueError):access.validate_mapping({},['1'],['1'],'BOS',self.now)
        m={'schema':1,'provider':'BALLDONTLIE','target_namespace':'ESPN','team':'BOS','reviewed':True,
           'evidence_reference':'SYNTHETIC TEST ONLY','retrieved_at':self.now.isoformat(),
           'players':[{'provider_id':1,'apex_id':99}]}
        self.assertEqual(access.validate_mapping(m,['1'],['99'],'BOS',self.now),{'1':'99'})
        with self.assertRaises(ValueError):access.validate_mapping(m,['1'],['99'],'NYK',self.now)
        with self.assertRaises(ValueError):access.validate_mapping(m,['1'],['99'],'BOS',self.now+timedelta(days=2))
    def test_permissions_not_inferred_from_public_access(self):
        e={'schema':1,'provider':'fixture','reviewed':True,'test_only':True,'evidence_reference':'SYNTHETIC ONLY',
           'reviewed_at':self.now.isoformat(),'expires_at':(self.now+timedelta(days=1)).isoformat(),
           'scopes':['model_training'],'upstream_review_complete':True}
        access.validate_source_evidence(e,'fixture',['model_training'],self.now,test=True)
        for change in ({'upstream_review_complete':False},{'reviewed':'true'},{'scopes':[]},{'evidence_reference':''}):
            with self.assertRaises(ValueError):access.validate_source_evidence({**e,**change},'fixture',['model_training'],self.now,test=True)
        with self.assertRaises(ValueError):access.validate_source_evidence(e,'fixture',['model_training'],self.now)
        with self.assertRaises(ValueError):access.validate_source_evidence(e,'fixture',['model_training'],self.now+timedelta(days=2),test=True)


class Phase8PipelineTests(unittest.TestCase):
    def test_independent_restart_preserves_frozen_model_and_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.json';r=fixture.exercise(path,'generate')
            original=Journal(path).rows('prediction');p=original[0]['payload']
            self.assertEqual(p['model_version'],'3.0.6');self.assertEqual(p['seed'],3000);self.assertEqual(p['trials'],2000)
            self.assertTrue(p['test_only']);self.assertEqual(r['live_provider_calls'],0)
            self.assertEqual(fixture.exercise(path,'generate')['generated'],0)
            self.assertEqual(fixture.exercise(path,'grade')['graded'],1)
            self.assertEqual(Journal(path).rows('prediction'),original)
            for probs in p['forecasts'].values():self.assertAlmostEqual(sum(probs.values()),1)
            corrupted=json.loads(path.read_text());corrupted['events'][0]['created_at']='2020-01-01T00:00:00Z';path.write_text(json.dumps(corrupted))
            with self.assertRaises(ValueError):Journal(path).read()
    def test_new_ui_no_network(self):
        from streamlit.testing.v1 import AppTest
        with patch.object(requests,'get',side_effect=AssertionError('No requests on render')):
            at=AppTest.from_string('import phase8_ui; phase8_ui.render()').run(timeout=20)
            self.assertFalse(at.exception)
            self.assertTrue(any('BALLDONTLIE' in x.value for x in at.info))

if __name__=='__main__':unittest.main()
