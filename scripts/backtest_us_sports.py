"""Backtest the margin model of a league built by us_sports.py on its past seasons.

Game level: before each week, ratings are fitted on the games played so far (and last
season's, weighted) and that week's games are predicted. The log loss of those predictions
picks the margin cap, half-life, weight on last season, ridge and spread (sigma).

Season level: at 25%, 50% and 75% of each season the rest of it is simulated with the chosen
settings and a strength drift, and the Brier score of the playoff odds against the real
playoff field picks the drift.

    venv/bin/python scripts/backtest_us_sports.py --league wnba --seasons 2022 2023 2024 2025 2026 --espn 2021 2022 2023

FixtureDownload has the regular season of most leagues; --espn reads the listed seasons from
ESPN's public scoreboard instead (the WNBA before 2024).
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import leagues  # noqa: E402
import team_sports  # noqa: E402
import us_sports  # noqa: E402
from team_sports import Game  # noqa: E402

CACHE = Path(os.getenv("FIXTURES_CACHE_DIR", ROOT / ".cache" / "fixtures"))
CHECKPOINTS = (0.25, 0.5, 0.75)


def espn_season(config: dict, year: int) -> list[Game]:
    """Regular-season games from ESPN; the Commissioner's Cup final and All-Star games are left out."""
    league = us_sports.ESPN_PROVIDERS[config["postseason"]["provider"]]["league"]
    data = us_sports._cached_json(us_sports.ESPN_URL.format(league=league, year=year), CACHE / f"{league}-espn-{year}.json", 24 * 30)
    games = []
    for event in data.get("events", []):
        competition = event["competitions"][0]
        headline = next((note.get("headline", "") for note in competition.get("notes", [])), "")
        if event.get("season", {}).get("type") != 2 or "Championship" in headline:
            continue
        if not competition.get("status", {}).get("type", {}).get("completed"):
            continue
        sides = {item["homeAway"]: item for item in competition["competitors"]}
        games.append(
            Game(
                id=event["id"],
                round=None,
                date=datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
                home=sides["home"]["team"]["displayName"],
                away=sides["away"]["team"]["displayName"],
                venue=None,
                home_score=int(sides["home"]["score"]),
                away_score=int(sides["away"]["score"]),
            )
        )
    return sorted(games, key=lambda game: game.date)


def season_config(config: dict, games: list[Game]) -> dict:
    """The league config cut down to one season's teams and schedule length."""
    aliases = config.get("aliases", {})
    names = {aliases.get(name, name) for game in games for name in (game.home, game.away)} & set(config["teams"])
    counts = Counter()
    for game in games:
        home, away = aliases.get(game.home, game.home), aliases.get(game.away, game.away)
        if home in names and away in names:
            counts[home] += 1
            counts[away] += 1
    per_team = Counter(counts.values()).most_common(1)[0][0]
    return dict(config, teams={name: config["teams"][name] for name in names}, gamesPerTeam=per_team)


def load(config: dict, year: int, espn_years: set[int]) -> tuple[dict, list[Game]]:
    if year in espn_years:
        raw = espn_season(config, year)
    else:
        feed = config["season"]["feed"].format(year=year, next=year + 1, yy=f"{(year + 1) % 100:02d}")
        raw = team_sports.fetch_games(feed, CACHE, max_age_hours=24 * 30)
    cfg = season_config(config, raw)
    games = [game for game in us_sports.regular_season(cfg, raw) if game.played]
    return cfg, games


def week_predictions(games, previous, teams, model) -> tuple[np.ndarray, np.ndarray]:
    """Predicted home margins and outcomes for every game, from ratings fitted before its week."""
    start = games[0].date
    margins, outcomes = [], []
    week = 0
    while True:
        begin, end = start + timedelta(days=7 * week), start + timedelta(days=7 * (week + 1))
        if begin > games[-1].date:
            break
        batch = [game for game in games if begin <= game.date < end]
        if batch:
            ratings = us_sports.fit_ratings([game for game in games if game.date < begin], previous, teams, model, begin)
            for game in batch:
                margins.append(ratings.home + ratings.rating.get(game.home, 0.0) - ratings.rating.get(game.away, 0.0))
                outcomes.append(game.home_score > game.away_score)
        week += 1
    return np.array(margins), np.array(outcomes)


def log_loss(p: np.ndarray, outcomes: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(np.where(outcomes, np.log(p), np.log(1 - p))))


