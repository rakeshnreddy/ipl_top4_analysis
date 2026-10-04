from __future__ import annotations

import contextlib
import dataclasses
import io
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import extract_table
import leagues
import team_sports
from test_cricsheet import round_robin_season, write_archive


class LeagueConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        extract_table.use_league(leagues.load_league(leagues.DEFAULT_LEAGUE_ID))

    def test_every_config_loads_and_validates(self) -> None:
        ids = leagues.available_league_ids()

        self.assertEqual(ids[0], leagues.DEFAULT_LEAGUE_ID)
        for league_id in ids:
            config = leagues.read_config(league_id)
            self.assertEqual(config["id"], league_id)
            if not leagues.is_cricket(config):
                self.assertIn(config["sport"], extract_table.SPORT_MODULES)
                team_sports.validate_config(config)
                continue
            league = leagues.load_league(league_id)
            self.assertEqual(league.league_match_count * 2, len(league.teams) * league.matches_per_team)
            self.assertTrue(league.cricsheet_competition, f"{league_id} needs a Cricsheet source")

    def test_rolling_configs_are_not_loaded_as_cricket_seasons(self) -> None:
        with self.assertRaisesRegex(ValueError, "football"):
            leagues.load_league("epl")

    def test_unknown_league_lists_the_available_ones(self) -> None:
        with self.assertRaisesRegex(ValueError, "ipl-2026"):
            leagues.load_league("nope-2026")

    def test_invalid_qualification_sizes_are_rejected(self) -> None:
        raw = json.loads((leagues.LEAGUES_DIR / "wpl-2026.json").read_text())
        raw["qualification"] = [{"size": 1, "label": "Top 1"}, {"size": 3, "label": "Top 3"}]

        with self.assertRaisesRegex(ValueError, "descending"):
            leagues.parse_league(raw)

    def test_ipl_aliases_still_resolve(self) -> None:
        self.assertEqual(extract_table.team_key("Royal Challengers Bangalore"), "Bangalore")
        self.assertEqual(extract_table.team_key("RC Bengaluru"), "Bangalore")
        self.assertEqual(extract_table.team_key("Sunrisers"), "Hyderabad")
        self.assertEqual(extract_table.team_key("PBKS"), "Punjab")

    def test_use_league_switches_teams_and_tiers(self) -> None:
        extract_table.use_league(leagues.load_league("wpl-2026"))

        self.assertEqual(len(extract_table.TEAM_META), 5)
        self.assertEqual(extract_table.QUALIFICATION_SIZES, [3, 1])
        self.assertEqual(extract_table.LEAGUE_MATCH_COUNT, 20)
        self.assertEqual(extract_table.team_key("UP Warriors"), "UPW")
        self.assertEqual(extract_table.CANONICAL_OUTPUT.name, "wpl-2026.json")

    def test_cli_writes_payload_and_league_index(self) -> None:
        wpl = leagues.load_league("wpl-2026")
        names = [team.full_name for team in wpl.teams]

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            archive = write_archive(Path(tmp), round_robin_season(names, season="2025/26"))
            with mock.patch.object(extract_table, "DATA_DIR", data_dir), mock.patch.object(
                extract_table, "LEAGUE_INDEX_OUTPUT", data_dir / "leagues.json"
            ):
                extract_table.main(["--league", "wpl-2026", "--source", "cricsheet", "--cricsheet-archive", str(archive)])

            payload = json.loads((data_dir / "wpl-2026.json").read_text())
            index = json.loads((data_dir / "leagues.json").read_text())

        self.assertEqual(payload["league"]["shortName"], "WPL")
        self.assertEqual(payload["standings"][0]["teamKey"], "RCB")
        # No IPL season is on, so the home page is the all-sports hub.
        self.assertEqual(index["default"], "hub")
        self.assertEqual(index["ipl"], "ipl-2026")
        # The synthetic season has no playoff matches: the league stage is over, the playoffs are not.
        self.assertEqual(index["leagues"][0]["facts"], [{"label": "In the playoffs", "value": "RCB, GG, DC"}])
        self.assertEqual([entry["id"] for entry in index["leagues"]], ["wpl-2026"])
        self.assertEqual(index["leagues"][0]["path"], "data/wpl-2026.json")

    def test_cli_rejects_a_shared_archive_for_several_leagues(self) -> None:
        with self.assertRaises(SystemExit):
            extract_table.main(["--league", "all", "--cricsheet-archive", "ipl_json.zip"])


