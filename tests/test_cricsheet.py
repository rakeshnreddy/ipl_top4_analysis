from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
from datetime import datetime, timezone

import cricsheet
import extract_table
from leagues import DEFAULT_LEAGUE_ID, ExtraResult, load_league


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


def innings_of(team: str, balls: int, runs: int, wickets: int = 0, **extra: object) -> dict[str, object]:
    """An innings of exactly ``runs`` off ``balls`` legal balls."""
    data = innings(team, balls, runs // balls, wickets, **extra)
    deliveries = [delivery for over in data["overs"] for delivery in over["deliveries"]]
    for delivery in deliveries[: runs % balls]:
        delivery["runs"]["total"] += 1
    return data


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


def round_robin_season(names: list[str], season: str = "2026", rounds: int = 2) -> list[dict[str, object]]:
    """Every pair meets ``rounds`` times and the team listed first always wins."""
    matches = []
    for _ in range(rounds):
        for left in range(len(names)):
            for right in range(left + 1, len(names)):
                matches.append(
                    raw_match(
                        names[left],
                        names[right],
                        {"winner": names[left], "by": {"runs": 120}},
                        [innings(names[left], 120, 2), innings(names[right], 120, 1, target={"runs": 241, "overs": 20})],
                        match_number=len(matches) + 1,
                        season=season,
                    )
                )
    return matches


def playoff(stage: str, winner: str, loser: str, date: str, season: str = "2026") -> dict[str, object]:
    return raw_match(
        winner,
        loser,
        {"winner": winner, "by": {"wickets": 5}},
        [innings(loser, 120, 1), innings(winner, 100, 2, target={"runs": 121, "overs": 20})],
        stage=stage,
        date=date,
        season=season,
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

    def test_tie_without_a_super_over_splits_the_points(self) -> None:
        match = parse(
            raw_match(
                TEAMS[0],
                TEAMS[1],
                {"result": "tie"},
                [innings(TEAMS[0], 120, 1), innings(TEAMS[1], 120, 1, target={"runs": 121, "overs": 20})],
            )
        )

        table = cricsheet.league_table([match], extract_table.team_key, cricsheet.PointsRule(win=4, tie=2))

        self.assertEqual((table["Chennai"].ties, table["Chennai"].points), (1, 2))
        self.assertEqual(table["Delhi"].nrr, 0.0)

    def test_bonus_point_needs_a_run_rate_one_and_a_quarter_times_the_losers(self) -> None:
        rule = cricsheet.PointsRule(win=4, no_result=2, bonus_run_rate_ratio=1.25)
        big_win = parse(raw_match(TEAMS[0], TEAMS[1], {"winner": TEAMS[0], "by": {"runs": 30}},
                                  [innings(TEAMS[0], 120, 2), innings(TEAMS[1], 120, 1, target={"runs": 241, "overs": 20})]))
        close_win = parse(raw_match(TEAMS[2], TEAMS[3], {"winner": TEAMS[2], "by": {"runs": 1}},
                                    [innings(TEAMS[2], 120, 1), innings(TEAMS[3], 119, 1, target={"runs": 121, "overs": 20})]))

        table = cricsheet.league_table([big_win, close_win], extract_table.team_key, rule)

        self.assertEqual((table["Chennai"].bonus_points, table["Chennai"].points), (1, 5))
        self.assertEqual((table["Gujarat"].bonus_points, table["Gujarat"].points), (0, 4))

    SUPER_SMASH_WOMEN = cricsheet.PointsRule(win=4, no_result=2, tie=2, bonus_runs=150, bonus_chase_run_rate_ratio=1.25)

    def test_150_runs_earns_a_bonus_point_win_or_lose(self) -> None:
        match = parse(raw_match(TEAMS[0], TEAMS[1], {"winner": TEAMS[1], "by": {"wickets": 5}},
                                [innings_of(TEAMS[0], 120, 160, wickets=4),
                                 innings_of(TEAMS[1], 118, 161, wickets=5, target={"runs": 161, "overs": 20})]))
        close = parse(raw_match(TEAMS[2], TEAMS[3], {"winner": TEAMS[2], "by": {"runs": 1}},
                                [innings_of(TEAMS[2], 120, 149), innings_of(TEAMS[3], 120, 148, target={"runs": 150, "overs": 20})]))

        table = cricsheet.league_table([match, close], extract_table.team_key, self.SUPER_SMASH_WOMEN)

        self.assertEqual((table["Chennai"].bonus_points, table["Chennai"].points), (1, 1))
        self.assertEqual((table["Delhi"].bonus_points, table["Delhi"].points), (1, 5))
        self.assertEqual((table["Gujarat"].bonus_points, table["Kolkata"].bonus_points), (0, 0))

    def test_the_runs_target_shrinks_with_the_overs_in_a_reduced_match(self) -> None:
        # Five overs a side: 150 off 20 overs becomes 37.5.
        match = parse(raw_match(TEAMS[0], TEAMS[1], {"winner": TEAMS[0], "by": {"runs": 3}},
                                [innings_of(TEAMS[0], 30, 40, wickets=2), innings_of(TEAMS[1], 30, 37, wickets=3, target={"runs": 41, "overs": 5})]))

        table = cricsheet.league_table([match], extract_table.team_key, self.SUPER_SMASH_WOMEN)

        self.assertEqual((table["Chennai"].bonus_points, table["Delhi"].bonus_points), (1, 0))

    def test_a_chase_needs_more_than_one_and_a_quarter_times_the_first_innings_rate(self) -> None:
        def chase(balls: int) -> cricsheet.Match:
            return parse(raw_match(TEAMS[0], TEAMS[1], {"winner": TEAMS[1], "by": {"wickets": 5}},
                                   [innings_of(TEAMS[0], 120, 120, wickets=6),
                                    innings_of(TEAMS[1], balls, 125, wickets=5, target={"runs": 121, "overs": 20})]))

        for balls, expected in ((99, 1), (100, 0)):  # 7.58 and exactly 7.5 runs an over against 6.0
            with self.subTest(balls=balls):
                table = cricsheet.league_table([chase(balls)], extract_table.team_key, self.SUPER_SMASH_WOMEN)
                self.assertEqual((table["Delhi"].bonus_points, table["Chennai"].bonus_points), (expected, 0))

    def test_no_result_earns_no_bonus_point(self) -> None:
        match = parse(raw_match(TEAMS[0], TEAMS[1], {"result": "no result"},
                                [innings_of(TEAMS[0], 120, 180), innings_of(TEAMS[1], 12, 20)]))

        table = cricsheet.league_table([match], extract_table.team_key, self.SUPER_SMASH_WOMEN)

        self.assertEqual((table["Chennai"].bonus_points, table["Chennai"].points), (0, 2))

    def test_a_side_that_runs_out_of_batters_is_charged_its_full_quota(self) -> None:
        # Nine wickets down in 18.1 overs and beaten: the tenth batter was absent, so all out.
        match = parse(raw_match(TEAMS[0], TEAMS[1], {"winner": TEAMS[0], "by": {"runs": 11}},
                                [innings(TEAMS[0], 120, 1), innings(TEAMS[1], 109, 1, wickets=9, target={"runs": 121, "overs": 20})]))

        self.assertEqual(cricsheet.nrr_lines(match)[1], (TEAMS[1], 109, 120))

    def test_hundred_style_innings_count_five_ball_sets(self) -> None:
        data = raw_match(TEAMS[0], TEAMS[1], {"winner": TEAMS[1], "by": {"wickets": 5}},
                         [innings(TEAMS[0], 100, 1, wickets=10), innings(TEAMS[1], 50, 2, target={"runs": 101, "overs": 20})])
        data["info"]["balls_per_over"] = 5

        match = parse(data)

        self.assertEqual((match.scheduled_balls, match.target_balls), (100, 100))
        self.assertEqual(cricsheet.nrr_lines(match)[0], (TEAMS[0], 100, 100))

    def test_load_season_can_filter_a_mixed_gender_archive(self) -> None:
        men = raw_match(TEAMS[0], TEAMS[1], {"result": "no result"}, [])
        women = raw_match(TEAMS[2], TEAMS[3], {"result": "no result"}, [])
        men["info"]["gender"], women["info"]["gender"] = "male", "female"
        with tempfile.TemporaryDirectory() as tmp:
            archive = write_archive(Path(tmp), [men, women])

            matches = cricsheet.load_season(archive, "2026", gender="female")

        self.assertEqual([match.teams for match in matches], [(TEAMS[2], TEAMS[3])])

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


class LeagueSeasonTests(unittest.TestCase):
    frozen_now = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def setUp(self) -> None:
        self.wpl = load_league("wpl-2026")
        self.names = [team.full_name for team in self.wpl.teams]

    def tearDown(self) -> None:
        extract_table.use_league(load_league(DEFAULT_LEAGUE_ID))

    def build(self, league, matches: list[dict[str, object]]) -> dict[str, object]:
        extract_table.use_league(league)
        with tempfile.TemporaryDirectory() as tmp:
            archive = write_archive(Path(tmp), matches)
            with mock.patch.object(extract_table, "utc_now", return_value=self.frozen_now):
                return extract_table.build_cricsheet_payload(archive)

    def test_wpl_qualifies_top_three_with_one_bye_to_the_final(self) -> None:
        rcb, gg, dc = self.names[:3]
        playoffs = [
            playoff("Eliminator", dc, gg, "2026-02-03", season="2025/26"),
            playoff("Final", rcb, dc, "2026-02-05", season="2025/26"),
        ]

        payload = self.build(self.wpl, round_robin_season(self.names, season="2025/26") + playoffs)

        probabilities = payload["analysis"]["overallProbabilities"]
        self.assertEqual([tier["label"] for tier in payload["league"]["qualification"]], ["Top 3", "Top 1"])
        self.assertEqual([row["teamKey"] for row in payload["standings"]], ["RCB", "GG", "DC", "MI", "UPW"])
        self.assertEqual({key for key, value in probabilities.items() if value["top3"] == 100.0}, {"RCB", "GG", "DC"})
        self.assertEqual(probabilities["RCB"]["top1"], 100.0)
        self.assertEqual(payload["playoffs"]["champion"], "RCB")
        self.assertEqual(payload["playoffs"]["matches"][0]["result"], "DC won by 5 wickets")

    def test_extra_results_fill_matches_missing_from_cricsheet(self) -> None:
        rcb, gg = self.names[:2]
        matches = round_robin_season(self.names, season="2025/26")
        del matches[10]  # the second RCB v GG game had no play
        league = dataclasses.replace(
            self.wpl,
            extra_results=(ExtraResult("2026-01-20", (rcb, gg), "Abandoned without a ball bowled"),),
        )

        payload = self.build(league, matches)

        rows = {row["teamKey"]: row for row in payload["standings"]}
        self.assertEqual((rows["RCB"]["noResult"], rows["RCB"]["points"]), (1, 15))
        self.assertEqual((rows["GG"]["noResult"], rows["GG"]["points"]), (1, 13))
        self.assertIn("Abandoned without a ball bowled", payload["metadata"]["notes"][0])

    def test_unique_cricsheet_stage_names_are_kept_even_on_the_same_day(self) -> None:
        rcb, gg, dc = self.names[:3]
        playoffs = [
            playoff("Final", rcb, dc, "2026-02-03", season="2025/26"),
            playoff("Eliminator", dc, gg, "2026-02-03", season="2025/26"),
        ]

        payload = self.build(self.wpl, round_robin_season(self.names, season="2025/26") + playoffs)

        stages = {match["stage"]: match["winner"] for match in payload["playoffs"]["matches"]}
        self.assertEqual(stages, {"Final": "RCB", "Eliminator": "DC"})

    def test_unexpected_playoff_count_keeps_cricsheet_stage_names(self) -> None:
        _, gg, dc = self.names[:3]
        semi = playoff("Semi-final", dc, gg, "2026-02-03", season="2025/26")

        payload = self.build(self.wpl, round_robin_season(self.names, season="2025/26") + [semi])

        self.assertEqual(payload["playoffs"]["matches"][0]["stage"], "Semi-final")
        self.assertIn("Expected 2 playoff matches but Cricsheet has 1", payload["metadata"]["warnings"][0])
        self.assertEqual(payload["metadata"]["season_status"], "playoffs")


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


# Final league tables (points, NRR) as published by each competition.
OFFICIAL_TABLES = {
    "wpl-2026": {"RCB": (12, 1.247), "GG": (10, -0.168), "DC": (8, -0.055), "MI": (6, 0.059), "UPW": (4, -1.076)},
    "psl-2026": {
        "PZ": (17, 2.324), "IU": (13, 1.667), "MS": (12, 0.326), "HK": (10, -0.361),
        "LQ": (10, -0.482), "KK": (10, -0.869), "QG": (6, -0.41), "RPZ": (2, -1.76),
    },
    "bbl-2025-26": {
        "SCO": (14, 1.363), "SIX": (13, 0.605), "HUR": (13, 0.331), "STA": (12, 0.759),
        "HEA": (10, -0.431), "STR": (8, -0.231), "REN": (6, -1.202), "THU": (4, -1.212),
    },
    "mlc-2026": {
        "SFU": (12, 0.487), "LAKR": (12, 0.245), "WAF": (12, -0.399),
        "MINY": (10, -0.165), "SEO": (8, 0.034), "TSK": (6, -0.151),
    },
    "ilt-2025-26": {"DV": (16, 0.438), "MIE": (14, 0.676), "DUC": (10, 0.578), "ADKR": (8, -0.559), "GG": (6, -0.31), "SJW": (6, -0.815)},
    "bpl-2025-26": {"RJW": (16, 0.335), "CHR": (12, 0.497), "RAN": (12, 0.22), "SYT": (10, 0.373), "DHC": (6, -0.381), "NOE": (4, -1.038)},
    "lpl-2026": {"JK": (11, 0.385), "GG": (10, 0.604), "CK": (8, 0.108), "KR": (6, -0.567), "DS": (5, -0.565)},
    # 4 points a win, 2 a no result, plus a bonus point for winning at 1.25x the loser's run rate.
    "sa20-2025-26": {"SEC": (28, 1.762), "PC": (24, 0.218), "PR": (24, -0.922), "JSK": (22, 0.045), "DSG": (19, -0.068), "MICT": (14, -1.013)},
    # The Hundred measures NRR per 5-ball set.
    "hundred-men-2026": {
        "TR": (24, 0.74), "MSG": (20, 0.791), "SRL": (20, 0.603), "MIL": (20, 0.241),
        "WF": (16, -0.9), "SB": (12, -0.015), "LS": (12, -0.098), "BP": (4, -1.318),
    },
    "hundred-women-2026": {
        "TR": (28, 1.391), "SRL": (20, 1.031), "SB": (20, 0.107), "MSG": (18, 0.344),
        "WF": (16, 0.133), "LS": (10, -0.363), "BP": (10, -1.602), "MIL": (6, -1.165),
    },
    # https://www.espn.com/cricket/table/series/20898 (ESPNcricinfo's table, with runs and overs for and against).
    "wcpl-2026": {"TKR": (4, 1.016), "GAW": (4, 0.475), "BT": (2, -0.444), "JE": (2, -1.153)},
    "cpl-2026": {
        "GAW": (16, 0.615), "ABF": (13, 0.174), "BT": (12, -0.125), "JAK": (8, -0.085),
        "SLK": (8, -0.887), "SKNP": (7, 0.252), "TKR": (6, -0.01),
    },
    # https://www.cricket.com.au/matches/series/CA:3193 (ladder). Heat v Sixers on 28 Nov was abandoned without a ball.
    "wbbl-2025-26": {
        "HUR": (15, 0.662), "SIX": (13, -0.313), "SCO": (12, -0.132), "STA": (11, 0.629),
        "REN": (10, 0.121), "STR": (9, 0.077), "THU": (9, -0.124), "HEA": (1, -0.869),
    },
    # https://www.espn.com/cricket/table/series/8654 (ESPNcricinfo's table, which also lists runs and overs for and
    # against). 4 points a win, 2 a tie or no result; three matches were abandoned without a ball.
    "super-smash-men-2025-26": {
        "NB": (28, 1.977), "AA": (24, 0.491), "CK": (20, -0.864), "CS": (18, -0.6), "OV": (16, -0.622), "WF": (14, 0.031),
    },
    # https://www.espn.com/cricket/table/series/8819, with bonus points (150 runs, or chasing at more than 1.25x
    # the first innings' rate): https://www.nzc.nz/news-items/archive/bonus-point-system-introduced-to-women-s-super-smash/
    "super-smash-women-2025-26": {
        "WB": (33, 0.891), "NB": (28, 0.702), "AH": (25, 0.316), "CH": (25, -0.281), "OS": (22, 0.247), "CM": (6, -1.82),
    },
}


class OfficialTablesTests(unittest.TestCase):
    """Runs against cached Cricsheet archives; skipped when none are cached."""

    def tearDown(self) -> None:
        extract_table.use_league(load_league(DEFAULT_LEAGUE_ID))

    def test_cricsheet_reproduces_official_tables(self) -> None:
        checked = 0
        for league_id, expected in OFFICIAL_TABLES.items():
            league = load_league(league_id)
            archive = extract_table.CRICSHEET_CACHE_DIR / f"{league.cricsheet_competition}_json.zip"
            if not archive.exists():
                continue
            with self.subTest(league=league_id):
                extract_table.use_league(league)
                payload = extract_table.build_cricsheet_payload(archive)
                actual = {row["teamKey"]: (row["points"], row["nrr"]) for row in payload["standings"]}
                self.assertEqual(actual, expected)
            checked += 1
        if not checked:
            self.skipTest("No Cricsheet archives cached locally")


if __name__ == "__main__":
    unittest.main()
