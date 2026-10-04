"""The A-Leagues on the football playoff engine (football_playoffs.py), checked against real seasons.

tests/fixtures/a-league-men-2025.json and a-league-men-2026.json hold FixtureDownload's feeds (the
2025-26 one lists the finals after the regular season) plus ESPN's finals and table in compact
form, so these tests run offline.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

import extract_table
import football_playoffs
import leagues
import team_sports
from team_sports import Game

FIXTURES = Path(__file__).parent / "fixtures"
UTC = timezone.utc


def raw_scoreboard(rows: list[list]) -> dict:
    """ESPN's scoreboard JSON (the fields the engine reads) from a fixture's compact rows."""
    events = []
    for date, slug, season_year, status, completed, home, away, home_score, away_score, home_pens, away_pens in rows:
        def side(where: str, team: str, score, pens) -> dict:
            item = {"homeAway": where, "team": {"displayName": team}, "score": "" if score is None else str(score)}
            if pens is not None:
                item["shootoutScore"] = pens
            return item

        events.append(
            {
                "date": date,
                "season": {"slug": slug, "year": season_year},
                "competitions": [
                    {
                        "status": {"type": {"name": status, "completed": completed, "state": "post" if completed else "pre"}},
                        "competitors": [side("home", home, home_score, home_pens), side("away", away, away_score, away_pens)],
                    }
                ],
            }
        )
    return {"events": events}


def raw_standings(rows: list[list]) -> dict:
    entries = []
    for rank, team, played, wins, draws, losses, goals_for, goals_against, points in rows:
        stats = dict(rank=rank, gamesPlayed=played, wins=wins, ties=draws, losses=losses, pointsFor=goals_for, pointsAgainst=goals_against, points=points)
        entries.append({"team": {"displayName": team}, "stats": [{"name": key, "value": float(value)} for key, value in stats.items()]})
    return {"children": [{"abbreviation": "A-League", "standings": {"entries": entries}}]}


def load(cache: Path, config: dict, year: int, as_of: datetime | None = None, espn: bool = True) -> None:
    """Write a season's fixture into a cache directory as the engine's downloads.

    ESPN's scoreboard is split by calendar year, as ESPN serves it. With ``as_of``, ESPN
    games after it are not played yet, and those more than a week later are not scheduled
    yet (ESPN lists a finals match once its teams are known).
    """
    league = config["id"]
    data = json.loads((FIXTURES / f"{league}-{year}.json").read_text(encoding="utf-8"))
    feed = [
        {"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score}
        for number, round_number, date, home, away, home_score, away_score in data["games"]
    ]
    (cache / f"{config['season']['feed'].format(year=year)}.json").write_text(json.dumps(feed), encoding="utf-8")
    if not espn:
        return
    code = config["sources"]["espn"]
    rows = data["espn"]
    if as_of:
        kept = []
        for row in rows:
            date = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            if date > as_of + timedelta(days=7):
                continue
            if date > as_of:
                row = row[:3] + ["STATUS_SCHEDULED", False] + row[5:7] + [None, None, None, None]
            kept.append(row)
        rows = kept
    for calendar_year in (year, year + 1):
        part = [row for row in rows if row[0].startswith(str(calendar_year))]
        scoreboard = football_playoffs.parse_scoreboard(raw_scoreboard(part))
        (cache / f"espn-{code}-scoreboard-{calendar_year}.json").write_text(json.dumps(scoreboard), encoding="utf-8")
    standings = football_playoffs.parse_standings(raw_standings(data["standings"]))
    (cache / f"espn-{code}-standings-{year}.json").write_text(json.dumps(standings), encoding="utf-8")


def build(config: dict, now: datetime, seasons: list[int], as_of: datetime | None = None, espn: bool = True) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        for year in seasons:
            load(cache, config, year, as_of=as_of, espn=espn)
        # Seasons without a fixture have no feed yet, as before 2023-24.
        previous = team_sports.resolve_season(config, now, offset=-1)
        path = cache / f"{previous.feed}.json"
        if not path.exists():
            path.write_text("[]", encoding="utf-8")
        return football_playoffs.build_payload(config, now, cache)


def ladder(payload: dict) -> list[tuple]:
    return [
        (row["shortName"], row["played"], row["wins"], row["draws"], row["losses"], row["goalsFor"], row["goalsAgainst"], row["points"])
        for row in payload["standings"]
    ]


def bracket_rows(payload: dict) -> dict[str, list[tuple]]:
    short = {row["teamKey"]: row["shortName"] for row in payload["standings"]}
    found = {}
    for item in payload["bracket"]["rounds"]:
        found[item["key"]] = [
            (
                short.get(series["top"]),
                short.get(series["bottom"]),
                series["topSeed"],
                series["bottomSeed"],
                (series["aggregate"]["top"], series["aggregate"]["bottom"]) if series.get("aggregate") else None,
                short.get(series["winner"]),
                series.get("note"),
            )
            for series in item["series"]
        ]
    return found


# Official ladder: club, played, won, drawn, lost, goals for, goals against, points.
# https://aleagues.com.au/ladders/a-league-men/2025-2026/ (final); ESPN's aus.1 table agrees.
OFFICIAL_MEN_2025 = [
    ("NEW", 26, 15, 3, 8, 55, 39, 48),
    ("ADE", 26, 12, 7, 7, 46, 36, 43),
    ("AKL", 26, 11, 9, 6, 42, 29, 42),
    ("MVC", 26, 11, 7, 8, 44, 33, 40),
    ("SYD", 26, 11, 6, 9, 33, 25, 39),
    ("MCY", 26, 10, 8, 8, 33, 33, 38),
    ("MAC", 26, 9, 7, 10, 37, 44, 34),
    ("WEL", 26, 9, 6, 11, 36, 48, 33),
    ("CCM", 26, 8, 8, 10, 35, 42, 32),
    ("PER", 26, 8, 7, 11, 32, 39, 31),
    ("BRI", 26, 6, 8, 12, 27, 36, 26),
    ("WSW", 26, 5, 6, 15, 27, 43, 21),
]

# The 2026 Finals Series (https://aleagues.com.au/isuzu-ute-a-league-men-finals-series-2026/; Grand Final:
# https://www.isuzuute.com.au/discover/news/a-league-grand-final-2026; Sydney through on penalties:
# https://www.flashscore.com/news/soccer-a-league-sydney-fc-edge-past-newcastle-jets-on-penalties-to-reach-a-league-grand-final/4lFS0bGD/):
# (higher-placed club, other club, their ladder places, goals (aggregate over both semi-final legs), winner, note).
OFFICIAL_MEN_FINALS_2025 = {
    "EF": [
        ("AKL", "MCY", 3, 6, (1, 1), "AKL", "7-6 on penalties"),
        ("MVC", "SYD", 4, 5, (0, 1), "SYD", None),
    ],
    # 1st plays the lower-ranked Elimination Final winner (5th), 2nd the higher-ranked (3rd).
    "SF": [
        ("NEW", "SYD", 1, 5, (2, 2), "SYD", "2-4 on penalties"),
        ("ADE", "AKL", 2, 3, (1, 4), "AKL", None),
    ],
    # Auckland, the higher-placed finalist, hosted the Grand Final at Go Media Stadium.
    "GF": [("AKL", "SYD", 3, 5, (1, 0), "AKL", None)],
}


class ALeagueMen2025Tests(unittest.TestCase):
    """The finished 2025-26 season, rebuilt from the aleague-men-2025 feed and ESPN's finals."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("a-league-men")
        cls.payload = build(cls.cfg, datetime(2026, 6, 10, tzinfo=UTC), [2025])

    def test_the_final_ladder_matches_the_official_one(self) -> None:
        self.assertEqual(ladder(self.payload), OFFICIAL_MEN_2025)

    def test_the_finals_in_the_feed_are_left_out_of_the_ladder(self) -> None:
        data = json.loads((FIXTURES / "a-league-men-2025.json").read_text(encoding="utf-8"))
        games = [Game(str(row[0]), row[1], datetime.fromisoformat(row[2].replace("Z", "+00:00")), row[3], row[4], None, row[5], row[6]) for row in data["games"]]
        regular, finals = football_playoffs.split_postseason(games, 6)
        self.assertEqual((len(regular), len(finals)), (156, 7))
        self.assertEqual({game.round for game in finals}, {27, 28, 29, 30})
        # FixtureDownload's finals agree with ESPN's, which also have the shoot-outs.
        aliases = self.cfg["aliases"]
        espn = {(aliases.get(row[5], row[5]), aliases.get(row[6], row[6])): (row[7], row[8]) for row in data["espn"]}
        self.assertEqual({(game.home, game.away): (game.home_score, game.away_score) for game in finals}, espn)

    def test_the_real_finals_are_reproduced(self) -> None:
        self.assertEqual(bracket_rows(self.payload), OFFICIAL_MEN_FINALS_2025)
        self.assertEqual([item["label"] for item in self.payload["bracket"]["rounds"]], ["Elimination Finals", "Semi-Finals", "Grand Final"])
        semis = self.payload["bracket"]["rounds"][1]["series"]
        self.assertEqual({series["bestOf"] for series in semis}, {2})

    def test_the_premiers_and_champions_are_settled(self) -> None:
        probabilities = self.payload["analysis"]["probabilities"]
        self.assertEqual(probabilities["Newcastle Jets"]["premiership"], 100.0)
        self.assertEqual(probabilities["Auckland"]["championship"], 100.0)
        self.assertEqual(probabilities["Auckland"]["top2"], 0.0)
        self.assertEqual(self.payload["bracket"]["champion"], "Auckland")
        self.assertEqual(self.payload["metadata"]["season_status"], "complete")
        self.assertTrue(all(tier.get("settled") for tier in self.payload["league"]["tiers"]))
        self.assertEqual(extract_table.index_entry(self.payload)["champion"], "AKL")

    def test_finals_results_carry_their_stage(self) -> None:
        notes = [item["note"] for item in self.payload["results"] if item["id"].startswith("playoff-result")]
        self.assertEqual(
            notes,
            [
                "Grand Final",
                "Semi-Finals, leg 2, 2-4 pens",
                "Semi-Finals, leg 2",
                "Semi-Finals, leg 1",
                "Semi-Finals, leg 1",
                "Elimination Finals",
                "Elimination Finals, 7-6 pens",
            ],
        )
        self.assertEqual(self.payload["fixtures"], [])

    def test_the_page_shows_one_ladder_with_the_finals_lines(self) -> None:
        league = self.payload["league"]
        self.assertEqual(league["id"], "a-league-men-2025-26")
        self.assertEqual(league["groups"], [])
        self.assertEqual(league["cutoffs"], [{"after": 2, "label": "Elimination finals"}, {"after": 6, "label": "Out"}])
        self.assertEqual(league["positionLabel"], "Ladder position")
        # One table: place and points, not an MLS-style record and conference seed.
        self.assertNotIn("record", self.payload["standings"][0])
        self.assertNotIn("seed", self.payload["standings"][0])
        self.assertEqual(self.payload["standings"][2]["fullName"], "Auckland FC")


