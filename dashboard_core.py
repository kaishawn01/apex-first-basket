"""Data access and dashboard logic; provider IDs never cross provider boundaries."""
import json
import time
from datetime import datetime, timezone
import requests
import first_basket_engine as eng


def request(url, params=None, key=None):
    headers = {"User-Agent": "APEX-Local-Dashboard/2.0", "Accept": "application/json"}
    if key:
        headers["Authorization"] = key
    try:
        r = requests.get(url, params=params, headers=headers, timeout=25)
        if r.status_code != 200:
            raise RuntimeError(f"Data request returned HTTP {r.status_code}. Check access, subscription, or try again later.")
        return r.json()
    except requests.RequestException:
        raise RuntimeError("Could not reach the data provider. Check your connection and retry.") from None
    except ValueError:
        raise RuntimeError("Provider returned an unreadable response.") from None


def fresh_schedule(day):
    payload = request(eng.ESPN_BASE + "/scoreboard", {"dates": day.replace("-", ""), "limit": 1000})
    return [g for g in eng.parse_espn_schedule(payload) if g['_date']==day]


def upcoming(g, now=None):
    return eng.game_is_upcoming(g,now)


def roster(team):
    inverse = {v:k for k,v in eng.ESPN_ALIASES.items()}
    data = request(eng.ESPN_BASE + f"/teams/{inverse.get(team, team).lower()}/roster")
    result = []
    for a in data.get("athletes", []):
        if a.get("id") and a.get("displayName"):
            result.append({"player_id": str(a["id"]), "player": a["displayName"]})
    if not result:
        raise RuntimeError(f"No roster returned for {team}.")
    return result


def projection_evidence(history, team, day, players, roster_verified=True):
    """Recent recorded starts, not provider-confirmed starting lineups."""
    from datetime import date, timedelta
    from collections import defaultdict
    import research_tools as research
    target=date.fromisoformat(day)
    allowed={p['player_id']:p for p in players}
    if len(allowed)!=len(players):raise ValueError('Roster contains duplicate player IDs.')
    valid,issues=research.audit(history)
    games=defaultdict(list)
    for r in valid:
        if r['team']==team and r['date']<day:games[r['game_id']].append(r)
    ordered=sorted(games.values(),key=lambda g:(g[0]['date'],g[0]['game_id']),reverse=True)
    latest=ordered[0] if ordered else []
    last_day=latest[0]['date'] if latest else None
    age=(target-date.fromisoformat(last_day)).days if last_day else None
    cutoff=(target-timedelta(days=60)).isoformat()
    recent=[g for g in ordered if g[0]['date']>=cutoff][:5]
    latest_ids={r['player_id'] for r in latest}
    defaults=[r['player_id'] for r in latest if r['player_id'] in allowed] if roster_verified and age is not None and age<=30 else []
    warnings=[]
    if not roster_verified:warnings.append('Current roster unavailable: no automatic starter selections. Historical names are manual options only.')
    if age is None:warnings.append('No valid earlier starting-five history for this team. Choose the announced starters manually.')
    elif age>30:warnings.append(f'Last recorded starting five is {age} days old. Automatic selections are withheld; review all five starters.')
    if latest and roster_verified:
        removed=[r['player'] for r in latest if r['player_id'] not in allowed]
        if removed:warnings.append('Last-game starters absent from the loaded roster: '+', '.join(removed)+'. Vacancies require manual selection.')
    if len(recent)<5:warnings.append(f'Only {len(recent)} valid recorded team games are available in the last 60 days; recent-start counts may be incomplete.')
    evidence=[]
    for pid,player in allowed.items():
        starts=[g for g in recent if any(r['player_id']==pid for r in g)]
        earlier=[g for g in ordered if any(r['player_id']==pid for r in g)]
        last_start=earlier[0][0]['date'] if earlier else None
        evidence.append({'Player ID':pid,'Player':player['player'],'Started last recorded game':pid in latest_ids,
                         'Starts in recent recorded games':len(starts),'Recorded games reviewed':len(recent),
                         'Last recorded start':last_start,'Days since recorded start':(target-date.fromisoformat(last_start)).days if last_start else None,
                         'Selection basis':'Last-game projection' if pid in defaults else 'Review candidate' if starts else 'No recent recorded starts'})
    evidence.sort(key=lambda r:(-r['Starts in recent recorded games'],-int(r['Started last recorded game']),r['Player ID']))
    return {'defaults':defaults,'players':evidence,'warnings':warnings,'last_game_date':last_day,
            'history_age_days':age,'reviewed_games':len(recent),'roster_loaded':roster_verified}


