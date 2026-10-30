"""Quarantined DunkAPI pilot preparation. Live ingestion remains unavailable.

No source adapter is connected to the frozen model. Only injected synthetic
transport can execute until NBA upstream rights and free-balance evidence exist.
"""
import argparse
import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from phase4_data import canonical, digest
from phase5_providers import ProviderError, stamp
from phase5_store import Store
from phase8_access import positive_id

COSTS = {'get_game': 5, 'get_plays': 10}
LIMIT = 100
HOST = 'https://mcp.dunkapi.com/v1/'
MAX_BYTES = 2_000_000
BLOCKER = 'Live ingestion disabled: NBA upstream permission and free-only balance evidence unresolved'


class Pilot:
    """Fixed five-game manifest; durable reservations survive timeout/interruption.

    test_transport is solely for synthetic fixtures. There is intentionally no
    --enable-live switch or default HTTP transport in this preparation release.
    """
    def __init__(self, store, game_ids, *, free_balance, test_transport=None):
        self.store = store
        ids = [positive_id(x) for x in game_ids]
        if len(ids) != 5 or len(set(ids)) != 5:
            raise ValueError('Exactly five unique source-native game IDs required')
        if type(free_balance) is not int or free_balance < 0:
            raise ValueError('Explicit free-only balance required')
        self.cap = min(LIMIT, free_balance)
        self.ids, self.transport = ids, test_transport
        self.test_only = test_transport is not None
        config = {'game_ids': ids, 'ceiling': self.cap, 'test_only': self.test_only, 'costs': COSTS}
        # Immutable registration rejects changing games/caps to reset the budget.
        store.append('dunk_pilot', 'phase10-five-games', config)

    def fetch(self, endpoint, gid, offset=0):
        if not self.test_only:
            raise ProviderError(BLOCKER)
        if os.environ.get('APEX_AUTOMATION_DISABLED') == 'true':
            raise ProviderError('Automation disabled')
        gid = positive_id(gid)
        if endpoint not in COSTS or gid not in self.ids:
            raise ProviderError('Endpoint or game outside fixed pilot allowlist')
        if type(offset) is not int or offset < 0 or (endpoint == 'get_game' and offset != 0):
            raise ValueError('Invalid offset')
        params = {'game_id': gid}
        if endpoint == 'get_plays':
            params.update(limit=1000, offset=offset)
        key = digest({'endpoint':endpoint, 'params':params})
        lease = self.store.acquire('phase10:requests', 90)
        if not lease:
            raise ProviderError('Pilot already running')
        try:
            self.store.rows()  # Verify append-only hash chain before trusting cache/budget.
            cached = self.store.get('dunk_response', key)
            if cached:
                raw = base64.b64decode(cached['payload']['raw_base64'], validate=True)
                if hashlib.sha256(raw).hexdigest() != cached['payload']['sha256']:
                    raise ValueError('Raw source checksum mismatch')
                return json.loads(raw)
            if self.store.get('dunk_attempt', key):
                raise ProviderError('Prior attempt unresolved; no automatic repeat or refund')
            now = self.store.clock().timestamp()
            if now < self.store.state('phase10:next_allowed', 0):
                raise ProviderError('Pilot cooldown active')
            spent = sum(r['payload']['cost'] for r in self.store.rows('dunk_attempt'))
            if spent + COSTS[endpoint] > self.cap:
                raise ProviderError('Pilot credit ceiling reached; retain incomplete games')
            # Reservation commits before HTTP, even if the process subsequently dies.
            self.store.append('dunk_attempt', key, {'cost':COSTS[endpoint], 'endpoint':endpoint,
                              'params':params, 'test_only':True}, fence=lease)
            self.store.set_state('phase10:next_allowed', now + 7)
            try:
                response = self.transport(HOST + endpoint, json=params,
                    headers={'x-api-key':'SYNTHETIC-ONLY'}, timeout=15,
                    allow_redirects=False, stream=True)
            except requests.RequestException:
                raise ProviderError('Provider transport failure; reservation retained') from None
            try:
                if response.status_code == 429:
                    # Deliberately requires operator review; never auto-retry a charged query.
                    self.store.set_state('phase10:next_allowed', now + 3600)
                    raise ProviderError('Provider rate limit; stop and review cooldown')
                if response.status_code != 200:
                    raise ProviderError('Provider HTTP failure; body withheld; no retry')
                raw = bytearray(); deadline = time.monotonic() + 30
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES or time.monotonic() > deadline:
                        raise ProviderError('Response size/time bound exceeded')
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError('Object response required')
                self.store.append('dunk_response', key, {'provider':'DunkAPI', 'test_only':True,
                    'endpoint':endpoint, 'request':params, 'retrieved_at':self.store.clock().isoformat(),
                    'sha256':hashlib.sha256(raw).hexdigest(),
                    'raw_base64':base64.b64encode(raw).decode()}, fence=lease)
                return payload
            except (ValueError, TypeError, requests.RequestException):
                raise ProviderError('Invalid provider response; reservation retained') from None
            finally:
                response.close()
        finally:
            self.store.release(lease)

    def plays(self, gid):
        """Explicit terminal cursor required. Never treat a short page as complete."""
        pages = []; offset = 0
        for _ in range(10):  # Global credit ceiling normally stops much earlier.
            page = self.fetch('get_plays', gid, offset)
            rows = page.get('plays')
            if not isinstance(rows, list) or type(page.get('count')) is not int or page['count'] != len(rows):
                raise ValueError('Invalid pagination count')
            if 'next_offset' not in page:
                raise ValueError('Terminal pagination signal missing')
            pages.append(page)
            nxt = page['next_offset']
            if nxt is None:
                return pages
            if type(nxt) is not int or not rows or nxt != offset + len(rows):
                raise ValueError('Pagination gap, loop or invalid cursor')
            offset = nxt
        raise ValueError('Pagination bound reached')


    def run(self, target_day):
        """Bounded pilot orchestration. Source failures remain explicit, not dropped."""
        reports = []
        for gid in self.ids:
            try:
                box = self.fetch('get_game', gid)
                pages = self.plays(gid)
                reports.append({'game_id':gid,'status':'audited',
                                'audit':inspect_game(box,pages,target_day)})
            except ProviderError as error:
                reports.append({'game_id':gid,'status':'blocked','diagnostic':str(error)})
                break  # Respect provider/storage budget failure, no further automatic calls.
            except (ValueError, KeyError, TypeError):
                reports.append({'game_id':gid,'status':'invalid','diagnostic':'Source shape or integrity failed; raw response retained'})
        for gid in self.ids[len(reports):]:
            reports.append({'game_id':gid,'status':'not_attempted'})
        return {'test_only':self.test_only,'games':reports,
                'reserved_credits':sum(r['payload']['cost'] for r in self.store.rows('dunk_attempt')),
                'model_compatibility_established':False}