class ALeagueMenMidFinalsTests(unittest.TestCase):
    """2025-26 on 10 May 2026: the Elimination Finals and both semi-final first legs played."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("a-league-men")
        as_of = datetime(2026, 5, 10, tzinfo=UTC)
        cls.payload = build(cls.cfg, as_of, [2025], as_of=as_of)

    def test_semi_finals_start_from_the_first_leg(self) -> None:
        rounds = bracket_rows(self.payload)
        self.assertEqual(rounds["EF"], OFFICIAL_MEN_FINALS_2025["EF"])
        self.assertEqual(rounds["SF"], [("NEW", "SYD", 1, 5, (1, 1), None, None), ("ADE", "AKL", 2, 3, (1, 1), None, None)])
        self.assertEqual(rounds["GF"], [(None, None, None, None, None, None, None)])
        self.assertEqual(self.payload["metadata"]["season_status"], "postseason")

    def test_title_odds_go_to_the_four_semi_finalists(self) -> None:
        title = {team: values["championship"] for team, values in self.payload["analysis"]["probabilities"].items()}
        self.assertAlmostEqual(sum(title.values()), 100, delta=0.05)
        self.assertEqual({team for team, value in title.items() if value > 0}, {"Newcastle Jets", "Adelaide United", "Auckland", "Sydney"})
        settled = {tier["key"] for tier in self.payload["league"]["tiers"] if tier.get("settled")}
        self.assertEqual(settled, {"finals", "top2", "premiership"})

    def test_the_second_legs_are_the_next_games(self) -> None:
        stages = [(fixture["home"], fixture["away"], fixture["stage"]) for fixture in self.payload["fixtures"]]
        self.assertEqual(stages, [("Adelaide United", "Auckland", "Semi-Finals, leg 2"), ("Newcastle Jets", "Sydney", "Semi-Finals, leg 2")])


class ALeagueMenPreseasonTests(unittest.TestCase):
    """2026-27 on 3 October 2026, before the first game: odds from last season's ratings."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("a-league-men")
        cls.payload = build(cls.cfg, datetime(2026, 10, 3, 12, tzinfo=UTC), [2026, 2025])

    def test_every_game_is_still_to_play(self) -> None:
        self.assertEqual(self.payload["league"]["id"], "a-league-men-2026-27")
        self.assertEqual(len(self.payload["fixtures"]), 156)
        self.assertEqual(self.payload["fixtures"][0]["home"], "Sydney")
        self.assertEqual(self.payload["fixtures"][0]["away"], "Western Sydney Wanderers")
        self.assertTrue(all(row["played"] == 0 for row in self.payload["standings"]))
        self.assertEqual(len(self.payload["standings"]), 12)
        self.assertEqual(self.payload["metadata"]["season_status"], "in_progress")
        self.assertEqual(self.payload["metadata"]["warnings"], [])
        self.assertNotIn("bracket", self.payload)
        team_sports.validate_config(self.cfg)

    def test_odds_add_up_to_the_places_on_offer(self) -> None:
        probabilities = self.payload["analysis"]["probabilities"]
        totals = {key: sum(values[key] for values in probabilities.values()) / 100 for key in ("finals", "top2", "premiership", "championship")}
        self.assertAlmostEqual(totals["finals"], 6, delta=0.01)
        self.assertAlmostEqual(totals["top2"], 2, delta=0.01)
        self.assertAlmostEqual(totals["premiership"], 1, delta=0.01)
        self.assertAlmostEqual(totals["championship"], 1, delta=0.01)
        for values in probabilities.values():
            self.assertLessEqual(values["championship"], values["finals"] + 1e-9)
            self.assertLessEqual(values["premiership"], values["top2"] + 1e-9)
            self.assertLessEqual(values["top2"], values["finals"] + 1e-9)
        # Every club is a real chance before a ball is kicked, with salary-cap parity.
        self.assertTrue(all(5 < values["finals"] < 95 for values in probabilities.values()))


