"""The Süper Lig (leagues/super-lig.json), checked against the TFF's official tables.

tests/fixtures/super-lig-2026.json holds FixtureDownload's 2026-27 feed (the schedule, and results
after six rounds), so these tests run offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import football
import leagues
import team_sports
from team_sports import Game

FIXTURES = Path(__file__).parent / "fixtures"

# Official table after round 6, read on 3 October 2026: (short name, played, points, goal difference).
# https://www.tff.org/default.aspx?pageID=198 (ESPN's tur.1 standings agree).
OFFICIAL_2026_27 = [
    ("AMD", 6, 13, 8), ("GS", 6, 13, 3), ("BJK", 6, 12, 7), ("KOC", 6, 12, 3), ("ALA", 6, 11, 2),
    ("FB", 6, 10, 10), ("TS", 6, 10, 8), ("KAS", 6, 10, 2), ("RIZ", 6, 10, 1), ("GFK", 6, 8, 0),
    ("COR", 6, 7, 1), ("IBF", 6, 7, -1), ("GEN", 6, 7, -8), ("ERZ", 6, 7, -8), ("KON", 6, 4, -4),
    ("SAM", 6, 4, -6), ("GOZ", 6, 3, -4), ("EYP", 6, 3, -14),
]

# Official 2025-26 final table: team, played, wins, draws, losses, goals for, goals against, points.
# https://www.tff.org/default.aspx?pageID=1768
OFFICIAL_2025_26 = [
    ("Galatasaray", 34, 24, 5, 5, 77, 30, 77),
    ("Fenerbahçe", 34, 21, 11, 2, 77, 37, 74),
    ("Trabzonspor", 34, 20, 9, 5, 61, 39, 69),
    ("Besiktas", 34, 17, 9, 8, 59, 40, 60),
    ("Istanbul Basaksehir", 34, 16, 9, 9, 58, 35, 57),
    ("Göztepe", 34, 14, 13, 7, 42, 32, 55),
    ("Samsunspor", 34, 13, 12, 9, 46, 45, 51),
    ("Çaykur Rizespor", 34, 10, 11, 13, 46, 52, 41),
    ("Konyaspor", 34, 10, 10, 14, 43, 50, 40),
    ("Kocaelispor", 34, 9, 10, 15, 26, 38, 37),
    ("Alanyaspor", 34, 7, 16, 11, 41, 41, 37),
    ("Gaziantep", 34, 9, 10, 15, 43, 58, 37),
    ("Kasimpasa", 34, 8, 11, 15, 33, 49, 35),
    ("Gençlerbirligi", 34, 9, 7, 18, 36, 47, 34),
    ("Eyüpspor", 34, 8, 9, 17, 33, 48, 33),
    ("Antalyaspor", 34, 8, 8, 18, 33, 55, 32),
    ("Kayserispor", 34, 6, 12, 16, 27, 62, 30),
    ("Fatih Karagümrük", 34, 8, 6, 20, 31, 54, 30),
]
# The 2025-26 games between the teams level on points at the end (from FixtureDownload's feed).
MEETINGS_2025_26 = [
    ("Gaziantep", "Kocaelispor", 2, 0),
    ("Kocaelispor", "Alanyaspor", 2, 0),
    ("Alanyaspor", "Gaziantep", 0, 0),
    ("Kocaelispor", "Gaziantep", 3, 0),
    ("Alanyaspor", "Kocaelispor", 5, 0),
    ("Gaziantep", "Alanyaspor", 1, 1),
    ("Fatih Karagümrük", "Kayserispor", 2, 2),
    ("Kayserispor", "Fatih Karagümrük", 1, 0),
]


def load_fixture(cache: Path, feed: str) -> list[Game]:
    data = json.loads((FIXTURES / f"{feed}.json").read_text(encoding="utf-8"))
    rows = [
        {"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score}
        for number, round_number, date, home, away, home_score, away_score in data["games"]
    ]
    (cache / f"{feed}.json").write_text(json.dumps(rows), encoding="utf-8")
    return [team_sports.parse_game(row) for row in rows]


class SuperLigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = leagues.read_config("super-lig")
        # Without ESPN, so the test stays offline; it shows no deductions this season.
        offline = dict(cls.config, sources={"fixturedownload": cls.config["sources"]["fixturedownload"]})
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            cls.games = load_fixture(cache, "super-lig-2026")
            (cache / "super-lig-2025.json").write_text("[]", encoding="utf-8")
            cls.payload = football.build_payload(offline, datetime(2026, 10, 3, 12, tzinfo=timezone.utc), cache)

    def test_the_table_matches_the_official_one(self) -> None:
        table = [(row["shortName"], row["played"], row["points"], row["goalDifference"]) for row in self.payload["standings"]]
        self.assertEqual(table, OFFICIAL_2026_27)
        self.assertEqual(self.payload["league"]["id"], "super-lig-2026-27")

    def test_head_to_head_waits_until_the_teams_have_met_twice(self) -> None:
        # Kasimpasa and Trabzonspor (1-1) are the only teams level on 10 points to have met; the TFF
        # table still ranks the four by goal difference, as it does Çorum, Basaksehir, Gençlerbirligi
        # and Erzurumspor on 7 points.
        rows = football.standings(self.games, sorted({game.home for game in self.games} | {game.away for game in self.games}))
        self.assertNotEqual(football.ranked(rows, self.games, "head-to-head"), football.ranked(rows, self.games, self.config["tiebreak"]))

    def test_the_tff_tiebreak_reproduces_the_2025_26_final_table(self) -> None:
        rows = {
            team: {"played": played, "wins": wins, "draws": draws, "losses": losses, "goalsFor": scored, "goalsAgainst": conceded, "goalDifference": scored - conceded, "points": points}
            for team, played, wins, draws, losses, scored, conceded, points in OFFICIAL_2025_26
        }
        games = [Game(str(i), None, datetime(2026, 1, 1, tzinfo=timezone.utc), home, away, None, hs, aws) for i, (home, away, hs, aws) in enumerate(MEETINGS_2025_26)]
        official = [team for team, *_ in OFFICIAL_2025_26]

        self.assertEqual(football.ranked(rows, games, self.config["tiebreak"]), official)
        # Goal difference alone would have put Alanyaspor 10th and sent Kayserispor down instead of Fatih Karagümrük.
        by_goal_difference = football.ranked(rows, games)
        self.assertEqual(by_goal_difference[9], "Alanyaspor")
        self.assertEqual(by_goal_difference[16], "Fatih Karagümrük")

    def test_tiers_follow_the_2026_27_statute(self) -> None:
        tiers = {tier["key"]: (tier["kind"], tier["size"]) for tier in self.payload["league"]["tiers"]}
        self.assertEqual(tiers, {"title": ("top", 1), "top2": ("top", 2), "relegation": ("bottom", 3)})
        probabilities = self.payload["analysis"]["probabilities"]
        self.assertAlmostEqual(sum(values["relegation"] for values in probabilities.values()), 300, delta=0.1)
        self.assertEqual(len(self.payload["fixtures"]), 306 - 54)


if __name__ == "__main__":
    unittest.main()
