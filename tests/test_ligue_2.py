"""Ligue 2 (leagues/ligue-2.json), checked against the LFP's official table.

tests/fixtures/ligue-2-2026.json holds FixtureDownload's 2026-27 feed (the schedule, and results
after seven rounds), so these tests run offline. FixtureDownload has no earlier Ligue 2 season.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import football
import leagues

FIXTURES = Path(__file__).parent / "fixtures"

# Official table after round 7, read on 3 October 2026: (short name, played, points, goal difference).
# https://ligue1.com/fr/competitions/ligue2bkt/standings (ESPN's fra.2 standings agree).
# Guingamp and Dunkerque have the same record, goals, wins and away wins and have not met; the LFP
# ranks them on discipline (Guingamp 12 yellow cards and 1 red, Dunkerque 18 and 2).
OFFICIAL_2026_27 = [
    ("STE", 7, 16, 11), ("RSF", 7, 14, 2), ("REI", 7, 13, 6), ("MHS", 7, 12, 1), ("MET", 7, 10, 3),
    ("ASN", 7, 10, 1), ("ANN", 7, 10, 0), ("SOC", 7, 10, -1), ("DIJ", 7, 9, 0), ("PAU", 7, 8, 0),
    ("EAG", 7, 8, -2), ("DUN", 7, 8, -2), ("GRE", 7, 8, -3), ("ROD", 7, 7, -2), ("NAN", 7, 7, -4),
    ("CLE", 7, 6, -2), ("BOU", 7, 5, -2), ("LAV", 7, 5, -6),
]


class LigueTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = leagues.read_config("ligue-2")
        # Without ESPN, so the test stays offline; it shows no deductions this season.
        offline = dict(cls.config, sources={"fixturedownload": cls.config["sources"]["fixturedownload"]})
        data = json.loads((FIXTURES / "ligue-2-2026.json").read_text(encoding="utf-8"))
        rows = [
            {"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score}
            for number, round_number, date, home, away, home_score, away_score in data["games"]
        ]
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "ligue-2-2026.json").write_text(json.dumps(rows), encoding="utf-8")
            # There is no ligue-2-2025 feed; the build must not need one.
            cls.payload = football.build_payload(offline, datetime(2026, 10, 3, 12, tzinfo=timezone.utc), cache)

    def test_the_table_matches_the_official_one(self) -> None:
        table = [(row["shortName"], row["played"], row["points"], row["goalDifference"]) for row in self.payload["standings"]]
        self.assertEqual(table, OFFICIAL_2026_27)
        self.assertEqual(self.payload["league"]["id"], "ligue-2-2026-27")

    def test_the_first_season_in_the_feed_builds_without_a_previous_one(self) -> None:
        self.assertEqual(self.payload["metadata"]["warnings"], [])
        self.assertEqual(self.payload["metadata"]["data_freshness_status"], "fresh")
        notes = " ".join(self.payload["analysis"]["modelNotes"])
        self.assertIn("FixtureDownload has no Ligue 2 season before 2026-27", notes)
        self.assertIn("fitted on this season with", notes)
        # Nantes and Metz, relegated from Ligue 1, and the clubs promoted from National all start level.
        self.assertEqual(len(self.payload["analysis"]["ratings"]), 18)

    def test_tiers_follow_the_lfp_rules(self) -> None:
        tiers = {tier["key"]: (tier["kind"], tier["size"]) for tier in self.payload["league"]["tiers"]}
        self.assertEqual(
            tiers,
            {"title": ("top", 1), "promotion": ("top", 2), "playoffs": ("top", 5), "relegation": ("bottom", 2), "bottom3": ("bottom", 3)},
        )
        probabilities = self.payload["analysis"]["probabilities"]
        for key, slots in (("promotion", 2), ("playoffs", 5), ("relegation", 2), ("bottom3", 3)):
            self.assertAlmostEqual(sum(values[key] for values in probabilities.values()), slots * 100, delta=0.1)
        self.assertEqual(len(self.payload["fixtures"]), 306 - 63)

    def test_goal_difference_comes_before_head_to_head(self) -> None:
        self.assertEqual(self.config["tiebreak"][:2], ["goal-difference", "head-to-head-complete"])
        self.assertIn("ranked by goal difference, then head-to-head points", " ".join(self.payload["analysis"]["modelNotes"]))


if __name__ == "__main__":
    unittest.main()