# https://aleagues.com.au/ladders/a-league-women/2025-2026/ (final); ESPN's aus.w.1 table agrees.
# Sydney (4 wins) finish above Western Sydney (5 wins) on goal difference, which comes before wins.
OFFICIAL_WOMEN_2025 = [
    ("MCY", 20, 12, 4, 4, 36, 20, 40),
    ("WEL", 20, 10, 4, 6, 38, 17, 34),
    ("CAN", 20, 9, 4, 7, 30, 24, 31),
    ("BRI", 20, 9, 4, 7, 37, 39, 31),
    ("ADE", 20, 9, 3, 8, 24, 26, 30),
    ("MVC", 20, 8, 4, 8, 27, 24, 28),
    ("CCM", 20, 7, 7, 6, 27, 26, 28),
    ("PER", 20, 7, 3, 10, 20, 30, 24),
    ("NEW", 20, 7, 2, 11, 30, 36, 23),
    ("SYD", 20, 4, 7, 9, 18, 29, 19),
    ("WSW", 20, 5, 4, 11, 18, 34, 19),
]

# The 2026 Finals Series (https://aleagues.com.au/ninja-a-league-finals-series-2026/: Melbourne City champions;
# scores from ESPN's aus.w.1 scoreboard, which FixtureDownload's agree with).
OFFICIAL_WOMEN_FINALS_2025 = {
    "EF": [
        ("CAN", "MVC", 3, 6, (1, 3), "MVC", None),
        ("BRI", "ADE", 4, 5, (3, 0), "BRI", None),
    ],
    # Premiers Melbourne City play Victory (6th), the lower-ranked Elimination Final winner: the
    # semi-finals are reseeded, not 1 v the 4/5 winner.
    "SF": [
        ("MCY", "MVC", 1, 6, (2, 0), "MCY", None),
        ("WEL", "BRI", 2, 4, (3, 2), "WEL", "After extra time"),
    ],
    "GF": [("MCY", "WEL", 1, 2, (3, 1), "MCY", None)],
}