def projections(history, team, day, players):
    return projection_evidence(history,team,day,players)['defaults']


def injury_reports(key):
    if not key:
        raise ValueError("Enter your BALLDONTLIE key in Settings first.")
    base = "https://api.balldontlie.io/v1"
    teams = request(base + "/teams", key=key)
    lookup = {str(t["id"]): t["abbreviation"] for t in teams["data"]}
    result, cursor, seen = [], None, set()
    while True:
        params = {"per_page": 100}
        if cursor is not None:
            params["cursor"] = cursor
        payload = request(base + "/player_injuries", params, key)
        for row in payload["data"]:
            p = row["player"]
            team = p.get("team", {})
            code = team.get("abbreviation") or lookup.get(str(p.get("team_id")), "")
            result.append({"team": code, "player": f"{p['first_name']} {p['last_name']}",
                           "status": row.get("status", "Unknown"), "description": row.get("description", "")})
        cursor = payload.get("meta", {}).get("next_cursor")
        if cursor is None:
            return result
        if cursor in seen:
            raise RuntimeError("Injury pagination repeated. Please retry later.")
        seen.add(cursor)
        time.sleep(1.1)  # All-Star permits 60 requests per minute.


def injury_for(reports, team, player):
    matches = [r for r in reports if r["team"] == team and eng.norm(r["player"]) == eng.norm(player)]
    return matches[0] if len(matches) == 1 else None


def live_prices(key, games):
    if not key:
        raise ValueError("Enter your Odds API key in Settings first.")
    events = request(eng.ODDS_BASE + "/events", {"apiKey": key})
    prices, messages = {}, []
    for g in games:
        home, away = (g[s]["teamTricode"] for s in ("homeTeam", "awayTeam"))
        matches = [e for e in events if eng.norm(e.get("home_team")) == eng.norm(eng.TEAMS[home])
                   and eng.norm(e.get("away_team")) == eng.norm(eng.TEAMS[away])
                   and abs((datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) - datetime.fromisoformat(g["start_time"].replace("Z", "+00:00"))).total_seconds()) < 3600]
        if len(matches) != 1:
            messages.append(f"{away}@{home}: no unique odds event matched.")
            continue
        event = matches[0]
        data = request(eng.ODDS_BASE + f"/events/{event['id']}/odds", {
            "apiKey": key, "regions": "us", "bookmakers": "fanduel",
            "markets": "player_first_basket", "oddsFormat": "american"})
        count = 0
        for book in data.get("bookmakers", []):
            if book.get("key") != "fanduel":
                continue
            for market in book.get("markets", []):
                if market.get("key") != "player_first_basket":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome.get("description") and outcome.get("name", "").lower() != "yes":
                        continue
                    name = outcome.get("description") or outcome.get("name", "")
                    odds = outcome.get("price")
                    dec = eng.american_to_decimal(odds)
                    if name and dec:
                        prices[(g["gameId"], eng.norm(name))] = (dec, str(odds), "FanDuel", market.get("last_update") or book.get("last_update", ""))
                        count += 1
        if not count:
            messages.append(f"{away}@{home}: no FanDuel first-basket market returned. Check plan and market coverage.")
    return prices, messages


