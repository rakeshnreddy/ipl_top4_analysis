from __future__ import annotations

from datetime import datetime, timedelta, timezone
import itertools
import json
from pathlib import Path
import tempfile
import unittest

import football
import leagues
import team_sports
from team_sports import Game


TEAMS = ["Albion", "Borough", "City", "Rovers"]
KICKOFF = datetime(2026, 8, 15, 14, tzinfo=timezone.utc)


def feed_rows(scores: dict[tuple[str, str], tuple[int, int]], teams: list[str] = TEAMS, start: datetime = KICKOFF) -> list[dict[str, object]]:
    """A double round robin in FixtureDownload's format; pairs missing from ``scores`` are unplayed."""
    rows = []
    for number, (home, away) in enumerate(itertools.permutations(teams, 2), start=1):
        home_score, away_score = scores.get((home, away), (None, None))
        rows.append(
            {
                "MatchNumber": number,
                "RoundNumber": (number + 1) // 2,
                "DateUtc": (start + timedelta(days=7 * number)).strftime("%Y-%m-%d %H:%M:%SZ"),
                "Location": f"{home} Ground",
                "HomeTeam": home,
                "AwayTeam": away,
                "HomeTeamScore": home_score,
                "AwayTeamScore": away_score,
            }
        )
    return rows


def config() -> dict[str, object]:
    return {
        "id": "test-league",
        "sport": "football",
        "name": "Test League",
        "shortName": "TL",
        "season": {"startMonth": 8, "endMonth": 6, "label": "{year}-{yy}", "feed": "test-{year}"},
        "points": {"win": 3, "draw": 1},
        "tiers": [
            {"key": "title", "label": "Title", "kind": "top", "size": 1},
            {"key": "top2", "label": "Top 2", "kind": "top", "size": 2},
            {"key": "relegation", "label": "Relegation", "kind": "bottom", "size": 1},
        ],
        "teams": {"Albion": {"shortName": "ALB", "color": "#123456", "textColor": "#FFFFFF"}},
    }


class SeasonTests(unittest.TestCase):
    def test_autumn_to_spring_seasons_roll_over_in_the_start_month(self) -> None:
        rule = leagues.read_config("epl")

        october = team_sports.resolve_season(rule, datetime(2026, 10, 3, tzinfo=timezone.utc))
        may = team_sports.resolve_season(rule, datetime(2027, 5, 20, tzinfo=timezone.utc))
        previous = team_sports.resolve_season(rule, datetime(2026, 10, 3, tzinfo=timezone.utc), offset=-1)

        self.assertEqual((october.payload_id, october.feed), ("epl-2026-27", "epl-2026"))
        self.assertEqual(may.payload_id, "epl-2026-27")
        self.assertEqual((previous.label, previous.feed), ("2025-26", "epl-2025"))
        self.assertFalse(october.contains(datetime(2027, 7, 15, tzinfo=timezone.utc)))
        self.assertTrue(october.contains(datetime(2027, 6, 30, 23, tzinfo=timezone.utc)))

    def test_malformed_tiers_are_rejected(self) -> None:
        broken = config()
        broken["tiers"] = [{"key": "title", "label": "Title", "kind": "middle", "size": 1}]

        with self.assertRaisesRegex(ValueError, "tier"):
            team_sports.validate_config(broken)


