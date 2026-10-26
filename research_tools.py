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
                for f in (f for f in eng.FIELDS[6:] if f not in ('opening_shot_observed','first_team_shot_made','opening_score_path')):
                    if str(r[f]) not in ('0','1'): raise ValueError('Invalid binary outcome')
                shot_result=str(r.get('first_team_shot_made',''))
                if shot_result not in ('','None','0','1'):raise ValueError('Invalid opening-shot result')
                if shot_result in ('0','1') and int(r['first_team_shot'])!=1:raise ValueError('Opening-shot result belongs to a non-opening shooter')
                if shot_result=='1' and int(r['first_game_shot']) and not int(r['first_fg_scorer']):raise ValueError('Made game-opening shot contradicts first field-goal scorer')
            paths={str(r.get('opening_score_path','')) for r in game}
            if not (paths<= {'','None'} or paths in ({'free_throw_before_fg'},{'opening_fg_made'},{'opening_fg_missed'})):
                raise ValueError('Invalid or inconsistent opening scoring path')
            if paths=={'opening_fg_made'} and not any(int(r['first_game_shot']) and int(r['first_scorer']) and int(r['first_fg_scorer']) for r in game):
                raise ValueError('Made opening path contradicts scorer flags')
            if paths=={'opening_fg_missed'} and any(int(r['first_game_shot']) and str(r.get('first_team_shot_made',''))=='1' for r in game):
                raise ValueError('Missed opening path contradicts shot outcome')
            winners=[r for r in game if int(r['first_scorer'])==1]
            if len(winners)!=1: raise ValueError('Expected exactly one first scorer')
            winning_team=winners[0]['team']
            if any(int(r['team_scored_first'])!=int(r['team']==winning_team) for r in game): raise ValueError('Inconsistent first-scoring team')
            for team in teams:
                team_rows=[r for r in game if r['team']==team]
                coverage={str(r.get('opening_shot_observed','')) for r in team_rows}
                if not (coverage<= {'','None'} or coverage in ({'0'},{'1'})):
                    raise ValueError('Invalid or inconsistent opening-shot coverage')
                if coverage=={'0'} and any(int(r['first_team_shot']) for r in team_rows):
                    raise ValueError('Opening shooter flagged despite unknown coverage')
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


def read_import_attempts(path,season_end):
    if not path.exists():return {}
    try:
        record=json.loads(path.read_text())
        attempts=record['attempts']
        if record.get('schema')!=1 or record.get('season_end')!=season_end or not isinstance(attempts,dict):raise ValueError()
        if any(not isinstance(gid,str) or not gid or isinstance(n,bool) or not isinstance(n,int) or n<0 for gid,n in attempts.items()):raise ValueError()
        return attempts
    except (ValueError,KeyError,TypeError,AttributeError):
        raise ValueError('Import retry tracker is invalid; history has not been changed.')


def write_import_attempts(path,season_end,attempts):
    import os
    import tempfile
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='history_attempts_',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump({'schema':1,'season_end':season_end,'attempts':attempts},stream)
            stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()


def import_season(season_end,limit=250,progress=lambda msg:None):
    if isinstance(season_end,bool) or not isinstance(season_end,int) or not 1000<=season_end<=9999:raise ValueError('Season must be a four-digit ending year.')
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=1500:raise ValueError('Import batch size must be between 1 and 1500.')
    old=eng.read_csv(eng.HISTORY)
    _,issues=audit(old)
    if issues: raise ValueError('Existing history failed validation. Open Data quality before importing; no data was changed.')
    attempt_path=eng.DATA/f'history_import_attempts_{season_end}.json'
    attempts=read_import_attempts(attempt_path,season_end)
    games,errors=season_index(season_end,progress)
    known={r['game_id'] for r in old}
    today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    missing=[g for g in games if g['gameStatus']==3 and g['_date']<today and g['gameId'] not in known]
    # Fresh games first; retries with fewer prior attempts next. Dates break ties.
    selected=sorted(missing,key=lambda g:(attempts.get(g['gameId'],0),-date.fromisoformat(g['_date']).toordinal(),g['gameId']))[:limit]
    retries=sum(attempts.get(g['gameId'],0)>0 for g in selected)
    backup=eng.DATA/'history_before_prior_season.csv'
    if old and not backup.exists(): shutil.copy2(eng.HISTORY,backup)
    added=0; rejected=[]
    for i,g in enumerate(selected,1):
        progress(f'Game {i}/{len(selected)} · {g["_date"]} · {g["gameId"]}')
        attempts[g['gameId']]=attempts.get(g['gameId'],0)+1
        # Save before the request so an interruption cannot trap the next batch.
        write_import_attempts(attempt_path,season_end,attempts)
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
    summary={'season_end':season_end,'added':added,'attempted':len(selected),'remaining':len(missing)-added,'retry_attempted':retries,'never_attempted_remaining':sum(g['gameId'] not in known and attempts.get(g['gameId'],0)==0 for g in missing),'schedule_warnings':errors,'skipped':rejected,'finished':datetime.now().isoformat(timespec='seconds')}
    (eng.DATA/'last_history_import.json').write_text(json.dumps(summary,indent=2))
    return summary


def top_k_credit(probabilities, winner, k):
    """Fractional credit for a tie crossing the top-k boundary."""
    if winner not in probabilities:return 0.0
    score=probabilities[winner]
    ahead=sum(p>score+1e-12 for p in probabilities.values())
    tied=sum(abs(p-score)<=1e-12 for p in probabilities.values())
    return max(0.0,min(1.0,(k-ahead)/tied))


def compare_evaluations(baseline, candidate, draws=1000, metrics=('Log loss','Brier','Top-1 credit','Top-3 credit')):
    """Paired date-cluster bootstrap: candidate minus baseline, per-game mean."""
    import random
    if not metrics or len(set(metrics))!=len(metrics) or any(m not in ('Log loss','Brier','Top-1 credit','Top-3 credit') for m in metrics):
        raise ValueError('Choose unique supported comparison metrics.')
    def indexed(result):
        games=result['games'];index={r['Game']:r for r in games}
        if len(index)!=len(games):raise ValueError('Duplicate evaluation games.')
        return index
    a,b=indexed(baseline),indexed(candidate)
    if set(a)!=set(b):raise ValueError('Models must evaluate identical games.')
    byday=defaultdict(list)
    for gid in sorted(a):
        if a[gid]['Date']!=b[gid]['Date']:raise ValueError('Evaluation dates do not match.')
        differences={metric:b[gid][metric]-a[gid][metric] for metric in metrics}
        if any(not math.isfinite(v) for v in differences.values()):raise ValueError('Comparison metrics must be finite.')
        byday[a[gid]['Date']].append({m:0.0 if abs(v)<1e-12 else v for m,v in differences.items()})
    days=sorted(byday);n=len(a);report=[]
    if not n:return {'games':0,'dates':0,'metrics':[]}
    if draws<100:raise ValueError('Use at least 100 bootstrap draws.')
    rng=random.Random(250)
    samples={m:[] for m in metrics}
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


def equal_benchmark_evidence(games):
    """Compare historical ten-starter forecasts with equal probabilities on identical dates."""
    reference=[{'Game':r['Game'],'Date':r['Date'],'Log loss':math.log(10),
                'Brier':.9,'Top-1 credit':.1,'Top-3 credit':.3} for r in games]
    comparison=compare_evaluations({'games':reference},{'games':games})
    return benchmark_evidence_rows(comparison)


