"""Audited historical imports and chronological model evaluation."""
import json
import math
import shutil
import hashlib
from pathlib import Path
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
            for team in teams:
                team_rows=[r for r in game if r['team']==team]
                if sum(int(r['first_team_shot']) for r in team_rows)>1:
                    raise ValueError('Multiple opening shooters recorded for one team')
                if len({int(r['tip_first_action']) for r in team_rows})!=1:
                    raise ValueError('Opening-possession proxy disagrees within a team')
            if sum(int(next(r for r in game if r['team']==t)['tip_first_action']) for t in teams)>1:
                raise ValueError('Both teams marked as first opening action')
            if sum(int(r['first_game_shot']) for r in game)>1:
                raise ValueError('Multiple game-opening shooters')
            if any(int(r['first_game_shot']) and not int(r['first_team_shot']) for r in game):
                raise ValueError('Game-opening shooter is not their team-opening shooter')
            if sum(int(r['first_fg_scorer']) for r in game)>1:
                raise ValueError('Multiple first field-goal scorers')
            # Zero flags can be legitimate: the relevant event involved a nonstarter,
            # or the possession proxy is unknown. Do not invent a starter event.
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
            eng.validate_espn_summary(g,summary)
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


def top_k_credit(probabilities, winner, k):
    """Fractional credit for a tie crossing the top-k boundary."""
    if winner not in probabilities:return 0.0
    score=probabilities[winner]
    ahead=sum(p>score+1e-12 for p in probabilities.values())
    tied=sum(abs(p-score)<=1e-12 for p in probabilities.values())
    return max(0.0,min(1.0,(k-ahead)/tied))


def compare_evaluations(baseline, candidate, draws=1000):
    """Paired date-cluster bootstrap: candidate minus baseline, per-game mean."""
    import random
    def indexed(result):
        games=result['games'];index={r['Game']:r for r in games}
        if len(index)!=len(games):raise ValueError('Duplicate evaluation games.')
        return index
    a,b=indexed(baseline),indexed(candidate)
    if set(a)!=set(b):raise ValueError('Models must evaluate identical games.')
    byday=defaultdict(list)
    for gid in sorted(a):
        if a[gid]['Date']!=b[gid]['Date']:raise ValueError('Evaluation dates do not match.')
        byday[a[gid]['Date']].append({metric:b[gid][metric]-a[gid][metric] for metric in ('Log loss','Brier','Top-1 credit','Top-3 credit')})
    days=sorted(byday);n=len(a);report=[]
    if not n:return {'games':0,'dates':0,'metrics':[]}
    if draws<100:raise ValueError('Use at least 100 bootstrap draws.')
    rng=random.Random(250)
    samples={m:[] for m in ('Log loss','Brier','Top-1 credit','Top-3 credit')}
    if len(days)>=2:
        for _ in range(draws):
            selected=[r for day in rng.choices(days,k=len(days)) for r in byday[day]]
            for metric in samples:samples[metric].append(sum(r[metric] for r in selected)/len(selected))
    for metric in samples:
        values=sorted(samples[metric]);scale=100 if 'credit' in metric else 1
        report.append({'Metric':metric.replace('credit','hit percentage points'),
                       'Candidate minus baseline':scale*sum(r[metric] for rows in byday.values() for r in rows)/n,
                       '95% lower':scale*values[int(.025*(len(values)-1))] if values else None,
                       '95% upper':scale*values[int(.975*(len(values)-1))] if values else None,
                       'Better direction':'Higher' if 'credit' in metric else 'Lower'})
    return {'games':n,'dates':len(days),'metrics':report}


