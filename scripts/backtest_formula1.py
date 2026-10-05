"""Backtest the Formula 1 pace model (formula1.py) on past seasons.

Race level: before every Grand Prix the model is fitted on the races and sprints run so far
(this season and the one before, as on the site) and gives each starter a chance of winning.
Those chances are scored against the winner (log loss and Brier score) next to two naive
guesses: every starter equal, and chances in proportion to championship points so far (plus
one; last season's points before a season's first race).

Season level: at 25%, 50% and 75% of each season the rest of it is simulated, and the
drivers' title, top-three and constructors' title odds are scored (Brier score) against the
final standings, next to the table at the time and base rates.

    venv/bin/python scripts/backtest_formula1.py --seasons 2022 2023 2024 2025
    venv/bin/python scripts/backtest_formula1.py --tune

Downloads go through formula1.py's cache (FIXTURES_CACHE_DIR, default .cache/fixtures), so a
repeat run makes no requests.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import formula1  # noqa: E402
import leagues  # noqa: E402

CACHE = Path(os.getenv("FIXTURES_CACHE_DIR", ROOT / ".cache" / "fixtures"))
CHECKPOINTS = (0.25, 0.5, 0.75)
FLOOR = 1e-4


def load(seasons: list[int]) -> dict[int, formula1.SeasonData]:
    years = sorted(set(seasons) | {season - 1 for season in seasons})
    return {year: formula1.load_season(year, CACHE, current=False) for year in years}


def fit(config: dict, season: int, events: list[formula1.Event], settings: formula1.ModelSettings, teams=()) -> formula1.PaceModel:
    return formula1.fit_model(
        events,
        season,
        settings,
        new_rules=config.get("regulationChanges", []),
        predecessors=config.get("predecessors", {}),
        teams=teams,
    )


def history(data: dict[int, formula1.SeasonData], season: int, before: formula1.Event | None) -> list[formula1.Event]:
    """Every result before ``before`` from this season and the previous one."""
    events = [event for year in (season - 1, season) if year in data for event in data[year].events if event.done]
    if before is None:
        return events
    return [event for event in events if (event.season, event.date) < (before.season, before.date)]


def race_scores(config: dict, data: dict[int, formula1.SeasonData], seasons: list[int], settings: formula1.ModelSettings) -> dict[str, dict[str, float]]:
    totals = {name: {"log_loss": 0.0, "brier": 0.0} for name in ("model", "equal", "points")}
    count = 0
    for season in seasons:
        rules = formula1.PointsRules.from_config(config, season)
        previous_rows, _, _ = formula1.championship(data[season - 1].events, formula1.PointsRules.from_config(config, season - 1)) if season - 1 in data else ({}, {}, [])
        for event in data[season].events:
            if event.kind != "race" or not event.done:
                continue
            starters = [entry for entry in event.entries if entry.started]
            winner = next(entry.driver for entry in event.entries if entry.position == 1)
            lineup = {entry.driver: entry.constructor for entry in starters}
            before = history(data, season, event)
            model = fit(config, season, before, settings, teams=set(lineup.values()))
            chances = formula1.win_probabilities(model, lineup)
            rows, _, _ = formula1.championship([item for item in before if item.season == season], rules)
            source = rows if any(row.points for row in rows.values()) else previous_rows
            weights = {driver: (source[driver].points if driver in source else 0.0) + 1.0 for driver in lineup}
            guesses = {
                "model": chances,
                "equal": {driver: 1 / len(lineup) for driver in lineup},
                "points": {driver: weights[driver] / sum(weights.values()) for driver in lineup},
            }
            for name, guess in guesses.items():
                total = sum(guess.values())
                totals[name]["log_loss"] -= math.log(max(guess.get(winner, 0.0) / total, FLOOR))
                totals[name]["brier"] += sum((value / total - (driver == winner)) ** 2 for driver, value in guess.items())
            count += 1
    return {name: {metric: value / count for metric, value in values.items()} | {"races": count} for name, values in totals.items()}


def season_scores(
    config: dict, data: dict[int, formula1.SeasonData], seasons: list[int], settings: formula1.ModelSettings, simulations: int = 4000
) -> dict[str, object]:
    """Brier scores of title and top-three odds at each checkpoint, with the predictions for binning."""
    records = []  # (tier, predicted, outcome, table guess, base rate)
    for season in seasons:
        rules = formula1.PointsRules.from_config(config, season)
        events = data[season].events
        final_drivers, final_teams, _ = formula1.championship(events, rules)
        driver_order = formula1.ranked_keys(final_drivers)
        team_order = formula1.ranked_keys(final_teams)
        races = [event for event in events if event.kind == "race"]
        for share in CHECKPOINTS:
            last = races[round(share * len(races)) - 1]
            done = [event for event in events if event.round <= last.round]
            remaining = [dataclasses.replace(event, entries=()) for event in events if event.round > last.round]
            lineup = {entry.driver: entry.constructor for entry in last.entries}
            before = [event for event in history(data, season, None) if event.season < season] + done
            model = fit(config, season, before, settings, teams=set(lineup.values()))
            drivers, teams, _ = formula1.championship(done, rules)
            odds = formula1.simulate_season(
                model, lineup, remaining, rules, drivers, teams, settings.drift, len(events),
                driver_drift=settings.driver_drift, simulations=simulations, seed=season * 10 + int(share * 4),
            )
            now_drivers = formula1.ranked_keys(drivers)
            now_teams = formula1.ranked_keys(teams)
            for driver in drivers:
                records.append(("title", odds.driver_title.get(driver, 0.0), driver == driver_order[0], driver == now_drivers[0], 1 / len(drivers)))
                records.append(("top3", odds.driver_top3.get(driver, 0.0), driver in driver_order[:3], driver in now_drivers[:3], 3 / len(drivers)))
            for team in teams:
                records.append(("constructors", odds.constructor_title.get(team, 0.0), team == team_order[0], team == now_teams[0], 1 / len(teams)))
    result: dict[str, object] = {}
    for tier in ("title", "top3", "constructors", "all"):
        chosen = [record for record in records if tier == "all" or record[0] == tier]
        predicted = np.array([record[1] for record in chosen])
        outcome = np.array([record[2] for record in chosen], dtype=float)
        table = np.array([record[3] for record in chosen], dtype=float)
        base = np.array([record[4] for record in chosen])
        result[tier] = {
            "brier": float(((predicted - outcome) ** 2).mean()),
            "table": float(((table - outcome) ** 2).mean()),
            "base": float(((base - outcome) ** 2).mean()),
            "log_loss": float(-(outcome * np.log(np.clip(predicted, FLOOR, 1)) + (1 - outcome) * np.log(np.clip(1 - predicted, FLOOR, 1))).mean()),
        }
    bins = [(0.0, 0.02), (0.02, 0.1), (0.1, 0.3), (0.3, 0.7), (0.7, 0.9), (0.9, 1.01)]
    result["bins"] = []
    for low, high in bins:
        chosen = [record for record in records if low <= record[1] < high]
        if chosen:
            result["bins"].append((low, high, len(chosen), float(np.mean([r[1] for r in chosen])), float(np.mean([r[2] for r in chosen]))))
    return result


def describe(settings: formula1.ModelSettings) -> str:
    return (
        f"half-life {settings.half_life_days:g}, skill ridge {settings.skill_ridge:g}, car ridge {settings.car_ridge:g}, "
        f"carryover {settings.carryover:g}/{settings.carryover_new_rules:g}, sprint weight {settings.sprint_weight:g}, dnf prior {settings.dnf_prior:g}"
    )


def tune(config: dict, data: dict[int, formula1.SeasonData], stable: list[int], new_rules: list[int], settings: formula1.ModelSettings) -> formula1.ModelSettings:
    """Coordinate search on race-winner log loss; the new-rules carryover is tuned on new-rules seasons only."""
    grid = {
        "half_life_days": [45, 60, 90, 120, 180, 270, 365],
        "skill_ridge": [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0],
        "car_ridge": [0.1, 0.25, 0.5, 1.0, 2.0, 4.0],
        "carryover": [0.4, 0.6, 0.8, 0.9, 1.0],
        "sprint_weight": [0.0, 0.1, 0.25, 0.5, 1.0],
        "dnf_prior": [0.5, 1.0, 3.0, 10.0, 30.0],
    }
    everything = stable + new_rules
    for round_number in range(2):
        for name, values in grid.items():
            seasons = stable if name == "carryover" else everything
            scores = {}
            for value in values:
                trial = dataclasses.replace(settings, **{name: value})
                scores[value] = race_scores(config, data, seasons, trial)["model"]["log_loss"]
            best = min(scores, key=scores.get)
            print(f"  pass {round_number + 1} {name} ({'+'.join(map(str, seasons))}): " + ", ".join(f"{value:g}={score:.4f}" for value, score in scores.items()) + f" -> {best:g}")
            settings = dataclasses.replace(settings, **{name: best})
        scores = {}
        for value in [0.0, 0.15, 0.3, 0.5, 0.7, 0.9]:
            trial = dataclasses.replace(settings, carryover_new_rules=value)
            scores[value] = race_scores(config, data, new_rules, trial)["model"]["log_loss"]
        best = min(scores, key=scores.get)
        print(f"  pass {round_number + 1} carryover_new_rules ({'+'.join(map(str, new_rules))}): " + ", ".join(f"{value:g}={score:.4f}" for value, score in scores.items()) + f" -> {best:g}")
        settings = dataclasses.replace(settings, carryover_new_rules=best)
    return settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seasons", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    parser.add_argument("--tune", action="store_true", help="search the model settings on race-winner log loss, then the drift on title odds")
    parser.add_argument("--drifts", nargs="+", type=float, default=None, help="car drifts to try (default: the model's)")
    parser.add_argument("--driver-drifts", nargs="+", type=float, default=None, help="driver drifts to try (default: the model's)")
    parser.add_argument("--simulations", type=int, default=4000)
    args = parser.parse_args()

    config = leagues.read_config("f1")
    data = load(args.seasons)
    settings = formula1.ModelSettings()
    new_rules = [season for season in args.seasons if season in config.get("regulationChanges", [])]
    stable = [season for season in args.seasons if season not in new_rules]
    if args.tune:
        print("Tuning race-winner predictions")
        settings = tune(config, data, stable, new_rules, settings)
    print(f"Settings: {describe(settings)}")

    print("\nRace winners (before each Grand Prix):")
    for seasons in [[season] for season in args.seasons] + [args.seasons]:
        scores = race_scores(config, data, seasons, settings)
        label = "all" if len(seasons) > 1 else str(seasons[0])
        print(
            f"  {label}: {scores['model']['races']} races; log loss {scores['model']['log_loss']:.3f} "
            f"(points share {scores['points']['log_loss']:.3f}, equal {scores['equal']['log_loss']:.3f}); "
            f"Brier {scores['model']['brier']:.3f} (points share {scores['points']['brier']:.3f}, equal {scores['equal']['brier']:.3f})"
        )

    print("\nSeason odds at 25%, 50% and 75% (Brier; table at the time; base rate; log loss):")
    if args.tune:
        args.drifts = args.drifts or [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        args.driver_drifts = args.driver_drifts or [0.0, 0.25, 0.5, 1.0]
    best = None
    for drift in args.drifts or [settings.drift]:
        for driver_drift in args.driver_drifts or [settings.driver_drift]:
            trial = dataclasses.replace(settings, drift=drift, driver_drift=driver_drift)
            result = season_scores(config, data, args.seasons, trial, args.simulations)
            parts = ", ".join(f"{tier} {result[tier]['brier']:.4f}" for tier in ("title", "top3", "constructors"))
            print(
                f"  drift {drift:g}/{driver_drift:g}: all {result['all']['brier']:.4f} (table {result['all']['table']:.4f}, "
                f"base {result['all']['base']:.4f}; log loss {result['all']['log_loss']:.4f}); {parts}"
            )
            if best is None or result["all"]["brier"] < best[1]["all"]["brier"]:
                best = ((drift, driver_drift), result)
    (drift, driver_drift), result = best
    print(f"\nBest drift {drift:g} (cars), {driver_drift:g} (drivers). Calibration, predicted v observed:")
    for low, high, size, predicted, observed in result["bins"]:
        print(f"  {low:.2f}-{min(high, 1):.2f}: {predicted:.3f} v {observed:.3f} ({size})")
    for tier in ("title", "top3", "constructors"):
        print(f"  {tier}: Brier {result[tier]['brier']:.4f}, table at the time {result[tier]['table']:.4f}, base rate {result[tier]['base']:.4f}")


if __name__ == "__main__":
    main()
