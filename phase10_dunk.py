"""Quarantined DunkAPI pilot with deliberately opt-in Windows local execution.

No source adapter is connected to the frozen model. Only injected synthetic
transport can execute by default. Wallet authorization does not enable transport.
"""
import argparse
import base64
import hashlib
import json
import os
import time
import subprocess
import sys
import sqlite3
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
BLOCKER = 'Live ingestion disabled pending credentials and activation; upstream rights not independently cleared'


def response_payload(endpoint, payload):
    """Normalize get_game only, after preserving the exact source bytes.

    Legacy top-level fixtures remain supported. A data envelope must be the
    only top-level member; mixed/nested/partial wrappers fail closed.
    get_plays deliberately receives no inferred envelope transformation.
    """
    if not isinstance(payload, dict):raise ValueError('Object response required')
    if endpoint != 'get_game':return payload
    if 'data' in payload:
        if set(payload) != {'data'} or not isinstance(payload['data'], dict):
            raise ValueError('Invalid get_game envelope')
        payload=payload['data']
    if ('data' in payload or not isinstance(payload.get('game'),dict)
            or not isinstance(payload.get('players'),list)
            or any(not isinstance(p,dict) for p in payload['players'])
            or type(payload.get('plays')) is not int or payload['plays']<0):
        raise ValueError('Invalid get_game contents')
    return payload


class WalletTransport:
    """Exact ten-call transport, disabled by default; never purchases credits.

    Funding selection happens at the provider. Operator must attest existing
    wallet-only funding, no top-ups/overages and exclusive pilot account use.
    No credentials are stored in the journal, repr, URL or exceptions.
    """
    def __init__(self, manifest, *, wallet_balance, funding_confirmed=False,
                 enabled=False, session=None, one_request=False):
        if manifest.get('live_authorized') is not True or manifest.get('funding_source') != 'existing_wallet':
            raise ValueError('Existing-wallet authorization required')
        if type(wallet_balance) is not int or wallet_balance < 75:
            raise ValueError('Existing wallet insufficient for initial manifest')
        ids = [g['game_id'] for g in manifest['games']]
        if ids != ['401809243','401809236','401809943','401809956','401809970']:
            raise ValueError('Approved game IDs changed')
        expected=[]
        for gid in ids:
            expected.extend([{'method':'POST','endpoint':'get_game','body':{'game_id':gid},'credits_reserved_before_request':5},
                {'method':'POST','endpoint':'get_plays','body':{'game_id':gid,'limit':1000,'offset':0},'credits_reserved_before_request':10}])
        if manifest['requests'] != expected or manifest.get('lifetime_cap') != 100:
            raise ValueError('Approved requests or ceiling changed')
        self.one_request=one_request; self.request_used=False
        self.ids=ids; self.allowed={(HOST+q['endpoint'],canonical(q['body'])) for q in expected}
        self.balance=wallet_balance; self.enabled=enabled; self.funding_confirmed=funding_confirmed
        self.session=session or requests.Session()
        self.session.trust_env=False
        self.session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))

    def preflight(self):
        if not self.enabled:raise ProviderError('Live transport disabled')
        if self.funding_confirmed is not True:raise ProviderError('Existing-wallet funding controls not confirmed')
        if not os.environ.get('DUNKAPI_API_KEY'):raise ProviderError('DUNKAPI_API_KEY unavailable')

    def __call__(self,url,**kwargs):
        self.preflight()
        if (url,canonical(kwargs.get('json'))) not in self.allowed:
            raise ProviderError('Request outside owner-authorized manifest')
        if self.one_request:
            if self.request_used or url!=HOST+'get_plays' or kwargs.get('json')!={'game_id':'401809243','limit':1000,'offset':0}:
                raise ProviderError('One-request transport stopped')
            self.request_used=True  # Consumed before HTTP, including failures.
        kwargs['headers']={'x-api-key':os.environ['DUNKAPI_API_KEY'],
                           'x-idempotency-key':digest({'pilot':'phase10-five-games','url':url,'body':kwargs['json']})}
        kwargs.update(timeout=15,allow_redirects=False,stream=True)
        try:return self.session.post(url,**kwargs)
        except requests.RequestException:raise ProviderError('Provider transport failed; reservation retained') from None