def evaluate(rows,min_training=100,model="baseline"):
    if model not in ("baseline","recent","lineup"):raise ValueError("Unknown model.")
    valid,issues=audit(rows)
    byday=defaultdict(lambda:defaultdict(list))
    for r in valid: byday[r['date']][r['game_id']].append(r)
    prior=[]; results=[]; calibration=[]
    for day in sorted(byday):
        train=history_window(prior,day)
        if len({r['game_id'] for r in train})>=min_training:
            for gid,game in byday[day].items():
                teams=sorted({r['team'] for r in game})
                lineups={t:[r for r in game if r['team']==t] for t in teams}
                probs=eng.predict_first_score(train,lineups,day,model)
                winner=next(r for r in game if int(r['first_scorer']))
                wp=probs[winner['player_id']]
                best=max(probs.values()); ties=[pid for pid,p in probs.items() if abs(p-best)<1e-12]
                hit=1/len(ties) if winner['player_id'] in ties else 0
                brier=sum((p-int(pid==winner['player_id']))**2 for pid,p in probs.items())
                results.append({'Date':day,'Game':gid,'Winner':winner['player'],'Winner probability':wp,'Top-1 credit':hit,'Top-3 credit':top_k_credit(probs,winner['player_id'],3),'Log loss':-math.log(wp),'Brier':brier,'Training games':len({r['game_id'] for r in train})})
                calibration.extend((p,int(pid==winner['player_id'])) for pid,p in probs.items())
        # No same-day results enter training until every game that day is evaluated.
        prior.extend(r for game in byday[day].values() for r in game)
    bins=[]
    for lo,hi in ((0,.05),(.05,.10),(.10,.15),(.15,.20),(.20,.30),(.30,1.000001)):
        subset=[(p,y) for p,y in calibration if lo<=p<hi]
        if subset: bins.append({'Probability band':f'{lo:.0%}–{min(hi,1):.0%}','Player predictions':len(subset),'Mean predicted %':100*sum(p for p,y in subset)/len(subset),'Observed first-score %':100*sum(y for p,y in subset)/len(subset)})
    n=len(results)
    metrics={'Evaluated games':n,'Top-1 hit %':100*sum(r['Top-1 credit'] for r in results)/n if n else None,'Top-3 hit %':100*sum(r['Top-3 credit'] for r in results)/n if n else None,'Log loss':sum(r['Log loss'] for r in results)/n if n else None,'Brier':sum(r['Brier'] for r in results)/n if n else None}
    return {'metrics':metrics,'games':results,'calibration':bins,'excluded':issues,'fingerprint':fingerprint(rows),'min_training':min_training,'window_days':MODEL_DAYS,'model':model}

# Forward journal: local, immutable pregame forecasts; outcomes are stored separately.
def journal_connection(path=None):
    import sqlite3
    path=path or eng.DATA/'forward_journal.sqlite3'
    conn=sqlite3.connect(path,timeout=10)
    conn.execute('CREATE TABLE IF NOT EXISTS forecasts (game_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, outcome TEXT)')
    conn.commit()
    return conn


