#!/usr/bin/env python3
"""Backtest the World Test Championship model on past cycles.

Match predictions: before every championship Test of the 2019-21, 2021-23, 2023-25 and
2025-27 cycles, the model is fitted on the Tests finished before it started (as the site
would have been) and its win/draw/loss chances are scored (ranked probability score and
log loss) against base rates: the home-win, draw and away-win shares of all Tests in the
previous four years.

Season odds: at 25%, 50% and 75% of the 2021-23 and 2023-25 round stages (the ones with
today's 12-6-4 points), the rest of each cycle is simulated from the table at the time
and the chances of reaching the final are scored (Brier score) against the real finalists,
next to the table at the time and a no-skill guess. This sets the rating drift.

    venv/bin/python scripts/backtest_wtc.py
    venv/bin/python scripts/backtest_wtc.py --tune
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wtc  # noqa: E402
import wtc_model  # noqa: E402
from wtc_model import ModelSettings, TestMatch  # noqa: E402

TEAMS = ("AUS", "BAN", "ENG", "IND", "NZ", "PAK", "SA", "SL", "WI")
NAMES = {
    "AUS": "Australia", "BAN": "Bangladesh", "ENG": "England", "IND": "India", "NZ": "New Zealand",
    "PAK": "Pakistan", "SA": "South Africa", "SL": "Sri Lanka", "WI": "West Indies",
}

# Round-stage windows. Tests between two championship teams in a window are championship Tests,
# except bilateral series arranged outside it (listed by their first day).
CYCLES = {
    "2019-21": {
        "start": date(2019, 8, 1),
        # South Africa's second Test in St Lucia (18-22 June 2021) counted, alongside the final.
        "end": date(2021, 6, 22),
        # England's two Tests in New Zealand (Nov 2019) and New Zealand's two in England (June 2021).
        "exclude": {(frozenset({"ENG", "NZ"}), date(2019, 11, 21)), (frozenset({"ENG", "NZ"}), date(2019, 11, 29)),
                    (frozenset({"ENG", "NZ"}), date(2021, 6, 2)), (frozenset({"ENG", "NZ"}), date(2021, 6, 10))},
        "finalists": ("IND", "NZ"),
        "points": "series",
    },
    "2021-23": {
        "start": date(2021, 8, 4),
        "end": date(2023, 6, 6),
        # England's two Tests in New Zealand (February 2023) were not championship Tests (ICC table: ENG 22, NZ 13).
        "exclude": {(frozenset({"ENG", "NZ"}), date(2023, 2, 16)), (frozenset({"ENG", "NZ"}), date(2023, 2, 24))},
        "finalists": ("AUS", "IND"),
        "points": "match",
    },
    "2023-25": {"start": date(2023, 6, 16), "end": date(2025, 6, 10), "exclude": set(), "finalists": ("SA", "AUS"), "points": "match"},
    "2025-27": {"start": date(2025, 6, 17), "end": date(2027, 4, 30), "exclude": set(), "finalists": None, "points": "match"},
}
# Over-rate deductions of the 12-6-4 cycles: team, points, first day of the Test (ICC releases;
# totals agree with the ICC's final tables: 2021-23 IND 5, ENG 12, WI 2; 2023-25 AUS 10, IND 2,
# NZ 3, ENG 22, BAN 3, PAK 13).
DEDUCTIONS: dict[str, list[tuple[str, int, date]]] = {
    "2021-23": [
        ("ENG", 2, date(2021, 8, 4)), ("IND", 2, date(2021, 8, 4)), ("ENG", 8, date(2021, 12, 8)),
        ("IND", 1, date(2021, 12, 26)), ("WI", 2, date(2022, 3, 8)), ("ENG", 2, date(2022, 6, 10)),
        ("IND", 2, date(2022, 7, 1)),
    ],
    "2023-25": [
        ("ENG", 2, date(2023, 6, 16)), ("ENG", 9, date(2023, 6, 28)), ("ENG", 3, date(2023, 7, 19)),
        ("AUS", 10, date(2023, 7, 19)), ("ENG", 5, date(2023, 7, 27)), ("PAK", 2, date(2023, 12, 14)),
        ("IND", 2, date(2023, 12, 26)), ("PAK", 6, date(2024, 8, 21)), ("BAN", 3, date(2024, 8, 21)),
        ("ENG", 3, date(2024, 11, 28)), ("NZ", 3, date(2024, 11, 28)), ("PAK", 5, date(2025, 1, 3)),
    ],
}
# The ICC's final PCT of the 12-6-4 cycles, to check the rebuilt tables.
OFFICIAL_PCT = {
    "2021-23": {"AUS": 66.67, "IND": 58.80, "SA": 55.56, "ENG": 46.97, "SL": 44.44, "NZ": 38.46, "PAK": 38.10, "WI": 34.62, "BAN": 11.11},
    "2023-25": {"SA": 69.44, "AUS": 67.54, "IND": 50.00, "NZ": 48.21, "ENG": 43.18, "SL": 38.46, "BAN": 31.25, "WI": 28.21, "PAK": 27.98},
}
BASE_RATE_YEARS = 4


def cycle_tests(tests: list[TestMatch], name: str) -> list[TestMatch]:
    spec = CYCLES[name]
    chosen = []
    for test in tests:
        if not set(test.teams) <= set(TEAMS) or not spec["start"] <= test.start <= spec["end"]:
            continue
        if (frozenset(test.teams), test.start) in spec["exclude"]:
            continue
        if test.event == "ICC World Test Championship":
            continue
        chosen.append(test)
    return chosen


def oriented(test: TestMatch) -> tuple[str, str, int]:
    """The home side first (the first listed at a neutral ground), and the result for it."""
    first, second = test.teams
    if test.country == second:
        first, second = second, first
    if test.winner is None:
        result = wtc_model.DRAW
    else:
        result = wtc_model.WIN if test.winner == first else wtc_model.LOSS
    return first, second, result


def base_rates(tests: list[TestMatch], before: date) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Home/draw/away shares (and for neutral grounds) of the Tests in the previous four years."""
    since = before - timedelta(days=int(365.25 * BASE_RATE_YEARS))
    counts = np.ones(3)  # a pseudo-count each
    for test in tests:
        if not since <= test.end < before or test.country not in test.teams:
            continue
        counts[oriented(test)[2]] += 1
    home = tuple(counts / counts.sum())
    neutral = ((home[0] + home[2]) / 2, home[1], (home[0] + home[2]) / 2)
    return home, neutral