def rank_game(history, game, lineups, confirmed, prices, reports, model="baseline"):
    if model not in ("baseline", "recent", "lineup"): raise ValueError("Unknown model.")
    from research_tools import history_window, audit
    hist, issues = audit(history_window(history, game["_date"]))
    if issues:
        raise ValueError("Historical data failed validation. Open Data quality before ranking.")
    away, home = (game[s]["teamTricode"] for s in ("awayTeam", "homeTeam"))
    for t in (away, home):
        ids = [p["player_id"] for p in lineups[t]]
        if len(ids) != 5 or len(set(ids)) != 5:
            raise ValueError(f"Choose exactly five distinct players for {t}.")
    if {p['player_id'] for p in lineups[away]} & {p['player_id'] for p in lineups[home]}:
        raise ValueError("A player cannot appear on both teams.")
    predictions=eng.predict_first_score(hist,lineups,game["_date"],model)
    stats = eng.team_stats(hist)
    shot_coverage=eng.opening_shot_games(hist)
    shot_samples={}
    for r in hist:
        if (r["game_id"],r["team"]) not in shot_coverage:continue
        key=(r["team"],r["player_id"])
        count,mass=shot_samples.get(key,(0,0.0))
        age=(datetime.fromisoformat(game["_date"])-datetime.fromisoformat(r["date"])).days
        shot_samples[key]=(count+1,mass+2**(-age/90.0))
    pa = eng.first_team_probability(away, home, stats)
    baseline_pa = pa
    recent_stats = eng.recent_team_stats(hist,game["_date"])
    if model!="baseline": pa=eng.recent_first_team_probability(away,home,recent_stats)
    all_confirmed = all(confirmed.get(t, False) for t in (away, home))
    injury_conflict = any(injury_for(reports,t,p['player']) for t in (away,home) for p in lineups[t])
    target = datetime.fromisoformat(game["_date"])
    season_start = f"{target.year if target.month >= 10 else target.year-1}-10-01"
    current = [r for r in hist if r["date"] >= season_start]
    rows=[]
    for team, team_p in ((away, pa), (home, 1-pa)):
        baseline={r[0]['player_id']:r[1] for r in eng.player_weights(hist,lineups[team],team)}
        recent={r[0]['player_id']:r for r in eng.recent_player_weights(hist,lineups[team],team,game['_date'])}
        context={r[0]['player_id']:r for r in eng.lineup_player_weights(hist,lineups[team],team,game['_date'])} if model=='lineup' else {}
        weights=list(context.values()) if model=='lineup' else eng.recent_player_weights(hist,lineups[team],team,game['_date']) if model=='recent' else eng.player_weights(hist,lineups[team],team)
        for player, share, starts, *_ in weights:
            p=predictions[player["player_id"]]
            price=prices.get((game['gameId'],eng.norm(player['player'])))
            report=injury_for(reports,team,player['player'])
            shot_count,shot_mass=shot_samples.get((team,player['player_id']),(0,0.0))
            shot_insufficient=shot_count<8 or (model!='baseline' and shot_mass<8)
            shot_note=('Below 8 observed opening-shot starts' if shot_count<8 else 'Below 8 decayed opening-shot starts' if model!='baseline' and shot_mass<8 else 'Meets shot-count safeguard; accuracy unvalidated')
            enough=all(stats.get(t,{}).get('n',0)>=10 for t in (away,home)) and starts>=8
            status='HOLD: LINEUP' if not all_confirmed else 'HOLD: INJURY REVIEW' if injury_conflict else 'HOLD: SAMPLE' if not enough else 'NO PRICE' if not price else 'RESEARCH ONLY'
            if model!='baseline' and (recent[player['player_id']][5]<8 or any(recent_stats.get(t,{}).get('weighted_games',0)<10 for t in (away,home))) and status not in ('HOLD: LINEUP','HOLD: INJURY REVIEW'):
                status='HOLD: WEIGHTED SAMPLE'
            if shot_insufficient and not status.startswith('HOLD:'):
                status='HOLD: SHOT COVERAGE'
            if game.get('research_only'):
                status='RESEARCH MATCHUP';price=None;prices={}
            fair=100*(1-p)/p if p<=.5 else -100*p/(1-p)
            rows.append({'_game_id':game['gameId'],'_player_id':player['player_id'],'_probability':p,'_research_only':bool(game.get('research_only')),'Model':model,'Matchup':f'{away} @ {home}','Player':player['player'],'Team':team,
                         'Model %':round(p*100,2),'Baseline %':round(baseline[player['player_id']]*(baseline_pa if team==away else 1-baseline_pa)*100,2),'Team first %':round(team_p*100,2),'Within-team share %':round(share*100,2),'Similar-lineup starts':context[player['player_id']][8] if context else None,'Weighted lineup starts':round(context[player['player_id']][9],1) if context else None,'Other-lineup starts':context[player['player_id']][10] if context else None,'Weighted other-lineup starts':round(context[player['player_id']][11],1) if context else None,'Weighted starts':round(recent[player['player_id']][5],1),'Fair odds':round(fair),'Book odds':price[1] if price else '',
                         'Model EV %':round((p*price[0]-1)*100,2) if price else None,
                         'Starts':starts,'Observed opening-shot starts':shot_count,'Weighted observed shot starts':round(shot_mass,3),'Shot coverage note':shot_note,'Team games':stats.get(team,{}).get('n',0),
                         'Current-season starts':sum(r['team']==team and r['player_id']==player['player_id'] for r in current),
                         'Injury':report['status'] if report else 'Not flagged / not verified',
                         'Status':status,'Odds updated':price[3] if price else ''})
    return sorted(rows,key=lambda r:r['_probability'],reverse=True)