def write_payload(data_dir: Path, league_id: str, status: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"generated_at": "2026-10-01T00:00:00Z", "season_status": status},
        "league": leagues.load_league(league_id).payload_block(),
        "standings": [],
    }
    (data_dir / f"{league_id}.json").write_text(json.dumps(payload))


CRICKET_IDS = [league_id for league_id in leagues.available_league_ids() if leagues.is_cricket(leagues.read_config(league_id))]


class LiveSeasonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.patches = [
            mock.patch.object(extract_table, "DATA_DIR", self.data_dir),
            mock.patch.object(extract_table, "LEAGUE_INDEX_OUTPUT", self.data_dir / "leagues.json"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self) -> None:
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()
        extract_table.use_league(leagues.load_league(leagues.DEFAULT_LEAGUE_ID))

    def cricket_plan(self, now: datetime) -> list[tuple[str, str]]:
        return [item for item in extract_table.league_plan(now) if item[1] != "feed"]

    def test_plan_builds_live_leagues_from_cricketdata(self) -> None:
        plan = self.cricket_plan(datetime(2026, 12, 20, 19, 30, tzinfo=timezone.utc))

        # The WBBL final was on 5 December, so it waits for its Cricsheet rebuild.
        self.assertEqual(
            plan, [("bbl-2026-27", "cricketdata"), ("ilt-2026-27", "cricketdata"), ("wbbl-2026-27", "cricsheet")]
        )

    def test_plan_rebuilds_a_finished_league_from_cricsheet_until_it_is_complete(self) -> None:
        now = datetime(2027, 2, 1, 19, 30, tzinfo=timezone.utc)

        # BPL 2026-27 has no config: it is rolled forward from 2025-26 and finalized from Cricsheet too.
        self.assertEqual(
            self.cricket_plan(now),
            [
                ("wpl-2027", "cricketdata"),
                ("bbl-2026-27", "cricsheet"),
                ("sa20-2026-27", "cricketdata"),
                ("ilt-2026-27", "cricsheet"),
                ("super-smash-men-2026-27", "cricsheet"),
                ("super-smash-women-2026-27", "cricsheet"),
                ("bpl-2026-27", "cricsheet"),
            ],
        )
        write_payload(self.data_dir, "bbl-2026-27", "complete")
        self.assertEqual(
            self.cricket_plan(now),
            [
                ("wpl-2027", "cricketdata"),
                ("sa20-2026-27", "cricketdata"),
                ("ilt-2026-27", "cricsheet"),
                ("super-smash-men-2026-27", "cricsheet"),
                ("super-smash-women-2026-27", "cricsheet"),
                ("bpl-2026-27", "cricsheet"),
            ],
        )

    def test_plan_builds_rolling_leagues_only_in_season(self) -> None:
        in_season = extract_table.league_plan(datetime(2026, 12, 20, tzinfo=timezone.utc))
        summer = extract_table.league_plan(datetime(2027, 7, 15, tzinfo=timezone.utc))

        self.assertIn(("epl", "feed"), in_season)
        self.assertIn(("ligue-1", "feed"), in_season)
        self.assertNotIn(("epl", "feed"), summer)

    def test_active_build_off_season_writes_nothing(self) -> None:
        # Between CPL's finalize window (to 4 Nov) and ILT20's start (22 Nov). Some cricket is on
        # almost every day of the year, so the leagues in season then are left out.
        in_season = ("wbbl-",)
        off_season = [league_id for league_id in CRICKET_IDS if not league_id.startswith(in_season)]
        with mock.patch.object(extract_table, "utc_now", return_value=datetime(2026, 11, 10, tzinfo=timezone.utc)), mock.patch.object(
            extract_table, "available_league_ids", return_value=off_season
        ):
            extract_table.main(["--league", "active"])

        self.assertFalse(self.data_dir.exists())

    def test_one_failing_league_is_a_warning_when_others_build(self) -> None:
        good = {"metadata": {"generated_at": "2026-10-03T19:30:00Z", "season_status": "complete"}, "league": {"id": "wpl-2026"}, "standings": []}

        def build(league_id: str, source: str, archive: object = None) -> dict[str, object]:
            if league_id == "epl":
                raise team_sports.FeedError("epl-2026: offline")
            return good

        # Capture output: a real "::warning::" line would show as an annotation on every CI run.
        with mock.patch.object(
            extract_table, "league_plan", return_value=[("epl", "feed"), ("wpl-2026", "cricketdata")]
        ), mock.patch.object(extract_table, "build_league", side_effect=build), contextlib.redirect_stdout(io.StringIO()) as output:
            extract_table.main(["--league", "active"])

        self.assertTrue((self.data_dir / "wpl-2026.json").exists())
        self.assertIn("::warning::epl: epl-2026: offline", output.getvalue())

    def test_a_night_where_every_league_fails_fails_the_run(self) -> None:
        with mock.patch.object(extract_table, "league_plan", return_value=[("epl", "feed")]), mock.patch.object(
            extract_table, "build_league", side_effect=team_sports.FeedError("epl-2026: offline")
        ), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                extract_table.main(["--league", "active"])

    def test_a_payload_that_only_differs_in_its_timestamp_is_not_rewritten(self) -> None:
        first = {"metadata": {"generated_at": "2026-10-02T19:30:00Z", "season_status": "complete"}, "league": {"id": "wpl-2026"}, "standings": []}
        second = json.loads(json.dumps(first))
        second["metadata"]["generated_at"] = "2026-10-03T19:30:00Z"

        for payload in (first, second):
            with mock.patch.object(extract_table, "build_league", return_value=payload):
                extract_table.main(["--league", "wpl-2026"])

        published = json.loads((self.data_dir / "wpl-2026.json").read_text())
        self.assertEqual(published["metadata"]["generated_at"], "2026-10-02T19:30:00Z")

    def test_index_lists_live_leagues_first(self) -> None:
        for league_id in ("ipl-2026", "wpl-2026", "bbl-2025-26"):
            write_payload(self.data_dir, league_id, "complete")
        write_payload(self.data_dir, "bbl-2026-27", "league_stage")

        extract_table.write_league_index()

        index = json.loads((self.data_dir / "leagues.json").read_text())
        self.assertEqual(
            [entry["id"] for entry in index["leagues"]],
            ["bbl-2026-27", "ipl-2026", "wpl-2026", "bbl-2025-26"],
        )

    def test_finalize_run_publishes_a_partial_season_once_then_waits_for_the_final(self) -> None:
        def partial(generated: str) -> dict[str, object]:
            return {
                "metadata": {"generated_at": generated, "season_status": "playoffs"},
                "league": leagues.load_league("cpl-2026").payload_block(),
                "standings": [],
                "analysis": {"overallProbabilities": {}},
            }

        now = datetime(2026, 10, 3, 19, 30, tzinfo=timezone.utc)
        for generated in ("2026-10-03T19:30:00Z", "2026-10-04T19:30:00Z"):
            with mock.patch.object(extract_table, "utc_now", return_value=now), mock.patch.object(
                extract_table, "league_plan", return_value=[("cpl-2026", "cricsheet")]
            ), mock.patch.object(extract_table, "build_league", return_value=partial(generated)):
                extract_table.main(["--league", "active"])

        published = json.loads((self.data_dir / "cpl-2026.json").read_text())
        # The first partial page stays until a complete rebuild replaces it.
        self.assertEqual(published["metadata"]["generated_at"], "2026-10-03T19:30:00Z")

    def test_index_default_is_the_newest_published_ipl_season(self) -> None:
        for league_id in ("ipl-2026", "ipl-2027", "wpl-2027"):
            write_payload(self.data_dir, league_id, "league_stage")
        for league_id in ("ipl-2026", "ipl-2027"):
            path = self.data_dir / f"{league_id}.json"
            payload = json.loads(path.read_text())
            payload["league"]["shortName"] = "IPL"
            path.write_text(json.dumps(payload))

        extract_table.write_league_index()

        self.assertEqual(json.loads((self.data_dir / "leagues.json").read_text())["default"], "ipl-2027")

    def test_football_cards_show_the_title_favourite_and_relegation_risk(self) -> None:
        payload = {
            "metadata": {"season_status": "in_progress"},
            "league": {
                "sport": "football",
                "tiers": [
                    {"key": "title", "label": "Title", "kind": "top", "size": 1},
                    {"key": "relegation", "label": "Relegation", "kind": "bottom", "size": 1},
                ],
            },
            "standings": [{"teamKey": "Arsenal", "shortName": "ARS"}, {"teamKey": "Spurs", "shortName": "TOT"}],
            "analysis": {"probabilities": {"Arsenal": {"title": 99.97, "relegation": 0.0}, "Spurs": {"title": 0.03, "relegation": 64.4}}},
        }

        self.assertEqual(
            extract_table.league_facts(payload, None),
            [{"label": "Title favourite", "value": "ARS >99.9%"}, {"label": "Relegation risk", "value": "TOT 64%"}],
        )
        self.assertEqual(extract_table.league_facts({"league": {}}, None), [])

    def test_series_id_env_var_only_applies_to_the_default_league(self) -> None:
        bbl = leagues.load_league("bbl-2026-27")

        with mock.patch.dict(extract_table.os.environ, {"CRICDATA_SERIES_ID": "ipl-series"}, clear=True):
            extract_table.use_league(bbl)
            self.assertIsNone(extract_table.cricdata_series_id())
            # A later IPL season must not inherit the 2026 series.
            extract_table.use_league(leagues.load_league("ipl-2027"))
            self.assertIsNone(extract_table.cricdata_series_id())
            extract_table.use_league(leagues.load_league("ipl-2026"))
            self.assertEqual(extract_table.cricdata_series_id(), "ipl-series")
            extract_table.use_league(dataclasses.replace(bbl, cricketdata_series_id="bbl-series"))
            self.assertEqual(extract_table.cricdata_series_id(), "bbl-series")

    def test_series_discovery_matches_season_labels_written_either_way(self) -> None:
        extract_table.use_league(leagues.load_league("bbl-2026-27"))
        response = mock.Mock(ok=True)
        response.json.return_value = {
            "status": "success",
            "data": [
                {"id": "old", "name": "Big Bash League 2025-26"},
                {"id": "new", "name": "Big Bash League 2026/27"},
            ],
        }
        session = mock.Mock()
        session.get.return_value = response

        with mock.patch.dict(extract_table.os.environ, {}, clear=True):
            self.assertEqual(extract_table.find_cricdata_series_id(session, "key"), "new")

    def test_series_discovery_keeps_mens_and_womens_series_apart(self) -> None:
        response = mock.Mock(ok=True)
        response.json.return_value = {
            "status": "success",
            "data": [
                {"id": "wbbl", "name": "Women's Big Bash League 2026-27"},
                {"id": "bbl", "name": "Big Bash League 2026-27"},
                {"id": "ssw", "name": "Super Smash Women 2026-27"},
                {"id": "ss", "name": "Super Smash 2026-27"},
            ],
        }
        session = mock.Mock()
        session.get.return_value = response

        with mock.patch.dict(extract_table.os.environ, {}, clear=True):
            extract_table.use_league(leagues.load_league("bbl-2026-27"))
            self.assertEqual(extract_table.find_cricdata_series_id(session, "key"), "bbl")
            extract_table.use_league(leagues.load_league("wbbl-2026-27"))
            self.assertEqual(extract_table.find_cricdata_series_id(session, "key"), "wbbl")
            extract_table.use_league(leagues.load_league("super-smash-men-2026-27"))
            self.assertEqual(extract_table.find_cricdata_series_id(session, "key"), "ss")
            extract_table.use_league(leagues.load_league("super-smash-women-2026-27"))
            self.assertEqual(extract_table.find_cricdata_series_id(session, "key"), "ssw")



def live_payload(played: int, odds: dict[str, float], movement: object = None) -> dict[str, object]:
    return {
        "metadata": {"generated_at": f"2027-01-{14 + played:02d}T19:30:00Z", "season_status": "league_stage"},
        "league": {"id": "wpl-2027"},
        "standings": [{"teamKey": team, "matches": played} for team in odds],
        "analysis": {"overallProbabilities": {team: {"top3": value} for team, value in odds.items()}},
        "movement": movement,
    }


class ProbabilityMovementTests(unittest.TestCase):
    def setUp(self) -> None:
        extract_table.use_league(leagues.load_league("wpl-2027"))

    def tearDown(self) -> None:
        extract_table.use_league(leagues.load_league(leagues.DEFAULT_LEAGUE_ID))

    def test_movement_is_the_change_since_the_previous_update(self) -> None:
        previous = live_payload(2, {"RCB": 60.0, "GG": 55.5})
        current = live_payload(3, {"RCB": 72.25, "GG": 40.0})

        movement = extract_table.probability_movement(previous, current)

        self.assertEqual(movement, {"since": "2027-01-16T19:30:00Z", "tier": "top3", "changes": {"RCB": 12.25, "GG": -15.5}})

    def test_movement_carries_forward_when_no_match_finished(self) -> None:
        earlier = {"since": "2027-01-15T19:30:00Z", "tier": "top3", "changes": {"RCB": 4.0}}
        previous = live_payload(3, {"RCB": 64.0}, movement=earlier)

        self.assertEqual(extract_table.probability_movement(previous, live_payload(3, {"RCB": 64.0})), earlier)

    def test_no_movement_without_a_previous_payload_from_the_same_league(self) -> None:
        other_league = dict(live_payload(2, {"RCB": 50.0}), league={"id": "wpl-2026"})

        self.assertIsNone(extract_table.probability_movement(None, live_payload(3, {"RCB": 60.0})))
        self.assertIsNone(extract_table.probability_movement(other_league, live_payload(3, {"RCB": 60.0})))


class RolloverTests(unittest.TestCase):
    def test_a_season_rolls_forward_with_its_teams_and_rules(self) -> None:
        bbl = leagues.read_config("bbl-2027-28")

        self.assertEqual((bbl["id"], bbl["season"], bbl["seasonLabel"]), ("bbl-2027-28", "2027/28", "2027-28"))
        self.assertEqual((bbl["seasonStart"], bbl["seasonEnd"]), ("2027-12-12", "2028-01-26"))
        self.assertTrue(bbl["tentative"])
        self.assertEqual(bbl["teams"], leagues.read_config("bbl-2026-27")["teams"])
        self.assertEqual(leagues.load_league("ipl-2029").season_label, "2029")

    def test_season_specific_details_are_not_carried_over(self) -> None:
        sa20 = leagues.read_config("sa20-2027-28")

        self.assertEqual(sa20["seasonLabel"], "2028")
        self.assertNotIn("extraResults", sa20)
        self.assertNotIn("seriesId", sa20["sources"].get("cricketdata", {}))
        self.assertEqual(sa20["points"], leagues.read_config("sa20-2026-27")["points"])

    def test_competitions_roll_forward_only_once_their_newest_season_is_over(self) -> None:
        october = leagues.rolled_league_ids(datetime(2026, 10, 3, tzinfo=timezone.utc), 21)
        next_summer = leagues.rolled_league_ids(datetime(2027, 7, 1, tzinfo=timezone.utc), 21)

        self.assertNotIn("ipl-2028", october)
        self.assertIn("ipl-2028", next_summer)
        self.assertIn("cpl-2027", next_summer)
        self.assertIn("wcpl-2027", next_summer)
        self.assertNotIn("epl-2027", next_summer)

    def test_the_planner_builds_a_rolled_season_live(self) -> None:
        plan = extract_table.league_plan(datetime(2028, 3, 20, tzinfo=timezone.utc))

        self.assertIn(("ipl-2028", "cricketdata"), plan)

    def test_rolling_sports_and_unknown_ids_are_not_rolled(self) -> None:
        for league_id in ("epl-2027", "nope-2027", "nfl-2027"):
            with self.subTest(league_id), self.assertRaises(ValueError):
                leagues.read_config(league_id)


if __name__ == "__main__":
    unittest.main()
