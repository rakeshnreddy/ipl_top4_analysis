from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
from datetime import datetime, timezone

import cricsheet
import extract_table


TEAMS = [meta.full_name for meta in extract_table.TEAM_META.values()]


def innings(team: str, balls: int, runs_per_ball: int = 1, wickets: int = 0, **extra: object) -> dict[str, object]:
    deliveries = []
    for index in range(balls):
        delivery: dict[str, object] = {"runs": {"total": runs_per_ball}}
        if index < wickets:
            delivery["wickets"] = [{"kind": "bowled", "player_out": f"{team} {index}"}]
        deliveries.append(delivery)
    overs = [{"over": n, "deliveries": deliveries[n * 6 : (n + 1) * 6]} for n in range((balls + 5) // 6)]
    return {"team": team, "overs": overs, **extra}


def raw_match(
    team_a: str,
    team_b: str,
    outcome: dict[str, object],
    innings_list: list[dict[str, object]],
    match_number: int | None = 1,
    stage: str | None = None,
    date: str = "2026-04-01",
    season: str = "2026",
) -> dict[str, object]:
    event: dict[str, object] = {"name": "Indian Premier League"}
    if stage:
        event["stage"] = stage
    else:
        event["match_number"] = match_number
    return {
        "info": {
            "dates": [date],
            "season": season,
            "event": event,
            "teams": [team_a, team_b],
            "outcome": outcome,
            "overs": 20,
            "venue": "Test Ground",
        },
        "innings": innings_list,
    }


def parse(data: dict[str, object]) -> cricsheet.Match:
    return cricsheet.parse_match("test", data)


def write_archive(directory: Path, matches: list[dict[str, object]]) -> Path:
    path = directory / "ipl_json.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        for index, match in enumerate(matches):
            bundle.writestr(f"{900000 + index}.json", json.dumps(match))
    return path


def season_matches(league_match_count: int = 70) -> list[dict[str, object]]:
    """A round-robin-style season where the earlier team in TEAM_META always wins."""
    order = list(range(len(TEAMS)))
    rounds = []
    for _ in range(len(TEAMS) - 1):
        rounds.append([(order[i], order[-1 - i]) for i in range(len(TEAMS) // 2)])
        order = [order[0], order[-1], *order[1:-1]]
    pairings = [pair for round_pairs in rounds + rounds[:5] for pair in round_pairs]

    matches = []
    for number, (left, right) in enumerate(pairings[:league_match_count], start=1):
        winner, loser = sorted((left, right))
        matches.append(
            raw_match(
                TEAMS[winner],
                TEAMS[loser],
                {"winner": TEAMS[winner], "by": {"runs": 120}},
                [innings(TEAMS[winner], 120, 2), innings(TEAMS[loser], 120, 1, target={"runs": 241, "overs": 20})],
                match_number=number,
            )
        )
    return matches


def playoff(stage: str, winner: str, loser: str, date: str) -> dict[str, object]:
    return raw_match(
        winner,
        loser,
        {"winner": winner, "by": {"wickets": 5}},
        [innings(loser, 120, 1), innings(winner, 100, 2, target={"runs": 121, "overs": 20})],
        stage=stage,
        date=date,
    )


class CricsheetRulesTests(unittest.TestCase):
    def test_overs_to_balls_reads_cricket_notation(self) -> None:
        self.assertEqual(cricsheet.overs_to_balls(19), 114)
        self.assertEqual(cricsheet.overs_to_balls(16.4), 100)

    def test_all_out_side_is_charged_its_full_quota(self) -> None:
        match = parse(
            raw_match(
                TEAMS[0],
                TEAMS[1],
                {"winner": TEAMS[0], "by": {"runs": 60}},
                [innings(TEAMS[0], 120, 1), innings(TEAMS[1], 60, 1, wickets=10, target={"runs": 121, "overs": 20})],
            )
        )

        table = cricsheet.league_table([match], extract_table.team_key)

        self.assertEqual(table["Chennai"].nrr, 3.0)
        self.assertEqual(table["Delhi"].nrr, -3.0)
        self.assertEqual(table["Delhi"].balls_faced, 120)

    def test_dl_result_credits_side_batting_first_with_revised_target_minus_one(self) -> None:
        match = parse(
            raw_match(
                TEAMS[0],
                TEAMS[1],
                {"winner": TEAMS[1], "by": {"wickets": 4}, "method": "D/L"},
                [innings(TEAMS[0], 120, 2), innings(TEAMS[1], 80, 2, target={"runs": 150, "overs": 15})],
            )
        )

        self.assertEqual(cricsheet.nrr_lines(match), [(TEAMS[0], 149, 90), (TEAMS[1], 160, 80)])

    def test_reduced_match_without_dl_uses_the_reduced_quota_for_both_sides(self) -> None:
        match = parse(
            raw_match(
                TEAMS[0],
                TEAMS[1],
                {"winner": TEAMS[1], "by": {"wickets": 9}},
                [innings(TEAMS[0], 50, 1, wickets=10), innings(TEAMS[1], 30, 2, target={"runs": 51, "overs": 11})],
            )
        )

        self.assertEqual(cricsheet.nrr_lines(match), [(TEAMS[0], 50, 66), (TEAMS[1], 60, 30)])

    def test_super_over_win_counts_but_super_over_runs_do_not(self) -> None:
        match = parse(
            raw_match(
                TEAMS[0],
                TEAMS[1],
                {"result": "tie", "eliminator": TEAMS[1]},
                [
                    innings(TEAMS[0], 120, 1),
                    innings(TEAMS[1], 120, 1, target={"runs": 121, "overs": 20}),
                    innings(TEAMS[1], 6, 4, super_over=True),
                    innings(TEAMS[0], 6, 1, super_over=True),
                ],
            )
        )

        table = cricsheet.league_table([match], extract_table.team_key)

        self.assertEqual((table["Delhi"].wins, table["Delhi"].points), (1, 2))
        self.assertEqual(table["Chennai"].losses, 1)
        self.assertEqual(table["Delhi"].nrr, 0.0)

    def test_no_result_gives_a_point_each_and_is_excluded_from_nrr(self) -> None:
        match = parse(raw_match(TEAMS[0], TEAMS[1], {"result": "no result"}, [innings(TEAMS[0], 20, 1)]))

        table = cricsheet.league_table([match], extract_table.team_key)

        self.assertEqual((table["Chennai"].no_result, table["Chennai"].points), (1, 1))
        self.assertIsNone(table["Chennai"].nrr)

    def test_unknown_team_is_rejected(self) -> None:
        match = parse(raw_match("Mystery XI", TEAMS[1], {"winner": TEAMS[1], "by": {"runs": 1}}, []))

        with self.assertRaisesRegex(ValueError, "Mystery XI"):
            cricsheet.league_table([match], extract_table.team_key)

    def test_load_season_keeps_only_the_requested_season(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = write_archive(
                Path(tmp),
                [
                    raw_match(TEAMS[0], TEAMS[1], {"result": "no result"}, [], date="2026-04-02"),
                    raw_match(TEAMS[2], TEAMS[3], {"result": "no result"}, [], date="2025-04-02", season="2025"),
                ],
            )

            matches = cricsheet.load_season(archive, "2026")

        self.assertEqual([match.teams for match in matches], [(TEAMS[0], TEAMS[1])])


class CricsheetPayloadTests(unittest.TestCase):
    frozen_now = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def build(self, matches: list[dict[str, object]]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            archive = write_archive(Path(tmp), matches)
            with mock.patch.object(extract_table, "utc_now", return_value=self.frozen_now):
                return extract_table.build_cricsheet_payload(archive)

    def test_completed_season_payload_has_final_table_and_playoffs(self) -> None:
        playoffs = [
            playoff("Qualifier 1", TEAMS[0], TEAMS[1], "2026-05-26"),
            playoff("Eliminator", TEAMS[3], TEAMS[2], "2026-05-27"),
            playoff("Qualifier 2", TEAMS[3], TEAMS[1], "2026-05-29"),
            playoff("Final", TEAMS[3], TEAMS[0], "2026-05-31"),
        ]

        payload = self.build(season_matches() + playoffs)

        standings = payload["standings"]
        self.assertEqual(payload["metadata"]["source"], "Cricsheet")
        self.assertEqual(payload["metadata"]["source_license"], "ODC-By 1.0")
        self.assertEqual(payload["metadata"]["season_status"], "complete")
        self.assertEqual(payload["fixtures"], [])
        self.assertEqual([row["matches"] for row in standings], [14] * 10)
        self.assertEqual(standings[0]["teamKey"], "Chennai")
        self.assertEqual(payload["analysis"]["method"], "Final standings")
        self.assertEqual(payload["playoffs"]["champion"], "Kolkata")
        self.assertEqual(payload["playoffs"]["runnerUp"], "Chennai")
        self.assertEqual(
            [match["stage"] for match in payload["playoffs"]["matches"]],
            ["Qualifier 1", "Eliminator", "Qualifier 2", "Final"],
        )
        self.assertEqual(payload["playoffs"]["matches"][-1]["result"], "KKR won by 5 wickets")

    def test_league_in_progress_is_rejected(self) -> None:
        with self.assertRaisesRegex(extract_table.SourceValidationError, "still in progress"):
            self.build(season_matches(league_match_count=60))


OFFICIAL_IPL_2026_NRR = {
    "Bangalore": 0.783,
    "Gujarat": 0.695,
    "Hyderabad": 0.524,
    "Rajasthan": 0.189,
    "Punjab": 0.309,
    "Delhi": -0.651,
    "Kolkata": -0.147,
    "Chennai": -0.345,
    "Mumbai": -0.584,
    "Lucknow": -0.740,
}
CACHED_IPL_ARCHIVE = extract_table.CRICSHEET_CACHE_DIR / "ipl_json.zip"


@unittest.skipUnless(CACHED_IPL_ARCHIVE.exists(), "Cricsheet IPL archive not cached locally")
class CricsheetRealDataTests(unittest.TestCase):
    def test_ipl_2026_nrr_matches_the_official_table(self) -> None:
        matches = cricsheet.load_season(CACHED_IPL_ARCHIVE, "2026")

        table = cricsheet.league_table(matches, extract_table.team_key)

        self.assertEqual({key: row.nrr for key, row in table.items()}, OFFICIAL_IPL_2026_NRR)


if __name__ == "__main__":
    unittest.main()