def benchmark_evidence_rows(comparison):
    evidence=[]
    for row in comparison['metrics']:
        low,high=row['95% lower'],row['95% upper']
        if low is None or high is None:
            reading='Not enough dates for an interval'
        elif low<=0<=high:
            reading='Interval includes zero: no clear difference'
        elif (row['Better direction']=='Lower' and high<0) or (row['Better direction']=='Higher' and low>0):
            reading='Interval favors model on this sample'
        else:
            reading='Interval favors equal probabilities on this sample'
        evidence.append({'Metric':row['Metric'],'Model minus equal':row['Candidate minus baseline'],
                         '95% lower':low,'95% upper':high,'Better direction':row['Better direction'],
                         'Games':comparison['games'],'Dates':comparison['dates'],'Reading':reading})
    return evidence


def scoring_stage_metrics(probabilities, player_teams, winner):
    """Factor a ten-player forecast into team and conditional player probabilities."""
    if set(probabilities)!=set(player_teams) or winner not in probabilities:
        raise ValueError('Stage diagnostics require matching player IDs and an in-field winner.')
    if len(probabilities)!=10 or len(set(player_teams.values()))!=2 or any(list(player_teams.values()).count(t)!=5 for t in set(player_teams.values())):
        raise ValueError('Stage diagnostics require two teams of five.')
    if any(not math.isfinite(p) or p<=0 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-8:
        raise ValueError('Stage diagnostics require positive normalized probabilities.')
    teams=defaultdict(float)
    for pid,p in probabilities.items():teams[player_teams[pid]]+=p
    winning_team=player_teams[winner];team_p=teams[winning_team]
    conditional={pid:p/team_p for pid,p in probabilities.items() if player_teams[pid]==winning_team}
    return {'Winning team probability':team_p,'Winner share within team':conditional[winner],
            'Team top-1 credit':top_k_credit(teams,winning_team,1),
            'Within-winning-team top-1 credit':top_k_credit(conditional,winner,1),
            'Team log loss':-math.log(team_p),'Within-team log loss':-math.log(conditional[winner])}


def scoring_stage_summary(games):
    if not games:return {}
    n=len(games)
    team=sum(r['Team log loss'] for r in games)/n
    player=sum(r['Within-team log loss'] for r in games)/n
    return {'Games':n,'Team hit %':100*sum(r['Team top-1 credit'] for r in games)/n,
            'Player hit % within actual winning team':100*sum(r['Within-winning-team top-1 credit'] for r in games)/n,
            'Team log loss':team,'Within-team log loss':player,
            'Team loss minus 50/50':team-math.log(2),
            'Within-team loss minus equal five':player-math.log(5)}


def temper_probabilities(probabilities,temperature=1.0):
    """Positive temperature scaling preserves player order and normalizes the field."""
    if isinstance(temperature,bool) or not isinstance(temperature,(int,float)) or not math.isfinite(temperature) or not .5<=temperature<=2:
        raise ValueError('Temperature must be finite and between 0.5 and 2.')
    if len(probabilities)!=10 or any(not math.isfinite(p) or p<=0 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-8:
        raise ValueError('Temperature scaling requires ten positive normalized probabilities.')
    if temperature==1:return dict(probabilities)
    logits={pid:math.log(p)/temperature for pid,p in probabilities.items()}
    peak=max(logits.values());weights={pid:math.exp(v-peak) for pid,v in logits.items()}
    if any(w==0 for w in weights.values()):raise ValueError('Temperature scaling underflowed; probabilities are too extreme.')
    total=sum(weights.values())
    return {pid:w/total for pid,w in weights.items()}


def evaluate(rows,min_training=100,model="baseline",shot_weight=.65,half_life=90.0,temperature=1.0):
    temper_probabilities({str(i):.1 for i in range(10)},temperature)
    eng.validate_half_life(half_life)
    eng.validate_shot_weight(shot_weight)
    if model not in ("baseline","recent","lineup","conversion","post_miss"):raise ValueError("Unknown model.")
    valid,issues=audit(rows)
    byday=defaultdict(lambda:defaultdict(list))
    for r in valid: byday[r['date']][r['game_id']].append(r)
    prior=[]; results=[]; calibration=[]
    for day in sorted(byday):
        train=history_window(prior,day)
        training_games=len({r['game_id'] for r in train})
        conversion_counts=defaultdict(int)
        for r in train:
            if int(r['first_team_shot'])==1 and str(r.get('first_team_shot_made','')) in ('0','1'):
                conversion_counts[(r['team'],r['player_id'])]+=1
        if training_games>=min_training:
            matchups={gid:{t:[r for r in game if r['team']==t] for t in {r['team'] for r in game}} for gid,game in byday[day].items()}
            predictions=eng.predict_matchups(train,matchups,day,model,shot_weight=shot_weight,half_life=half_life)
            for gid,game in byday[day].items():
                probs=temper_probabilities(predictions[gid],temperature)
                conversion_attempts=sum(conversion_counts[(r['team'],r['player_id'])] for r in game)
                path_counts=[len({r['game_id'] for r in train if r['team']==team and r.get('opening_score_path') in ('free_throw_before_fg','opening_fg_made','opening_fg_missed')}) for team in {r['team'] for r in game}]
                winner=next(r for r in game if int(r['first_scorer']))
                wp=probs[winner['player_id']]
                best=max(probs.values()); ties=[pid for pid,p in probs.items() if abs(p-best)<1e-12]
                hit=1/len(ties) if winner['player_id'] in ties else 0
                brier=sum((p-int(pid==winner['player_id']))**2 for pid,p in probs.items())
                results.append({'Date':day,'Game':gid,'Winner':winner['player'],'Winner probability':wp,'Top probability':best,'Top margin':0.0 if len(ties)>1 else best-sorted(probs.values(),reverse=True)[1],'Tied leaders':len(ties),'Top-1 credit':hit,'Top-3 credit':top_k_credit(probs,winner['player_id'],3),'Log loss':-math.log(wp),'Brier':brier,'Training games':training_games,'Known conversion training attempts':conversion_attempts,'Minimum team sequence games':min(path_counts),**scoring_stage_metrics(probs,{r['player_id']:r['team'] for r in game},winner['player_id'])})
                calibration.extend((p,int(pid==winner['player_id'])) for pid,p in probs.items())
        # No same-day results enter training until every game that day is evaluated.
        prior.extend(r for game in byday[day].values() for r in game)
    bins=[]
    for lo,hi in ((0,.05),(.05,.10),(.10,.15),(.15,.20),(.20,.30),(.30,1.000001)):
        subset=[(p,y) for p,y in calibration if lo<=p<hi]
        if subset: bins.append({'Probability band':f'{lo:.0%}–{min(hi,1):.0%}','Player predictions':len(subset),'Mean predicted %':100*sum(p for p,y in subset)/len(subset),'Observed first-score %':100*sum(y for p,y in subset)/len(subset)})
    n=len(results)
    metrics={'Evaluated games':n,'Top-1 hit %':100*sum(r['Top-1 credit'] for r in results)/n if n else None,'Top-3 hit %':100*sum(r['Top-3 credit'] for r in results)/n if n else None,'Log loss':sum(r['Log loss'] for r in results)/n if n else None,'Brier':sum(r['Brier'] for r in results)/n if n else None}
    return {'metrics':metrics,'games':results,'calibration':bins,'excluded':issues,'fingerprint':fingerprint(rows),'min_training':min_training,'window_days':MODEL_DAYS,'model':model,'shot_weight':shot_weight,'half_life':half_life,'temperature':temperature}

# Forward journal: local, immutable pregame forecasts; outcomes are stored separately.
def journal_connection(path=None):
    import sqlite3
    path=path or eng.DATA/'forward_journal.sqlite3'
    conn=sqlite3.connect(path,timeout=10)
    conn.execute('CREATE TABLE IF NOT EXISTS forecasts (game_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, outcome TEXT)')
    conn.commit()
    return conn


def save_forecast(game,rows,confirmed,model_version,history_hash,injury_time=None,path=None,now=None,model_forecasts=None,lineup_evidence=None):
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
              'model_version':model_version,'model':rows[0].get('Model','baseline'),'history_hash':history_hash,'injuries_checked_at':injury_time,'lineup_evidence':lineup_evidence or {},
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
                      'Lineup verification':' / '.join(t+': '+v.get('method','Not recorded') for t,v in sorted(snap.get('lineup_evidence',{}).items())) or 'Not recorded',
                      'NBA lineup retrieval UTC':' / '.join(t+': '+v['fetched_at'] for t,v in sorted(snap.get('lineup_evidence',{}).items()) if v.get('fetched_at')) or None,
                      'Top prediction':' / '.join(tops),'Top probability %':100*best,
                      'Winner':outcome['winner'] if outcome else 'Pending',
                      'Top-1 credit':outcome['top1_credit'] if outcome else None,
                      'Brier':outcome['brier'] if outcome else None,
                      'Log loss':('Infinite (zero-probability winner)' if outcome['outside_field'] else outcome['log_loss']) if outcome else None,
                      'Lineup matched':outcome['lineup_matches'] if outcome else None,
                      'Outside field':outcome['outside_field'] if outcome else None,
                      'Sample holds':sum(r['Status'] in ('HOLD: SAMPLE','HOLD: WEIGHTED SAMPLE','HOLD: SHOT COVERAGE') for r in snap['rows'])})
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