def inspect_game(box, pages, target_day, mapping=None):
    """Source-native audit, NOT model training rows. Missing facts never invented."""
    game = box['game']; gid = positive_id(game['game_id'])
    start = stamp(game['starts_at'])
    day = start.astimezone(ZoneInfo('America/New_York')).date()
    target = datetime.fromisoformat(target_day).date()
    if game['date'] != day.isoformat() or not 0 < (target-day).days <= 400:
        raise ValueError('Historical date outside strictly earlier frozen window')
    if game.get('status') != 'final' or game.get('season_type') != 'regular':
        raise ValueError('Completed regular-season game required')
    teams = {positive_id(game[x]['team_id']):game[x]['abbrev'] for x in ('home','away')}
    if len(teams) != 2 or len(set(teams.values())) != 2:
        raise ValueError('Distinct teams required')
    owners = {}; starters = {t:[] for t in teams}
    for p in box['players']:
        pid, tid = positive_id(p['player_id']), positive_id(p['team_id'])
        if pid in owners or tid not in teams or type(p.get('starter')) is not bool:
            raise ValueError('Duplicate identity, invalid team or unknown starter flag')
        owners[pid] = tid
        if p['starter']:
            if p.get('did_not_play') is not False:
                raise ValueError('Starting player availability contradicts box score')
            starters[tid].append(pid)
    if any(len(v) != 5 for v in starters.values()):
        raise ValueError('Historical starting five missing')
    rows = []; offset = 0
    if not pages:
        raise ValueError('No event pages')
    for i, page in enumerate(pages):
        part = page.get('plays')
        if not isinstance(part,list) or type(page.get('count')) is not int or page['count'] != len(part):
            raise ValueError('Invalid event page')
        offset += len(part)
        expected = None if i == len(pages)-1 else offset
        if 'next_offset' not in page or page['next_offset'] != expected:
            raise ValueError('Incomplete or inconsistent pagination')
        rows.extend(part)
    if type(box.get('plays')) is not int or len(rows) != box['plays'] or not rows:
        raise ValueError('Total event count cannot be reconciled')
    clean = []; last_seq = -1; last_period = 1; last_clock = 720
    score = [0,0]; first_score = None; first_attempt = None; first_made = None
    issues = []
    sides = [game['home']['abbrev'],game['away']['abbrev']]
    for r in rows:
        seq, period, clock = r.get('seq'), r.get('period'), r.get('clock_seconds')
        if (positive_id(r['game_id']) != gid or type(seq) is not int or seq <= last_seq
                or type(period) is not int or period < last_period or period < 1
                or type(clock) not in (int,float) or not 0 <= clock <= (720 if period <= 4 else 300)
                or (period == last_period and clock > last_clock)):
            raise ValueError('Invalid event identity/order/clock')
        if last_seq >= 0 and seq != last_seq + 1:
            issues.append('sequence_gap')
        if not clean and (period != 1 or clock != 720):
            issues.append('opening_boundary_unverified')
        last_seq,last_period,last_clock = seq,period,clock
        totals = [r.get('home_score'),r.get('away_score')]
        if any(type(v) is not int or v < 0 for v in totals):
            raise ValueError('Missing scoreboard')
        deltas = [totals[i]-score[i] for i in (0,1)]
        points = r.get('points')
        if type(points) is not int or points not in (0,1,2,3) or any(d<0 for d in deltas) or sum(deltas) != points or sum(d>0 for d in deltas)>1:
            raise ValueError('Score discontinuity or correction requires review')
        pid = str(r['player_id']) if r.get('player_id') is not None else None
        team = r.get('team'); known = pid in owners and teams[owners[pid]] == team
        if pid and not known:
            issues.append('unknown_or_mismatched_actor')
        shot = r.get('shot'); shot_kind = None
        if shot is not None:
            value = shot.get('points_attempted')
            if type(value) is not int or value not in (1,2,3) or type(shot.get('made')) is not bool:
                raise ValueError('Unknown shot semantics')
            if points != (value if shot['made'] else 0):
                raise ValueError('Shot result/score mismatch')
            shot_kind = 'free_throw' if value == 1 else 'field_goal'
        if points and (team not in sides or deltas[sides.index(team)] != points):
            raise ValueError('Scoring team mismatch')
        e = {'seq':seq,'period':period,'clock_seconds':clock,'team':team,
             'player_id':pid if known else None,'points':points,'kind':shot_kind,
             'made':shot['made'] if shot else None}
        clean.append(e); score = totals
        if shot_kind == 'field_goal' and first_attempt is None:
            first_attempt = e
        if shot_kind == 'field_goal' and points and first_made is None:
            first_made = e
        if points and first_score is None:
            first_score = e
    if score != [game['home']['score'],game['away']['score']]:
        issues.append('final_score_mismatch')
    if not first_score or first_score['player_id'] is None:
        issues.append('first_scorer_unresolved')
    if first_score and first_score['kind'] is None:
        issues.append('first_score_type_unresolved')
    if not first_attempt:
        issues.append('first_fg_attempt_missing')
    mapping_ok = False
    if mapping:
        if (mapping.get('source_namespace') != 'DunkAPI' or mapping.get('target_namespace') != 'ESPN'
                or mapping.get('source_game_id') != gid or mapping.get('reviewed') is not True
                or not mapping.get('evidence_reference') or mapping.get('source_hash') != digest(box)):
            raise ValueError('Independent source-bound identity evidence required')
        pairs = mapping.get('players',[])
        source = [positive_id(p['source_id']) for p in pairs]; target_ids = [positive_id(p['target_id']) for p in pairs]
        if set(source) != set(owners) or len(source)!=len(set(source)) or len(target_ids)!=len(set(target_ids)):
            raise ValueError('Incomplete or colliding player crosswalk')
        for p in pairs:
            if positive_id(p['source_team_id']) != owners[positive_id(p['source_id'])] or not p.get('target_team') or not p.get('evidence_reference'):
                raise ValueError('Player-team crosswalk evidence missing')
        mapping_ok = True
    return {'provider':'DunkAPI','game_id':gid,'source_hash':digest(box),
        'event_pages':len(pages),'single_response_complete':len(pages)==1,
        'events_received':len(rows),'historical_starters':starters,
        'starter_evidence':'postgame only; never pre-tip confirmation',
        'first_score':first_score,'first_fg_attempt':first_attempt,'first_made_fg':first_made,
        'first_scorer_status':('unknown' if not first_score or not first_score['player_id'] else
            'starter' if first_score['player_id'] in sum(starters.values(),[]) else 'nonstarter'),
        'events':clean,'issues':sorted(set(issues)), 'player_crosswalk_reviewed':mapping_ok,
        'model_compatible':False,'live_ingestion_permitted':False,
        'remaining':['Game/team cross-provider reconciliation and model adapter not approved',
                     'NBA upstream rights unresolved; no genuine source sample validated']}


def main():
    parser = argparse.ArgumentParser(description='Phase 10 preparation; no live requests enabled')
    parser.add_argument('command',choices=['status'])
    parser.parse_args()
    print(json.dumps({'live_ingestion_enabled':False,'maximum_credits':LIMIT,
                     'credential_present':bool(os.environ.get('DUNKAPI_API_KEY')),
                     'reason':BLOCKER}))

if __name__ == '__main__':
    main()
