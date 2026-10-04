"""The football playoff engine (football_playoffs.py) and MLS, checked against real seasons.

tests/fixtures/mls-2025.json and mls-2026.json hold FixtureDownload's regular season plus
ESPN's scoreboard and standings in compact form, so these tests run offline.
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
import football
import football_playoffs
import leagues
import team_sports
from team_sports import Game

FIXTURES = Path(__file__).parent / "fixtures"
UTC = timezone.utc


def raw_scoreboard(rows: list[list]) -> dict:
    """ESPN's scoreboard JSON (the fields the engine reads) from a fixture's compact rows."""
    events = []
    for date, slug, status, completed, home, away, home_score, away_score, home_pens, away_pens in rows:
        def side(where: str, team: str, score, pens) -> dict:
            item = {"homeAway": where, "team": {"displayName": team}, "score": "" if score is None else str(score)}
            if pens is not None:
                item["shootoutScore"] = pens
            return item

        events.append(
            {
                "date": date,
                "season": {"slug": slug},
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
    children = {}
    for group, rank, team, played, wins, draws, losses, goals_for, goals_against, points in rows:
        stats = dict(rank=rank, gamesPlayed=played, wins=wins, ties=draws, losses=losses, pointsFor=goals_for, pointsAgainst=goals_against, points=points)
        children.setdefault(group, []).append({"team": {"displayName": team}, "stats": [{"name": key, "value": float(value)} for key, value in stats.items()]})
    return {"children": [{"abbreviation": group, "standings": {"entries": entries}} for group, entries in children.items()]}


def load_mls(cache: Path, year: int, as_of: datetime | None = None, espn: bool = True) -> None:
    """Write a season's fixture into a cache directory as the engine's downloads.

    With ``as_of``, ESPN games after it are not played yet, and those more than a week
    later are not scheduled yet (as ESPN lists playoff games once the matchup is known).
    """
    data = json.loads((FIXTURES / f"mls-{year}.json").read_text(encoding="utf-8"))
    feed = [
        {"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score}
        for number, round_number, date, home, away, home_score, away_score in data["games"]
    ]
    (cache / f"mls-{year}.json").write_text(json.dumps(feed), encoding="utf-8")
    if not espn:
        return
    rows = data["espn"]
    if as_of:
        kept = []
        for row in rows:
            date = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            if date > as_of + timedelta(days=7):
                continue
            if date > as_of:
                row = [row[0], row[1], "STATUS_SCHEDULED", False, row[4], row[5], None, None, None, None]
            kept.append(row)
        rows = kept
    scoreboard = football_playoffs.parse_scoreboard(raw_scoreboard(rows))
    (cache / f"espn-usa.1-scoreboard-{year}.json").write_text(json.dumps(scoreboard), encoding="utf-8")
    standings = football_playoffs.parse_standings(raw_standings(data["standings"]))
    (cache / f"espn-usa.1-standings-{year}.json").write_text(json.dumps(standings), encoding="utf-8")


def conference_table(payload: dict, group: str) -> list[tuple]:
    rows = {row["teamKey"]: row for row in payload["standings"]}
    members = next(item["teams"] for item in payload["league"]["groups"] if item["key"] == group)
    return [
        (rows[team]["shortName"], rows[team]["played"], rows[team]["wins"], rows[team]["losses"], rows[team]["draws"], rows[team]["goalsFor"], rows[team]["goalsAgainst"], rows[team]["points"])
        for team in members
    ]


# Official conference standings: club, played, wins, losses, ties, goals for, goals against, points.
OFFICIAL_MLS = {
    # https://www.mlssoccer.com/standings/2026/conference (3 October 2026, after Seattle 2-1 Sporting KC
    # on 1 October); ESPN's https://site.api.espn.com/apis/v2/sports/soccer/usa.1/standings agrees.
    2026: {
        "East": [
            ("NSH", 27, 18, 3, 6, 55, 21, 60), ("NE", 27, 14, 9, 4, 45, 36, 46), ("MIA", 27, 12, 5, 10, 64, 50, 46),
            ("CLT", 27, 12, 8, 7, 47, 38, 43), ("CHI", 26, 12, 8, 6, 46, 38, 42), ("PHI", 27, 11, 10, 6, 54, 44, 39),
            ("ORL", 27, 10, 13, 4, 48, 64, 34), ("RBNY", 27, 9, 12, 6, 34, 51, 33), ("NYC", 27, 8, 10, 9, 41, 36, 33),
            ("CIN", 26, 8, 9, 9, 55, 64, 33), ("DC", 26, 6, 8, 12, 34, 42, 30), ("CLB", 27, 8, 14, 5, 39, 43, 29),
            ("TOR", 27, 6, 10, 11, 39, 51, 29), ("ATL", 27, 7, 14, 6, 32, 45, 27), ("MTL", 27, 6, 15, 6, 34, 54, 24),
        ],
        "West": [
            ("VAN", 26, 15, 6, 5, 59, 26, 50), ("STL", 27, 13, 6, 8, 48, 36, 47), ("DAL", 27, 13, 6, 8, 50, 42, 47),
            ("SJ", 27, 13, 8, 6, 49, 39, 45), ("HOU", 27, 13, 9, 5, 34, 32, 44), ("LAFC", 28, 11, 9, 8, 43, 30, 41),
            ("SEA", 27, 10, 9, 8, 35, 35, 38), ("COL", 27, 11, 13, 3, 38, 38, 36), ("LA", 28, 9, 10, 9, 37, 44, 36),
            ("POR", 27, 9, 13, 5, 48, 51, 32), ("RSL", 27, 9, 13, 5, 40, 44, 32), ("SD", 27, 8, 11, 8, 47, 47, 32),
            ("ATX", 27, 7, 10, 10, 35, 47, 31), ("MIN", 27, 7, 12, 8, 40, 49, 29), ("SKC", 27, 6, 18, 3, 32, 65, 21),
        ],
    },
    # https://www.mlssoccer.com/standings/2025/conference (final; season selector set to 2025)
    2025: {
        "East": [
            ("PHI", 34, 20, 8, 6, 57, 35, 66), ("CIN", 34, 20, 9, 5, 52, 40, 65), ("MIA", 34, 19, 7, 8, 81, 55, 65),
            ("CLT", 34, 19, 13, 2, 55, 46, 59), ("NYC", 34, 17, 12, 5, 50, 44, 56), ("NSH", 34, 16, 12, 6, 58, 45, 54),
            ("CLB", 34, 14, 8, 12, 55, 51, 54), ("CHI", 34, 15, 11, 8, 68, 60, 53), ("ORL", 34, 14, 9, 11, 63, 51, 53),
            ("RBNY", 34, 12, 15, 7, 48, 47, 43), ("NE", 34, 9, 16, 9, 44, 51, 36), ("TOR", 34, 6, 14, 14, 37, 44, 32),
            ("MTL", 34, 6, 18, 10, 34, 60, 28), ("ATL", 34, 5, 16, 13, 38, 63, 28), ("DC", 34, 5, 18, 11, 30, 66, 26),
        ],
        "West": [
            ("SD", 34, 19, 9, 6, 64, 41, 63), ("VAN", 34, 18, 7, 9, 66, 38, 63), ("LAFC", 34, 17, 8, 9, 65, 40, 60),
            ("MIN", 34, 16, 8, 10, 56, 39, 58), ("SEA", 34, 15, 9, 10, 58, 48, 55), ("ATX", 34, 13, 13, 8, 37, 45, 47),
            ("DAL", 34, 11, 12, 11, 52, 55, 44), ("POR", 34, 11, 12, 11, 41, 48, 44), ("RSL", 34, 12, 17, 5, 38, 49, 41),
            ("SJ", 34, 11, 15, 8, 60, 63, 41), ("COL", 34, 11, 15, 8, 44, 56, 41), ("HOU", 34, 9, 15, 10, 43, 56, 37),
            ("STL", 34, 8, 18, 8, 44, 58, 32), ("LA", 34, 7, 18, 9, 46, 66, 30), ("SKC", 34, 7, 20, 7, 46, 70, 28),
        ],
    },
}

# The Audi 2025 MLS Cup Playoffs, from https://www.mlssoccer.com/playoffs/2025/news/who-s-left-audi-2025-mls-cup-playoffs-teams-matchups-results
# and https://www.mlssoccer.com/playoffs/2025/news/champions-inter-miami-lionel-messi-win-mls-cup-over-vancouver-whitecaps:
# (higher seed, lower seed, their seeds, series wins or goals, winner, note).
OFFICIAL_BRACKET_2025 = {
    "WC": [
        ("CHI", "ORL", 8, 9, (3, 1), "CHI", None),
        ("POR", "RSL", 8, 9, (3, 1), "POR", None),
    ],
    "R1": [
        ("PHI", "CHI", 1, 8, (2, 0), "PHI", "2-2 (4-2 pens), 3-0"),
        ("CLT", "NYC", 4, 5, (1, 2), "NYC", "0-1, 0-0 (7-6 pens), 1-3"),
        ("CIN", "CLB", 2, 7, (2, 1), "CIN", "1-0, 0-4, 2-1"),
        ("MIA", "NSH", 3, 6, (2, 1), "MIA", "3-1, 1-2, 4-0"),
        ("SD", "POR", 1, 8, (2, 1), "SD", "2-1, 2-2 (2-3 pens), 4-0"),
        ("MIN", "SEA", 4, 5, (2, 1), "MIN", "0-0 (3-2 pens), 2-4, 3-3 (7-6 pens)"),
        ("VAN", "DAL", 2, 7, (2, 0), "VAN", "3-0, 1-1 (4-2 pens)"),
        ("LAFC", "ATX", 3, 6, (2, 0), "LAFC", "2-1, 4-1"),
    ],
    "CSF": [
        ("PHI", "NYC", 1, 5, (0, 1), "NYC", None),
        ("CIN", "MIA", 2, 3, (0, 4), "MIA", None),
        ("SD", "MIN", 1, 4, (1, 0), "SD", None),
        ("VAN", "LAFC", 2, 3, (2, 2), "VAN", "4-3 on penalties"),
    ],
    "CF": [
        ("MIA", "NYC", 3, 5, (5, 1), "MIA", None),
        ("SD", "VAN", 1, 2, (1, 3), "VAN", None),
    ],
    # MLS Cup at Chase Stadium: Miami finished above Vancouver in the Supporters' Shield standings.
    "F": [("MIA", "VAN", 3, 2, (3, 1), "MIA", None)],
}


def bracket_rows(payload: dict) -> dict[str, list[tuple]]:
    short = {row["teamKey"]: row["shortName"] for row in payload["standings"]}
    found = {}
    for item in payload["bracket"]["rounds"]:
        found[item["key"]] = [
            (
                short[series["top"]],
                short[series["bottom"]],
                series["topSeed"],
                series["bottomSeed"],
                (series["aggregate"]["top"], series["aggregate"]["bottom"]) if "aggregate" in series else (series["topWins"], series["bottomWins"]),
                short[series["winner"]],
                series.get("note"),
            )
            for series in item["series"]
        ]
    return found


class MlsLiveTests(unittest.TestCase):
    """The 2026 regular season on 3 October 2026: 404 of 510 games played."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("mls")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load_mls(cache, 2026)
            load_mls(cache, 2025)
            cls.payload = football_playoffs.build_payload(cls.cfg, datetime(2026, 10, 3, 12, tzinfo=UTC), cache)

    def test_the_conference_tables_match_the_official_standings(self) -> None:
        # Level teams are split by wins before goal difference (New England above Miami,
        # Red Bull New York above New York City and Cincinnati, Colorado above LA Galaxy).
        for group in ("East", "West"):
            self.assertEqual(conference_table(self.payload, group), OFFICIAL_MLS[2026][group], group)

    def test_wrong_fixturedownload_scores_are_corrected_from_espn(self) -> None:
        note = next(note for note in self.payload["analysis"]["modelNotes"] if "FixtureDownload score" in note)
        self.assertIn("3 FixtureDownload scores differ", note)
        self.assertIn("LA Galaxy 1-3 St. Louis City SC on 22 Jul (not 3-1)", note)
        self.assertIn("LAFC 3-1 Real Salt Lake on 22 Jul (not 1-3)", note)
        self.assertIn("Orlando City 1-2 Chicago Fire on 19 Aug (not 1-0)", note)
        result = next(item for item in self.payload["results"] if item["id"] == "291")
        self.assertEqual((result["home"], result["homeScore"], result["awayScore"], result["away"]), ("Orlando City", 1, 2, "Chicago Fire FC"))

    def test_the_league_table_is_the_supporters_shield_race(self) -> None:
        ranks = [row["shortName"] for row in self.payload["standings"]][:6]
        self.assertEqual(ranks, ["NSH", "VAN", "STL", "DAL", "NE", "MIA"])
        nashville = self.payload["standings"][0]
        self.assertEqual((nashville["record"], nashville["seed"], nashville["conference"]), ("18-3-6", 1, "East"))

    def test_odds_add_up_to_the_places_on_offer(self) -> None:
        probabilities = self.payload["analysis"]["probabilities"]
        totals = {key: sum(values[key] for values in probabilities.values()) / 100 for key in ("playoffs", "top7", "shield", "cup")}
        self.assertAlmostEqual(totals["playoffs"], 18, delta=0.01)
        self.assertAlmostEqual(totals["top7"], 14, delta=0.01)
        self.assertAlmostEqual(totals["shield"], 1, delta=0.01)
        self.assertAlmostEqual(totals["cup"], 1, delta=0.01)
        # Nashville have clinched a playoff place ("x" on mlssoccer.com) and lead the Shield race by ten points.
        self.assertEqual(probabilities["Nashville SC"]["playoffs"], 100.0)
        self.assertGreater(probabilities["Nashville SC"]["shield"], 80)
        for values in probabilities.values():
            self.assertLessEqual(values["cup"], values["playoffs"] + 1e-9)
            self.assertLessEqual(values["top7"], values["playoffs"] + 1e-9)

    def test_the_page_shows_conference_tables_with_playoff_lines(self) -> None:
        league = self.payload["league"]
        self.assertEqual(league["id"], "mls-2026")
        self.assertEqual([group["label"] for group in league["groups"]], ["East", "West"])
        self.assertEqual(league["groups"][0]["cutoffs"], [{"after": 7, "label": "Wild Card"}, {"after": 9, "label": "Out"}])
        self.assertEqual((league["rankLabel"], league["positionLabel"]), ("Overall", "Conference position"))
        self.assertEqual(len(self.payload["analysis"]["positions"]["Nashville SC"]), 15)
        self.assertEqual(self.payload["metadata"]["season_status"], "in_progress")
        self.assertNotIn("bracket", self.payload)
        self.assertEqual(len(self.payload["fixtures"]), 106)
        self.assertTrue(self.payload["matchesThatMatter"])
        self.assertEqual(self.payload["metadata"]["warnings"], [])
        team_sports.validate_config(self.cfg)