def forward_pick_games(records):
    """Diagnostics from frozen probabilities and settled outcomes, never a model rerun."""
    games=[]
    for record in records:
        outcome=record['outcome']
        if outcome is None:continue
        snap=record['snapshot'];values=sorted((r['_probability'] for r in snap['rows']),reverse=True)
        top=values[0];ties=sum(abs(p-top)<1e-12 for p in values)
        games.append({'Game':snap['game_id'],'Date':snap['date'],
                      'Top probability':top,'Top margin':0.0 if ties>1 else top-values[1],
                      'Tied leaders':ties,'Top-1 credit':outcome['top1_credit'],
                      'Outside field':outcome['outside_field'],'Lineup mismatch':not outcome['lineup_matches']})
    return games


def forward_equal_evidence(records):
    """Grade a uniform forecast over the saved field; retain every settled winner."""
    games=[];reference=[];outside=0;mismatches=0
    for record in records:
        outcome=record['outcome']
        if outcome is None:continue
        snap=record['snapshot'];rows=snap['rows']
        probs={r['_player_id']:r['_probability'] for r in rows}
        if len(rows)!=10 or len(probs)!=10 or any(not math.isfinite(p) or p<=0 for p in probs.values()) or abs(sum(probs.values())-1)>1e-8:
            raise ValueError('Forward evidence requires ten unique positive normalized probabilities.')
        winner=outcome['winner_id'];missing=winner not in probs
        outside+=int(missing);mismatches+=int(not outcome['lineup_matches'])
        common={'Game':snap['game_id'],'Date':snap['date']}
        games.append({**common,'Log loss':-math.log(probs[winner]) if not missing else None,
                      'Brier':sum((p-int(pid==winner))**2 for pid,p in probs.items())+int(missing),
                      'Top-1 credit':top_k_credit(probs,winner,1),'Top-3 credit':top_k_credit(probs,winner,3)})
        reference.append({**common,'Log loss':math.log(10) if not missing else None,
                          'Brier':1.1 if missing else .9,'Top-1 credit':0. if missing else .1,
                          'Top-3 credit':0. if missing else .3})
    metrics=('Brier','Top-1 credit','Top-3 credit') if outside else ('Log loss','Brier','Top-1 credit','Top-3 credit')
    comparison=compare_evaluations({'games':reference},{'games':games},metrics=metrics)
    evidence=benchmark_evidence_rows(comparison)
    if outside:
        evidence.insert(0,{'Metric':'Log loss','Model minus equal':None,'95% lower':None,'95% upper':None,
                           'Better direction':'Lower','Games':comparison['games'],'Dates':comparison['dates'],
                           'Reading':'Undefined difference: both forecasts have infinite log loss for outside-field winners'})
    return [{**r,'Outside-field winners':outside,'Lineup mismatches':mismatches} for r in evidence]


