"""The NWSL on the football playoff engine (football_playoffs.py), checked against real seasons.

tests/fixtures/nwsl-2025.json and nwsl-2026.json hold FixtureDownload's feed (2025's lists the
playoffs too) plus ESPN's scoreboard and standings in compact form, so these tests run offline.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

import extract_table
import football_playoffs
import leagues
import team_sports
from team_sports import Game
from test_football_playoffs import raw_scoreboard, raw_standings

FIXTURES = Path(__file__).parent / "fixtures"
UTC = timezone.utc
NOW_2026 = datetime(2026, 10, 4, 6, tzinfo=UTC)


def load_nwsl(cache: Path, year: int, as_of: datetime | None = None, espn: bool = True) -> None:
    """Write a season's fixture into a cache directory as the engine's downloads.

    With ``as_of``, ESPN games after it are not played yet, and those more than a week
    later are not scheduled yet (ESPN lists playoff games once the matchup is known).
    """
    data = json.loads((FIXTURES / f"nwsl-{year}.json").read_text(encoding="utf-8"))
    feed = [
        {"MatchNumber": number, "RoundNumber": round_number, "DateUtc": date, "Location": None, "HomeTeam": home, "AwayTeam": away, "HomeTeamScore": home_score, "AwayTeamScore": away_score}
        for number, round_number, date, home, away, home_score, away_score in data["games"]
    ]
    (cache / f"nwsl-{year}.json").write_text(json.dumps(feed), encoding="utf-8")
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
    (cache / f"espn-usa.nwsl-scoreboard-{year}.json").write_text(json.dumps(scoreboard), encoding="utf-8")
    standings = football_playoffs.parse_standings(raw_standings(data["standings"]))
    (cache / f"espn-usa.nwsl-standings-{year}.json").write_text(json.dumps(standings), encoding="utf-8")


def build(year: int, now: datetime, as_of: datetime | None = None, config: dict | None = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        load_nwsl(cache, year, as_of)
        if year == 2026:
            load_nwsl(cache, 2025)
        else:
            (cache / f"nwsl-{year - 1}.json").write_text("[]", encoding="utf-8")
        return football_playoffs.build_payload(config or leagues.read_config("nwsl"), now, cache)


def table(payload: dict) -> list[tuple]:
    return [
        (row["shortName"], row["played"], row["wins"], row["losses"], row["draws"], row["goalsFor"], row["goalsAgainst"], row["points"])
        for row in payload["standings"]
    ]


# Official standings: club, played, wins, losses, draws, goals for, goals against, points.
OFFICIAL_NWSL = {
    # https://www.nwslsoccer.com/standings/index (3 October 2026, after Portland 2-4 Boston; 213 of 240
    # games). Angel City are above North Carolina and Washington above Utah on goal difference:
    # the NWSL ranks goal difference before wins.
    2026: [
        ("GFC", 26, 16, 4, 6, 34, 20, 54), ("SD", 27, 16, 8, 3, 40, 28, 51), ("WAS", 26, 14, 8, 4, 36, 24, 46),
        ("UTA", 27, 14, 9, 4, 44, 35, 46), ("KC", 27, 13, 9, 5, 48, 38, 44), ("POR", 27, 12, 8, 7, 45, 39, 43),
        ("LA", 26, 12, 8, 6, 44, 28, 42), ("NC", 27, 13, 11, 3, 50, 39, 42), ("SEA", 27, 12, 11, 4, 33, 32, 40),
        ("DEN", 26, 9, 9, 8, 42, 37, 35), ("ORL", 27, 10, 14, 3, 36, 43, 33), ("HOU", 26, 8, 12, 6, 32, 36, 30),
        ("BOS", 27, 8, 14, 5, 36, 46, 29), ("BAY", 27, 7, 15, 5, 28, 42, 26), ("LOU", 27, 7, 17, 3, 36, 52, 24),
        ("CHI", 26, 5, 19, 2, 15, 60, 17),
    ],
    # https://www.nwslsoccer.com/standings/index with "Regular Season 2025" selected (final).
    2025: [
        ("KC", 26, 21, 3, 2, 49, 13, 65), ("WAS", 26, 12, 6, 8, 42, 33, 44), ("POR", 26, 11, 8, 7, 36, 29, 40),
        ("ORL", 26, 11, 8, 7, 33, 27, 40), ("SEA", 26, 10, 7, 9, 32, 29, 39), ("SD", 26, 10, 9, 7, 41, 34, 37),
        ("LOU", 26, 10, 9, 7, 35, 38, 37), ("GFC", 26, 9, 8, 9, 35, 25, 36), ("NC", 26, 9, 9, 8, 37, 39, 35),
        ("HOU", 26, 8, 12, 6, 27, 39, 30), ("LA", 26, 7, 13, 6, 31, 41, 27), ("UTA", 26, 6, 13, 7, 28, 42, 25),
        ("BAY", 26, 4, 14, 8, 26, 41, 20), ("CHI", 26, 3, 12, 11, 32, 54, 20),
    ],
}

# The 2025 NWSL Playoffs (https://www.nwslsoccer.com/playoffs): (higher seed, lower seed, their
# seeds, goals, winner, note). Results from nwslsoccer.com's reports, with ESPN's scores:
# https://www.nwslsoccer.com/news/gotham-pull-off-stunning-upset-eliminating-kc-current-at-cpkc-stadium (extra time),
# https://www.nwslsoccer.com/news/fired-up-orlando-pride-welcome-doubters-we-love-it (2-0),
# https://www.nwslsoccer.com/news/washington-spirit-beat-racing-louisville-advance-to-semifinals-in-yet-another-pk-shootout-at-audi-field,
# https://www.nwslsoccer.com/news/portland-thorns-advance-to-record-10th-semifinal-sending-the-wave-packing (extra time),
# https://www.nwslsoccer.com/news/don-t-call-them-the-underdog-gotham-fc-punch-their-ticket-to-the-nwsl-championship,
# https://www.nwslsoccer.com/news/gift-monday-croix-bethune-goals-send-washington-spirit-to-back-to-back-nwsl-championships and
# https://www.nwslsoccer.com/news/mvp-rose-lavelle-leads-gotham-to-second-nwsl-championship-victory-over-washington-spirit.
OFFICIAL_BRACKET_2025 = {
    "QF": [
        ("KC", "GFC", 1, 8, (1, 2), "GFC", "After extra time"),
        ("ORL", "SEA", 4, 5, (2, 0), "ORL", None),
        ("WAS", "LOU", 2, 7, (1, 1), "WAS", "3-1 on penalties"),
        ("POR", "SD", 3, 6, (1, 0), "POR", "After extra time"),
    ],
    "SF": [
        ("ORL", "GFC", 4, 8, (0, 1), "GFC", None),
        ("WAS", "POR", 2, 3, (2, 0), "WAS", None),
    ],
    # At PayPal Park, San Jose (Bay FC's home), so on neutral ground for both finalists.
    "F": [("WAS", "GFC", 2, 8, (0, 1), "GFC", None)],
}


def bracket_rows(payload: dict) -> dict[str, list[tuple]]:
    short = {row["teamKey"]: row["shortName"] for row in payload["standings"]}
    return {
        item["key"]: [
            (
                short[series["top"]],
                short[series["bottom"]],
                series["topSeed"],
                series["bottomSeed"],
                (series["aggregate"]["top"], series["aggregate"]["bottom"]),
                short[series["winner"]],
                series.get("note"),
            )
            for series in item["series"]
        ]
        for item in payload["bracket"]["rounds"]
    }


class NwslLiveTests(unittest.TestCase):
    """The 2026 regular season on 4 October 2026: 213 of 240 games played."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = leagues.read_config("nwsl")
        cls.payload = build(2026, NOW_2026)

    def test_the_table_matches_the_official_standings(self) -> None:
        self.assertEqual(table(self.payload), OFFICIAL_NWSL[2026])

    def test_our_tiebreakers_alone_give_the_official_order(self) -> None:
        # With ESPN down, goal difference before wins still puts Angel City above North Carolina.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(team_sports, "get_json", side_effect=ConnectionError("down")):
            cache = Path(tmp)
            load_nwsl(cache, 2026, espn=False)
            load_nwsl(cache, 2025, espn=False)
            payload = football_playoffs.build_payload(self.cfg, NOW_2026, cache)
        self.assertEqual(table(payload), OFFICIAL_NWSL[2026])
        self.assertEqual(payload["metadata"]["warnings"], [])

    def test_odds_add_up_to_the_places_on_offer(self) -> None:
        probabilities = self.payload["analysis"]["probabilities"]
        totals = {key: sum(values[key] for values in probabilities.values()) / 100 for key in ("playoffs", "top4", "shield", "title")}
        self.assertAlmostEqual(totals["playoffs"], 8, delta=0.01)
        self.assertAlmostEqual(totals["top4"], 4, delta=0.01)
        self.assertAlmostEqual(totals["shield"], 1, delta=0.01)
        self.assertAlmostEqual(totals["title"], 1, delta=0.01)
        # Gotham (54 points) are clear of ninth-placed Seattle's best possible 49.
        self.assertEqual(probabilities["Gotham FC"]["playoffs"], 100.0)
        self.assertGreater(probabilities["Gotham FC"]["shield"], 50)
        for values in probabilities.values():
            self.assertLessEqual(values["title"], values["playoffs"] + 1e-9)
            self.assertLessEqual(values["top4"], values["playoffs"] + 1e-9)

    def test_the_page_shows_one_table_with_playoff_lines(self) -> None:
        league = self.payload["league"]
        self.assertEqual(league["id"], "nwsl-2026")
        self.assertEqual(league["groups"], [])
        self.assertEqual(league["cutoffs"], [{"after": 4, "label": "Away quarterfinal"}, {"after": 8, "label": "Out"}])
        self.assertEqual([tier["key"] for tier in league["tiers"]], ["playoffs", "top4", "shield", "title"])
        self.assertEqual(len(self.payload["analysis"]["positions"]["Gotham FC"]), 16)
        self.assertEqual(self.payload["metadata"]["season_status"], "in_progress")
        self.assertNotIn("bracket", self.payload)
        self.assertEqual(len(self.payload["fixtures"]), 27)
        # One table: the team panel shows place and points, not an MLS-style record and conference seed.
        self.assertEqual((self.payload["standings"][0]["wins"], self.payload["standings"][0]["losses"], self.payload["standings"][0]["draws"]), (16, 4, 6))
        self.assertFalse({"record", "seed", "conference"} & set(self.payload["standings"][0]))
        self.assertTrue(self.payload["matchesThatMatter"])
        self.assertEqual(self.payload["metadata"]["warnings"], [])
        team_sports.validate_config(self.cfg)
        self.assertEqual(extract_table.index_entry(self.payload)["facts"][0]["label"], "Championship favourite")

    def test_the_final_at_audi_field_is_a_home_game_for_washington(self) -> None:
        rounds = football_playoffs.parse_rounds(self.cfg, 2026)
        self.assertEqual([(item.key, item.neutral, item.host) for item in rounds], [("QF", False, None), ("SF", False, None), ("F", True, "Washington Spirit")])
        self.assertIsNone(football_playoffs.parse_rounds(self.cfg, 2027)[-1].host)


