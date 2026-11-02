"""Offline, public-only NBA first-score regression tests."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "validation" / "PHASE10_REQUEST_MANIFEST.json"
REFERENCE = ROOT / "validation" / "PHASE10_PUBLIC_FIRST_SCORE_REFERENCES.json"

MANIFEST_SHA256 = "c4309436dcae82adc9ee435f33a81acefa94385d32f9541b17a458428c72e905"

# Fixed references independently checked against NBA play-by-play.
# Date, away, home, NBA ID, scorer, team, kind, points, clock, URL slug, status.
GOLDEN = {
    "401809243": (
        "2025-10-21", "HOU", "OKC", "0022500001",
        "Chet Holmgren", "OKC", "field_goal", 2,
        "11:26", "hou-vs-okc", "owner_crosschecked"
    ),
    "401809236": (
        "2025-10-23", "OKC", "IND", "0022500005",
        "Shai Gilgeous-Alexander", "OKC", "free_throw", 1,
        "11:01", "okc-vs-ind", "public_reference_only"
    ),
    "401809943": (
        "2025-10-24", "ATL", "ORL", "0022500090",
        "Franz Wagner", "ORL", "field_goal", 3,
        "11:14", "atl-vs-orl", "public_reference_only"
    ),
    "401809956": (
        "2025-10-25", "OKC", "ATL", "0022500101",
        "Chet Holmgren", "OKC", "field_goal", 3,
        "11:16", "okc-vs-atl", "public_reference_only"
    ),
    "401809970": (
        "2025-10-27", "ATL", "CHI", "0022500115",
        "Kristaps Porzingis", "ATL", "field_goal", 2,
        "11:21", "atl-vs-chi", "public_reference_only"
    )
}

class PublicFirstScoreReferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(
            REFERENCE.read_text(encoding="utf-8-sig")
        )
        cls.manifest_raw = MANIFEST.read_bytes()
        cls.manifest = json.loads(cls.manifest_raw)
        cls.records = cls.document["records"]

    def test_01_public_only_schema(self):
        self.assertEqual(set(self.document), {
            "schema", "purpose", "provider",
            "training_enabled", "model_compatible", "records"
        })
        self.assertEqual(self.document["schema"], 1)
        self.assertEqual(
            self.document["provider"], "NBA official play-by-play"
        )
        self.assertEqual(len(self.records), 5)
        allowed = {
            "dunk_game_id", "nba_game_id", "date",
            "away", "home", "first_scorer", "scoring_team",
            "kind", "points", "clock", "clock_seconds",
            "source_url", "verification_status"
        }
        for record in self.records:
            with self.subTest(game=record.get("dunk_game_id")):
                self.assertEqual(set(record), allowed)

    def test_02_original_manifest_unchanged(self):
        self.assertEqual(
            hashlib.sha256(self.manifest_raw).hexdigest(),
            MANIFEST_SHA256
        )
        actual = {
            g["game_id"]: (g["date"], g["away"], g["home"])
            for g in self.manifest["games"]
        }
        expected = {
            gid: values[:3] for gid, values in GOLDEN.items()
        }
        self.assertEqual(actual, expected)

    def test_03_official_first_score_values(self):
        records = {
            r["dunk_game_id"]: r for r in self.records
        }
        self.assertEqual(len(records), 5)
        self.assertEqual(set(records), set(GOLDEN))

        for gid, expected in GOLDEN.items():
            with self.subTest(game=gid):
                r = records[gid]
                day, away, home, nbaid, name, team, kind, points, clock, slug, status = expected
                actual = (
                    r["date"], r["away"], r["home"],
                    r["nba_game_id"], r["first_scorer"],
                    r["scoring_team"], r["kind"], r["points"],
                    r["clock"], r["verification_status"]
                )
                self.assertEqual(actual, (
                    day, away, home, nbaid, name, team,
                    kind, points, clock, status
                ))
                mm, ss = map(int, clock.split(":"))
                self.assertEqual(
                    r["clock_seconds"], mm * 60 + ss
                )

    def test_04_official_nba_links(self):
        for record in self.records:
            with self.subTest(game=record["dunk_game_id"]):
                expected = GOLDEN[record["dunk_game_id"]]
                nbaid, slug = expected[3], expected[9]
                url = (
                    f"https://www.nba.com/game/"
                    f"{slug}-{nbaid}/play-by-play"
                )
                self.assertEqual(record["source_url"], url)

    def test_05_model_and_verification_gates(self):
        self.assertIs(self.document["training_enabled"], False)
        self.assertIs(self.document["model_compatible"], False)

        statuses = [
            r["verification_status"] for r in self.records
        ]
        self.assertEqual(
            statuses.count("owner_crosschecked"), 1
        )
        self.assertEqual(
            statuses.count("public_reference_only"), 4
        )

if __name__ == "__main__":
    unittest.main()