def save_forecast(game,rows,confirmed,model_version,history_hash,injury_time=None,path=None,now=None,model_forecasts=None):
    from datetime import timezone
    import math
    now=now or datetime.now(timezone.utc)
    if game.get('research_only') or any(r.get('_research_only') for r in rows):raise ValueError('Research matchups cannot be saved as forward forecasts.')
    if not core.upcoming(game,now):raise ValueError('Game has started or is no longer scheduled. Forecast was not saved.')
    teams={game[s]['teamTricode'] for s in ('homeTeam','awayTeam')}
    if not all(confirmed.get(team,False) for team in teams):raise ValueError('Verify both announced starting fives before saving a forward forecast.')
    if len(rows)!=10 or {r['Team'] for r in rows}!=teams:raise ValueError('A forward forecast must contain ten players across this matchup.')
    if len({r['_player_id'] for r in rows})!=10 or any(sum(r['Team']==t for r in rows)!=5 for t in teams):raise ValueError('Invalid starting-five IDs.')
    if any(r['_game_id']!=game['gameId'] for r in rows):raise ValueError('Forecast belongs to a different game.')
    probs=[r['_probability'] for r in rows]
    if any(not math.isfinite(p) or p<=0 or p>=1 for p in probs) or abs(sum(probs)-1)>1e-8:raise ValueError('Forecast probabilities must be positive and sum to one.')
    if model_forecasts is not None:
        if set(model_forecasts)!={'baseline','recent','lineup'}:raise ValueError('A model comparison requires all three forecasts.')
        expected={r['_player_id']:r['Team'] for r in rows}
        for model,forecast in model_forecasts.items():
            if len(forecast)!=10 or {r['_player_id']:r['Team'] for r in forecast}!=expected:
                raise ValueError('All models must use the same ten starters and teams.')
            if any(r.get('_research_only') or r['_game_id']!=game['gameId'] or r.get('Model')!=model for r in forecast):
                raise ValueError('Invalid model comparison identity or research forecast.')
            probs=[r['_probability'] for r in forecast]
            if any(not math.isfinite(p) or p<=0 or p>=1 for p in probs) or abs(sum(probs)-1)>1e-8:
                raise ValueError('Invalid model comparison probabilities.')
        primary=rows[0].get('Model','baseline')
        if primary not in model_forecasts or any(r.get('Model','baseline')!=primary for r in rows):
            raise ValueError('Invalid selected model.')
        saved={r['_player_id']:r['_probability'] for r in model_forecasts[primary]}
        if any(abs(saved[r['_player_id']]-r['_probability'])>1e-12 for r in rows):
            raise ValueError('Selected forecast does not match the comparison snapshot.')
    snapshot={'game_id':game['gameId'],'date':game['_date'],'start_time':game['start_time'],'saved_at':now.isoformat(),
              'model_version':model_version,'model':rows[0].get('Model','baseline'),'history_hash':history_hash,'injuries_checked_at':injury_time,
              'lineup_confirmation':'User confirmed','rows':rows}
    if model_forecasts is not None:snapshot['model_forecasts']=model_forecasts
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
                      'Version':snap['model_version'],'Model':snap.get('model','baseline'),'Saved before tip':snap['saved_at'],
                      'Top prediction':' / '.join(tops),'Top probability %':100*best,
                      'Winner':outcome['winner'] if outcome else 'Pending',
                      'Top-1 credit':outcome['top1_credit'] if outcome else None,
                      'Brier':outcome['brier'] if outcome else None,
                      'Log loss':('Infinite (zero-probability winner)' if outcome['outside_field'] else outcome['log_loss']) if outcome else None,
                      'Lineup matched':outcome['lineup_matches'] if outcome else None,
                      'Outside field':outcome['outside_field'] if outcome else None,
                      'Sample holds':sum(r['Status'] in ('HOLD: SAMPLE','HOLD: WEIGHTED SAMPLE') for r in snap['rows'])})
    return table


def journal_model_records(records, model):
    """Score immutable pre-tip probabilities against the recorded actual winner."""
    if model not in ('baseline','recent','lineup'):raise ValueError('Unknown journal model.')
    result=[]
    for record in records:
        snap=record['snapshot']
        if snap.get('model','baseline')==model:
            result.append(record);continue
        rows=snap.get('model_forecasts',{}).get(model)
        if rows is None:continue  # Never manufacture historical challenger forecasts.
        outcome=record['outcome']
        if outcome is not None:
            winner=outcome['winner_id'];probs={r['_player_id']:r['_probability'] for r in rows}
            wp=probs.get(winner,0)
            outcome={**outcome,'winner_probability':wp,'outside_field':winner not in probs,
                     'top1_credit':top_k_credit(probs,winner,1),
                     'brier':sum((p-int(pid==winner))**2 for pid,p in probs.items())+int(winner not in probs),
                     'log_loss':-math.log(wp) if wp>0 else None}
        result.append({'snapshot':{**snap,'model':model,'rows':rows},'outcome':outcome})
    return result


def forward_model_comparison(records):
    """All models evaluated on exactly the same prospectively saved games."""
    matched=[r for r in records if set(r['snapshot'].get('model_forecasts',{}))=={'baseline','recent','lineup'}]
    summaries=[];details=[]
    for model in ('baseline','recent','lineup'):
        viewed=journal_model_records(matched,model)
        summaries.append({'Model':model,**journal_summary(viewed)})
        details.extend(journal_table(viewed))
    return {'matched_games':len(matched),'excluded_games':len(records)-len(matched),'summary':summaries,'details':details}


