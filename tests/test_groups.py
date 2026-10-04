"""Group-stage leagues (the T20 Blast): seeding across groups, sampled odds, deductions and missing targets."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import unittest
from unittest import mock

import cricsheet
import extract_table
import leagues
from leagues import DEFAULT_LEAGUE_ID, Target, load_league
from test_cricsheet import innings, parse, raw_match


# The official 2026 group tables (points, NRR): https://www.ecb.co.uk/t20-blast/tables/2026
BLAST_2026 = {
    "NOT": (32, 0.169), "YOR": (30, 0.72), "LAN": (26, -0.335), "DUR": (20, 0.462), "DER": (16, 0.393), "LEI": (12, -1.6),
    "NOR": (36, 0.936), "SOM": (28, 0.763), "GLO": (28, 0.288), "WAR": (24, 0.367), "GLA": (24, 0.217), "WOR": (24, -0.337),
    "HAM": (32, 0.283), "SUR": (28, 0.666), "ESS": (28, 0.354), "KEN": (16, -0.895), "MID": (16, -1.243), "SUS": (10, -1.168),
}
# The quarter-final draw: seed 1 v 8, 2 v 7, 3 v 6 and 4 v 5.
BLAST_2026_SEEDS = ["NOR", "HAM", "NOT", "YOR", "SOM", "SUR", "ESS", "GLO"]


def row(key: str, points: int, nrr: float | None, played: int = 12) -> dict[str, object]:
    wins = points // 4
    return {
        "teamKey": key, "shortName": key, "fullName": key, "matches": played, "wins": wins, "losses": played - wins,
        "noResult": 0, "points": points, "nrr": nrr, "rank": 0, "remainingMatches": 12 - played,
    }


class GroupStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.league = load_league("t20-blast-2026")
        extract_table.use_league(self.league)

    def tearDown(self) -> None:
        extract_table.use_league(load_league(DEFAULT_LEAGUE_ID))

    def test_seeds_are_the_group_winners_then_the_seconds_then_the_best_thirds(self) -> None:
        standings = extract_table.ranked_standings([row(key, *values) for key, values in BLAST_2026.items()])

        by_key = {item["teamKey"]: item for item in standings}
        self.assertEqual([item["teamKey"] for item in standings[:8]], BLAST_2026_SEEDS)
        # Lancashire were third in the North but behind both better third-placed teams.
        self.assertEqual((by_key["LAN"]["group"], by_key["LAN"]["groupRank"], by_key["LAN"]["rank"]), ("North", 3, 9))
        self.assertEqual((by_key["GLO"]["groupRank"], by_key["SOM"]["groupRank"]), (3, 2))

        analysis = extract_table.run_analysis(standings, [], datetime(2026, 7, 13, tzinfo=timezone.utc))
        odds = analysis["overallProbabilities"]
        self.assertEqual(analysis["method"], "Final standings")
        self.assertEqual({key for key, value in odds.items() if value["top8"] == 100.0}, set(BLAST_2026_SEEDS))
        self.assertEqual({key for key, value in odds.items() if value["top4"] == 100.0}, {"NOR", "HAM", "NOT", "YOR"})

    def test_group_stage_odds_are_sampled_within_groups(self) -> None:
        # Each group's leader has finished on 48 points, out of reach of the other five,
        # who have eight games each left against one another (at most 8 + 8 x 4 = 40).
        standings = []
        for group in self.league.groups:
            for index, key in enumerate(group.teams):
                standings.append(row(key, 48, 1.0) if index == 0 else row(key, 8, 0.1 * index, played=4))
        fixtures = [
            {"id": f"{group.name}-{left}-{right}-{leg}", "matchNo": None, "teamA": left, "teamB": right}
            for group in self.league.groups
            for leg in range(2)
            for i, left in enumerate(group.teams[1:], start=1)
            for right in group.teams[i + 1:]
        ]

        with mock.patch.object(extract_table, "DEFAULT_MONTE_CARLO_SIMULATIONS", 3000):
            analysis = extract_table.run_analysis(extract_table.ranked_standings(standings), fixtures, datetime(2026, 6, 20, tzinfo=timezone.utc))

        odds = analysis["overallProbabilities"]
        self.assertEqual(analysis["method"], "Monte Carlo")
        self.assertAlmostEqual(sum(value["top8"] for value in odds.values()), 800.0, places=0)
        self.assertAlmostEqual(sum(value["top4"] for value in odds.values()), 400.0, places=0)
        for group in self.league.groups:
            leader = group.teams[0]
            self.assertEqual((odds[leader]["top8"], odds[leader]["top4"]), (100.0, 100.0))
            # At least the top two of every group go through.
            self.assertGreaterEqual(sum(odds[key]["top8"] for key in group.teams), 199.9)

    def test_deductions_come_off_the_points_and_still_validate(self) -> None:
        standings = [row(key, 24, 0.0) for key in extract_table.TEAM_META]

        extract_table.apply_deductions(standings)

        sussex = next(item for item in standings if item["teamKey"] == "SUS")
        self.assertEqual((sussex["points"], sussex["deductedPoints"]), (22, 2))
        extract_table.validate_source_data(standings, [], datetime(2026, 8, 1, tzinfo=timezone.utc), strict_zero_fixtures=False)
        sussex.pop("deductedPoints")
        with self.assertRaisesRegex(extract_table.SourceValidationError, "SUS points=22 expected=24"):
            extract_table.validate_source_data(standings, [], datetime(2026, 8, 1, tzinfo=timezone.utc), strict_zero_fixtures=False)

    def test_configured_targets_fill_shortened_matches(self) -> None:
        # Ten overs a side: without the target the first innings would be charged 20 overs.
        extract_table.use_league(dataclasses.replace(self.league, targets=self.league.targets[:1]))
        match = parse(raw_match("Durham", "Lancashire", {"winner": "Lancashire", "by": {"wickets": 7}},
                                [innings("Durham", 60, 2, wickets=2), innings("Lancashire", 55, 2, wickets=3)], date="2026-06-09"))
        self.assertEqual(cricsheet.nrr_lines(match)[0], ("Durham", 120, 120))

        filled = extract_table.with_targets([match])

        self.assertEqual((filled[0].target_runs, filled[0].target_balls), (129, 60))
        self.assertEqual(cricsheet.nrr_lines(filled[0])[0], ("Durham", 120, 60))

    def test_a_target_that_matches_no_match_is_an_error(self) -> None:
        extract_table.use_league(dataclasses.replace(self.league, targets=(Target("2026-06-10", ("Durham", "Lancashire"), 129, 10),)))
        match = parse(raw_match("Durham", "Lancashire", {"winner": "Lancashire", "by": {"wickets": 7}},
                                [innings("Durham", 60, 2), innings("Lancashire", 55, 2)], date="2026-06-09"))

        with self.assertRaisesRegex(extract_table.SourceValidationError, "Durham v Lancashire"):
            extract_table.with_targets([match])


class GroupConfigTests(unittest.TestCase):
    def raw(self) -> dict[str, object]:
        return leagues.read_config("t20-blast-2026")

    def test_every_team_must_be_in_exactly_one_group(self) -> None:
        raw = self.raw()
        raw["groups"][0]["teams"].append("NOR")

        with self.assertRaisesRegex(ValueError, "exactly one group"):
            leagues.parse_league(raw)

    def test_deductions_must_name_a_team(self) -> None:
        raw = self.raw()
        raw["deductions"][0]["team"] = "Sussex"

        with self.assertRaisesRegex(ValueError, "deductions must name a team key"):
            leagues.parse_league(raw)

    def test_the_payload_lists_groups_and_deductions(self) -> None:
        block = load_league("t20-blast-2026").payload_block()

        self.assertEqual([group["name"] for group in block["groups"]], ["North", "Central & West", "South"])
        self.assertEqual(block["deductions"], [{"team": "SUS", "points": 2, "note": "ECB financial agreement"}])
        self.assertEqual(block["qualification"][0], {"size": 8, "label": "Quarter-finals", "shortLabel": "QF"})
        other = load_league("bbl-2025-26").payload_block()
        self.assertNotIn("groups", other)
        self.assertEqual(other["qualification"][0], {"size": 4, "label": "Top 4"})

    def test_next_season_keeps_the_groups_but_not_the_deductions_or_targets(self) -> None:
        rolled = leagues.read_config("t20-blast-2027")

        self.assertEqual(rolled["groups"], self.raw()["groups"])
        self.assertNotIn("deductions", rolled)
        self.assertNotIn("targets", rolled)


CACHED_BLAST_ARCHIVE = extract_table.CRICSHEET_CACHE_DIR / "ntb_json.zip"


@unittest.skipUnless(CACHED_BLAST_ARCHIVE.exists(), "Cricsheet T20 Blast archive not cached locally")
class BlastRealDataTests(unittest.TestCase):
    def tearDown(self) -> None:
        extract_table.use_league(load_league(DEFAULT_LEAGUE_ID))

    def test_2026_seeds_reproduce_the_quarter_final_draw(self) -> None:
        extract_table.use_league(load_league("t20-blast-2026"))

        payload = extract_table.build_cricsheet_payload(CACHED_BLAST_ARCHIVE)

        seeds = [item["teamKey"] for item in payload["standings"]]
        self.assertEqual(seeds[:8], BLAST_2026_SEEDS)
        draw = {frozenset((match["teamA"], match["teamB"])) for match in payload["playoffs"]["matches"] if match["stage"] == "Quarter-final"}
        self.assertEqual(draw, {frozenset((seeds[i], seeds[7 - i])) for i in range(4)})
        self.assertEqual(payload["playoffs"]["champion"], "NOR")


if __name__ == "__main__":
    unittest.main()
