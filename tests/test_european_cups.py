from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

import european_cups
import extract_table
import leagues
import team_sports
import uefa
from team_sports import Game


# The 2025-26 Champions League (league phase and knockouts), Europa League and Conference
# League (league phases), with UEFA's official final league-phase tables. Source: UEFA's
# match and standings services behind uefa.com, e.g.
# https://standings.uefa.com/v1/standings?competitionId=1&seasonYear=2026 and
# https://www.uefa.com/uefachampionsleague/standings/ (season 2025/26).
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "uefa-2025-26.json").read_text(encoding="utf-8"))
PSG, ARSENAL, BAYERN, SPORTING = "52747", "52280", "50037", "50149"
UCL_CONFIG = leagues.read_config("champions-league")


def load(name: str) -> tuple[list[uefa.Match], dict[str, uefa.Team], list[dict[str, int]]]:
    data = FIXTURE[name]
    teams = {key: uefa.Team(id=key, name=item[0], code=item[1], country=item[2]) for key, item in data["teams"].items()}
    matches = [
        uefa.Match(
            id=row[0], competition=data["competition"], season=data["season"], round=row[1], qualifying=False, leg=row[2],
            date=datetime.fromisoformat(row[3].replace("Z", "+00:00")), home=row[4], away=row[5], status="FINISHED",
            home_score=row[6], away_score=row[7], home_total=row[8], away_total=row[9], home_penalties=row[10],
            away_penalties=row[11], winner=row[12], neutral=row[1] == "FINAL",
        )
        for row in data["matches"]
    ]
    standings = [
        dict(zip(("rank", "team", "played", "wins", "draws", "losses", "goalsFor", "goalsAgainst", "points"), row))
        for row in data["standings"]
    ]
    return matches, teams, standings


def unplayed(match: uefa.Match) -> uefa.Match:
    return dataclasses.replace(
        match, status="UPCOMING", home_score=None, away_score=None, home_total=None, away_total=None,
        home_penalties=None, away_penalties=None, winner=None,
    )


def league_teams(matches: list[uefa.Match]) -> list[str]:
    league = [match for match in matches if match.round == uefa.LEAGUE_PHASE]
    return sorted({match.home for match in league} | {match.away for match in league})


class UefaFeedTests(unittest.TestCase):
    def raw(self, **overrides: object) -> dict[str, object]:
        team = lambda key, name, code: {"id": key, "internationalName": name, "teamCode": code, "countryCode": "XXX", "isPlaceHolder": False}  # noqa: E731
        raw = {
            "id": 7,
            "type": "SECOND_LEG",
            "status": "FINISHED",
            "kickOffTime": {"dateTime": "2026-03-17T20:00:00Z"},
            "round": {"phase": "TOURNAMENT", "metaData": {"type": "ROUND_OF_16"}},
            "homeTeam": team("1", "Home", "HOM"),
            "awayTeam": team("2", "Away", "AWY"),
            "score": {"regular": {"home": 1, "away": 0}, "total": {"home": 1, "away": 1}, "penalty": {"home": 4, "away": 5}},
            "winner": {"aggregate": {"team": {"id": "2"}}, "match": {"team": {"id": "1"}}},
        }
        raw.update(overrides)
        return raw

    def test_a_second_leg_records_the_tie_winner_and_every_score(self) -> None:
        match, home, away = uefa.parse_match(self.raw(), 1, 2026)
        self.assertEqual((home.code, away.code), ("HOM", "AWY"))
        self.assertEqual((match.round, match.leg, match.qualifying), ("ROUND_OF_16", 2, False))
        self.assertEqual((match.home_score, match.away_score), (1, 0))  # 90 minutes, for the goals model
        self.assertEqual((match.home_total, match.away_total, match.home_penalties, match.away_penalties), (1, 1, 4, 5))
        self.assertEqual(match.winner, "2")  # the aggregate winner, not the match winner
        self.assertTrue(match.played)

    def test_placeholder_teams_are_skipped_until_the_draw(self) -> None:
        raw = self.raw(awayTeam={"id": "9", "isPlaceHolder": True, "internationalName": "W QF1"})
        self.assertIsNone(uefa.parse_match(raw, 1, 2026))

    def test_unplayed_matches_have_no_score(self) -> None:
        match, _, _ = uefa.parse_match(self.raw(status="UPCOMING", score=None, winner=None), 1, 2026)
        self.assertFalse(match.played)
        self.assertIsNone(match.winner)


