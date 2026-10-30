"""Validated early-sequence sidecar. Box-score starters are NOT pre-tip verification."""
import json
import re
import os
import tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import first_basket_engine as eng

SCHEMA=1


def history_identity(rows):
    fields=('game_id','date','team','opponent','player_id','first_team_shot','first_game_shot','first_scorer')
    return sorted([tuple(str(r[f]) for f in fields) for r in rows])


def shot_type(play):
    text=str(play.get('text','')).lower();values=set()
    if re.search(r'\b(?:3|three)[ -]?(?:point|pt)\b',text):values.add(3)
    if re.search(r'\b(?:2|two)[ -]?(?:point|pt)\b',text) or any(x in text for x in ('layup','dunk','hook shot')):values.add(2)
    if play.get('scoringPlay') is True and type(play.get('scoreValue')) is int and play['scoreValue'] in (2,3):values.add(play['scoreValue'])
    return next(iter(values)) if len(values)==1 else None


def category(play,value):
    text=str(play.get('text','')).lower()
    if value==3:return 'three'
    if value==2 and any(x in text for x in ('layup','dunk')):return 'rim'
    if value==2:return 'two_jump'
    return 'other'


def extract(game,payload,allow_nonstarter=False):
    eng.validate_espn_summary(game,payload)
    comp=payload['header']['competitions'][0]
    stamp=datetime.fromisoformat(comp['date'].replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp.astimezone(ZoneInfo('America/New_York')).date().isoformat()!=game['_date']:raise ValueError('Sequence date mismatch.')
    play,box=eng.espn_game_payloads(payload);rows=eng.extract_game(game,play,box,allow_nonstarter=allow_nonstarter)
    teams={str(c['team']['id']):eng.espn_team(c['team']) for c in comp['competitors']}
    identities={};names={};starters={r['player_id']:r['team'] for r in rows}
    for side in ('homeTeam','awayTeam'):
        for p in box['game'][side]['players']:
            pid=str(p['personId']);identities[pid]=box['game'][side]['teamTricode'];names[pid]=eng.norm(p['name'])
    events=[];tip=None;first_teams=set();pending=None;second_chance=False;warnings=[];sub_before_score=False
    ordered=sorted([p for p in payload.get('plays',[]) if p.get('period',{}).get('number')==1],key=lambda p:int(p['sequenceNumber']))
    first_score=next((int(p['sequenceNumber']) for p in ordered if p.get('scoringPlay') is True and p.get('scoreValue',0)>0),None)
    for p in ordered:
        text=str(p.get('text',''));typ=eng.norm(p.get('type',{}).get('text',''));team=teams.get(str(p.get('team',{}).get('id')))
        actors=[str(x.get('athlete',{}).get('id','')) for x in p.get('participants',[])];pid=actors[0] if actors else None
        clock=str(p.get('clock',{}).get('displayValue',''))
        if not re.fullmatch(r'\d{1,2}:\d{2}(?:\.\d+)?',clock):warnings.append('Invalid clock; sequence truncated');break
        minute,second=clock.split(':');remaining=int(minute)*60+float(second)
        if not 0<=remaining<=720 or float(second)>=60:warnings.append('Invalid clock range');break
        if remaining<540:break
        if 'substitution' in typ or ' enters the game for ' in text.lower():
            sub_before_score=first_score is not None and int(p['sequenceNumber'])<first_score
            break
        if typ=='jumpball' and tip is None and not events and len(actors)==3:
            gained=re.search(r'\((.+?) gains possession\)',text,re.I)
            if gained and all(a in starters for a in actors) and identities[actors[0]]!=identities[actors[1]] and team==identities[actors[2]] and eng.norm(gained.group(1))==names[actors[2]]:
                tip={'winner':team,'jumpers':{identities[a]:a for a in actors[:2]}}
            continue
        if 'rebound' in typ or 'rebound' in text.lower():
            if pending and team in teams.values():events.append({'kind':'rebound','team':pending,'offensive':team==pending})
            second_chance=bool(pending and team==pending);pending=None;continue
        if team is None:continue
        if 'turnover' in typ or 'turnover' in text.lower():
            events.append({'kind':'turnover','team':team});pending=None;second_chance=False;continue
        if 'free throw' in text.lower():
            if pid not in starters or starters[pid]!=team:warnings.append('Nonstarter action; sequence truncated');break
            result=p.get('scoringPlay');value=p.get('scoreValue')
            if type(result) is not bool or type(value) is not int or value!=(1 if result else 0):continue
            trip=re.search(r'(\d) of ([123])',text)
            # Technicals and unspecified trips inform FT accuracy, not possession event rates.
            events.append({'kind':'ft','team':team,'player':pid,'made':int(result),'trip_start':bool(trip and trip.group(1)=='1'),
                           'shots':int(trip.group(2)) if trip else None})
            pending=team if not result and trip and trip.group(1)==trip.group(2) else None
            continue
        if p.get('shootingPlay') is True:
            if pid not in starters or starters[pid]!=team:warnings.append('Nonstarter action; sequence truncated');break
            result=p.get('scoringPlay');value=p.get('scoreValue')
            known=type(result) is bool and type(value) is int and ((result and value in (2,3)) or (not result and value==0))
            if not known or (result and re.search(r'\bmiss(?:es|ed)?\b',text,re.I)) or (not result and re.search(r'\bmakes\b',text,re.I)):continue
            value=shot_type(p)
            events.append({'kind':'shot','team':team,'player':pid,'made':int(result),'value':value,'category':category(p,value),
                           'first_team_shot':team not in first_teams,'second_chance':second_chance})
            first_teams.add(team);pending=None if result else team
            if result:second_chance=False
    return {'schema':SCHEMA,'game_id':game['gameId'],'date':game['_date'],'start_time':game.get('start_time',stamp.isoformat()),
            'history_identity':history_identity(rows),'starters':starters,'tip':tip,'events':events,
            'substitution_before_first_score':sub_before_score,'warnings':warnings,
            'lineup_verification':'unverified','source':'ESPN completed-game summary; opening 3 minutes before first substitution'}


def _valid_for_history(record,rows):
    """Validate the sidecar before using it; fail closed on identity/data conflicts."""
    if type(record.get('schema')) is not int or record.get('schema')!=SCHEMA or record.get('game_id')!=rows[0]['game_id'] or record.get('date')!=rows[0]['date']:return False
    if sorted(tuple(x) for x in record.get('history_identity',[]))!=history_identity(rows):return False
    starters={r['player_id']:r['team'] for r in rows};teams=set(starters.values())
    if record.get('starters')!=starters or not isinstance(record.get('events'),list):return False
    tip=record.get('tip')
    if tip is not None and (not isinstance(tip,dict) or tip.get('winner') not in teams or set(tip.get('jumpers',{}))!=teams or any(starters.get(pid)!=team for team,pid in tip['jumpers'].items())):return False
    for e in record['events']:
        if not isinstance(e,dict) or e.get('team') not in teams:return False
        if e.get('kind') in ('shot','ft'):
            if starters.get(e.get('player'))!=e['team'] or type(e.get('made')) is not int or e['made'] not in (0,1):return False
        if e.get('kind')=='shot':
            if e.get('value') not in (None,2,3) or e.get('category') not in ('rim','two_jump','three','other') or type(e.get('first_team_shot')) is not bool or type(e.get('second_chance')) is not bool:return False
        elif e.get('kind')=='ft':
            if (e.get('shots') is not None and (type(e.get('shots')) is not int or e['shots'] not in (1,2,3))) or type(e.get('trip_start')) is not bool:return False
        elif e.get('kind')=='rebound':
            if type(e.get('offensive')) is not bool:return False
        elif e.get('kind')!='turnover':return False
    return True


def valid_for_history(record,rows):
    try:return _valid_for_history(record,rows)
    except (TypeError,KeyError,ValueError,AttributeError,IndexError):return False


def load(path=None):
    path=path or eng.DATA/'opening_sequences.json'
    if not path.exists():return {}
    payload=json.loads(path.read_text())
    if not isinstance(payload,dict) or type(payload.get('schema')) is not int or payload.get('schema')!=SCHEMA or not isinstance(payload.get('games'),dict):raise ValueError('Invalid opening-sequence file.')
    return payload['games']


def write(records,path=None):
    path=path or eng.DATA/'opening_sequences.json';path.parent.mkdir(parents=True,exist_ok=True)
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as stream:
            name=Path(stream.name);json.dump({'schema':SCHEMA,'games':records},stream);stream.flush();os.fsync(stream.fileno())
        name.replace(path)
    finally:
        if name and name.exists():name.unlink()


def enrich(history,limit=20,path=None,progress=lambda message:None):
    import research_tools as rt
    import dashboard_core as core
    valid,issues=rt.audit(history)
    if issues:raise ValueError('Repair history before enriching sequences.')
    if type(limit) is not int or not 1<=limit<=50:raise ValueError('Choose 1 to 50 games.')
    path=path or eng.DATA/'opening_sequences.json';path.parent.mkdir(parents=True,exist_ok=True)
    records=load(path);expected=path.read_bytes() if path.exists() else None
    tracker=path.with_name(path.stem+'_attempts.json');attempts=rt.read_opening_attempts(tracker)
    groups={}
    for row in valid:groups.setdefault(row['game_id'],[]).append(row)
    today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    pending=[(gid,rows) for gid,rows in groups.items() if re.fullmatch('espn_[0-9]+',gid) and rows[0]['date']<today and (gid not in records or not valid_for_history(records[gid],rows))]
    errors=[];added=0
    for gid,rows in sorted(pending,key=lambda item:(attempts.get(item[0],0),item[1][0]['date'],item[0]))[:limit]:
        progress('Reading early possessions: '+gid)
        if (path.read_bytes() if path.exists() else None)!=expected:raise ValueError('Opening sequences changed during enrichment; stop other imports and retry.')
        attempts[gid]=attempts.get(gid,0)+1;rt.write_opening_attempts(tracker,attempts)
        try:
            p=core.request(eng.ESPN_BASE+'/summary',{'event':gid.removeprefix('espn_')});c=p['header']['competitions'][0]
            sides={x['homeAway']:eng.espn_team(x['team']) for x in c['competitors']}
            g={'gameId':gid,'_date':rows[0]['date'],'start_time':c['date'],'homeTeam':{'teamTricode':sides['home']},'awayTeam':{'teamTricode':sides['away']}}
            record=extract(g,p)
            if not valid_for_history(record,rows):raise ValueError('Stored historical facts differ from summary.')
            if (path.read_bytes() if path.exists() else None)!=expected:raise ValueError('Opening sequences changed during enrichment; nothing overwritten.')
            records[gid]=record;write(records,path);expected=path.read_bytes();added+=1
        except (ValueError,KeyError,TypeError,RuntimeError,AttributeError,IndexError) as exc:errors.append({'game':gid,'reason':str(exc)})
    return {'added':added,'attempted':min(limit,len(pending)),'remaining':len(pending)-added,'errors':errors}