class Mls2025Tests(unittest.TestCase):
    """The finished 2025 season, rebuilt from the mls-2025 feed and ESPN's playoff games."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("mls")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load_mls(cache, 2025)
            (cache / "mls-2024.json").write_text("[]", encoding="utf-8")
            cls.payload = football_playoffs.build_payload(cls.cfg, datetime(2025, 12, 20, tzinfo=UTC), cache)

    def test_the_final_tables_match_the_official_standings(self) -> None:
        # Cincinnati above Miami and San Diego above Vancouver on wins; Dallas above Portland on goal difference.
        for group in ("East", "West"):
            self.assertEqual(conference_table(self.payload, group), OFFICIAL_MLS[2025][group], group)

    def test_the_real_bracket_is_reproduced(self) -> None:
        self.assertEqual(bracket_rows(self.payload), OFFICIAL_BRACKET_2025)
        rounds = {item["key"]: item for item in self.payload["bracket"]["rounds"]}
        self.assertEqual([item["label"] for item in self.payload["bracket"]["rounds"]], ["Wild Card", "Round One", "Conference Semifinals", "Conference Final", "MLS Cup"])
        self.assertEqual({series["bestOf"] for series in rounds["R1"]["series"]}, {3})
        self.assertNotIn("aggregate", rounds["R1"]["series"][0])
        self.assertEqual([series["conference"] for series in rounds["CF"]["series"]], ["East", "West"])

    def test_the_champion_is_named_and_every_race_is_settled(self) -> None:
        self.assertEqual(self.payload["bracket"]["champion"], "Inter Miami CF")
        self.assertEqual(self.payload["playoffs"], {"champion": "Inter Miami CF"})
        self.assertEqual(self.payload["metadata"]["season_status"], "complete")
        self.assertTrue(all(tier.get("settled") for tier in self.payload["league"]["tiers"]))
        probabilities = self.payload["analysis"]["probabilities"]
        self.assertEqual(probabilities["Inter Miami CF"]["cup"], 100.0)
        self.assertEqual(probabilities["Philadelphia Union"]["shield"], 100.0)
        self.assertEqual(extract_table.index_entry(self.payload)["champion"], "MIA")

    def test_playoff_results_carry_their_round(self) -> None:
        # 30 games: ESPN's three cancelled "if necessary" Round One games are left out.
        notes = [item["note"] for item in self.payload["results"] if item["id"].startswith("playoff-result")]
        self.assertEqual(len(notes), 30)
        self.assertEqual(notes[0], "MLS Cup")
        self.assertIn("Conference Semifinals, 4-3 pens", notes)
        self.assertIn("Round One, game 3, 7-6 pens", notes)
        self.assertEqual(self.payload["fixtures"], [])


class MlsMidPlayoffsTests(unittest.TestCase):
    """2025 on 4 November: two Round One series decided, the rest level or under way."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("mls")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load_mls(cache, 2025, as_of=datetime(2025, 11, 4, tzinfo=UTC))
            (cache / "mls-2024.json").write_text("[]", encoding="utf-8")
            cls.payload = football_playoffs.build_payload(cls.cfg, datetime(2025, 11, 4, tzinfo=UTC), cache)

    def test_series_under_way_start_from_their_real_score(self) -> None:
        first ={(series["top"], series["bottom"]): (series["topWins"], series["bottomWins"], series["winner"]) for series in self.payload["bracket"]["rounds"][1]["series"]}
        self.assertEqual(first[("Philadelphia Union", "Chicago Fire FC")], (2, 0, "Philadelphia Union"))
        self.assertEqual(first[("Minnesota United FC", "Seattle Sounders FC")], (1, 0, None))
        self.assertEqual(first[("FC Cincinnati", "Columbus Crew")], (1, 1, None))
        semis = self.payload["bracket"]["rounds"][2]["series"]
        self.assertEqual((semis[0]["top"], semis[0]["bottom"]), ("Philadelphia Union", None))
        self.assertEqual(self.payload["metadata"]["season_status"], "postseason")

    def test_title_odds_go_to_teams_still_in(self) -> None:
        cup = {team: values["cup"] for team, values in self.payload["analysis"]["probabilities"].items()}
        self.assertAlmostEqual(sum(cup.values()), 100, delta=0.05)
        out = {"Chicago Fire FC", "Orlando City", "Real Salt Lake", "FC Dallas", "Austin FC", "Red Bull New York"}
        self.assertTrue(all(cup[team] == 0 for team in out))
        alive = {team for team, value in cup.items() if value > 0}
        self.assertEqual(len(alive), 13)
        settled = {tier["key"] for tier in self.payload["league"]["tiers"] if tier.get("settled")}
        self.assertEqual(settled, {"playoffs", "top7", "shield"})

    def test_upcoming_games_skip_decided_series(self) -> None:
        stages = [(fixture["home"], fixture["away"], fixture["stage"]) for fixture in self.payload["fixtures"]]
        self.assertIn(("Seattle Sounders FC", "Minnesota United FC", "Round One, game 2"), stages)
        self.assertIn(("Charlotte FC", "New York City Football Club", "Round One, game 3"), stages)
        self.assertFalse(any("Philadelphia Union" in (home, away) for home, away, _ in stages))
        self.assertEqual(self.payload["fixtures"][0]["stage"], "Round One, game 2")