def forward_model_comparison(records):
    """All models evaluated on exactly the same prospectively saved games."""
    matched=[r for r in records if set(r['snapshot'].get('model_forecasts',{}))=={'baseline','recent','lineup'}]
    summaries=[];details=[];reliability=[];evidence=[]
    for model in ('baseline','recent','lineup'):
        viewed=journal_model_records(matched,model)
        summaries.append({'Model':model,**journal_summary(viewed)})
        evidence.extend({'Model':model,**r} for r in forward_equal_evidence(viewed))
        details.extend(journal_table(viewed))
        reliability.extend({'Model':model,**r} for r in pick_reliability(forward_pick_games(viewed)))
    return {'matched_games':len(matched),'excluded_games':len(records)-len(matched),'summary':summaries,'details':details,'pick_reliability':reliability,'equal_benchmark_evidence':evidence}


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
    observed=eng.opening_shot_games(valid)
    rows=sorted([r for r in valid if r['team']==team and r['player_id']==player_id],key=lambda r:(r['date'],r['game_id']),reverse=True)
    def summarize(label,records):
        n=len(records);shots=sum(int(r['first_team_shot']) for r in records)
        scores=sum(int(r['first_scorer']) for r in records)
        opportunities=sum(int(r['team_scored_first']) for r in records)
        known=sum((r['game_id'],team) in observed for r in records)
        return {'Window':label,'Starts':n,'Observed opening-shot starts':known,'Unknown opening-shot starts':n-known,'Team opening shots':shots,'Opening-shot rate %':100*shots/known if known else None,
                'Game first scores':scores,'First-score rate %':100*scores/n if n else None,
                'Team scored first':opportunities,'Share when team scored first %':100*scores/opportunities if opportunities else None,
                'Similar-lineup starts':sum(len(team_games[r['game_id']] & selected)>=4 for r in records)}
    logs=[{'Date':r['date'],'Game':r['game_id'],'Opponent':r['opponent'],
           'Opening shooter observed':(r['game_id'],team) in observed,
           'Took team first shot':bool(int(r['first_team_shot'])) if (r['game_id'],team) in observed else None,
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


def pick_reliability(games):
    """Descriptive top-pick diagnostics, one observation per evaluated game."""
    output=[]
    dimensions=(
        ('Top probability',((0,.15,'Below 15%'),(.15,.20,'15–20%'),(.20,.25,'20–25%'),(.25,.30,'25–30%'),(.30,float('inf'),'30%+'))),
        ('Top margin',((0,.02,'Below 2 pp'),(.02,.05,'2–5 pp'),(.05,.10,'5–10 pp'),(.10,float('inf'),'10 pp+'))))
    for dimension,bands in dimensions:
        for lo,hi,label in bands:
            subset=[r for r in games if lo<=r[dimension]<hi]
            if not subset:continue
            n=len(subset)
            predicted=100*sum(r['Top probability'] for r in subset)/n
            observed=100*sum(r['Top-1 credit'] for r in subset)/n
            output.append({'Group by':dimension,'Band':label,'Games':n,
                           'Dates':len({r['Date'] for r in subset}),
                           'Mean top probability %':predicted,'Observed top-1 hit %':observed,
                           'Observed minus predicted pp':observed-predicted,
                           'Tied-leader games':sum(r['Tied leaders']>1 for r in subset),
                           **({'Outside-field winners':sum(r['Outside field'] for r in subset),
                               'Lineup mismatches':sum(r['Lineup mismatch'] for r in subset)}
                              if all('Outside field' in r and 'Lineup mismatch' in r for r in subset) else {})})
    return output


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
    summary=[];monthly=[];details=[];latest={};reliability=[];stages=[];equal_evidence=[]
    for model,result in results.items():
        games=result['games'];newest=[r for r in games if r['Date'] in recent_dates]
        latest[model]={'games':newest}
        for label,subset in [('All evaluated dates',games),('Newest quarter of dates',newest)]:
            if subset:
                metrics=evaluation_metrics(subset)
                equal_evidence.extend({'Model':model,'Period':label,**r} for r in equal_benchmark_evidence(subset))
                stages.append({'Model':model,'Period':label,**scoring_stage_summary(subset)})
                reliability.extend({'Model':model,'Period':label,**r} for r in pick_reliability(subset))
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
            'equal_benchmark_evidence':equal_evidence,'scoring_stages':stages,'pick_reliability':reliability,'latest_comparisons':paired,'evaluated_dates':len(dates),'latest_dates':len(recent_dates),'excluded_games':len(results['baseline']['excluded'])}


def adaptive_signal_games(results,min_selection_games=100):
    """Choose among fixed blends using only earlier-date evaluated losses."""
    labels=('Current blend','Opening shot only','First score only')
    weights={'Current blend':.65,'Opening shot only':1.0,'First score only':0.0}
    if isinstance(min_selection_games,bool) or not isinstance(min_selection_games,int) or min_selection_games<1:
        raise ValueError('Selection requires a positive integer game minimum.')
    indexed={label:{(r['Date'],r['Game']):r for r in results[label]['games']} for label in labels}
    keys=set(indexed[labels[0]])
    if any(set(indexed[label])!=keys or len(indexed[label])!=len(results[label]['games']) for label in labels):
        raise ValueError('Adaptive selection requires identical games and dates.')
    for label in labels:
        for (day,gid),row in indexed[label].items():
            date.fromisoformat(day)
            if not math.isfinite(row['Log loss']) or row['Log loss']<0:
                raise ValueError('Adaptive selection requires finite nonnegative log losses.')
    byday=defaultdict(list)
    for key in sorted(keys):byday[key[0]].append(key)
    prior=[];chosen_games=[];decisions=[]
    for day in sorted(byday):
        cutoff=(date.fromisoformat(day)-timedelta(days=MODEL_DAYS)).isoformat()
        prior=[key for key in prior if key[0]>=cutoff]
        chosen='Current blend';learned=len(prior)>=min_selection_games
        losses={label:sum(indexed[label][key]['Log loss'] for key in prior)/len(prior) for label in labels} if prior else {}
        if learned:
            best=min(losses.values())
            # Prefer the current blend for numerical ties, then shot-only, score-only.
            chosen=next(label for label in labels if losses[label]<=best+1e-12)
        reason='Earlier-date loss comparison' if learned else 'Fallback: fewer than '+str(min_selection_games)+' prior evaluated games'
        decisions.append({'Date':day,'Selected signal':chosen,'Selected shot weight':weights[chosen],
                          'Selection training games':len(prior),'Selection training dates':len({key[0] for key in prior}),
                          'Selection reason':reason,**{label+' prior log loss':losses.get(label) for label in labels}})
        chosen_games.extend({**indexed[chosen][key],'Selected signal':chosen,'Selected shot weight':weights[chosen],
                             'Selection training games':len(prior),'Selection learned':learned} for key in byday[day])
        # Every matchup on a date gets the same decision before that date's outcomes.
        prior.extend(byday[day])
    return chosen_games,decisions


def adaptive_active_report(results):
    """Evaluate all variants on the pre-outcome subset with sufficient selection history."""
    adaptive=results['Earlier-date selector']['games']
    keys={(r['Date'],r['Game']) for r in adaptive if r['Selection learned']}
    summary=[];details=[];selected={}
    for label,result in results.items():
        subset=[r for r in result['games'] if (r['Date'],r['Game']) in keys]
        if len(subset)!=len(keys) or {(r['Date'],r['Game']) for r in subset}!=keys:
            raise ValueError('Active selection comparison requires identical games and dates.')
        selected[label]={'games':subset}
        if subset:summary.append({'Signal variant':label,**evaluation_metrics(subset),**scoring_stage_summary(subset)})
        details.extend({'Signal variant':label,**r} for r in subset)
    choices=[]
    for label in ('Current blend','Opening shot only','First score only'):
        subset=[r for r in adaptive if r['Selection learned'] and r['Selected signal']==label]
        choices.append({'Selected signal':label,'Games':len(subset),'Dates':len({r['Date'] for r in subset})})
    paired=compare_evaluations(selected['Current blend'],selected['Earlier-date selector'])
    return {'games':len(keys),'dates':len({d for d,g in keys}),
            'fallback_games':len(adaptive)-len(keys),'summary':summary,'details':details,
            'choices':choices,'comparison':paired['metrics']}


def compare_scoring_signals(history,min_training=100,model='baseline',progress=lambda text:None):
    """Fixed-signal and earlier-date adaptive experiments; never change live rankings."""
    variants={'Current blend':.65,'Opening shot only':1.0,'First score only':0.0}
    results={}
    for label,weight in variants.items():
        progress('Testing '+label.lower()+'…')
        results[label]=evaluate(history,min_training,model,shot_weight=weight)
    expected={(r['Game'],r['Date']) for r in results['Current blend']['games']}
    if any({(r['Game'],r['Date']) for r in result['games']}!=expected or len(result['games'])!=len(expected) for result in results.values()):
        raise ValueError('Signal comparisons require identical games and dates.')
    adaptive,decisions=adaptive_signal_games(results)
    results['Earlier-date selector']={'games':adaptive}
    variants['Earlier-date selector']=None
    dates=sorted({d for g,d in expected})
    newest=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    summary=[];details=[];recent={}
    for label,result in results.items():
        games=result['games'];latest=[r for r in games if r['Date'] in newest]
        recent[label]={'games':latest}
        for period,subset in [('All evaluated dates',games),('Newest quarter of dates',latest)]:
            if subset:summary.append({'Signal variant':label,'Period':period,'Shot weight':variants[label],**evaluation_metrics(subset),**scoring_stage_summary(subset)})
        details.extend({'Signal variant':label,'Shot weight':variants[label],'Newest quarter':r['Date'] in newest,**r} for r in games)
    paired=[]
    for label in ('Opening shot only','First score only','Earlier-date selector'):
        paired.extend({'Signal variant':label,**r} for r in compare_evaluations(recent['Current blend'],recent[label])['metrics'])
    return {'fingerprint':fingerprint(history),'model':model,'min_training':min_training,'summary':summary,
            'details':details,'recent_comparisons':paired,'latest_dates':len(newest),'selection_decisions':decisions,
            'adaptive_learned_games':sum(r['Selection learned'] for r in adaptive),'active_selection':adaptive_active_report(results),
            'excluded_games':len(results['Current blend']['excluded'])}


def research_export(history,engine_version,analysis_day,model='baseline'):
    """Build an explicit data-only review archive in memory; never read app files."""
    import io
    import csv
    import zipfile
    import re
    if not re.fullmatch(r'\d+\.\d+\.\d+',engine_version):raise ValueError('Invalid engine version.')
    date.fromisoformat(analysis_day)
    if model not in ('baseline','recent','lineup'):raise ValueError('Unknown model.')
    # Only known history columns are exported. Extra row fields, settings,
    # journal entries, source paths, environment variables and key files are absent.
    rows=[{field:'' if row.get(field) is None else str(row.get(field,'')) for field in eng.FIELDS} for row in history]
    valid,issues=audit(rows)
    active=history_window(valid,analysis_day)
    observed=eng.opening_shot_games(active)
    proxy=eng.team_stats(active)
    coverage=[]
    for team in sorted(eng.TEAMS):
        team_rows=[r for r in active if r['team']==team]
        games={r['game_id'] for r in team_rows}
        coverage.append({'Team':team,'Games in 400-day window':len(games),
                         'Observed opening-shot games':sum((gid,team) in observed for gid in games),
                         'Opening-action proxy games':proxy.get(team,{}).get('proxy_games',0),
                         'Latest valid game':max((r['date'] for r in team_rows),default='')})
    def csv_bytes(fields,records):
        stream=io.StringIO(newline='')
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(records)
        return stream.getvalue().encode('utf-8')
    metadata={'export_schema':1,'engine_version':engine_version,'analysis_day':analysis_day,'selected_model':model,
              'created_utc':datetime.now(ZoneInfo('UTC')).isoformat(),'model_window_days':MODEL_DAYS,
              'history_rows':len(rows),'history_games':len({r['game_id'] for r in rows}),
              'valid_games':len({r['game_id'] for r in valid}),'flagged_games':len(issues),
              'exported_history_fingerprint':fingerprint(rows),
              'first_valid_date':min((r['date'] for r in valid),default=None),
              'last_valid_date':max((r['date'] for r in valid),default=None)}
    files={'history.csv':csv_bytes(eng.FIELDS,rows),
           'quality_issues.csv':csv_bytes(['game_id','reason'],issues),
           'team_coverage.csv':csv_bytes(['Team','Games in 400-day window','Observed opening-shot games','Opening-action proxy games','Latest valid game'],coverage),
           'metadata.json':json.dumps(metadata,indent=2).encode('utf-8'),
           'READ_ME.txt':('APEX data-only research export\n\n'
                          'history.csv contains all saved rows in known history columns, including flagged games. No rows are repaired or deleted by export.\n'
                          'quality_issues.csv lists validation failures. team_coverage.csv uses only valid games within 400 days before the analysis date.\n'
                          'metadata.json identifies the engine version, selected model, analysis date and exported data fingerprint.\n'
                          'checksums.json contains SHA-256 hashes of every other file. These check bytes, not source authenticity.\n'
                          'This archive is not an app backup. It contains no program files, API-key files, environment configuration, odds cache or forward journal.\n'
                          'No API calls, uploads or model evaluations occur when preparing it. Review before sharing.\n'
                          'To reproduce research, use this engine version and pass history rows to research_tools.evaluate, validation_report or compare_scoring_signals with an explicit training minimum.\n'
                          'Historical starter-only selection and missing-play limitations still apply. This archive does not establish predictive accuracy or profit.\n').encode('utf-8')}
    files['checksums.json']=json.dumps({name:hashlib.sha256(content).hexdigest() for name,content in files.items()},indent=2).encode('utf-8')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in files.items():archive.writestr(name,content)
    return output.getvalue()


def compare_recency(history,min_training=100,model='recent',progress=lambda text:None):
    """Compare fixed decay choices; does not tune or deploy a winner."""
    if model not in ('recent','lineup'):raise ValueError('Recency comparison requires recent or lineup model.')
    results={}
    for half_life in (30,90,180):
        progress(f'Testing {half_life}-day half-life…')
        results[half_life]=evaluate(history,min_training,model,half_life=half_life)
    expected={(r['Game'],r['Date']) for r in results[90]['games']}
    if any({(r['Game'],r['Date']) for r in result['games']}!=expected or len(result['games'])!=len(expected) for result in results.values()):
        raise ValueError('Recency comparisons require identical games and dates.')
    dates=sorted({d for g,d in expected})
    newest=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    summary=[];details=[];recent={}
    for half_life,result in results.items():
        games=result['games'];latest=[r for r in games if r['Date'] in newest]
        recent[half_life]={'games':latest}
        for period,subset in [('All evaluated dates',games),('Newest quarter of dates',latest)]:
            if subset:summary.append({'Half-life days':half_life,'Period':period,**evaluation_metrics(subset),**scoring_stage_summary(subset)})
        details.extend({'Half-life days':half_life,'Newest quarter':r['Date'] in newest,**r} for r in games)
    paired=[]
    for half_life in (30,180):
        paired.extend({'Half-life days':half_life,**r} for r in compare_evaluations(recent[90],recent[half_life])['metrics'])
    return {'fingerprint':fingerprint(history),'model':model,'min_training':min_training,
            'summary':summary,'details':details,'recent_comparisons':paired,'latest_dates':len(newest),
            'excluded_games':len(results[90]['excluded'])}


def schedule_history_coverage(history,games,analysis_day,today=None):
    """Compare indexed completed events with saved data without importing or deleting."""
    target=date.fromisoformat(analysis_day)
    today=today or datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    end=min(target,date.fromisoformat(today));start=target-timedelta(days=MODEL_DAYS)
    indexed={}
    for game in games:
        gid=game['gameId'];day=date.fromisoformat(game['_date'])
        away=game['awayTeam']['teamTricode'];home=game['homeTeam']['teamTricode']
        if away==home or away not in eng.TEAMS or home not in eng.TEAMS:raise ValueError('Invalid schedule matchup in coverage check.')
        identity=(game['_date'],game['gameStatus'],away,home)
        if gid in indexed and indexed[gid]!=identity:raise ValueError('Conflicting schedule entries in coverage check.')
        indexed[gid]=identity
    valid,issues=audit(history)
    valid_by_id=defaultdict(list);raw_ids={r.get('game_id','') for r in history}
    for row in valid:valid_by_id[row['game_id']].append(row)
    reasons={r['game_id']:r['reason'] for r in issues}
    details=[]
    for gid,(day,status,away,home) in sorted(indexed.items(),key=lambda pair:(pair[1][0],pair[0])):
        if status!=3 or not start<=date.fromisoformat(day)<end:continue
        saved=valid_by_id.get(gid,[])
        if gid not in raw_ids:state='Missing';reason='Not in saved history'
        elif not saved:state='Saved invalid';reason=reasons.get(gid,'History validation failed')
        elif {r['date'] for r in saved}!={day} or {r['team'] for r in saved}!={away,home}:
            state='Schedule mismatch';reason='Saved date or teams disagree with the schedule index'
        else:state='Saved valid';reason=''
        details.append({'Game':gid,'Date':day,'Away':away,'Home':home,'Coverage':state,'Reason':reason})
    teams=[]
    for team in sorted(eng.TEAMS):
        subset=[r for r in details if team in (r['Away'],r['Home'])]
        counts={state:sum(r['Coverage']==state for r in subset) for state in ('Saved valid','Missing','Saved invalid','Schedule mismatch')}
        teams.append({'Team':team,'Indexed completed games':len(subset),**counts,
                      'Usable coverage %':100*counts['Saved valid']/len(subset) if subset else None})
    counts={state:sum(r['Coverage']==state for r in details) for state in ('Saved valid','Missing','Saved invalid','Schedule mismatch')}
    return {'details':details,'teams':teams,'counts':counts,'indexed_games':len(details),
            'window_start':start.isoformat(),'end_exclusive':end.isoformat(),
            'fingerprint':fingerprint(history),'analysis_day':analysis_day,'checked_on':today}


def check_season_coverage(history,season_end,analysis_day,progress=lambda text:None):
    games,warnings=season_index(season_end,progress)
    report=schedule_history_coverage(history,games,analysis_day)
    return {**report,'season_end':season_end,'schedule_warnings':warnings}


TEMPERATURES={'Unchanged':1.0,'Softer':1.25,'Sharper':.8}


def adaptive_temperature_games(results,min_selection_games=100,min_selection_dates=30):
    """Choose only from earlier-date out-of-sample forecasts, before seeing today's outcomes."""
    for value in (min_selection_games,min_selection_dates):
        if isinstance(value,bool) or not isinstance(value,int) or value<1:raise ValueError('Selection minimums must be positive integers.')
    labels=tuple(TEMPERATURES)
    indexed={label:{(r['Date'],r['Game']):r for r in results[label]['games']} for label in labels}
    keys=set(indexed[labels[0]])
    if any(set(indexed[label])!=keys or len(indexed[label])!=len(results[label]['games']) for label in labels):raise ValueError('Temperature variants require identical games and dates.')
    if len({gid for day,gid in keys})!=len(keys):raise ValueError('Duplicate evaluation game IDs.')
    for label in labels:
        for (day,gid),row in indexed[label].items():
            date.fromisoformat(day)
            if not math.isfinite(row['Log loss']) or row['Log loss']<0:raise ValueError('Selection requires finite nonnegative log loss.')
    byday=defaultdict(list)
    for key in sorted(keys):byday[key[0]].append(key)
    prior=[];chosen_games=[];decisions=[]
    for day in sorted(byday):
        cutoff=(date.fromisoformat(day)-timedelta(days=MODEL_DAYS)).isoformat()
        prior=[key for key in prior if key[0]>=cutoff]
        dates=len({key[0] for key in prior})
        learned=len(prior)>=min_selection_games and dates>=min_selection_dates
        losses={label:sum(indexed[label][key]['Log loss'] for key in prior)/len(prior) for label in labels} if prior else {}
        chosen='Unchanged'
        if learned:
            best=min(losses.values());chosen=next(label for label in labels if losses[label]<=best+1e-12)
        decision={'Date':day,'Selected adjustment':chosen,'Temperature':TEMPERATURES[chosen],
                  'Selection training games':len(prior),'Selection training dates':dates,'Selection learned':learned,
                  'Selection reason':'Earlier-date log-loss comparison' if learned else f'Fallback: needs {min_selection_games} earlier evaluated games across {min_selection_dates} dates',
                  **{label+' prior log loss':losses.get(label) for label in labels}}
        decisions.append(decision)
        chosen_games.extend({**indexed[chosen][key],**decision} for key in byday[day])
        prior.extend(byday[day])
    return chosen_games,decisions


def compare_temperature(history,min_training=100,model='baseline',progress=lambda text:None):
    results={}
    for label,temperature in TEMPERATURES.items():
        progress('Testing '+label.lower()+' probabilities…')
        results[label]=evaluate(history,min_training,model,temperature=temperature)
    adaptive,decisions=adaptive_temperature_games(results)
    results['Earlier-date adjustment']={'games':adaptive}
    dates=sorted({r['Date'] for r in adaptive})
    latest=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    learned={(r['Date'],r['Game']) for r in adaptive if r['Selection learned']}
    summary=[];details=[];comparisons=[]
    periods=(('All evaluated dates',lambda r:True),('Newest quarter of dates',lambda r:r['Date'] in latest),
             ('After selection warmup',lambda r:(r['Date'],r['Game']) in learned))
    for period,include in periods:
        subsets={label:[r for r in result['games'] if include(r)] for label,result in results.items()}
        for label,subset in subsets.items():
            if subset:summary.append({'Variant':label,'Period':period,'Dates':len({r['Date'] for r in subset}),**evaluation_metrics(subset)})
        for label in ('Softer','Sharper','Earlier-date adjustment'):
            comparison=compare_evaluations({'games':subsets['Unchanged']},{'games':subsets[label]})
            comparisons.extend({'Variant':label,'Period':period,'Games':comparison['games'],'Dates':comparison['dates'],**r} for r in comparison['metrics'])
    for label,result in results.items():details.extend({'Variant':label,**r} for r in result['games'])
    return {'fingerprint':fingerprint(history),'min_training':min_training,'model':model,'summary':summary,
            'comparisons':comparisons,'details':details,'decisions':decisions,'learned_games':len(learned),
            'learned_dates':len({day for day,gid in learned}),'latest_dates':len(latest),'excluded_games':len(results['Unchanged']['excluded'])}


def evaluate_starting_fives(history,as_of):
    """Historical lineup forecasts using earlier dates only; no hindsight roster filter."""
    date.fromisoformat(as_of)
    valid,issues=audit(history)
    byday=defaultdict(lambda:defaultdict(list))
    for row in valid:
        if row['date']<as_of:byday[row['date']][row['game_id']].append(row)
    prior=defaultdict(list);details=[];skipped=0
    labels=('Last recorded five','Recent start frequency')
    for day in sorted(byday):
        target=date.fromisoformat(day);cutoff=(target-timedelta(days=60)).isoformat()
        for gid,game in sorted(byday[day].items()):
            winner=next(r for r in game if int(r['first_scorer']))
            for team in sorted({r['team'] for r in game}):
                previous=sorted((g for g in prior[team] if g[0]['date']>=cutoff),key=lambda g:(g[0]['date'],g[0]['game_id']),reverse=True)[:5]
                if len(previous)<5 or (target-date.fromisoformat(previous[0][0]['date'])).days>30:
                    skipped+=1;continue
                latest={r['player_id'] for r in previous[0]}
                counts=defaultdict(int);last_start={};names={}
                for old_game in previous:
                    for row in old_game:
                        pid=row['player_id'];counts[pid]+=1;names.setdefault(pid,row['player'])
                        last_start.setdefault(pid,row['date'])
                # Dates are ISO strings; use ordinals for descending chronological tie-breaking.
                candidates=sorted(counts,key=lambda pid:(-counts[pid],-int(pid in latest),-date.fromisoformat(last_start[pid]).toordinal(),pid))[:5]
                actual={r['player_id'] for r in game if r['team']==team}
                for label,projected in zip(labels,(latest,set(candidates))):
                    hits=len(projected&actual)
                    details.append({'Method':label,'Game':gid,'Date':day,'Team':team,
                                    'Latest training game':previous[0][0]['date'],'Earlier team games':len(previous),
                                    'Correct starters':hits,'Exact five':int(hits==5),
                                    'Winning team':team==winner['team'],
                                    'First scorer covered':int(winner['player_id'] in projected) if team==winner['team'] else None,
                                    'Projected player IDs':' / '.join(sorted(projected)),
                                    'Projected players':' / '.join(names[pid] for pid in sorted(projected)),
                                    'Actual player IDs':' / '.join(sorted(actual)),
                                    'Missed starter IDs':' / '.join(sorted(actual-projected))})
        # Same-day games never feed another game's starting-five forecast that day.
        for game in byday[day].values():
            for team in {r['team'] for r in game}:prior[team].append([r for r in game if r['team']==team])
    dates=sorted({r['Date'] for r in details})
    latest_dates=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    summary=[]
    for period in ('All evaluated dates','Newest quarter of dates'):
        for method in labels:
            subset=[r for r in details if r['Method']==method and (period=='All evaluated dates' or r['Date'] in latest_dates)]
            if not subset:continue
            winning=[r for r in subset if r['Winning team']]
            summary.append({'Method':method,'Period':period,'Team lineups':len(subset),'Dates':len({r['Date'] for r in subset}),
                            'Exact five %':100*sum(r['Exact five'] for r in subset)/len(subset),
                            'Starter slots matched %':100*sum(r['Correct starters'] for r in subset)/(5*len(subset)),
                            'Eligible winning-team lineups':len(winning),
                            'First scorer covered %':100*sum(r['First scorer covered'] for r in winning)/len(winning) if winning else None})
    return {'fingerprint':fingerprint(history),'as_of':as_of,'summary':summary,'details':details,
            'skipped_team_lineups':skipped,'excluded_games':len(issues),'evaluated_dates':len(dates),'latest_dates':len(latest_dates)}


def compare_opening_conversion(history,min_training=100):
    results={label:evaluate(history,min_training,model=model) for label,model in (('Recent form','recent'),('Opening-shot conversion','conversion'))}
    dates=sorted({r['Date'] for r in results['Recent form']['games']})
    latest=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    summary=[];details=[];comparisons=[]
    for period in ('All evaluated dates','Newest quarter of dates'):
        subsets={label:[r for r in result['games'] if period=='All evaluated dates' or r['Date'] in latest] for label,result in results.items()}
        for label,games in subsets.items():
            if games:summary.append({'Model':label,'Period':period,'Dates':len({r['Date'] for r in games}),
                'Games with conversion training data':sum(r['Known conversion training attempts']>0 for r in games),
                **evaluation_metrics(games),**scoring_stage_summary(games)})
        paired=compare_evaluations({'games':subsets['Recent form']},{'games':subsets['Opening-shot conversion']})
        comparisons.extend({'Period':period,'Games':paired['games'],'Dates':paired['dates'],**r} for r in paired['metrics'])
    for label,result in results.items():details.extend({'Model':label,**r} for r in result['games'])
    valid,_=audit(history)
    known=[r for r in valid if int(r['first_team_shot'])==1 and str(r.get('first_team_shot_made','')) in ('0','1')]
    return {'fingerprint':fingerprint(history),'min_training':min_training,'summary':summary,'comparisons':comparisons,'details':details,
            'known_attempts':len(known),'known_makes':sum(int(r['first_team_shot_made']) for r in known),'latest_dates':len(latest)}


def enrich_opening_results(game_ids,progress=lambda text:None,_batch_backup=None):
    """Add only missing opening-shot results after checking all existing outcome facts."""
    import os,re,tempfile
    selected=list(dict.fromkeys(game_ids))
    if not selected or len(selected)>20:raise ValueError('Choose between 1 and 20 saved games.')
    original=eng.HISTORY.read_bytes();history=eng.read_csv(eng.HISTORY)
    valid,issues=audit(history)
    if issues:raise ValueError('Repair invalid history before enriching opening shots.')
    groups=defaultdict(list)
    for row in valid:groups[row['game_id']].append(row)
    if any(gid not in groups for gid in selected):raise ValueError('Selected game is not in saved history.')
    updates={};errors=[]
    for i,gid in enumerate(selected,1):
        progress(f'Opening-shot results {i}/{len(selected)} · {gid}')
        try:
            if not re.fullmatch(r'espn_\d+',gid):raise ValueError('Only ESPN games can be enriched.')
            old=groups[gid];day=old[0]['date']
            if day>=datetime.now(ZoneInfo('America/New_York')).date().isoformat():raise ValueError('Only earlier completed dates can be enriched.')
            payload=core.request(eng.ESPN_BASE+'/summary',{'event':gid.removeprefix('espn_')})
            comp=payload['header']['competitions'][0];sides={c['homeAway']:eng.espn_team(c['team']) for c in comp['competitors']}
            if set(sides.values())!={r['team'] for r in old}:raise ValueError('Stored matchup differs from provider.')
            start=datetime.fromisoformat(comp['date'].replace('Z','+00:00'))
            if start.tzinfo is None or start.astimezone(ZoneInfo('America/New_York')).date().isoformat()!=day:raise ValueError('Stored date differs from provider.')
            game={'gameId':gid,'_date':day,'homeTeam':{'teamTricode':sides['home']},'awayTeam':{'teamTricode':sides['away']}}
            eng.validate_espn_summary(game,payload);play,box=eng.espn_game_payloads(payload);fresh=eng.extract_game(game,play,box)
            _,bad=audit(fresh)
            if bad:raise ValueError(bad[0]['reason'])
            indexed={r['player_id']:r for r in fresh}
            if set(indexed)!={r['player_id'] for r in old}:raise ValueError('Stored starters differ from provider; no enrichment applied.')
            patch={}
            for row in old:
                new=indexed[row['player_id']]
                facts=('date','team','opponent','first_team_shot','first_game_shot','first_scorer','first_fg_scorer','team_scored_first','tip_first_action')
                if any(str(row[f])!=str(new[f]) for f in facts):raise ValueError('Stored outcomes differ from provider; no enrichment applied.')
                additions={}
                for field,allowed in (('first_team_shot_made',('0','1')),('opening_score_path',('free_throw_before_fg','opening_fg_made','opening_fg_missed'))):
                    value=new.get(field,'');current=row.get(field,'')
                    if str(current) in allowed and str(value)!=str(current):raise ValueError('Existing opening data differs from provider.')
                    if str(current) not in allowed and str(value) in allowed:additions[field]=value
                if additions:patch[row['player_id']]=additions
            if not patch:raise ValueError('No missing opening-shot outcomes could be resolved.')
            updates[gid]=patch
        except (RuntimeError,ValueError,KeyError,TypeError,IndexError) as exc:errors.append({'game_id':gid,'reason':str(exc)})
    backup=None
    if updates:
        if eng.HISTORY.read_bytes()!=original:raise ValueError('History changed during enrichment; nothing was written.')
        enriched=[{**r,**updates.get(r['game_id'],{}).get(r['player_id'],{})} for r in history]
        _,bad=audit(enriched)
        if bad:raise ValueError('Enriched history failed validation; nothing was written.')
        if _batch_backup is None:
            fd,name=tempfile.mkstemp(prefix='history_before_opening_results_',suffix='.csv',dir=eng.DATA);backup=Path(name)
            with os.fdopen(fd,'wb') as stream:stream.write(original);stream.flush();os.fsync(stream.fileno())
        else:
            backup=Path(_batch_backup)
            if backup.parent.resolve()!=eng.DATA.resolve() or not backup.name.startswith('history_before_opening_results_') or not backup.is_file():
                raise ValueError('Batch backup is missing or invalid; history was not written.')
        fields=list(history[0])
        for field in ('first_team_shot_made','opening_score_path'):
            if field not in fields:fields.append(field)
        eng.write_csv(eng.HISTORY,fields,enriched)
    return {'attempted':len(selected),'enriched_games':len(updates),'added_results':sum('first_team_shot_made' in fields for patch in updates.values() for fields in patch.values()),'added_paths':sum(any('opening_score_path' in fields for fields in patch.values()) for patch in updates.values()),'errors':errors,'backup':backup.name if backup else None}


def compare_post_miss(history,min_training=100):
    results={label:evaluate(history,min_training,model=model) for label,model in (('Opening conversion','conversion'),('Post-miss challenger','post_miss'))}
    dates=sorted({r['Date'] for r in results['Opening conversion']['games']})
    latest=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    eligible={(r['Date'],r['Game']) for r in results['Opening conversion']['games'] if r['Minimum team sequence games']>=10}
    summary=[];details=[];comparisons=[]
    for period in ('All evaluated dates','Newest quarter of dates','After sequence minimum'):
        subsets={label:[r for r in result['games'] if period=='All evaluated dates' or (r['Date'] in latest if period=='Newest quarter of dates' else (r['Date'],r['Game']) in eligible)] for label,result in results.items()}
        for label,games in subsets.items():
            if games:summary.append({'Model':label,'Period':period,'Dates':len({r['Date'] for r in games}),**evaluation_metrics(games)})
        paired=compare_evaluations({'games':subsets['Opening conversion']},{'games':subsets['Post-miss challenger']})
        comparisons.extend({'Period':period,'Games':paired['games'],'Dates':paired['dates'],**r} for r in paired['metrics'])
    for label,result in results.items():details.extend({'Model':label,**r} for r in result['games'])
    valid,_=audit(history);paths={r['game_id']:r.get('opening_score_path','') for r in valid}
    return {'fingerprint':fingerprint(history),'min_training':min_training,'summary':summary,'details':details,'comparisons':comparisons,
            'eligible_games':len(eligible),'path_counts':{path:sum(v==path for v in paths.values()) for path in ('free_throw_before_fg','opening_fg_made','opening_fg_missed')}}


def opening_enrichment_candidates(history,today):
    """Only valid, earlier-date saved ESPN games with unresolved opening data."""
    import re
    date.fromisoformat(today)
    valid,issues=audit(history)
    if issues:raise ValueError('Repair invalid history before running batch enrichment.')
    groups=defaultdict(list)
    for row in valid:groups[row['game_id']].append(row)
    result=[]
    for gid,rows in groups.items():
        if not re.fullmatch(r'espn_\d+',gid) or rows[0]['date']>=today:continue
        missing_shots=sum(int(r['first_team_shot'])==1 and str(r.get('first_team_shot_made','')) not in ('0','1') for r in rows)
        missing_path=rows[0].get('opening_score_path','') not in ('free_throw_before_fg','opening_fg_made','opening_fg_missed')
        if missing_shots or missing_path:result.append({'game_id':gid,'date':rows[0]['date'],'missing_shots':missing_shots,'missing_path':missing_path})
    return sorted(result,key=lambda r:(r['date'],r['game_id']),reverse=True)


def read_opening_attempts(path):
    if not path.exists():return {}
    try:
        record=json.loads(path.read_text());attempts=record['attempts']
        if record.get('schema')!=1 or record.get('kind')!='opening_enrichment' or not isinstance(attempts,dict):raise ValueError()
        if any(not isinstance(gid,str) or not gid or isinstance(n,bool) or not isinstance(n,int) or n<0 for gid,n in attempts.items()):raise ValueError()
        return attempts
    except (ValueError,KeyError,TypeError,AttributeError):raise ValueError('Opening-data retry tracker is invalid; no batch requests were made.')


def write_opening_attempts(path,attempts):
    import os,tempfile
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='opening_attempts_',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump({'schema':1,'kind':'opening_enrichment','attempts':attempts},stream)
            stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()


def enrich_opening_batch(limit=20,progress=lambda text:None):
    """Checkpoint each game, sharing one backup and persisting fair retry priority."""
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=50:raise ValueError('Batch size must be an integer from 1 to 50.')
    today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    history=eng.read_csv(eng.HISTORY)
    candidates=opening_enrichment_candidates(history,today)
    tracker=eng.DATA/'opening_enrichment_attempts.json';attempts=read_opening_attempts(tracker)
    selected=sorted(candidates,key=lambda r:(attempts.get(r['game_id'],0),-date.fromisoformat(r['date']).toordinal(),r['game_id']))[:limit]
    report={'attempted':0,'enriched_games':0,'added_results':0,'added_paths':0,'errors':[],'backup':None,
            'retry_attempted':sum(attempts.get(r['game_id'],0)>0 for r in selected),'remaining':len(candidates),
            'never_attempted_remaining':sum(attempts.get(r['game_id'],0)==0 for r in candidates)}
    if not selected:return report
    expected=eng.HISTORY.read_bytes();backup=None
    for index,row in enumerate(selected,1):
        gid=row['game_id'];progress(f'Opening-data batch {index}/{len(selected)} · {gid}')
        if eng.HISTORY.read_bytes()!=expected:raise ValueError('History changed between batch games. Earlier saved results remain; stop other imports before retrying.')
        attempts[gid]=attempts.get(gid,0)+1
        write_opening_attempts(tracker,attempts)  # Persist before starting the request, including interrupted attempts.
        single=enrich_opening_results([gid],_batch_backup=backup)
        expected=eng.HISTORY.read_bytes()
        for field in ('attempted','enriched_games','added_results','added_paths'):report[field]+=single[field]
        report['errors'].extend(single['errors'])
        if single['backup']:backup=eng.DATA/single['backup'];report['backup']=single['backup']
    remaining=opening_enrichment_candidates(eng.read_csv(eng.HISTORY),today)
    report['remaining']=len(remaining)
    report['never_attempted_remaining']=sum(attempts.get(r['game_id'],0)==0 for r in remaining)
    return report


def scoring_model_scorecard(history,min_training=100,progress=lambda text:None):
    """Same-game assessment of live models and challengers, without selecting a winner."""
    models=('baseline','recent','lineup','conversion','post_miss')
    results={}
    for model in models:
        progress('Evaluating '+model.replace('_',' ')+'…')
        results[model]=evaluate(history,min_training,model=model)
    reference=results['baseline']['games']
    expected={(r['Date'],r['Game']) for r in reference}
    if len({r['Game'] for r in reference})!=len(reference):raise ValueError('Duplicate scorecard games.')
    for result in results.values():
        if len(result['games'])!=len(expected) or {(r['Date'],r['Game']) for r in result['games']}!=expected:
            raise ValueError('Scorecard models must evaluate identical games and dates.')
    dates=sorted({day for day,gid in expected})
    latest=set(dates[-max(1,math.ceil(len(dates)/4)):]) if dates else set()
    active={(r['Date'],r['Game']) for r in reference if r['Known conversion training attempts']>0 and r['Minimum team sequence games']>=10}
    periods=(('All evaluated dates',lambda r:True),('Newest quarter of dates',lambda r:r['Date'] in latest),
             ('Challenger-active games',lambda r:(r['Date'],r['Game']) in active))
    summaries=[];paired=[];details=[];coverage=[]
    for period,include in periods:
        subsets={model:[r for r in result['games'] if include(r)] for model,result in results.items()}
        base=evaluation_metrics(subsets['baseline'])
        selected=subsets['baseline']
        coverage.append({'Period':period,'Games':len(selected),'Dates':len({r['Date'] for r in selected}),
                         'Conversion-data games':sum(r['Known conversion training attempts']>0 for r in selected),
                         'Sequence-eligible games':sum(r['Minimum team sequence games']>=10 for r in selected)})
        for model,rows in subsets.items():
            if not rows:continue
            metrics=evaluation_metrics(rows)
            summaries.append({'Period':period,'Model':model,'Dates':len({r['Date'] for r in rows}),
                              'First date':min(r['Date'] for r in rows),'Last date':max(r['Date'] for r in rows),**metrics,
                              'Log loss minus baseline':metrics['Log loss']-base['Log loss'],
                              'Brier minus baseline':metrics['Brier']-base['Brier'],
                              'Top-1 difference pp':metrics['Top-1 hit %']-base['Top-1 hit %'],
                              **scoring_stage_summary(rows)})
            if model!='baseline':
                comparison=compare_evaluations({'games':selected},{'games':rows})
                paired.extend({'Period':period,'Model':model,'Games':comparison['games'],'Dates':comparison['dates'],**r} for r in comparison['metrics'])
    for model,result in results.items():
        details.extend({'Model':model,'Challenger-active':(r['Date'],r['Game']) in active,**r} for r in result['games'])
    return {'fingerprint':fingerprint(history),'min_training':min_training,'summary':summaries,'paired':paired,'details':details,
            'coverage':coverage,'active_games':len(active),'excluded_games':len(results['baseline']['excluded'])}
