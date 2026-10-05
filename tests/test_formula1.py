"""Formula 1 (formula1.py): championship tables, points rules, the pace model and the simulation.

tests/fixtures/f1-2025.json and f1-2026.json are compact copies of the Jolpica F1 API's
downloads (https://api.jolpi.ca/ergast/f1/{season}/races, results, sprint, driverstandings and
constructorstandings) made on 4 October 2026, after round 16 of 2026. ``load_season_fixture``
writes them back into a cache directory in Jolpica's shape, so these tests run offline.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import requests

import extract_table
import formula1
import leagues
import team_sports

FIXTURES = Path(__file__).parent / "fixtures"
UTC = timezone.utc
NOW_2026 = datetime(2026, 10, 4, 21, tzinfo=UTC)
CONFIG = leagues.read_config("f1")

# Official standings, position by position: (driver code or team, points, wins).
# 2026 after round 16 (Bahrain Grand Prix in Malaysia, 4 October 2026):
#   formula1.com https://www.formula1.com/en/results/2026/drivers and /2026/team (points and order);
#   Jolpica https://api.jolpi.ca/ergast/f1/2026/driverstandings/ and /constructorstandings/ (points, order, wins).
# Countback decides NOR/VER on 188 (2 wins to 1), HUL/OCO/ALO/SAI on 7 and STR/BOT/PER on 0.
OFFICIAL_2026_DRIVERS = [
    ("ANT", 320, 8), ("RUS", 236, 3), ("HAM", 214, 1), ("LEC", 191, 1), ("NOR", 188, 2), ("VER", 188, 1),
    ("PIA", 128, 0), ("HAD", 96, 0), ("LAW", 65, 0), ("GAS", 41, 0), ("LIN", 38, 0), ("COL", 27, 0),
    ("BEA", 20, 0), ("BOR", 10, 0), ("HUL", 7, 0), ("OCO", 7, 0), ("ALO", 7, 0), ("SAI", 7, 0),
    ("ALB", 5, 0), ("TSU", 1, 0), ("STR", 0, 0), ("BOT", 0, 0), ("PER", 0, 0),
]
OFFICIAL_2026_CONSTRUCTORS = [
    ("mercedes", 556, 11), ("ferrari", 405, 2), ("mclaren", 316, 2), ("red_bull", 298, 1), ("rb", 90, 0),
    ("alpine", 68, 0), ("haas", 27, 0), ("audi", 17, 0), ("williams", 12, 0), ("aston_martin", 7, 0), ("cadillac", 0, 0),
]
# 2025 final standings: formula1.com https://www.formula1.com/en/results/2025/drivers and /2025/team;
# Jolpica https://api.jolpi.ca/ergast/f1/2025/driverstandings/ and /constructorstandings/.
# Countback decides HUL/HAD on 51, LAW/OCO on 38, STR/TSU on 33 and COL/DOO on 0.
OFFICIAL_2025_DRIVERS = [
    ("NOR", 423, 7), ("VER", 421, 8), ("PIA", 410, 7), ("RUS", 319, 2), ("LEC", 242, 0), ("HAM", 156, 0),
    ("ANT", 150, 0), ("ALB", 73, 0), ("SAI", 64, 0), ("ALO", 56, 0), ("HUL", 51, 0), ("HAD", 51, 0),
    ("BEA", 41, 0), ("LAW", 38, 0), ("OCO", 38, 0), ("STR", 33, 0), ("TSU", 33, 0), ("GAS", 22, 0),
    ("BOR", 19, 0), ("COL", 0, 0), ("DOO", 0, 0),
]
OFFICIAL_2025_CONSTRUCTORS = [
    ("mclaren", 833, 14), ("mercedes", 469, 2), ("red_bull", 451, 8), ("ferrari", 398, 0), ("williams", 137, 0),
    ("rb", 92, 0), ("aston_martin", 89, 0), ("haas", 79, 0), ("sauber", 70, 0), ("alpine", 22, 0),
]


def jolpica_shape(data: dict) -> dict[str, dict]:
    """The compact fixture back in the shape of formula1.fetch_season's downloads."""
    season = str(data["season"])
    drivers, constructors = data["drivers"], data["constructors"]
    rounds = {row[0]: row for row in data["schedule"]}

    def race_block(round_number: int) -> dict:
        _, name, day, clock, circuit, locality, country, sprint_day, sprint_clock = rounds[round_number]
        block = {
            "season": season,
            "round": str(round_number),
            "raceName": name,
            "date": day,
            "time": clock,
            "Circuit": {"circuitName": circuit, "Location": {"locality": locality, "country": country}},
        }
        if sprint_day:
            block["Sprint"] = {"date": sprint_day, "time": sprint_clock}
        return block

    def results(key: str, rows_by_round: dict) -> dict:
        races = []
        for round_number, rows in rows_by_round.items():
            entries = []
            for order, (driver, constructor, text, points, status, grid, fastest) in enumerate(rows, start=1):
                code, given, family, number = drivers[driver]
                entry = {
                    "number": number,
                    "position": str(order),
                    "positionText": text,
                    "points": str(points),
                    "Driver": {"driverId": driver, "permanentNumber": number, "code": code, "givenName": given, "familyName": family},
                    "Constructor": {"constructorId": constructor, "name": constructors[constructor]},
                    "grid": str(grid),
                    "status": status,
                }
                if fastest:
                    entry["FastestLap"] = {"rank": str(fastest)}
                entries.append(entry)
            races.append({**race_block(int(round_number)), key: entries})
        return {"total": sum(len(rows) for rows in rows_by_round.values()), "Races": races}

    def standings(kind: str) -> dict:
        block = data[kind]
        key, inner = ("DriverStandings", "Driver") if kind == "driverstandings" else ("ConstructorStandings", "Constructor")
        id_key = "driverId" if inner == "Driver" else "constructorId"
        rows = [{"position": str(position), "points": str(points), "wins": str(wins), inner: {id_key: key_id}} for key_id, position, points, wins in block["rows"]]
        return {"total": 1, "StandingsLists": [{"season": season, "round": str(block["round"]), key: rows}]}

    return {
        "races": {"total": len(rounds), "Races": [race_block(round_number) for round_number in sorted(rounds)]},
        "results": results("Results", data["results"]),
        "sprint": results("SprintResults", data["sprint"]),
        "driverstandings": standings("driverstandings"),
        "constructorstandings": standings("constructorstandings"),
    }


