"""Read-only BDL diagnostics. No forecast adapter or paid endpoint is enabled.

The public BDL terms allow analytical use, but access entitlement, identity and
coverage are separate checks. Provider IDs never become ESPN IDs implicitly.
"""
import argparse
import json
import os
from datetime import datetime, timezone, timedelta, date
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import first_basket_engine as eng
from phase4_data import digest
from phase5_providers import ProviderError, stamp
from phase5_store import Store

BASE = 'https://api.balldontlie.io'
TERMS = 'https://www.balldontlie.io/terms.html'
DOCS = 'https://docs.balldontlie.io/'
ET = ZoneInfo('America/New_York')
FREE_PATHS = {'/v1/teams', '/v1/players', '/v1/games'}
ACCOUNT_PATHS = {'/account/v1/plans/nba', '/account/v1/subscriptions'}
DAILY_LIMIT = 20
MAX_RESPONSE = 2_000_000


def positive_id(value):
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise ValueError('Invalid provider identity')
    return str(int(value))


def account_summary(plans, subscriptions, now):
    """Allowlisted output only: never include emails, keys or billing URLs."""
    plan = plans.get('data', {})
    free = plan.get('tiers', {}).get('free', {})
    entries = [s for s in subscriptions.get('data', []) if s.get('sport') == 'nba']
    if plan.get('sport') != 'nba' or free.get('price') != 0 or type(free.get('price')) not in (int, float):
        raise ValueError('Zero-cost NBA plan could not be verified')
    if (len(entries) != 1 or entries[0].get('tier') not in ('free', 'paid', 'paid_plus', 'all_access_v3')
            or entries[0].get('status') not in (None, 'active')):
        raise ValueError('NBA entitlement absent, trialing, inactive or ambiguous')
    if entries[0]['tier'] != 'free' and entries[0].get('status') != 'active':
        raise ValueError('Existing subscription is not active')
    rate, window = free.get('rate_limit'), free.get('rate_limit_window_seconds')
    if type(rate) is not int or rate < 5 or type(window) is not int or window != 60:
        raise ValueError('Free quota changed; review required')
    return {'provider': 'BALLDONTLIE', 'checked_at': now.isoformat(),
            'observed_tier': entries[0]['tier'], 'status': entries[0].get('status'),
            'free_price_verified': True, 'allowed_paths': sorted(FREE_PATHS),
            'request_spacing_seconds': 13, 'daily_attempt_limit': DAILY_LIMIT,
            'paid_endpoints_enabled': False, 'billing_changes_allowed': False,
            'remaining_account_quota': None,
            'limitations': ['Subscription renewal/overage settings not exposed here',
                            'Free endpoints do not supply opening plays or confirmed starters']}


