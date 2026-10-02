from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