def compare_lineup_swap(history, game, lineups, team, outgoing_id, replacement_id, roster_players, reports, model='baseline'):
    """Hypothetical comparison only: never mutate selections or produce market EV."""
    teams={game[s]['teamTricode'] for s in ('awayTeam','homeTeam')}
    if set(lineups)!=teams or team not in teams:raise ValueError('Choose a team in this matchup.')
    if outgoing_id not in {p['player_id'] for p in lineups[team]}:raise ValueError('Outgoing player must be a selected starter.')
    all_ids={p['player_id'] for players in lineups.values() for p in players}
    if replacement_id in all_ids:raise ValueError('Replacement must not already be selected.')
    roster={p['player_id']:p for p in roster_players}
    if replacement_id not in roster:raise ValueError('Replacement is not in the loaded team roster.')
    alternate={t:[dict(p) for p in players] for t,players in lineups.items()}
    alternate[team]=[dict(roster[replacement_id]) if p['player_id']==outgoing_id else p for p in alternate[team]]
    hypothetical={**game,'research_only':True}
    before=rank_game(history,hypothetical,lineups,{}, {},reports,model)
    after=rank_game(history,hypothetical,alternate,{}, {},reports,model)
    old={r['_player_id']:r for r in before};new={r['_player_id']:r for r in after}
    table=[]
    for pid in sorted(set(old)|set(new)):
        r=new.get(pid) or old[pid]
        p0=old[pid]['_probability'] if pid in old else None
        p1=new[pid]['_probability'] if pid in new else None
        table.append({'Player':r['Player'],'Team':r['Team'],'Scenario role':'Replacement' if pid not in old else 'Removed starter' if pid not in new else 'Unchanged starter',
                      'Before %':100*p0 if p0 is not None else None,'After %':100*p1 if p1 is not None else None,
                      'Change (percentage points)':100*(p1-p0) if p0 is not None and p1 is not None else None,
                      'After starts':new[pid]['Starts'] if pid in new else None,
                      'After similar-lineup starts':new[pid]['Similar-lineup starts'] if pid in new else None,
                      'Injury':r['Injury']})
    def leaders(rows):
        best=max(r['_probability'] for r in rows)
        return [r['Player'] for r in rows if abs(r['_probability']-best)<1e-12]
    return {'research_only':True,'model':model,'rows':table,'before_top':leaders(before),'after_top':leaders(after)}


def compare_model_forecasts(bundle):
    """Describe model disagreement without treating it as a confidence interval."""
    import math
    models=('baseline','recent','lineup')
    if set(bundle)!=set(models):raise ValueError('All three model forecasts are required.')
    indexed={};reference=None;gid=None
    for model in models:
        rows=bundle[model]
        identity={(r['_player_id'],r['Team']) for r in rows}
        teams={r['Team'] for r in rows}
        if len(teams)!=2 or any(sum(r['Team']==t for r in rows)!=5 for t in teams):raise ValueError('Each model requires five starters per team.')
        game_ids={r['_game_id'] for r in rows}
        if len(rows)!=10 or len(identity)!=10 or len({r['_player_id'] for r in rows})!=10 or len(game_ids)!=1:
            raise ValueError('Each model needs ten unique players from one game.')
        if reference is None:reference=identity;gid=game_ids
        if identity!=reference or game_ids!=gid or any(r.get('Model')!=model for r in rows):
            raise ValueError('Models must use the same matchup and starting fives.')
        probs=[r['_probability'] for r in rows]
        if any(not math.isfinite(p) or not 0<p<1 for p in probs) or abs(sum(probs)-1)>1e-8:
            raise ValueError('Invalid model probabilities.')
        indexed[model]={r['_player_id']:r for r in rows}
    leaders={};summary=[]
    for model in models:
        rows=bundle[model];best=max(r['_probability'] for r in rows)
        leaders[model]={r['_player_id'] for r in rows if abs(r['_probability']-best)<1e-12}
        summary.append({'Model':model,'Top estimate':' / '.join(sorted(r['Player'] for r in rows if r['_player_id'] in leaders[model])),
                        'Top probability %':100*best,'Players tied at top':len(leaders[model])})
    rows=[]
    labels={'baseline':'Baseline','recent':'Recent form','lineup':'Lineup context'}
    for pid,base in indexed['baseline'].items():
        values={m:indexed[m][pid]['_probability'] for m in models}
        row={'Player':base['Player'],'Team':base['Team']}
        for model in models:
            row[labels[model]+' %']=100*values[model]
            row[labels[model]+' rank']=1+sum(r['_probability']>values[model]+1e-12 for r in bundle[model])
            row[labels[model]+' status']=indexed[model][pid]['Status']
        row.update({'Range (percentage points)':100*(max(values.values())-min(values.values())),
                    'Models ranking player top (ties included)':sum(pid in leaders[m] for m in models),
                    'Recorded starts':base['Starts'],'Weighted starts':indexed['recent'][pid]['Weighted starts'],
                    'Similar-lineup starts':indexed['lineup'][pid]['Similar-lineup starts'],'Injury':base['Injury']})
        rows.append(row)
    common=set.intersection(*(leaders[m] for m in models))
    return {'rows':sorted(rows,key=lambda r:(-r['Baseline %'],r['Team'],r['Player'])),
            'leaders':summary,'shared_top':[indexed['baseline'][pid]['Player'] for pid in sorted(common)],
            'all_tied':all(len(leaders[m])==10 for m in models)}