class Pilot:
    """Fixed five-game manifest; durable reservations survive timeout/interruption.

    test_transport is solely for synthetic fixtures. There is intentionally no
    default live transport; the Windows CLI has separate preflight gates.
    """
    def __init__(self, store, game_ids, *, free_balance=None, test_transport=None, wallet_transport=None):
        self.store = store
        ids = [positive_id(x) for x in game_ids]
        if len(ids) != 5 or len(set(ids)) != 5:
            raise ValueError('Exactly five unique source-native game IDs required')
        if wallet_transport is not None and (type(wallet_transport) is not WalletTransport or test_transport is not None or ids != wallet_transport.ids):
            raise ValueError('Invalid live wallet transport')
        if wallet_transport is not None:free_balance=wallet_transport.balance
        if type(free_balance) is not int or free_balance < 0:
            raise ValueError('Explicit free-only balance required')
        self.cap = min(LIMIT, free_balance)
        self.ids, self.transport = ids, wallet_transport or test_transport
        self.wallet_transport = wallet_transport
        self.test_only = test_transport is not None
        config = {'game_ids': ids, 'ceiling': self.cap, 'test_only': self.test_only, 'costs': COSTS, 'funding_source':'existing_wallet' if wallet_transport else 'synthetic_or_disabled'}
        # Immutable registration rejects changing games/caps to reset the budget.
        store.append('dunk_pilot', 'phase10-five-games', config)

    def fetch(self, endpoint, gid, offset=0):
        if not self.test_only:
            if self.wallet_transport is None:raise ProviderError(BLOCKER)
            self.wallet_transport.preflight()
            if offset != 0:raise ProviderError('Pagination requires separate approval')
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
                if cached['payload'].get('http_status',200)!=200:
                    raise ProviderError('Cached provider failure; no repeat')
                return response_payload(endpoint, json.loads(raw))
            if self.wallet_transport and self.wallet_transport.one_request:
                if endpoint!='get_plays' or gid!='401809243' or offset!=0:
                    raise ProviderError('Outside one-request continuation')
                if self.wallet_transport.request_used:
                    raise ProviderError('One-request transport already consumed')
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
                              'params':params, 'test_only':self.test_only}, fence=lease)
            self.store.set_state('phase10:next_allowed', now + 7)
            try:
                response = self.transport(HOST + endpoint, json=params,
                    headers={'x-api-key':'SYNTHETIC-ONLY'}, timeout=15,
                    allow_redirects=False, stream=True)
            except requests.RequestException:
                raise ProviderError('Provider transport failure; reservation retained') from None
            try:
                keep_error=bool(self.wallet_transport and self.wallet_transport.one_request)
                if response.status_code == 429:
                    # Deliberately requires operator review; never auto-retry a charged query.
                    self.store.set_state('phase10:next_allowed', now + 3600)
                    if not keep_error:raise ProviderError('Provider rate limit; stop and review cooldown')
                if response.status_code != 200 and not keep_error:
                    raise ProviderError('Provider HTTP failure; body withheld; no retry')
                raw = bytearray(); deadline = time.monotonic() + 30
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES or time.monotonic() > deadline:
                        raise ProviderError('Response size/time bound exceeded')
                self.store.append('dunk_response', key, {'provider':'DunkAPI', 'test_only':self.test_only,
                    'endpoint':endpoint, 'request':params, 'http_status':response.status_code, 'retrieved_at':self.store.clock().isoformat(),
                    'sha256':hashlib.sha256(raw).hexdigest(),
                    'raw_base64':base64.b64encode(raw).decode()}, fence=lease)
                if response.status_code!=200:raise ProviderError('Provider HTTP failure retained privately; no retry')
                return response_payload(endpoint, json.loads(raw))
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


    def _pace(self):
        delay=self.store.state('phase10:next_allowed',0)-self.store.clock().timestamp()
        if delay>7:raise ProviderError('Provider cooldown requires review')
        if delay>0:time.sleep(delay)

    def run(self, target_day):
        """Bounded pilot orchestration. Source failures remain explicit, not dropped."""
        reports = []
        for gid in self.ids:
            try:
                if self.wallet_transport:self._pace()
                box = self.fetch('get_game', gid)
                if self.wallet_transport:
                    expected = next(g for g in json.loads((Path(__file__).parent/'validation/PHASE10_REQUEST_MANIFEST.json').read_text())['games'] if g['game_id']==gid)
                    game=box['game']
                    if (str(game['game_id']) != gid or game['date'] != expected['date'] or game['home']['abbrev'] != expected['home'] or game['away']['abbrev'] != expected['away'] or game['status'] != 'final' or game['season_type'] != 'regular'):
                        raise ValueError('Manifest game identity mismatch')
                    self._pace()
                pages = self.plays(gid)
                audit=inspect_game(box,pages,target_day)
                reports.append({'game_id':gid,'status':'audited','audit':audit})
                if self.wallet_transport and audit['issues']:break
            except ProviderError as error:
                reports.append({'game_id':gid,'status':'blocked','diagnostic':str(error)})
                break  # Respect provider/storage budget failure, no further automatic calls.
            except (ValueError, KeyError, TypeError):
                reports.append({'game_id':gid,'status':'invalid','diagnostic':'Source shape or integrity failed; raw response retained'})
                if self.wallet_transport:break
        for gid in self.ids[len(reports):]:
            reports.append({'game_id':gid,'status':'not_attempted'})
        return {'test_only':self.test_only,'games':reports,
                'reserved_credits':sum(r['payload']['cost'] for r in self.store.rows('dunk_attempt')),
                'model_compatibility_established':False}