def load_fixture(season: int) -> dict:
    return json.loads((FIXTURES / f"f1-{season}.json").read_text(encoding="utf-8"))


def write_cache(cache: Path, season: int) -> None:
    """A season's fixture as fresh downloads in ``cache``, so nothing is fetched."""
    folder = cache / "jolpica"
    folder.mkdir(parents=True, exist_ok=True)
    for endpoint, data in jolpica_shape(load_fixture(season)).items():
        (folder / f"{season}-{endpoint}.json").write_text(json.dumps(data), encoding="utf-8")


def season_data(season: int) -> formula1.SeasonData:
    shaped = jolpica_shape(load_fixture(season))
    return formula1.parse_season(season, shaped["races"], shaped["results"], shaped["sprint"])


def tables(season: int) -> tuple[dict, dict, list[str], list[str], formula1.SeasonData]:
    data = season_data(season)
    drivers, constructors, _ = formula1.championship(data.events, formula1.PointsRules.from_config(CONFIG, season))
    return drivers, constructors, formula1.ranked_keys(drivers), formula1.ranked_keys(constructors), data


def offline_download(season: int, endpoint: str) -> dict:
    raise requests.ConnectionError(f"offline: {season} {endpoint}")


class StandingsTests(unittest.TestCase):
    def assert_matches(self, season: int, official_drivers: list, official_constructors: list) -> None:
        drivers, constructors, driver_order, team_order, data = tables(season)
        codes = [data.drivers[key].code for key in driver_order]
        self.assertEqual(codes, [code for code, _, _ in official_drivers])
        for key, (code, points, wins) in zip(driver_order, official_drivers):
            with self.subTest(driver=code):
                self.assertEqual(drivers[key].points, points)
                self.assertEqual(drivers[key].wins, wins)
        self.assertEqual(team_order, [team for team, _, _ in official_constructors])
        for key, (_, points, wins) in zip(team_order, official_constructors):
            with self.subTest(team=key):
                self.assertEqual(constructors[key].points, points)
                self.assertEqual(constructors[key].wins, wins)

    def test_2026_tables_match_the_official_standings_after_round_16(self) -> None:
        self.assert_matches(2026, OFFICIAL_2026_DRIVERS, OFFICIAL_2026_CONSTRUCTORS)

    def test_2025_final_tables_match_the_official_standings(self) -> None:
        self.assert_matches(2025, OFFICIAL_2025_DRIVERS, OFFICIAL_2025_CONSTRUCTORS)

    def test_the_published_standings_agree_with_the_computed_tables(self) -> None:
        for season in (2025, 2026):
            drivers, constructors, driver_order, team_order, _ = tables(season)
            shaped = jolpica_shape(load_fixture(season))
            for kind, rows, order in (("drivers", drivers, driver_order), ("constructors", constructors, team_order)):
                _, published = formula1.published_standings(shaped[f"{kind[:-1]}standings"], kind)
                self.assertEqual(formula1.standings_differences(rows, order, published), [], f"{season} {kind}")

    def test_a_published_table_that_disagrees_is_reported(self) -> None:
        drivers, _, order, _, _ = tables(2026)
        _, published = formula1.published_standings(jolpica_shape(load_fixture(2026))["driverstandings"], "drivers")
        published[0] = dict(published[0], points=321.0)
        self.assertIn("antonelli: 320 pts, 8 wins; published 321 pts, 8 wins", formula1.standings_differences(drivers, order, published))
        swapped = [published[1], published[0], *published[2:]]
        swapped = [dict(item, points=drivers[item["key"]].points) for item in swapped]
        self.assertTrue(formula1.standings_differences(drivers, order, swapped)[0].startswith("order differs"))

    def test_the_published_order_settles_drivers_level_on_points(self) -> None:
        drivers, _, order, _, _ = tables(2026)
        data = jolpica_shape(load_fixture(2026))["driverstandings"]
        rows = data["StandingsLists"][0]["DriverStandings"]
        first = next(i for i, row in enumerate(rows) if row["Driver"]["driverId"] == "hulkenberg")
        second = next(i for i, row in enumerate(rows) if row["Driver"]["driverId"] == "ocon")
        rows[first], rows[second] = rows[second], rows[first]
        warnings: list[str] = []
        agreed = formula1.check_published("drivers", drivers, order, data, 16, warnings)
        self.assertEqual(warnings, [])
        self.assertLess(agreed.index("ocon"), agreed.index("hulkenberg"))
        # Published standings of another round are not compared; a points difference is a warning.
        self.assertIsNone(formula1.check_published("drivers", drivers, order, data, 15, warnings))
        rows[0]["points"] = "321"
        self.assertIsNone(formula1.check_published("drivers", drivers, order, data, 16, warnings))
        self.assertIn("differs from Jolpica F1 API's published standings", warnings[0])

    def test_the_2026_entry_list_has_eleven_teams(self) -> None:
        _, constructors, _, _, data = tables(2026)
        self.assertEqual(len(constructors), 11)
        self.assertIn("cadillac", constructors)
        self.assertIn("audi", constructors)
        self.assertNotIn("sauber", constructors)
        latest = [event for event in data.events if event.done][-1]
        self.assertEqual(len(latest.entries), 22)