class Nwsl2025Tests(unittest.TestCase):
    """The finished 2025 season: FixtureDownload's feed lists the playoffs, ESPN supplies them."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build(2025, datetime(2025, 12, 20, tzinfo=UTC))

    def test_the_final_table_matches_the_official_standings(self) -> None:
        # Every club has 26 games: the feed's seven playoff games are left out of the table.
        self.assertEqual(table(self.payload), OFFICIAL_NWSL[2025])

    def test_wrong_and_missing_feed_scores_come_from_espn(self) -> None:
        note = next(note for note in self.payload["analysis"]["modelNotes"] if "FixtureDownload score" in note)
        self.assertIn("2 FixtureDownload scores differ", note)
        self.assertIn("Chicago Stars FC 2-2 Seattle Reign FC on 14 Jun (not 4-2)", note)
        self.assertIn("Kansas City Current 4-2 Racing Louisville FC on 14 Jun (not 2-2)", note)
        # The feed has no score for Seattle 1-0 Louisville (16 September); ESPN's fills it in.
        result = next(item for item in self.payload["results"] if item["id"] == "140")
        self.assertEqual((result["home"], result["homeScore"], result["awayScore"]), ("Seattle Reign FC", 1, 0))

    def test_the_real_bracket_is_reproduced(self) -> None:
        self.assertEqual(bracket_rows(self.payload), OFFICIAL_BRACKET_2025)
        self.assertEqual([item["label"] for item in self.payload["bracket"]["rounds"]], ["Quarterfinals", "Semifinals", "NWSL Championship"])
        self.assertEqual({series["bestOf"] for item in self.payload["bracket"]["rounds"] for series in item["series"]}, {1})

    def test_the_champion_is_named_and_every_race_is_settled(self) -> None:
        self.assertEqual(self.payload["bracket"]["champion"], "Gotham FC")
        self.assertEqual(self.payload["playoffs"], {"champion": "Gotham FC"})
        self.assertEqual(self.payload["metadata"]["season_status"], "complete")
        self.assertTrue(all(tier.get("settled") for tier in self.payload["league"]["tiers"]))
        probabilities = self.payload["analysis"]["probabilities"]
        self.assertEqual(probabilities["Gotham FC"]["title"], 100.0)
        self.assertEqual(probabilities["Kansas City Current"]["shield"], 100.0)
        self.assertEqual(extract_table.index_entry(self.payload)["champion"], "GFC")

    def test_playoff_results_carry_their_round(self) -> None:
        notes = [item["note"] for item in self.payload["results"] if item["id"].startswith("playoff-result")]
        self.assertEqual(len(notes), 7)
        self.assertEqual(notes[0], "NWSL Championship")
        self.assertIn("Quarterfinals, 3-1 pens", notes)
        self.assertEqual(notes.count("Quarterfinals, aet"), 2)
        self.assertEqual(self.payload["fixtures"], [])


class NwslMidPlayoffsTests(unittest.TestCase):
    """2025 on 10 November: the quarterfinals played, the semifinals scheduled."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.as_of = datetime(2025, 11, 10, tzinfo=UTC)
        cls.payload = build(2025, cls.as_of, as_of=cls.as_of)

    def test_the_semifinals_follow_the_fixed_bracket(self) -> None:
        semis = [(series["top"], series["bottom"], series["winner"]) for series in self.payload["bracket"]["rounds"][1]["series"]]
        # 1 v 8's winner meets 4 v 5's, and 2 v 7's meets 3 v 6's, with no reseeding.
        self.assertEqual(semis, [("Orlando Pride", "Gotham FC", None), ("Washington Spirit", "Portland Thorns FC", None)])
        self.assertEqual(self.payload["metadata"]["season_status"], "postseason")
        stages = [(fixture["home"], fixture["away"], fixture["stage"]) for fixture in self.payload["fixtures"]]
        self.assertEqual(stages, [("Washington Spirit", "Portland Thorns FC", "Semifinals"), ("Orlando Pride", "Gotham FC", "Semifinals")])

    def test_title_odds_go_to_the_four_teams_left(self) -> None:
        title = {team: values["title"] for team, values in self.payload["analysis"]["probabilities"].items()}
        self.assertAlmostEqual(sum(title.values()), 100, delta=0.05)
        self.assertEqual({team for team, value in title.items() if value > 0}, {"Orlando Pride", "Gotham FC", "Washington Spirit", "Portland Thorns FC"})
        settled = {tier["key"] for tier in self.payload["league"]["tiers"] if tier.get("settled")}
        self.assertEqual(settled, {"playoffs", "top4", "shield"})


