"""Audited historical imports and chronological model evaluation."""
import json
import math
import shutil
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import first_basket_engine as eng
import dashboard_core as core

MODEL_DAYS = 400


def history_window(rows, target):
    cutoff=(date.fromisoformat(target)-timedelta(days=MODEL_DAYS)).isoformat()
    return [r for r in rows if cutoff <= r['date'] < target]


def audit(rows):
    groups=defaultdict(list)
    for r in rows: groups[r.get('game_id','')].append(r)
    valid=[]; issues=[]
    for gid,game in groups.items():
        try:
            if not gid: raise ValueError('Missing game ID')
            dates={r['date'] for r in game}
            if len(dates)!=1: raise ValueError('Inconsistent dates')
            date.fromisoformat(next(iter(dates)))
            if len(game)!=10: raise ValueError('Expected ten starter rows')
            if len({r['player_id'] for r in game})!=10: raise ValueError('Duplicate player IDs')
            teams={r['team'] for r in game}
            if len(teams)!=2 or not teams.issubset(eng.TEAMS): raise ValueError('Invalid teams')
            if any(sum(r['team']==t for r in game)!=5 for t in teams): raise ValueError('Expected five players per team')
            for r in game:
                if not r['player_id'].isdigit() or not r['player'].strip(): raise ValueError('Invalid player')
                if r['opponent'] not in teams-{r['team']}: raise ValueError('Invalid opponent')
                for f in eng.FIELDS[6:]:
                    if str(r[f]) not in ('0','1'): raise ValueError('Invalid binary outcome')
            winners=[r for r in game if int(r['first_scorer'])==1]
            if len(winners)!=1: raise ValueError('Expected exactly one first scorer')
            winning_team=winners[0]['team']
            if any(int(r['team_scored_first'])!=int(r['team']==winning_team) for r in game): raise ValueError('Inconsistent first-scoring team')
            valid.extend(game)
        except (KeyError,TypeError,ValueError) as exc:
            issues.append({'game_id':gid,'reason':str(exc)})
    return valid,issues


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()


def season_index(season_end, progress=lambda msg:None):
    cache=eng.DATA/f'season_index_{season_end}.json'
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved.get('complete'):
            progress('Using saved season schedule index.')
            return saved['games'],[]
    games={}; errors=[]
    inverse={v:k for k,v in eng.ESPN_ALIASES.items()}
    for n,team in enumerate(sorted(eng.TEAMS),1):
        progress(f'Schedule {n}/30 · {team} · {season_end-1}–{season_end}')
        try:
            payload=core.request(eng.ESPN_BASE+f'/teams/{inverse.get(team,team).lower()}/schedule',{'season':season_end,'seasontype':2})
            events=[]
            for event in payload.get('events',[]):
                # ESPN's top-level season may be current even on a historical query.
                if int(event.get('season',{}).get('year',0))!=season_end: continue
                typ=event.get('season',{}).get('type',event.get('seasonType',{}).get('type'))
                if int(typ or 0)!=2: continue
                event={**event,'season':{**event['season'],'type':2}}
                events.append(event)
            parsed=eng.parse_espn_schedule({'events':events})
            if not parsed: raise ValueError('No matching regular-season events')
            for g in parsed: games[g['gameId']]=g
        except (RuntimeError,ValueError,KeyError,TypeError) as exc:
            errors.append(f'{team}: {exc}')
    result=sorted(games.values(),key=lambda g:(g['_date'],g['gameId']))
    if not result: raise RuntimeError('No historical schedule available. Your existing data was left unchanged.')
    cache.write_text(json.dumps({'games':result,'complete':not errors}))
    return result,errors