class LeaguePhaseTests(unittest.TestCase):
    def test_computed_order_matches_uefas_official_tables(self) -> None:
        for name in ("UCL", "UEL", "UECL"):
            with self.subTest(competition=name):
                matches, _, standings = load(name)
                league = [match for match in matches if match.round == uefa.LEAGUE_PHASE]
                table = european_cups.league_table(league, league_teams(matches))
                official = european_cups.official_order(table, standings)
                self.assertIsNotNone(official, "every record should match UEFA's table")
                self.assertEqual(european_cups.ranked(table, league), official)

    def test_official_order_is_ignored_when_a_record_differs(self) -> None:
        matches, _, standings = load("UCL")
        league = [match for match in matches if match.round == uefa.LEAGUE_PHASE]
        table = european_cups.league_table(league, league_teams(matches))
        changed = [dict(row, points=row["points"] + 3) if row["rank"] == 10 else row for row in standings]
        self.assertIsNone(european_cups.official_order(table, changed))

    def test_away_goals_break_a_tie_before_wins(self) -> None:
        def game(home: str, away: str, home_score: int, away_score: int, day: int) -> uefa.Match:
            return uefa.Match(
                id=f"{home}{away}", competition=1, season=2026, round=uefa.LEAGUE_PHASE, qualifying=False, leg=None,
                date=datetime(2025, 9, day, tzinfo=timezone.utc), home=home, away=away, status="FINISHED",
                home_score=home_score, away_score=away_score,
            )

        # A and B: 3 points, goal difference 0, three goals each; B scored two of them away.
        matches = [game("A", "C", 2, 0, 1), game("D", "A", 3, 1, 2), game("B", "C", 1, 3, 3), game("D", "B", 0, 2, 4)]
        table = european_cups.league_table(matches, ["A", "B", "C", "D"])
        order = european_cups.ranked(table, matches)
        self.assertLess(order.index("B"), order.index("A"))


class KnockoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matches, self.teams, self.standings = load("UCL")
        self.ties = european_cups.knockout_ties(self.matches)
        self.order = [row["team"] for row in sorted(self.standings, key=lambda row: row["rank"])]

    def test_ties_are_grouped_with_their_winners(self) -> None:
        self.assertEqual({name: len(items) for name, items in self.ties.items()}, european_cups.EXPECTED_TIES)
        final = self.ties["FINAL"][0]
        self.assertEqual(final.teams, frozenset((PSG, ARSENAL)))
        self.assertEqual(final.winner, PSG)  # 1-1, PSG won the shoot-out 4-3
        self.assertTrue(all(tie.winner for items in self.ties.values() for tie in items))

    def test_real_pairings_follow_the_seeding_rules_the_simulation_uses(self) -> None:
        position = {team: rank for rank, team in enumerate(self.order)}
        for tie in self.ties["FINAL_TOURNAMENT_PLAY_OFF"]:
            seeded, unseeded = sorted(position[team] for team in tie.teams)
            group = (seeded - 8) // 2
            self.assertIn(unseeded, (22 - 2 * group, 23 - 2 * group))
        playoff_group = {
            tie.winner: (min(position[team] for team in tie.teams) - 8) // 2 for tie in self.ties["FINAL_TOURNAMENT_PLAY_OFF"]
        }
        for tie in self.ties["ROUND_OF_16"]:
            top = min(position[team] for team in tie.teams)
            other = next(team for team in tie.teams if position[team] != top)
            self.assertLess(top, 8)
            self.assertEqual(playoff_group[other], 3 - top // 2)

    def test_known_quarter_and_semi_finals_pin_down_the_bracket_halves(self) -> None:
        position = {team: rank for rank, team in enumerate(self.order)}
        label = {tie.winner: min(position[team] for team in tie.teams) for tie in self.ties["ROUND_OF_16"]}
        quarters = [frozenset(label[team] for team in tie.teams) for tie in self.ties["QUARTER_FINALS"]]
        pair_of = {team: pair for tie, pair in zip(self.ties["QUARTER_FINALS"], quarters) for team in tie.teams}
        semis = [pair_of[a] | pair_of[b] for a, b in (tuple(tie.teams) for tie in self.ties["SEMIFINAL"])]
        self.assertEqual(len(european_cups.half_layouts([], [])), 16)
        # The quarter-finals fix two relative flips, the semi-finals a third; swapping the halves changes nothing.
        self.assertEqual(len(european_cups.half_layouts(quarters, [])), 4)
        self.assertEqual(len(european_cups.half_layouts(quarters, semis)), 2)

    def test_a_big_first_leg_lead_almost_always_goes_through(self) -> None:
        model = european_cups.CupModel(mu=0.25, home=0.25, attack={}, defence={})
        rng = np.random.default_rng(1)
        count = 4000
        zeros = np.zeros((count, 2))
        winners = european_cups.play_ties(
            rng, model, zeros, zeros, np.arange(count), np.zeros(count, dtype=int), np.ones(count, dtype=int),
            first_leg=(np.full(count, 5.0), np.zeros(count)),
        )
        self.assertGreater((winners == 0).mean(), 0.99)
        level = european_cups.play_ties(rng, model, zeros, zeros, np.arange(count), np.zeros(count, dtype=int), np.ones(count, dtype=int))
        self.assertAlmostEqual(float((level == 0).mean()), 0.5, delta=0.04)

    def test_a_finished_season_is_certain(self) -> None:
        teams = league_teams(self.matches)
        league = [match for match in self.matches if match.round == uefa.LEAGUE_PHASE]
        table = european_cups.league_table(league, teams)
        model = european_cups.CupModel(mu=0.3, home=0.2, attack={}, defence={})
        result = european_cups.simulate(model, teams, table, league, self.ties, self.order, UCL_CONFIG["tiers"], simulations=500)
        probabilities = result["probabilities"]
        self.assertEqual(probabilities[PSG]["title"], 100.0)
        quarter_finalists = set().union(*(tie.teams for tie in self.ties["QUARTER_FINALS"]))
        self.assertEqual({team for team, values in probabilities.items() if values["quarterFinals"] == 100.0}, quarter_finalists)
        self.assertEqual(sum(values["top8"] for values in probabilities.values()), 800.0)

    def test_mid_season_odds_add_up(self) -> None:
        teams = league_teams(self.matches)
        cutoff = datetime(2025, 11, 1, tzinfo=timezone.utc)
        league = [match if match.date < cutoff else unplayed(match) for match in self.matches if match.round == uefa.LEAGUE_PHASE]
        table = european_cups.league_table(league, teams)
        model = european_cups.fit_model(european_cups.uefa_results(league), cutoff)
        result = european_cups.simulate(model, teams, table, league, {}, None, UCL_CONFIG["tiers"], simulations=2000)
        totals = {key: sum(values[key] for values in result["probabilities"].values()) for key in ("top8", "top24", "quarterFinals", "title")}
        for key, expected in (("top8", 800), ("top24", 2400), ("quarterFinals", 800), ("title", 100)):
            self.assertAlmostEqual(totals[key], expected, delta=0.5)
        self.assertTrue(result["matchesThatMatter"])


class ModelTests(unittest.TestCase):
    def test_the_team_that_scores_more_rates_higher(self) -> None:
        day = datetime(2026, 1, 1, tzinfo=timezone.utc)
        results = [european_cups.Result("A", "B", 3, 0, day), european_cups.Result("B", "A", 0, 2, day), european_cups.Result("A", "C", 1, 1, day)]
        model = european_cups.fit_model(results, day)
        self.assertGreater(model.attack["A"], model.attack["B"])
        home, draw, away = model.outcome("A", "B")
        self.assertAlmostEqual(home + draw + away, 1.0)
        self.assertGreater(home, away)
        # Unknown teams are average, and a neutral venue removes home advantage.
        self.assertEqual(model.rates("X", "Y", neutral=True)[0], model.rates("Y", "X", neutral=True)[0])

    def test_domestic_names_link_to_uefa_clubs_without_guessing(self) -> None:
        teams = {
            "1": uefa.Team("1", "Paris", "PSG", "FRA"),
            "2": uefa.Team("2", "Celta", "CEL", "ESP"),
            "3": uefa.Team("3", "B. Dortmund", "BVB", "GER"),
            "4": uefa.Team("4", "Inter", "INT", "ITA"),
            "5": uefa.Team("5", "Internazionale Milano", "IN2", "ITA"),
        }
        day = datetime(2026, 1, 1, tzinfo=timezone.utc)
        games = {
            "FRA": [Game("1", 1, day, "Paris Saint-Germain", "Paris FC", None, 1, 0)],
            "ESP": [Game("2", 1, day, "RC Celta", "Getafe CF", None, 1, 0), Game("3", 2, day, "Celta", "Getafe CF", None, 1, 0)],
            "GER": [Game("4", 1, day, "Borussia Dortmund", "FC Augsburg", None, 1, 0)],
            "ITA": [Game("5", 1, day, "Internazionale", "Milan", None, 1, 0)],
        }
        names = european_cups.domestic_names(teams, games)
        self.assertEqual(names[("FRA", "Paris Saint-Germain")], "1")
        self.assertNotIn(("FRA", "Paris FC"), names)
        self.assertEqual((names[("ESP", "RC Celta")], names[("ESP", "Celta")]), ("2", "2"))
        self.assertEqual(names[("GER", "Borussia Dortmund")], "3")
        # Two UEFA clubs claim "Internazionale": no link rather than a wrong one.
        self.assertNotIn(("ITA", "Internazionale"), names)


class PayloadTests(unittest.TestCase):
    def build(self, now: datetime, hide_after: datetime | None = None) -> dict[str, object]:
        matches, teams, standings = load("UCL")
        if hide_after:
            matches = [match if match.date < hide_after else unplayed(match) for match in matches]
            standings_source = mock.Mock(side_effect=team_sports.FeedError("no table"))
        else:
            standings_source = mock.Mock(return_value=standings)
        with (
            mock.patch.object(uefa, "fetch_matches", side_effect=lambda competition, season, *_, **__: (matches, teams) if competition == 1 else ([], {})),
            mock.patch.object(uefa, "fetch_standings", standings_source),
            mock.patch.object(european_cups, "domestic_results", return_value=[]),
            mock.patch.object(european_cups, "SIMULATIONS", 500),
        ):
            return european_cups.build_payload(UCL_CONFIG, now, Path("/nonexistent"))

    def test_a_finished_season_names_the_champion_and_shows_the_bracket(self) -> None:
        payload = self.build(datetime(2026, 6, 1, tzinfo=timezone.utc))
        self.assertEqual(payload["league"]["id"], "champions-league-2025-26")
        self.assertEqual(payload["metadata"]["season_status"], "complete")
        self.assertEqual(payload["playoffs"]["champion"], PSG)
        self.assertEqual([item["key"] for item in payload["bracket"]["rounds"]], list(uefa.KNOCKOUT_ROUNDS))
        final = payload["bracket"]["rounds"][-1]["series"][0]
        self.assertEqual((final["aggregate"], final["note"], final["winner"]), ({"top": 1, "bottom": 1}, "3-4 on penalties", PSG))  # Arsenal (1st) listed first
        self.assertEqual([row["teamKey"] for row in payload["standings"][:2]], [ARSENAL, BAYERN])
        self.assertTrue(all(tier.get("settled") for tier in payload["league"]["tiers"]))
        self.assertEqual(payload["fixtures"], [])
        sporting_r16 = next(result for result in payload["results"] if result["note"] and "Round of 16, 2nd leg" in result["note"] and SPORTING in (result["home"], result["away"]))
        self.assertIn("after extra time", sporting_r16["note"])
        entry = extract_table.index_entry(payload)
        self.assertEqual(entry["champion"], "PSG")
        self.assertEqual(entry["facts"], [{"label": "Champions", "value": "PSG"}])

    def test_mid_league_phase_payload_has_odds_fixtures_and_facts(self) -> None:
        cutoff = datetime(2025, 11, 1, tzinfo=timezone.utc)
        payload = self.build(datetime(2025, 10, 31, tzinfo=timezone.utc), hide_after=cutoff)
        self.assertEqual(payload["metadata"]["season_status"], "in_progress")
        self.assertNotIn("bracket", payload)
        self.assertEqual(len(payload["standings"]), 36)
        self.assertTrue(all(fixture["date"] >= "2025-11-01" for fixture in payload["fixtures"]))
        self.assertEqual(set(payload["fixtures"][0]["probabilities"]), {"home", "draw", "away"})
        labels = [fact["label"] for fact in extract_table.index_entry(payload)["facts"]]
        self.assertEqual(labels, ["Title favourite", "Top 8 bubble"])


class ConfigTests(unittest.TestCase):
    def test_cup_configs_are_valid_and_build_with_the_cup_engine(self) -> None:
        team_sports.validate_config(UCL_CONFIG)
        self.assertEqual(UCL_CONFIG["engine"], "european_cups")
        season = team_sports.resolve_season(UCL_CONFIG, datetime(2026, 10, 3, tzinfo=timezone.utc))
        self.assertEqual((season.payload_id, season.feed), ("champions-league-2026-27", "2027"))
        self.assertFalse(team_sports.resolve_season(UCL_CONFIG, datetime(2026, 8, 1, tzinfo=timezone.utc)).contains(datetime(2026, 7, 15, tzinfo=timezone.utc)))
        with mock.patch.object(european_cups, "build_payload", return_value={"ok": True}) as build:
            self.assertEqual(extract_table.build_league("champions-league", "auto"), {"ok": True})
        build.assert_called_once()


if __name__ == "__main__":
    unittest.main()
