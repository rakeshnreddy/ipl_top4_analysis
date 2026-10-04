"""Basketball leagues built by us_sports.py, checked against real seasons.

Fixtures in tests/fixtures hold a season's FixtureDownload regular season and its playoff
games from ESPN's scoreboard, so these tests run offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import leagues
import us_sports

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(cache: Path, feed: str, espn_league: str | None = None, espn_year: int | None = None) -> None:
    """Write a fixture into a cache directory as the FixtureDownload feed and ESPN scoreboard."""
    data = json.loads((FIXTURES / f"{feed}.json").read_text(encoding="utf-8"))
    rows = [
        {"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score}
        for number, round_number, date, home, away, home_score, away_score in data["games"]
    ]
    (cache / f"{feed}.json").write_text(json.dumps(rows), encoding="utf-8")
    if espn_league:
        events = [
            {
                "date": date,
                "season": {"type": kind},
                "competitions": [
                    {
                        "notes": [{"headline": headline}] if headline else [],
                        "neutralSite": neutral,
                        "status": {"type": {"completed": home_score is not None}},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": home}, "score": str(home_score or 0)},
                            {"homeAway": "away", "team": {"displayName": away}, "score": str(away_score or 0)},
                        ],
                    }
                ],
            }
            for date, kind, headline, home, away, home_score, away_score, neutral in data["playoffs"]
        ]
        (cache / f"{espn_league}-espn-{espn_year}.json").write_text(json.dumps({"events": events}), encoding="utf-8")


def table(payload: dict) -> list[tuple[str, int, int]]:
    return [(row["shortName"], row["wins"], row["losses"]) for row in payload["standings"] if row["played"]]


# Official final standings, in order.
OFFICIAL_WNBA = {
    # https://www.wnba.com/standings (seeds 1-8 confirmed by
    # https://www.wnba.com/news/2026-playoffs-series-preview-first-round)
    2026: [
        ("MIN", 33, 11), ("GSV", 32, 12), ("LVA", 31, 13), ("ATL", 30, 14), ("WAS", 28, 16),
        ("IND", 28, 16), ("DAL", 27, 17), ("NYL", 26, 18), ("PDX", 17, 27), ("PHX", 16, 28),
        ("CHI", 16, 28), ("LAS", 16, 28), ("TOR", 11, 33), ("CON", 11, 33), ("SEA", 8, 36),
    ],
    # https://www.wnba.com/standings?season=2025
    2025: [
        ("MIN", 34, 10), ("LVA", 30, 14), ("ATL", 30, 14), ("PHX", 27, 17), ("NYL", 27, 17),
        ("IND", 24, 20), ("SEA", 23, 21), ("GSV", 23, 21), ("LAS", 21, 23), ("WAS", 16, 28),
        ("CON", 11, 33), ("CHI", 10, 34), ("DAL", 10, 34),
    ],
}


class WnbaTests(unittest.TestCase):
    """The 2026 season during its semifinals (3 October 2026) and the finished 2025 season."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("wnba")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load_fixture(cache, "wnba-2026", "wnba", 2026)
            load_fixture(cache, "wnba-2025", "wnba", 2025)
            (cache / "wnba-2024.json").write_text("[]", encoding="utf-8")
            cls.live = us_sports.build_payload(cls.cfg, datetime(2026, 10, 3, 12, tzinfo=timezone.utc), cache)
            cls.past = us_sports.build_payload(cls.cfg, datetime(2025, 10, 20, tzinfo=timezone.utc), cache)

    def test_the_tables_match_the_official_standings(self) -> None:
        # Ties (WAS-IND, PHX-CHI-LAS, TOR-CON in 2026) follow the WNBA's tiebreakers.
        self.assertEqual(table(self.live), OFFICIAL_WNBA[2026])
        # The 2025 feed has the Commissioner's Cup final (Indiana beat Minnesota); it does not count.
        self.assertEqual(table(self.past), OFFICIAL_WNBA[2025])

    def test_eight_teams_are_seeded_as_one_table(self) -> None:
        seeds = {row["shortName"]: row["seed"] for row in self.live["standings"]}
        self.assertEqual([short for short, _, _ in OFFICIAL_WNBA[2026]], sorted(seeds, key=seeds.get))
        playoffs = {team for team, values in self.live["analysis"]["probabilities"].items() if values["playoffs"] == 100.0}
        self.assertEqual(len(playoffs), 8)
        league = self.live["league"]
        self.assertEqual(league["cutoffs"], [{"after": 8, "label": "Playoff line"}])
        self.assertEqual([group["key"] for group in league["groups"]], ["East", "West"])
        self.assertEqual(league["positionLabel"], "Seed")

    def test_the_real_2026_bracket_is_reproduced(self) -> None:
        rounds = {item["key"]: item["series"] for item in self.live["bracket"]["rounds"]}
        first = [(item["topSeed"], item["bottomSeed"], item["topWins"], item["bottomWins"], item["winner"]) for item in rounds["R1"]]
        self.assertEqual(
            first,
            [
                (1, 8, 0, 2, "New York Liberty"),
                (4, 5, 2, 0, "Atlanta Dream"),
                (2, 7, 2, 1, "Golden State Valkyries"),
                (3, 6, 2, 1, "Las Vegas Aces"),
            ],
        )
        self.assertEqual([(item["top"], item["bottom"], item["bestOf"]) for item in rounds["SF"]], [
            ("Atlanta Dream", "New York Liberty", 5),
            ("Golden State Valkyries", "Las Vegas Aces", 5),
        ])
        self.assertEqual([item["bestOf"] for item in rounds["F"]], [7])
        self.assertEqual(self.live["metadata"]["season_status"], "postseason")

    def test_title_odds_go_to_the_semifinalists_only(self) -> None:
        title = {team: values["title"] for team, values in self.live["analysis"]["probabilities"].items()}
        # Each chance is rounded to two decimals.
        self.assertAlmostEqual(sum(title.values()), 100, delta=0.05)
        self.assertEqual({team for team, value in title.items() if value > 0}, {"Atlanta Dream", "New York Liberty", "Golden State Valkyries", "Las Vegas Aces"})
        settled = {tier["key"] for tier in self.live["league"]["tiers"] if tier.get("settled")}
        self.assertEqual(settled, {"playoffs", "top4", "top1"})
        self.assertEqual(self.live["fixtures"][0]["stage"], "Semifinals")
        self.assertEqual(self.live["metadata"]["credits"][0]["name"], "ESPN")

    def test_the_finished_2025_playoffs_name_the_champion(self) -> None:
        # ESPN wrote one Finals game as "WNBA FINALS - Game 3"; it still counts.
        final = self.past["bracket"]["rounds"][-1]["series"][0]
        self.assertEqual((final["top"], final["bottom"], final["topWins"], final["bottomWins"]), ("Las Vegas Aces", "Phoenix Mercury", 4, 0))
        self.assertEqual(self.past["bracket"]["champion"], "Las Vegas Aces")
        self.assertEqual(self.past["playoffs"], {"champion": "Las Vegas Aces"})
        self.assertEqual(self.past["metadata"]["season_status"], "complete")