@dataclasses.dataclass
class Score:
    rps: list[float] = dataclasses.field(default_factory=list)
    loss: list[float] = dataclasses.field(default_factory=list)
    base_rps: list[float] = dataclasses.field(default_factory=list)
    base_loss: list[float] = dataclasses.field(default_factory=list)
    draw_pred: list[float] = dataclasses.field(default_factory=list)
    draw_seen: list[int] = dataclasses.field(default_factory=list)

    def add(self, probabilities, base, result) -> None:
        self.rps.append(wtc_model.ranked_probability_score(probabilities, result))
        self.loss.append(wtc_model.log_loss(probabilities, result))
        self.base_rps.append(wtc_model.ranked_probability_score(base, result))
        self.base_loss.append(wtc_model.log_loss(base, result))
        self.draw_pred.append(probabilities[1])
        self.draw_seen.append(int(result == wtc_model.DRAW))

    def summary(self) -> dict[str, float]:
        return {
            "tests": len(self.rps),
            "rps": float(np.mean(self.rps)),
            "base_rps": float(np.mean(self.base_rps)),
            "log_loss": float(np.mean(self.loss)),
            "base_log_loss": float(np.mean(self.base_loss)),
            "draw_pred": float(np.mean(self.draw_pred)),
            "draw_seen": float(np.mean(self.draw_seen)),
        }


def match_backtest(tests: list[TestMatch], settings: ModelSettings, cycles: list[str]) -> dict[str, Score]:
    scores: dict[str, Score] = {name: Score() for name in cycles}
    scores["all"] = Score()
    fits: dict[date, wtc_model.Ratings] = {}
    for name in cycles:
        for test in cycle_tests(tests, name):
            if test.start not in fits:
                fits[test.start] = wtc_model.fit(tests, test.start, settings)
            ratings = fits[test.start]
            first, second, result = oriented(test)
            probabilities = ratings.probabilities(first, second, test.country)
            home, neutral = base_rates(tests, test.start)
            base = home if test.country in test.teams else neutral
            scores[name].add(probabilities, base, result)
            scores["all"].add(probabilities, base, result)
    return scores


