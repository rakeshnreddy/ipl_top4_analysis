from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import extract_table
import leagues
from test_cricsheet import round_robin_season, write_archive


class LeagueConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        extract_table.use_league(leagues.load_league(leagues.DEFAULT_LEAGUE_ID))

    def test_every_config_loads_and_validates(self) -> None:
        ids = leagues.available_league_ids()

        self.assertEqual(ids[0], leagues.DEFAULT_LEAGUE_ID)
        for league_id in ids:
            league = leagues.load_league(league_id)
            self.assertEqual(league.id, league_id)
            self.assertEqual(league.league_match_count * 2, len(league.teams) * league.matches_per_team)
            self.assertTrue(league.cricsheet_competition, f"{league_id} needs a Cricsheet source")

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
        self.assertEqual(index["default"], "ipl-2026")
        self.assertEqual([entry["id"] for entry in index["leagues"]], ["wpl-2026"])
        self.assertEqual(index["leagues"][0]["path"], "data/wpl-2026.json")

    def test_cli_rejects_a_shared_archive_for_several_leagues(self) -> None:
        with self.assertRaises(SystemExit):
            extract_table.main(["--league", "all", "--cricsheet-archive", "ipl_json.zip"])


def write_payload(data_dir: Path, league_id: str, status: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"generated_at": "2026-10-01T00:00:00Z", "season_status": status},
        "league": {"shortName": league_id.split("-")[0].upper(), "seasonLabel": league_id.split("-", 1)[1]},
        "standings": [],
    }
    (data_dir / f"{league_id}.json").write_text(json.dumps(payload))


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

    def test_plan_builds_live_leagues_from_cricketdata(self) -> None:
        plan = extract_table.league_plan(datetime(2026, 12, 20, 19, 30, tzinfo=timezone.utc))

        self.assertEqual(plan, [("bbl-2026-27", "cricketdata"), ("ilt-2026-27", "cricketdata")])

    def test_plan_rebuilds_a_finished_league_from_cricsheet_until_it_is_complete(self) -> None:
        now = datetime(2027, 2, 1, 19, 30, tzinfo=timezone.utc)

        self.assertEqual(
            extract_table.league_plan(now),
            [("wpl-2027", "cricketdata"), ("bbl-2026-27", "cricsheet"), ("sa20-2026-27", "cricketdata")],
        )
        write_payload(self.data_dir, "bbl-2026-27", "complete")
        self.assertEqual(
            extract_table.league_plan(now),
            [("wpl-2027", "cricketdata"), ("sa20-2026-27", "cricketdata")],
        )

    def test_active_build_off_season_writes_nothing(self) -> None:
        # Between CPL's finalize window (to 11 Oct) and ILT20's start (22 Nov).
        with mock.patch.object(extract_table, "utc_now", return_value=datetime(2026, 11, 1, tzinfo=timezone.utc)):
            extract_table.main(["--league", "active"])

        self.assertFalse(self.data_dir.exists())

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

    def test_finalize_run_publishes_only_a_finished_season(self) -> None:
        playoffs_only = {"metadata": {"season_status": "playoffs"}}
        now = datetime(2026, 10, 3, 19, 30, tzinfo=timezone.utc)

        with mock.patch.object(extract_table, "utc_now", return_value=now), mock.patch.object(
            extract_table, "league_plan", return_value=[("cpl-2026", "cricsheet")]
        ), mock.patch.object(extract_table, "build_league", return_value=playoffs_only):
            extract_table.main(["--league", "active"])

        self.assertFalse((self.data_dir / "cpl-2026.json").exists())

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

    def test_series_id_env_var_only_applies_to_the_default_league(self) -> None:
        bbl = leagues.load_league("bbl-2026-27")

        with mock.patch.dict(extract_table.os.environ, {"CRICDATA_SERIES_ID": "ipl-series"}, clear=True):
            extract_table.use_league(bbl)
            self.assertIsNone(extract_table.cricdata_series_id())
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


if __name__ == "__main__":
    unittest.main()
