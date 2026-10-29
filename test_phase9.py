"""Synthetic diagnostics only: no account or paid endpoint is contacted."""
import copy
import json
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch
import phase8_access as access
from phase5_providers import ProviderError
import test_phase8


class Phase9Tests(unittest.TestCase):
    def setUp(self):
        f = test_phase8.Phase8AccessTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.f = f
        self.row = f.subs['data'][0]
        self.row.update(tier='paid', status='active', current_period_end=(f.now+timedelta(days=10)).isoformat(), cancel_at_period_end=False)
        f.plans['data']['tiers']['paid'] = {'rate_limit':60,'rate_limit_window_seconds':60}
    def report(self):
        return access.entitlement_report(self.f.plans,self.f.subs,self.f.now)
    def test_active_paid_renewal_does_not_authorize_plays(self):
        r=self.report();self.assertEqual(r['renewal_status'],'renewal_reported_not_guaranteed')
        self.assertEqual(r['documented_requests_per_minute'],60)
        self.assertFalse(r['paid_endpoints_enabled']);self.assertFalse(r['endpoint_access_tested'])
    def test_scheduled_cancellation_not_immediate_expiry(self):
        self.row['cancel_at_period_end']=True
        r=self.report();self.assertEqual(r['renewal_status'],'cancellation_scheduled')
        self.assertEqual(r['entitlement_state'],'active_reported')
    def test_expired_period_blocks_authorization(self):
        self.row['current_period_end']=self.f.now.isoformat()
        self.assertEqual(self.report()['entitlement_state'],'expired_period')
        with self.assertRaises(ValueError):self.f.auth()
    def test_canceled_blocks_even_future_period(self):
        self.row['status']='canceled'
        self.assertEqual(self.report()['entitlement_state'],'inactive_or_trial')
        with self.assertRaises(ValueError):self.f.auth()
    def test_trial_is_not_activated_or_authorized(self):
        self.row['status']='trialing'
        with self.assertRaises(ValueError):self.f.auth()
        self.f.get.assert_not_called()
    def test_missing_period_explicitly_unverified(self):
        del self.row['current_period_end']
        self.assertEqual(self.report()['entitlement_state'],'active_period_unverified')
        self.assertEqual(self.report()['renewal_status'],'unknown')
    def test_naive_and_malformed_period_fail_closed(self):
        for value in ['2027-02-01T00:00:00','secret-string',{},False]:
            self.row['current_period_end']=value
            with self.assertRaises(ValueError):self.f.auth()
            self.assertIsNone(self.report()['current_period_end'])
    def test_unknown_values_are_not_echoed(self):
        self.row.update(tier='secret-tier',status='private-status',email='private-mail',api_key='secret-key',payment_url='private-url',cancel_at_period_end='secret-cancel')
        result=json.dumps(self.report())
        for secret in ['secret-tier','private-status','private-mail','secret-key','private-url','secret-cancel']:
            self.assertNotIn(secret,result)
        with self.assertRaises(ValueError):self.f.auth()
    def test_nested_private_values_are_not_echoed(self):
        self.row.update(tier={'api_key':'secret'},status=['secret'])
        self.assertNotIn('secret',json.dumps(self.report()))
    def test_other_sport_does_not_grant_nba(self):
        self.row['sport']='nfl'
        self.assertEqual(self.report()['nba_subscription_count'],0)
        with self.assertRaises(ValueError):self.f.auth()
    def test_duplicate_nba_is_ambiguous(self):
        self.f.subs['data'].append(copy.deepcopy(self.row))
        self.assertEqual(self.report()['entitlement_state'],'unverified')
    def test_invalid_subscription_container_rejected(self):
        for value in [None,{},['private']]:
            with self.assertRaises(ValueError):access.entitlement_report({}, {'data':value},self.f.now)
    def test_lineups_never_pretip(self):
        for tier in ['free','paid','paid_plus','all_access_v3']:
            self.row['tier']=tier
            self.assertFalse(self.report()['lineups_available_before_tip'])
    def test_no_unknown_quota_inference(self):
        self.f.plans['data']['tiers']['paid']['rate_limit']='secret'
        r=self.report();self.assertIsNone(r['documented_requests_per_minute']);self.assertIsNone(r['remaining_account_quota'])
    def test_401_403_are_redacted_no_retry(self):
        for status in [401,403]:
            self.f.now+=timedelta(seconds=14)
            self.f.get.return_value=self.f.response({'api_key':'private-body'},status=status)
            with self.assertRaisesRegex(ProviderError,'HTTP '+str(status)):
                self.f.client.inspect_subscriptions()
        self.assertEqual(self.f.get.call_count,2)
    def test_absolute_host_and_mutation_paths_rejected(self):
        for path in ['https://api.balldontlie.io.evil.test/v1/teams','//api.balldontlie.io/v1/teams','/account/v1/subscriptions/upgrade','/account/v1/api-key/rotate']:
            with self.assertRaises(ProviderError):self.f.client._request(path)
        self.f.get.assert_not_called()
    def test_local_inspect_uses_exactly_two_reads(self):
        self.f.get.side_effect=[self.f.response(self.f.plans),self.f.response(self.f.subs)]
        with patch('sys.argv',['phase8_access.py','inspect','--state','unused','--enable-read-only']), patch.object(access,'ReadOnlyBDL',return_value=self.f.client), patch.object(access,'Store',return_value=self.f.store), patch.object(access.time,'sleep',side_effect=lambda _:setattr(self.f,'now',self.f.now+timedelta(seconds=13))), patch('builtins.print') as output:
            access.main()
        self.assertEqual(self.f.get.call_count,2)
        self.assertEqual(json.loads(output.call_args.args[0])['observed_tier'],'paid')
    def test_equal_numeric_id_is_not_a_crosswalk(self):
        with self.assertRaises(ValueError):access.validate_mapping({},['1'],['1'],'BOS',self.f.now)
    def test_unknown_roster_team_is_rejected(self):
        with self.assertRaises(ValueError):access.player_identities([{'id':1,'first_name':'Test','last_name':'Only','team':{'id':2}}],3)

    def test_failed_refresh_revokes_previous_local_grant(self):
        self.f.auth()
        self.row['status']='canceled'
        with self.assertRaises(ValueError):self.f.auth()
        self.assertIsNone(self.f.client.entitlement)
        with self.assertRaises(ProviderError):self.f.client.page('/v1/teams')
        self.f.get.assert_not_called()
    def test_hidden_prompt_refuses_noninteractive_input(self):
        with patch('sys.argv',['phase8_access.py','inspect','--state','unused','--enable-read-only','--prompt-key']), patch.dict(access.os.environ,{},clear=True), patch.object(access.sys.stdin,'isatty',return_value=False), patch.object(access.getpass,'getpass') as prompt:
            with self.assertRaises(SystemExit):access.main()
        prompt.assert_not_called()