def cycle_config(tests: list[TestMatch], name: str) -> tuple[dict, list[TestMatch]]:
    """A championship config for a past cycle: each pair's Tests in the window form its series."""
    chosen = cycle_tests(tests, name)
    groups: dict[tuple[str, str], list[TestMatch]] = defaultdict(list)
    for test in chosen:
        first, second, _ = oriented(test)
        host = first if test.country in test.teams else test.teams[0]
        visitor = second if host == first else first
        groups[(host, visitor)].append(test)
    series = []
    for (host, visitor), games in sorted(groups.items()):
        games.sort(key=lambda item: item.start)
        # A pair can meet twice in a cycle (home and away); split by a gap of over 60 days.
        runs: list[list[TestMatch]] = [[games[0]]]
        for game in games[1:]:
            if (game.start - runs[-1][-1].start).days > 60:
                runs.append([game])
            else:
                runs[-1].append(game)
        for number, run in enumerate(runs, start=1):
            series.append(
                {
                    "id": f"{host.lower()}-{visitor.lower()}-{run[0].start.year}-{number}",
                    "host": host,
                    "visitor": visitor,
                    "tests": [
                        {"number": i, "start": game.start.isoformat(), "end": game.end.isoformat(), "country": game.country, "venue": game.venue}
                        for i, game in enumerate(run, start=1)
                    ],
                }
            )
    spec = CYCLES[name]
    config = {
        "id": f"wtc-{name}",
        "name": "ICC World Test Championship",
        "shortName": "WTC",
        "seasonLabel": name,
        "seasonStart": spec["start"].isoformat(),
        "seasonEnd": (spec["end"] + timedelta(days=10)).isoformat(),
        "standingsClose": spec["end"].isoformat(),
        "final": {"country": "ENG", "start": (spec["end"] + timedelta(days=2)).isoformat()},
        "teams": [{"key": team, "shortName": team, "fullName": NAMES[team]} for team in TEAMS],
        "series": series,
    }
    deductions = []
    for team, points, day in DEDUCTIONS.get(name, []):
        key = next(
            f"{item['id']}-{test['number']}"
            for item in series
            for test in item["tests"]
            if test["start"] == day.isoformat() and team in (item["host"], item["visitor"])
        )
        deductions.append({"team": team, "points": points, "test": key, "note": "over rate"})
    config["deductions"] = deductions
    return config, chosen


def final_tables(tests: list[TestMatch]) -> None:
    """Rebuild each 12-6-4 cycle's final table and compare it with the ICC's."""
    for name in OFFICIAL_PCT:
        config, chosen = cycle_config(tests, name)
        cycle = wtc.parse_config(config)
        rows = wtc.table(cycle, wtc.match_cricsheet(cycle, chosen, []))
        order = wtc.rank(cycle, rows)
        ours = {team: round(float(rows[team].pct(cycle.rules)) * 100, 2) for team in order}
        same = all(ours[team] == OFFICIAL_PCT[name][team] for team in TEAMS)
        print(f"  {name}: {' '.join(f'{team} {ours[team]:.2f}' for team in order)} -> {'matches the ICC table' if same else 'DIFFERS from the ICC table'}")


