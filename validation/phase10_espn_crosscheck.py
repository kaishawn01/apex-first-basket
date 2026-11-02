import sys
import subprocess

APPROVED_GAMES = (
    "401809243",
    "401809236",
    "401809943",
    "401809956",
    "401809970"
)

if len(sys.argv) == 1:
    for game_id in APPROVED_GAMES:
        subprocess.run(
            [sys.executable, "-B", __file__, game_id],
            check=True
        )
    print("PASS: All five ESPN reference comparisons matched.")
    raise SystemExit(0)

if len(sys.argv) != 2 or sys.argv[1] not in APPROVED_GAMES:
    raise SystemExit("Unapproved game ID; stop")

import json, re, unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

path = Path("validation/PHASE10_PUBLIC_FIRST_SCORE_REFERENCES.json")
doc = json.loads(path.read_text(encoding="utf-8-sig"))
assert doc["schema"] == 1
assert doc["training_enabled"] is False
assert doc["model_compatible"] is False

records = [
    r for r in doc["records"]
    if r["dunk_game_id"] == sys.argv[1]
]
assert len(records) == 1
expected = records[0]
assert expected["verification_status"] in ("public_reference_only", "owner_crosschecked")

url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

# One public request, no credentials, redirects or retries.
with requests.get(
    url,
    params={"event": expected["dunk_game_id"]},
    headers={"Accept": "application/json"},
    timeout=(5, 20),
    allow_redirects=False,
    stream=True
) as response:
    if response.status_code != 200:
        raise ValueError(
            f"ESPN HTTP {response.status_code}; stop without retry"
        )
    raw = bytearray()
    for chunk in response.iter_content(65536):
        raw.extend(chunk)
        if len(raw) > 5_000_000:
            raise ValueError("ESPN response too large; stop")

data = json.loads(raw)
header = data["header"]
assert str(header["id"]) == expected["dunk_game_id"]

assert len(header["competitions"]) == 1
game = header["competitions"][0]
assert game["status"]["type"]["completed"] is True

competitors = game["competitors"]
sides = {
    c["homeAway"]: c["team"]["abbreviation"]
    for c in competitors
}
assert sides == {
    "home": expected["home"],
    "away": expected["away"]
}, "Matchup mismatch"

source_date = datetime.fromisoformat(
    game["date"].replace("Z", "+00:00")
)
assert source_date.tzinfo is not None
assert source_date.astimezone(
    ZoneInfo("America/New_York")
).date().isoformat() == expected["date"]

plays = [
    p for p in data["plays"]
    if p.get("period", {}).get("number") == 1
]
assert plays
assert all(
    str(p.get("sequenceNumber", "")).isdigit()
    for p in plays
)
plays.sort(key=lambda p: int(p["sequenceNumber"]))
assert len({
    int(p["sequenceNumber"]) for p in plays
}) == len(plays)

first = None
for play in plays:
    points = play.get("scoreValue")
    scoring = play.get("scoringPlay")

    assert type(points) is int and 0 <= points <= 3
    assert type(scoring) is bool
    assert scoring == (points > 0)

    if scoring:
        first = play
        break

    if "homeScore" in play or "awayScore" in play:
        assert play.get("homeScore") == 0
        assert play.get("awayScore") == 0

assert first is not None, "No first score found"

team_ids = {
    str(c["team"]["id"]): c["team"]["abbreviation"]
    for c in competitors
}
scoring_id = str(first["team"]["id"])
assert scoring_id in team_ids
scoring_team = team_ids[scoring_id]

people = first.get("participants", [])
assert people and isinstance(people[0], dict)
athlete_id = str(people[0]["athlete"]["id"])

roster = {}
for side in data["boxscore"]["players"]:
    team_id = str(side["team"]["id"])
    for stat in side.get("statistics", []):
        for row in stat.get("athletes", []):
            athlete = row.get("athlete", {})
            if athlete.get("id") is not None:
                roster[(team_id, str(athlete["id"]))] = (
                    athlete.get("displayName")
                )

scorer = roster.get((scoring_id, athlete_id))
assert scorer, "First scorer not resolved to team roster"

clock = first.get("clock", {}).get("displayValue", "")
match = re.fullmatch(
    r"(\d{1,2}):(\d{2})(?:\.(0+))?", clock
)
assert match and int(match[2]) < 60
clock_seconds = int(match[1]) * 60 + int(match[2])

description = first.get("text", "")
assert isinstance(description, str)
kind = (
    "free_throw" if "free throw" in description.lower()
    else "field_goal" if first.get("shootingPlay") is True
    else "unresolved"
)

if "homeScore" in first or "awayScore" in first:
    assert first.get("homeScore") == (
        first["scoreValue"] if scoring_team == sides["home"] else 0
    )
    assert first.get("awayScore") == (
        first["scoreValue"] if scoring_team == sides["away"] else 0
    )

def norm(name):
    return re.sub(
        r"[^a-z0-9]", "",
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore").decode().lower()
    )

checks = {
    "first_scorer": norm(scorer) == norm(expected["first_scorer"]),
    "scoring_team": scoring_team == expected["scoring_team"],
    "basket_type": kind == expected["kind"],
    "points": first["scoreValue"] == expected["points"],
    "clock": clock_seconds == expected["clock_seconds"]
}

print(json.dumps({
    "source": "ESPN public historical summary",
    "game": expected["dunk_game_id"],
    "espn_first_scorer": scorer,
    "espn_first_score_type": kind,
    "espn_first_score_clock": clock,
    "comparisons": checks,
    "all_comparisons_match": all(checks.values()),
    "espn_public_requests": 1,
    "dunkapi_requests": 0,
    "private_database_modified": False,
    "training_enabled": False,
    "model_compatible": False
}, indent=2))

if not all(checks.values()):
    raise SystemExit("MISMATCH: Stop for review")

print("PASS: ESPN first score matches saved NBA reference.")
