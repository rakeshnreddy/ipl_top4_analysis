"""Leagues that split in two (football_split.py), checked on the Scottish Premiership.

Fixtures in tests/fixtures hold the FixtureDownload feed on 3 October 2026 and the 2024-25
season from ESPN's public scoreboard (FixtureDownload has no Scottish season before 2026-27),
so these tests run offline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import football
import football_split
import leagues
import team_sports
from team_sports import Game

FIXTURES = Path(__file__).parent / "fixtures"
FIELDS = ("MatchNumber", "RoundNumber", "DateUtc", "HomeTeam", "AwayTeam", "HomeTeamScore", "AwayTeamScore")
KICKOFF = datetime(2026, 8, 1, 15, tzinfo=timezone.utc)


def feed(name: str) -> list[dict[str, object]]:
    return [dict(zip(FIELDS, game)) for game in json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["games"]]


def espn_standings(rows: list[tuple[str, int, int, int, int, int, int, int, int]]) -> dict[str, object]:
    """An ESPN standings document (what football.espn_table reads) for official table rows."""
    names = ("gamesPlayed", "wins", "ties", "losses", "pointsFor", "pointsAgainst", "points")
    entries = [
        {"stats": [{"name": name, "value": value} for name, value in zip(names, (played, wins, draws, losses, scored, conceded, points))]}
        for _, played, wins, draws, losses, scored, conceded, _, points in rows
    ]
    return {"children": [{"standings": {"entries": entries}}]}


def build(rows: list[dict[str, object]], year: int, now: datetime, espn: dict[str, object] | None = None) -> dict[str, object]:
    config = leagues.read_config("scottish-premiership")
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        (cache / f"scottish-premiership-{year}.json").write_text(json.dumps(rows), encoding="utf-8")
        if espn is None:
            config = dict(config, sources={"fixturedownload": config["sources"]["fixturedownload"]})
        else:
            (cache / "espn-sco.1.json").write_text(json.dumps(espn), encoding="utf-8")
        return football.build_payload(config, now, cache)


def table(payload: dict[str, object]) -> list[tuple[str, int, int, int, int, int, int, int, int]]:
    return [
        (row["shortName"], row["played"], row["wins"], row["draws"], row["losses"], row["goalsFor"], row["goalsAgainst"], row["goalDifference"], row["points"])
        for row in payload["standings"]
    ]


# The official table after seven rounds (20 September 2026): position, played, goal difference and
# points from https://spfl.co.uk/league/premiership/table (1 October 2026); wins, draws, losses and
# goals from https://www.espn.com/soccer/standings/_/league/sco.1 and
# https://en.wikipedia.org/wiki/2026%E2%80%9327_Scottish_Premiership. Motherwell and Dundee United are
# level on points, goal difference and goals; Motherwell won their meeting 3-0 (SPFL Rule C36).
OFFICIAL_2026_27 = [
    ("CEL", 7, 6, 0, 1, 14, 4, 10, 18),
    ("RAN", 7, 5, 1, 1, 8, 4, 4, 16),
    ("HEA", 7, 4, 1, 2, 14, 8, 6, 13),
    ("DUN", 7, 3, 1, 3, 9, 7, 2, 10),
    ("STM", 7, 3, 1, 3, 8, 9, -1, 10),
    ("STJ", 7, 2, 2, 3, 9, 10, -1, 8),
    ("ABE", 7, 2, 2, 3, 7, 8, -1, 8),
    ("MOT", 7, 2, 2, 3, 9, 11, -2, 8),
    ("DDU", 7, 2, 2, 3, 9, 11, -2, 8),
    ("HIB", 7, 2, 1, 4, 8, 11, -3, 7),
    ("FAL", 7, 1, 3, 3, 6, 9, -3, 6),
    ("KIL", 7, 1, 2, 4, 6, 15, -9, 5),
]

# The final 2024-25 table: https://en.wikipedia.org/wiki/2024%E2%80%9325_Scottish_Premiership (from the
# SPFL's table) and https://www.espn.com/soccer/standings/_/league/sco.1/season/2024. Hearts finished
# seventh with more points than sixth-placed St Mirren: they were seventh at the split.
OFFICIAL_2024_25 = [
    ("CEL", 38, 29, 5, 4, 112, 26, 86, 92),
    ("RAN", 38, 22, 9, 7, 80, 41, 39, 75),
    ("HIB", 38, 15, 13, 10, 62, 50, 12, 58),
    ("DDU", 38, 15, 8, 15, 45, 54, -9, 53),
    ("ABE", 38, 15, 8, 15, 48, 61, -13, 53),
    ("STM", 38, 14, 8, 16, 53, 59, -6, 50),
    ("HEA", 38, 15, 7, 16, 52, 47, 5, 52),
    ("MOT", 38, 14, 7, 17, 46, 63, -17, 49),
    ("KIL", 38, 12, 8, 18, 45, 64, -19, 44),
    ("DUN", 38, 11, 8, 19, 57, 77, -20, 41),
    ("ROS", 38, 9, 10, 19, 37, 65, -28, 37),
    ("STJ", 38, 9, 5, 24, 38, 68, -30, 32),
]
TOP_SIX_2024_25 = {"Celtic", "Rangers", "Hibernian", "Dundee United", "Aberdeen", "St. Mirren"}


class LiveSeasonTests(unittest.TestCase):
    """2026-27 after seven rounds: the feed has the 198 pre-split games only."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build(feed("scottish-premiership-2026"), 2026, datetime(2026, 10, 3, 12, tzinfo=timezone.utc), espn_standings(OFFICIAL_2026_27))

    def test_the_table_matches_the_official_one(self) -> None:
        self.assertEqual(table(self.payload), OFFICIAL_2026_27)

    def test_odds_fill_every_place_once(self) -> None:
        probabilities = self.payload["analysis"]["probabilities"]
        for tier, places in (("title", 1), ("top3", 3), ("top6", 6), ("playoff", 1), ("relegation", 1)):
            self.assertAlmostEqual(sum(values[tier] for values in probabilities.values()), places * 100, delta=0.1, msg=tier)
        for team, positions in self.payload["analysis"]["positions"].items():
            self.assertAlmostEqual(sum(positions), 100, delta=0.1)
            # The play-off tier is 11th place exactly.
            self.assertAlmostEqual(positions[10], probabilities[team]["playoff"], delta=0.02)
        # 228 games in all (38 each): a game is worth 2 or 3 points, about 2.75 on average.
        total = sum(values["points"] for values in self.payload["analysis"]["expected"].values())
        self.assertTrue(2.5 < total / 228 < 2.9, total)

    def test_the_split_is_still_open(self) -> None:
        payload = self.payload
        self.assertEqual(payload["metadata"]["season_status"], "in_progress")
        self.assertEqual(payload["metadata"]["warnings"], [])
        self.assertEqual(payload["league"]["cutoffs"], [{"after": 6, "label": "Split"}])
        self.assertEqual(payload["league"]["headline"], "Scottish Premiership Title, Top Six & Relegation Odds")
        self.assertFalse(any(tier.get("settled") for tier in payload["league"]["tiers"]))
        # Only the feed's own fixtures are listed; the simulated post-split games are not.
        self.assertEqual(len(payload["fixtures"]), 198 - 42)
        self.assertTrue(all(not item["fixtureId"].startswith("split-") for item in payload["matchesThatMatter"]))
        notes = " ".join(payload["analysis"]["modelNotes"])
        self.assertIn("has no Scottish Premiership season before 2026-27", notes)
        self.assertIn("fitted on this season with", notes)
        self.assertIn("splits into sections of 6", notes)
        self.assertIn("goal difference, then goals scored, then head-to-head points", notes)
        # The config's own notes (European places, the play-off) reach the page.
        self.assertIn("Scottish Cup winners", notes)