class ReadOnlyBDL:
    """One attempt per call, local persistent quota and cooldown, no redirects.

Use one shared Store per credential on a single machine. Cloud use is not wired
in: it needs durable shared quota reservation and explicit deployment review.
"""
    def __init__(self, store, key, *, enabled=False, get=None):
        self.store, self.key, self.enabled = store, key, enabled
        self.get = get or requests.get
        self.entitlement = None

    def _request(self, path, params=None):
        if os.environ.get('APEX_AUTOMATION_DISABLED') == 'true' or self.enabled is not True:
            raise ProviderError('Read-only access disabled')
        if not isinstance(self.key, str) or not self.key.strip():
            raise ProviderError('No secure BALLDONTLIE credential available')
        if path not in FREE_PATHS | ACCOUNT_PATHS:
            raise ProviderError('Endpoint is not on the zero-cost GET allowlist')
        params = params or {}
        permitted = {'/v1/teams': set(), '/v1/players': {'team_ids[]', 'cursor', 'per_page'},
                     '/v1/games': {'dates[]', 'cursor', 'per_page'}}.get(path, set())
        if set(params) - permitted:
            raise ProviderError('Unsupported query fields')
        if 'per_page' in params and (type(params['per_page']) is not int or not 1 <= params['per_page'] <= 100):
            raise ProviderError('Invalid page size')
        if 'cursor' in params:
            positive_id(params['cursor'])
        if 'team_ids[]' in params:
            positive_id(params['team_ids[]'])
        if 'dates[]' in params:
            date.fromisoformat(params['dates[]'])
        now = self.store.clock()
        if now.tzinfo is None:
            raise ProviderError('Aware clock required')
        if path in FREE_PATHS:
            e = self.entitlement
            if not e or not 0 <= (now - stamp(e['checked_at'])).total_seconds() <= 3600:
                raise ProviderError('Fresh read-only entitlement inspection required')
        lease = self.store.acquire('p8:bdl:http', 90)
        if not lease:
            raise ProviderError('BALLDONTLIE diagnostic already running')
        try:
            today = now.astimezone(ET).date().isoformat()
            budget = self.store.state('p8:bdl:budget', {})
            if now.timestamp() < self.store.state('p8:bdl:next_allowed', 0):
                raise ProviderError('BALLDONTLIE cooldown active; no automatic retry')
            if budget.get('day') != today:
                budget = {'day': today, 'attempts': 0}
            if budget['attempts'] >= DAILY_LIMIT:
                raise ProviderError('Daily diagnostic request budget exhausted')
            # Persist before HTTP: crashes/timeouts spend their attempt.
            self.store.set_state('p8:bdl:budget', {**budget, 'attempts': budget['attempts'] + 1})
            self.store.set_state('p8:bdl:next_allowed', now.timestamp() + 13)
            token = 'Bearer ' + self.key if path in ACCOUNT_PATHS else self.key
            try:
                response = self.get(BASE + path, params=params,
                                    headers={'Authorization': token, 'Accept': 'application/json'},
                                    timeout=15, allow_redirects=False, stream=True)
            except requests.RequestException:
                raise ProviderError('BALLDONTLIE transport failed; attempt counted') from None
            try:
                if response.status_code == 429:
                    retry = response.headers.get('Retry-After', '300')
                    try:
                        until = now + timedelta(seconds=int(retry)) if str(retry).isdigit() else parsedate_to_datetime(retry)
                        if until.tzinfo is None:
                            raise ValueError()
                    except (ValueError, TypeError, OverflowError):
                        until = now + timedelta(seconds=300)
                    self.store.set_state('p8:bdl:next_allowed', max(now.timestamp()+30, until.timestamp()))
                    raise ProviderError('BALLDONTLIE rate limit; retry time persisted')
                if response.status_code != 200:
                    raise ProviderError('BALLDONTLIE HTTP ' + str(response.status_code) + '; no upgrade or retry attempted')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_RESPONSE:
                        raise ProviderError('BALLDONTLIE response size limit')
                    chunks.append(chunk)
                payload = json.loads(b''.join(chunks))
                if not isinstance(payload, dict):
                    raise ValueError()
                return payload
            except (requests.RequestException, ValueError, TypeError):
                raise ProviderError('BALLDONTLIE response invalid; nothing accepted') from None
            finally:
                response.close()
        finally:
            self.store.release(lease)

    def inspect_plans(self):
        return self._request('/account/v1/plans/nba')

    def inspect_subscriptions(self):
        return self._request('/account/v1/subscriptions')

    def verify_entitlement(self, plans, subscriptions):
        self.entitlement = account_summary(plans, subscriptions, self.store.clock())
        return self.entitlement

    def page(self, path, params=None):
        if path not in FREE_PATHS:
            raise ProviderError('Only free data pages are supported')
        payload = self._request(path, params)
        if not isinstance(payload.get('data'), list):
            raise ProviderError('Invalid data page')
        cursor = payload.get('meta', {}).get('next_cursor')
        if cursor is not None:
            positive_id(cursor)
        return {'provider': 'BALLDONTLIE', 'retrieved_at': self.store.clock().isoformat(),
                'sha256': digest(payload), 'payload': payload, 'complete': cursor is None,
                'next_cursor': cursor, 'terms_url': TERMS}


def scheduled_game(row, retrieved_at, now):
    """Strict diagnostic normalization. Not connected to the ESPN forecast runner."""
    at = stamp(retrieved_at)
    if not 0 <= (now-at).total_seconds() <= 60:
        raise ValueError('Stale schedule evidence')
    gid = positive_id(row['id'])
    start = stamp(row['datetime'])  # Never infer a time from date-only or display text.
    if row.get('date') != start.astimezone(ET).date().isoformat():
        raise ValueError('Game date/start disagreement')
    if (row.get('status_state') != 'scheduled' or row.get('postponed') is not False
            or type(row.get('period')) is not int or row['period'] != 0
            or any(type(row.get(k)) is not int or row[k] != 0 for k in ('home_team_score', 'visitor_team_score'))
            or (start-now).total_seconds() < 30):
        raise ValueError('Game not safely pre-tip, rescheduled, or status unknown')
    teams = [row['home_team'], row['visitor_team']]
    if len({positive_id(t['id']) for t in teams}) != 2:
        raise ValueError('Duplicate team identities')
    names = [t['abbreviation'] for t in teams]
    if len(set(names)) != 2 or any(t not in eng.TEAMS for t in names):
        raise ValueError('Unknown or duplicate NBA teams')
    return {'provider': 'BALLDONTLIE', 'game_id': 'bdl_' + gid,
            'provider_game_id': gid, 'start_time': start.isoformat(), 'date': row['date'],
            'home': names[0], 'away': names[1], 'retrieved_at': at.isoformat(),
            'lineup_status': 'unknown', 'injuries_checked': False,
            'forecast_adapter_ready': False, 'source_hash': digest(row)}