class TableTests(unittest.TestCase):
    def test_standings_rank_by_points_then_goal_difference_then_goals(self) -> None:
        games = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 2, 0),
            Game("2", 1, KICKOFF, "City", "Rovers", None, 3, 1),
            Game("3", 2, KICKOFF, "Albion", "City", None, 1, 1),
            Game("4", 2, KICKOFF, "Borough", "Rovers", None, 0, 0),
        ]

        table = football.standings(games, TEAMS)

        # City and Albion are level on points and goal difference, as are Rovers and Borough.
        self.assertEqual(football.ranked(table), ["City", "Albion", "Rovers", "Borough"])
        self.assertEqual(table["City"], {"played": 2, "wins": 1, "draws": 1, "losses": 0, "goalsFor": 4, "goalsAgainst": 2, "points": 4, "goalDifference": 2})

    def test_head_to_head_decides_ties_once_the_teams_have_met_both_ways(self) -> None:
        # Albion and Borough finish level on points; Borough has the better goal difference but lost both meetings.
        games = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 1, 0),
            Game("2", 2, KICKOFF, "Borough", "Albion", None, 0, 1),
            Game("3", 3, KICKOFF, "Borough", "City", None, 6, 0),
            Game("4", 4, KICKOFF, "Rovers", "Borough", None, 0, 6),
            Game("5", 5, KICKOFF, "Albion", "City", None, 0, 1),
            Game("6", 6, KICKOFF, "Rovers", "Albion", None, 1, 0),
        ]
        table = football.standings(games, TEAMS)
        self.assertEqual(table["Albion"]["points"], table["Borough"]["points"])

        self.assertEqual(football.ranked(table)[:2], ["Borough", "Albion"])
        self.assertEqual(football.ranked(table, games, "head-to-head-complete")[:2], ["Albion", "Borough"])
        # After one meeting, Spain and Italy still rank by goal difference; Portugal does not wait.
        first_leg = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 1, 0),
            Game("2", 2, KICKOFF, "Borough", "City", None, 3, 0),
            Game("3", 2, KICKOFF, "Rovers", "City", None, 0, 0),
        ]
        partial = football.standings(first_leg, TEAMS)
        self.assertEqual(football.ranked(partial, first_leg, "head-to-head-complete")[:2], ["Borough", "Albion"])
        self.assertEqual(football.ranked(partial, first_leg, "head-to-head")[:2], ["Albion", "Borough"])

    def test_a_league_can_list_its_own_tiebreak_steps(self) -> None:
        # Albion and Borough finish level on points and goal difference; Borough scored more but lost both meetings.
        games = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 1, 0),
            Game("2", 2, KICKOFF, "Borough", "Albion", None, 0, 1),
            Game("3", 3, KICKOFF, "Albion", "City", None, 0, 0),
            Game("4", 4, KICKOFF, "Rovers", "Albion", None, 1, 0),
            Game("5", 5, KICKOFF, "Borough", "City", None, 3, 1),
            Game("6", 6, KICKOFF, "Borough", "Rovers", None, 2, 1),
            Game("7", 7, KICKOFF, "Rovers", "Borough", None, 0, 0),
        ]
        table = football.standings(games, TEAMS)
        self.assertEqual([table[team]["points"] for team in ("Albion", "Borough")], [7, 7])
        self.assertEqual([table[team]["goalDifference"] for team in ("Albion", "Borough")], [1, 1])

        # France: goal difference, then head-to-head once both meetings are played, then goals.
        france = ["goal-difference", "head-to-head-complete", "goals", "wins", "away-wins"]
        self.assertEqual(football.ranked(table, games, france)[:2], ["Albion", "Borough"])
        # England's WSL: goal difference, goals, wins, then head-to-head.
        self.assertEqual(football.ranked(table, games, ["goal-difference", "goals", "wins", "head-to-head"])[:2], ["Borough", "Albion"])
        self.assertEqual(football.ranked(table, games)[:2], ["Borough", "Albion"])

    def test_turkey_compares_head_to_head_goals_of_three_teams_level(self) -> None:
        # Albion, Borough and City draw all six games between them; Borough scored most in them, City least.
        games = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 2, 2),
            Game("2", 2, KICKOFF, "Borough", "Albion", None, 1, 1),
            Game("3", 3, KICKOFF, "Albion", "City", None, 0, 0),
            Game("4", 4, KICKOFF, "City", "Albion", None, 0, 0),
            Game("5", 5, KICKOFF, "Borough", "City", None, 1, 1),
            Game("6", 6, KICKOFF, "City", "Borough", None, 0, 0),
            Game("7", 7, KICKOFF, "City", "Rovers", None, 5, 0),
            Game("8", 8, KICKOFF, "Albion", "Rovers", None, 3, 0),
            Game("9", 9, KICKOFF, "Borough", "Rovers", None, 1, 0),
        ]
        table = football.standings(games, TEAMS)

        turkey = ["head-to-head-goals-complete", "goal-difference", "goals"]
        self.assertEqual(football.ranked(table, games, turkey)[:3], ["Borough", "Albion", "City"])
        # Without head-to-head goals the overall goal difference decides.
        self.assertEqual(football.ranked(table, games, "head-to-head-complete")[:3], ["City", "Albion", "Borough"])
        self.assertIn("then overall goal difference", football.tiebreak_note(turkey))

    def test_away_wins_can_separate_teams(self) -> None:
        # Same points, goal difference, goals and wins; Borough won away, Albion at home.
        games = [
            Game("1", 1, KICKOFF, "Albion", "City", None, 1, 0),
            Game("2", 2, KICKOFF, "Rovers", "Albion", None, 1, 0),
            Game("3", 1, KICKOFF, "City", "Borough", None, 0, 1),
            Game("4", 2, KICKOFF, "Borough", "Rovers", None, 0, 1),
        ]
        table = football.standings(games, TEAMS)

        self.assertEqual(football.ranked(table, games)[1:3], ["Albion", "Borough"])
        self.assertEqual(football.ranked(table, games, ["goal-difference", "goals", "wins", "away-wins"])[1:3], ["Borough", "Albion"])

    def test_every_football_config_names_known_tiebreak_steps(self) -> None:
        for league_id in leagues.available_league_ids():
            config = leagues.read_config(league_id)
            if config.get("sport") == "football" and not config.get("engine"):
                self.assertTrue(football.tiebreak_steps(config.get("tiebreak")), league_id)
        with self.assertRaisesRegex(ValueError, "tiebreak"):
            football.tiebreak_steps(["head-to-tail"])

    def test_deductions_are_found_by_matching_records(self) -> None:
        table = football.standings([Game("1", 1, KICKOFF, "Albion", "Borough", None, 2, 0), Game("2", 1, KICKOFF, "City", "Rovers", None, 1, 1)], TEAMS)
        official = [dict(row) for row in table.values()]
        for row in official:
            if row["wins"] == 1:
                row["points"] -= 4
        # Two teams share the drawn record, so no deduction can be pinned on either of them.
        official[2]["points"] -= 1

        self.assertEqual(football.official_adjustments(table, official), {"Albion": -4})

    def test_form_lists_the_latest_result_first(self) -> None:
        games = [
            Game("1", 1, KICKOFF, "Albion", "Borough", None, 2, 0),
            Game("2", 2, KICKOFF + timedelta(days=7), "Rovers", "Albion", None, 1, 1),
            Game("3", 3, KICKOFF + timedelta(days=14), "Albion", "City", None, 0, 1),
        ]

        self.assertEqual(team_sports.form_strings(games, "Albion"), ["L", "D", "W"])


