from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import tempfile
import unittest

import numpy as np

import leagues
import team_sports
import us_sports
from team_sports import Game


START = datetime(2026, 10, 1, 23, tzinfo=timezone.utc)


def config(league_id: str) -> dict[str, object]:
    return leagues.read_config(league_id)


def schedule(cfg: dict[str, object], games_per_team: int, played: int, seed: int = 3) -> list[Game]:
    """A random schedule in which every team plays `games_per_team` games; the first `played` have scores."""
    rng = random.Random(seed)
    teams = sorted(cfg["teams"])
    games = []
    for round_number in range(games_per_team):
        order = teams[:]
        rng.shuffle(order)
        # With an odd number of teams, one sits out each round.
        for pair in range(0, len(order) - 1, 2):
            home, away = order[pair], order[pair + 1]
            number = len(games) + 1
            date = START + timedelta(days=round_number, minutes=pair)
            if number <= played:
                home_score, away_score = rng.randint(0, 30), rng.randint(0, 30)
                if home_score == away_score:
                    home_score += 1
            else:
                home_score = away_score = None
            games.append(Game(str(number), round_number + 1, date, home, away, None, home_score, away_score))
    return games


def seeds_for(cfg: dict[str, object], wins: dict[str, int]) -> dict[str, np.ndarray]:
    structure = us_sports.league_structure(cfg)
    teams = structure.teams
    zeros = np.zeros((1, len(teams)))
    won = np.array([[wins.get(team, 0) for team in teams]], dtype=float)
    lost = 17 - won
    division_key, conference_key = us_sports.rank_keys(
        cfg["sport"], won, lost, zeros, zeros, won, zeros, zeros, -np.arange(len(teams))[None, :] * 1e-6
    )
    return us_sports.seed_conferences(cfg, structure, division_key, conference_key)


class ScheduleTests(unittest.TestCase):
    def test_playoff_rounds_and_placeholder_teams_are_dropped(self) -> None:
        nfl = config("nfl")
        games = [
            Game("1", 18, START, "Buffalo Bills", "Miami Dolphins", None, 20, 17),
            Game("2", 19, START, "Buffalo Bills", "Kansas City Chiefs", None, 24, 21),
            Game("3", 5, START, "To be announced", "Miami Dolphins", None, None, None),
        ]

        self.assertEqual([game.id for game in us_sports.regular_season(nfl, games)], ["1"])

    def test_the_cup_final_between_two_teams_over_the_schedule_is_dropped(self) -> None:
        cfg = {"teams": {"A": {}, "B": {}, "C": {}}, "gamesPerTeam": 2}
        games = [
            Game("1", 1, START, "A", "B", None, 100, 90),
            Game("2", 1, START, "B", "C", None, 100, 90),
            Game("3", 1, START, "C", "A", None, 100, 90),
            Game("4", 2, START + timedelta(days=50), "A", "B", None, 110, 100),
        ]

        self.assertEqual([game.id for game in us_sports.regular_season(cfg, games)], ["1", "2", "3"])

    def test_renamed_franchises_are_mapped(self) -> None:
        games = [Game("1", 1, START, "Arizona Coyotes", "Boston Bruins", None, 3, 2)]

        kept = us_sports.regular_season(config("nhl"), games)

        self.assertEqual(kept[0].home, "Utah Mammoth")


class RecordTests(unittest.TestCase):
    def test_overtime_losses_and_regulation_wins_in_the_nhl(self) -> None:
        nhl = config("nhl")
        structure = us_sports.league_structure(nhl)
        games = [
            Game("1", None, START, "Boston Bruins", "Buffalo Sabres", None, 3, 2, note="OT"),
            Game("2", None, START, "Buffalo Sabres", "Boston Bruins", None, 4, 1),
        ]

        records = us_sports.team_records(games, structure, "ice-hockey")

        self.assertEqual(
            {key: records["Buffalo Sabres"][key] for key in ("wins", "losses", "otLosses", "regulationWins")},
            {"wins": 1, "losses": 0, "otLosses": 1, "regulationWins": 1},
        )
        self.assertEqual(records["Boston Bruins"]["regulationWins"], 0)

    def test_ties_count_half_a_win(self) -> None:
        nfl = config("nfl")
        structure = us_sports.league_structure(nfl)
        games = [Game("1", 1, START, "Dallas Cowboys", "Green Bay Packers", None, 40, 40)]

        records = us_sports.team_records(games, structure, "american-football")

        self.assertEqual(records["Dallas Cowboys"]["ties"], 1)
        self.assertEqual(us_sports.pct(0, 0, 1), 0.5)
        self.assertEqual(us_sports.streak(["W", "L", "L"]), "L2")
        self.assertEqual(us_sports.last_ten(["W"] * 7 + ["L"] * 4), "6-4")