def event(kind: str, rows: list[tuple[str, str, str, str]], round_number: int = 1, season: int = 2026, published: dict | None = None) -> formula1.Event:
    """A toy event: (driver, team, positionText, status) in classification order."""
    entries = []
    for order, (driver, team, text, status) in enumerate(rows, start=1):
        entries.append(
            formula1.Entry(
                driver=driver,
                constructor=team,
                order=order,
                position=int(text) if text.isdigit() and status != "Disqualified" else None,
                position_text="D" if status == "Disqualified" else text,
                status=status,
                points=(published or {}).get(driver, 0.0),
                fastest_lap_rank=None,
            )
        )
    return formula1.Event(season, round_number, kind, "Toy Grand Prix", datetime(season, 3, round_number, tzinfo=UTC), tuple(entries))


def scored(rows: list[tuple[str, str, str, str]], kind: str = "race", rules: formula1.PointsRules = formula1.PointsRules()) -> dict[str, float]:
    toy = event(kind, rows)
    expected = {entry.driver: rules.points(toy, entry) for entry in toy.entries}
    return expected


class PointsRulesTests(unittest.TestCase):
    def test_race_and_sprint_points(self) -> None:
        rows = [(f"d{place}", "team", str(place), "Finished") for place in range(1, 13)]
        race = scored(rows)
        self.assertEqual([race[f"d{place}"] for place in range(1, 12)], [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0])
        sprint = scored(rows, kind="sprint")
        self.assertEqual([sprint[f"d{place}"] for place in range(1, 10)], [8, 7, 6, 5, 4, 3, 2, 1, 0])

    def test_unclassified_and_disqualified_cars_score_nothing(self) -> None:
        rows = [("a", "t", "1", "Finished"), ("b", "t", "R", "Retired"), ("c", "t", "3", "Disqualified")]
        self.assertEqual(scored(rows), {"a": 25.0, "b": 0.0, "c": 0.0})
        toy = event("race", rows)
        self.assertTrue(toy.entries[1].retired)
        self.assertFalse(toy.entries[2].retired)

    def test_the_fastest_lap_point_is_for_2019_to_2024_and_the_top_ten(self) -> None:
        self.assertEqual(formula1.PointsRules.from_config(CONFIG, 2024).fastest_lap, 1)
        self.assertEqual(formula1.PointsRules.from_config(CONFIG, 2025).fastest_lap, 0)
        self.assertEqual(formula1.PointsRules.from_config(CONFIG, 2026).fastest_lap, 0)
        rules = formula1.PointsRules.from_config(CONFIG, 2024)
        toy = event("race", [("a", "t", "1", "Finished"), ("b", "t", "11", "Finished")])
        fastest_in_top_ten = formula1.Entry("a", "t", 1, 1, "1", "Finished", 26.0, fastest_lap_rank=1)
        fastest_outside = formula1.Entry("b", "t", 2, 11, "11", "Finished", 0.0, fastest_lap_rank=1)
        self.assertEqual(rules.points(toy, fastest_in_top_ten), 26)
        self.assertEqual(rules.points(toy, fastest_outside), 0)
        self.assertEqual(formula1.PointsRules.from_config(CONFIG, 2026).points(toy, fastest_in_top_ten), 25)

    def test_a_shortened_race_is_scored_as_published(self) -> None:
        # Half distance: 19-14-12-... (Article A2.2.1, column 3); the results do not say how far they went.
        published = {"a": 19.0, "b": 14.0}
        toy = event("race", [("a", "t", "1", "Finished"), ("b", "u", "2", "Finished")], published=published)
        drivers, constructors, as_published = formula1.championship([toy], formula1.PointsRules())
        self.assertEqual(as_published, [toy])
        self.assertEqual((drivers["a"].points, drivers["b"].points, constructors["u"].points), (19.0, 14.0, 14.0))

    def test_countback_uses_race_places_only(self) -> None:
        # A: a sprint win and fifth in the race (8 + 10); B: second in the race (18). Level on 18:
        # B's second place beats A's fifth, because the sprint win does not count.
        sprint = event("sprint", [("a", "t", "1", "Finished"), ("b", "u", "9", "Finished")], published={"a": 8.0})
        race = event("race", [("x", "v", "1", "Finished"), ("b", "u", "2", "Finished"), ("y", "v", "3", "Finished"), ("z", "w", "4", "Finished"), ("a", "t", "5", "Finished")], published={"x": 25.0, "b": 18.0, "y": 15.0, "z": 12.0, "a": 10.0})
        drivers, _, _ = formula1.championship([sprint, race], formula1.PointsRules())
        self.assertEqual((drivers["a"].points, drivers["b"].points), (18.0, 18.0))
        self.assertEqual(drivers["a"].sprint_wins, 1)
        self.assertEqual(drivers["a"].wins, 0)
        order = formula1.ranked_keys(drivers)
        self.assertLess(order.index("b"), order.index("a"))

    def test_constructors_score_both_cars_and_a_driver_scores_for_each_team_he_drove_for(self) -> None:
        first = event("race", [("a", "t", "1", "Finished"), ("b", "t", "2", "Finished"), ("c", "u", "3", "Finished")], round_number=1, published={"a": 25.0, "b": 18.0, "c": 15.0})
        second = event("race", [("c", "t", "1", "Finished"), ("a", "u", "2", "Finished")], round_number=2, published={"c": 25.0, "a": 18.0})
        drivers, constructors, _ = formula1.championship([first, second], formula1.PointsRules())
        self.assertEqual(constructors["t"].points, 25 + 18 + 25)
        self.assertEqual(constructors["u"].points, 15 + 18)
        self.assertEqual(drivers["c"].points, 40)


