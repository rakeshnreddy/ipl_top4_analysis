from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest import mock

import extract_table


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

    def test_build_payload_prefers_cricketdata_before_cricbuzz(self) -> None:
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
                "nrr": float(index) / 10,
                "rank": index,
                "remainingMatches": 6,
            }
            for index, meta in enumerate(extract_table.TEAM_META.values(), start=1)
        ]
        fixtures = [
            {
                "id": "cricdata-test",
                "matchNo": 44,
                "teamA": "Chennai",
                "teamB": "Mumbai",
                "dateTimeGMT": "2026-05-02T14:00:00Z",
                "dateTimeLocal": None,
                "venue": "MA Chidambaram Stadium, Chennai",
                "status": "scheduled",
                "sourceUrl": extract_table.CRICDATA_SERIES_INFO_URL,
            }
        ]

        with mock.patch.object(
            extract_table,
            "fetch_cricdata_data",
            return_value=(standings, fixtures, ["Loaded CricketData series id test-series"]),
        ) as cricdata_mock, mock.patch.object(extract_table, "fetch_cricbuzz_data") as cricbuzz_mock:
            payload = extract_table.build_payload()

        self.assertEqual(payload["metadata"]["source"], "CricketData")
        self.assertEqual(payload["metadata"]["source_url"], extract_table.CRICDATA_SOURCE_URL)
        cricdata_mock.assert_called_once()
        cricbuzz_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