def import_season(season_end,limit=250,progress=lambda msg:None):
    old=eng.read_csv(eng.HISTORY)
    _,issues=audit(old)
    if issues: raise ValueError('Existing history failed validation. Open Data quality before importing; no data was changed.')
    games,errors=season_index(season_end,progress)
    known={r['game_id'] for r in old}
    today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    missing=[g for g in games if g['gameStatus']==3 and g['_date']<today and g['gameId'] not in known]
    selected=missing[-limit:]
    backup=eng.DATA/'history_before_prior_season.csv'
    if old and not backup.exists(): shutil.copy2(eng.HISTORY,backup)
    added=0; rejected=[]
    for i,g in enumerate(selected,1):
        progress(f'Game {i}/{len(selected)} · {g["_date"]} · {g["gameId"]}')
        try:
            summary=core.request(eng.ESPN_BASE+'/summary',{'event':g['gameId'].removeprefix('espn_')})
            play,box=eng.espn_game_payloads(summary)
            rows=eng.extract_game(g,play,box)
            _,bad=audit(rows)
            if bad: raise ValueError(bad[0]['reason'])
            old.extend(rows);known.add(g['gameId']);added+=1
            old.sort(key=lambda r:(r['date'],r['game_id'],r['team'],r['player_id']))
            eng.write_csv(eng.HISTORY,eng.FIELDS,old)  # Atomic checkpoint after each success.
        except (RuntimeError,KeyError,ValueError,TypeError) as exc:
            rejected.append({'game_id':g['gameId'],'date':g['_date'],'reason':str(exc)})
    summary={'season_end':season_end,'added':added,'attempted':len(selected),'remaining':len(missing)-added,'schedule_warnings':errors,'skipped':rejected,'finished':datetime.now().isoformat(timespec='seconds')}
    (eng.DATA/'last_history_import.json').write_text(json.dumps(summary,indent=2))
    return summary


def evaluate(rows,min_training=100):
    valid,issues=audit(rows)
    byday=defaultdict(lambda:defaultdict(list))
    for r in valid: byday[r['date']][r['game_id']].append(r)
    prior=[]; results=[]; calibration=[]
    for day in sorted(byday):
        train=history_window(prior,day)
        if len({r['game_id'] for r in train})>=min_training:
            stats=eng.team_stats(train)
            for gid,game in byday[day].items():
                a,b=sorted({r['team'] for r in game})
                pa=eng.first_team_probability(a,b,stats); probs={}
                for team,pt in ((a,pa),(b,1-pa)):
                    for p,w,*_ in eng.player_weights(train,[r for r in game if r['team']==team],team):
                        probs[p['player_id']]=pt*w
                winner=next(r for r in game if int(r['first_scorer']))
                wp=probs[winner['player_id']]
                best=max(probs.values()); ties=[pid for pid,p in probs.items() if abs(p-best)<1e-12]
                hit=1/len(ties) if winner['player_id'] in ties else 0
                brier=sum((p-int(pid==winner['player_id']))**2 for pid,p in probs.items())
                results.append({'Date':day,'Game':gid,'Winner':winner['player'],'Winner probability':wp,'Top-1 credit':hit,'Log loss':-math.log(wp),'Brier':brier,'Training games':len({r['game_id'] for r in train})})
                calibration.extend((p,int(pid==winner['player_id'])) for pid,p in probs.items())
        # No same-day results enter training until every game that day is evaluated.
        prior.extend(r for game in byday[day].values() for r in game)
    bins=[]
    for lo,hi in ((0,.05),(.05,.10),(.10,.15),(.15,.20),(.20,.30),(.30,1.000001)):
        subset=[(p,y) for p,y in calibration if lo<=p<hi]
        if subset: bins.append({'Probability band':f'{lo:.0%}–{min(hi,1):.0%}','Player predictions':len(subset),'Mean predicted %':100*sum(p for p,y in subset)/len(subset),'Observed first-score %':100*sum(y for p,y in subset)/len(subset)})
    n=len(results)
    metrics={'Evaluated games':n,'Top-1 hit %':100*sum(r['Top-1 credit'] for r in results)/n if n else None,'Log loss':sum(r['Log loss'] for r in results)/n if n else None,'Brier':sum(r['Brier'] for r in results)/n if n else None}
    return {'metrics':metrics,'games':results,'calibration':bins,'excluded':issues,'fingerprint':fingerprint(rows),'min_training':min_training,'window_days':MODEL_DAYS}

