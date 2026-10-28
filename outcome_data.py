"""Complete first-score research ledger, separate from legacy starter-only CSVs."""
import copy,json,re
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import first_basket_engine as eng
import opening_data

def game_from_payload(payload):
    c=payload['header']['competitions'][0]
    sides={x['homeAway']:eng.espn_team(x['team']) for x in c['competitors']}
    stamp=datetime.fromisoformat(c['date'].replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Missing game timezone')
    return {'gameId':'espn_'+str(payload['header']['id']),'_date':stamp.astimezone(ZoneInfo('America/New_York')).date().isoformat(),'start_time':c['date'],'gameStatus':3,'homeTeam':{'teamTricode':sides['home']},'awayTeam':{'teamTricode':sides['away']}}

def extract(game,payload):
    eng.validate_espn_summary(game,payload)
    actual=game_from_payload(payload)
    if actual['_date']!=game['_date']:raise ValueError('Outcome date mismatch')
    record={'schema':1,'game_id':game['gameId'],'date':game['_date'],'start_time':actual['start_time'],'status':'ambiguous','scorer_id':None,'starter_status':'unknown','score_type':None,'warnings':[],'lineup_verification':'unverified','rows':[]}
    # Missing identities in unrelated bench rows must not discard a known first score.
    clean=copy.deepcopy(payload);identities={};states={};ambiguous=set()
    teams={str(c['team']['id']):eng.espn_team(c['team']) for c in payload['header']['competitions'][0]['competitors']}
    for side in clean.get('boxscore',{}).get('players',[]):
        team=teams.get(str(side['team']['id']))
        if team is None:raise ValueError('Boxscore team does not match matchup')
        for stats in side.get('statistics',[]):
            kept=[]
            for row in stats.get('athletes',[]):
                athlete=row.get('athlete',{});pid=str(athlete.get('id',''))
                if not pid.isdigit() or int(pid)<=0 or not athlete.get('displayName'):
                    record['warnings'].append('Boxscore player identity missing');continue
                state='starter' if eng.is_starter(row.get('starter')) else 'bench' if row.get('starter') is False else 'unknown'
                if pid in identities and (identities[pid]!=team or states[pid]!=state):ambiguous.add(pid)
                identities[pid]=team;states[pid]=state;kept.append(row)
            stats['athletes']=kept
    try:
        sides={c['homeAway']:str(c['team']['id']) for c in clean['header']['competitions'][0]['competitors']}
        boxes={tid:{'players':[{'personId':int(pid)} for pid,t in identities.items() if t==team]} for tid,team in teams.items()}
        checked=eng.checked_opening_plays(clean,sides,boxes)
        raw=next(p for p in checked if p.get('scoringPlay'))
        pid=str(raw['participants'][0]['athlete']['id'])
        scorer={'teamTricode':teams[str(raw['team']['id'])],'actionType':'free throw' if 'free throw' in raw.get('text','').lower() else 'made shot'}
        if pid in ambiguous:raise ValueError('Conflicting scorer identity or starter status')
        # Validate monotone first-quarter clock through the first score.
        ordered=sorted((p for p in clean['plays'] if p.get('period',{}).get('number')==1),key=lambda p:int(p['sequenceNumber']))
        previous=720
        for p in ordered:
            clock=str(p.get('clock',{}).get('displayValue',''))
            if not re.fullmatch(r'\d{1,2}:\d{2}(?:\.\d+)?',clock):raise ValueError('Unknown opening clock')
            m,s=clock.split(':');seconds=int(m)*60+float(s)
            if float(s)>=60 or not 0<=seconds<=previous:raise ValueError('Opening event clock order conflict')
            previous=seconds
            if p.get('scoringPlay'):break
        record.update(status='resolved',scorer_id=pid,scorer_team=scorer['teamTricode'],starter_status=states.get(pid,'unknown'),score_type='FT' if eng.norm(scorer['actionType'])=='freethrow' else 'FG')
        try:
            play,box=eng.espn_game_payloads(clean)
            rows=eng.extract_game(game,play,box,allow_nonstarter=True)
            if len({r['player_id'] for r in rows})!=10 or ambiguous:raise ValueError('Ambiguous starter identities')
            record['rows']=rows
        except (ValueError,KeyError,TypeError) as e:record['warnings'].append('Starter model unavailable: '+str(e))
    except (ValueError,KeyError,TypeError,StopIteration,IndexError) as e:record['warnings'].append(str(e))
    return record

def load(path=None):
    path=path or eng.DATA/'first_score_outcomes.json'
    if not path.exists():return {}
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or type(data.get('schema')) is not int or data.get('schema')!=1 or not isinstance(data.get('games'),dict):raise ValueError('Invalid complete-outcome ledger')
    for gid,r in data['games'].items():
        if not isinstance(r,dict) or r.get('game_id')!=gid or r.get('schema')!=1 or r.get('status') not in ('resolved','ambiguous') or r.get('starter_status') not in ('starter','bench','unknown') or not isinstance(r.get('rows'),list):raise ValueError('Invalid complete-outcome record')
        datetime.strptime(r.get('date',''),'%Y-%m-%d')
        if r['status']=='resolved' and (not isinstance(r.get('scorer_id'),str) or not r['scorer_id'].isdigit() or int(r['scorer_id'])<=0):raise ValueError('Invalid resolved scorer identity')
    return data['games']

def write(records,path=None):opening_data.write(records,path or eng.DATA/'first_score_outcomes.json')

def audit(records):
    from collections import Counter
    counts=Counter(r['starter_status'] if r['status']=='resolved' else 'ambiguous' for r in records.values())
    return {'games':len(records),'outcomes':dict(counts),'free_throw_first_scores':sum(r.get('score_type')=='FT' for r in records.values()),'without_ten_valid_starters':sum(not r.get('rows') for r in records.values()),'warnings':[{'game':r['game_id'],'reasons':r['warnings']} for r in records.values() if r['warnings']]}

def archive_lineup(game,lineups,manual,provider,rosters,reports,injury_checked_at,path=None,now=None):
    """Append-only snapshots retain projected/manual/provider distinctions; never backdate."""
    import dashboard_core as core
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or game.get('research_only') or not core.upcoming(game,now):raise ValueError('Only a live pre-tip game can be archived')
    ready=core.phase2_readiness(game,lineups,manual,provider,rosters,reports,injury_checked_at,now)
    if any('roster' in s or 'identit' in s for s in ready['messages']):raise ValueError('Archive roster/identity verification failed')
    record={'schema':1,'game_id':game['gameId'],'date':game['_date'],'start_time':game['start_time'],'saved_at':now.isoformat(),'lineups':lineups,'sources':ready['sources'],'lineup_evidence':{t:{**provider.get(t,{}),'method':source} for t,source in ready['sources'].items()},'diagnostics':ready['messages'],'injury_checked_at':injury_checked_at,'provider_verified':ready['provider_verified']}
    path=path or eng.DATA/'pregame_lineups.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(record,sort_keys=True)+'\n')
    return record

def collect_day(day,path=None,progress=lambda message:None):
    """Explicit, cached daily full-outcome import. One attempt per event per click."""
    import dashboard_core as core
    from datetime import date
    if date.fromisoformat(day)>=datetime.now(ZoneInfo('America/New_York')).date():raise ValueError('Choose a completed prior date')
    path=path or eng.DATA/'first_score_outcomes.json';records=load(path)
    cache=path.parent/'outcome_source_cache';cache.mkdir(parents=True,exist_ok=True)
    expected=path.read_bytes() if path.exists() else None
    payload=core.request(eng.ESPN_BASE+'/scoreboard',{'dates':day.replace('-',''),'limit':1000})
    games={g['gameId']:g for g in eng.parse_espn_schedule(payload) if g['_date']==day and g['gameStatus']==3}
    errors=[];added=0
    for gid,g in sorted(games.items()):
        if gid in records and records[gid]['status']=='resolved':continue
        progress('Complete first-score outcome: '+gid)
        try:
            source=cache/(gid+'.json')
            p=json.loads(source.read_text()) if source.exists() else core.request(eng.ESPN_BASE+'/summary',{'event':gid.removeprefix('espn_')})
            if not source.exists():source.write_text(json.dumps(p))
            record=extract(g,p)
            if (path.read_bytes() if path.exists() else None)!=expected:raise ValueError('Outcome ledger changed during import; retry after other imports finish')
            records[gid]=record;write(records,path);expected=path.read_bytes();added+=1
            if record['status']!='resolved':errors.append({'game':gid,'reason':record['warnings']})
        except (ValueError,RuntimeError,KeyError,TypeError,OSError) as exc:
            errors.append({'game':gid,'reason':str(exc)})
            if isinstance(exc,RuntimeError):break # Provider failures stop this batch; no retry bypass.
    result={'scheduled_completed':len(games),'saved':added,'errors':errors,'audit':audit(records)}
    # Keep failed games visible across sessions; never silently discard the import report.
    path.with_name('complete_outcome_last_import.json').write_text(json.dumps(result,indent=2))
    return result

def archive_for_evaluation(records,path=None):
    """Only real pre-tip provider snapshots matching observed IDs enter verified cohorts."""
    import phase2
    path=path or eng.DATA/'pregame_lineups.jsonl';verified={};errors=[]
    if not path.exists():return verified,errors
    for number,line in enumerate(path.read_text().splitlines(),1):
        try:
            snap=json.loads(line);gid=snap['game_id'];actual=records.get(gid)
            if actual and actual.get('rows') and phase2.verified_historical_lineup(snap,actual['rows'],actual.get('start_time')):
                # Keep the first qualifying snapshot, never infer provider verification from box scores.
                verified.setdefault(gid,snap)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:errors.append({'line':number,'reason':str(exc)})
    return verified,errors