def inspect_box(box, target_day):
    """Validate historical identities and starters without inventing events."""
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
    return game, gid, teams, owners, starters


def inspect_game(box, pages, target_day, mapping=None):
    """Source-native audit, NOT model training rows. Missing facts never invented."""
    game, gid, teams, owners, starters = inspect_box(box, target_day)
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
             'made':shot['made'] if shot else None,
             'source_type':r.get('type') if isinstance(r.get('type'),str) else None,
             'secondary_player_id':str(r['player2_id']) if r.get('player2_id') is not None and str(r['player2_id']) in owners else None}
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
                     'Owner reports provider research permission; NBA rights not independently cleared; no genuine sample validated']}


MANIFEST_SHA256 = "c4309436dcae82adc9ee435f33a81acefa94385d32f9541b17a458428c72e905"


def local_manifest(expected):
    raw=(Path(__file__).parent/'validation/PHASE10_REQUEST_MANIFEST.json').read_bytes()
    if expected != MANIFEST_SHA256 or hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:
        raise ValueError('Manifest changed; stop for review')
    return json.loads(raw)


def private_directory():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') or os.environ.get('CI'):
        raise ValueError('Live CLI is Windows-local only; cloud/CI prohibited')
    base=os.environ.get('LOCALAPPDATA')
    if not base or not Path(base).is_absolute():raise ValueError('LOCALAPPDATA unavailable')
    root=Path(base)/'APEX'/'DunkPilotPhase10'
    for parent in [root,*root.parents]:
        if parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()):
            raise ValueError('Linked private directory prohibited')
        if (parent/'.git').exists():raise ValueError('Private storage must be outside Git')
    if root.resolve().is_relative_to(Path(__file__).parent.resolve()):
        raise ValueError('Private storage overlaps application')
    return root


def secure_acl(root,create=False):
    # No provider access. Fixed PowerShell script; path passed as environment data.
    env=os.environ.copy();env.pop('DUNKAPI_API_KEY',None);env['APEX_PRIVATE_DIR']=str(root)
    script=r"""$ErrorActionPreference='Stop'
$p=$env:APEX_PRIVATE_DIR
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
"""
    if create:
        script+=r"""$acl=New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetOwner($sid)
$acl.SetAccessRuleProtection($true,$false)
$rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $p -AclObject $acl
"""
    script+=r"""$items=@(Get-Item -LiteralPath $p)+@(Get-ChildItem -LiteralPath $p -Force -Recurse)
foreach($item in $items){
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Linked storage'}
 $a=Get-Acl -LiteralPath $item.FullName
 if($item.FullName -eq $p -and !$a.AreAccessRulesProtected){throw 'Inherited directory permissions'}
 if($a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $sid.Value){throw 'Different owner'}
 foreach($rule in $a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])){
  if($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -ne $sid.Value){throw 'Other principal has access'}
 }
}
"""
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,timeout=30)
    if result.returncode:raise ValueError('Private Windows permissions could not be verified; no requests made')


def initialize_local(root,confirmed):
    if not confirmed:raise ValueError('Confirm no prior pilot; never initialize over previous reservations')
    if root.exists():raise ValueError('Private directory already exists; do not delete or reinitialize')
    root.mkdir(parents=True,exist_ok=False)
    secure_acl(root,create=True)
    marker={'pilot':'phase10-five-games','manifest_sha256':MANIFEST_SHA256}
    with (root/'identity.json').open('x') as f:json.dump(marker,f)
    Store(root/'pilot.sqlite3')
    secure_acl(root)