class ALeagueWomen2025Tests(unittest.TestCase):
    """The finished 2025-26 season, rebuilt from the aleague-women-2025 feed and ESPN's finals."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("a-league-women")
        cls.payload = build(cls.cfg, datetime(2026, 6, 10, tzinfo=UTC), [2025])

    def test_the_final_ladder_matches_the_official_one(self) -> None:
        self.assertEqual(ladder(self.payload), OFFICIAL_WOMEN_2025)

    def test_a_result_missing_from_the_feed_comes_from_espn(self) -> None:
        # FixtureDownload has no score for Newcastle Jets v Wellington Phoenix on 1 February 2026.
        data = json.loads((FIXTURES / "a-league-women-2025.json").read_text(encoding="utf-8"))
        self.assertIn([75, 15, "2026-02-01 06:00:00Z", "Newcastle Jets", "Wellington Phoenix", None, None], data["games"])
        result = next(item for item in self.payload["results"] if item["id"] == "75")
        self.assertEqual((result["home"], result["homeScore"], result["awayScore"], result["away"]), ("Newcastle Jets", 1, 5, "Wellington Phoenix"))
        self.assertEqual(self.payload["metadata"]["warnings"], ["Previous season unavailable (aleague-women-2024: the feed has no fixtures yet); ratings use this season only."])

    def test_the_real_finals_are_reproduced(self) -> None:
        self.assertEqual(bracket_rows(self.payload), OFFICIAL_WOMEN_FINALS_2025)
        self.assertEqual(self.payload["bracket"]["champion"], "Melbourne City")
        probabilities = self.payload["analysis"]["probabilities"]
        self.assertEqual(probabilities["Melbourne City"]["premiership"], 100.0)
        self.assertEqual(probabilities["Melbourne City"]["championship"], 100.0)
        self.assertEqual(self.payload["metadata"]["season_status"], "complete")
        self.assertEqual(extract_table.index_entry(self.payload)["champion"], "MCY")
        # ESPN pads some names ("Sydney FC ", "Western Sydney "); they are trimmed and mapped.
        self.assertEqual({row["teamKey"] for row in self.payload["standings"]}, set(self.cfg["teams"]) - {"Western United"})


class ALeagueWomenPreseasonTests(unittest.TestCase):
    """2026-27 on 3 October 2026, before the first game."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("a-league-women")
        cls.payload = build(cls.cfg, datetime(2026, 10, 3, 12, tzinfo=UTC), [2026, 2025])

    def test_every_game_is_still_to_play(self) -> None:
        self.assertEqual(self.payload["league"]["id"], "a-league-women-2026-27")
        self.assertEqual(len(self.payload["fixtures"]), 110)
        self.assertEqual(len(self.payload["standings"]), 11)
        self.assertIn(("Newcastle Jets", "Perth Glory"), {(item["home"], item["away"]) for item in self.payload["fixtures"][:2]})
        self.assertEqual(self.payload["metadata"]["season_status"], "in_progress")
        self.assertEqual(self.payload["metadata"]["warnings"], [])
        team_sports.validate_config(self.cfg)

    def test_odds_add_up_to_the_places_on_offer(self) -> None:
        probabilities = self.payload["analysis"]["probabilities"]
        totals = {key: sum(values[key] for values in probabilities.values()) / 100 for key in ("finals", "top2", "premiership", "championship")}
        self.assertEqual({key: round(value, 2) for key, value in totals.items()}, {"finals": 6, "top2": 2, "premiership": 1, "championship": 1})
        for values in probabilities.values():
            self.assertLessEqual(values["championship"], values["finals"] + 1e-9)
            self.assertLessEqual(values["premiership"], values["top2"] + 1e-9)
        # Last season's Grand Finalists start as favourites: Wellington (the best goal difference) and Melbourne City.
        favourites = sorted(probabilities, key=lambda team: -probabilities[team]["championship"])[:2]
        self.assertEqual(set(favourites), {"Wellington Phoenix", "Melbourne City"})