class NeutralFinalTests(unittest.TestCase):
    """A final at one finalist's home ground (the 2026 NWSL Championship at Audi Field)."""

    def test_a_neutral_final_is_level_and_the_grounds_club_plays_at_home(self) -> None:
        rounds = [{"key": "F", "label": "F", "neutral": True, "homeGround": {"2026": "T2"}, "pairs": [[1, 2]]}]
        config = {"id": "toy", "shortName": "Toy", "playoffs": {"rounds": rounds}}
        sims, count = 20_000, 2
        seeds = {"League": np.broadcast_to(np.arange(count), (sims, count))}
        position = np.broadcast_to(np.arange(count), (sims, count))
        zeros = np.zeros((sims, count))

        def champion_share(year: int | None, hosts: dict) -> float:
            parsed = football_playoffs.parse_rounds(config, year)
            bracket = football_playoffs.Bracket(np.random.default_rng(3), np.log(1.3), 0.4, zeros, zeros, seeds, position, position, None, hosts)
            _, champion = bracket.run(parsed)
            return float((champion == 1).mean())

        # Equal teams on neutral ground: the lower seed wins half the time, home advantage or not.
        self.assertAlmostEqual(champion_share(None, {}), 0.5, delta=0.015)
        # At the lower seed's own ground, it has the home advantage.
        self.assertGreater(champion_share(2026, {"F": 1}), 0.56)

    def test_only_a_neutral_single_match_round_names_a_home_ground(self) -> None:
        config = {"id": "toy", "shortName": "Toy", "playoffs": {"rounds": [{"key": "F", "label": "F", "homeGround": {"2026": "T1"}, "pairs": [[1, 2]]}]}}
        with self.assertRaisesRegex(ValueError, "homeGround"):
            football_playoffs.parse_rounds(config)

    def test_the_final_fixture_gives_home_advantage_only_to_the_grounds_club(self) -> None:
        as_of = datetime(2025, 11, 17, tzinfo=UTC)
        neutral = build(2025, as_of, as_of=as_of)
        config = copy.deepcopy(leagues.read_config("nwsl"))
        # Suppose the 2025 final had been at Gotham's ground (ESPN lists Gotham as the away side).
        config["playoffs"]["rounds"][-1]["homeGround"]["2025"] = "Gotham FC"
        hosted = build(2025, as_of, as_of=as_of, config=config)
        final = neutral["fixtures"][0]
        self.assertEqual((final["home"], final["away"], final["stage"]), ("Washington Spirit", "Gotham FC", "NWSL Championship"))
        self.assertGreater(hosted["fixtures"][0]["probabilities"]["away"], final["probabilities"]["away"] + 0.03)
        gotham = lambda payload: payload["analysis"]["probabilities"]["Gotham FC"]["title"]
        self.assertGreater(gotham(hosted), gotham(neutral) + 3)