def player_identities(rows, team_id):
    """General players endpoint is not evidence of active roster membership."""
    expected = positive_id(team_id); seen = set(); result = []
    for row in rows:
        pid = positive_id(row['id'])
        if pid in seen or positive_id(row['team']['id']) != expected:
            raise ValueError('Duplicate player or mismatched team')
        seen.add(pid)
        first, last = row.get('first_name'), row.get('last_name')
        if not isinstance(first, str) or not isinstance(last, str) or not (first.strip() and last.strip()):
            raise ValueError('Missing player name')
        result.append({'provider': 'BALLDONTLIE', 'provider_player_id': pid,
                       'player': first.strip() + ' ' + last.strip(), 'provider_team_id': expected,
                       'active_roster_verified': False, 'starter_status': 'unknown'})
    return result


def validate_mapping(mapping, provider_ids, apex_ids, team, now):
    """Operator-reviewed crosswalk; equal integers or names alone prove nothing."""
    if (mapping.get('schema') != 1 or mapping.get('provider') != 'BALLDONTLIE'
            or mapping.get('target_namespace') != 'ESPN' or mapping.get('team') != team
            or mapping.get('reviewed') is not True or not mapping.get('evidence_reference')
            or not 0 <= (now-stamp(mapping['retrieved_at'])).total_seconds() <= 86400):
        raise ValueError('Fresh identity crosswalk evidence required')
    rows = mapping.get('players', [])
    source = [positive_id(x['provider_id']) for x in rows]
    target = [positive_id(x['apex_id']) for x in rows]
    if (len(source) != len(set(source)) or len(target) != len(set(target))
            or set(source) != set(provider_ids) or not set(target) <= set(apex_ids)):
        raise ValueError('Identity mapping missing, duplicate or outside current roster')
    return dict(zip(source, target))


def validate_source_evidence(evidence, provider, scopes, now, *, test=False):
    """Validates a review record, not provider rights themselves. No blanket grants."""
    if (evidence.get('schema') != 1 or evidence.get('provider') != provider
            or evidence.get('test_only') is not test or evidence.get('reviewed') is not True
            or not isinstance(evidence.get('evidence_reference'), str)
            or not evidence['evidence_reference'].strip()
            or not isinstance(evidence.get('scopes'), list)
            or not set(scopes) <= set(evidence['scopes'])):
        raise ValueError('Applicable source evidence absent')
    if not stamp(evidence['reviewed_at']) <= now < stamp(evidence['expires_at']):
        raise ValueError('Source evidence expired or future dated')
    # A package license must not silently clear identified upstream restrictions.
    if evidence.get('upstream_review_complete') is not True:
        raise ValueError('Upstream permission review unresolved')
    return {'provider': provider, 'review_hash': digest(evidence), 'scopes': sorted(scopes)}


def main():
    p = argparse.ArgumentParser(description='Read-only access diagnostics; never generates a live forecast')
    p.add_argument('action', choices=['plans', 'subscriptions'])
    p.add_argument('--state', required=True, help='Same local state file for every invocation; do not reset quotas')
    p.add_argument('--enable-read-only', action='store_true')
    a = p.parse_args()
    client = ReadOnlyBDL(Store(Path(a.state)), os.environ.get('BALLDONTLIE_API_KEY'), enabled=a.enable_read_only)
    try:
        if a.action == 'plans':
            data = client.inspect_plans().get('data', {})
            # Print only approved plan metadata, never the entire response.
            result = {'sport': data.get('sport'), 'free': {k:data.get('tiers',{}).get('free',{}).get(k) for k in ('price','rate_limit','rate_limit_window_seconds')}}
        else:
            data = client.inspect_subscriptions().get('data', [])
            result = {'subscriptions': [{k:s.get(k) for k in ('sport','tier','status')} for s in data if s.get('sport')=='nba']}
        print(json.dumps(result, indent=2))
    except (ProviderError, ValueError, KeyError, TypeError):
        raise SystemExit('Read-only inspection failed or blocked. No billing action taken; inspect configuration and cooldown locally.') from None


if __name__ == '__main__':
    main()
