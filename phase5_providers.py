"""Fresh provider evidence with explicit provenance, cooldowns and conservative mapping."""
import os,time,uuid
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
import requests
import dashboard_core as core,first_basket_engine as eng
from phase4_data import digest
from phase5_store import utc

class ProviderError(RuntimeError):pass
class Cooldown(ProviderError):pass

def stamp(text):
    value=datetime.fromisoformat(text.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('Provider timestamp has no timezone')
    return value.astimezone(timezone.utc)

class Transport:
    def __init__(self,store,get=None,sleep=time.sleep):self.store=store;self.get=get or requests.get;self.sleep=sleep
    def fetch(self,provider,url,params=None,headers=None,ttl=0):
        now=utc(self.store.clock());key=provider+':'+digest({'url':url,'params':params or {}})
        cached=self.store.state('cache:'+key)
        if cached and 0<=(now-stamp(cached['retrieved_at'])).total_seconds()<ttl:
            if cached.get('sha256')!=digest(cached.get('payload')):raise ProviderError(provider+' cached response checksum mismatch')
            return cached
        gate=self.store.state('cooldown:'+provider,0)
        if now.timestamp()<gate:raise Cooldown(provider+' cooldown active')
        lease=self.store.acquire('http:'+provider,60)
        if not lease:raise Cooldown(provider+' request already in progress')
        try:
            for attempt in range(3):
                try:
                    response=self.get(url,params=params,headers={'User-Agent':'APEX-Research/3.0.4','Accept':'application/json',**(headers or {})},timeout=15)
                    if response.status_code==429:
                        value=response.headers.get('Retry-After','300')
                        try:until=now+timedelta(seconds=max(30,int(value))) if str(value).isdigit() else parsedate_to_datetime(value)
                        except (ValueError,TypeError,OverflowError):until=now+timedelta(seconds=300)
                        if until.tzinfo is None:until=until.replace(tzinfo=timezone.utc)
                        self.store.set_state('cooldown:'+provider,max(now.timestamp()+30,until.timestamp()))
                        raise Cooldown(provider+' HTTP 429; retry window recorded')
                    if response.status_code in (500,502,503,504):raise requests.ConnectionError()
                    if response.status_code!=200:raise ProviderError(provider+' HTTP '+str(response.status_code))
                    payload=response.json();received=utc(self.store.clock()).isoformat()
                    wrapper={'provider':provider,'url':url,'params':params or {},'retrieved_at':received,'provider_date':response.headers.get('Date'),'provider_age':response.headers.get('Age'),'payload':payload,'sha256':digest(payload)}
                    self.store.append('provider_response',key+':'+received+':'+uuid.uuid4().hex,wrapper)
                    self.store.set_state('cache:'+key,wrapper);self.store.set_state('health:'+provider,{'ok':True,'at':received})
                    return wrapper
                except (requests.Timeout,requests.ConnectionError):
                    if attempt==2:
                        self.store.set_state('cooldown:'+provider,utc(self.store.clock()).timestamp()+60)
                        raise ProviderError(provider+' unavailable after three bounded attempts') from None
                    self.sleep(2**attempt)
                except (requests.RequestException,ValueError):raise ProviderError(provider+' malformed response or transport failure') from None
        except ProviderError as exc:
            self.store.set_state('health:'+provider,{'ok':False,'at':utc(self.store.clock()).isoformat(),'reason':str(exc)})
            raise
        finally:self.store.release(lease)

class Providers:
    def __init__(self,store,transport=None,injury_key=None,sports_key=None,licensed=False):
        self.store=store;self.http=transport or Transport(store)
        self.injury_key=injury_key if injury_key is not None else os.environ.get('BALLDONTLIE_API_KEY')
        self.sports_key=sports_key if sports_key is not None else os.environ.get('SPORTSDATAIO_API_KEY')
        self.licensed=licensed or os.environ.get('APEX_SPORTSDATAIO_LICENSED_LIVE')=='1'
    def schedule(self,day,fresh=False):
        w=self.http.fetch('ESPN',eng.ESPN_BASE+'/scoreboard',{'dates':day.replace('-',''),'limit':1000},ttl=0 if fresh else 30)
        if w.get('provider_age') is not None and int(w['provider_age'])>30:raise ProviderError('ESPN returned stale schedule cache')
        return [g for g in eng.parse_espn_schedule(w['payload']) if g['_date']==day],w
    def roster(self,team):
        inverse={v:k for k,v in eng.ESPN_ALIASES.items()}
        w=self.http.fetch('ESPN',eng.ESPN_BASE+f"/teams/{inverse.get(team,team).lower()}/roster",ttl=300)
        try:source_fresh(w,utc(self.store.clock()))
        except ValueError:raise ProviderError(team+': stale or invalid roster source') from None
        returned=w['payload'].get('team',{}).get('abbreviation')
        if returned and eng.ESPN_ALIASES.get(returned,returned)!=team:raise ProviderError(team+': roster response team mismatch')
        players=[{'player_id':str(a.get('id','')),'player':a.get('displayName','')} for a in w['payload'].get('athletes',[])]
        ids=[p['player_id'] for p in players]
        if not players or len(set(ids))!=len(ids) or any(not p['player_id'].isdigit() or int(p['player_id'])<=0 or not p['player'] for p in players):raise ProviderError(team+': invalid roster identities')
        return players,w
    def injuries(self):
        if not self.injury_key:raise ProviderError('BALLDONTLIE not configured; injuries unchecked')
        headers={'Authorization':self.injury_key};base='https://api.balldontlie.io/v1'
        teams=self.http.fetch('BALLDONTLIE',base+'/teams',headers=headers,ttl=3600)
        lookup={str(t['id']):t['abbreviation'] for t in teams['payload']['data']};result=[];cursor=None;seen=set();sources=[]
        for page in range(10):
            params={'per_page':100}
            if cursor is not None:params['cursor']=cursor
            self.http.sleep(1.1)
            w=self.http.fetch('BALLDONTLIE',base+'/player_injuries',params,headers,ttl=300)
            try:source_fresh(w,utc(self.store.clock()))
            except ValueError:raise ProviderError('BALLDONTLIE stale injury response; availability unchecked') from None
            sources.append(w)
            for row in w['payload']['data']:
                p=row['player'];team=p.get('team',{}).get('abbreviation') or lookup.get(str(p.get('team_id')))
                if not team:raise ProviderError('BALLDONTLIE injury team is unknown')
                result.append({'team':team,'player':p['first_name']+' '+p['last_name'],'status':row.get('status','Unknown'),'description':row.get('description',''),'provider_player_id':str(p['id'])})
            cursor=w['payload'].get('meta',{}).get('next_cursor')
            if cursor is None:return result,{'retrieved_at':min(x['retrieved_at'] for x in sources),'response_hashes':[x['sha256'] for x in sources]}
            if cursor in seen:raise ProviderError('BALLDONTLIE pagination repeated')
            seen.add(cursor)
        raise ProviderError('BALLDONTLIE pagination limit reached; partial report not accepted')
    def lineups(self,day):
        sources=[];errors=[]
        try:sources.append(self.http.fetch('NBA',core.NBA_LINEUP_URL.format(day=day.replace('-','')),ttl=30))
        except ProviderError as exc:errors.append(str(exc))
        if self.sports_key and self.licensed:
            try:sources.append(self.http.fetch('SportsDataIO','https://api.sportsdata.io/v3/nba/projections/json/StartingLineupsByDate/'+day,headers={'Ocp-Apim-Subscription-Key':self.sports_key},ttl=180))
            except ProviderError as exc:errors.append(str(exc))
        return sources,errors
    def result(self,gid):return self.http.fetch('ESPN',eng.ESPN_BASE+'/summary',{'event':gid.removeprefix('espn_')},ttl=120)

def map_names(players,roster,name_key,id_key,team_id=None):
    mapped=[];source_ids=[]
    for p in players:
        sid=str(p.get(id_key,''));name=core.lineup_name_key(name_key(p))
        if not sid.isdigit() or int(sid)<=0:raise ValueError('Invalid provider player ID')
        matches=[r for r in roster if name and core.lineup_name_key(r['player'])==name]
        if len(matches)!=1:raise ValueError('Player does not uniquely match current team roster')
        mapped.append(matches[0]['player_id']);source_ids.append(sid)
    if len(set(mapped))!=5 or len(set(source_ids))!=5 or len(mapped)!=5:raise ValueError('Five distinct player identities required')
    return mapped,source_ids

def source_fresh(wrapper,now):
    if not 0<=(now-stamp(wrapper['retrieved_at'])).total_seconds()<=300:raise ValueError('Stale lineup retrieval')
    if wrapper.get('sha256')!=digest(wrapper.get('payload')):raise ValueError('Lineup response checksum mismatch')
    if wrapper.get('provider_age') is not None and int(wrapper['provider_age'])>300:raise ValueError('Provider returned stale cached lineup')

def nba_evidence(wrapper,game,rosters,now):
    source_fresh(wrapper,now);p=wrapper['payload'];day=game['_date']
    parsed=core.parse_nba_confirmed_lineups(p,day,[game],rosters,now);output={};warnings=list(parsed['messages'])
    candidates=[g for g in p.get('games',[]) if g.get('awayTeam',{}).get('teamAbbreviation')==game['awayTeam']['teamTricode'] and g.get('homeTeam',{}).get('teamAbbreviation')==game['homeTeam']['teamTricode']]
    if len(candidates)!=1:return output,warnings
    g=candidates[0]
    if g.get('gameStatus')!=1:return output,warnings+['NBA source is not pregame']
    team_ids=[g[side].get('teamId') for side in ('awayTeam','homeTeam')]
    source_ids=[str(p.get('personId','')) for side in ('awayTeam','homeTeam') for p in g[side].get('players',[]) if p.get('position')]
    if len(set(team_ids))!=2 or any(type(x) is not int or x<=0 for x in team_ids) or len(set(source_ids))!=len(source_ids):return {},warnings+['Invalid or duplicate NBA team/player identity across sides']
    if sum(x.get('gameId')==g.get('gameId') for x in p['games'])!=1:return {},warnings+['Duplicate NBA game identity']
    for side in ('awayTeam','homeTeam'):
        team=game[side]['teamTricode'];rows=[x for x in g[side].get('players',[]) if x.get('position')]
        try:
            if len(rows)!=5 or {r.get('position') for r in rows}!={'PG','SG','SF','PF','C'}:raise ValueError('Incomplete positioned five')
            if any(r.get('teamId')!=g[side].get('teamId') for r in rows):raise ValueError('NBA player/team mismatch')
            ids,source_ids=map_names(rows,rosters.get(team,[]),lambda x:x.get('playerName',''),'personId')
            times=[x.get('timestamp') for x in rows]
            if any(not core.lineup_timestamp_valid(t,day,now) for t in times):raise ValueError('Wrong-date or invalid source time')
            official=team in parsed['entries'].get(game['gameId'],{})
            age_known=True
            for t in times:
                try:
                    age=(now-stamp(t)).total_seconds()
                    if not 0<=age<=1800:raise ValueError('Stale or future source announcement')
                except ValueError as exc:
                    if 'timezone' not in str(exc):raise
                    age_known=False
            if official and not age_known:
                official=False;warnings.append(team+': NBA claims confirmation but announcement timezone is unknown; verification withheld')
            if any(x.get('rosterStatus')!='Active' for x in rows):raise ValueError('Unavailable player in announced five')
            if any(x.get('lineupStatus') not in ('Expected','Confirmed') for x in rows):raise ValueError('Unknown provider lineup status')
            output[team]={'status':'provider-confirmed' if official else 'expected','player_ids':ids,'provider_player_ids':source_ids,'provider':'NBA','provider_game_id':str(g.get('gameId')),'source_times':times,'source_age_known':age_known,'retrieved_at':wrapper['retrieved_at'],'raw_hash':wrapper['sha256'],'claimed_confirmation':all(x.get('lineupStatus')=='Confirmed' for x in rows)}
        except (ValueError,TypeError,KeyError) as exc:warnings.append(team+': '+str(exc))
    return output,warnings

def sports_evidence(wrapper,game,rosters,now):
    """Live licensed data only. Naive DateTime requires explicit configured timezone."""
    from zoneinfo import ZoneInfo
    source_fresh(wrapper,now);p=wrapper['payload']
    if not isinstance(p,list):raise ValueError('Unreadable SportsDataIO lineup')
    candidates=[x for x in p if x.get('AwayTeam')==game['awayTeam']['teamTricode'] and x.get('HomeTeam')==game['homeTeam']['teamTricode']]
    if len(candidates)!=1:raise ValueError('No unique SportsDataIO matchup')
    g=candidates[0]
    if g.get('Status')!='Scheduled':raise ValueError('SportsDataIO game is not explicitly scheduled')
    team_ids=[g.get(x+'TeamID') for x in ('Home','Away')]
    if len(set(team_ids))!=2 or any(type(x) is not int or x<=0 for x in team_ids):raise ValueError('Invalid SportsDataIO team identities')
    start=datetime.fromisoformat(g['DateTime'])
    if start.tzinfo is None:
        zone=os.environ.get('APEX_SPORTSDATAIO_TIMEZONE')
        if zone!='America/New_York':raise ValueError('SportsDataIO DateTime timezone must be confirmed in account integration settings')
        start=start.replace(tzinfo=ZoneInfo(zone))
    if start!=stamp(game['start_time']):raise ValueError('SportsDataIO scheduled start mismatch')
    if not str(g.get('GameID','')).isdigit() or int(g['GameID'])<=0 or sum(x.get('GameID')==g.get('GameID') for x in p)!=1:raise ValueError('Invalid SportsDataIO game identity')
    result={};warnings=[]
    for side in ('Home','Away'):
        team=g[side+'Team'];players=[x for x in g.get(side+'Lineup',[]) if x.get('Starting') is True]
        try:
            if any(x.get('Team')!=team or x.get('TeamID')!=g.get(side+'TeamID') for x in players):raise ValueError('SportsDataIO team mismatch')
            if any(x.get('LineupStatus')=='Inactive' for x in players):raise ValueError('Inactive starter')
            ids,sids=map_names(players,rosters.get(team,[]),lambda x:x.get('FirstName','')+' '+x.get('LastName',''),'PlayerID')
            result[team]={'status':'provider-confirmed' if all(x.get('Confirmed') is True for x in players) else 'expected','player_ids':ids,'provider_player_ids':sids,'provider':'SportsDataIO','provider_game_id':str(g['GameID']),'source_times':[],'source_age_known':False,'retrieved_at':wrapper['retrieved_at'],'raw_hash':wrapper['sha256'],'warning':'Provider assertion at retrieval; no individual announcement timestamp supplied'}
        except (ValueError,KeyError,TypeError) as exc:warnings.append(team+': '+str(exc))
    return result,warnings

def resolve(game,rosters,history,sources,injuries,injury_time,now,manual=None):
    now=utc(now);warnings=[];evidence={};teams={game[s]['teamTricode'] for s in ('awayTeam','homeTeam')}
    all_roster_ids=[p['player_id'] for ps in rosters.values() for p in ps]
    if len(all_roster_ids)!=len(set(all_roster_ids)):warnings.append('Duplicate player identity across current team rosters')
    for source in sources:
        try:
            if source.get('provider') not in ('NBA','SportsDataIO'):raise ValueError('Unsupported lineup evidence provider')
            parsed,notes=(nba_evidence if source['provider']=='NBA' else sports_evidence)(source,game,rosters,now)
            warnings.extend(notes)
            for team,item in parsed.items():evidence.setdefault(team,[]).append(item)
        except (ValueError,KeyError,TypeError) as exc:warnings.append(source.get('provider','Unknown')+': '+str(exc))
    lineups={};statuses={};chosen={}
    for team in sorted(teams):
        candidates=evidence.get(team,[]);confirmed=[x for x in candidates if x['status']=='provider-confirmed']
        contradiction=len({tuple(sorted(x['player_ids'])) for x in candidates})>1
        if contradiction:warnings.append(team+': contradictory provider lineups; confirmation withheld')
        selected=(confirmed or candidates or [None])[0]
        if selected:
            ids=selected['player_ids'];status='unknown' if contradiction else selected['status'];chosen[team]=selected
        else:
            p=core.projection_evidence(history,team,game['_date'],rosters.get(team,[]),bool(rosters.get(team)))
            ids=p['defaults'];status='projected' if len(ids)==5 else 'unknown';warnings.extend(team+': '+w for w in p['warnings'])
        m=(manual or {}).get(team)
        if m and not confirmed:
            try:
                if not 0<=(now-stamp(m['confirmed_at'])).total_seconds()<=300 or m['game_id']!=game['gameId'] or m['start_time']!=game['start_time']:raise ValueError()
                ids=m['player_ids'];status='manual'
            except (KeyError,ValueError):warnings.append(team+': stale or invalid manual evidence')
        roster={x['player_id']:x for x in rosters.get(team,[])}
        if len(ids)!=5 or len(set(ids))!=5 or any(pid not in roster for pid in ids):status='unknown';warnings.append(team+': incomplete lineup or roster mismatch')
        lineups[team]=[roster[pid] for pid in ids if pid in roster];statuses[team]=status
        for player in lineups[team]:
            matches=[x for x in injuries if x['team']==team and core.lineup_name_key(x['player'])==core.lineup_name_key(player['player'])]
            if len(matches)>1:warnings.append(team+': contradictory injury evidence for '+player['player']);statuses[team]='unknown'
            elif matches:
                condition=matches[0]['status'];warnings.append(team+' / '+player['player']+': '+condition)
                if condition.lower() in ('out','inactive','suspended','unavailable'):statuses[team]='unknown'
    ids=[p['player_id'] for ps in lineups.values() for p in ps]
    valid=len(ids)==10 and len(set(ids))==10 and len(all_roster_ids)==len(set(all_roster_ids)) and all(len(ps)==5 for ps in lineups.values())
    if not valid:warnings.append('Ten distinct current-team players required')
    try:injury_fresh=0<=(now-stamp(injury_time)).total_seconds()<=900
    except (ValueError,TypeError,AttributeError):injury_fresh=False
    if not injury_fresh:warnings.append('Injury evidence missing or stale; availability unchecked')
    verified=valid and all(v=='provider-confirmed' for v in statuses.values())
    cohort='provider-confirmed' if verified else 'incomplete' if not valid or 'unknown' in statuses.values() else 'manual' if 'manual' in statuses.values() else 'projected'
    return {'lineups':lineups,'statuses':statuses,'evidence':evidence,'selected_evidence':chosen,'cohort':cohort,'valid_identities':valid,'injury_checked':injury_fresh,'provider_verified':verified,'warnings':warnings,'actionable':False}