def game(number: int, home: str, away: str, day: int, score: tuple[int, int] | None = (1, 0)) -> Game:
    home_score, away_score = score if score else (None, None)
    return Game(str(number), None, datetime(2026, 3, 1, tzinfo=UTC) + timedelta(days=day), home, away, None, home_score, away_score)


def double_round_robin(teams: list[str]) -> list[Game]:
    games, day = [], 0
    for home in teams:
        for away in teams:
            if home != away:
                day += 1
                games.append(game(len(games) + 1, home, away, day))
    return games


class FeedPlayoffTests(unittest.TestCase):
    TEAMS = list("ABCDEFGH")

    def test_the_feeds_playoff_games_are_split_off(self) -> None:
        data = json.loads((FIXTURES / "nwsl-2025.json").read_text(encoding="utf-8"))
        games = [
            Game(str(number), round_number, datetime.fromisoformat(date.replace(" ", "T").replace("Z", "+00:00")), home, away, None, home_score, away_score)
            for number, round_number, date, home, away, home_score, away_score in data["games"]
        ]
        regular, postseason = football_playoffs.split_postseason(games, 8)
        self.assertEqual((len(regular), len(postseason)), (182, 7))
        self.assertEqual(sorted(int(item.id) for item in postseason), list(range(183, 190)))

    def test_a_regular_season_feed_is_unchanged(self) -> None:
        games = double_round_robin(self.TEAMS)
        self.assertEqual(football_playoffs.split_postseason(games, 4), (games, []))
        # A game missing from the feed leaves two clubs a game short; nothing else moves.
        self.assertEqual(football_playoffs.split_postseason(games[1:], 4), (games[1:], []))

    def test_playoff_games_and_placeholders_after_the_regular_season(self) -> None:
        games = double_round_robin(self.TEAMS)
        # After the semifinals and before the final's teams are known, half the clubs have a
        # game more than the others; the clubs that missed the playoffs give the season's length.
        playoffs = [game(100, "A", "D", 70, (2, 1)), game(101, "B", "C", 70, (0, 1))]
        placeholder = game(102, "Winner SF1", "Winner SF2", 77, None)
        regular, postseason = football_playoffs.split_postseason(games + playoffs + [placeholder], 4)
        self.assertEqual(regular, games)
        self.assertEqual(postseason, playoffs + [placeholder])