class FailureTests(unittest.TestCase):
    def test_without_espn_the_table_still_builds_and_title_odds_wait(self) -> None:
        cfg = leagues.read_config("mls")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(team_sports, "get_json", side_effect=ConnectionError("down")):
            cache = Path(tmp)
            load_mls(cache, 2025, espn=False)
            (cache / "mls-2024.json").write_text("[]", encoding="utf-8")
            payload = football_playoffs.build_payload(cfg, datetime(2025, 12, 20, tzinfo=UTC), cache)
        self.assertIn("Playoff results unavailable", " ".join(payload["metadata"]["warnings"]))
        self.assertNotIn("cup", {tier["key"] for tier in payload["league"]["tiers"]})
        self.assertNotIn("bracket", payload)
        self.assertEqual(payload["metadata"]["season_status"], "postseason")
        # MLS's own tiebreakers reproduce the official order without ESPN's table.
        for group in ("East", "West"):
            self.assertEqual(conference_table(payload, group), OFFICIAL_MLS[2025][group], group)

    def test_a_changed_scoreboard_falls_back_to_the_last_copy(self) -> None:
        cfg = leagues.read_config("mls")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load_mls(cache, 2025)
            (cache / "mls-2024.json").write_text("[]", encoding="utf-8")
            board = cache / "espn-usa.1-scoreboard-2025.json"
            old = time.time() - 24 * 3600
            os.utime(board, (old, old))
            with mock.patch.object(team_sports, "get_json", return_value={"sports": []}):
                payload = football_playoffs.build_payload(cfg, datetime(2025, 12, 20, tzinfo=UTC), cache)
        self.assertIn("ESPN could not be read (KeyError)", " ".join(payload["metadata"]["warnings"]))
        self.assertEqual(payload["bracket"]["champion"], "Inter Miami CF")

    def test_an_unknown_team_names_the_config_to_fix(self) -> None:
        cfg = copy.deepcopy(leagues.read_config("mls"))
        del cfg["teams"]["San Diego FC"]
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            load_mls(cache, 2025, espn=False)
            (cache / "mls-2024.json").write_text("[]", encoding="utf-8")
            with mock.patch.object(team_sports, "get_json", side_effect=ConnectionError("down")):
                with self.assertRaisesRegex(team_sports.FeedError, "San Diego FC has no conference"):
                    football_playoffs.build_payload(cfg, datetime(2025, 12, 20, tzinfo=UTC), cache)