def season_backtest(tests: list[TestMatch], settings: ModelSettings, drift: float, simulations: int = 4000) -> dict[str, float]:
    """Brier score of final-place odds at 25%, 50% and 75% of each finished 12-6-4 cycle."""
    model_scores, table_scores, base_scores = [], [], []
    bins: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for name, spec in CYCLES.items():
        if spec["points"] != "match" or not spec["finalists"]:
            continue
        config, chosen = cycle_config(tests, name)
        cycle = wtc.parse_config(config)
        warnings: list[str] = []
        all_results = wtc.match_cricsheet(cycle, chosen, warnings)
        ordered = sorted(cycle.fixtures, key=lambda item: item.start)
        ends = {fixture.key: fixture.end for fixture in ordered}
        for share in (0.25, 0.5, 0.75):
            cut = ordered[int(len(ordered) * share)].start
            known = {key: result for key, result in all_results.items() if result.end and result.end < cut}
            remaining = [fixture for fixture in ordered if fixture.key not in known]
            # Only the deductions announced by then.
            at_cut = dataclasses.replace(cycle, deductions=tuple(item for item in cycle.deductions if ends[item.test] < cut))
            rows = wtc.table(at_cut, known)
            ratings = wtc_model.fit(tests, cut, settings)
            sim = wtc.simulate(at_cut, rows, known, remaining, ratings, cut, simulations, drift=drift, seed=7)
            order = wtc.rank(at_cut, rows)
            for team in TEAMS:
                truth = int(team in spec["finalists"])
                p = sim.final[team] / 100
                model_scores.append((p - truth) ** 2)
                table_scores.append((float(team in order[:2]) - truth) ** 2)
                base_scores.append((2 / 9 - truth) ** 2)
                bins[min(int(p * 5), 4)].append((p, truth))
    calibration = {
        f"{index * 20}-{index * 20 + 20}%": (round(float(np.mean([p for p, _ in items])), 3), round(float(np.mean([t for _, t in items])), 3), len(items))
        for index, items in sorted(bins.items())
    }
    return {
        "brier": float(np.mean(model_scores)),
        "table": float(np.mean(table_scores)),
        "base": float(np.mean(base_scores)),
        "checkpoints": len(model_scores) // len(TEAMS),
        "calibration": calibration,
    }


def report(scores: dict[str, Score]) -> None:
    for name, score in scores.items():
        s = score.summary()
        print(
            f"  {name:8} {s['tests']:4d} Tests  RPS {s['rps']:.4f} (base {s['base_rps']:.4f})  "
            f"log loss {s['log_loss']:.4f} (base {s['base_log_loss']:.4f})  draws predicted {s['draw_pred']:.3f}, seen {s['draw_seen']:.3f}"
        )


def tune(tests: list[TestMatch], cycles: list[str]) -> ModelSettings:
    grid = {
        "half_life_years": [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 20.0],
        "rating_ridge": [0.25, 0.5, 1.0, 2.0, 4.0],
        "home_ridge": [1.0, 4.0, 16.0, 64.0, 256.0],
        "draw_ridge": [0.5, 2.0, 8.0, 32.0, 128.0],
        "draw_trend": [True, False],
    }
    best = ModelSettings()
    best_score = match_backtest(tests, best, cycles)["all"].summary()["log_loss"]
    print(f"start {best} log loss {best_score:.4f}")
    for _ in range(2):
        for field, values in grid.items():
            for value in values:
                candidate = dataclasses.replace(best, **{field: value})
                if candidate == best:
                    continue
                scores = match_backtest(tests, candidate, cycles)["all"].summary()
                print(f"  {field}={value}: log loss {scores['log_loss']:.4f}  RPS {scores['rps']:.4f}")
                if scores["log_loss"] < best_score - 1e-5:
                    best, best_score = candidate, scores["log_loss"]
        print(f"pass best {best} log loss {best_score:.4f}")
    return best


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--archive", type=Path, help="Cricsheet tests_male_json.zip (downloaded if omitted)")
    parser.add_argument("--cycles", nargs="+", default=list(CYCLES))
    parser.add_argument("--tune", action="store_true", help="coordinate search over the model settings")
    parser.add_argument("--drifts", nargs="+", type=float, default=[0.0, 0.1, 0.2, 0.3, 0.5])
    args = parser.parse_args(argv)
    archive = args.archive or wtc_model.fetch_tests_archive(ROOT / ".cache" / "cricsheet")
    tests = wtc_model.load_tests(archive)
    settings = tune(tests, args.cycles) if args.tune else ModelSettings()
    print("Final tables of the 12-6-4 cycles, rebuilt from Cricsheet and the deductions:")
    final_tables(tests)
    print(f"Match predictions with {settings}:")
    report(match_backtest(tests, settings, args.cycles))
    print("Season odds (reach the final), Brier score:")
    for drift in args.drifts:
        result = season_backtest(tests, settings, drift)
        print(
            f"  drift {drift:.2f}: {result['brier']:.4f} (table at the time {result['table']:.4f}, no-skill {result['base']:.4f}; "
            f"{result['checkpoints']} checkpoints) calibration {result['calibration']}"
        )


if __name__ == "__main__":
    main()
