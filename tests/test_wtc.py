"""World Test Championship: rules, table, exact claims, simulation, sources and states."""

from __future__ import annotations

import copy
import itertools
import json
import random
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from unittest import mock

import extract_table
import leagues
import wtc
import wtc_model
from wtc_model import TestMatch

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "leagues" / "wtc-2025-27.json").read_text(encoding="utf-8"))
OFFICIAL = json.loads((ROOT / "tests" / "fixtures" / "wtc-2025-27.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)

# The ICC's table on 20 November 2026 (icc-cricket.com WTC standings and its data feed):
# matches, won, lost, drawn, penalty points deducted, points and PCT, in the ICC's order.
OFFICIAL_TABLE = [
    ("SA", 8, 6, 2, 0, 0, 72, 75.00),
    ("NZ", 6, 4, 1, 1, 0, 52, 72.22),
    ("AUS", 13, 9, 4, 0, 0, 108, 69.23),
    ("IND", 11, 5, 4, 2, 0, 68, 51.52),
    ("BAN", 9, 3, 4, 2, 0, 44, 40.74),
    ("ENG", 16, 7, 8, 1, 14, 74, 38.54),
    ("WI", 14, 3, 8, 3, 2, 46, 27.38),
    ("SL", 8, 1, 3, 4, 15, 13, 13.54),
    ("PAK", 11, 3, 7, 1, 24, 16, 12.12),
]


def official_results(cycle: wtc.Cycle) -> dict[str, wtc.Result]:
    winners = {}
    for item in OFFICIAL["results"]:
        winners[item["test"]] = wtc.Result(item["test"], item["result"], margin=item.get("margin", ""), source="ICC")
    return winners


def mini_config(series: list[dict], teams=("AAA", "BBB", "CCC", "DDD"), **extra) -> dict:
    """A small championship for rule tests: each series is (id, host, visitor, [start dates])."""
    config = {
        "id": "wtc-test",
        "sport": "cricket",
        "engine": "wtc",
        "name": "Test Championship",
        "shortName": "TC",
        "seasonLabel": "2025-27",
        "seasonStart": "2025-06-01",
        "standingsClose": "2027-04-30",
        "seasonEnd": "2027-06-14",
        "format": {"points": {"win": 12, "tie": 6, "draw": 4, "loss": 0}, "finalists": 2},
        "final": {"country": "ENG", "start": "2027-06-09", "end": "2027-06-13"},
        "teams": [{"key": team, "shortName": team, "fullName": team.title()} for team in teams],
        "series": series,
    }
    config.update(extra)
    return config


def series(identifier: str, host: str, visitor: str, starts: list[str], **extra) -> dict:
    return {"id": identifier, "host": host, "visitor": visitor, "tests": [{"number": i + 1, "start": day, **extra.get("test", {})} for i, day in enumerate(starts)], **{k: v for k, v in extra.items() if k != "test"}}


def flat_ratings(teams, home=0.3, draw=-1.2) -> wtc_model.Ratings:
    return wtc_model.Ratings(
        teams=list(teams), countries=list(teams), rating={team: 0.0 for team in teams}, home=home,
        home_by_country={}, draw=draw, draw_by_country={},
    )


def write_tests_archive(directory: Path, tests: list[dict]) -> Path:
    path = directory / "tests_male_json.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for index, info in enumerate(tests):
            archive.writestr(f"{9000 + index}.json", json.dumps({"info": {"match_type": "Test", **info}}))
    return path


class ConfigTests(unittest.TestCase):
    def test_config_has_the_full_schedule(self) -> None:
        cycle = wtc.parse_config(CONFIG)
        self.assertEqual(len(cycle.teams), 9)
        self.assertEqual(len(cycle.series), 27)
        self.assertEqual(len(cycle.fixtures), 71)
        for team in cycle.teams:
            home = sum(item.host == team for item in cycle.series)
            away = sum(item.visitor == team for item in cycle.series)
            self.assertEqual((home, away), (3, 3), team)
        for item in cycle.series:
            self.assertTrue(2 <= len(item.fixtures) <= 5, item.id)
        self.assertEqual(cycle.final.venue, "The Oval")
        self.assertEqual(cycle.final.draw_result, "joint")
        self.assertEqual(sorted(cycle.rankings), sorted(cycle.teams))

    def test_every_deduction_names_its_test_and_source(self) -> None:
        cycle = wtc.parse_config(CONFIG)
        for item in cycle.deductions:
            self.assertTrue(item.source.startswith("https://"), item)
            self.assertIn(item.team, next(f for f in cycle.fixtures if f.key == item.test).teams)

    def test_bad_configs_fail_fast(self) -> None:
        broken = copy.deepcopy(CONFIG)
        broken["deductions"].append({"team": "AUS", "points": 3, "test": "eng-ind-2025-1", "note": "wrong Test"})
        with self.assertRaisesRegex(ValueError, "did not play"):
            wtc.parse_config(broken)
        broken = copy.deepcopy(CONFIG)
        broken["results"].append({"test": "aus-nz-2026-1", "result": "host"})
        with self.assertRaisesRegex(ValueError, "source"):
            wtc.parse_config(broken)
        broken = copy.deepcopy(CONFIG)
        broken["results"].append({"test": "aus-nz-2026-1", "result": "forfeit", "source": "ICC"})
        with self.assertRaisesRegex(ValueError, "winner"):
            wtc.parse_config(broken)
        broken = copy.deepcopy(CONFIG)
        broken["series"].pop()
        with self.assertRaisesRegex(ValueError, "series, not 6"):
            wtc.parse_config(broken)

    def test_the_championship_is_not_a_t20_season_and_is_not_rolled_forward(self) -> None:
        self.assertFalse(leagues.is_cricket(CONFIG))
        with self.assertRaisesRegex(ValueError, "wtc config"):
            leagues.load_league("wtc-2025-27")
        # 2027-29's format is not known yet: no successor is made from this cycle.
        later = datetime(2027, 9, 1, tzinfo=timezone.utc)
        self.assertFalse(any(item.startswith("wtc") for item in leagues.rolled_league_ids(later, 45)))
        with self.assertRaises(ValueError):
            leagues.read_config("wtc-2027-29")

    def test_month_only_dates_are_tentative_and_never_assumed_under_way(self) -> None:
        cycle = wtc.parse_config(CONFIG)
        fixture = next(f for f in cycle.fixtures if f.key == "ban-eng-2027-1")
        self.assertEqual((fixture.precision, fixture.tentative), ("month", True))
        states = wtc.classify(cycle, {}, {}, date(2027, 2, 2))
        self.assertEqual(states["ban-eng-2027-1"], "scheduled")
        self.assertEqual(wtc.classify(cycle, {}, {}, date(2027, 3, 3))["ban-eng-2027-1"], "awaiting")


class OfficialTableTests(unittest.TestCase):
    def test_table_matches_the_icc_table_of_20_november_2026(self) -> None:
        cycle = wtc.parse_config(CONFIG)
        rows = wtc.table(cycle, official_results(cycle))
        order = wtc.rank(cycle, rows)
        self.assertEqual(order, [item[0] for item in OFFICIAL_TABLE])
        for team, played, won, lost, drawn, deducted, points, pct in OFFICIAL_TABLE:
            row = rows[team]
            self.assertEqual((row.played, row.won, row.lost, row.drawn, row.deducted, row.points), (played, won, lost, drawn, deducted, points), team)
            self.assertEqual(round(float(row.pct(cycle.rules)) * 100, 2), pct, team)

    def test_config_results_plus_cricsheet_reproduce_the_official_table(self) -> None:
        """Every Cricsheet Test of the cycle matches the ICC's result (only when the archive is cached)."""
        archive = ROOT / ".cache" / "cricsheet" / "tests_male_json.zip"
        if not archive.exists():
            self.skipTest("Cricsheet Test archive not cached")
        cycle = wtc.parse_config(CONFIG)
        warnings: list[str] = []
        found = wtc.match_cricsheet(cycle, wtc_model.load_tests(archive), warnings)
        self.assertEqual(warnings, [])
        official = official_results(cycle)
        for key, result in found.items():
            if key in official:
                self.assertEqual(result.kind, official[key].kind, key)
        for item in cycle.results:
            self.assertEqual(item.kind, official[item.fixture].kind, item.fixture)


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = mini_config([
            series("a-b", "AAA", "BBB", ["2025-07-01", "2025-07-10", "2025-07-20"]),
            series("c-d", "CCC", "DDD", ["2025-08-01", "2025-08-10"]),
            series("b-c", "BBB", "CCC", ["2025-09-01", "2025-09-10"]),
            series("d-a", "DDD", "AAA", ["2025-10-01", "2025-10-10"]),
        ])

    def results(self, cycle, **kinds) -> dict[str, wtc.Result]:
        out = {}
        for key, spec in kinds.items():
            key = key.replace("_", "-")
            kind, winner = (spec, None) if isinstance(spec, str) else spec
            out[key] = wtc.Result(key, kind, winner=winner, source="test")
        return out

    def test_points_for_every_kind_of_result(self) -> None:
        cycle = wtc.parse_config(self.config)
        fixture = cycle.fixtures[0]
        cases = {
            "host": {"AAA": 12, "BBB": 0},
            "visitor": {"AAA": 0, "BBB": 12},
            "draw": {"AAA": 4, "BBB": 4},
            "tie": {"AAA": 6, "BBB": 6},
            # Abandoned (weather, no ball bowled) is a draw (Playing Conditions 16.10.2).
            "abandoned": {"AAA": 4, "BBB": 4},
            # Abandoned on an unfit pitch or outfield: the visitors take a win's points.
            "unfit": {"AAA": 0, "BBB": 12},
        }
        for kind, points in cases.items():
            self.assertEqual(wtc.Result(fixture.key, kind).points(fixture, cycle.rules), points, kind)
        for kind in ("awarded", "forfeit"):
            # Conceded, refused, or not played through unacceptable non-compliance (Regulation 8.1).
            self.assertEqual(wtc.Result(fixture.key, kind, winner="AAA").points(fixture, cycle.rules), {"AAA": 12, "BBB": 0})
            self.assertEqual(wtc.Result(fixture.key, kind, winner="BBB").points(fixture, cycle.rules), {"AAA": 0, "BBB": 12})

    def test_record_and_series_follow_the_statistical_result(self) -> None:
        cycle = wtc.parse_config(self.config)
        results = self.results(cycle, a_b_1="unfit", a_b_2="abandoned", a_b_3=("forfeit", "AAA"))
        rows = wtc.table(cycle, results)
        # The unfit-pitch Test is a draw in the records though the visitors got 12 points.
        self.assertEqual((rows["AAA"].played, rows["AAA"].won, rows["AAA"].drawn, rows["AAA"].points), (3, 1, 2, 16))
        self.assertEqual((rows["BBB"].played, rows["BBB"].lost, rows["BBB"].drawn, rows["BBB"].points), (3, 1, 2, 16))
        # 1-0 to AAA: the unfit-pitch Test does not count as a BBB win in the series.
        self.assertEqual((rows["AAA"].series_won, rows["BBB"].series_won), (1, 0))
        self.assertEqual(rows["AAA"].pct(cycle.rules), Fraction(16, 36))

    def test_cancelled_and_postponed_tests_leave_the_points_percentage(self) -> None:
        config = copy.deepcopy(self.config)
        config["series"][0]["tests"][2]["status"] = "cancelled"
        config["series"][1]["tests"][1]["status"] = "postponed"
        cycle = wtc.parse_config(config)
        results = self.results(cycle, a_b_1="host", a_b_2="draw", c_d_1="visitor")
        rows = wtc.table(cycle, results)
        self.assertEqual(rows["AAA"].played, 2)
        self.assertEqual(rows["AAA"].pct(cycle.rules), Fraction(16, 24))
        # A shortened series is complete once its remaining Tests are in.
        self.assertTrue(wtc.series_state(cycle, cycle.series[0], results)["complete"])
        self.assertEqual(rows["AAA"].series_won, 1)
        self.assertEqual(rows["DDD"].series_won, 1)
        states = wtc.classify(cycle, results, {}, date(2025, 12, 1))
        self.assertEqual((states["a-b-3"], states["c-d-2"]), ("cancelled", "postponed"))

    def test_a_series_lengthened_mid_cycle_counts_its_new_test(self) -> None:
        config = copy.deepcopy(self.config)
        config["series"][1]["tests"].append({"number": 3, "start": "2025-08-20"})
        cycle = wtc.parse_config(config)
        results = self.results(cycle, c_d_1="host", c_d_2="visitor")
        self.assertFalse(wtc.series_state(cycle, cycle.series[1], results)["complete"])
        results["c-d-3"] = wtc.Result("c-d-3", "host", source="test")
        rows = wtc.table(cycle, results)
        self.assertEqual((rows["CCC"].played, rows["CCC"].series_won), (3, 1))

    def test_deductions_come_off_points_and_away_points(self) -> None:
        config = copy.deepcopy(self.config)
        config["deductions"] = [
            {"team": "BBB", "points": 3, "test": "a-b-1", "note": "3 overs short", "source": "https://example.org/a"},
            {"team": "AAA", "points": 2, "test": "a-b-1", "note": "2 overs short", "source": "https://example.org/b"},
        ]
        cycle = wtc.parse_config(config)
        rows = wtc.table(cycle, self.results(cycle, a_b_1="visitor"))
        self.assertEqual((rows["BBB"].points, rows["BBB"].deducted, rows["BBB"].away_points), (9, 3, 9))
        # AAA was at home: its deduction is not in its away PCT.
        self.assertEqual((rows["AAA"].points, rows["AAA"].away_points), (-2, 0))
        self.assertEqual(rows["AAA"].pct(cycle.rules), Fraction(-2, 12))

    def test_tie_breakers_in_order(self) -> None:
        cycle = wtc.parse_config(mini_config([], rankings={"order": ["DDD", "CCC", "BBB", "AAA"]}))
        rows = {team: wtc.Row(team, played=12, points_won=96) for team in cycle.teams}
        # Level on PCT: series wins first.
        rows["AAA"].series_won = 3
        rows["BBB"].series_won = 2
        rows["CCC"].series_won = 2
        rows["DDD"].series_won = 2
        # Then away PCT.
        for team, away in (("BBB", 30), ("CCC", 36), ("DDD", 30)):
            rows[team].away_played, rows[team].away_points = 6, away
        # Then the ICC ranking: DDD above BBB.
        self.assertEqual(wtc.rank(cycle, rows), ["AAA", "CCC", "DDD", "BBB"])
        notes = wtc.tie_notes(cycle, rows, wtc.rank(cycle, rows))
        self.assertEqual(len(notes), 1)
        self.assertIn("ICC Test ranking", notes[0])

    def test_pct_is_compared_exactly(self) -> None:
        cycle = wtc.parse_config(mini_config([], rankings={"order": ["BBB", "AAA", "CCC", "DDD"]}))
        rows = {team: wtc.Row(team) for team in cycle.teams}
        # 2/3 and 8/12 are the same PCT; 0.6667 rounded would hide the difference from 66.66...%.
        rows["AAA"].played, rows["AAA"].points_won = 3, 24
        rows["BBB"].played, rows["BBB"].points_won = 12, 96
        rows["CCC"].played, rows["CCC"].points_won = 12, 95
        order = wtc.rank(cycle, rows)
        self.assertEqual(order[:3], ["BBB", "AAA", "CCC"])


class SourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cycle = wtc.parse_config(CONFIG)

    def test_cricsheet_tests_are_matched_by_teams_and_date(self) -> None:
        tests = [
            TestMatch("1", date(2026, 12, 10), date(2026, 12, 14), ("AUS", "NZ"), "Perth Stadium", "Perth", "AUS", "NZ", margin="5 wickets"),
            # A day late (rain-delayed start or a time zone) still matches.
            TestMatch("2", date(2026, 12, 18), date(2026, 12, 22), ("AUS", "NZ"), "Adelaide Oval", "Adelaide", "AUS", None),
            # India v Australia in a window with no such series: flagged.
            TestMatch("3", date(2026, 6, 1), date(2026, 6, 5), ("IND", "AUS"), "Lord's", "London", "ENG", "IND"),
            # Zimbabwe are not in the championship.
            TestMatch("4", date(2026, 6, 1), date(2026, 6, 5), ("ZIM", "SA"), "Harare Sports Club", "Harare", "ZIM", "SA"),
        ]
        warnings: list[str] = []
        found = wtc.match_cricsheet(self.cycle, tests, warnings)
        self.assertEqual(found["aus-nz-2026-1"].kind, "visitor")
        self.assertEqual(found["aus-nz-2026-1"].margin, "5 wickets")
        self.assertEqual(found["aus-nz-2026-2"].kind, "draw")
        self.assertEqual(len(found), 2)
        self.assertEqual(len(warnings), 1)
        self.assertIn("not in the championship schedule", warnings[0])

    def test_tests_known_only_by_month_match_anywhere_in_it(self) -> None:
        # Bangladesh v England is scheduled for "February 2027" only.
        tests = [
            TestMatch("1", date(2027, 2, 10), date(2027, 2, 14), ("BAN", "ENG"), "Mirpur", "Dhaka", "BAN", "ENG", margin="7 wickets"),
            TestMatch("2", date(2027, 2, 18), date(2027, 2, 22), ("BAN", "ENG"), "Chattogram", "Chattogram", "BAN", None),
        ]
        warnings: list[str] = []
        found = wtc.match_cricsheet(self.cycle, tests, warnings)
        self.assertEqual(warnings, [])
        self.assertEqual((found["ban-eng-2027-1"].kind, found["ban-eng-2027-2"].kind), ("visitor", "draw"))

    def test_tests_outside_the_championship_are_ignored(self) -> None:
        # The MCG's 150th anniversary Test (March 2027) is not a championship Test.
        tests = [TestMatch("1", date(2027, 3, 11), date(2027, 3, 15), ("AUS", "ENG"), "Melbourne Cricket Ground", "Melbourne", "AUS", "AUS")]
        warnings: list[str] = []
        self.assertEqual(wtc.match_cricsheet(self.cycle, tests, warnings), {})
        self.assertEqual(warnings, [])

    def test_cricsheet_awarded_tests_count_as_awarded(self) -> None:
        tests = [TestMatch("1", date(2026, 12, 9), date(2026, 12, 13), ("AUS", "NZ"), "Perth Stadium", "Perth", "AUS", "AUS", awarded=True)]
        found = wtc.match_cricsheet(self.cycle, tests, [])
        self.assertEqual((found["aus-nz-2026-1"].kind, found["aus-nz-2026-1"].winner), ("awarded", "AUS"))

    def test_cricketdata_status_text(self) -> None:
        fixture = next(f for f in self.cycle.fixtures if f.key == "nz-ind-2026-1")
        read = lambda text: wtc.parse_cricdata_status(self.cycle, fixture, text)
        self.assertEqual((read("India won by 8 wkts").kind, read("India won by 8 wkts").margin), ("visitor", "8 wickets"))
        self.assertEqual(read("New Zealand won by an innings and 31 runs").kind, "host")
        self.assertEqual(read("Match drawn").kind, "draw")
        self.assertEqual(read("Match tied").kind, "tie")
        self.assertEqual(read("Match abandoned without a ball bowled").kind, "abandoned")
        self.assertIsNone(read("Stumps - Day 4"))
        self.assertIsNone(read(""))
        # A win is read first, whatever else the text mentions.
        self.assertEqual(read("India won by 3 wkts after a tied first innings").kind, "visitor")
        self.assertEqual(read("New Zealand won by 5 wkts (draw avoided on day 5)").kind, "host")
        # An unfit pitch, an award or a forfeit changes the points: left to the config.
        self.assertIsNone(read("Match abandoned due to an unfit pitch"))
        self.assertIsNone(read("Match awarded to India"))

    def test_cricketdata_fills_lagging_results_and_live_tests(self) -> None:
        pending = [f for f in self.cycle.fixtures if f.key in ("nz-ind-2026-1", "sa-ban-2026-1")]
        calls = []

        class Response:
            def __init__(self, payload):
                self.payload, self.ok, self.status_code = payload, True, 200

            def json(self):
                return self.payload

        class Session:
            def get(self, url, params, timeout):
                calls.append((url.rsplit("/", 1)[-1], params.get("id") or params.get("offset")))
                if url.endswith("/series"):
                    return Response({"status": "success", "data": [
                        {"id": "s-women", "name": "India Women tour of New Zealand, 2026"},
                        {"id": "s-nz", "name": "India tour of New Zealand, 2026-27"},
                        {"id": "s-sa", "name": "Bangladesh tour of South Africa, 2026"},
                    ]})
                if params["id"] == "s-nz":
                    return Response({"status": "success", "data": {"matchList": [
                        {"name": "New Zealand vs India, 1st Test", "matchType": "test", "teams": ["New Zealand", "India"], "dateTimeGMT": "2026-11-18T22:00:00", "status": "Day 3: Stumps", "matchStarted": True, "matchEnded": False},
                        {"name": "New Zealand vs India, 1st T20I", "matchType": "t20", "teams": ["New Zealand", "India"], "dateTimeGMT": "2026-11-19T06:00:00", "status": "India won by 4 wkts", "matchStarted": True, "matchEnded": True},
                    ]}})
                return Response({"status": "success", "data": {"matchList": [
                    {"name": "South Africa vs Bangladesh, 1st Test", "matchType": "test", "teams": ["South Africa", "Bangladesh"], "date": "2026-11-15", "status": "South Africa won by 9 wkts", "matchStarted": True, "matchEnded": True},
                ]}})

        warnings: list[str] = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"CRICDATA_API_KEY": "test-key"}):
            results, live = wtc.fetch_cricdata(self.cycle, pending, NOW, Path(tmp), warnings, Session())
            cached = json.loads((Path(tmp) / "cricketdata-wtc-series.json").read_text())
        self.assertEqual(warnings, [])
        self.assertEqual(results["sa-ban-2026-1"].kind, "host")
        self.assertEqual(results["sa-ban-2026-1"].source, "CricketData")
        self.assertNotIn("nz-ind-2026-1", results)
        self.assertEqual(live["nz-ind-2026-1"].status, "Day 3: Stumps")
        self.assertEqual(cached, {"nz-ind-2026": "s-nz", "sa-ban-2026": "s-sa"})

    def test_cricketdata_finds_a_series_named_by_its_season(self) -> None:
        series = next(item for item in self.cycle.series if item.id == "nz-sl-2027")

        class Session:
            def get(self, url, params, timeout):
                class Response:
                    ok, status_code = True, 200

                    def json(self):
                        return {"status": "success", "data": [{"id": "s1", "name": "Sri Lanka tour of New Zealand, 2026-27"}]}

                return Response()

        self.assertEqual(wtc.find_cricdata_series(self.cycle, series, Session(), "key", {}), "s1")

    def test_no_cricketdata_key_means_no_calls(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(wtc.fetch_cricdata(self.cycle, self.cycle.fixtures[:2], NOW, Path("."), [], session=object()), ({}, {}))


class ModelTests(unittest.TestCase):
    def test_home_advantage_follows_the_ground_not_the_series(self) -> None:
        ratings = flat_ratings(["PAK", "SL"])
        at_home = ratings.probabilities("PAK", "SL", "PAK")
        neutral = ratings.probabilities("PAK", "SL", "UAE")
        away = ratings.probabilities("PAK", "SL", "SL")
        self.assertGreater(at_home[0], at_home[2])
        self.assertAlmostEqual(neutral[0], neutral[2])
        self.assertAlmostEqual(away[0], at_home[2])
        config = mini_config([series("p-s", "AAA", "BBB", ["2026-03-01"], test={"country": "UAE"})])
        fixture = wtc.parse_config(config).fixtures[0]
        self.assertTrue(fixture.neutral)
        self.assertEqual(fixture.host, "AAA")

    def test_scores(self) -> None:
        self.assertAlmostEqual(wtc_model.ranked_probability_score((1.0, 0.0, 0.0), wtc_model.WIN), 0.0)
        self.assertAlmostEqual(wtc_model.ranked_probability_score((0.0, 0.0, 1.0), wtc_model.WIN), 1.0)
        self.assertAlmostEqual(wtc_model.ranked_probability_score((0.5, 0.0, 0.5), wtc_model.DRAW), 0.25)
        self.assertAlmostEqual(wtc_model.log_loss((0.5, 0.25, 0.25), wtc_model.DRAW), 1.3862943611)

    def test_fit_rates_a_dominant_side_higher_and_draws_by_country(self) -> None:
        tests = []
        day = date(2023, 1, 1)
        for index in range(60):
            day += timedelta(days=10)
            # AAA beat BBB everywhere; Tests in CCC's country are mostly drawn.
            country = "AAA" if index % 2 else "BBB"
            tests.append(TestMatch(str(index), day, day + timedelta(days=4), ("AAA", "BBB"), "x", None, country, "AAA" if index % 3 else None))
            tests.append(TestMatch(f"c{index}", day, day + timedelta(days=4), ("CCC", "BBB"), "y", None, "CCC", None if index % 4 else "CCC"))
        ratings = wtc_model.fit(tests, day + timedelta(days=30))
        self.assertGreater(ratings.rating["AAA"], ratings.rating["BBB"])
        self.assertGreater(ratings.probabilities("CCC", "BBB", "CCC")[1], ratings.probabilities("AAA", "BBB", "BBB")[1])

    def test_every_test_ground_in_the_archive_has_a_country(self) -> None:
        archive = ROOT / ".cache" / "cricsheet" / "tests_male_json.zip"
        if not archive.exists():
            self.skipTest("Cricsheet Test archive not cached")
        missing = [(test.venue, test.city) for test in wtc_model.load_tests(archive) if test.country is None]
        self.assertEqual(missing, [])


def brute_force(cycle: wtc.Cycle, rows: dict[str, wtc.Row], remaining: list[wtc.Remaining]) -> dict[str, dict[str, bool]]:
    """Every completion of the remaining Tests (win, loss, draw, tie): who can be where."""
    rules = cycle.rules
    teams = list(cycle.teams)
    played = {team: rows[team].played + sum(team in (g.host, g.visitor) for g in remaining) for team in teams}
    facts = {team: {"always_top": True, "always_top_or_level": True, "can_top": False, "can_level": False} for team in teams}
    outcomes = [(rules.win, rules.loss), (rules.loss, rules.win), (rules.draw, rules.draw), (rules.tie, rules.tie)]
    for combo in itertools.product(outcomes, repeat=len(remaining)):
        points = {team: rows[team].points for team in teams}
        for game, (host, visitor) in zip(remaining, combo):
            points[game.host] += host
            points[game.visitor] += visitor
        pct = {team: Fraction(points[team], played[team]) for team in teams}
        for team in teams:
            above = sum(pct[other] > pct[team] for other in teams if other != team)
            at_least = sum(pct[other] >= pct[team] for other in teams if other != team)
            if at_least >= 2:
                facts[team]["always_top"] = False
            if above >= 2:
                facts[team]["always_top_or_level"] = False
            if at_least <= 1:
                facts[team]["can_top"] = True
            if above <= 1:
                facts[team]["can_level"] = True
    return facts


class ExactClaimTests(unittest.TestCase):
    def random_case(self, rng: random.Random):
        teams = ("AAA", "BBB", "CCC", "DDD", "EEE")[: rng.choice([4, 5])]
        pairs = list(itertools.combinations(teams, 2))
        rng.shuffle(pairs)
        config = mini_config([], teams=teams)
        cycle = wtc.parse_config(config)
        rows = {}
        for team in teams:
            played = rng.randint(2, 8)
            # Points from W/L/D/T combinations, less an occasional deduction.
            points = sum(rng.choice([12, 0, 4, 6, 0, 12]) for _ in range(played)) - rng.choice([0, 0, 0, 1, 3])
            rows[team] = wtc.Row(team, played=played, points_won=points + 3, deducted=3)
        remaining = []
        for index in range(rng.randint(2, 6)):
            host, visitor = pairs[index % len(pairs)]
            remaining.append(wtc.Remaining(f"g{index}", host, visitor))
        return cycle, rows, remaining

    def test_claims_agree_with_brute_force(self) -> None:
        rng = random.Random(11)
        for case in range(120):
            cycle, rows, remaining = self.random_case(rng)
            truth = brute_force(cycle, rows, remaining)
            claims = wtc.needs(cycle, rows, remaining)
            for team, entry in claims.items():
                facts = truth[team]
                status = entry["status"]
                message = f"case {case} {team} {status} {facts} {rows[team]} {remaining}"
                if status == "clinched":
                    self.assertTrue(facts["always_top"], message)
                elif status == "clinched-unless-level":
                    self.assertTrue(facts["always_top_or_level"] and not facts["always_top"], message)
                else:
                    self.assertFalse(facts["always_top_or_level"], message)
                if status == "eliminated":
                    self.assertFalse(facts["can_level"], message)
                elif status == "level-only":
                    self.assertTrue(facts["can_level"] and not facts["can_top"], message)
                elif status in ("needs-help", "in-control"):
                    self.assertTrue(facts["can_top"], message)

    def test_statements_say_level_when_a_tie_breaker_decides(self) -> None:
        cycle = wtc.parse_config(mini_config([], teams=("AAA", "BBB", "CCC")))
        # AAA are done on 50%. If BBB beat CCC in the last Test all three finish on 50%;
        # any other result puts CCC above and BBB below AAA.
        rows = {
            "AAA": wtc.Row("AAA", played=1, points_won=6),
            "BBB": wtc.Row("BBB", played=1, points_won=0),
            "CCC": wtc.Row("CCC", played=1, points_won=12),
        }
        remaining = [wtc.Remaining("g", "BBB", "CCC")]
        claims = wtc.needs(cycle, rows, remaining)
        self.assertEqual(claims["AAA"]["status"], "clinched-unless-level")
        self.assertEqual(claims["CCC"]["status"], "clinched-unless-level")
        self.assertEqual(claims["BBB"]["status"], "level-only")
        self.assertIn("tie-breaker", wtc.need_statements(cycle, claims["AAA"], "AAA")[0])
        self.assertIn("level on PCT", wtc.need_statements(cycle, claims["BBB"], "BBB")[0])
        # Without the tie the claims firm up: a CCC side two wins up has clinched.
        rows["CCC"] = wtc.Row("CCC", played=2, points_won=24)
        claims = wtc.needs(cycle, rows, remaining)
        self.assertEqual(claims["CCC"]["status"], "clinched")

    def test_a_finished_table_is_settled_by_its_tie_breakers(self) -> None:
        cycle = wtc.parse_config(mini_config([], teams=("AAA", "BBB", "CCC"), rankings={"order": ["CCC", "BBB", "AAA"]}))
        rows = {
            "AAA": wtc.Row("AAA", played=2, points_won=24),
            "BBB": wtc.Row("BBB", played=2, points_won=12, series_won=2),
            "CCC": wtc.Row("CCC", played=2, points_won=12, series_won=1),
        }
        claims = wtc.needs(cycle, rows, [])
        # BBB and CCC are level on PCT, but series wins decide it: no "level" left.
        self.assertEqual({team: claims[team]["status"] for team in rows}, {"AAA": "clinched", "BBB": "clinched", "CCC": "eliminated"})
        # Level on PCT, series wins and away PCT: the ICC ranking decides, and it can still change.
        rows["BBB"].series_won = 1
        claims = wtc.needs(cycle, rows, [])
        self.assertEqual((claims["CCC"]["status"], claims["BBB"]["status"]), ("clinched-unless-level", "level-only"))
        self.assertIn("ICC Test ranking", wtc.need_statements(cycle, claims["BBB"], "BBB")[0])

    def test_live_table_claims_on_20_november_2026(self) -> None:
        cycle = wtc.parse_config(CONFIG)
        results = official_results(cycle)
        rows = wtc.table(cycle, results)
        states = wtc.classify(cycle, results, {}, date(2026, 11, 21))
        fixtures = {f.key: f for f in cycle.fixtures}
        remaining = [wtc.Remaining(key, fixtures[key].host, fixtures[key].visitor) for key, state in states.items() if state != "result"]
        claims = wtc.needs(cycle, rows, remaining)
        # West Indies have no Tests left on 27.38%; Pakistan's best is 25.64% (ICC and Wikipedia agree).
        self.assertEqual(claims["WI"]["status"], "eliminated")
        self.assertEqual(claims["PAK"]["status"], "eliminated")
        self.assertEqual(claims["PAK"]["bestPct"], 25.64)
        # Sri Lanka's best is 42.36%, below South Africa's worst (42.86%), and Australia and
        # New Zealand, who meet four times, cannot both finish below it.
        self.assertEqual(claims["SL"]["bestPct"], 42.36)
        self.assertEqual(claims["SA"]["worstPct"], 42.86)
        self.assertEqual(claims["SL"]["status"], "eliminated")
        for team in ("SA", "NZ", "AUS"):
            self.assertEqual(claims[team]["status"], "in-control", team)


class SimulationTests(unittest.TestCase):
    def build(self, now: datetime = NOW, config: dict | None = None, tests: list[dict] | None = None, simulations: int = 2000) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            archive = write_tests_archive(Path(tmp), tests if tests is not None else history())
            with mock.patch.dict("os.environ", {}, clear=False) as env:
                env.pop("CRICDATA_API_KEY", None)
                env.pop("CRICAPI_KEY", None)
                return wtc.build_payload(config or CONFIG, now, Path(tmp) / "fixtures", archive=archive, simulations=simulations)

    def test_live_payload_is_consistent(self) -> None:
        payload = self.build()
        analysis = payload["analysis"]
        probabilities = analysis["probabilities"]
        self.assertEqual(payload["metadata"]["season_status"], "league_stage")
        self.assertAlmostEqual(sum(item["final"] for item in probabilities.values()), 200, delta=0.2)
        self.assertAlmostEqual(sum(item["title"] + item["joint"] / 2 for item in probabilities.values()), 100, delta=0.2)
        for team, values in analysis["positions"].items():
            self.assertAlmostEqual(sum(values), 100, delta=0.2)
            self.assertLessEqual(probabilities[team]["champion"], probabilities[team]["final"] + 1e-9)
            need = analysis["needs"][team]
            if need["status"] == "eliminated":
                self.assertEqual(probabilities[team]["final"], 0.0, team)
            if need["status"] == "clinched":
                self.assertEqual(probabilities[team]["final"], 100.0, team)
        # The config's four lagging results and seven deductions give the ICC's table.
        table = {row["teamKey"]: (row["played"], row["deducted"], row["points"], row["pct"]) for row in payload["standings"]}
        for team, played, _, _, _, deducted, points, pct in OFFICIAL_TABLE:
            self.assertEqual(table[team], (played, deducted, points, pct), team)
        # The Test under way in Wellington is shown, not counted.
        nz = next(item for item in payload["series"] if item["id"] == "nz-ind-2026")
        self.assertEqual(nz["tests"][0]["state"], "in_progress")
        self.assertNotIn("result", nz["tests"][0])
        self.assertEqual(payload["fixtures"][0]["state"], "in_progress")
        for match in analysis["swing"]:
            values = [v for v in (match["ifHost"], match["ifDraw"], match["ifVisitor"]) if v is not None]
            self.assertAlmostEqual(match["swing"], max(values) - min(values), places=1)
        self.assertEqual([column["key"] for column in payload["league"]["columns"]][-1], "pct")
        self.assertEqual(payload["league"]["engine"], "wtc")
        self.assertIn("ODC-By", payload["metadata"]["license"])

    def test_a_day_without_cricket_changes_nothing(self) -> None:
        # Nothing finishes or starts between 21 and 22 November 2026: the nightly build writes nothing.
        first = self.build(datetime(2026, 11, 21, 19, 30, tzinfo=timezone.utc), simulations=500)
        second = self.build(datetime(2026, 11, 22, 7, 0, tzinfo=timezone.utc), simulations=500)
        self.assertTrue(extract_table.same_content(first, second))
        # The next Test's first morning is a real change (it is shown as under way).
        third = self.build(datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc), simulations=500)
        self.assertFalse(extract_table.same_content(first, third))

    def test_pre_season_state(self) -> None:
        config = copy.deepcopy(CONFIG)
        config["results"] = []
        payload = self.build(datetime(2025, 6, 1, tzinfo=timezone.utc), config, tests=history(until=date(2025, 6, 1)))
        self.assertEqual(payload["metadata"]["season_status"], "pre_season")
        self.assertTrue(all(row["pct"] is None for row in payload["standings"]))
        self.assertAlmostEqual(sum(item["final"] for item in payload["analysis"]["probabilities"].values()), 200, delta=0.2)

    def test_final_settled_then_won_or_shared(self) -> None:
        config = copy.deepcopy(CONFIG)
        # Every remaining Test is a home win, recorded in the config.
        cycle = wtc.parse_config(CONFIG)
        done = {item["test"] for item in OFFICIAL["results"]}
        config["results"] = [{"test": item["test"], "result": item["result"], "source": "ICC"} for item in OFFICIAL["results"]]
        config["results"] += [{"test": f.key, "result": "host", "source": "test"} for f in cycle.fixtures if f.key not in done]
        payload = self.build(datetime(2027, 5, 15, tzinfo=timezone.utc), config)
        self.assertEqual(payload["metadata"]["season_status"], "playoffs")
        finalists = payload["final"]["finalists"]
        self.assertEqual(finalists, [row["teamKey"] for row in payload["standings"][:2]])
        odds = payload["final"]["odds"]
        self.assertAlmostEqual(odds[finalists[0]] + odds["draw"] + odds[finalists[1]], 100, delta=0.05)
        probabilities = payload["analysis"]["probabilities"]
        for team, values in probabilities.items():
            self.assertEqual(values["final"], 100.0 if team in finalists else 0.0)
        self.assertAlmostEqual(sum(v["joint"] for v in probabilities.values()) / 2, odds["draw"], delta=2.5)
        a, b = finalists
        names = {key: team["fullName"] for key, team in cycle.teams.items()}
        final = {"teams": [names[a], names[b]], "dates": ["2027-06-09", "2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13", "2027-06-14"], "venue": "Kennington Oval, London", "city": "London", "event": {"name": "ICC World Test Championship"}}
        won = self.build(datetime(2027, 6, 20, tzinfo=timezone.utc), config, tests=history() + [{**final, "outcome": {"winner": names[b], "by": {"runs": 50}}}])
        self.assertEqual(won["metadata"]["season_status"], "complete")
        self.assertEqual(won["playoffs"], {"champion": b, "jointChampions": None})
        self.assertEqual(won["analysis"]["probabilities"][b]["title"], 100.0)
        self.assertEqual(won["final"]["result"]["kind"], "win")
        shared = self.build(datetime(2027, 6, 20, tzinfo=timezone.utc), config, tests=history() + [{**final, "outcome": {"result": "draw"}}])
        self.assertEqual(shared["playoffs"]["jointChampions"], finalists)
        self.assertEqual(shared["final"]["result"]["kind"], "joint")
        entry = extract_table.index_entry(shared)
        self.assertEqual(entry["champion"], f"{a} & {b}")
        self.assertEqual(entry["status"], "complete")
        # As soon as the last Test is in, before the window closes, the final is settled.
        early = self.build(datetime(2027, 3, 20, tzinfo=timezone.utc), config, simulations=500)
        self.assertEqual((early["metadata"]["season_status"], early["final"]["finalists"]), ("playoffs", finalists))
        # A tied (or abandoned) final recorded in the config: joint champions too (Regulation 10.4).
        tied = copy.deepcopy(config)
        tied["final"]["result"] = {"result": "tie", "source": "test"}
        self.assertEqual(self.build(datetime(2027, 6, 20, tzinfo=timezone.utc), tied)["playoffs"]["jointChampions"], finalists)

    def test_final_from_cricketdata_while_cricsheet_lags(self) -> None:
        config = copy.deepcopy(CONFIG)
        cycle = wtc.parse_config(CONFIG)
        done = {item["test"] for item in OFFICIAL["results"]}
        config["results"] = [{"test": item["test"], "result": item["result"], "source": "ICC"} for item in OFFICIAL["results"]]
        config["results"] += [{"test": f.key, "result": "host", "source": "test"} for f in cycle.fixtures if f.key not in done]
        settled = self.build(datetime(2027, 5, 1, tzinfo=timezone.utc), config, simulations=200)
        a, b = settled["final"]["finalists"]
        names = {key: team["fullName"] for key, team in cycle.teams.items()}

        def session(ended: bool):
            class Response:
                ok, status_code = True, 200

                def __init__(self, payload):
                    self.payload = payload

                def json(self):
                    return self.payload

            class Session:
                def get(self, url, params, timeout):
                    if url.endswith("/series"):
                        return Response({"status": "success", "data": [{"id": "f", "name": "ICC World Test Championship Final, 2027"}]})
                    status = f"{names[b]} won by 5 wkts" if ended else "Day 2: Stumps"
                    return Response({"status": "success", "data": {"matchList": [
                        # The finalists' round-stage meeting in the same list is not the final.
                        {"matchType": "test", "teams": [names[a], names[b]], "date": "2027-02-11", "status": f"{names[a]} won by 9 wkts", "matchStarted": True, "matchEnded": True},
                        {"matchType": "test", "teams": [names[a], names[b]], "date": "2027-06-09", "status": status, "matchStarted": True, "matchEnded": ended},
                    ]}})

            return Session()

        def build(now, ended):
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"CRICDATA_API_KEY": "test-key"}):
                archive = write_tests_archive(Path(tmp), history())
                return wtc.build_payload(config, now, Path(tmp) / "fixtures", archive=archive, simulations=200, session=session(ended))

        live = build(datetime(2027, 6, 10, 12, tzinfo=timezone.utc), False)
        self.assertEqual((live["metadata"]["season_status"], live["final"]["live"]), ("playoffs", "Day 2: Stumps"))
        won = build(datetime(2027, 6, 14, 12, tzinfo=timezone.utc), True)
        self.assertEqual(won["metadata"]["season_status"], "complete")
        self.assertEqual(won["playoffs"]["champion"], b)
        self.assertIn("CricketData", won["metadata"]["source"])


