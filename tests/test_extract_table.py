from __future__ import annotations

from datetime import datetime, timezone
from itertools import product
import unittest
from unittest import mock

import extract_table
from leagues import DEFAULT_LEAGUE_ID, load_league


_DEFAULT_NRR = object()


def valid_standings(nrr: object = _DEFAULT_NRR) -> list[dict[str, object]]:
    return [
        {
            "teamKey": meta.key,
            "shortName": meta.short_name,
            "fullName": meta.full_name,
            "matches": 8,
            "wins": 4,
            "losses": 4,
            "noResult": 0,
            "points": 8,
            "nrr": float(index) / 10 if nrr is _DEFAULT_NRR else nrr,
            "rank": index,
            "remainingMatches": 6,
        }
        for index, meta in enumerate(extract_table.TEAM_META.values(), start=1)
    ]


def valid_fixture(match_no: int = 44) -> dict[str, object]:
    team_keys = list(extract_table.TEAM_META)
    team_a = team_keys[match_no % len(team_keys)]
    team_b = team_keys[(match_no + 1) % len(team_keys)]
    return {
        "id": f"test-fixture-{match_no}",
        "matchNo": match_no,
        "teamA": team_a,
        "teamB": team_b,
        "dateTimeGMT": "2026-05-02T14:00:00Z",
        "dateTimeLocal": None,
        "venue": "MA Chidambaram Stadium, Chennai",
        "status": "scheduled",
        "sourceUrl": extract_table.CRICDATA_SERIES_INFO_URL,
    }


def valid_fixtures(count: int) -> list[dict[str, object]]:
    # Eight games each are played, so the remaining league matches are numbered 41-70.
    return [valid_fixture(match_no) for match_no in range(41, 41 + count)]


def completed_standings(nrr: object = _DEFAULT_NRR) -> list[dict[str, object]]:
    rows = valid_standings(nrr)
    for row in rows:
        row.update({"matches": 14, "wins": 7, "losses": 7, "points": 14, "remainingMatches": 0})
    return rows


FROZEN_MID_SEASON = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)


def analysis_stub() -> dict[str, object]:
    return {
        "method": "Exact all-combinations",
        "simulationCount": 1,
        "generatedAt": "2026-05-01T12:00:00Z",
        "overallProbabilities": {},
        "teamAnalysis": {"4": {}, "2": {}},
        "qualificationPath": {"4": {}, "2": {}},
    }