class ALeagueFailureTests(unittest.TestCase):
    def test_without_espn_the_ladder_still_builds_and_title_odds_wait(self) -> None:
        cfg = leagues.read_config("a-league-men")
        with mock.patch.object(team_sports, "get_json", side_effect=ConnectionError("down")):
            payload = build(cfg, datetime(2026, 6, 10, tzinfo=UTC), [2025], espn=False)
        self.assertIn("Playoff results unavailable", " ".join(payload["metadata"]["warnings"]))
        self.assertNotIn("championship", {tier["key"] for tier in payload["league"]["tiers"]})
        self.assertNotIn("bracket", payload)
        # The A-Leagues' own tiebreakers reproduce the official ladder without ESPN's.
        self.assertEqual(ladder(payload), OFFICIAL_MEN_2025)

    def test_a_scoreboard_year_that_fails_falls_back_to_its_last_copy(self) -> None:
        cfg = leagues.read_config("a-league-men")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load(cache, cfg, 2025)
            (cache / "aleague-men-2024.json").write_text("[]", encoding="utf-8")
            board = cache / "espn-aus.1-scoreboard-2026.json"
            old = time.time() - 24 * 3600
            os.utime(board, (old, old))
            with mock.patch.object(team_sports, "get_json", return_value={"sports": []}):
                payload = football_playoffs.build_payload(cfg, datetime(2026, 6, 10, tzinfo=UTC), cache)
        self.assertIn("ESPN could not be read (KeyError)", " ".join(payload["metadata"]["warnings"]))
        self.assertEqual(payload["bracket"]["champion"], "Auckland")