def game(home: str, away: str, home_score: int | None, away_score: int | None, day: int = 1) -> Game:
    return Game(f"{home}-{away}-{day}", None, datetime(2026, 3, day, tzinfo=UTC), home, away, None, home_score, away_score)


class TableTests(unittest.TestCase):
    def test_home_and_away_goals_are_split(self) -> None:
        games = [game("A", "B", 3, 1, 1), game("B", "A", 2, 2, 2), game("A", "B", None, None, 3)]
        rows = football_playoffs.table_rows(games, ["A", "B"], {"win": 3, "draw": 1})
        self.assertEqual((rows["A"]["points"], rows["A"]["wins"], rows["A"]["goalDifference"]), (4, 1, 2))
        self.assertEqual((rows["A"]["homeGoalsFor"], rows["A"]["awayGoalsFor"], rows["B"]["awayGoalsAgainst"]), (3, 2, 3))

    def test_more_wins_beat_a_better_goal_difference(self) -> None:
        rows = {
            "Wins": {"points": 10, "wins": 3, "goalDifference": 0, "goalsFor": 5},
            "Goals": {"points": 10, "wins": 2, "goalDifference": 9, "goalsFor": 12},
        }
        order = football_playoffs.rank_teams(["Goals", "Wins"], rows, [], ["wins", "goal-difference", "goals-for"], {"Wins": "E", "Goals": "E"})
        self.assertEqual(order, ["Wins", "Goals"])

    def test_head_to_head_only_separates_teams_of_one_conference(self) -> None:
        base = {"points": 10, "wins": 3, "goalDifference": 2, "goalsFor": 6, "homeGoalsFor": 3, "homeGoalsAgainst": 2, "awayGoalsFor": 3, "awayGoalsAgainst": 2}
        rows = {"Beta": dict(base), "Alpha": dict(base)}
        games = [game("Beta", "Alpha", 2, 0)]
        steps = ["wins", "goal-difference", "goals-for", "head-to-head"]
        self.assertEqual(football_playoffs.rank_teams(["Alpha", "Beta"], rows, games, steps, {"Alpha": "E", "Beta": "E"}), ["Beta", "Alpha"])
        self.assertEqual(football_playoffs.rank_teams(["Alpha", "Beta"], rows, games, steps, {"Alpha": "E", "Beta": "W"}), ["Alpha", "Beta"])

    def test_the_league_table_keeps_each_conference_order(self) -> None:
        base = {"points": 10, "wins": 3, "goalDifference": 2, "goalsFor": 6, "homeGoalsFor": 3, "homeGoalsAgainst": 2, "awayGoalsFor": 3, "awayGoalsAgainst": 2}
        rows = {"Alpha": dict(base), "Beta": dict(base, awayGoalsFor=5)}
        # The official order put Alpha first (fewer disciplinary points, say), although Beta scored more away.
        order = football_playoffs.rank_teams(["Alpha", "Beta"], rows, [], ["wins", "away-goals"], {"Alpha": "E", "Beta": "E"}, fallback={"Alpha": 0, "Beta": 1})
        self.assertEqual(order, ["Alpha", "Beta"])

    def test_the_official_order_and_deductions_come_from_matching_records(self) -> None:
        record = {"played": 2, "wins": 1, "draws": 0, "losses": 1, "goalsFor": 2, "goalsAgainst": 2}
        rows = {"A": dict(record, points=3), "B": dict(record, points=3)}
        official = [dict(record, team="B", rank=1, points=3), dict(record, team="A", rank=2, points=0)]
        order, adjustments = football_playoffs.official_order(rows, official, {"East": ["A", "B"]})
        self.assertEqual(order, {"East": ["B", "A"]})
        self.assertEqual(adjustments, {"A": -3})
        official[0]["wins"] = 2
        self.assertEqual(football_playoffs.official_order(rows, official, {"East": ["A", "B"]}), (None, {}))

    def test_espn_scores_replace_wrong_feed_scores(self) -> None:
        feed = [game("A", "B", 3, 1, 5), game("B", "A", 0, 0, 9), game("A", "C", None, None, 12)]
        espn = [
            football_playoffs.EspnMatch(datetime(2026, 3, 5, 2, tzinfo=UTC), "A", "B", 1, 3, None, None, True, "post", False, "regular-season"),
            football_playoffs.EspnMatch(datetime(2026, 3, 9, tzinfo=UTC), "B", "A", 0, 0, None, None, True, "post", False, "regular-season"),
            football_playoffs.EspnMatch(datetime(2026, 3, 12, tzinfo=UTC), "A", "C", 2, 2, None, None, True, "post", False, "regular-season"),
        ]
        fixed, changes = football_playoffs.corrected_games(feed, espn)
        self.assertEqual([(item.home_score, item.away_score) for item in fixed], [(1, 3), (0, 0), (2, 2)])
        # Only a result that FixtureDownload had wrong is reported; a missing one is just filled in.
        self.assertEqual([(before.home_score, after.home_score) for before, after in changes], [(3, 1)])


