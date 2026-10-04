"""Backtest the goals model and playoff odds of a league built by football_playoffs.py.

Game level: before each week of a season, football.py's goals model is fitted on the games
played so far and last season's, and that week's games are predicted. The ranked probability
score (RPS) of those home/draw/away predictions is compared with base rates (the home, draw
and away shares of the games the model was fitted on) and across half-lives and ridges.

Season level: at 25%, 50% and 75% of each season the rest of the regular season and the
playoffs are simulated, and the Brier score and log loss of the playoff, top-seed, Supporters'
Shield and title odds against what happened pick the strength drift.

    venv/bin/python scripts/backtest_football_playoffs.py --league mls --seasons 2024 2025

Scores are cross-checked with ESPN's scoreboard as in the published build, and the real
champion comes from ESPN's playoff games.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import football  # noqa: E402
import football_playoffs  # noqa: E402
import leagues  # noqa: E402
import team_sports  # noqa: E402
from team_sports import Game  # noqa: E402

CACHE = Path(os.getenv("FIXTURES_CACHE_DIR", ROOT / ".cache" / "fixtures"))
CHECKPOINTS = (0.25, 0.5, 0.75)


def season_games(config: dict, year: int) -> tuple[list[Game], list[football_playoffs.EspnMatch]]:
    aliases = config.get("aliases", {})
    rule = config["season"]
    feed = rule["feed"].format(year=year, next=year + 1, yy=f"{(year + 1) % 100:02d}")
    games = football_playoffs.rename(team_sports.fetch_games(feed, CACHE, max_age_hours=24 * 30), aliases)
    espn: list[football_playoffs.EspnMatch] = []
    code = config.get("sources", {}).get("espn")
    if code:
        try:
            espn, _ = football_playoffs.fetch_espn_matches(code, year, CACHE, aliases, max_age_hours=24 * 30)
        except team_sports.FeedError as exc:
            print(f"{year}: ESPN unavailable ({exc}); FixtureDownload scores are used as they are")
    if espn:
        games, corrections = football_playoffs.corrected_games(games, espn)
        for before, after in corrections:
            print(f"{year}: {after.home} {after.home_score}-{after.away_score} {after.away} on {football_playoffs.local_day(after.date, config)} (FixtureDownload has {before.home_score}-{before.away_score})")
    return games, espn


def previous_games(config: dict, year: int) -> list[Game]:
    try:
        return season_games(config, year - 1)[0]
    except team_sports.FeedError:
        return []


def rps(probabilities: tuple[float, float, float], outcome: int) -> float:
    observed = [0.0, 0.0, 0.0]
    observed[outcome] = 1.0
    first = probabilities[0] - observed[0]
    second = probabilities[0] + probabilities[1] - observed[0] - observed[1]
    return (first * first + second * second) / 2


def outcome_of(game: Game) -> int:
    return 0 if game.home_score > game.away_score else 1 if game.home_score == game.away_score else 2


def week_ahead(config: dict, seasons: list[int], half_lives: list[float], ridges: list[float]) -> None:
    print("\nWeek-ahead match predictions (ranked probability score, lower is better)")
    data = {year: (season_games(config, year)[0], previous_games(config, year)) for year in seasons}
    rows = []
    base_scores: dict[int, list[float]] = {}
    for half_life in half_lives:
        for ridge in ridges:
            football.HALF_LIFE_DAYS, football.RIDGE = half_life, ridge
            scores: dict[int, list[float]] = {}
            for year, (games, previous) in data.items():
                played = sorted((game for game in games if game.played), key=lambda game: game.date)
                start = played[0].date.replace(hour=0, minute=0, second=0)
                previous_teams = {game.home for game in previous} | {game.away for game in previous}
                teams = sorted({game.home for game in games} | {game.away for game in games} | previous_teams)
                promoted = ({game.home for game in games} | {game.away for game in games}) - previous_teams if previous_teams else set()
                window = start
                while window <= played[-1].date:
                    upcoming = [game for game in played if window <= game.date < window + timedelta(days=7)]
                    if upcoming:
                        known = [game for game in previous if game.played] + [game for game in played if game.date < window]
                        latest = max((game.date for game in known), default=window)
                        model = football.fit_goal_model(known, teams, promoted, min(latest, window))
                        counts = np.bincount([outcome_of(game) for game in known], minlength=3) + 1
                        base = tuple(counts / counts.sum())
                        for game in upcoming:
                            scores.setdefault(year, []).append(rps(model.outcome(game.home, game.away), outcome_of(game)))
                            if not rows:
                                base_scores.setdefault(year, []).append(rps(base, outcome_of(game)))
                    window += timedelta(days=7)
            rows.append((half_life, ridge, {year: float(np.mean(values)) for year, values in scores.items()}, float(np.mean([v for values in scores.values() for v in values]))))
    football.HALF_LIFE_DAYS, football.RIDGE = 240, 2.0
    print(f"  base rates: " + ", ".join(f"{year} {np.mean(values):.4f} ({len(values)} games)" for year, values in base_scores.items())
          + f", all {np.mean([v for values in base_scores.values() for v in values]):.4f}")
    for half_life, ridge, by_year, overall in sorted(rows, key=lambda row: row[3]):
        marker = "  <- football.py's settings" if (half_life, ridge) == (240, 2.0) else ""
        print(f"  half-life {half_life:>4g} days, ridge {ridge:>3g}: " + ", ".join(f"{year} {value:.4f}" for year, value in by_year.items()) + f", all {overall:.4f}{marker}")


def final_outcomes(config: dict, year: int, games: list[Game], espn, rounds) -> tuple[dict[str, dict[str, bool]], dict[str, str]]:
    teams = sorted({game.home for game in games} | {game.away for game in games})
    group_of = {team: football_playoffs.team_group(config, team) for team in teams}
    points = {"win": config["points"]["win"], "draw": config["points"]["draw"]}
    steps = config["tiebreakers"]
    table = football_playoffs.table_rows(games, teams, points)
    members: dict[str, list[str]] = {}
    for team in teams:
        members.setdefault(group_of[team], []).append(team)
    order = {key: football_playoffs.rank_teams(group, table, games, steps, group_of) for key, group in members.items()}
    place = {team: i for group in order.values() for i, team in enumerate(group)}
    overall = football_playoffs.rank_teams(teams, table, games, steps, group_of, fallback=place)
    last = max(game.date for game in games)
    playoff_games = [game for game in espn if not game.regular and game.home in group_of and game.away in group_of and game.date > last]
    bracket = football_playoffs.real_bracket(rounds, order, overall, playoff_games, {}) if playoff_games else None
    champion = bracket["champion"] if bracket and not bracket["unplaced"] else None
    if bracket and bracket["unplaced"]:
        print(f"{year}: ESPN's playoff games do not fit the bracket; title odds are not scored")
    qualifiers = football_playoffs.qualifiers(rounds)
    outcomes = {}
    for team in teams:
        outcomes[team] = {}
        for tier in config["tiers"]:
            kind = tier["kind"]
            if kind == "playoffs":
                outcomes[team][tier["key"]] = place[team] < qualifiers
            elif kind == "seed":
                outcomes[team][tier["key"]] = place[team] < tier["size"]
            elif kind == "top":
                outcomes[team][tier["key"]] = overall.index(team) < tier["size"]
            elif kind == "best-record":
                outcomes[team][tier["key"]] = overall.index(team) == 0
            elif kind == "champion" and champion:
                outcomes[team][tier["key"]] = team == champion
    return outcomes, {"champion": champion or "unknown", "shield": overall[0]}


def season_odds(config: dict, seasons: list[int], drifts: list[float], simulations: int) -> None:
    print("\nSeason odds at 25%, 50% and 75% of each season (Brier score and log loss, lower is better)")
    rounds = football_playoffs.parse_rounds(config)
    points = {"win": config["points"]["win"], "draw": config["points"]["draw"]}
    steps = config["tiebreakers"]
    tiers = config["tiers"]
    collected: dict[float, dict[str, list[tuple[float, float]]]] = {drift: {} for drift in drifts}
    by_checkpoint: dict[float, dict[tuple[int, float], dict[str, float]]] = {drift: {} for drift in drifts}
    for year in seasons:
        games, espn = season_games(config, year)
        previous = previous_games(config, year)
        outcomes, facts = final_outcomes(config, year, games, espn, rounds)
        print(f"  {year}: {len(games)} games, Supporters' Shield {facts['shield']}, MLS Cup {facts['champion']}")
        ordered = sorted(games, key=lambda game: game.date)
        teams = sorted({game.home for game in games} | {game.away for game in games})
        group_of = {team: football_playoffs.team_group(config, team) for team in teams}
        previous_teams = {game.home for game in previous} | {game.away for game in previous}
        promoted = set(teams) - previous_teams if previous_teams else set()
        model_teams = sorted(set(teams) | previous_teams)
        for share in CHECKPOINTS:
            cut = ordered[int(round(share * len(ordered)))].date
            known = [game for game in ordered if game.date < cut]
            remaining = [Game(game.id, game.round, game.date, game.home, game.away, game.venue, None, None) for game in ordered if game.date >= cut]
            latest = max(game.date for game in previous + known)
            model = football.fit_goal_model(previous + known, model_teams, promoted, latest)
            table = football_playoffs.table_rows(known, teams, points)
            for drift in drifts:
                result = football_playoffs.simulate(
                    model, teams, group_of, table, remaining, tiers, points, steps, rounds, drift,
                    simulations=simulations, season_left=len(remaining) / len(ordered),
                )
                scores: dict[str, list[tuple[float, float]]] = {}
                for team in teams:
                    for key, happened in outcomes[team].items():
                        p = min(max(result["probabilities"][team][key] / 100, 1e-4), 1 - 1e-4)
                        y = 1.0 if happened else 0.0
                        item = ((p - y) ** 2, -(y * math.log(p) + (1 - y) * math.log(1 - p)))
                        scores.setdefault(key, []).append(item)
                        collected[drift].setdefault(key, []).append(item)
                        collected[drift].setdefault(f"{key}-calibration", []).append((p, y))
                by_checkpoint[drift][(year, share)] = {key: float(np.mean([s[0] for s in values])) for key, values in scores.items()}
                sums = {key: round(sum(result["probabilities"][team][key] for team in teams) / 100, 2) for key in outcomes[teams[0]]}
                if drift == drifts[0]:
                    print(f"    {int(share * 100)}%: {len(known)} played; expected counts {sums}")
    labels = {tier["key"]: tier["label"] for tier in tiers}
    for drift in drifts:
        parts = []
        for key in labels:
            if key in collected[drift]:
                values = collected[drift][key]
                parts.append(f"{labels[key]} {np.mean([v[0] for v in values]):.4f}/{np.mean([v[1] for v in values]):.4f}")
        brier_total = np.mean([np.mean([v[0] for v in collected[drift][key]]) for key in labels if key in collected[drift]])
        print(f"  drift {drift:>4g}: " + ", ".join(parts) + f"; mean Brier {brier_total:.4f}")
    for drift in drifts:
        print(f"  drift {drift:g} Brier by checkpoint: " + "; ".join(
            f"{year} {int(share * 100)}% " + " ".join(f"{key} {value:.3f}" for key, value in values.items())
            for (year, share), values in by_checkpoint[drift].items()
        ))
    print("\nPlayoff-place calibration (predicted vs observed share, by bin)")
    for drift in drifts:
        pairs = collected[drift].get("playoffs-calibration", [])
        bins = [(0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
        cells = []
        for low, high in bins:
            inside = [(p, y) for p, y in pairs if low <= p < high]
            if inside:
                cells.append(f"{low:.1f}-{min(high, 1):.1f}: {np.mean([p for p, _ in inside]):.2f} vs {np.mean([y for _, y in inside]):.2f} (n={len(inside)})")
        print(f"  drift {drift:g}: " + "; ".join(cells))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--league", default="mls")
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025])
    parser.add_argument("--half-lives", type=float, nargs="+", default=[120, 180, 240, 365, 540])
    parser.add_argument("--ridges", type=float, nargs="+", default=[1, 2, 4])
    parser.add_argument("--drifts", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.4])
    parser.add_argument("--simulations", type=int, default=20_000)
    parser.add_argument("--skip-games", action="store_true", help="only score the season odds")
    args = parser.parse_args()
    config = leagues.read_config(args.league)
    if not args.skip_games:
        week_ahead(config, args.seasons, args.half_lives, args.ridges)
    season_odds(config, args.seasons, args.drifts, args.simulations)


if __name__ == "__main__":
    main()