def player_evidence(history, target_day, team, player_id, selected_five):
    """Raw same-team starting-game evidence, separate from smoothed forecasts."""
    selected={p['player_id'] for p in selected_five}
    if len(selected_five)!=5 or len(selected)!=5 or player_id not in selected:
        raise ValueError('Choose a player from a valid selected starting five.')
    valid,issues=audit(history_window(history,target_day))
    if issues:raise ValueError('History failed validation. Review Data quality before inspecting evidence.')
    team_games=defaultdict(set)
    for r in valid:
        if r['team']==team:team_games[r['game_id']].add(r['player_id'])
    rows=sorted([r for r in valid if r['team']==team and r['player_id']==player_id],key=lambda r:(r['date'],r['game_id']),reverse=True)
    def summarize(label,records):
        n=len(records);shots=sum(int(r['first_team_shot']) for r in records)
        scores=sum(int(r['first_scorer']) for r in records)
        opportunities=sum(int(r['team_scored_first']) for r in records)
        return {'Window':label,'Starts':n,'Team opening shots':shots,'Opening-shot rate %':100*shots/n if n else None,
                'Game first scores':scores,'First-score rate %':100*scores/n if n else None,
                'Team scored first':opportunities,'Share when team scored first %':100*scores/opportunities if opportunities else None,
                'Similar-lineup starts':sum(len(team_games[r['game_id']] & selected)>=4 for r in records)}
    logs=[{'Date':r['date'],'Game':r['game_id'],'Opponent':r['opponent'],
           'Took team first shot':bool(int(r['first_team_shot'])),
           'Scored game first points':bool(int(r['first_scorer'])),
           'Scored game first field goal':bool(int(r['first_fg_scorer'])),
           'Team scored first':bool(int(r['team_scored_first'])),
           'Selected starters in this game':len(team_games[r['game_id']] & selected)} for r in rows]
    last=rows[0]['date'] if rows else None
    return {'summary':[summarize('Last 10 recorded starts',rows[:10]),summarize('Last 30 recorded starts',rows[:30]),summarize('400-day model window',rows)],
            'games':logs,'last_start':last,'days_since_last_start':(date.fromisoformat(target_day)-date.fromisoformat(last)).days if last else None,
            'other_team_starts':sum(r['player_id']==player_id and r['team']!=team for r in valid)}


def repair_history(game_ids, progress=lambda text:None):
    """Replace only explicitly selected invalid games after provider validation."""
    import os
    import re
    import tempfile
    selected=list(dict.fromkeys(game_ids))
    if not selected or len(selected)>20:raise ValueError('Select between 1 and 20 flagged games.')
    original=eng.HISTORY.read_bytes()
    history=eng.read_csv(eng.HISTORY)
    _,issues=audit(history)
    flagged={r['game_id'] for r in issues}
    if not set(selected).issubset(flagged):raise ValueError('Selection changed or includes valid games. Refresh Data quality first.')
    replacements={};errors=[]
    for index,gid in enumerate(selected,1):
        progress(f'Rechecking game {index}/{len(selected)} · {gid}')
        try:
            if not re.fullmatch(r'espn_\d+',gid):raise ValueError('Only ESPN game IDs can be repaired automatically.')
            old_rows=[r for r in history if r.get('game_id')==gid]
            old_teams={r.get('team') for r in old_rows}
            if len(old_teams)!=2 or not old_teams.issubset(eng.TEAMS):
                raise ValueError('Stored matchup is ambiguous; manual review is required.')
            payload=core.request(eng.ESPN_BASE+'/summary',{'event':gid.removeprefix('espn_')})
            comp=payload['header']['competitions'][0]
            sides={c['homeAway']:eng.espn_team(c['team']) for c in comp['competitors']}
            if set(sides.values())!=old_teams:raise ValueError('Provider matchup differs from the stored teams.')
            start=datetime.fromisoformat(comp['date'].replace('Z','+00:00'))
            if start.tzinfo is None:raise ValueError('Provider game time has no timezone.')
            day=start.astimezone(ZoneInfo('America/New_York')).date()
            if day>datetime.now(ZoneInfo('America/New_York')).date():raise ValueError('Provider game date is in the future.')
            game={'gameId':gid,'_date':day.isoformat(),'homeTeam':{'teamTricode':sides['home']},'awayTeam':{'teamTricode':sides['away']}}
            eng.validate_espn_summary(game,payload)
            play,box=eng.espn_game_payloads(payload)
            rows=eng.extract_game(game,play,box)
            _,bad=audit(rows)
            if bad:raise ValueError(bad[0]['reason'])
            replacements[gid]=rows
        except (RuntimeError,ValueError,KeyError,TypeError,IndexError) as exc:
            errors.append({'game_id':gid,'reason':str(exc)})
    backup=None
    if replacements:
        if eng.HISTORY.read_bytes()!=original:raise ValueError('History changed during repair. Nothing replaced; retry with other imports stopped.')
        fd,name=tempfile.mkstemp(prefix='history_before_repair_',suffix='.csv',dir=eng.DATA)
        backup=Path(name)
        with os.fdopen(fd,'wb') as stream:
            stream.write(original);stream.flush();os.fsync(stream.fileno())
        repaired=[];emitted=set()
        for row in history:
            gid=row.get('game_id')
            if gid in replacements:
                if gid not in emitted:repaired.extend(replacements[gid]);emitted.add(gid)
            else:repaired.append(row)
        eng.write_csv(eng.HISTORY,eng.FIELDS,repaired)
    return {'attempted':len(selected),'repaired':len(replacements),'games':list(replacements),'errors':errors,'backup':backup.name if backup else None}