class SeedingTests(unittest.TestCase):
    def test_nfl_division_winners_take_the_top_four_seeds(self) -> None:
        nfl = config("nfl")
        # The AFC South winner has the conference's worst winning record but still hosts a game.
        wins = {team: 9 for team in nfl["teams"]}
        wins.update({"Houston Texans": 8, "Indianapolis Colts": 7, "Jacksonville Jaguars": 6, "Tennessee Titans": 5, "Buffalo Bills": 14})

        seeding = seeds_for(nfl, wins)
        teams = sorted(nfl["teams"])
        seed = {team: int(seeding["seed"][0, i]) for i, team in enumerate(teams)}

        self.assertEqual(seed["Buffalo Bills"], 1)
        self.assertEqual(seed["Houston Texans"], 4)
        self.assertTrue(seeding["playoff"][0, teams.index("Houston Texans")])
        self.assertEqual(int(seeding["playoff"][0].sum()), 14)
        self.assertEqual(int(seeding["division_winner"][0].sum()), 8)

    def test_nhl_takes_three_per_division_and_two_wild_cards(self) -> None:
        nhl = config("nhl")
        seeding = seeds_for(nhl, {team: i for i, team in enumerate(sorted(nhl["teams"]))})
        teams = sorted(nhl["teams"])
        structure = us_sports.league_structure(nhl)

        self.assertEqual(int(seeding["playoff"][0].sum()), 16)
        for d in range(len(structure.divisions)):
            members = np.flatnonzero(structure.division == d)
            self.assertGreaterEqual(int(seeding["playoff"][0, members].sum()), 3, structure.divisions[d])
        self.assertEqual(sorted(teams[i] for i in np.flatnonzero(seeding["division_winner"][0])), sorted(
            max((team for team in teams if nhl["teams"][team]["division"] == division), key=teams.index)
            for division in structure.divisions
        ))


class SimulationTests(unittest.TestCase):
    def check_sums(self, league_id: str, games_per_team: int, played: int) -> dict[str, object]:
        cfg = config(league_id)
        structure = us_sports.league_structure(cfg)
        games = schedule(cfg, games_per_team, played)
        model = us_sports.SPORT_MODELS[cfg["sport"]]
        ratings = us_sports.fit_ratings(games, [], structure.teams, model, START + timedelta(days=games_per_team))
        result = us_sports.simulate(cfg, cfg["sport"], structure, games, ratings, 0.5, simulations=2000, seed=5)
        probabilities = result["probabilities"]
        total = lambda key: sum(values[key] for values in probabilities.values())  # noqa: E731
        self.assertAlmostEqual(total("title"), 100, delta=0.01)
        for team, positions in result["positions"].items():
            self.assertAlmostEqual(sum(positions), 100, delta=0.05, msg=team)
        return {"total": total, "result": result}

    def test_every_league_fills_its_playoff_field_and_crowns_one_champion(self) -> None:
        for league_id, per_team, playoff_teams in (("nfl", 6, 14), ("nhl", 8, 16), ("mlb", 8, 12), ("nba", 8, 16), ("wnba", 8, 8), ("nbl", 8, 6), ("wnbl", 8, 5)):
            with self.subTest(league_id):
                cfg = config(league_id)
                if "gamesPerTeam" in cfg:
                    cfg = dict(cfg, gamesPerTeam=per_team)
                checked = self.check_sums(league_id, per_team, played=len(cfg["teams"]) * per_team // 4)
                key = next(tier["key"] for tier in cfg["tiers"] if tier["kind"] == "playoffs")
                self.assertAlmostEqual(checked["total"](key), playoff_teams * 100, delta=0.01)

    def test_a_finished_season_has_settled_places(self) -> None:
        cfg = config("mlb")
        games = schedule(cfg, 6, played=10_000)
        structure = us_sports.league_structure(cfg)
        ratings = us_sports.fit_ratings(games, [], structure.teams, us_sports.SPORT_MODELS["baseball"], START + timedelta(days=6))

        result = us_sports.simulate(cfg, "baseball", structure, games, ratings, 0.0, simulations=500, seed=1)

        self.assertTrue(all(values["playoffs"] in (0.0, 100.0) for values in result["probabilities"].values()))
        self.assertEqual(result["matchesThatMatter"], [])


class PayloadTests(unittest.TestCase):
    def test_a_schedule_that_ended_with_unplayed_games_is_complete(self) -> None:
        cfg = config("mlb")
        games = schedule(cfg, 4, played=59)
        rows = [
            {
                "MatchNumber": int(game.id),
                "RoundNumber": game.round,
                "DateUtc": (game.date.replace(year=2026, month=9, day=1) + timedelta(days=game.round)).strftime("%Y-%m-%d %H:%M:%SZ"),
                "Location": None,
                "HomeTeam": game.home,
                "AwayTeam": game.away,
                "HomeTeamScore": game.home_score,
                "AwayTeamScore": game.away_score,
            }
            for game in games
        ]
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "mlb-2026.json").write_text(json.dumps(rows))
            (cache / "mlb-2025.json").write_text(json.dumps(rows))
            payload = us_sports.build_payload(cfg, datetime(2026, 10, 3, tzinfo=timezone.utc), cache)

        self.assertEqual(payload["metadata"]["season_status"], "complete")
        self.assertEqual(payload["fixtures"], [])
        self.assertTrue(any("never played" in note for note in payload["analysis"]["modelNotes"]))
        self.assertEqual(sum(row["played"] for row in payload["standings"]), 2 * 59)
        conference_groups = [group for group in payload["league"]["groups"] if group.get("cutoffs")]
        self.assertEqual([len(group["teams"]) for group in conference_groups], [15, 15])


class PostseasonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = config("mlb")
        self.structure = us_sports.league_structure(self.cfg)
        teams = self.structure.teams
        # Records that make the 2026 field: seeds follow the order of these lists in each league.
        wins = {team: 70 for team in teams}
        for order in (
            ["Tampa Bay Rays", "Cleveland Guardians", "Houston Astros", "New York Yankees", "Boston Red Sox", "Chicago White Sox"],
            ["Milwaukee Brewers", "Los Angeles Dodgers", "Atlanta Braves", "San Diego Padres", "Chicago Cubs", "Philadelphia Phillies"],
        ):
            for place, team in enumerate(order):
                wins[team] = 100 - 2 * place
        # Division winners must lead their divisions; wild cards trail a division winner.
        records = {team: {**dict.fromkeys(("played", "losses", "ties", "otLosses", "divisionWins", "divisionLosses", "divisionTies", "conferenceWins", "conferenceLosses", "conferenceTies", "scored", "allowed", "homeWins", "homeLosses", "awayWins", "awayLosses"), 0), "wins": wins[team], "regulationWins": wins[team], "results": []} for team in teams}
        for team in teams:
            records[team]["losses"] = 162 - wins[team]
        self.seeding = us_sports.current_seeding(self.cfg, self.structure, records, "baseball", dict.fromkeys(teams, 0.0))
        self.ratings = us_sports.Ratings(home=0.1, sigma=2.4, rating=dict.fromkeys(teams, 0.0))

    def game(self, stage: str, home: str, away: str, home_score: int | None, away_score: int | None) -> us_sports.PlayoffGame:
        return us_sports.PlayoffGame(stage, START, home, away, home_score, away_score)

    def series(self, stage: str, winner: str, loser: str, wins: int, losses: int = 0) -> list[us_sports.PlayoffGame]:
        return [self.game(stage, winner, loser, 5, 2) for _ in range(wins)] + [self.game(stage, winner, loser, 1, 3) for _ in range(losses)]

    def wild_cards(self) -> list[us_sports.PlayoffGame]:
        return (
            self.series("F", "Chicago White Sox", "Houston Astros", 2)
            + self.series("F", "New York Yankees", "Boston Red Sox", 2)
            + self.series("F", "Atlanta Braves", "Philadelphia Phillies", 2, 1)
            + self.series("F", "San Diego Padres", "Chicago Cubs", 2)
        )

    def test_finished_series_fix_their_winners(self) -> None:
        result = us_sports.simulate_postseason(self.cfg, self.structure, self.seeding, self.ratings, self.wild_cards(), simulations=2000)

        title = {team: values["title"] for team, values in result["probabilities"].items()}
        self.assertAlmostEqual(sum(title.values()), 100, delta=0.01)
        for eliminated in ("Houston Astros", "Boston Red Sox", "Philadelphia Phillies", "Chicago Cubs"):
            self.assertEqual(title[eliminated], 0.0)
        first_round = result["rounds"][0]["series"]
        self.assertEqual({item["winner"] for item in first_round}, {"Chicago White Sox", "New York Yankees", "Atlanta Braves", "San Diego Padres"})
        division_series = result["rounds"][1]["series"]
        self.assertEqual(
            {frozenset((item["top"], item["bottom"])) for item in division_series},
            {
                frozenset(("Tampa Bay Rays", "New York Yankees")),
                frozenset(("Cleveland Guardians", "Chicago White Sox")),
                frozenset(("Milwaukee Brewers", "San Diego Padres")),
                frozenset(("Los Angeles Dodgers", "Atlanta Braves")),
            },
        )
        self.assertIsNone(result["champion"])

    def test_a_real_bracket_unlike_our_seeds_pauses_title_odds(self) -> None:
        games = self.series("F", "Houston Astros", "Boston Red Sox", 1)

        self.assertIsNone(us_sports.simulate_postseason(self.cfg, self.structure, self.seeding, self.ratings, games, simulations=200))

    def test_a_finished_world_series_names_the_champion(self) -> None:
        games = (
            self.wild_cards()
            + self.series("D", "New York Yankees", "Tampa Bay Rays", 3)
            + self.series("D", "Cleveland Guardians", "Chicago White Sox", 3, 1)
            + self.series("D", "Milwaukee Brewers", "San Diego Padres", 3)
            + self.series("D", "Los Angeles Dodgers", "Atlanta Braves", 3, 2)
            + self.series("L", "Cleveland Guardians", "New York Yankees", 4, 2)
            + self.series("L", "Milwaukee Brewers", "Los Angeles Dodgers", 4, 3)
            + self.series("W", "Milwaukee Brewers", "Cleveland Guardians", 4, 1)
        )

        result = us_sports.simulate_postseason(self.cfg, self.structure, self.seeding, self.ratings, games, simulations=500)

        self.assertEqual(result["champion"], "Milwaukee Brewers")
        self.assertEqual(result["probabilities"]["Milwaukee Brewers"]["title"], 100.0)
        self.assertEqual(result["probabilities"]["Tampa Bay Rays"]["bye"], 100.0)

    def test_a_tie_for_the_last_place_is_settled_by_the_real_bracket(self) -> None:
        # Detroit and the White Sox finish level; our order gives Chicago the 6th seed, the league gave it to Detroit.
        teams = self.structure.teams
        records = {team: {**dict.fromkeys(("played", "ties", "otLosses", "divisionWins", "divisionLosses", "divisionTies", "conferenceWins", "conferenceLosses", "conferenceTies", "scored", "allowed", "homeWins", "homeLosses", "awayWins", "awayLosses"), 0), "results": []} for team in teams}
        wins = {team: 70 for team in teams}
        wins.update({"Tampa Bay Rays": 100, "Cleveland Guardians": 98, "Houston Astros": 96, "New York Yankees": 94, "Boston Red Sox": 92, "Chicago White Sox": 90, "Detroit Tigers": 90})
        wins.update({"Milwaukee Brewers": 100, "Los Angeles Dodgers": 98, "Atlanta Braves": 96, "San Diego Padres": 94, "Chicago Cubs": 92, "Philadelphia Phillies": 90})
        for team in teams:
            records[team].update(wins=wins[team], regulationWins=wins[team], losses=162 - wins[team])
        seeding = us_sports.current_seeding(self.cfg, self.structure, records, "baseball", dict.fromkeys(teams, 0.0))
        games = self.series("F", "Detroit Tigers", "Houston Astros", 1)

        result = us_sports.simulate_postseason(self.cfg, self.structure, seeding, self.ratings, games, simulations=200, records=records)

        self.assertIsNotNone(result)
        seed = {team: int(result["seeding"]["seed"][0, i]) for i, team in enumerate(teams)}
        self.assertEqual(seed["Detroit Tigers"], 6)
        self.assertEqual(result["probabilities"]["Chicago White Sox"]["playoffs"], 0.0)


