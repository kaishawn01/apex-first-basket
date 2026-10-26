"""Run: py -m unittest -v test_engine.py (no internet required)."""
import unittest
import json
from pathlib import Path
import first_basket_engine as eng


class FirstBasketTests(unittest.TestCase):
    def test_fanduel_free_throw_scoring_and_first_fg(self):
        def a(n, typ, team, pid, desc, fg=0, result=""):
            return dict(period=1, actionId=n, actionType=typ, teamTricode=team,
                        personId=pid, description=desc, isFieldGoal=fg, shotResult=result)
        actions = [
            a(1, "period", "", 0, "Start of 1st Period"),
            a(2, "Jump Ball", "AAA", 1, "Jump ball"),
            a(3, "Missed Shot", "AAA", 1, "MISS One three", 1, "Missed"),
            a(4, "Missed Shot", "BBB", 6, "MISS Six layup", 1, "Missed"),
            a(5, "Free Throw", "BBB", 7, "MISS Seven Free Throw 1 of 2"),
            a(6, "Free Throw", "BBB", 7, "Seven Free Throw 2 of 2"),
            a(7, "Made Shot", "AAA", 2, "Two 3PT Jump Shot", 1, "Made"),
        ]
        play = {"game": {"actions": actions}}
        box = {"game": {
            "homeTeam": {"teamTricode": "AAA", "players": [{"personId": i, "name": f"AAA Player{i}", "starter": "1"} for i in range(1, 6)]},
            "awayTeam": {"teamTricode": "BBB", "players": [{"personId": i, "name": f"BBB Player{i}", "starter": True} for i in range(6, 11)]},
        }}
        history = eng.extract_game({"gameId": "0022600001", "_date": "2026-10-25"}, play, box)
        self.assertEqual(len(history), 10)
        self.assertEqual([(r["team"], r["player_id"]) for r in history if r["first_scorer"]], [("BBB", "7")])
        self.assertEqual([(r["team"], r["player_id"]) for r in history if r["first_fg_scorer"]], [("AAA", "2")])
        self.assertEqual([(r["team"], r["player_id"]) for r in history if r["first_team_shot"]], [("AAA", "1"), ("BBB", "6")])
        self.assertEqual(sum(r["first_game_shot"] for r in history), 1)
        self.assertEqual(sum(r["tip_first_action"] for r in history), 5)

    def test_live_cdn_action_types(self):
        base = dict(personId=1, teamTricode="AAA", period=1, isFieldGoal=1)
        for typ in ("2pt", "3pt"):
            made = dict(base, actionType=typ, shotResult="Made")
            missed = dict(base, actionType=typ, shotResult="Missed")
            self.assertTrue(eng.is_fg_attempt(made))
            self.assertTrue(eng.is_made_score(made))
            self.assertFalse(eng.is_made_score(missed))
            self.assertEqual(eng.first_offense_team([missed]), "AAA")
        free = dict(base, actionType="freethrow", isFieldGoal=0, shotResult="Made")
        self.assertTrue(eng.is_made_score(free))
        self.assertFalse(eng.is_fg_attempt(free))
        self.assertFalse(eng.is_made_score(dict(free, shotResult="Missed")))
        self.assertFalse(eng.is_made_score(dict(free, shotResult="")))

    def test_espn_real_game_adapter(self):
        payload = json.loads(Path(__file__).with_name("espn_test_fixture.json").read_text())
        play, box = eng.espn_game_payloads(payload)
        rows = eng.extract_game({"gameId": "espn_401809955", "_date": "2025-10-25"}, play, box)
        self.assertEqual(len(rows), 10)
        self.assertEqual([r["player"] for r in rows if r["first_scorer"]], ["Josh Giddey"])
        self.assertEqual(eng.espn_team({"abbreviation": "GS"}), "GSW")

    def test_odds_math(self):
        self.assertAlmostEqual(eng.american_to_decimal("+650"), 7.5)
        self.assertAlmostEqual(eng.american_to_decimal("-150"), 1.66666666667)
        self.assertIsNone(eng.american_to_decimal("NA"))
        self.assertAlmostEqual(0.20 * eng.american_to_decimal("+650") - 1, 0.50)

    def test_normalized_probability(self):
        stats = {"AAA": {"first": 0.55, "tip_proxy": 0.52}, "BBB": {"first": 0.45, "tip_proxy": 0.48}}
        p_team = eng.first_team_probability("AAA", "BBB", stats)
        starters = [{"player_id": str(i), "player": f"Player {i}"} for i in range(1, 6)]
        shares = eng.player_weights([], starters, "AAA")
        self.assertAlmostEqual(sum(p * p_team for _, p, *_ in shares), p_team, places=8)
        self.assertAlmostEqual(p_team + (1 - p_team), 1.0, places=8)

    def test_date_formats(self):
        self.assertEqual(eng.day_of_game({"gameDate": "10/25/2026 00:00:00"}), "2026-10-25")
        self.assertEqual(eng.day_of_game({"gameDate": "2026-10-25"}), "2026-10-25")


if __name__ == "__main__":
    unittest.main()
