from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest import mock

import extract_table


def valid_standings() -> list[dict[str, object]]:
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
            "nrr": float(index) / 10,
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


if __name__ == "__main__":
    unittest.main()