def game(home: str, away: str, home_score: int | None, away_score: int | None, day: int) -> Game:
    return Game(f"{home}-{away}-{day}", None, datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day), home, away, None, home_score, away_score)


class EngineTests(unittest.TestCase):
    """The pieces of football_playoffs.py the A-Leagues rely on."""

    def test_the_regular_season_is_each_clubs_first_games(self) -> None:
        # A top-six league: split_postseason is told six clubs reach the playoffs.
        clubs = [f"T{i:02d}" for i in range(1, 13)]
        # Twelve clubs meet once (eleven games each), then a top-six finals series and a Grand
        # Final whose second side is still a placeholder.
        schedule = [(home, away) for i, home in enumerate(clubs) for away in clubs[i + 1 :]]
        games = [game(home, away, 1, 0, day) for day, (home, away) in enumerate(schedule)]
        finals = [
            game(home, away, 1, 1, day)
            for day, (home, away) in enumerate(
                [("T03", "T06"), ("T04", "T05"), ("T06", "T01"), ("T04", "T02"), ("T01", "T06"), ("T02", "T04")], start=100
            )
        ] + [game("T01", "To be announced", None, None, 110)]
        regular, rest = football_playoffs.split_postseason(games + finals, 6)
        self.assertEqual(regular, games)
        self.assertEqual(rest, finals)
        # Before the finals are listed, every game is regular.
        self.assertEqual(football_playoffs.split_postseason(games, 6), (games, []))
        # A club one game short (a match missing from the feed) does not push others' last games out.
        short = [item for item in games if (item.home, item.away) != ("T11", "T12")]
        self.assertEqual(football_playoffs.split_postseason(short + finals, 6), (short, finals))

    def test_per_game_tiebreakers_divide_by_games_played(self) -> None:
        base = {"points": 10, "wins": 3, "goalDifference": 2, "goalsFor": 6, "homeGoalsFor": 3, "homeGoalsAgainst": 2, "homePlayed": 3}
        # Level on away goal difference; Fewer has scored fewer away goals but in fewer away games.
        rows = {
            "More": dict(base, awayGoalsFor=4, awayGoalsAgainst=4, awayPlayed=4),
            "Fewer": dict(base, awayGoalsFor=3, awayGoalsAgainst=3, awayPlayed=2),
        }
        group = {"More": "L", "Fewer": "L"}
        self.assertEqual(football_playoffs.rank_teams(["More", "Fewer"], rows, [], ["away-goal-difference", "away-goals"], group), ["More", "Fewer"])
        self.assertEqual(football_playoffs.rank_teams(["More", "Fewer"], rows, [], ["away-goal-difference", "away-goals-per-game"], group), ["Fewer", "More"])
        table = football_playoffs.table_rows([game("A", "B", 2, 1, 1), game("B", "A", 0, 0, 2), game("A", "B", 3, 0, 3)], ["A", "B"], {"win": 3, "draw": 1})
        self.assertEqual((table["A"]["homePlayed"], table["A"]["awayPlayed"], table["B"]["awayPlayed"]), (2, 1, 2))

    def test_a_second_leg_is_where_the_first_was_not(self) -> None:
        rounds = football_playoffs.parse_rounds({"id": "toy", "shortName": "Toy", "playoffs": {"rounds": [{"key": "F", "label": "F", "match": "two-legged", "pairs": [[1, 2]]}]}})
        tie = rounds[0]
        SimGame = football_playoffs.SimGame
        sims, count = 20_000, 2
        seeds = {"League": np.broadcast_to(np.arange(count), (sims, count))}
        zeros = np.zeros((sims, count))

        def top_through(first_leg: SimGame) -> float:
            bracket = football_playoffs.Bracket(np.random.default_rng(3), np.log(1.3), 0.4, zeros, zeros, seeds, seeds["League"], seeds["League"], {frozenset((0, 1)): [first_leg]})
            _, champion = bracket.run(rounds)
            return float((champion == 0).mean())

        # A goalless first leg at the lower seed's ground leaves the higher seed at home for the second...
        self.assertGreater(top_through(SimGame(1, 0, 0, 0, None)), 0.55)
        # ...but if the higher seed chose to host the first leg, the second is away, and it is the underdog.
        self.assertLess(top_through(SimGame(0, 1, 0, 0, None)), 0.45)
        state = football_playoffs.real_state(tie, 0, 1, [SimGame(0, 1, 2, 1, 0)])
        self.assertEqual((state["firstLeg"], state["firstLegAtTop"]), ((2, 1), True))

    def test_a_season_across_new_year_reads_both_scoreboards(self) -> None:
        rows = [
            ["2025-05-31T09:40Z", "grand-final", 2024, "STATUS_FULL_TIME", True, "Melbourne City FC", "Melbourne Victory", 1, 0, None, None],
            ["2025-10-17T08:00Z", "regular-season", 2025, "STATUS_FULL_TIME", True, "Adelaide United ", "Sydney FC ", 2, 1, None, None],
            ["2026-05-23T08:10Z", "grand-final", 2025, "STATUS_FULL_TIME", True, "Auckland FC", "Sydney FC", 1, 0, None, None],
            ["2026-10-16T09:00Z", "regular-season", 2026, "STATUS_SCHEDULED", False, "Sydney FC", "Western Sydney Wanderers", None, None, None, None],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            for year in (2025, 2026):
                part = football_playoffs.parse_scoreboard(raw_scoreboard([row for row in rows if row[0].startswith(str(year))]))
                (cache / f"espn-aus.1-scoreboard-{year}.json").write_text(json.dumps(part), encoding="utf-8")
            aliases = {"Sydney FC": "Sydney", "Auckland FC": "Auckland"}
            matches, warning = football_playoffs.fetch_espn_matches("aus.1", 2025, cache, aliases, span=2)
            calendar, _ = football_playoffs.fetch_espn_matches("aus.1", 2025, cache, aliases)
        self.assertIsNone(warning)
        # 2025-26 only, from both calendar years, with ESPN's padded names trimmed.
        self.assertEqual([(match.home, match.away, match.season) for match in matches], [("Adelaide United", "Sydney", "regular-season"), ("Auckland", "Sydney", "grand-final")])
        # One calendar year is the whole season for MLS.
        self.assertEqual(len(calendar), 2)

    def test_the_config_bracket_reseeds_the_semi_finals(self) -> None:
        cfg = copy.deepcopy(leagues.read_config("a-league-men"))
        rounds = football_playoffs.parse_rounds(cfg)
        self.assertEqual(football_playoffs.qualifiers(rounds), 6)
        self.assertEqual([(item.key, item.match, item.reseed) for item in rounds], [("EF", "single", False), ("SF", "two-legged", True), ("GF", "single", False)])
        teams = [f"T{i}" for i in range(1, 7)]
        played = [
            football_playoffs.EspnMatch(datetime(2026, 5, 2, tzinfo=UTC), home, away, home_score, away_score, None, None, True, "post", False, "elimination-finals")
            for home, away, home_score, away_score in [("T3", "T6", 0, 1), ("T4", "T5", 2, 0)]
        ]
        bracket = football_playoffs.real_bracket(rounds, {"League": teams}, teams, played, {})
        # 1st plays the lowest-ranked winner (6th), 2nd the highest (4th).
        self.assertEqual([(series["top"], series["bottom"]) for series in bracket["rounds"][1]["series"]], [("T1", "T6"), ("T2", "T4")])


if __name__ == "__main__":
    unittest.main()