class DownloadTests(unittest.TestCase):
    def test_pages_that_split_a_race_are_joined(self) -> None:
        page = lambda offset, rows: {"total": "3", "offset": str(offset), "RaceTable": {"Races": [{"season": "2026", "round": "5", "Results": rows}]}}  # noqa: E731
        merged = formula1._merge_pages([page(0, [{"position": "1"}, {"position": "2"}]), page(2, [{"position": "3"}])])
        self.assertEqual(len(merged["Races"]), 1)
        self.assertEqual([row["position"] for row in merged["Races"][0]["Results"]], ["1", "2", "3"])

    def test_a_failed_refresh_uses_the_cached_copy_and_no_copy_is_a_feed_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(formula1, "_download", side_effect=offline_download):
            cache = Path(folder)
            with self.assertRaises(team_sports.FeedError):
                formula1.fetch_season(2026, "results", cache)
            write_cache(cache, 2026)
            path = cache / "jolpica" / "2026-results.json"
            stale = time.time() - 24 * 3600
            os.utime(path, (stale, stale))
            self.assertEqual(len(formula1.fetch_season(2026, "results", cache)["Races"]), 16)

    def test_a_refresh_with_fewer_results_keeps_the_cached_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(formula1, "_download", return_value={"total": "0", "Races": []}), mock.patch("builtins.print"):
            cache = Path(folder)
            write_cache(cache, 2026)
            stale = time.time() - 24 * 3600
            for endpoint in ("results", "races"):
                path = cache / "jolpica" / f"2026-{endpoint}.json"
                os.utime(path, (stale, stale))
            self.assertEqual(len(formula1.fetch_season(2026, "results", cache)["Races"]), 16)
            # The calendar can lose a race (a cancellation), so a shorter one is taken.
            self.assertEqual(formula1.fetch_season(2026, "races", cache)["Races"], [])