class TiebreakTests(unittest.TestCase):
    STEPS = ["goal-difference", "wins", "goals-for", "head-to-head-points", "head-to-head-goals"]

    def rank(self, games: list[Game]) -> list[str]:
        rows = {team: {"points": 10, "wins": 3, "goalDifference": 2, "goalsFor": 6} for team in ("Alpha", "Beta", "Gamma")}
        return football_playoffs.rank_teams(sorted(rows), rows, games, self.STEPS, {team: "League" for team in rows})

    def test_head_to_head_points_then_head_to_head_goals(self) -> None:
        day = lambda number: datetime(2026, 3, number, tzinfo=UTC)
        # Gamma beat both; Alpha and Beta took three points each from each other, Beta scoring more.
        games = [
            Game("1", None, day(1), "Gamma", "Alpha", None, 1, 0),
            Game("2", None, day(2), "Gamma", "Beta", None, 2, 1),
            Game("3", None, day(3), "Alpha", "Beta", None, 1, 0),
            Game("4", None, day(4), "Beta", "Alpha", None, 3, 1),
        ]
        self.assertEqual(self.rank(games), ["Gamma", "Beta", "Alpha"])
        # Head-to-head goals count the games between the teams still level (Alpha and Beta drew
        # 2-2), not Beta's goal against Gamma; level again, the order falls back to the name (a
        # coin flip or drawing of lots, officially, after disciplinary points).
        self.assertEqual(self.rank(games[:2] + [Game("3", None, day(3), "Alpha", "Beta", None, 2, 2)]), ["Gamma", "Alpha", "Beta"])

    def test_goal_difference_comes_before_wins(self) -> None:
        rows = {"Wins": {"points": 10, "wins": 3, "goalDifference": 0, "goalsFor": 5}, "Goals": {"points": 10, "wins": 2, "goalDifference": 4, "goalsFor": 5}}
        steps = leagues.read_config("nwsl")["tiebreakers"]
        self.assertEqual(football_playoffs.rank_teams(["Wins", "Goals"], rows, [], steps, {"Wins": "League", "Goals": "League"}), ["Goals", "Wins"])


if __name__ == "__main__":
    unittest.main()
