"""APEX First Basket Engine V1.2 — NBA/FanDuel prototype.

Install: python -m pip install requests
Commands:
    python first_basket_engine.py sync
    python first_basket_engine.py picks
    python first_basket_engine.py picks --live-odds
    python first_basket_engine.py picks --date 2026-10-25

Uses public ESPN data, with optional The Odds API first-basket market.
This is an experimental probabilistic baseline, NOT a validated betting model.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
HISTORY = DATA / "history_espn.csv"
STARTERS = ROOT / "starters_espn.csv"
ODDS = ROOT / "odds.csv"
SCHEDULE_CACHE = DATA / "schedule_espn.json"

CDN = "https://cdn.nba.com/static/json"
SCHEDULE_URL = f"{CDN}/staticData/scheduleLeagueV2.json"
SCHEDULE_FALLBACK = f"{CDN}/staticData/scheduleLeagueV2_1.json"
PBP_URL = f"{CDN}/liveData/playbyplay/playbyplay_{{}}.json"
BOX_URL = f"{CDN}/liveData/boxscore/boxscore_{{}}.json"
NBA_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://www.nba.com/"}
ODDS_BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"

TEAMS = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}
FIELDS = ["game_id", "date", "team", "opponent", "player_id", "player", "first_team_shot",
          "first_game_shot", "first_scorer", "first_fg_scorer", "team_scored_first", "tip_first_action", "opening_shot_observed"]


def get_json(url, *, params=None):
    response = requests.get(url, params=params, headers=NBA_HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def norm(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_starter(value):
    return value is True or str(value).lower() in {"true", "1", "yes"}


def day_of_game(game):
    # NBA schedule date supplied as e.g. 2026-10-25 or 10/25/2026 00:00:00.
    for k in ("gameDateEst", "gameDate", "gameDateTimeEst", "gameDateTimeUTC"):
        value = str(game.get(k) or "")
        if not value:
            continue
        try:
            if re.match(r"\d{4}-\d{2}-\d{2}", value):
                if k == "gameDateTimeUTC":
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return dt.astimezone(ZoneInfo("America/New_York")).date().isoformat()
                return value[:10]
            if "/" in value:
                return datetime.strptime(value[:10], "%m/%d/%Y").date().isoformat()
        except ValueError:
            pass
    return ""


ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_ALIASES = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}


def espn_team(team):
    code = team["abbreviation"].upper()
    code = ESPN_ALIASES.get(code, code)
    if code not in TEAMS:
        raise ValueError(f"Unknown ESPN team: {code}")
    return code


def game_is_upcoming(game, now=None):
    """Require a coherent, timezone-aware future start and fresh scheduled status."""
    try:
        if game.get('research_only') or game.get('_schedule_cached') or game.get('gameStatus')!=1:return False
        start=datetime.fromisoformat(game['start_time'].replace('Z','+00:00'))
        now=now or datetime.now(timezone.utc)
        if start.tzinfo is None or now.tzinfo is None:return False
        if start.astimezone(ZoneInfo('America/New_York')).date().isoformat()!=game['_date']:return False
        return start>now
    except (KeyError,TypeError,ValueError,AttributeError):return False


def parse_espn_schedule(payload):
    games = {}
    for event in payload.get("events", []):
        if event.get("season", {}).get("type") != 2:
            continue
        if len(event['competitions'])!=1:raise ValueError('Schedule has an ambiguous competition.')
        comp = event["competitions"][0]
        sides = {c["homeAway"]: {"teamTricode": espn_team(c["team"])} for c in comp["competitors"]}
        if len(comp['competitors'])!=2 or set(sides)!={'home','away'} or sides['home']==sides['away']:
            raise ValueError('Schedule has an invalid matchup.')
        state = event.get("status", comp.get("status", {})).get("type", {})
        status = 3 if state.get("completed") is True else 1 if state.get("name") == "STATUS_SCHEDULED" else 2
        start=datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        if start.tzinfo is None:raise ValueError('Schedule start time has no timezone.')
        day=start.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        gid='espn_'+str(event['id'])
        if not re.fullmatch(r'espn_\d+',gid):raise ValueError('Invalid schedule event ID.')
        game={"gameId":gid,"_date":day,'start_time':start.isoformat(),
              "gameStatus":status,"homeTeam":sides["home"],"awayTeam":sides["away"]}
        if gid in games and games[gid]!=game:raise ValueError('Conflicting schedule entries for one game.')
        games[gid]=game
    return list(games.values())


def schedule(target_day=None):
    today = datetime.now(ZoneInfo("America/New_York")).date()
    target = date.fromisoformat(target_day) if target_day else today
    # Sync up to 45 recent days; ESPN scoreboard accepts single dates reliably.
    year = today.year if today.month >= 10 else today.year - 1
    start = max(date(year, 10, 1), today - timedelta(days=45)) if target_day is None else target
    end = today if target_day is None else target
    games = {}
    range_start=start
    try:
        while start <= end:
            stop = start
            print(f"Loading ESPN schedule: {start.isoformat()}", flush=True)
            payload = get_json(ESPN_BASE + "/scoreboard", params={
                "dates": start.strftime("%Y%m%d") if start == stop else start.strftime("%Y%m%d") + "-" + stop.strftime("%Y%m%d"), "limit": 1000})
            for g in parse_espn_schedule(payload):
                if g["_date"]==start.isoformat():games[g["gameId"]] = g
            start = stop + timedelta(days=1)
        result = list(games.values())
        SCHEDULE_CACHE.write_text(json.dumps(result), encoding="utf-8")
        print(f"ESPN schedule loaded: {len(result)} games.")
        return result
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        if target_day is not None:
            raise RuntimeError('Fresh schedule unavailable. Cached games cannot be used for pregame rankings.') from exc
        if SCHEDULE_CACHE.exists():
            cached=json.loads(SCHEDULE_CACHE.read_text(encoding="utf-8"))
            eligible=[{**g,'_schedule_cached':True} for g in cached if range_start.isoformat()<=g.get('_date','')<=end.isoformat() and g.get('gameStatus')==3]
            print('ESPN unavailable; using cached completed games within the requested history window. Summaries will be revalidated.')
            return eligible
        raise RuntimeError(f"ESPN schedule unavailable: {exc}") from exc


def validate_espn_summary(game, payload):
    """Reject a mismatched provider event before importing any starter rows."""
    header=payload.get('header',{})
    competitions=header.get('competitions',[])
    if len(competitions)!=1:raise ValueError('Summary has no unique game competition.')
    competition=competitions[0]
    expected=str(game['gameId']).removeprefix('espn_')
    if str(header.get('id',''))!=expected or str(competition.get('id',expected))!=expected:
        raise ValueError('Summary game ID does not match the requested game.')
    if not competition.get('status',{}).get('type',{}).get('completed'):
        raise ValueError('Summary does not confirm a completed game.')
    competitors=competition.get('competitors',[])
    actual={c.get('homeAway'):espn_team(c['team']) for c in competitors}
    expected_teams={'home':game['homeTeam']['teamTricode'],'away':game['awayTeam']['teamTricode']}
    if len(competitors)!=2 or actual!=expected_teams:
        raise ValueError('Summary home/away teams do not match the requested matchup.')


def espn_game_payloads(payload):
    teams = {}
    sides = {}
    for comp in payload["header"]["competitions"][0]["competitors"]:
        teams[str(comp["team"]["id"])] = espn_team(comp["team"])
        sides[comp["homeAway"]] = str(comp["team"]["id"])
    boxes = {}
    for team in payload["boxscore"]["players"]:
        tid = str(team["team"]["id"])
        players = {}
        for stat in team["statistics"]:
            for row in stat.get("athletes", []):
                athlete = row["athlete"]
                players[athlete["id"]] = {"personId": int(athlete["id"]), "name": athlete["displayName"], "starter": row.get("starter", False)}
        boxes[tid] = {"teamTricode": teams[tid], "players": list(players.values())}
    actions = []
    for play in payload.get("plays", []):
        if play.get("period", {}).get("number") != 1:
            continue
        desc = play.get("text", "")
        free = "free throw" in desc.lower()
        shot = bool(play.get("shootingPlay")) and not free
        made = bool(play.get("scoringPlay")) and play.get("scoreValue", 0) > 0
        typ = "free throw" if free else ("made shot" if made else "missed shot") if shot else "turnover" if "turnover" in desc.lower() else "other"
        people = play.get("participants", [])
        actions.append({"period": 1, "actionNumber": int(play["sequenceNumber"]),
                        "actionType": typ, "teamTricode": teams.get(str(play.get("team", {}).get("id")), ""),
                        "personId": int(people[0]["athlete"]["id"]) if people else 0,
                        "description": desc, "isFieldGoal": int(shot), "shotResult": "Made" if made else "Missed"})
    return {"game": {"actions": actions}}, {"game": {"homeTeam": boxes[sides["home"]], "awayTeam": boxes[sides["away"]]}}


def sorted_actions(payload):
    return sorted(payload["game"]["actions"], key=lambda a: int(a.get("actionId", a.get("actionNumber", 0))))


def is_fg_attempt(a):
    typ = norm(a.get("actionType", ""))
    return typ in {"2pt", "3pt", "madeshot", "missedshot"} and str(a.get("isFieldGoal", 0)).lower() in {"1", "true"}


def is_made_score(a):
    typ = norm(a.get("actionType", ""))
    result = str(a.get("shotResult") or "").lower()
    desc = str(a.get("description", "")).strip().upper()
    if not a.get("personId") or not a.get("teamTricode"):
        return False
    if result == "missed" or desc.startswith("MISS"):
        return False
    if is_fg_attempt(a):
        return result == "made" or typ == "madeshot"
    if typ == "freethrow":
        return result == "made" or (bool(desc) and "FREE THROW" in desc)
    return False


def first_offense_team(actions):
    # Proxy for opening tip possession, NOT an independently verified tip-winner.
    for a in actions:
        if int(a.get("period", 0)) != 1:
            continue
        typ = str(a.get("actionType", "")).lower()
        team = a.get("teamTricode", "")
        if team and (is_fg_attempt(a) or norm(typ) in {"turnover", "freethrow"}):
            return team
    return ""


def extract_game(game, play, box):
    actions = [a for a in sorted_actions(play) if int(a.get("period", 0)) == 1]
    if not actions:
        raise ValueError("Missing first-period plays")
    scorer = next((a for a in actions if is_made_score(a)), None)
    fg_scorer = next((a for a in actions if is_made_score(a) and is_fg_attempt(a)), None)
    if not scorer or not fg_scorer:
        raise ValueError("No valid first scorer or first made FG")
    fg_attempts = [a for a in actions if is_fg_attempt(a)]
    first_game_shot = fg_attempts[0] if fg_attempts else None
    first_per_team = {}
    for a in fg_attempts:
        if a.get("teamTricode") and a["teamTricode"] not in first_per_team:
            first_per_team[a["teamTricode"]] = a
    first_action_team = first_offense_team(actions)
    game_id = str(game["gameId"])
    found = []
    sides = [box["game"]["homeTeam"], box["game"]["awayTeam"]]
    for side in sides:
        team = side["teamTricode"]
        opponent = next(t["teamTricode"] for t in sides if t["teamTricode"] != team)
        for p in side.get("players", []):
            if not is_starter(p.get("starter")):
                continue
            pid = int(p["personId"])
            found.append({
                "game_id": game_id,
                "date": game.get("_date", ""),
                "team": team,
                "opponent": opponent,
                "player_id": str(pid),
                "player": p.get("name") or (str(p.get("firstName", "")) + " " + str(p.get("familyName", ""))).strip(),
                "first_team_shot": int(first_per_team.get(team, {}).get("personId", 0) == pid),
                "opening_shot_observed": int(int(first_per_team.get(team, {}).get("personId", 0)) in {int(q["personId"]) for q in side.get("players", []) if int(q["personId"])>0}),
                "first_game_shot": int(first_game_shot is not None and int(first_game_shot.get("personId", 0)) == pid),
                "first_scorer": int(int(scorer.get("personId", 0)) == pid),
                "first_fg_scorer": int(int(fg_scorer.get("personId", 0)) == pid),
                "team_scored_first": int(scorer.get("teamTricode", "") == team),
                "tip_first_action": int(first_action_team == team),
            })
    if len(found) != 10:
        raise ValueError(f"Expected 10 starters, got {len(found)} (skip suspect game)")
    if sum(int(r["first_scorer"]) for r in found) != 1:
        raise ValueError("First scorer is not one of the ten starters; game excluded")
    return found


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def write_csv(path, fields, rows):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def sync(max_games):
    games = schedule()
    completed = [g for g in games if int(g.get("gameStatus", 0)) == 3]
    completed = sorted(completed, key=lambda g: (g.get("_date", ""), g.get("gameId", "")))[-max_games:]
    old = read_csv(HISTORY)
    saved_ids = {r["game_id"] for r in old}
    if not ODDS.exists():
        write_csv(ODDS, ["team", "player", "odds", "sportsbook"], [])
    count, failures = 0, 0
    for i, g in enumerate(completed, start=1):
        game_id = str(g["gameId"])
        if game_id in saved_ids:
            continue
        try:
            summary = get_json(ESPN_BASE + "/summary", params={"event": game_id.removeprefix("espn_")})
            validate_espn_summary(g,summary)
            play, box = espn_game_payloads(summary)
            rows = extract_game(g, play, box)
            from research_tools import audit
            _,issues=audit(rows)
            if issues:raise ValueError(issues[0]['reason'])
            old.extend(rows)
            saved_ids.add(game_id)
            count += 1
            print(f"[{i}/{len(completed)}] Saved {game_id}: {rows[0]['team']} vs {rows[5]['team']}")
            # Checkpoint each game so an interrupted download keeps its progress.
            write_csv(HISTORY, FIELDS, old)
            time.sleep(0.2)
        except (ValueError, KeyError, TypeError, requests.RequestException) as exc:
            failures += 1
            print(f"[{i}/{len(completed)}] Skipping {game_id}: {str(exc)[:140]}")
    print(f"\nSync finished: {count} new games; {len(saved_ids)} total; {failures} skipped.")
    if old:
        create_starter_template(old, games)
    else:
        print("No completed games available. Cannot project starters yet.")


def recent_starters(history, team):
    games = defaultdict(list)
    for r in history:
        if r["team"] == team:
            games[r["game_id"]].append(r)
    if not games:
        return []
    latest = max(games.values(), key=lambda g: (g[0]["date"], g[0]["game_id"]))
    return latest if len(latest) == 5 else []


def create_starter_template(history, games):
    if STARTERS.exists():
        print("Keeping your existing starters_espn.csv (not overwriting manual confirmations).")
        return
    # Add teams across today's games first, then all available teams from history.
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    today_teams = set()
    for g in games:
        if g.get("_date") == today and int(g.get("gameStatus", 0)) == 1:
            today_teams.update([g.get("homeTeam", {}).get("teamTricode"), g.get("awayTeam", {}).get("teamTricode")])
    teams = sorted({r["team"] for r in history} | today_teams)
    rows = []
    for team in teams:
        for r in recent_starters(history, team):
            rows.append({"team": team, "player_id": r["player_id"], "player": r["player"], "confirmed": "NO"})
    write_csv(STARTERS, ["team", "player_id", "player", "confirmed"], rows)
    print(f"Created {STARTERS.name} using last recorded starters. EDIT it before betting.")


def starters_for_team(rows, team):
    chosen = [r for r in rows if r.get("team", "").upper().strip() == team]
    if len(chosen) != 5 or len({r.get("player_id") for r in chosen}) != 5:
        return None
    return chosen


def team_stats(history):
    games = defaultdict(dict)
    proxy_known=set()
    for r in history:
        games[r["team"]][r["game_id"]] = r
        if int(r["tip_first_action"]):proxy_known.add(r["game_id"])
    stats = {}
    for team, bygame in games.items():
        records = list(bygame.values())
        n = len(records)
        first = sum(int(r["team_scored_first"]) for r in records)
        proxy_records=[r for r in records if r["game_id"] in proxy_known]
        tip = sum(int(r["tip_first_action"]) for r in proxy_records)
        # Prior is 50% to mitigate tiny early-season samples.
        stats[team] = {"n": n, "first": (first + 10) / (n + 20),
                       "tip_proxy": (tip + 10) / (len(proxy_records) + 20), "proxy_games":len(proxy_records)}
    return stats


def first_team_probability(team, opp, stats):
    a = stats.get(team, {"n": 0, "first": 0.5, "tip_proxy": 0.5})
    b = stats.get(opp, {"n": 0, "first": 0.5, "tip_proxy": 0.5})
    p = 0.5 + 0.45 * (a["first"] - b["first"]) + 0.12 * (a["tip_proxy"] - b["tip_proxy"])
    return max(0.25, min(0.75, p))


def opening_shot_games(history):
    """Team/game pairs with an identified opening shooter; infer legacy positives only."""
    groups=defaultdict(list)
    for row in history:groups[(row['game_id'],row['team'])].append(row)
    known=set()
    for key,rows in groups.items():
        explicit={str(r.get('opening_shot_observed','')) for r in rows}
        if explicit=={'1'} or (explicit<= {'', 'None'} and any(int(r['first_team_shot']) for r in rows)):
            known.add(key)
    return known


def player_weights(history, starters, team):
    observed=opening_shot_games(history)
    bykey = defaultdict(list)
    for r in history:
        bykey[(r["team"], r["player_id"])].append(r)
    raw = []
    for s in starters:
        rows = bykey.get((team, s["player_id"]), [])
        n = len(rows)
        nshots = sum(int(r["first_team_shot"]) for r in rows)
        nscores = sum(int(r["first_scorer"]) for r in rows)
        # Shrunk rates; score needs all 10 players normalized after mixing.
        shot_n=sum((r['game_id'],team) in observed for r in rows)
        shot_rate = (nshots + 1.0) / (shot_n + 5.0)
        first_rate = (nscores + 0.5) / (n + 5.0)
        w = 0.65 * shot_rate + 0.35 * first_rate
        raw.append((s, w, n, nshots, nscores))
    total = sum(item[1] for item in raw)
    return [(s, w / total, n, shots, scores) for s, w, n, shots, scores in raw]


def american_to_decimal(raw):
    s = str(raw).strip().replace(",", "")
    if not s:
        return None
    try:
        a = int(s)
        return 1 + a / 100 if a > 0 else 1 + 100 / abs(a) if a < 0 else None
    except ValueError:
        return None


def local_prices():
    prices = {}
    for r in read_csv(ODDS):
        team = r.get("team", "").strip().upper()
        who = norm(r.get("player", ""))
        dec = american_to_decimal(r.get("odds", ""))
        if team and who and dec:
            prices[(team, who)] = (dec, str(r["odds"]).strip(), r.get("sportsbook", "MANUAL"))
    return prices


def api_prices(games):
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        print("Live odds unavailable: set ODDS_API_KEY first; using odds.csv only.")
        return {}
    prices = {}
    try:
        events = get_json(f"{ODDS_BASE}/events", params={"apiKey": api_key})
    except (requests.RequestException, ValueError) as exc:
        print(f"Cannot fetch NBA odds events: {exc}")
        return prices
    matchups = {(norm(TEAMS[g["awayTeam"]["teamTricode"]]), norm(TEAMS[g["homeTeam"]["teamTricode"]]))
                for g in games if g.get("awayTeam", {}).get("teamTricode") in TEAMS and g.get("homeTeam", {}).get("teamTricode") in TEAMS}
    for event in events:
        matchup = (norm(event.get("away_team", "")), norm(event.get("home_team", "")))
        if matchup not in matchups:
            continue
        try:
            data = get_json(f"{ODDS_BASE}/events/{event['id']}/odds", params={
                "apiKey": api_key, "regions": "us", "bookmakers": "fanduel",
                "markets": "player_first_basket", "oddsFormat": "american"})
        except (requests.RequestException, ValueError) as exc:
            print(f"First-basket market unavailable for {event.get('home_team')}: {str(exc)[:160]}")
            continue
        team_lookup = {norm(TEAMS[g[side]["teamTricode"]]): g[side]["teamTricode"]
                       for g in games for side in ("homeTeam", "awayTeam") if g.get(side, {}).get("teamTricode") in TEAMS}
        valid_teams = {team_lookup.get(norm(event.get("home_team", ""))), team_lookup.get(norm(event.get("away_team", "")))}
        for book in data.get("bookmakers", []):
            if norm(book.get("key", "")) != "fanduel":
                continue
            for market in book.get("markets", []):
                if market.get("key") != "player_first_basket":
                    continue
                for outcome in market.get("outcomes", []):
                    name = outcome.get("description") or outcome.get("name", "")
                    # Standard player yes/no outcome includes name='Yes', description='Player'.
                    if outcome.get("description") and str(outcome.get("name", "")).lower() not in ("yes", ""):
                        continue
                    value = outcome.get("price")
                    dec = american_to_decimal(value)
                    if not dec or not name:
                        continue
                    # Player belongs to exactly one of the matchup teams by starters lookup downstream.
                    for team in valid_teams:
                        if team:
                            prices[(team, norm(name))] = (dec, str(value), "FanDuel API")
    return prices


def backtest(min_training_games):
    """Chronological holdout validation using observed historical starting fives.

    Excludes games for which the scorer was not a starter (current V1 history filter).
    Reports a probability-scoring metric; cannot prove betting ROI without odds history.
    """
    hist = read_csv(HISTORY)
    bygame = defaultdict(list)
    for row in hist:
        bygame[row["game_id"]].append(row)
    games = sorted(bygame.values(), key=lambda rows: (rows[0]["date"], rows[0]["game_id"]))
    if len(games) <= min_training_games:
        print(f"Need > {min_training_games} historical games; have {len(games)}.")
        return
    # Hold out full game-days, so results of an earlier game on the same day
    # never affect predictions of another game in the same day's slate.
    day_groups = defaultdict(list)
    for game in games:
        day_groups[game[0]["date"]].append(game)
    train = []
    num_train_games = 0
    p_real, top_correct, briers = [], 0, []
    for day in sorted(day_groups):
        batch = day_groups[day]
        if num_train_games >= min_training_games:
            st = team_stats(train)
            for game in batch:
                teams = sorted({r["team"] for r in game})
                if len(teams) != 2 or len(game) != 10:
                    continue
                a, b = teams
                p_a = first_team_probability(a, b, st)
                prob = {}
                for team, p_team in ((a, p_a), (b, 1 - p_a)):
                    current_five = [r for r in game if r["team"] == team]
                    for player, w, *_ in player_weights(train, current_five, team):
                        prob[(team, player["player_id"])] = p_team * w
                true = next((r for r in game if int(r["first_scorer"]) == 1), None)
                if true and prob:
                    true_key = (true["team"], true["player_id"])
                    value = prob.get(true_key, 0.0)
                    if value > 0:
                        p_real.append(value)
                        top_correct += int(max(prob, key=prob.get) == true_key)
                        briers.append(sum((p - (1 if k == true_key else 0)) ** 2 for k, p in prob.items()))
        train.extend(row for game in batch for row in game)
        num_train_games += len(batch)
    n = len(p_real)
    if not n:
        print("No valid out-of-sample results. Try after gathering more games.")
        return
    logloss = -sum(math.log(p) for p in p_real) / n
    print("\nAPEX FIRST BASKET — WALK-FORWARD BACKTEST")
    print(f"Train-first N: {min_training_games}; evaluated N: {n}")
    print(f"Top-1 hit rate: {top_correct / n:.1%} | uniform baseline: 10.0%")
    print(f"Log loss:       {logloss:.4f} | uniform baseline: {math.log(10):.4f} (lower is better)")
    print(f"Brier score:    {sum(briers) / n:.4f} | uniform baseline: 0.9000 (lower is better)")
    print("CAUTION: No price-adjusted ROI, no verified tip data, and historical exclusions may bias results.")


def show_picks(args):
    hist = read_csv(HISTORY)
    if not hist:
        print("No history yet. Run: python first_basket_engine.py sync")
        return
    target_day = args.date or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    games = schedule(target_day)
    matchup_games = [g for g in games if g.get("_date") == target_day and game_is_upcoming(g)]
    if not matchup_games:
        print(f"No scheduled, unstarted NBA regular-season games found on {target_day}.")
        return
    if not STARTERS.exists():
        create_starter_template(hist, matchup_games)
    starters = read_csv(STARTERS)
    if args.live_odds:
        auto = api_prices(matchup_games)
    else:
        auto = {}
    prices = {**local_prices(), **auto}
    hist = [r for r in hist if r["date"] < target_day]
    ts = team_stats(hist)
    print("\n" + "=" * 94)
    print("  APEX FIRST BASKET ENGINE V1.2  |  FanDuel: first SCORE including free throws")
    print(f"  Date: {target_day} | Games in history: {len({r['game_id'] for r in hist})} | Prototype / not calibrated")
    print("=" * 94)
    final = []
    for g in matchup_games:
        away = g["awayTeam"]["teamTricode"]
        home = g["homeTeam"]["teamTricode"]
        a5 = starters_for_team(starters, away)
        h5 = starters_for_team(starters, home)
        print(f"\n🏀 {away} @ {home}")
        if not a5 or not h5:
            print("  HOLD: starters_espn.csv needs exactly five distinct player IDs per team.")
            continue
        p_away = first_team_probability(away, home, ts)
        print(f"  Model team-first-score estimate: {away} {p_away:.1%} | {home} {1-p_away:.1%}")
        predictions = []
        whole_lineup_confirmed = all(str(p.get("confirmed", "")).strip().upper() == "YES" for p in a5 + h5)
        for team, five, p_team in ((away, a5, p_away), (home, h5, 1-p_away)):
            for player, share, starts, shots, scores in player_weights(hist, five, team):
                p = p_team * share
                key = (team, norm(player["player"]))
                price = prices.get(key)
                odds = price[1] if price else "—"
                ev = p * price[0] - 1 if price else None
                confirmed = str(player.get("confirmed", "")).strip().upper() == "YES"
                sufficient_data = ts.get(away, {}).get("n", 0) >= 10 and ts.get(home, {}).get("n", 0) >= 10 and starts >= 8
                if not whole_lineup_confirmed:
                    verdict = "HOLD: STARTER"
                elif not sufficient_data:
                    verdict = "HOLD: SAMPLE"
                elif ev is None:
                    verdict = "NO PRICE"
                elif ev >= 0.08:
                    verdict = "A? REVIEW"
                elif ev >= 0.05:
                    verdict = "B? REVIEW"
                elif ev >= 0.03:
                    verdict = "LEAN? REVIEW"
                else:
                    verdict = "PASS"
                predictions.append({"team": team, "player": player["player"], "prob": p,
                                    "fair_odds": round(100 * (1-p)/p) if p > 0 else None,
                                    "odds": odds, "ev": ev, "starts": starts, "shots": shots,
                                    "scores": scores, "status": verdict, "confirmed": confirmed,
                                    "source": price[2] if price else ""})
        predictions.sort(key=lambda r: r["prob"], reverse=True)
        print("  {:<22} {:<4} {:>7} {:>9} {:>8} {:>9}  {:<15}".format("PLAYER", "TEAM", "MODEL", "FAIR +", "ODDS", "EV", "SCREEN"))
        for r in predictions:
            ev = f"{r['ev']:+.1%}" if r["ev"] is not None else "—"
            print("  {:<22} {:<4} {:>6.1%} {:>9} {:>8} {:>9}  {:<15}".format(
                r["player"][:22], r["team"], r["prob"], r["fair_odds"], r["odds"], ev, r["status"]))
            final.append({"date": target_day, "matchup": f"{away}@{home}", **r})
    if final:
        out = DATA / f"predictions_{target_day}.csv"
        write_csv(out, ["date", "matchup", "team", "player", "prob", "fair_odds", "odds", "ev",
                        "starts", "shots", "scores", "status", "confirmed", "source"], final)
        print(f"\nSaved ranked projections to {out}")
    print("\nIMPORTANT: These are UNVALIDATED estimates. NO real bets until starters are confirmed")
    print("and probabilities pass an out-of-sample backtest. 'A/B/LEAN' are screening labels only.")
    print("Manual prices: add team,player,odds,sportsbook to odds.csv.")


def main():
    parser = argparse.ArgumentParser(description="APEX NBA First Basket / first score engine")
    sub = parser.add_subparsers(dest="cmd", required=True)
    command_sync = sub.add_parser("sync", help="Download ESPN current-season historical first-score data")
    command_sync.add_argument("--max-games", type=int, default=250,
                              help="Process last N completed regular season games; default 250")
    command_picks = sub.add_parser("picks", help="Rank upcoming first scorers")
    command_picks.add_argument("--date", type=str, default=None, help="Game date in YYYY-MM-DD, ET")
    command_picks.add_argument("--live-odds", action="store_true", help="Optional FanDuel prices from The Odds API")
    command_test = sub.add_parser("backtest", help="Walk-forward first-score prediction evaluation")
    command_test.add_argument("--min-training-games", type=int, default=30)
    args = parser.parse_args()
    try:
        if args.cmd == "sync":
            if args.max_games < 1:
                parser.error("--max-games must be >= 1")
            sync(args.max_games)
        elif args.cmd == "picks":
            if args.date:
                date.fromisoformat(args.date)
            show_picks(args)
        else:
            if args.min_training_games < 5:
                parser.error("--min-training-games must be >= 5")
            backtest(args.min_training_games)
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)



# Experimental recency model. Fixed design choices, not fitted parameters.
def recent_team_stats(history, target_day, half_life=90.0):
    target=date.fromisoformat(target_day)
    by_team=defaultdict(dict)
    for row in history:
        age=(target-date.fromisoformat(row['date'])).days
        if age<=0 or age>400:continue
        weight=2.0**(-age/half_life)
        by_team[row['team']][row['game_id']]=(row,weight)
    result={}
    for team,games in by_team.items():
        mass=sum(w for r,w in games.values())
        first=sum(w*int(r['team_scored_first']) for r,w in games.values())
        result[team]={'n':len(games),'weighted_games':mass,'first':(first+10)/(mass+20)}
    return result


def recent_first_team_probability(team,opponent,stats):
    a=stats.get(team,{}).get('first',.5)
    b=stats.get(opponent,{}).get('first',.5)
    strength_a=a*(1-b);strength_b=b*(1-a)
    return max(.25,min(.75,strength_a/(strength_a+strength_b)))


def recent_player_weights(history,starters,team,target_day,half_life=90.0):
    target=date.fromisoformat(target_day)
    observed=opening_shot_games(history)
    by_player=defaultdict(list)
    for row in history:
        age=(target-date.fromisoformat(row['date'])).days
        if row['team']==team and 0<age<=400:
            by_player[row['player_id']].append((row,2.0**(-age/half_life)))
    raw=[]
    for player in starters:
        rows=by_player[player['player_id']]
        mass=sum(w for r,w in rows)
        shots=sum(w*int(r['first_team_shot']) for r,w in rows)
        scores=sum(w*int(r['first_scorer']) for r,w in rows)
        opportunities=sum(w*int(r['team_scored_first']) for r,w in rows)
        shot_mass=sum(w for r,w in rows if (r['game_id'],team) in observed)
        shot_rate=(shots+2)/(shot_mass+10)
        conditional_rate=(scores+1)/(opportunities+5)
        weight=.65*shot_rate+.35*conditional_rate
        raw.append((player,weight,len(rows),sum(int(r['first_team_shot']) for r,w in rows),sum(int(r['first_scorer']) for r,w in rows),mass,shot_rate,conditional_rate))
    total=sum(r[1] for r in raw)
    return [(p,w/total,n,shots,scores,mass,shot,conditional) for p,w,n,shots,scores,mass,shot,conditional in raw]

def lineup_player_weights(history, starters, team, target_day):
    """Similar-lineup evidence anchored on disjoint other-lineup starts; experimental."""
    target=date.fromisoformat(target_day)
    selected={p['player_id'] for p in starters}
    games=defaultdict(list)
    for row in history:
        age=(target-date.fromisoformat(row['date'])).days
        if row['team']==team and 0<age<=400:games[row['game_id']].append(row)
    observed=opening_shot_games(history)
    contexts=defaultdict(list);context_games=set()
    for rows in games.values():
        ids={r['player_id'] for r in rows}
        if len(rows)!=5 or len(ids)!=5:continue
        overlap=len(ids & selected)
        if overlap<4:continue
        context_games.add(rows[0]['game_id'])
        age=(target-date.fromisoformat(rows[0]['date'])).days
        # Exact five gets full weight; four-of-five gets half weight.
        weight=2**(-age/90.0)*(1.0 if overlap==5 else .5)
        for row in rows:
            if row['player_id'] in selected:contexts[row['player_id']].append((row,weight))
    # A game can inform the anchor or the context update, never both.
    other_history=[r for r in history if r['team']!=team or r['game_id'] not in context_games]
    anchors={r[0]['player_id']:r for r in recent_player_weights(other_history,starters,team,target_day)}
    raw=[]
    for player,share,n,shots,scores,mass,shot,conditional in recent_player_weights(history,starters,team,target_day):
        context=contexts[player['player_id']]
        anchor=anchors[player['player_id']]
        shot,conditional=anchor[6],anchor[7]
        context_mass=sum(w for r,w in context)
        opportunities=sum(w*int(r['team_scored_first']) for r,w in context)
        shot_mass=sum(w for r,w in context if (r['game_id'],team) in observed)
        context_shot=(sum(w*int(r['first_team_shot']) for r,w in context)+10*shot)/(shot_mass+10)
        context_score=(sum(w*int(r['first_scorer']) for r,w in context)+5*conditional)/(opportunities+5)
        weight=.65*context_shot+.35*context_score
        raw.append((player,weight,n,shots,scores,mass,context_shot,context_score,len(context),context_mass,anchor[2],anchor[5]))
    total=sum(r[1] for r in raw)
    return [(r[0],r[1]/total,*r[2:]) for r in raw]


def predict_matchups(history, matchups, target_day, model="baseline"):
    """Build date-specific statistics once, then score each matchup independently."""
    if model not in ('baseline','recent','lineup'):raise ValueError('Unknown model.')
    target=date.fromisoformat(target_day)
    for lineups in matchups.values():
        if len(lineups)!=2 or any(len(players)!=5 for players in lineups.values()):
            raise ValueError('Two teams with five starters each are required.')
        ids=[p['player_id'] for players in lineups.values() for p in players]
        if len(set(ids))!=10:raise ValueError('Ten distinct player IDs are required.')
    if not matchups:return {}
    prior=[r for r in history if 0<(target-date.fromisoformat(r['date'])).days<=400]
    by_team=defaultdict(list)
    for row in prior:by_team[row['team']].append(row)
    stats=recent_team_stats(prior,target_day) if model!='baseline' else team_stats(prior)
    results={}
    for game_id,lineups in matchups.items():
        a,b=sorted(lineups)
        pa=recent_first_team_probability(a,b,stats) if model!='baseline' else first_team_probability(a,b,stats)
        probabilities={}
        for team,pt in ((a,pa),(b,1-pa)):
            team_history=by_team.get(team,[])
            weights=(lineup_player_weights(team_history,lineups[team],team,target_day) if model=='lineup' else recent_player_weights(team_history,lineups[team],team,target_day) if model=='recent' else player_weights(team_history,lineups[team],team))
            probabilities.update({player['player_id']:pt*share for player,share,*_ in weights})
        results[game_id]=probabilities
    return results


def predict_first_score(history, lineups, target_day, model="baseline"):
    return predict_matchups(history,{'single':lineups},target_day,model)['single']


if __name__ == "__main__":
    main()