class ModelTests(unittest.TestCase):
    def test_a_driver_who_always_wins_is_rated_fastest(self) -> None:
        events = []
        for round_number in range(1, 9):
            rows = [("ace", "red", "1", "Finished"), ("mate", "red", "2", "Finished"), ("mid", "blue", "3", "Finished"), ("back", "blue", "4", "Finished")]
            if round_number % 4 == 0:
                rows[3] = ("back", "blue", "R", "Retired")
            events.append(event("race", rows, round_number=round_number))
        model = formula1.fit_model(events, 2026)
        strength = {driver: model.strength(driver, team) for driver, team in (("ace", "red"), ("mate", "red"), ("mid", "blue"), ("back", "blue"))}
        self.assertEqual(sorted(strength, key=strength.get, reverse=True), ["ace", "mate", "mid", "back"])
        self.assertGreater(model.retirement("back"), model.retirement("ace"))
        self.assertTrue(all(0 < model.retirement(driver) < 1 for driver in strength))
        chances = formula1.win_probabilities(model, {"ace": "red", "mate": "red", "mid": "blue", "back": "blue"})
        self.assertAlmostEqual(sum(chances.values()), 1.0, places=3)
        self.assertEqual(max(chances, key=chances.get), "ace")

    def test_new_rules_carry_less_of_last_seasons_car(self) -> None:
        # Last season only: this season's cars are rated from last season's, carried over.
        events = [event("race", [("a", "fast", "1", "Finished"), ("b", "slow", "2", "Finished")], round_number=r, season=2025) for r in range(1, 6)]
        settings = formula1.ModelSettings()
        stable = formula1.fit_model(events, 2026, settings, new_rules=(), teams={"fast"})
        changed = formula1.fit_model(events, 2026, settings, new_rules={2026}, teams={"fast"})
        self.assertGreater(changed.car[("fast", 2025)], 0)
        self.assertAlmostEqual(stable.car_rating("fast"), settings.carryover * stable.car[("fast", 2025)], places=4)
        self.assertAlmostEqual(changed.car_rating("fast"), settings.carryover_new_rules * changed.car[("fast", 2025)], places=4)
        self.assertLess(changed.car_rating("fast"), stable.car_rating("fast"))


class PayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder = tempfile.TemporaryDirectory()
        cache = Path(cls.folder.name)
        write_cache(cache, 2025)
        write_cache(cache, 2026)
        with mock.patch.object(formula1, "_download", side_effect=offline_download):
            cls.payload = formula1.build_payload(CONFIG, NOW_2026, cache, simulations=4000)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.folder.cleanup()

    def test_the_payload_describes_the_2026_season(self) -> None:
        payload = self.payload
        self.assertEqual(payload["league"]["id"], "f1-2026")
        self.assertEqual(payload["league"]["sport"], "motorsport")
        self.assertEqual(payload["metadata"]["season_status"], "in_progress")
        self.assertEqual(payload["metadata"]["warnings"], [])
        self.assertEqual(payload["league"]["eventsLeft"], 8)
        self.assertEqual([row["shortName"] for row in payload["standings"]], [code for code, _, _ in OFFICIAL_2026_DRIVERS])
        self.assertEqual([row["teamKey"] for row in payload["constructorStandings"]], [team for team, _, _ in OFFICIAL_2026_CONSTRUCTORS])
        self.assertTrue(any("match Jolpica F1 API's published standings (drivers and constructors) after round 16" in note for note in payload["analysis"]["modelNotes"]))
        self.assertTrue(any("2026 brings new chassis and power-unit rules" in note for note in payload["analysis"]["modelNotes"]))
        tsunoda = next(row for row in payload["standings"] if row["shortName"] == "TSU")
        self.assertFalse(tsunoda["racing"])
        self.assertEqual(payload["results"][0]["podium"], ["max_verstappen", "antonelli", "hamilton"])

    def test_title_odds_sum_to_one_hundred(self) -> None:
        drivers = self.payload["analysis"]["probabilities"]
        teams = self.payload["analysis"]["constructorProbabilities"]
        self.assertAlmostEqual(sum(values["title"] for values in drivers.values()), 100, delta=0.1)
        self.assertAlmostEqual(sum(values["top3"] for values in drivers.values()), 300, delta=0.1)
        self.assertAlmostEqual(sum(values["title"] for values in teams.values()), 100, delta=0.1)
        # Drivers out of a seat cannot win, and the leader is the favourite.
        self.assertEqual(drivers["tsunoda"]["title"], 0)
        self.assertEqual(max(drivers, key=lambda key: drivers[key]["title"]), "antonelli")

    def test_each_remaining_events_win_odds_sum_to_one_hundred(self) -> None:
        events = self.payload["events"]
        self.assertEqual([item["key"] for item in events[:2]], ["2026-17-sprint", "2026-17-race"])
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            write_cache(cache, 2025)
            write_cache(cache, 2026)
            data = formula1.load_season(2026, cache, current=True)
            drivers, constructors, _ = formula1.championship(data.events, formula1.PointsRules())
        latest = [item for item in data.events if item.done][-1]
        lineup = {entry.driver: entry.constructor for entry in latest.entries}
        remaining = [item for item in data.events if not item.done]
        model = formula1.fit_model(data.events, 2026, new_rules={2026})
        odds = formula1.simulate_season(model, lineup, remaining, formula1.PointsRules(), drivers, constructors, 1.5, len(data.events), simulations=3000)
        for key, chances in odds.events.items():
            with self.subTest(event=key):
                self.assertAlmostEqual(sum(win for win, _ in chances.values()), 1.0, places=9)
                self.assertAlmostEqual(sum(podium for _, podium in chances.values()), 3.0, places=9)
        # The payload keeps the favourites, which never add up to more than the whole.
        for item in events:
            self.assertLessEqual(sum(favourite["win"] for favourite in item["favourites"]), 100.01)
            self.assertEqual(len(item["favourites"]), formula1.FAVOURITES)

    def test_the_home_page_names_the_title_favourites(self) -> None:
        entry = extract_table.index_entry(self.payload)
        self.assertEqual(entry["sport"], "motorsport")
        self.assertTrue(entry["started"])
        labels = [fact["label"] for fact in entry["facts"]]
        self.assertEqual(labels, ["Drivers' title favourite", "Constructors' title favourite"])
        self.assertRegex(entry["facts"][0]["value"], r"^ANT (\d+(\.\d)?%|>99\.9%)$")
        self.assertRegex(entry["facts"][1]["value"], r"^MER ")

    def test_a_finished_season_shows_the_champions(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(formula1, "_download", side_effect=offline_download):
            cache = Path(folder)
            write_cache(cache, 2025)
            payload = formula1.build_payload(CONFIG, datetime(2025, 12, 20, tzinfo=UTC), cache, simulations=500)
        self.assertEqual(payload["metadata"]["season_status"], "complete")
        self.assertEqual(payload["playoffs"]["champion"], "norris")
        self.assertEqual(payload["analysis"]["probabilities"]["norris"]["title"], 100.0)
        self.assertEqual(payload["analysis"]["constructorProbabilities"]["mclaren"]["title"], 100.0)
        self.assertEqual(payload["events"], [])
        # 2024 is not in the cache and the source is offline: a warning, not a failure.
        self.assertTrue(any("Last season's results are unavailable" in warning for warning in payload["metadata"]["warnings"]))
        entry = extract_table.index_entry(payload)
        self.assertEqual((entry["champion"], entry["facts"]), ("NOR", [{"label": "Champions", "value": "NOR"}]))

    def test_before_the_first_race_the_odds_are_pre_season_projections(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(formula1, "_download", side_effect=offline_download):
            cache = Path(folder)
            write_cache(cache, 2025)
            write_cache(cache, 2026)
            for endpoint, empty in (("results", {"total": 0, "Races": []}), ("sprint", {"total": 0, "Races": []}), ("driverstandings", {"total": 0, "StandingsLists": []}), ("constructorstandings", {"total": 0, "StandingsLists": []})):
                (cache / "jolpica" / f"2026-{endpoint}.json").write_text(json.dumps(empty), encoding="utf-8")
            payload = formula1.build_payload(CONFIG, datetime(2026, 3, 2, tzinfo=UTC), cache, simulations=1000)
        self.assertEqual(payload["league"]["eventsLeft"], 29)
        self.assertIn("No results yet: the line-up is last season's final one until the first race.", payload["metadata"]["warnings"])
        self.assertFalse(extract_table.index_entry(payload)["started"])
        titles = [payload["analysis"]["probabilities"][row["teamKey"]]["title"] for row in payload["standings"]]
        self.assertEqual(titles, sorted(titles, reverse=True))
        self.assertAlmostEqual(sum(titles), 100, delta=0.1)

    def test_an_overdue_event_is_left_out_with_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(formula1, "_download", side_effect=offline_download):
            cache = Path(folder)
            write_cache(cache, 2025)
            write_cache(cache, 2026)
            payload = formula1.build_payload(CONFIG, NOW_2026 + timedelta(days=10), cache, simulations=500)
        self.assertEqual(payload["league"]["eventsLeft"], 6)
        self.assertTrue(any("Singapore Grand Prix" in warning and "cancelled" in warning for warning in payload["metadata"]["warnings"]))


class ConfigTests(unittest.TestCase):
    def test_the_config_validates_and_rolls_with_the_calendar(self) -> None:
        formula1.validate_config(CONFIG)
        self.assertEqual(extract_table.SPORT_MODULES[CONFIG["sport"]], "formula1")
        season = team_sports.resolve_season(CONFIG, NOW_2026)
        self.assertEqual((season.payload_id, season.feed), ("f1-2026", "2026"))
        self.assertFalse(team_sports.resolve_season(CONFIG, datetime(2027, 2, 10, tzinfo=UTC)).contains(datetime(2027, 2, 10, tzinfo=UTC)))
        self.assertEqual(team_sports.resolve_season(CONFIG, datetime(2027, 3, 2, tzinfo=UTC)).payload_id, "f1-2027")
        with self.assertRaisesRegex(ValueError, "points.sprint"):
            formula1.validate_config(dict(CONFIG, points=dict(CONFIG["points"], sprint=[1, 8])))

    def test_a_source_failure_is_a_warning_for_the_nightly_run(self) -> None:
        other = {"league": {"id": "epl-2026-27", "sport": "football"}, "metadata": {"season_status": "in_progress"}, "analysis": {"probabilities": {}}, "standings": []}

        def build(league_id: str, *_: object) -> dict:
            # The real engine with an empty cache and the source down, next to a league that builds.
            return formula1.build_payload(CONFIG, NOW_2026, Path(folder)) if league_id == "f1" else other

        with tempfile.TemporaryDirectory() as folder, mock.patch.object(formula1, "_download", side_effect=offline_download), mock.patch.object(
            extract_table, "league_plan", return_value=[("f1", "feed"), ("epl", "feed")]
        ), mock.patch.object(extract_table, "build_league", side_effect=build), mock.patch.object(extract_table, "write_league_index"), mock.patch.object(
            extract_table, "published_payload", return_value=None
        ), mock.patch.object(extract_table, "same_content", return_value=True), mock.patch("builtins.print") as printed:
            extract_table.main(["--league", "active"])
        lines = [" ".join(map(str, call.args)) for call in printed.call_args_list]
        self.assertTrue(any(line.startswith("::warning::f1: Jolpica F1 API 2026 races") for line in lines), lines)
        self.assertIn("epl-2026-27: unchanged", lines)


if __name__ == "__main__":
    unittest.main()