class ModelTests(unittest.TestCase):
    def test_the_team_that_scores_more_gets_the_higher_attack_rating(self) -> None:
        games = []
        for number, (home, away) in enumerate(itertools.permutations(TEAMS, 2)):
            home_score = 3 if home == "Albion" else 1
            away_score = 3 if away == "Albion" else 1
            games.append(Game(str(number), 1, KICKOFF + timedelta(days=number), home, away, None, home_score, away_score))

        model = football.fit_goal_model(games, TEAMS, set(), KICKOFF + timedelta(days=30))

        self.assertEqual(max(model.attack, key=model.attack.get), "Albion")
        home, draw, away = model.outcome("Albion", "Rovers")
        self.assertAlmostEqual(home + draw + away, 1.0, places=9)
        self.assertGreater(home, away)

    def test_a_finished_season_has_certain_outcomes(self) -> None:
        table = {team: {"points": points, "goalsFor": 10, "goalsAgainst": 10} for team, points in zip(TEAMS, (9, 6, 3, 0))}
        model = football.GoalModel(mu=0.3, home=0.2, attack=dict.fromkeys(TEAMS, 0.0), defence=dict.fromkeys(TEAMS, 0.0))

        result = football.simulate(model, TEAMS, table, [], config()["tiers"], {"win": 3, "draw": 1})

        self.assertEqual(result["probabilities"]["Albion"], {"title": 100.0, "top2": 100.0, "relegation": 0.0})
        self.assertEqual(result["probabilities"]["Rovers"]["relegation"], 100.0)
        self.assertEqual(result["matchesThatMatter"], [])