class NhlFeedTests(unittest.TestCase):
    def test_games_come_with_overtime_and_shootout_notes_in_utc(self) -> None:
        teams = {"data": [{"id": 6, "fullName": "Boston Bruins"}, {"id": 7, "fullName": "Buffalo Sabres"}]}
        games = {
            "data": [
                {"id": 1, "gameType": 2, "easternStartTime": "2026-10-08T19:00:00", "gameStateId": 7, "period": 5, "homeTeamId": 6, "visitingTeamId": 7, "homeScore": 3, "visitingScore": 2},
                {"id": 2, "gameType": 2, "easternStartTime": "2026-10-10T19:00:00", "gameStateId": 1, "period": 1, "homeTeamId": 7, "visitingTeamId": 6, "homeScore": 0, "visitingScore": 0},
                {"id": 3, "gameType": 1, "easternStartTime": "2026-09-20T19:00:00", "gameStateId": 7, "period": 3, "homeTeamId": 7, "visitingTeamId": 6, "homeScore": 1, "visitingScore": 0},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "nhl-teams.json").write_text(json.dumps(teams))
            (cache / "nhl-api-2026.json").write_text(json.dumps(games))
            parsed = us_sports.fetch_nhl_games(2026, cache)

        self.assertEqual([game.id for game in parsed], ["1", "2"])
        self.assertEqual(parsed[0].note, "SO")
        self.assertEqual(parsed[0].date, datetime(2026, 10, 8, 23, tzinfo=timezone.utc))
        self.assertFalse(parsed[1].played)

    def test_every_rolling_config_validates(self) -> None:
        for league_id in ("nfl", "nba", "nhl", "mlb", "wnba", "nbl", "wnbl"):
            with self.subTest(league_id):
                team_sports.validate_config(config(league_id))


if __name__ == "__main__":
    unittest.main()