# Forward journal: local, immutable pregame forecasts; outcomes are stored separately.
def journal_connection(path=None):
    import sqlite3
    path=path or eng.DATA/'forward_journal.sqlite3'
    conn=sqlite3.connect(path,timeout=10)
    conn.execute('CREATE TABLE IF NOT EXISTS forecasts (game_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, outcome TEXT)')
    conn.commit()
    return conn


def save_forecast(game,rows,confirmed,model_version,history_hash,injury_time=None,path=None,now=None):
    from datetime import timezone
    import math
    now=now or datetime.now(timezone.utc)
    if not core.upcoming(game,now):raise ValueError('Game has started or is no longer scheduled. Forecast was not saved.')
    teams={game[s]['teamTricode'] for s in ('homeTeam','awayTeam')}
    if not all(confirmed.get(team,False) for team in teams):raise ValueError('Verify both announced starting fives before saving a forward forecast.')
    if len(rows)!=10 or {r['Team'] for r in rows}!=teams:raise ValueError('A forward forecast must contain ten players across this matchup.')
    if len({r['_player_id'] for r in rows})!=10 or any(sum(r['Team']==t for r in rows)!=5 for t in teams):raise ValueError('Invalid starting-five IDs.')
    if any(r['_game_id']!=game['gameId'] for r in rows):raise ValueError('Forecast belongs to a different game.')
    probs=[r['_probability'] for r in rows]
    if any(not math.isfinite(p) or p<=0 or p>=1 for p in probs) or abs(sum(probs)-1)>1e-8:raise ValueError('Forecast probabilities must be positive and sum to one.')
    snapshot={'game_id':game['gameId'],'date':game['_date'],'start_time':game['start_time'],'saved_at':now.isoformat(),
              'model_version':model_version,'history_hash':history_hash,'injuries_checked_at':injury_time,
              'lineup_confirmation':'User confirmed','rows':rows}
    conn=journal_connection(path)
    try:
        with conn:
            cursor=conn.execute('INSERT OR IGNORE INTO forecasts(game_id,snapshot) VALUES (?,?)',(game['gameId'],json.dumps(snapshot)))
        return cursor.rowcount==1
    finally:conn.close()


def journal_records(path=None):
    conn=journal_connection(path)
    try:
        return [{'snapshot':json.loads(s),'outcome':json.loads(o) if o else None} for s,o in conn.execute('SELECT snapshot,outcome FROM forecasts ORDER BY game_id')]
    finally:conn.close()


