"""Backtest the football goals model (football.py) on a league's past seasons.

Match level: before each week, ratings are fitted on the results so far (and the previous
season's, as on the site) and that week's matches are predicted. The ranked probability score
of those predictions is compared with home/draw/away base rates taken from the results known
at the time (the season itself, in hindsight, when there is nothing earlier).

Season level: at 25%, 50% and 75% of each season the rest of it is simulated as on the site,
and the Brier score of every tier chance (title, top places, bottom places) against the final
table is compared with a no-skill guess (tier size over teams).

    venv/bin/python scripts/backtest_football.py --league epl --seasons 2023 2024 2025

--no-history drops the previous season, to see what a league without one in the feed loses;
--half-lives and --ridges try other model settings for the match predictions.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import football  # noqa: E402
import leagues  # noqa: E402
import team_sports  # noqa: E402
from team_sports import Game  # noqa: E402

CACHE = Path(os.getenv("FIXTURES_CACHE_DIR", ROOT / ".cache" / "fixtures"))
CHECKPOINTS = (0.25, 0.5, 0.75)


def feed_name(config: dict, year: int) -> str:
    return config["season"]["feed"].format(year=year, next=year + 1, yy=f"{(year + 1) % 100:02d}")


def load(config: dict, year: int) -> list[Game]:
    return team_sports.fetch_games(feed_name(config, year), CACHE, max_age_hours=24 * 30)


def teams_of(games: list[Game]) -> list[str]:
    return sorted({game.home for game in games} | {game.away for game in games})


def outcome_index(game: Game) -> int:
    return 0 if game.home_score > game.away_score else 1 if game.home_score == game.away_score else 2


def rps(probabilities: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    """Ranked probability score of home/draw/away forecasts (0 is perfect)."""
    observed = np.eye(3)[outcomes]
    return 0.5 * ((np.cumsum(probabilities, axis=1)[:, :2] - np.cumsum(observed, axis=1)[:, :2]) ** 2).sum(axis=1)


def fit(games: list[Game], previous: list[Game], before: datetime) -> football.GoalModel:
    """Ratings as the site would have had them just before ``before``."""
    known = [game for game in games if game.played and game.date < before]
    teams = teams_of(games)
    previous_teams = set(teams_of(previous)) if previous else set()
    promoted = set(teams) - previous_teams if previous_teams else set()
    latest = max((game.date for game in previous + known if game.played), default=before)
    return football.fit_goal_model(previous + known, sorted(set(teams) | previous_teams), promoted, min(latest, before))


def week_ahead(games: list[Game], previous: list[Game]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Model and base-rate forecasts, and outcomes, for every played match, a week at a time."""
    played = sorted((game for game in games if game.played), key=lambda game: game.date)
    start = played[0].date.replace(hour=0, minute=0, second=0, microsecond=0)
    start -= timedelta(days=start.weekday())
    model_p, base_p, outcomes = [], [], []
    hindsight = np.bincount([outcome_index(game) for game in played], minlength=3) / len(played)
    week = start
    while week <= played[-1].date:
        batch = [game for game in played if week <= game.date < week + timedelta(days=7)]
        if batch:
            model = fit(games, previous, week)
            known = [game for game in previous + played if game.played and game.date < week]
            base = np.bincount([outcome_index(game) for game in known], minlength=3) / len(known) if known else hindsight
            for game in batch:
                model_p.append(model.outcome(game.home, game.away))
                base_p.append(base)
                outcomes.append(outcome_index(game))
        week += timedelta(days=7)
    return np.array(model_p), np.array(base_p), np.array(outcomes)