def evaluation_metrics(games):
    n=len(games)
    return {'Evaluated games':n,'Top-1 hit %':100*sum(r['Top-1 credit'] for r in games)/n if n else None,
            'Top-3 hit %':100*sum(r['Top-3 credit'] for r in games)/n if n else None,
            'Log loss':sum(r['Log loss'] for r in games)/n if n else None,
            'Brier':sum(r['Brier'] for r in games)/n if n else None}


def validation_report(history, min_training=100, progress=lambda text:None):
    """Same-game comparison with a fixed newest-quarter-of-dates diagnostic."""
    results={}
    for model in ('baseline','recent','lineup'):
        progress('Evaluating '+model+' on earlier-date history…')
        results[model]=evaluate(history,min_training,model)
    expected={(r['Game'],r['Date']) for r in results['baseline']['games']}
    for result in results.values():
        if {(r['Game'],r['Date']) for r in result['games']}!=expected or len(result['games'])!=len(expected):
            raise ValueError('Validation models did not evaluate identical games and dates.')
    dates=sorted({day for gid,day in expected})
    recent_dates=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    summary=[];monthly=[];details=[];latest={}
    for model,result in results.items():
        games=result['games'];newest=[r for r in games if r['Date'] in recent_dates]
        latest[model]={'games':newest}
        for label,subset in [('All evaluated dates',games),('Newest quarter of dates',newest)]:
            if subset:
                metrics=evaluation_metrics(subset)
                summary.append({'Model':model,'Period':label,'First date':min(r['Date'] for r in subset),'Last date':max(r['Date'] for r in subset),**metrics,
                                'Log loss minus equal baseline':metrics['Log loss']-math.log(10),
                                'Brier minus equal baseline':metrics['Brier']-.9})
        for month in sorted({r['Date'][:7] for r in games}):
            subset=[r for r in games if r['Date'].startswith(month)]
            monthly.append({'Model':model,'Month':month,**evaluation_metrics(subset)})
        details.extend({'Model':model,'Newest quarter':r['Date'] in recent_dates,**r} for r in games)
    paired=[]
    for model in ('recent','lineup'):
        comparison=compare_evaluations(latest['baseline'],latest[model])
        paired.extend({'Candidate':model,**r} for r in comparison['metrics'])
    return {'fingerprint':fingerprint(history),'min_training':min_training,'summary':summary,'monthly':monthly,'details':details,
            'latest_comparisons':paired,'evaluated_dates':len(dates),'latest_dates':len(recent_dates),'excluded_games':len(results['baseline']['excluded'])}