def sanitized_report(report):
    games=[]
    allowed={'sequence_gap','opening_boundary_unverified','unknown_or_mismatched_actor',
             'final_score_mismatch','first_scorer_unresolved','first_score_type_unresolved','first_fg_attempt_missing'}
    for row in report.get('games',[]):
        a=row.get('audit',{});first=a.get('first_score') or {};shot=a.get('first_fg_attempt') or {}
        games.append({'game_id':row['game_id'],'status':row['status'],
            'starter_counts':sorted(len(v) for v in a.get('historical_starters',{}).values()),
            'events_received':a.get('events_received'),'single_response_complete':a.get('single_response_complete'),
            'first_score_kind':first.get('kind'),'first_scorer_status':a.get('first_scorer_status'),
            'first_attempt_made':shot.get('made'),'issues':sorted(allowed & set(a.get('issues',[])))})
    return {'schema':1,'pilot':'phase10-five-games','test_only':report.get('test_only'),
        'reserved_credits':report.get('reserved_credits'),'actual_provider_debit':'not independently verified; compare dashboard',
        'model_compatibility_established':False,'games':games}


def read_private_rows(path):
    """Read-only SQLite replay: no Store construction, leases, writes or HTTP."""
    path=Path(path)
    if not path.is_file():raise ValueError('Original database missing')
    connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
            raise ValueError('Database integrity failure')
        rows=[Store.decode(r) for r in connection.execute('SELECT * FROM apex_events ORDER BY id')]
        Store.verify(rows)
    finally:connection.close()
    return rows


