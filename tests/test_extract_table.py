from __future__ import annotations

from datetime import datetime, timezone
from itertools import product
import unittest
from unittest import mock

import extract_table


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
    return [valid_fixture(match_no) for match_no in range(44, 44 + count)]


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
    def test_parse_cricbuzz_points_table_fixture(self) -> None:
        html = """
        <html><body>
          <div>Teams</div><div>P</div><div>W</div><div>L</div><div>NR</div><div>Pts</div><div>NRR</div>
          <div>1</div><div>Punjab Kings</div><div>8</div><div>6</div><div>1</div><div>1</div><div>13</div><div>+1.043</div>
          <div>2</div><div>Royal Challengers Bengaluru</div><div>9</div><div>6</div><div>3</div><div>0</div><div>12</div><div>+1.420</div>
          <div>3</div><div>Sunrisers Hyderabad</div><div>9</div><div>6</div><div>3</div><div>0</div><div>12</div><div>+0.832</div>
          <div>4</div><div>Rajasthan Royals</div><div>10</div><div>6</div><div>4</div><div>0</div><div>12</div><div>+0.510</div>
          <div>5</div><div>Gujarat Titans</div><div>9</div><div>5</div><div>4</div><div>0</div><div>10</div><div>-0.192</div>
          <div>6</div><div>Delhi Capitals</div><div>9</div><div>4</div><div>5</div><div>0</div><div>8</div><div>-0.895</div>
          <div>7</div><div>Chennai Super Kings</div><div>8</div><div>3</div><div>5</div><div>0</div><div>6</div><div>-0.121</div>
          <div>8</div><div>Kolkata Knight Riders</div><div>8</div><div>2</div><div>5</div><div>1</div><div>5</div><div>-0.751</div>
          <div>9</div><div>Mumbai Indians</div><div>8</div><div>2</div><div>6</div><div>0</div><div>4</div><div>-0.784</div>
          <div>10</div><div>Lucknow Super Giants</div><div>8</div><div>2</div><div>6</div><div>0</div><div>4</div><div>-1.106</div>
        </body></html>
        """

        standings = extract_table.parse_cricbuzz_standings(html)

        self.assertEqual(len(standings), 10)
        self.assertEqual(standings[0]["shortName"], "PBKS")
        self.assertEqual(standings[1]["fullName"], "Royal Challengers Bengaluru")
        self.assertEqual(standings[1]["nrr"], 1.42)
        self.assertEqual(standings[-1]["remainingMatches"], 6)

    def test_parse_and_enrich_next_fixture(self) -> None:
        list_html = """
        <a href="/live-cricket-scores/151987/csk-vs-mi-44th-match-ipl-2026">
          Chennai Super Kings vs Mumbai Indians, 44th Match
        </a>
        """
        detail_html = """
        <main>
          <span>Match starts at May 02, 14:00 GMT</span>
          <span>Venue: MA Chidambaram Stadium, Chennai</span>
          <span>Date & Time: Sat, May 02, 7:30 PM LOCAL Info</span>
        </main>
        """

        fixtures = extract_table.parse_cricbuzz_fixtures(list_html, extract_table.CRICBUZZ_TABLE_URL)
        enriched = extract_table.enrich_fixture_from_match_page(fixtures[0], detail_html)

        self.assertEqual(enriched["matchNo"], 44)
        self.assertEqual(enriched["teamA"], "Chennai")
        self.assertEqual(enriched["teamB"], "Mumbai")
        self.assertEqual(enriched["dateTimeGMT"], "2026-05-02T14:00:00Z")
        self.assertEqual(enriched["venue"], "MA Chidambaram Stadium, Chennai")

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

    def test_legacy_outputs_are_derived_from_canonical_payload(self) -> None:
        standings = [
            {
                "teamKey": meta.key,
                "shortName": meta.short_name,
                "fullName": meta.full_name,
                "matches": 8,
                "wins": 4,
                "losses": 4,
                "noResult": 0,
                "points": 8,
                "nrr": 0.123,
                "rank": index,
                "remainingMatches": 6,
            }
            for index, meta in enumerate(extract_table.TEAM_META.values(), start=1)
        ]
        payload = {
            "metadata": {
                "generated_at": "2026-05-01T12:00:00Z",
                "source": "Test",
            },
            "standings": standings,
            "fixtures": [{"teamA": "Chennai", "teamB": "Mumbai"}],
            "analysis": {
                "generatedAt": "2026-05-01T12:00:00Z",
                "method": "Exhaustive",
                "simulationCount": 2,
                "overallProbabilities": {
                    team["teamKey"]: {"top4": 50, "top2": 25} for team in standings
                },
                "teamAnalysis": {"4": {}, "2": {}},
                "qualificationPath": {"4": {}, "2": {}},
            },
        }

        legacy_standings, legacy_fixtures, legacy_analysis = extract_table.legacy_outputs(payload)

        self.assertEqual(legacy_standings["standings"]["Chennai"]["NRR"], 0.123)
        self.assertEqual(legacy_fixtures["fixtures"], [["Chennai", "Mumbai"]])
        self.assertEqual(legacy_analysis["metadata"]["last_data_update"], "2026-05-01T12:00:00Z")
        self.assertEqual(
            legacy_analysis["analysis_data"]["overall_probabilities"]["Mumbai"]["Top 4 Probability"],
            50,
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
        ), mock.patch.object(extract_table, "fetch_cricbuzz_data") as cricbuzz_mock:
            payload = extract_table.build_payload()

        self.assertEqual(payload["metadata"]["source"], "CricketData")
        self.assertEqual(payload["metadata"]["source_url"], extract_table.CRICDATA_SOURCE_URL)
        self.assertEqual(payload["metadata"]["warnings"], [])
        cricdata_mock.assert_called_once()
        cricbuzz_mock.assert_not_called()

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
        ) as cricdata_mock, mock.patch.object(
            extract_table,
            "fetch_cricbuzz_data",
        ) as cricbuzz_mock:
            with self.assertRaisesRegex(extract_table.SourceValidationError, "Inconsistent league result totals"):
                extract_table.build_payload()

        cricdata_mock.assert_called_once()
        cricbuzz_mock.assert_not_called()

    def test_build_payload_rejects_partial_cricketdata_fixtures(self) -> None:
        standings = valid_standings()
        partial_fixtures = [valid_fixture()]

        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(standings, partial_fixtures, []),
        ) as cricdata_mock:
            with self.assertRaisesRegex(extract_table.SourceValidationError, "Fixture feed appears partial"):
                extract_table.build_payload()

        cricdata_mock.assert_called_once()

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