class ExtractTableTests(unittest.TestCase):
    def test_parse_cricdata_points_and_fixtures_payloads(self) -> None:
        points_payload = {
            "status": "success",
            "data": [
                {
                    "teamname": meta.full_name,
                    "matches": 8,
                    "wins": 4,
                    "losses": 4,
                    "nr": 0,
                    "points": 8,
                    "nrr": "0.250",
                }
                for meta in extract_table.TEAM_META.values()
            ],
        }
        fixtures_payload = {
            "status": "success",
            "data": {
                "matchList": [
                    {
                        "id": "match-44",
                        "name": "Chennai Super Kings vs Mumbai Indians, 44th Match",
                        "teams": ["Chennai Super Kings", "Mumbai Indians"],
                        "status": "Match not started",
                        "dateTimeGMT": "2026-05-02T14:00:00",
                        "venue": "MA Chidambaram Stadium, Chennai",
                    },
                    {
                        "id": "old-match",
                        "name": "Rajasthan Royals vs Delhi Capitals, 43rd Match",
                        "teams": ["Rajasthan Royals", "Delhi Capitals"],
                        "status": "Rajasthan Royals won by 5 wickets",
                        "matchEnded": True,
                    },
                ]
            },
        }

        standings = extract_table.parse_cricdata_standings(points_payload)
        fixtures = extract_table.parse_cricdata_fixtures(
            fixtures_payload,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(len(standings), 10)
        self.assertEqual(standings[0]["fullName"], "Chennai Super Kings")
        self.assertEqual(standings[0]["nrr"], 0.25)
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["id"], "match-44")
        self.assertEqual(fixtures[0]["teamA"], "Chennai")
        self.assertEqual(fixtures[0]["teamB"], "Mumbai")
        self.assertEqual(fixtures[0]["dateTimeGMT"], "2026-05-02T14:00:00Z")

    def test_parse_cricdata_standings_allows_missing_nrr(self) -> None:
        points_payload = {
            "status": "success",
            "data": [
                {
                    "teamname": meta.full_name,
                    "matches": 8,
                    "wins": 4,
                    "losses": 4,
                    "nr": 0,
                    "points": 8,
                }
                for meta in extract_table.TEAM_META.values()
            ],
        }

        standings = extract_table.parse_cricdata_standings(points_payload)

        self.assertEqual(len(standings), 10)
        self.assertIsNone(standings[0]["nrr"])

    def test_derive_cricdata_standings_from_match_results(self) -> None:
        info_payload = {
            "status": "success",
            "data": {
                "matchList": [
                    {
                        "id": "m1",
                        "name": "Punjab Kings vs Royal Challengers Bengaluru, 1st Match",
                        "teams": ["Punjab Kings", "Royal Challengers Bengaluru"],
                        "status": "Punjab Kings won by 7 wickets",
                        "matchEnded": True,
                    },
                    {
                        "id": "m2",
                        "name": "Sunrisers Hyderabad vs Rajasthan Royals, 2nd Match",
                        "teams": ["Sunrisers Hyderabad", "Rajasthan Royals"],
                        "status": "No result",
                        "matchEnded": True,
                    },
                    {
                        "id": "m3",
                        "name": "Gujarat Titans vs Delhi Capitals, 3rd Match",
                        "teams": ["Gujarat Titans", "Delhi Capitals"],
                        "status": "Match not started",
                    },
                ]
            },
        }

        standings = extract_table.derive_cricdata_standings_from_matches(info_payload)
        by_key = {row["teamKey"]: row for row in standings}

        self.assertEqual(by_key["Punjab"]["wins"], 1)
        self.assertEqual(by_key["Punjab"]["points"], 2)
        self.assertEqual(by_key["Bangalore"]["losses"], 1)
        self.assertEqual(by_key["Hyderabad"]["noResult"], 1)
        self.assertEqual(by_key["Rajasthan"]["points"], 1)
        self.assertEqual(by_key["Gujarat"]["matches"], 0)

    def test_points_table_nrr_is_attached_only_when_record_matches_results(self) -> None:
        standings = valid_standings(nrr=None)
        points_payload = {
            "status": "success",
            "data": [
                {
                    "teamname": row["fullName"],
                    "matches": row["matches"],
                    "wins": row["wins"],
                    "losses": row["losses"],
                    "nr": row["noResult"],
                    "points": row["points"],
                    "nrr": "0.250",
                }
                for row in standings
            ],
        }
        points_payload["data"][0]["losses"] = 5
        warnings: list[str] = []

        extract_table.apply_cricdata_nrr_from_points(standings, points_payload, warnings)

        self.assertIsNone(standings[0]["nrr"])
        self.assertEqual(standings[1]["nrr"], 0.25)
        self.assertTrue(any("did not match match results" in warning for warning in warnings))

    def test_validation_rejects_impossible_match_counts(self) -> None:
        standings = [
            {
                "teamKey": meta.key,
                "shortName": meta.short_name,
                "fullName": meta.full_name,
                "matches": 15 if meta.key == "Mumbai" else 8,
                "wins": 4,
                "losses": 4,
                "noResult": 0,
                "points": 8,
                "nrr": 0.0,
                "rank": index,
                "remainingMatches": 0,
            }
            for index, meta in enumerate(extract_table.TEAM_META.values(), start=1)
        ]

        with self.assertRaisesRegex(extract_table.SourceValidationError, "above 14"):
            extract_table.validate_source_data(
                standings,
                [{"teamA": "Chennai", "teamB": "Mumbai"}],
                datetime(2026, 5, 1, tzinfo=timezone.utc),
                strict_zero_fixtures=True,
            )

    def test_validation_rejects_bad_row_arithmetic(self) -> None:
        standings = valid_standings()
        standings[0]["points"] = 9

        with self.assertRaisesRegex(extract_table.SourceValidationError, "Invalid standings points"):
            extract_table.validate_source_data(
                standings,
                [valid_fixture()],
                datetime(2026, 5, 1, tzinfo=timezone.utc),
                strict_zero_fixtures=True,
            )

    def test_validation_rejects_inconsistent_win_loss_totals(self) -> None:
        standings = valid_standings()
        standings[0]["matches"] = 9
        standings[0]["losses"] = 5
        standings[0]["remainingMatches"] = 5

        with self.assertRaisesRegex(extract_table.SourceValidationError, "wins=40, losses=41"):
            extract_table.validate_source_data(
                standings,
                [valid_fixture()],
                datetime(2026, 5, 1, tzinfo=timezone.utc),
                strict_zero_fixtures=True,
            )

    def test_validation_rejects_partial_fixture_feed_when_required(self) -> None:
        standings = valid_standings()

        with self.assertRaisesRegex(extract_table.SourceValidationError, "Fixture feed appears partial"):
            extract_table.validate_source_data(
                standings,
                [valid_fixture()],
                datetime(2026, 5, 1, tzinfo=timezone.utc),
                strict_zero_fixtures=True,
                strict_partial_fixtures=True,
            )

    def test_series_id_prefers_explicit_configuration(self) -> None:
        session = mock.Mock()

        with mock.patch.dict(extract_table.os.environ, {"CRICDATA_SERIES_ID": "ipl-2026-series"}, clear=True):
            series_id = extract_table.find_cricdata_series_id(session, "api-key")

        self.assertEqual(series_id, "ipl-2026-series")
        session.get.assert_not_called()

    def test_build_payload_requires_cricketdata_api_key(self) -> None:
        with mock.patch.dict(extract_table.os.environ, {}, clear=True):
            with self.assertRaisesRegex(extract_table.SourceValidationError, "CRICDATA_API_KEY"):
                extract_table.build_payload()

    def test_build_payload_uses_cricketdata_only(self) -> None:
        standings = valid_standings()
        fixtures = valid_fixtures(30)

        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(standings, fixtures, []),
        ) as cricdata_mock, mock.patch.object(
            extract_table,
            "run_analysis",
            return_value=analysis_stub(),
        ):
            payload = extract_table.build_payload()

        self.assertEqual(payload["metadata"]["source"], "CricketData")
        self.assertEqual(payload["metadata"]["source_url"], extract_table.CRICDATA_SOURCE_URL)
        self.assertEqual(payload["metadata"]["season_status"], "league_stage")
        self.assertEqual(payload["metadata"]["warnings"], [])
        cricdata_mock.assert_called_once()

    def test_build_payload_allows_missing_nrr_for_probability_generation(self) -> None:
        standings = valid_standings(nrr=None)
        fixtures = valid_fixtures(30)

        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(
                standings,
                fixtures,
                ["CricketData standings omitted NRR for all teams; probabilities were generated without NRR."],
            ),
        ), mock.patch.object(
            extract_table,
            "run_analysis",
            return_value=analysis_stub(),
        ):
            payload = extract_table.build_payload()

        self.assertEqual(payload["metadata"]["source"], "CricketData")
        self.assertIsNone(payload["standings"][0]["nrr"])
        self.assertIn("omitted NRR", payload["metadata"]["warnings"][0])

    def test_build_payload_rejects_invalid_cricketdata_standings_without_fallback(self) -> None:
        invalid_standings = valid_standings()
        invalid_standings[0]["matches"] = 9
        invalid_standings[0]["losses"] = 5
        invalid_standings[0]["remainingMatches"] = 5
        cricdata_fixtures = valid_fixtures(30)

        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(invalid_standings, cricdata_fixtures, []),
        ) as cricdata_mock:
            with self.assertRaisesRegex(extract_table.SourceValidationError, "Inconsistent league result totals"):
                extract_table.build_payload()

        cricdata_mock.assert_called_once()

    def test_build_payload_rejects_partial_cricketdata_fixtures(self) -> None:
        standings = valid_standings()
        partial_fixtures = [valid_fixture()]

        # The partial-feed check only applies before the league stage ends, so pin the clock.
        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(standings, partial_fixtures, []),
        ) as cricdata_mock, mock.patch.object(extract_table, "utc_now", return_value=FROZEN_MID_SEASON):
            with self.assertRaisesRegex(extract_table.SourceValidationError, "Fixture feed appears partial"):
                extract_table.build_payload()

        cricdata_mock.assert_called_once()

    def test_build_payload_ignores_playoff_fixtures_once_league_is_complete(self) -> None:
        playoff_fixtures = [dict(valid_fixture(), matchNo=None), dict(valid_fixture(45), matchNo=None)]

        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(completed_standings(), playoff_fixtures, []),
        ), mock.patch.object(extract_table, "utc_now", return_value=FROZEN_MID_SEASON):
            payload = extract_table.build_payload()

        self.assertEqual(payload["fixtures"], [])
        self.assertEqual(payload["metadata"]["season_status"], "playoffs")
        self.assertIn("Ignored 2 non-league fixture(s)", payload["metadata"]["warnings"][0])
        self.assertEqual(payload["analysis"]["method"], "Final standings")

    def test_league_stage_fixtures_drops_match_numbers_beyond_the_league(self) -> None:
        warnings: list[str] = []
        fixtures = valid_fixtures(29) + [valid_fixture(71)]

        kept = extract_table.league_stage_fixtures(fixtures, valid_standings(), warnings)

        self.assertEqual(len(kept), 29)
        self.assertNotIn(71, [fixture["matchNo"] for fixture in kept])
        self.assertEqual(len(warnings), 1)

    def test_league_stage_fixtures_rejects_more_fixtures_than_remain(self) -> None:
        fixtures = [dict(valid_fixture(41 + index % 30), id=f"dup-{index}") for index in range(31)]

        with self.assertRaisesRegex(extract_table.SourceValidationError, "lists 31 league match"):
            extract_table.league_stage_fixtures(fixtures, valid_standings(), [])

    def test_completed_league_with_nrr_uses_final_table(self) -> None:
        standings = extract_table.ranked_standings(completed_standings())

        analysis = extract_table.run_analysis(standings, [], FROZEN_MID_SEASON)

        top4 = {key for key, value in analysis["overallProbabilities"].items() if value["top4"] == 100.0}
        self.assertEqual(analysis["method"], "Final standings")
        self.assertEqual(top4, {row["teamKey"] for row in standings if row["rank"] <= 4})
        self.assertEqual(sum(value["top2"] for value in analysis["overallProbabilities"].values()), 200.0)

    def test_completed_league_without_nrr_shares_tied_slots(self) -> None:
        standings = completed_standings(nrr=None)

        analysis = extract_table.run_analysis(standings, [], FROZEN_MID_SEASON)

        # All ten teams finish level on points and wins, so four slots are shared ten ways.
        self.assertEqual({value["top4"] for value in analysis["overallProbabilities"].values()}, {40.0})

    def test_season_with_no_results_yet_starts_every_team_level(self) -> None:
        extract_table.use_league(load_league("wpl-2027"))
        self.addCleanup(extract_table.use_league, load_league(DEFAULT_LEAGUE_ID))
        names = [meta.full_name for meta in extract_table.TEAM_META.values()]
        unplayed = [
            {"id": f"m{number}", "name": f"{a} vs {b}, {number}th Match", "teams": [a, b],
             "dateTimeGMT": f"2027-01-{14 + number // 2:02d}T14:00:00", "matchStarted": False, "matchEnded": False}
            for number, (a, b) in enumerate(
                [(x, y) for _ in range(2) for i, x in enumerate(names) for y in names[i + 1:]], start=1
            )
        ]

        def fake_json(session, endpoint, api_key, params=None):
            if endpoint != "series_info":
                raise AssertionError(f"{endpoint} should not be called before the first result")
            return {"status": "success", "data": {"matchList": unplayed}}

        now = datetime(2027, 1, 13, 20, tzinfo=timezone.utc)
        with mock.patch.dict(extract_table.os.environ, {"CRICDATA_API_KEY": "key"}, clear=True), mock.patch.object(
            extract_table, "find_cricdata_series_id", return_value="wpl-2027"
        ), mock.patch.object(extract_table, "fetch_cricdata_json", side_effect=fake_json), mock.patch.object(
            extract_table, "utc_now", return_value=now
        ):
            payload = extract_table.build_payload()

        odds = payload["analysis"]["overallProbabilities"]
        self.assertEqual(payload["metadata"]["warnings"], [])
        self.assertEqual({row["matches"] for row in payload["standings"]}, {0})
        self.assertEqual(len(payload["fixtures"]), 20)
        self.assertEqual({value["top3"] for value in odds.values()}, {60.0})
        self.assertEqual({value["top1"] for value in odds.values()}, {20.0})

    def test_simulation_rank_tolerates_missing_nrr(self) -> None:
        table = {
            row["teamKey"]: {"points": row["points"], "wins": row["wins"], "nrr": None}
            for row in valid_standings(nrr=None)
        }

        self.assertEqual(len(extract_table.simulation_rank(table)), 10)

    def test_exact_model_notes_explain_equal_records_can_diverge_by_schedule(self) -> None:
        standings = valid_standings(nrr=None)
        fixtures = [valid_fixture()]

        analysis = extract_table.run_exact_dp_analysis(
            standings,
            fixtures,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

        self.assertTrue(
            any("identical records" in note and "remaining fixtures" in note for note in analysis["modelNotes"])
        )

    def test_exact_dp_matches_bruteforce_when_equal_records_have_different_schedules(self) -> None:
        def row(team_key: str, points: int, wins: int, rank: int) -> dict[str, object]:
            meta = extract_table.TEAM_META[team_key]
            return {
                "teamKey": team_key,
                "shortName": meta.short_name,
                "fullName": meta.full_name,
                "matches": 10,
                "wins": wins,
                "losses": 10 - wins,
                "noResult": 0,
                "points": points,
                "nrr": None,
                "rank": rank,
                "remainingMatches": 1,
            }

        standings = [
            row("Chennai", 16, 8, 1),
            row("Delhi", 16, 8, 2),
            row("Kolkata", 14, 7, 3),
            row("Gujarat", 12, 6, 4),
            row("Rajasthan", 12, 6, 5),
            row("Bangalore", 12, 6, 6),
            row("Mumbai", 10, 5, 7),
            row("Punjab", 10, 5, 8),
            row("Hyderabad", 8, 4, 9),
            row("Lucknow", 6, 3, 10),
        ]
        fixtures = [
            {"id": "f1", "matchNo": 1, "teamA": "Gujarat", "teamB": "Rajasthan"},
            {"id": "f2", "matchNo": 2, "teamA": "Bangalore", "teamB": "Lucknow"},
            {"id": "f3", "matchNo": 3, "teamA": "Mumbai", "teamB": "Punjab"},
        ]

        analysis = extract_table.run_exact_dp_analysis(
            standings,
            fixtures,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

        team_keys = [item["teamKey"] for item in standings]
        team_index = {team_key: idx for idx, team_key in enumerate(team_keys)}
        base_points = [int(item["points"]) for item in standings]
        base_wins = [int(item["wins"]) for item in standings]
        fixture_pairs = [(str(item["teamA"]), str(item["teamB"])) for item in fixtures]
        brute_force_totals = {team_key: 0.0 for team_key in team_keys}

        for outcomes in product((0, 1), repeat=len(fixture_pairs)):
            points = base_points[:]
            wins = base_wins[:]
            for outcome, (left, right) in zip(outcomes, fixture_pairs):
                winner = left if outcome == 0 else right
                idx = team_index[winner]
                points[idx] += 2
                wins[idx] += 1
            shares = extract_table.top_share_for_state(points, wins, 4)
            for idx, team_key in enumerate(team_keys):
                brute_force_totals[team_key] += shares[idx]

        scenario_count = 2 ** len(fixture_pairs)
        for team_key in ("Gujarat", "Rajasthan", "Bangalore"):
            expected = round((brute_force_totals[team_key] / scenario_count) * 100, 2)
            self.assertEqual(analysis["overallProbabilities"][team_key]["top4"], expected)

        self.assertEqual(
            (standings[3]["matches"], standings[3]["wins"], standings[3]["points"]),
            (standings[4]["matches"], standings[4]["wins"], standings[4]["points"]),
        )
        self.assertEqual(
            (standings[4]["matches"], standings[4]["wins"], standings[4]["points"]),
            (standings[5]["matches"], standings[5]["wins"], standings[5]["points"]),
        )
        self.assertGreater(
            analysis["overallProbabilities"]["Gujarat"]["top4"],
            analysis["overallProbabilities"]["Bangalore"]["top4"],
        )


if __name__ == "__main__":
    unittest.main()