def toy_config(rounds: list[dict], groups: list[dict] | None = None) -> dict:
    return {"id": "toy", "shortName": "Toy", "conferences": groups or [], "playoffs": {"rounds": rounds}}


class BracketTests(unittest.TestCase):
    """The bracket engine on a toy league: eight equal teams in one table."""

    TEAMS = [f"T{i}" for i in range(1, 9)]

    def run_bracket(self, rounds: list[dict], real: dict | None = None, sims: int = 4000, home: float = 0.3) -> tuple[dict, np.ndarray]:
        parsed = football_playoffs.parse_rounds(toy_config(rounds))
        count = len(self.TEAMS)
        seeds = {"League": np.broadcast_to(np.arange(count), (sims, count))}
        position = np.broadcast_to(np.arange(count), (sims, count))
        zeros = np.zeros((sims, count))
        bracket = football_playoffs.Bracket(np.random.default_rng(1), np.log(1.4), home, zeros, zeros, seeds, position, position, real)
        return bracket.run(parsed)

    def test_slots_name_seeds_winners_and_losers(self) -> None:
        self.assertEqual(football_playoffs.parse_slot(8), football_playoffs.Slot(None, seed=8))
        self.assertEqual(football_playoffs.parse_slot("WC.1"), football_playoffs.Slot(None, round="WC", tie=1))
        self.assertEqual(football_playoffs.parse_slot("East:CF.1"), football_playoffs.Slot("East", round="CF", tie=1))
        self.assertEqual(football_playoffs.parse_slot("Q1.1.loser"), football_playoffs.Slot(None, round="Q1", tie=1, loser=True))
        self.assertEqual(football_playoffs.host_pattern("1-1-1", 3), (True, False, True))
        self.assertEqual(football_playoffs.host_pattern("2-2-1", 5), (True, True, False, False, True))

    def test_bad_brackets_fail_when_read(self) -> None:
        groups = [{"key": "East", "label": "East"}, {"key": "West", "label": "West"}]
        with self.assertRaisesRegex(ValueError, "before it is played"):
            football_playoffs.parse_rounds(toy_config([{"key": "F", "label": "F", "pairs": [["SF.1", "SF.2"]]}]))
        with self.assertRaisesRegex(ValueError, "needs a conference"):
            football_playoffs.parse_rounds(toy_config([{"key": "F", "label": "F", "across": True, "pairs": [[1, 2]]}], groups))
        with self.assertRaisesRegex(ValueError, "single tie"):
            football_playoffs.parse_rounds(toy_config([{"key": "SF", "label": "SF", "pairs": [[1, 4], [2, 3]]}]))
        with self.assertRaisesRegex(ValueError, "every series game needs a winner"):
            football_playoffs.parse_rounds(toy_config([{"key": "F", "label": "F", "match": "series", "decider": "higher-seed", "pairs": [[1, 2]]}]))
        for league_id in leagues.available_league_ids():
            config = leagues.read_config(league_id)
            if config.get("engine") == "football_playoffs":
                self.assertTrue(football_playoffs.parse_rounds(config))
                self.assertIn(config["sport"], extract_table.SPORT_MODULES)

    def test_a_drawn_game_goes_straight_to_penalties_or_to_extra_time(self) -> None:
        # Equal teams at a neutral ground: with or without extra time, each side goes through half the time.
        for decider in ("penalties", "extra-time"):
            reached, champion = self.run_bracket([{"key": "F", "label": "F", "neutral": True, "decider": decider, "pairs": [[1, 2]]}], home=0.0)
            self.assertAlmostEqual(float((champion == 0).mean()), 0.5, delta=0.03)
            self.assertTrue(reached["F"][:, :2].all())
        # The higher seed wins every level game when the rules say so.
        _, champion = self.run_bracket([{"key": "F", "label": "F", "neutral": True, "decider": "higher-seed", "pairs": [[1, 2]]}], home=0.0)
        self.assertGreater(float((champion == 0).mean()), 0.6)

    def test_real_results_replace_simulated_ones(self) -> None:
        rounds = [{"key": "SF", "label": "SF", "pairs": [[1, 4], [2, 3]]}, {"key": "F", "label": "F", "pairs": [["SF.1", "SF.2"]]}]
        real = {frozenset((0, 3)): [football_playoffs.SimGame(0, 3, 0, 2, 3)]}
        reached, champion = self.run_bracket(rounds, real)
        self.assertFalse(reached["F"][:, 0].any())
        self.assertTrue(reached["F"][:, 3].all())
        self.assertFalse((champion == 0).any())

    def test_a_series_starts_from_its_real_score(self) -> None:
        rounds = [{"key": "F", "label": "F", "match": "series", "bestOf": 3, "hosts": "1-1-1", "decider": "penalties", "pairs": [[1, 2]]}]
        _, fresh = self.run_bracket(rounds)
        # The higher seed hosts games 1 and 3, so it is the favourite before the series...
        self.assertGreater(float((fresh == 0).mean()), 0.5)
        # ...but after losing game 1 at home it must win twice in a row.
        lost_first = {frozenset((0, 1)): [football_playoffs.SimGame(0, 1, 0, 1, 1)]}
        _, behind = self.run_bracket(rounds, lost_first)
        self.assertLess(float((behind == 0).mean()), 0.35)
        won_two = {frozenset((0, 1)): [football_playoffs.SimGame(0, 1, 1, 0, 0), football_playoffs.SimGame(1, 0, 0, 1, 0)]}
        _, done = self.run_bracket(rounds, won_two)
        self.assertTrue((done == 0).all())

    def test_two_legged_ties_add_up_both_legs(self) -> None:
        rounds = [{"key": "F", "label": "F", "match": "two-legged", "pairs": [[1, 2]]}]
        # The lower seed hosts the first leg; the higher seed won it 4-0 away.
        first_leg = {frozenset((0, 1)): [football_playoffs.SimGame(1, 0, 0, 4, 0)]}
        _, champion = self.run_bracket(rounds, first_leg)
        self.assertGreater(float((champion == 0).mean()), 0.97)
        tie = football_playoffs.parse_rounds(toy_config(rounds))[0]
        SimGame = football_playoffs.SimGame
        # The aggregate decides, not the second leg: 3-0 away, then a 0-1 home defeat.
        state = football_playoffs.real_state(tie, 0, 1, [SimGame(1, 0, 0, 3, 0), SimGame(0, 1, 0, 1, 1)])
        self.assertEqual((state["top"], state["bottom"], state["winner"]), (3, 1, 0))
        # Level on aggregate: the second leg's shoot-out decides, though the home side won that leg 1-0.
        state = football_playoffs.real_state(tie, 0, 1, [SimGame(1, 0, 1, 0, 1), SimGame(0, 1, 1, 0, 0, 3, 4)])
        self.assertEqual((state["top"], state["bottom"], state["winner"]), (1, 1, 1))
        # Without extra time or penalties, a level tie goes to the higher seed when the rules say so.
        higher = football_playoffs.parse_rounds(toy_config([dict(rounds[0], decider="higher-seed")]))[0]
        state = football_playoffs.real_state(higher, 0, 1, [SimGame(1, 0, 2, 0, 1), SimGame(0, 1, 2, 0, 0)])
        self.assertEqual((state["top"], state["bottom"], state["winner"]), (2, 2, 0))
        _, champion = self.run_bracket(rounds, {frozenset((0, 1)): [SimGame(1, 0, 0, 3, 0), SimGame(0, 1, 0, 1, 1)]})
        self.assertTrue((champion == 0).all())

    def test_reseeding_pairs_the_best_seed_left_with_the_worst(self) -> None:
        rounds = [
            {"key": "QF", "label": "QF", "pairs": [[1, 8], [2, 7], [3, 6], [4, 5]]},
            {"key": "SF", "label": "SF", "teams": ["QF.1", "QF.2", "QF.3", "QF.4"]},
            {"key": "F", "label": "F", "pairs": [["SF.1", "SF.2"]]},
        ]
        parsed = football_playoffs.parse_rounds(toy_config(rounds))
        played = [
            football_playoffs.EspnMatch(datetime(2026, 5, day, tzinfo=UTC), home, away, hs, as_, None, None, True, "post", False, "playoffs")
            for day, home, away, hs, as_ in [(1, "T1", "T8", 0, 1), (1, "T2", "T7", 2, 0), (2, "T3", "T6", 1, 0), (2, "T4", "T5", 3, 1)]
        ]
        bracket = football_playoffs.real_bracket(parsed, {"League": self.TEAMS}, self.TEAMS, played, {})
        semis = [(series["top"], series["bottom"]) for series in bracket["rounds"][1]["series"]]
        self.assertEqual(semis, [("T2", "T8"), ("T3", "T4")])
        self.assertEqual(bracket["unplaced"], [])
        # The same rounds in the simulation: the 8th seed never meets the 3rd or 4th in the semi-finals.
        real = {frozenset((self.TEAMS.index(m.home), self.TEAMS.index(m.away))): [football_playoffs.SimGame(self.TEAMS.index(m.home), self.TEAMS.index(m.away), m.home_score, m.away_score, self.TEAMS.index(m.winner))] for m in played}
        reached, _ = self.run_bracket(rounds, real)
        self.assertTrue(reached["SF"][:, [1, 2, 3, 7]].all())
        self.assertFalse(reached["SF"][:, [0, 4, 5, 6]].any())

    def test_losers_can_play_on(self) -> None:
        # NBL style: 3 v 4, and the loser hosts the 5 v 6 winner.
        rounds = [
            {"key": "Q", "label": "Q", "pairs": [[3, 4], [5, 6]]},
            {"key": "E", "label": "E", "pairs": [["Q.1.loser", "Q.2"]]},
            {"key": "F", "label": "F", "pairs": [["Q.1", "E.1"]]},
        ]
        parsed = football_playoffs.parse_rounds(toy_config(rounds))
        played = [
            football_playoffs.EspnMatch(datetime(2026, 5, 1, tzinfo=UTC), "T3", "T4", 0, 2, None, None, True, "post", False, "playoffs"),
            football_playoffs.EspnMatch(datetime(2026, 5, 1, tzinfo=UTC), "T5", "T6", 1, 1, 4, 5, True, "post", True, "playoffs"),
        ]
        bracket = football_playoffs.real_bracket(parsed, {"League": self.TEAMS}, self.TEAMS, played, {})
        eliminator = bracket["rounds"][1]["series"][0]
        self.assertEqual((eliminator["top"], eliminator["bottom"]), ("T3", "T6"))
        self.assertEqual(bracket["rounds"][0]["series"][1]["note"], "4-5 on penalties")


class ScoreboardTests(unittest.TestCase):
    def test_cancelled_games_and_shootouts_are_read(self) -> None:
        rows = [
            ["2025-11-07T20:00Z", "western-conference-playoffs---round-one", "STATUS_CANCELED", False, "Vancouver Whitecaps", "FC Dallas", None, None, None, None],
            ["2025-11-02T01:30Z", "western-conference-playoffs---round-one", "STATUS_FINAL_PEN", True, "FC Dallas", "Vancouver Whitecaps", 1, 1, 2, 4],
        ]
        parsed = football_playoffs.parse_scoreboard(raw_scoreboard(rows))
        self.assertEqual(len(parsed), 1)
        self.assertEqual((parsed[0]["homeShootout"], parsed[0]["awayShootout"], parsed[0]["extraTime"]), (2, 4, True))
        with self.assertRaises(KeyError):
            football_playoffs.parse_scoreboard({"sports": []})


if __name__ == "__main__":
    unittest.main()
