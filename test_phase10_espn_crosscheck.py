"""Synthetic offline tests for the Phase 10 ESPN cross-checker."""
import io
import json
import runpy
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "validation" / "phase10_espn_crosscheck.py"
REFERENCE = ROOT / "validation" / "PHASE10_PUBLIC_FIRST_SCORE_REFERENCES.json"
GAME_ID = "401809943"

class FakeResponse:
    def __init__(self, data, status=200):
        self.status_code = status
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, size):
        yield self.data

class OfflineEspnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        doc = json.loads(REFERENCE.read_text(encoding="utf-8-sig"))
        cls.ref = next(
            r for r in doc["records"]
            if r["dunk_game_id"] == GAME_ID
        )

    def fixture(self):
        r = self.ref
        return {
            "header": {
                "id": GAME_ID,
                "competitions": [{
                    "date": r["date"] + "T23:00:00Z",
                    "status": {"type": {"completed": True}},
                    "competitors": [
                        {"homeAway": "home", "team": {
                            "id": "20", "abbreviation": r["home"]}},
                        {"homeAway": "away", "team": {
                            "id": "10", "abbreviation": r["away"]}}
                    ]
                }]
            },
            "plays": [
                {
                    "period": {"number": 1},
                    "sequenceNumber": 1,
                    "scoreValue": 0,
                    "scoringPlay": False,
                    "homeScore": 0,
                    "awayScore": 0,
                    "clock": {"displayValue": "11:59"}
                },
                {
                    "period": {"number": 1},
                    "sequenceNumber": 2,
                    "scoreValue": r["points"],
                    "scoringPlay": True,
                    "shootingPlay": True,
                    "homeScore": r["points"],
                    "awayScore": 0,
                    "clock": {"displayValue": r["clock"]},
                    "team": {"id": "20"},
                    "participants": [{"athlete": {"id": "7001"}}],
                    "text": "Synthetic made three-point jump shot"
                }
            ],
            "boxscore": {"players": [{
                "team": {"id": "20"},
                "statistics": [{"athletes": [{"athlete": {
                    "id": "7001", "displayName": r["first_scorer"]
                }}]}]
            }]}
        }

    def execute(self, payload, status=200):
        output = io.StringIO()

        def fake_get(url, **kwargs):
            self.assertEqual(
                url,
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
            )
            self.assertEqual(kwargs["params"], {"event": GAME_ID})
            self.assertFalse(kwargs["allow_redirects"])
            self.assertNotIn("x-api-key", kwargs["headers"])
            return FakeResponse(payload, status)

        with patch("requests.get", side_effect=fake_get) as request:
            with patch.object(sys, "argv", [str(SCRIPT), GAME_ID]):
                with redirect_stdout(output):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
            self.assertEqual(request.call_count, 1)

        return output.getvalue()

    def test_01_correct_reference_passes(self):
        output = self.execute(self.fixture())
        self.assertIn('"all_comparisons_match": true', output)
        self.assertIn(
            "PASS: ESPN first score matches saved NBA reference.",
            output
        )

    def test_02_wrong_scorer_rejected(self):
        data = self.fixture()
        athlete = data["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["athlete"]
        athlete["displayName"] = "Different Player"
        with self.assertRaisesRegex(SystemExit, "MISMATCH"):
            self.execute(data)

    def test_03_wrong_clock_rejected(self):
        data = self.fixture()
        data["plays"][1]["clock"]["displayValue"] = "11:12"
        with self.assertRaisesRegex(SystemExit, "MISMATCH"):
            self.execute(data)

    def test_04_wrong_shot_type_rejected(self):
        data = self.fixture()
        data["plays"][1]["shootingPlay"] = False
        with self.assertRaisesRegex(SystemExit, "MISMATCH"):
            self.execute(data)

    def test_05_duplicate_sequence_rejected(self):
        data = self.fixture()
        data["plays"][1]["sequenceNumber"] = 1
        with self.assertRaises(AssertionError):
            self.execute(data)

    def test_06_http_error_stops(self):
        with self.assertRaisesRegex(ValueError, "ESPN HTTP 503"):
            self.execute(self.fixture(), status=503)

if __name__ == "__main__":
    unittest.main()