def matchup_leader_board(rows):
    """Summarize each displayed matchup without hiding tied or held leaders."""
    import math
    from collections import defaultdict
    games=defaultdict(list)
    for row in rows:games[row['_game_id']].append(row)
    board=[]
    for gid,players in games.items():
        teams={r['Team'] for r in players}
        if len(players)!=10 or len({r['_player_id'] for r in players})!=10 or len(teams)!=2 or any(sum(r['Team']==t for r in players)!=5 for t in teams):
            raise ValueError('Leader board requires ten distinct players, five per team.')
        if len({r['Model'] for r in players})!=1 or len({r['Matchup'] for r in players})!=1:
            raise ValueError('Leader board requires one model and matchup label per game.')
        probabilities=[r['_probability'] for r in players]
        if any(not math.isfinite(p) or not 0<p<1 for p in probabilities) or abs(sum(probabilities)-1)>1e-8:
            raise ValueError('Leader board requires normalized positive probabilities.')
        best=max(probabilities)
        leaders=sorted([r for r in players if abs(r['_probability']-best)<1e-12],key=lambda r:(r['Team'],r['Player'],r['_player_id']))
        board.append({'Game':gid,'Matchup':players[0]['Matchup'],'Model':players[0]['Model'],
                      'Top candidates':' / '.join(r['Player']+' ('+r['Team']+')' for r in leaders),
                      'Each leader %':100*best,'Tied leaders':len(leaders),
                      'Gap to runner-up pp':0.0 if len(leaders)>1 else 100*(best-sorted(probabilities,reverse=True)[1]),
                      'Leader status':' / '.join(sorted({r['Status'] for r in leaders})),
                      'Leader injury review':' / '.join(sorted({r['Injury'] for r in leaders})),
                      'Fewest leader starts':min(r['Starts'] for r in leaders),
                      'Fewest observed shot starts':min(r['Observed opening-shot starts'] for r in leaders)})
    return sorted(board,key=lambda r:(-r['Each leader %'],r['Matchup'],r['Game']))


NBA_LINEUP_URL='https://stats.nba.com/js/data/leaders/00_daily_lineups_{day}.json'