class PastSeasonTests(unittest.TestCase):
    """2024-25 replayed: at the split, once the post-split fixtures are out, and finished."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = feed("scottish-premiership-2024")
        games = [team_sports.parse_game(row) for row in cls.rows]
        teams = sorted({game.home for game in games})
        before, later = football_split.before_and_after(games, teams, 33)
        cls.real_hosts = {frozenset((game.home, game.away)): game.home for game in later}
        split_day = max(game.date for game in before) + timedelta(days=1)
        pre_split_ids = {game.id for game in before}
        cls.at_split = build([row for row in cls.rows if str(row["MatchNumber"]) in pre_split_ids], 2024, split_day)
        unplayed_later = [row if str(row["MatchNumber"]) in pre_split_ids else dict(row, HomeTeamScore=None, AwayTeamScore=None) for row in cls.rows]
        cls.published = build(unplayed_later, 2024, split_day)
        cls.final = build(cls.rows, 2024, datetime(2025, 5, 25, tzinfo=timezone.utc))

    def test_the_final_table_keeps_the_sections_apart(self) -> None:
        self.assertEqual(table(self.final), OFFICIAL_2024_25)
        self.assertEqual(self.final["metadata"]["season_status"], "complete")
        probabilities = self.final["analysis"]["probabilities"]
        self.assertEqual(probabilities["Heart of Midlothian"]["top6"], 0.0)
        self.assertEqual(probabilities["Ross County"]["playoff"], 100.0)
        self.assertEqual(probabilities["St. Johnstone"]["relegation"], 100.0)

    def test_at_the_split_the_sections_are_fixed_before_the_fixtures_are_out(self) -> None:
        payload = self.at_split
        self.assertEqual(payload["metadata"]["season_status"], "in_progress")
        self.assertEqual(payload["fixtures"], [])
        self.assertEqual({row["teamKey"] for row in payload["standings"][:6]}, TOP_SIX_2024_25)
        top6 = next(tier for tier in payload["league"]["tiers"] if tier["key"] == "top6")
        self.assertTrue(top6["settled"])
        # Hearts went on to finish with more points than St Mirren but could not pass them.
        for team, positions in payload["analysis"]["positions"].items():
            self.assertAlmostEqual(sum(positions[:6]), 100.0 if team in TOP_SIX_2024_25 else 0.0, delta=0.05, msg=team)

    def test_the_post_split_home_sides_follow_the_earlier_meetings(self) -> None:
        games = [team_sports.parse_game(row) for row in self.rows]
        teams = sorted({game.home for game in games})
        before, _ = football_split.before_and_after(games, teams, 33)
        split = football_split.plan({"after": 33, "size": 6}, before, teams, lambda subset: football.ranked(football.standings(subset, teams), subset, "goals-then-head-to-head"))
        self.assertEqual(split.missing, 30)
        self.assertEqual(len(split.games), 30)
        hosted = [game.home == self.real_hosts[frozenset((game.home, game.away))] for game in split.games]
        # The SPFL swapped two of them to give every club two or three home games.
        self.assertEqual(sum(hosted), 28)

    def test_published_post_split_fixtures_replace_the_simulated_ones(self) -> None:
        payload = self.published
        self.assertEqual(len(payload["fixtures"]), 30)
        self.assertEqual({row["teamKey"] for row in payload["standings"][:6]}, TOP_SIX_2024_25)
        self.assertEqual(payload["metadata"]["season_status"], "in_progress")
        self.assertIn("post-split fixtures are published", " ".join(payload["analysis"]["modelNotes"]))
        for team, positions in payload["analysis"]["positions"].items():
            self.assertAlmostEqual(sum(positions[:6]), 100.0 if team in TOP_SIX_2024_25 else 0.0, delta=0.05, msg=team)


def round_robin(teams: list[str], meetings: int) -> list[Game]:
    """Every pair meets ``meetings`` times, alternating venues, a week apart."""
    games = []
    for meeting in range(meetings):
        for first, second in [(a, b) for i, a in enumerate(teams) for b in teams[i + 1 :]]:
            home, away = (first, second) if meeting % 2 == 0 else (second, first)
            games.append(Game(str(len(games) + 1), meeting + 1, KICKOFF + timedelta(days=7 * len(games)), home, away, None, None, None))
    return games


class SplitMechanicsTests(unittest.TestCase):
    TEAMS = ["Albion", "Borough", "City", "Rovers"]
    RULE = {"after": 3, "size": 2}

    def rank(self, subset: list[Game]) -> list[str]:
        return football.ranked(football.standings(subset, self.TEAMS), subset, "goals-then-head-to-head")

    def test_meetings_after_the_split_are_counted_per_pair(self) -> None:
        games = round_robin(self.TEAMS, 2)
        before, later = football_split.before_and_after(games, self.TEAMS, 3)
        self.assertEqual((len(before), len(later)), (6, 6))
        self.assertTrue(all(game.round == 1 for game in before))

    def test_the_team_with_fewer_home_games_against_its_opponent_hosts(self) -> None:
        played = [Game(game.id, game.round, game.date, game.home, game.away, None, 1, 0) for game in round_robin(self.TEAMS, 1)]
        split = football_split.plan(self.RULE, played, self.TEAMS, self.rank)
        # Every home side won its game: Albion (3 wins) and Borough (2) make the top section.
        self.assertEqual(split.sections, {"Albion": 0, "Borough": 0, "City": 1, "Rovers": 1})
        self.assertEqual([(game.home, game.away) for game in split.games], [("Borough", "Albion"), ("Rovers", "City")])
        self.assertEqual(split.missing, 2)

    def test_open_sections_cover_every_pair_until_the_split(self) -> None:
        games = round_robin(self.TEAMS, 1)
        split = football_split.plan(self.RULE, games, self.TEAMS, self.rank)
        self.assertIsNone(split.sections)
        self.assertEqual(len(split.games), 6)
        self.assertEqual(split.missing, 2)

    def test_no_team_leaves_its_section_in_any_simulated_season(self) -> None:
        # City lead by a mile but sit in the bottom section; Albion and Borough have nothing.
        table = {team: {"points": points, "goalsFor": 0, "goalsAgainst": 0} for team, points in zip(self.TEAMS, (0, 0, 30, 3))}
        split = football_split.Split(size=2, sections={"Albion": 0, "Borough": 0, "City": 1, "Rovers": 1}, games=[], missing=0)
        model = football.GoalModel(mu=0.3, home=0.2, attack=dict.fromkeys(self.TEAMS, 0.0), defence=dict.fromkeys(self.TEAMS, 0.0))
        tiers = [{"key": "top2", "label": "Top 2", "kind": "top", "size": 2}, {"key": "last", "label": "Last", "kind": "bottom", "size": 1}]
        remaining = [Game("1", 4, KICKOFF, "Albion", "Borough", None, None, None), Game("2", 4, KICKOFF, "City", "Rovers", None, None, None)]

        result = football.simulate(model, self.TEAMS, table, remaining, tiers, {"win": 3, "draw": 1}, simulations=2000, split=split)

        self.assertEqual(result["positions"]["City"][:3], [0.0, 0.0, 100.0])
        self.assertEqual(result["probabilities"]["Rovers"]["last"], 100.0)
        self.assertEqual(result["probabilities"]["Albion"]["top2"], 100.0)

    def test_simulated_seasons_split_their_own_tables(self) -> None:
        # Albion 9 points, Borough and City 3 (City ahead on goal difference), Rovers 0; City v Rovers decides
        # second place before the split, so the sections differ from one simulated season to the next.
        scores = [(2, 0), (2, 0), (2, 0), (0, 2), (2, 0), (None, None)]
        games = [Game(game.id, 1, game.date, game.home, game.away, None, *score) for game, score in zip(round_robin(self.TEAMS, 1), scores)]
        split = football_split.plan(self.RULE, games, self.TEAMS, self.rank)
        self.assertEqual((split.sections, len(split.games), split.missing), (None, 6, 2))
        table = football.standings(games, self.TEAMS)
        model = football.GoalModel(mu=0.3, home=0.2, attack=dict.fromkeys(self.TEAMS, 0.0), defence=dict.fromkeys(self.TEAMS, 0.0))
        tiers = [{"key": "top2", "label": "Top 2", "kind": "top", "size": 2}]

        result = football.simulate(model, self.TEAMS, table, [games[-1]], tiers, {"win": 3, "draw": 1}, simulations=4000, split=split)

        top2 = {team: values["top2"] for team, values in result["probabilities"].items()}
        self.assertEqual(top2["Albion"], 100.0)
        self.assertGreater(top2["City"], top2["Borough"])
        self.assertGreater(top2["Borough"], 0.0)
        self.assertAlmostEqual(sum(top2.values()), 200.0, delta=0.05)
        # Three games in each season (City v Rovers and one post-split game per section), worth 2 or 3 points each.
        extra = sum(values["points"] for values in result["expected"].values()) - sum(row["points"] for row in table.values())
        self.assertTrue(6 - 0.3 <= extra <= 9 + 0.3, extra)
        self.assertEqual([item["fixtureId"] for item in result["matchesThatMatter"]], ["6"])


class TiebreakAndTierTests(unittest.TestCase):
    def test_scotland_uses_head_to_head_only_after_goals(self) -> None:
        teams = ["Albion", "Borough", "City", "Rovers"]
        # Three teams on 3 points: goal difference puts Borough first, although Albion beat them.
        games = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 1, 0),
            Game("2", 2, KICKOFF, "Borough", "City", None, 3, 0),
            Game("3", 3, KICKOFF, "Rovers", "Albion", None, 1, 0),
        ]
        rows = football.standings(games, teams)
        self.assertEqual(football.ranked(rows, games, "goals-then-head-to-head"), ["Borough", "Rovers", "Albion", "City"])
        self.assertEqual(football.ranked(rows, games, "head-to-head")[:3], ["Rovers", "Albion", "Borough"])
        # Albion and Borough level on points, goal difference and goals: Borough won the meeting.
        level = [
            Game("1", 1, KICKOFF, "Borough", "Albion", None, 2, 1),
            Game("2", 2, KICKOFF, "Albion", "City", None, 1, 0),
            Game("3", 3, KICKOFF, "Rovers", "Borough", None, 1, 0),
        ]
        rows = football.standings(level, teams)
        self.assertEqual(football.ranked(rows), ["Rovers", "Albion", "Borough", "City"])
        self.assertEqual(football.ranked(rows, level, "goals-then-head-to-head"), ["Rovers", "Borough", "Albion", "City"])

    def test_a_tier_can_skip_the_places_at_its_edge(self) -> None:
        positions = np.array([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]])
        playoff = team_sports.tier_flags(positions, {"kind": "bottom", "size": 1, "skip": 1}, 12)
        self.assertEqual(np.flatnonzero(playoff[0]).tolist(), [10])
        relegation = team_sports.tier_flags(positions, {"kind": "bottom", "size": 1}, 12)
        self.assertEqual(np.flatnonzero(relegation[0]).tolist(), [11])
        second_and_third = team_sports.tier_flags(positions, {"kind": "top", "size": 2, "skip": 1}, 12)
        self.assertEqual(np.flatnonzero(second_and_third[0]).tolist(), [1, 2])

    def test_the_config_is_valid(self) -> None:
        config = leagues.read_config("scottish-premiership")
        team_sports.validate_config(config)
        with self.assertRaisesRegex(ValueError, "split"):
            team_sports.validate_config(dict(config, split={"after": 33, "size": 1}))
        season = team_sports.resolve_season(config, datetime(2026, 7, 31, 20, tzinfo=timezone.utc))
        self.assertEqual((season.payload_id, season.feed), ("scottish-premiership-2026-27", "scottish-premiership-2026"))


if __name__ == "__main__":
    unittest.main()