def replay_database(path, manifest, target_day):
    rows=read_private_rows(path)
    attempts={r['key']:r['payload'] for r in rows if r['kind']=='dunk_attempt'}
    allowed={digest({'endpoint':q['endpoint'],'params':q['body']}):q for q in manifest['requests']}
    for key,a in attempts.items():
        q=allowed.get(key)
        if not q or a['params']!=q['body'] or a['endpoint']!=q['endpoint'] or a['cost']!=COSTS[q['endpoint']]:
            raise ValueError('Reservation outside unchanged manifest')
    reserved=sum(a['cost'] for a in attempts.values())
    if reserved>LIMIT:raise ValueError('Reservation ceiling violated')
    games=[];cached=[r for r in rows if r['kind']=='dunk_response']
    for r in cached:
        p=r['payload'];q=allowed.get(r['key'])
        if (not q or r['key'] not in attempts or p['request']!=q['body']
                or p['endpoint']!=q['endpoint']):raise ValueError('Cache provenance mismatch')
        raw=base64.b64decode(p['raw_base64'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=p['sha256']:raise ValueError('Raw checksum mismatch')
        if p['endpoint']!='get_game':continue
        box=response_payload('get_game',json.loads(raw))
        game,gid,teams,owners,starters=inspect_box(box,target_day)
        expected=next(g for g in manifest['games'] if g['game_id']==q['body']['game_id'])
        if (gid!=expected['game_id'] or game['date']!=expected['date']
                or game['home']['abbrev']!=expected['home'] or game['away']['abbrev']!=expected['away']):
            raise ValueError('Manifest game identity mismatch')
        games.append({'game_id':gid,'identity_checks':'PASS','starter_counts':sorted(map(len,starters.values())),
                      'player_records':len(owners),'reported_plays':box['plays'],
                      'opening_events_validated':False,'cached_get_game_reusable':True})
    if not games:raise ValueError('No cached get_game response available')
    return {'offline_only':True,'integrity':'PASS','saved_responses':len(cached),
            'reservations':len(attempts),'reserved_credits':reserved,'new_requests':0,
            'new_reserved_credits':0,'database_modified':False,'games':games,
            'continuation_enabled':False,'model_compatibility_established':False}


def replay_local(root):
    manifest=local_manifest(MANIFEST_SHA256)
    secure_acl(root)
    if json.loads((root/'identity.json').read_text())!={'pilot':'phase10-five-games','manifest_sha256':MANIFEST_SHA256}:
        raise ValueError('Private identity mismatch')
    report=replay_database(root/'pilot.sqlite3',manifest,datetime.now(ZoneInfo('America/New_York')).date().isoformat())
    print(json.dumps(report,indent=2))
    return 0


def plays_structure(root):
    """Read-only shape inventory; no raw keys, values, players or events printed."""
    manifest=local_manifest(MANIFEST_SHA256)
    secure_acl(root)
    if json.loads((root/'identity.json').read_text())!={'pilot':'phase10-five-games','manifest_sha256':MANIFEST_SHA256}:
        raise ValueError('Private identity mismatch')
    rows=read_private_rows(root/'pilot.sqlite3')
    params={'game_id':'401809243','limit':1000,'offset':0}
    key=digest({'endpoint':'get_plays','params':params})
    attempts=[r for r in rows if r['kind']=='dunk_attempt']
    saved=next((r['payload'] for r in rows if r['kind']=='dunk_response' and r['key']==key),None)
    report={'offline_only':True,'game_id':'401809243','new_requests':0,'database_modified':False,
            'reserved_credits':sum(r['payload']['cost'] for r in attempts),
            'response_present':saved is not None,'interpretation_validated':False}
    if saved:
        if saved['endpoint']!='get_plays' or saved['request']!=params:raise ValueError('Cache provenance mismatch')
        raw=base64.b64decode(saved['raw_base64'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=saved['sha256']:raise ValueError('Raw checksum mismatch')
        attempt=next((r['payload'] for r in attempts if r['key']==key),None)
        if not attempt or attempt.get('cost')!=10 or attempt.get('params')!=params or attempt.get('endpoint')!='get_plays':
            raise ValueError('Response reservation mismatch')
        report['raw_integrity']='PASS'
        report['http_status']=saved.get('http_status',200)
        box_key=digest({'endpoint':'get_game','params':{'game_id':'401809243'}})
        box_saved=next((r['payload'] for r in rows if r['kind']=='dunk_response' and r['key']==box_key),None)
        reported=None
        if box_saved:
            box_raw=base64.b64decode(box_saved['raw_base64'],validate=True)
            if hashlib.sha256(box_raw).hexdigest()!=box_saved['sha256']:raise ValueError('Box checksum mismatch')
            reported=response_payload('get_game',json.loads(box_raw))['plays']
        report['get_game_reported_plays']=reported
        try:payload=json.loads(raw)
        except (ValueError,UnicodeError):report['json_valid']=False;return report
        report['json_valid']=True
        report['top_level_type']=type(payload).__name__
        # Fixed known fields only. Inspecting data is not acceptance of its semantics.
        report['locations']=[]
        for label,node in [('top_level',payload),('data',payload.get('data') if isinstance(payload,dict) else None)]:
            if not isinstance(node,dict):continue
            fields={k:type(node[k]).__name__ for k in ('plays','count','next_offset','limit','offset','total','has_more') if k in node}
            item={'location':label,'recognized_field_types':fields}
            if isinstance(node.get('plays'),list):
                item['event_count']=len(node['plays'])
                item['matches_get_game_count']=reported is not None and len(node['plays'])==reported
                item['all_events_objects']=all(isinstance(x,dict) for x in node['plays'])
                item['count_matches']=type(node.get('count')) is int and node['count']==len(node['plays'])
            item['terminal_null_observed']='next_offset' in node and node['next_offset'] is None
            item['additional_page_indicated']=('next_offset' in node and node['next_offset'] is not None) or node.get('has_more') is True
            report['locations'].append(item)
    return report


def execute_one(args,root):
    """Only the approved first get_plays call; never invokes run() or plays()."""
    if not args.execute or args.confirm_wallet!=495 or not args.confirm_no_replenishment or not args.confirm_exclusive_use:
        raise ValueError('Explicit execution and current 495-credit wallet attestation required')
    manifest=local_manifest(args.confirm_manifest)
    secure_acl(root)
    if json.loads((root/'identity.json').read_text())!={'pilot':'phase10-five-games','manifest_sha256':MANIFEST_SHA256}:
        raise ValueError('Private identity mismatch')
    path=root/'pilot.sqlite3'
    day=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    # No writable Store (which can initialize) until the original DB is verified.
    replay_database(path,manifest,day)
    store=Store(path)
    lease=store.acquire('phase10:local-run',900)
    if not lease:raise ValueError('Another or interrupted local run exists')
    transport=None
    try:
        report=replay_database(path,manifest,day)
        if (report['reservations']!=1 or report['reserved_credits']!=5 or report['saved_responses']!=1
                or len(report['games'])!=1 or report['games'][0]['game_id']!='401809243'):
            raise ValueError('Expected original five-credit cache only; no repeat continuation')
        rows=store.rows()
        if any(r['payload'].get('test_only') is not False for r in rows if r['kind'] in ('dunk_attempt','dunk_response')):
            raise ValueError('Synthetic cache cannot authorize live continuation')
        transport=WalletTransport(manifest,wallet_balance=495,funding_confirmed=True,enabled=True,one_request=True)
        transport.preflight()
        pilot=Pilot(store,transport.ids,wallet_transport=transport)
        pilot.fetch('get_game','401809243')  # Cache only; transport rejects get_game.
        pilot._pace()
        pilot.fetch('get_plays','401809243',0)  # Exactly one call; no parsing loop.
        print('ONE-REQUEST STOP: response saved. No further requests. Run plays-report-local offline.')
        return 0
    finally:
        store.release(lease)
        if transport:transport.session.close()


def execute_local(args,root):
    if not args.execute or args.confirm_wallet != 500 or not args.confirm_no_replenishment or not args.confirm_exclusive_use:
        raise ValueError('Explicit wallet, replenishment, exclusive-use and execution preflight required')
    manifest=local_manifest(args.confirm_manifest)
    if not root.is_dir():raise ValueError('Initialize private storage first')
    secure_acl(root)
    if not (root/'pilot.sqlite3').is_file():raise ValueError('Original reservation database missing; restore it, never reset')
    marker=json.loads((root/'identity.json').read_text())
    if marker != {'pilot':'phase10-five-games','manifest_sha256':MANIFEST_SHA256}:raise ValueError('Private identity mismatch')
    day=datetime.now(ZoneInfo('America/New_York')).date()
    if any(not 0<(day-datetime.fromisoformat(g['date']).date()).days<=400 for g in manifest['games']):
        raise ValueError('Approved games outside current frozen window')
    transport=WalletTransport(manifest,wallet_balance=500,funding_confirmed=True,enabled=True)
    transport.preflight()
    store=Store(root/'pilot.sqlite3');store.rows()
    lease=store.acquire('phase10:local-run',900)
    if not lease:raise ValueError('Another run or interrupted run lease exists; wait, never delete database')
    try:
        pilot=Pilot(store,transport.ids,wallet_transport=transport)
        report=pilot.run(day.isoformat())
        store.append('dunk_local_report',digest(report),report)
        safe=sanitized_report(report)
        target=root/'sanitized_results.json';tmp=root/'sanitized_results.tmp'
        tmp.write_text(json.dumps(safe,indent=2));tmp.replace(target)
        secure_acl(root)
        print(json.dumps(safe,indent=2))
        return 0 if all(x['status']=='audited' and not x.get('audit',{}).get('issues') for x in report['games']) else 2
    finally:
        store.release(lease);transport.session.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Phase 10: no network by default; opt-in local Windows pilot')
    parser.add_argument('command',choices=['status','init-local','run-local','report-local','replay-local','continue-one-local','plays-report-local'])
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--confirm-wallet',type=int)
    parser.add_argument('--confirm-no-replenishment',action='store_true')
    parser.add_argument('--confirm-exclusive-use',action='store_true')
    parser.add_argument('--confirm-no-prior-pilot',action='store_true')
    parser.add_argument('--confirm-manifest')
    args=parser.parse_args(argv)
    try:
        if args.command=='status':
            print(json.dumps({'live_enabled_by_default':False,'credential_present':bool(os.environ.get('DUNKAPI_API_KEY')),
                              'manifest_sha256':MANIFEST_SHA256,'maximum_credits':100}));return 0
        root=private_directory()
        if args.command=='init-local':initialize_local(root,args.confirm_no_prior_pilot);print('Private pilot storage initialized.');return 0
        if args.command=='continue-one-local':return execute_one(args,root)
        if args.command=='plays-report-local':print(json.dumps(plays_structure(root),indent=2));return 0
        if args.command=='run-local':return execute_local(args,root)
        if args.command=='replay-local':return replay_local(root)
        secure_acl(root)
        # Report command never constructs transport or requires a key.
        print((root/'sanitized_results.json').read_text());return 0
    except (Exception,KeyboardInterrupt):
        print('STOPPED: preflight, storage or execution check failed. No automatic retry. Preserve the private directory; inspect sanitized_results.json if present. Do not delete the reservation database.',file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