def history(until: date = date(2026, 11, 3)) -> list[dict]:
    """Cricsheet-style records of the cycle's results so far (from the ICC fixture) plus older Tests for ratings."""
    cycle = wtc.parse_config(CONFIG)
    names = {key: team["fullName"] for key, team in cycle.teams.items()}
    fixtures = {f.key: f for f in cycle.fixtures}
    records = []
    rng = random.Random(3)
    day = date(2021, 1, 1)
    pairs = list(itertools.combinations(names, 2))
    while day < date(2025, 5, 1):
        a, b = rng.choice(pairs)
        outcome = rng.choice([{"winner": names[a], "by": {"runs": 10}}, {"winner": names[b], "by": {"wickets": 3}}, {"result": "draw"}])
        city = {"AUS": "Sydney", "ENG": "London", "IND": "Mumbai", "NZ": "Wellington", "PAK": "Lahore", "SA": "Durban", "SL": "Galle", "WI": "Kingston", "BAN": "Dhaka"}[a]
        records.append({"teams": [names[a], names[b]], "dates": [day.isoformat()], "venue": "Ground", "city": city, "outcome": outcome})
        day += timedelta(days=9)
    for item in OFFICIAL["results"]:
        fixture = fixtures[item["test"]]
        if fixture.end >= until or item["test"] in {r.fixture for r in cycle.results}:
            continue
        kind = item["result"]
        outcome = {"result": "draw"} if kind == "draw" else {"winner": names[fixture.host if kind == "host" else fixture.visitor], "by": {"runs": 1}}
        city = {"AUS": "Sydney", "ENG": "London", "IND": "Mumbai", "NZ": "Wellington", "PAK": "Lahore", "SA": "Durban", "SL": "Galle", "WI": "Kingston", "BAN": "Dhaka"}[fixture.host]
        records.append({"teams": [names[fixture.host], names[fixture.visitor]], "dates": [fixture.start.isoformat()], "venue": fixture.venue or "Ground", "city": city, "outcome": outcome})
    return records