def game_level(config, seasons, caps, half_lives, previous_weights, ridges, sigmas):
    rows = []
    outcome = np.array([])
    for cap, half_life, weight, ridge in itertools.product(caps, half_lives, previous_weights, ridges):
        model = us_sports.SportModel(margin_cap=cap, half_life_days=half_life, previous_weight=weight, ridge=ridge, drift=0.0, sigma=1.0)
        margins, outcomes = [], []
        for year, (cfg, games, previous) in seasons.items():
            m, o = week_predictions(games, previous, sorted(cfg["teams"]), model)
            margins.append(m)
            outcomes.append(o)
        margin, outcome = np.concatenate(margins), np.concatenate(outcomes)
        losses = {sigma: log_loss(us_sports._ndtr(margin / sigma), outcome) for sigma in sigmas}
        sigma = min(losses, key=losses.get)
        rows.append({"cap": cap, "halfLife": half_life, "previousWeight": weight, "ridge": ridge, "sigma": sigma, "logLoss": losses[sigma], "games": len(outcome)})
    rows.sort(key=lambda row: row["logLoss"])
    base = log_loss(np.full(len(outcome), outcome.mean()), outcome)
    return rows, base, float(outcome.mean())


def final_playoff_field(cfg: dict, games: list[Game]) -> set[str]:
    """Teams in the playoff places of the final table, with the league's tiebreakers."""
    structure = us_sports.league_structure(cfg)
    records = us_sports.team_records(games, structure, cfg["sport"])
    steps = cfg["playoffs"].get("tiebreakers")
    order = us_sports.tiebreak_order(steps, cfg["sport"], games, records, {}) if steps else {}
    seeding = us_sports.ordered_seeding(cfg, structure, records, cfg["sport"], order)
    return {team for i, team in enumerate(structure.teams) if seeding["playoff"][0, i]}


def season_level(config, seasons, model, drifts, simulations):
    tier = next(tier["key"] for tier in config["tiers"] if tier["kind"] == "playoffs")
    results = {drift: [] for drift in drifts}
    for year, (cfg, games, previous) in seasons.items():
        field = final_playoff_field(cfg, games)
        structure = us_sports.league_structure(cfg)
        for share in CHECKPOINTS:
            cut = int(len(games) * share)
            anchor = games[cut].date
            known = games[:cut]
            schedule = known + [dataclasses.replace(game, home_score=None, away_score=None) for game in games[cut:]]
            ratings = us_sports.fit_ratings(known, previous, structure.teams, model, anchor)
            for drift in drifts:
                us_sports.LEAGUE_MODELS[config["id"]] = dataclasses.replace(model, drift=drift)
                out = us_sports.simulate(cfg, cfg["sport"], structure, schedule, ratings, 1 - share, simulations=simulations, seed=year)
                for team in structure.teams:
                    p = out["probabilities"][team][tier] / 100
                    results[drift].append((year, share, (p - (team in field)) ** 2))
    summary = {}
    for drift, items in results.items():
        summary[drift] = {
            "brier": float(np.mean([item[2] for item in items])),
            **{f"brier{int(share * 100)}": float(np.mean([item[2] for item in items if item[1] == share])) for share in CHECKPOINTS},
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--league", required=True)
    parser.add_argument("--seasons", type=int, nargs="+", required=True, help="First year of each season to evaluate.")
    parser.add_argument("--espn", type=int, nargs="*", default=[], help="Seasons to read from ESPN instead of FixtureDownload.")
    parser.add_argument("--simulations", type=int, default=4000)
    parser.add_argument("--caps", type=float, nargs="+", default=[15, 20, 25, 30])
    parser.add_argument("--half-lives", type=float, nargs="+", default=[30, 45, 60, 90, 120, 180, 365])
    parser.add_argument("--previous-weights", type=float, nargs="+", default=[0.25, 0.5, 1.0])
    parser.add_argument("--ridges", type=float, nargs="+", default=[0.5, 1, 2, 4, 8])
    parser.add_argument("--drifts", type=float, nargs="+", default=[0, 1, 2, 3, 4, 5, 6, 8])
    args = parser.parse_args()

    config = leagues.read_config(args.league)
    espn_years = set(args.espn)
    seasons = {}
    for year in args.seasons:
        cfg, games = load(config, year, espn_years)
        try:
            _, previous = load(config, year - 1, espn_years)
        except team_sports.FeedError:
            previous = []
        seasons[year] = (cfg, games, previous)
        print(f"{year}: {len(cfg['teams'])} teams, {len(games)} games, {cfg['gamesPerTeam']} each; previous season {len(previous)} games")

    sigmas = [round(value, 2) for value in np.arange(6.0, 16.01, 0.25)]
    rows, base, home_rate = game_level(config, seasons, args.caps, args.half_lives, args.previous_weights, args.ridges, sigmas)
    print(f"\nWeek-ahead games: {rows[0]['games']}; home teams won {home_rate:.3f}; base-rate log loss {base:.4f}")
    for row in rows[:10]:
        print(json.dumps(row))
    best = rows[0]
    model = us_sports.SportModel(
        margin_cap=best["cap"], half_life_days=best["halfLife"], previous_weight=best["previousWeight"], ridge=best["ridge"], drift=0.0, sigma=best["sigma"]
    )
    summary = season_level(config, seasons, model, args.drifts, args.simulations)
    print("\nPlayoff odds (Brier score, lower is better) by drift:")
    for drift, values in summary.items():
        print(f"  drift {drift:>4}: " + "  ".join(f"{key} {value:.4f}" for key, value in values.items()))


if __name__ == "__main__":
    main()
