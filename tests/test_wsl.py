"""The Women's Super League (leagues/wsl.json), checked against WSL Football's official table.

tests/fixtures/wsl-2026.json holds FixtureDownload's 2026-27 feed (the schedule, and results
after four rounds), so these tests run offline.
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

# Official table read on 3 October 2026: (short name, played, points, goal difference).
# https://www.wslfootball.com/standings/wsl (ESPN's eng.w.1 standings agree). It includes
# Manchester United 1-0 Liverpool, played on 3 October at 12:30 UTC, which FixtureDownload's
# feed still listed for 4 October without a score.
OFFICIAL_2026_27 = [
    ("MCI", 4, 12, 8), ("TOT", 4, 10, 13), ("CHE", 4, 10, 8), ("LCL", 4, 9, 5), ("LIV", 5, 7, 3),
    ("MNU", 5, 7, -4), ("EVE", 4, 6, -1), ("ARS", 4, 5, 0), ("CRY", 4, 5, -6), ("WHU", 4, 3, -3),
    ("BHA", 4, 2, -3), ("BIR", 4, 2, -4), ("AVL", 4, 2, -7), ("CHA", 4, 0, -9),
]
LATE_RESULT = ("Manchester United", "Liverpool", "2026-10-03 12:30:00Z", 1, 0)


def build(late_result: bool) -> dict:
    config = leagues.read_config("wsl")
    # Without ESPN, so the test stays offline; it shows no deductions this season.
    offline = dict(config, sources={"fixturedownload": config["sources"]["fixturedownload"]})
    data = json.loads((FIXTURES / "wsl-2026.json").read_text(encoding="utf-8"))
    rows = []
    for number, round_number, date, home, away, home_score, away_score in data["games"]:
        if late_result and (home, away) == LATE_RESULT[:2]:
            date, home_score, away_score = LATE_RESULT[2:]
        rows.append({"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score})
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        (cache / "wsl-2026.json").write_text(json.dumps(rows), encoding="utf-8")
        (cache / "wsl-2025.json").write_text("[]", encoding="utf-8")
        return football.build_payload(offline, datetime(2026, 10, 3, 18, tzinfo=timezone.utc), cache)


def table(payload: dict) -> list[tuple[str, int, int, int]]:
    return [(row["shortName"], row["played"], row["points"], row["goalDifference"]) for row in payload["standings"]]


class WslTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.feed = build(late_result=False)
        cls.complete = build(late_result=True)

    def test_the_table_matches_the_official_one(self) -> None:
        self.assertEqual(table(self.complete), OFFICIAL_2026_27)
        self.assertEqual(self.complete["league"]["id"], "wsl-2026-27")

    def test_the_feed_is_one_result_behind(self) -> None:
        official = {row[0]: row for row in OFFICIAL_2026_27}
        rows = {row[0]: row for row in table(self.feed)}
        self.assertEqual({key for key in rows if rows[key] != official[key]}, {"LIV", "MNU"})
        self.assertEqual((rows["LIV"][1], rows["MNU"][1]), (4, 4))

    def test_tiers_follow_the_2026_27_rules(self) -> None:
        tiers = {tier["key"]: (tier["kind"], tier["size"]) for tier in self.complete["league"]["tiers"]}
        self.assertEqual(tiers, {"title": ("top", 1), "ucl": ("top", 3), "relegation": ("bottom", 1), "bottom2": ("bottom", 2)})
        probabilities = self.complete["analysis"]["probabilities"]
        for key, slots in (("ucl", 3), ("relegation", 1), ("bottom2", 2)):
            self.assertAlmostEqual(sum(values[key] for values in probabilities.values()), slots * 100, delta=0.1)
        self.assertEqual(len(self.complete["fixtures"]), 182 - 29)

    def test_ties_go_to_goal_difference_then_goals_then_wins(self) -> None:
        self.assertEqual(leagues.read_config("wsl")["tiebreak"], ["goal-difference", "goals", "wins", "head-to-head"])
        # Tottenham (+13) are above Chelsea (+8) on 10 points; Brighton, Birmingham and Aston Villa on 2.
        order = [row[0] for row in table(self.complete)]
        self.assertLess(order.index("TOT"), order.index("CHE"))
        self.assertEqual(order[10:13], ["BHA", "BIR", "AVL"])


if __name__ == "__main__":
    unittest.main()