class PipelineTests(unittest.TestCase):
    def test_planner_builds_the_cycle_while_it_is_on(self) -> None:
        on = extract_table.league_plan(datetime(2026, 11, 21, 19, 30, tzinfo=timezone.utc))
        self.assertIn(("wtc-2025-27", "feed"), on)
        # Still rebuilt while Cricsheet adds the final, then left alone.
        self.assertIn(("wtc-2025-27", "feed"), extract_table.league_plan(datetime(2027, 7, 10, tzinfo=timezone.utc)))
        self.assertNotIn(("wtc-2025-27", "feed"), extract_table.league_plan(datetime(2027, 9, 1, tzinfo=timezone.utc)))

    def test_index_entry_and_facts(self) -> None:
        payload = SimulationTests().build(simulations=1000)
        entry = extract_table.index_entry(payload)
        self.assertEqual((entry["sport"], entry["engine"], entry["shortName"]), ("cricket", "wtc", "WTC"))
        self.assertEqual([fact["label"] for fact in entry["facts"]], ["Likely final", "Title favourite"])
        probabilities = payload["analysis"]["probabilities"]
        favourite = max(probabilities, key=lambda team: probabilities[team]["title"])
        self.assertTrue(entry["facts"][1]["value"].startswith(favourite))
        self.assertTrue(entry["started"])

    def test_movement_uses_every_tier(self) -> None:
        payload = SimulationTests().build(simulations=500)
        previous = copy.deepcopy(payload)
        previous["standings"][0]["played"] -= 1
        team = payload["standings"][0]["teamKey"]
        previous["analysis"]["probabilities"][team]["final"] -= 5
        import team_sports

        movement = team_sports.probability_movement(previous, payload)
        self.assertAlmostEqual(movement["changes"][team]["final"], 5, places=2)


if __name__ == "__main__":
    unittest.main()