def outcome_from_summary(snapshot,payload):
    header=payload['header'];competition=header['competitions'][0]
    if str(header.get('id',competition.get('id','')))!=snapshot['game_id'].removeprefix('espn_'):
        raise ValueError('Provider returned a different game ID.')
    if not competition.get('status',{}).get('type',{}).get('completed'):
        return None
    play,box=eng.espn_game_payloads(payload)
    actual_teams={side['teamTricode'] for side in (box['game']['homeTeam'],box['game']['awayTeam'])}
    if actual_teams!={r['Team'] for r in snapshot['rows']}:raise ValueError('Provider returned different matchup teams.')
    scorer=next((a for a in eng.sorted_actions(play) if eng.is_made_score(a)),None)
    if not scorer:raise ValueError('Completed game has no readable first score. Left pending for review.')
    people={str(p['personId']):p for side in (box['game']['homeTeam'],box['game']['awayTeam']) for p in side['players']}
    winner_id=str(scorer['personId'])
    if winner_id not in people:raise ValueError('First scorer could not be matched to the box score.')
    actual_starters={str(p['personId']) for p in people.values() if eng.is_starter(p.get('starter'))}
    rows=snapshot['rows'];probs={r['_player_id']:r['_probability'] for r in rows}
    winning_p=probs.get(winner_id,0.0)
    best=max(probs.values());ties=[pid for pid,p in probs.items() if abs(p-best)<1e-12]
    top_credit=1/len(ties) if winner_id in ties else 0.0
    # Keep outcomes outside the ten-player field, instead of dropping those misses.
    brier=sum((p-int(pid==winner_id))**2 for pid,p in probs.items())+int(winner_id not in probs)
    return {'winner_id':winner_id,'winner':people[winner_id]['name'],'team':scorer['teamTricode'],
            'score_type':'Free throw' if eng.norm(scorer['actionType'])=='freethrow' else 'Field goal',
            'winner_probability':winning_p,'outside_field':winner_id not in probs,'top1_credit':top_credit,
            'brier':brier,'log_loss':-math.log(winning_p) if winning_p>0 else None,
            'lineup_matches':actual_starters==set(probs),
            'checked_at':datetime.now(ZoneInfo('UTC')).isoformat()}


def refresh_journal(path=None,progress=lambda text:None):
    records=journal_records(path);updated=0;errors=[]
    for record in records:
        if record['outcome'] is not None:continue
        snapshot=record['snapshot'];gid=snapshot['game_id']
        if datetime.fromisoformat(snapshot['start_time'].replace('Z','+00:00'))>datetime.now(ZoneInfo('UTC')):continue
        progress('Checking '+gid)
        try:
            payload=core.request(eng.ESPN_BASE+'/summary',{'event':gid.removeprefix('espn_')})
            outcome=outcome_from_summary(snapshot,payload)
            if outcome is None:continue
            conn=journal_connection(path)
            try:
                with conn:
                    cursor=conn.execute('UPDATE forecasts SET outcome=? WHERE game_id=? AND outcome IS NULL',(json.dumps(outcome),gid))
                updated+=cursor.rowcount
            finally:conn.close()
        except (RuntimeError,ValueError,KeyError,TypeError) as exc:
            errors.append({'game_id':gid,'reason':str(exc)})
    return updated,errors


def journal_summary(records):
    settled=[r for r in records if r['outcome'] is not None]
    n=len(settled);outside=sum(r['outcome']['outside_field'] for r in settled)
    return {'Saved games':len(records),'Settled games':n,'Pending games':len(records)-n,
            'Top-1 hit %':100*sum(r['outcome']['top1_credit'] for r in settled)/n if n else None,
            'Outside-field winners':outside,'Lineup mismatches':sum(not r['outcome']['lineup_matches'] for r in settled),
            'Brier':sum(r['outcome']['brier'] for r in settled)/n if n else None,
            'Log loss':('Infinite (zero-probability winner)' if outside else sum(r['outcome']['log_loss'] for r in settled)/n if n else None)}


def journal_table(records):
    table=[]
    for record in records:
        snap=record['snapshot'];outcome=record['outcome'];best=max(r['_probability'] for r in snap['rows'])
        tops=[r['Player'] for r in snap['rows'] if abs(r['_probability']-best)<1e-12]
        table.append({'Game':snap['game_id'],'Date':snap['date'],'Matchup':snap['rows'][0]['Matchup'],
                      'Version':snap['model_version'],'Saved before tip':snap['saved_at'],
                      'Top prediction':' / '.join(tops),'Top probability %':100*best,
                      'Winner':outcome['winner'] if outcome else 'Pending',
                      'Top-1 credit':outcome['top1_credit'] if outcome else None,
                      'Lineup matched':outcome['lineup_matches'] if outcome else None,
                      'Outside field':outcome['outside_field'] if outcome else None,
                      'Sample holds':sum(r['Status']=='HOLD: SAMPLE' for r in snap['rows'])})
    return table