def season_odds(config: dict, games: list[Game], previous: list[Game], simulations: int, seed: int) -> list[tuple[float, float, float]]:
    """(checkpoint, model Brier, no-skill Brier) for every team and tier at each checkpoint."""
    tiers = config["tiers"]
    played = sorted((game for game in games if game.played), key=lambda game: game.date)
    teams = teams_of(games)
    points = {"win": config.get("points", {}).get("win", 3), "draw": config.get("points", {}).get("draw", 1)}
    final = football.standings(played, teams, **points)
    order = football.ranked(final, played, config.get("tiebreak"))
    place = {team: order.index(team) for team in teams}
    scores = []
    for share in CHECKPOINTS:
        cut = played[int(len(played) * share)].date
        known = [game for game in played if game.date < cut]
        remaining = [dataclasses.replace(game, home_score=None, away_score=None) for game in played if game.date >= cut]
        model = fit(games, previous, cut)
        table = football.standings(known, teams, **points)
        result = football.simulate(model, teams, table, remaining, tiers, points, simulations=simulations, seed=seed, season_left=len(remaining) / len(played))
        for tier in tiers:
            for team in teams:
                achieved = place[team] >= len(teams) - tier["size"] if tier["kind"] == "bottom" else place[team] < tier["size"]
                p = result["probabilities"][team][tier["key"]] / 100
                guess = tier["size"] / len(teams)
                scores.append((share, (p - achieved) ** 2, (guess - achieved) ** 2))
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--league", required=True)
    parser.add_argument("--seasons", type=int, nargs="+", required=True, help="First year of each season to evaluate.")
    parser.add_argument("--no-history", action="store_true", help="Ignore the previous season.")
    parser.add_argument("--simulations", type=int, default=5000)
    parser.add_argument("--half-lives", type=float, nargs="+", default=[football.HALF_LIFE_DAYS])
    parser.add_argument("--ridges", type=float, nargs="+", default=[football.RIDGE])
    parser.add_argument("--skip-season-odds", action="store_true")
    args = parser.parse_args()

    config = leagues.read_config(args.league)
    seasons = {}
    for year in args.seasons:
        games = load(config, year)
        previous: list[Game] = []
        if not args.no_history:
            try:
                previous = [game for game in load(config, year - 1) if game.played]
            except team_sports.FeedError:
                pass
        seasons[year] = (games, previous)
        played = sum(game.played for game in games)
        print(f"{year}: {len(teams_of(games))} teams, {played} of {len(games)} matches played; previous season {len(previous)} matches")

    print("\nWeek-ahead match predictions (ranked probability score, lower is better)")
    for half_life, ridge in itertools.product(args.half_lives, args.ridges):
        football.HALF_LIFE_DAYS, football.RIDGE = half_life, ridge
        model_all, base_all = [], []
        for year, (games, previous) in seasons.items():
            model_p, base_p, outcomes = week_ahead(games, previous)
            model_rps, base_rps = rps(model_p, outcomes), rps(base_p, outcomes)
            model_all.append(model_rps)
            base_all.append(base_rps)
            print(f"  half-life {half_life:g}, ridge {ridge:g}, {year}: {len(outcomes)} matches, model {model_rps.mean():.4f}, base rates {base_rps.mean():.4f}")
        model_rps, base_rps = np.concatenate(model_all), np.concatenate(base_all)
        print(f"  half-life {half_life:g}, ridge {ridge:g}, all: {len(model_rps)} matches, model {model_rps.mean():.4f}, base rates {base_rps.mean():.4f}")

    if args.skip_season_odds:
        return
    football.HALF_LIFE_DAYS, football.RIDGE = args.half_lives[0], args.ridges[0]
    print(f"\nSeason odds at {', '.join(f'{int(share * 100)}%' for share in CHECKPOINTS)} of each season (Brier score of every tier chance)")
    everything = []
    for year, (games, previous) in seasons.items():
        # A few results of a finished season can be missing from the feed; those matches are left out.
        if any(not game.played and game.date > datetime.now(timezone.utc) - timedelta(days=7) for game in games):
            print(f"  {year}: not finished, skipped")
            continue
        scores = season_odds(config, games, previous, args.simulations, seed=year)
        everything += scores
        by_share = "; ".join(
            f"{int(share * 100)}%: {np.mean([s[1] for s in scores if s[0] == share]):.4f} (no skill {np.mean([s[2] for s in scores if s[0] == share]):.4f})"
            for share in CHECKPOINTS
        )
        print(f"  {year}: {by_share}")
    if everything:
        print(f"  all: model {np.mean([s[1] for s in everything]):.4f}, no skill {np.mean([s[2] for s in everything]):.4f}")


if __name__ == "__main__":
    main()
