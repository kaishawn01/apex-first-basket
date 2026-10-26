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
    games = eng.parse_espn_schedule(payload)
    dates = {"espn_" + x["id"]: x["date"] for x in payload.get("events", [])}
    for g in games:
        g["start_time"] = dates[g["gameId"]]
    return games


def upcoming(g, now=None):
    now = now or datetime.now(timezone.utc)
    return g["gameStatus"] == 1 and datetime.fromisoformat(g["start_time"].replace("Z", "+00:00")) > now


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


def projections(history, team, day, players):
    prior = [r for r in history if r["date"] < day]
    allowed = {p["player_id"] for p in players}
    return [r["player_id"] for r in eng.recent_starters(prior, team) if r["player_id"] in allowed]


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
            enough=all(stats.get(t,{}).get('n',0)>=10 for t in (away,home)) and starts>=8
            status='HOLD: LINEUP' if not all_confirmed else 'HOLD: INJURY REVIEW' if injury_conflict else 'HOLD: SAMPLE' if not enough else 'NO PRICE' if not price else 'RESEARCH ONLY'
            if model!='baseline' and (recent[player['player_id']][5]<8 or any(recent_stats.get(t,{}).get('weighted_games',0)<10 for t in (away,home))) and status not in ('HOLD: LINEUP','HOLD: INJURY REVIEW'):
                status='HOLD: WEIGHTED SAMPLE'
            if game.get('research_only'):
                status='RESEARCH MATCHUP';price=None;prices={}
            fair=100*(1-p)/p if p<=.5 else -100*p/(1-p)
            rows.append({'_game_id':game['gameId'],'_player_id':player['player_id'],'_probability':p,'_research_only':bool(game.get('research_only')),'Model':model,'Matchup':f'{away} @ {home}','Player':player['player'],'Team':team,
                         'Model %':round(p*100,2),'Baseline %':round(baseline[player['player_id']]*(baseline_pa if team==away else 1-baseline_pa)*100,2),'Team first %':round(team_p*100,2),'Within-team share %':round(share*100,2),'Similar-lineup starts':context[player['player_id']][8] if context else None,'Weighted lineup starts':round(context[player['player_id']][9],1) if context else None,'Weighted starts':round(recent[player['player_id']][5],1),'Fair odds':round(fair),'Book odds':price[1] if price else '',
                         'Model EV %':round((p*price[0]-1)*100,2) if price else None,
                         'Starts':starts,'Team games':stats.get(team,{}).get('n',0),
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