def parse_nba_confirmed_lineups(payload,day,games,rosters,now=None):
    """Map only explicit five-position NBA confirmations to unique ESPN roster names."""
    from datetime import date
    date.fromisoformat(day)
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Lineup retrieval time must include a timezone.')
    if not isinstance(payload,dict) or not isinstance(payload.get('games'),list):raise ValueError('NBA lineup response is unreadable.')
    if any(not isinstance(g,dict) or any(not isinstance(g.get(side),dict) for side in ('awayTeam','homeTeam')) for g in payload['games']):raise ValueError('NBA lineup game structure is unreadable.')
    entries={};messages=[]
    for game in games:
        gid=game['gameId'];away=game['awayTeam']['teamTricode'];home=game['homeTeam']['teamTricode']
        if game.get('research_only') or game.get('_date')!=day or not upcoming(game,now):continue
        candidates=[g for g in payload['games'] if isinstance(g,dict) and
                    g.get('awayTeam',{}).get('teamAbbreviation')==away and g.get('homeTeam',{}).get('teamAbbreviation')==home]
        scheduled=[g for g in games if g.get('_date')==day and g.get('awayTeam',{}).get('teamTricode')==away and g.get('homeTeam',{}).get('teamTricode')==home]
        if len(candidates)!=1 or len(scheduled)!=1:
            messages.append(gid+': no unique NBA game match for this date and home/away pairing.');continue
        source=candidates[0]
        if sum(g.get('gameId')==source.get('gameId') for g in payload['games'])!=1:
            messages.append(gid+': duplicate NBA game identity.');continue
        if type(source.get('gameStatus')) is not int or source['gameStatus']!=1 or not str(source.get('gameId','')).isdigit():
            messages.append(gid+': NBA game is not explicitly pregame.');continue
        for side,team in (('awayTeam',away),('homeTeam',home)):
            try:
                data=source[side];players=data['players']
                if type(data.get('teamId')) is not int or data['teamId']<=0:raise ValueError('Invalid NBA team ID')
                if not isinstance(players,list):raise ValueError('Invalid player list')
                positioned=[r for r in players if r.get('position')]
                if len(positioned)!=5 or {r.get('position') for r in positioned}!={'PG','SG','SF','PF','C'}:
                    raise ValueError('No complete five-position starting lineup')
                if any(r.get('lineupStatus')!='Confirmed' or r.get('rosterStatus')!='Active' for r in positioned):
                    raise ValueError('Starting five is not fully confirmed and active')
                source_ids=[str(r.get('personId','')) for r in positioned]
                if len(set(source_ids))!=5 or any(not pid.isdigit() or int(pid)<=0 for pid in source_ids):raise ValueError('Invalid NBA player IDs')
                if any(r.get('teamId')!=data['teamId'] for r in positioned):raise ValueError('NBA player team mismatch')
                timestamps={r['timestamp'] for r in positioned}
                if len(timestamps)!=1 or any(datetime.fromisoformat(t.replace('Z','+00:00')).date().isoformat()!=day for t in timestamps):
                    raise ValueError('Mixed or wrong-date lineup timestamps')
                roster=rosters.get(team,[]);mapped=[]
                for player in positioned:
                    name=eng.norm(player['playerName'])
                    matches=[r for r in roster if name and eng.norm(r['player'])==name]
                    if len(matches)!=1:raise ValueError('Starter name does not uniquely match the loaded team roster')
                    mapped.append(matches[0]['player_id'])
                if len(set(mapped))!=5:raise ValueError('Duplicate mapped player IDs')
                entries.setdefault(gid,{})[team]={'game_id':gid,'date':day,'start_time':game['start_time'],
                    'home':home,'away':away,'team':team,'player_ids':mapped,'nba_player_ids':source_ids,
                    'nba_game_id':str(source['gameId']),'source':'NBA daily lineup feed','source_timestamp':next(iter(timestamps)),
                    'fetched_at':now.isoformat(),'source_url':NBA_LINEUP_URL.format(day=day.replace('-',''))}
            except (ValueError,KeyError,TypeError,AttributeError):
                messages.append(team+': no usable confirmed five; keep the lineup unconfirmed or verify it manually.')
    return {'day':day,'entries':entries,'messages':messages,'fetched_at':now.isoformat()}


def fetch_nba_confirmed_lineups(day,games,rosters):
    from datetime import date
    date.fromisoformat(day)
    payload=request(NBA_LINEUP_URL.format(day=day.replace('-','')))
    return parse_nba_confirmed_lineups(payload,day,games,rosters)


def nba_confirmation_matches(entry,game,selected,now=None):
    now=now or datetime.now(timezone.utc)
    try:
        age=(now-datetime.fromisoformat(entry['fetched_at'])).total_seconds()
        ids=[p['player_id'] for p in selected]
        return (not game.get('research_only') and upcoming(game,now) and 0<=age<=300 and
                entry['game_id']==game['gameId'] and entry['date']==game['_date'] and entry['start_time']==game['start_time'] and
                entry['home']==game['homeTeam']['teamTricode'] and entry['away']==game['awayTeam']['teamTricode'] and
                len(ids)==5 and len(set(ids))==5 and set(ids)==set(entry['player_ids']))
    except (KeyError,TypeError,ValueError):return False


def lineup_confirmation_sources(game,lineups,manual,provider,now=None):
    return {team:('NBA feed confirmed' if nba_confirmation_matches(provider.get(team,{}),game,players,now)
                   else 'User confirmed' if manual.get(team) and len(players)==5 else 'Unconfirmed') for team,players in lineups.items()}