class PayloadTests(unittest.TestCase):
    def build(self, scores: dict[tuple[str, str], tuple[int, int]]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "test-2026.json").write_text(json.dumps(feed_rows(scores)))
            (cache / "test-2025.json").write_text(
                json.dumps(feed_rows({pair: (1, 1) for pair in itertools.permutations(TEAMS, 2)}, start=KICKOFF - timedelta(days=365)))
            )
            return football.build_payload(config(), datetime(2026, 10, 3, tzinfo=timezone.utc), cache)

    def test_payload_has_a_table_fixtures_and_consistent_probabilities(self) -> None:
        payload = self.build({("Albion", "Borough"): (2, 0), ("City", "Rovers"): (1, 1), ("Albion", "City"): (3, 1)})

        self.assertEqual(payload["league"]["id"], "test-league-2026-27")
        self.assertEqual(payload["metadata"]["season_status"], "in_progress")
        self.assertEqual(payload["standings"][0]["teamKey"], "Albion")
        self.assertEqual(payload["standings"][0]["shortName"], "ALB")
        self.assertEqual(len(payload["fixtures"]), 12 - 3)
        self.assertEqual(len(payload["results"]), 3)
        for fixture in payload["fixtures"]:
            self.assertAlmostEqual(sum(fixture["probabilities"].values()), 1.0, delta=0.002)

        probabilities = payload["analysis"]["probabilities"]
        for tier, slots in (("title", 1), ("top2", 2), ("relegation", 1)):
            self.assertAlmostEqual(sum(values[tier] for values in probabilities.values()), slots * 100, delta=0.05)
        for positions in payload["analysis"]["positions"].values():
            self.assertAlmostEqual(sum(positions), 100, delta=0.05)

    def test_a_complete_season_is_marked_complete(self) -> None:
        scores = {pair: (1, 0) for pair in itertools.permutations(TEAMS, 2)}

        payload = self.build(scores)

        self.assertEqual(payload["metadata"]["season_status"], "complete")
        self.assertEqual(payload["fixtures"], [])

    def test_ratings_do_not_drift_between_days_without_results(self) -> None:
        scores = {("Albion", "Borough"): (2, 0), ("Albion", "City"): (1, 1)}
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "test-2026.json").write_text(json.dumps(feed_rows(scores)))
            (cache / "test-2025.json").write_text(json.dumps([]))
            first = football.build_payload(config(), datetime(2026, 10, 3, tzinfo=timezone.utc), cache)
            second = football.build_payload(config(), datetime(2026, 10, 4, tzinfo=timezone.utc), cache)

        self.assertEqual(first["analysis"]["probabilities"], second["analysis"]["probabilities"])
        self.assertTrue(first["metadata"]["warnings"])

    def test_a_league_whose_feed_starts_this_season_does_not_look_for_the_last_one(self) -> None:
        first = config()
        first["season"] = dict(first["season"], firstYear=2026)
        team_sports.validate_config(first)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            # Albion and Borough beat City and Rovers 1-0 at home; the six matches before 3 October are played.
            played = dict.fromkeys(list(itertools.permutations(TEAMS, 2))[:6], (1, 0))
            (cache / "test-2026.json").write_text(json.dumps(feed_rows(played)))
            # No test-2025 feed: fetching it would fail (or go online) and warn.
            payload = football.build_payload(first, datetime(2026, 10, 3, tzinfo=timezone.utc), cache)

        self.assertEqual(payload["metadata"]["warnings"], [])
        self.assertEqual(payload["metadata"]["data_freshness_status"], "fresh")
        notes = payload["analysis"]["modelNotes"]
        self.assertIn("fitted on this season with", notes[0])
        self.assertIn("FixtureDownload has no Test League season before 2026-27", notes[1])
        # Nobody is treated as promoted: both sides of an unplayed match start level.
        self.assertEqual(payload["analysis"]["ratings"]["City"], payload["analysis"]["ratings"]["Rovers"])

        first["season"]["firstYear"] = "2026"
        with self.assertRaisesRegex(ValueError, "firstYear"):
            team_sports.validate_config(first)

    def test_movement_compares_with_the_previous_payload(self) -> None:
        previous = {
            "metadata": {"generated_at": "2026-10-02T19:30:00Z"},
            "league": {"id": "x"},
            "standings": [{"played": 1}],
            "analysis": {"probabilities": {"Albion": {"title": 40.0}}},
        }
        current = {"league": {"id": "x"}, "standings": [{"played": 2}], "analysis": {"probabilities": {"Albion": {"title": 52.5}}}}

        movement = team_sports.probability_movement(previous, current)

        self.assertEqual(movement, {"since": "2026-10-02T19:30:00Z", "changes": {"Albion": {"title": 12.5}}})
        self.assertEqual(team_sports.probability_movement(dict(previous, movement=movement), dict(current, standings=[{"played": 1}])), movement)


if __name__ == "__main__":
    unittest.main()