class SeriesTests(unittest.TestCase):
    def test_home_patterns(self) -> None:
        self.assertEqual(us_sports.home_pattern("1-1-1"), [True, False, True])
        self.assertEqual(us_sports.home_pattern("2-2-1"), [True, True, False, False, True])
        self.assertEqual(us_sports.home_pattern("2-2-1-1-1"), [True, True, False, False, True, False, True])
        with self.assertRaises(ValueError):
            us_sports.home_pattern("2-2")

    def test_wnba_series_lengths_by_round(self) -> None:
        cfg = leagues.read_config("wnba")
        self.assertEqual([len(us_sports.series_pattern(cfg, stage)) for stage in ("R1", "SF", "F")], [3, 5, 7])

    def test_a_series_under_way_starts_from_its_score(self) -> None:
        # Two even teams, the top team leading a best-of-three 1-0 with game 2 away and game 3 at home.
        rng = np.random.default_rng(1)
        strength = np.zeros((20_000, 2))
        top, bottom = np.zeros(20_000, dtype=int), np.ones(20_000, dtype=int)
        winner = us_sports.play_series(rng, strength, top, bottom, 0.0, 10.0, 3, [True, False, True], top_wins=1)
        self.assertAlmostEqual(float((winner == 0).mean()), 0.75, delta=0.02)


class TiebreakTests(unittest.TestCase):
    def test_a_three_way_tie_restarts_after_each_split(self) -> None:
        # A and B beat C twice; A and B split. A then wins on record against winning teams.
        from team_sports import Game

        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        games = [
            Game("1", None, start, "A", "C", None, 80, 70),
            Game("2", None, start, "B", "C", None, 80, 70),
            Game("3", None, start, "A", "B", None, 80, 70),
            Game("4", None, start, "B", "A", None, 90, 70),
            Game("5", None, start, "C", "D", None, 90, 70),
            Game("6", None, start, "C", "D", None, 90, 70),
            Game("7", None, start, "A", "D", None, 60, 70),
            Game("8", None, start, "B", "D", None, 60, 70),
            Game("9", None, start, "D", "E", None, 60, 50),
        ]
        cfg = {"teams": {name: {"conference": "overall", "division": "East"} for name in "ABCDE"}, "conferences": [{"key": "overall", "label": "League", "divisions": ["East"]}]}
        structure = us_sports.league_structure(cfg)
        records = us_sports.team_records(games, structure, "basketball")
        self.assertEqual({team: (records[team]["wins"], records[team]["losses"]) for team in "ABCD"}, {"A": (2, 2), "B": (2, 2), "C": (2, 2), "D": (3, 2)})

        order = us_sports.tiebreak_order(["head-to-head", "vs-winning-teams", "head-to-head-differential", "differential"], "basketball", games, records, {})

        # Head-to-head among A, B and C: A 2-1, B 2-1, C 0-2, so C is last. A and B start again:
        # 1-1 against each other, 2-2 against winning teams, then B's +10 head-to-head points win.
        self.assertEqual(sorted("ABC", key=lambda team: -order[team]), ["B", "A", "C"])


if __name__ == "__main__":
    unittest.main()
