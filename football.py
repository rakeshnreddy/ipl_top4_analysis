"""Football (soccer) league tables, a goals model and season simulations.

Each match is modelled with independent Poisson goal counts from team attack and
defence ratings plus home advantage (a Maher/Dixon-Coles style model), fitted on
the previous and current season with a time decay. The rest of the season is then
simulated to estimate title, top-four and relegation chances.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

import football_split
import team_sports
from team_sports import Game


SIMULATIONS = 20_000
SEED = 20260801
# Chosen by backtesting 2025-26 in five leagues (ranked probability score).
HALF_LIFE_DAYS = 240
RIDGE = 2.0
# A league's first season in the feed has no last season to anchor the ratings. Without it,
# week-ahead predictions of 2023-24 to 2025-26 scored better with a ridge of 4 than 2 in all eight
# leagues (ranked probability score 0.0005-0.0022 lower), and season odds at a fifth of the way
# through were no worse (Brier 0.0582 against 0.0585).
FIRST_SEASON_RIDGE = 4.0
# Newly promoted sides score less and concede more than the league average, and their ratings
# rest on far fewer top-flight games, so they are held to that prior more firmly (ridge x6).
# Week-ahead predictions of 25 league-seasons (2023-24 to 2025-26, nine leagues) improved with
# it: ranked probability score 0.2020 against 0.2026 overall, 0.2002 against 0.2019 in games
# with a promoted side, 0.2007 against 0.2057 in those games in the first quarter of a season;
# season odds were unchanged (Brier 0.0389). A promoted side that starts with a few big wins
# no longer outranks the champions on six games.
PROMOTED_PRIOR = -0.2
PROMOTED_RIDGE_FACTOR = 6.0
MAX_GOALS = 10
MATCHES_THAT_MATTER = 10
# Team strength drifts through a season (injuries, transfers, managers). Each simulated
# season shifts every team's attack and defence by N(0, (DRIFT * sqrt(share of season left))^2);
# 0.2 gave the best calibrated title/top-four/relegation odds over 18 past league-seasons.
STRENGTH_DRIFT = 0.2


def standings(games: list[Game], teams: list[str], win: int = 3, draw: int = 1) -> dict[str, dict[str, int]]:
    rows = {
        team: {"played": 0, "wins": 0, "draws": 0, "losses": 0, "goalsFor": 0, "goalsAgainst": 0, "points": 0}
        for team in teams
    }
    for game in games:
        if not game.played:
            continue
        for team, scored, conceded in ((game.home, game.home_score, game.away_score), (game.away, game.away_score, game.home_score)):
            row = rows[team]
            row["played"] += 1
            row["goalsFor"] += scored
            row["goalsAgainst"] += conceded
            if scored > conceded:
                row["wins"] += 1
                row["points"] += win
            elif scored == conceded:
                row["draws"] += 1
                row["points"] += draw
            else:
                row["losses"] += 1
    for row in rows.values():
        row["goalDifference"] = row["goalsFor"] - row["goalsAgainst"]
    return rows


# Steps that rank teams level on points, which a config can list under "tiebreak", as the page
# describes them. A head-to-head step builds one mini-table from the games between the teams
# still level (it is not built again for teams it leaves level); "-complete" steps wait until
# those teams have all played each other home and away.
TIEBREAK_STEPS = {
    "goal-difference": "goal difference",
    "goals": "goals scored",
    "wins": "wins",
    "away-wins": "away wins",
    "head-to-head": "head-to-head points, then head-to-head goal difference",
    "head-to-head-complete": "head-to-head points, then head-to-head goal difference (once they have met home and away)",
    "head-to-head-goals-complete": "head-to-head points, goal difference and goals (once they have met home and away)",
}
# Shorthand "tiebreak" names: the default, Portugal, Spain and Italy, and Scotland (SPFL Rule C36:
# goal difference, goals, then the games between the teams still level).
TIEBREAK_RULES = {
    None: ["goal-difference", "goals"],
    "head-to-head": ["head-to-head", "goal-difference", "goals"],
    "head-to-head-complete": ["head-to-head-complete", "goal-difference", "goals"],
    "goals-then-head-to-head": ["goal-difference", "goals", "head-to-head"],
}


def tiebreak_steps(rule: str | list[str] | None) -> list[str]:
    steps = list(rule) if isinstance(rule, list) else TIEBREAK_RULES.get(rule)
    if steps is None or any(step not in TIEBREAK_STEPS for step in steps):
        raise ValueError(f"Unknown football tiebreak {rule!r}; steps are {', '.join(TIEBREAK_STEPS)}")
    return steps


def ranked(rows: dict[str, dict[str, int]], games: list[Game] | None = None, rule: str | list[str] | None = None) -> list[str]:
    """Points, then the league's tiebreak steps (by default goal difference, then goals scored).

    `rule` is a config's "tiebreak": a list of TIEBREAK_STEPS, or "head-to-head" (Portugal),
    which ranks teams level on points by their games against each other first, or
    "head-to-head-complete" (Spain, Italy), which does so once they have met home and away, or
    "goals-then-head-to-head" (Scotland), which uses those games last, for teams also level on
    goal difference and goals. Teams level on every step are listed by name.
    """
    played = [game for game in games or [] if game.played]
    fields = {"points": "points", "goal-difference": "goalDifference", "goals": "goalsFor", "wins": "wins"}

    def values(step: str, group: list[str]) -> dict[str, Any] | None:
        if step in fields:
            return {team: rows[team][fields[step]] for team in group}
        if step == "away-wins":
            return {team: sum(1 for game in played if game.away == team and game.away_score > game.home_score) for team in group}
        members = set(group)
        between = [game for game in played if game.home in members and game.away in members]
        if step.endswith("-complete") and len(between) < len(group) * (len(group) - 1):
            return None
        among = standings(between, group)
        size = 3 if step.startswith("head-to-head-goals") else 2
        return {team: (among[team]["points"], among[team]["goalDifference"], among[team]["goalsFor"])[:size] for team in group}

    def order(group: list[str], steps: list[str]) -> list[str]:
        if len(group) < 2 or not steps:
            return sorted(group)
        found = values(steps[0], group)
        if found is None:
            return order(group, steps[1:])
        ranking = []
        for value in sorted(set(found.values()), reverse=True):
            ranking += order([team for team in group if found[team] == value], steps[1:])
        return ranking

    return order(list(rows), ["points", *tiebreak_steps(rule)])


def tiebreak_note(rule: str | list[str] | None) -> str:
    if isinstance(rule, list) or rule == "goals-then-head-to-head":
        phrases, after_head_to_head = [], False
        for step in tiebreak_steps(rule):
            overall = after_head_to_head and step in ("goal-difference", "goals")
            phrases.append(("overall " if overall else "") + TIEBREAK_STEPS[step])
            after_head_to_head = after_head_to_head or step.startswith("head-to-head")
        return (
            "Teams level on points are ranked by "
            + ", then ".join(phrases)
            + "; simulated seasons separate them by goal difference, then goals scored."
        )
    if rule:
        return (
            "The table ranks teams level on points by their head-to-head points and goal difference, then overall goal "
            "difference; simulated seasons separate them by goal difference, then goals scored."
        )
    return "Teams level on points are separated by goal difference, then goals scored."


def official_adjustments(table: dict[str, dict[str, int]], official: list[dict[str, int]]) -> dict[str, int]:
    """Points deductions, found by matching each team to the official row with the same record.

    Records (played, wins, draws, losses, goals for and against) almost always identify a
    team, so no name matching is needed; ambiguous or missing records are skipped.
    """
    fields = ("played", "wins", "draws", "losses", "goalsFor", "goalsAgainst")
    by_record: dict[tuple[int, ...], list[dict[str, int]]] = {}
    for row in official:
        by_record.setdefault(tuple(row[field] for field in fields), []).append(row)
    ours: dict[tuple[int, ...], list[str]] = {}
    for team, row in table.items():
        ours.setdefault(tuple(row[field] for field in fields), []).append(team)
    adjustments = {}
    for record, teams in ours.items():
        matches = by_record.get(record, [])
        if len(teams) == 1 and len(matches) == 1:
            difference = matches[0]["points"] - table[teams[0]]["points"]
            if difference and abs(difference) <= 30:
                adjustments[teams[0]] = difference
    return adjustments


ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings"


def espn_table(code: str, cache_dir: Path) -> list[dict[str, int]]:
    """The official table as published by ESPN (unofficial API, used only to detect deductions)."""
    import json
    import time

    path = cache_dir / f"espn-{code}.json"
    if not (path.exists() and time.time() - path.stat().st_mtime < 3 * 3600):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(team_sports.get_json(ESPN_STANDINGS_URL.format(code=code))), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - deductions are optional; keep the last copy if any
            if not path.exists():
                raise team_sports.FeedError(f"ESPN standings {code}: {exc}") from exc
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for entry in data["children"][0]["standings"]["entries"]:
        stats = {item["name"]: item.get("value") for item in entry["stats"]}
        rows.append(
            {
                "played": int(stats["gamesPlayed"]),
                "wins": int(stats["wins"]),
                "draws": int(stats["ties"]),
                "losses": int(stats["losses"]),
                "goalsFor": int(stats["pointsFor"]),
                "goalsAgainst": int(stats["pointsAgainst"]),
                "points": int(stats["points"]),
            }
        )
    return rows


@dataclass(frozen=True)
class GoalModel:
    mu: float
    home: float
    attack: dict[str, float]
    defence: dict[str, float]

    def rates(self, home: str, away: str) -> tuple[float, float]:
        home_rate = math.exp(self.mu + self.home + self.attack[home] - self.defence[away])
        away_rate = math.exp(self.mu + self.attack[away] - self.defence[home])
        return home_rate, away_rate

    def outcome(self, home: str, away: str) -> tuple[float, float, float]:
        """Probabilities of a home win, a draw and an away win."""
        home_rate, away_rate = self.rates(home, away)
        goals = np.arange(MAX_GOALS + 1)
        factorials = np.array([math.factorial(k) for k in goals], dtype=float)
        home_p = np.exp(-home_rate) * home_rate ** goals / factorials
        away_p = np.exp(-away_rate) * away_rate ** goals / factorials
        grid = np.outer(home_p, away_p)
        total = grid.sum()
        return float(np.tril(grid, -1).sum() / total), float(np.trace(grid) / total), float(np.triu(grid, 1).sum() / total)


def fit_goal_model(games: list[Game], teams: list[str], promoted: set[str], now: datetime, ridge: float | None = None) -> GoalModel:
    """Penalised, time-weighted Poisson regression fitted with Newton steps."""
    index = {team: i for i, team in enumerate(teams)}
    count = len(teams)
    size = 2 * count + 2  # mu, home, attack[count], defence[count]
    rows, goals, weights = [], [], []
    for game in games:
        if not game.played or game.home not in index or game.away not in index:
            continue
        weight = 0.5 ** (max(0.0, (now - game.date).total_seconds() / 86400) / HALF_LIFE_DAYS)
        if weight < 1e-3:
            continue
        home_row = np.zeros(size)
        home_row[[0, 1, 2 + index[game.home]]] = 1
        home_row[2 + count + index[game.away]] = -1
        away_row = np.zeros(size)
        away_row[[0, 2 + index[game.away]]] = 1
        away_row[2 + count + index[game.home]] = -1
        rows += [home_row, away_row]
        goals += [game.home_score, game.away_score]
        weights += [weight, weight]

    prior = np.zeros(size)
    penalty = np.zeros(size)
    penalty[2:] = RIDGE if ridge is None else ridge
    for team in promoted & set(index):
        for offset in (2, 2 + count):
            prior[offset + index[team]] = PROMOTED_PRIOR
            penalty[offset + index[team]] *= PROMOTED_RIDGE_FACTOR
    theta = prior.copy()
    theta[0] = math.log(1.35)
    if rows:
        design, observed, weight = np.array(rows), np.array(goals, dtype=float), np.array(weights)
        for _ in range(30):
            rate = np.exp(design @ theta)
            gradient = design.T @ (weight * (observed - rate)) - penalty * (theta - prior)
            hessian = (design * (weight * rate)[:, None]).T @ design + np.diag(penalty)
            step = np.linalg.solve(hessian, gradient)
            theta += step
            if np.abs(step).max() < 1e-7:
                break
    return GoalModel(
        mu=float(theta[0]),
        home=float(theta[1]),
        attack={team: float(theta[2 + i]) for team, i in index.items()},
        defence={team: float(theta[2 + count + i]) for team, i in index.items()},
    )


def simulate(
    model: GoalModel,
    teams: list[str],
    table: dict[str, dict[str, int]],
    remaining: list[Game],
    tiers: list[dict[str, Any]],
    points: dict[str, int],
    simulations: int = SIMULATIONS,
    seed: int = SEED,
    season_left: float = 1.0,
    split: football_split.Split | None = None,
) -> dict[str, Any]:
    count = len(teams)
    index = {team: i for i, team in enumerate(teams)}
    base_points = np.array([table[team]["points"] for team in teams], dtype=np.float32)
    base_for = np.array([table[team]["goalsFor"] for team in teams], dtype=np.float32)
    base_against = np.array([table[team]["goalsAgainst"] for team in teams], dtype=np.float32)
    rng = np.random.default_rng(seed)
    # A league that splits in two also plays the post-split games that are not in the feed yet.
    real = len(remaining)
    remaining = remaining + (split.games if split else [])
    sections = football_split.known_sections(split, teams)

    if remaining:
        log_rates = np.log(np.array([model.rates(game.home, game.away) for game in remaining]))
        home_index = np.array([index[game.home] for game in remaining])
        away_index = np.array([index[game.away] for game in remaining])
        scale = STRENGTH_DRIFT * math.sqrt(min(max(season_left, 0.0), 1.0))
        attack_shift = rng.normal(0.0, scale, (simulations, count))
        defence_shift = rng.normal(0.0, scale, (simulations, count))
        home_rates = np.exp(log_rates[:, 0] + attack_shift[:, home_index] - defence_shift[:, away_index])
        away_rates = np.exp(log_rates[:, 1] + attack_shift[:, away_index] - defence_shift[:, home_index])
        home_goals = rng.poisson(home_rates).astype(np.float32)
        away_goals = rng.poisson(away_rates).astype(np.float32)
        del home_rates, away_rates, attack_shift, defence_shift
        home_side = np.zeros((len(remaining), count), dtype=np.float32)
        away_side = np.zeros((len(remaining), count), dtype=np.float32)
        home_side[np.arange(len(remaining)), [index[game.home] for game in remaining]] = 1
        away_side[np.arange(len(remaining)), [index[game.away] for game in remaining]] = 1
        win, draw = points["win"], points["draw"]
        home_points = np.where(home_goals > away_goals, win, np.where(home_goals == away_goals, draw, 0)).astype(np.float32)
        away_points = np.where(away_goals > home_goals, win, np.where(home_goals == away_goals, draw, 0)).astype(np.float32)
        if split and sections is None:
            sections = football_split.split_each_season(
                split, teams, real, (base_points, base_for, base_against), (home_goals, away_goals), (home_points, away_points), (home_side, away_side), rng
            )
        final_points = base_points + home_points @ home_side + away_points @ away_side
        goals_for = base_for + home_goals @ home_side + away_goals @ away_side
        goals_against = base_against + away_goals @ home_side + home_goals @ away_side
    else:
        simulations = 1
        home_goals = away_goals = np.zeros((1, 0), dtype=np.float32)
        final_points, goals_for, goals_against = base_points[None, :], base_for[None, :], base_against[None, :]

    # Points, then goal difference, then goals scored; remaining ties are broken at random.
    keys = (
        final_points.astype(np.float64) * 1e6
        + (goals_for - goals_against + 1000).astype(np.float64) * 1e3
        + goals_for
        + rng.random(final_points.shape)
    )
    if sections is not None:
        # Nobody leaves their section: the top six take places 1-6 whatever their points.
        keys -= sections * 1e9
    positions = team_sports.positions_from_keys(keys)
    flags = {tier["key"]: team_sports.tier_flags(positions, tier, count) for tier in tiers}

    probabilities = {
        team: {key: round(float(flag[:, i].mean()) * 100, 2) for key, flag in flags.items()}
        for team, i in index.items()
    }
    position_odds = {
        team: [round(value * 100, 2) for value in np.bincount(positions[:, i], minlength=count) / simulations]
        for team, i in index.items()
    }
    expected = {
        team: {"points": round(float(final_points[:, i].mean()), 1), "position": round(float(positions[:, i].mean()) + 1, 1)}
        for team, i in index.items()
    }
    return {
        "simulations": simulations,
        "probabilities": probabilities,
        "positions": position_odds,
        "expected": expected,
        "matchesThatMatter": matches_that_matter(remaining[:real], home_goals, away_goals, flags, tiers, teams),
    }


def matches_that_matter(
    remaining: list[Game],
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    flags: dict[str, np.ndarray],
    tiers: list[dict[str, Any]],
    teams: list[str],
) -> list[dict[str, Any]]:
    """Upcoming matches whose result moves one team's chances the most."""
    upcoming = sorted(range(len(remaining)), key=lambda i: remaining[i].date)[:MATCHES_THAT_MATTER]
    labels = {tier["key"]: tier["label"] for tier in tiers}
    found = []
    for column in upcoming:
        outcomes = {
            "home": home_goals[:, column] > away_goals[:, column],
            "draw": home_goals[:, column] == away_goals[:, column],
            "away": home_goals[:, column] < away_goals[:, column],
        }
        best = None
        for key, flag in flags.items():
            chances = {name: flag[mask].mean(axis=0) for name, mask in outcomes.items() if mask.sum() >= 200}
            if len(chances) < 2:
                continue
            stacked = np.vstack(list(chances.values()))
            swings = stacked.max(axis=0) - stacked.min(axis=0)
            team = int(swings.argmax())
            if best is None or swings[team] > best[0]:
                best = (float(swings[team]), key, team, {name: float(value[team]) for name, value in chances.items()})
        if best and best[0] >= 0.01:
            swing, key, team, chances = best
            game = remaining[column]
            found.append(
                {
                    "fixtureId": game.id,
                    "date": iso(game.date),
                    "home": game.home,
                    "away": game.away,
                    "tier": key,
                    "tierLabel": labels[key],
                    "team": teams[team],
                    "swing": round(swing * 100, 1),
                    **{
                        f"if{name.title()}": round(chances[name] * 100, 1) if name in chances else None
                        for name in ("home", "draw", "away")
                    },
                }
            )
    return sorted(found, key=lambda item: -item["swing"])


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payload(config: dict[str, Any], now: datetime, cache_dir: Path) -> dict[str, Any]:
    season = team_sports.resolve_season(config, now)
    games = team_sports.fetch_games(season.feed, cache_dir)
    warnings: list[str] = []
    previous_season = team_sports.resolve_season(config, now, offset=-1)
    # A league whose feed starts with this season ("firstYear") has no earlier results to fetch.
    first_season = previous_season.year < config["season"].get("firstYear", previous_season.year)
    previous_games = []
    if not first_season:
        try:
            previous_games = team_sports.fetch_games(previous_season.feed, cache_dir, max_age_hours=24 * 30)
        except team_sports.FeedError as exc:
            warnings.append(f"Previous season unavailable ({exc}); ratings use this season only.")

    teams = sorted({game.home for game in games} | {game.away for game in games})
    previous_teams = {game.home for game in previous_games} | {game.away for game in previous_games}
    points = {"win": config.get("points", {}).get("win", 3), "draw": config.get("points", {}).get("draw", 1)}
    table = standings(games, teams, **points)
    # Points deductions (financial or disciplinary) only show in the official table.
    adjustments: dict[str, int] = {}
    official_code = config.get("sources", {}).get("espn")
    if official_code:
        try:
            adjustments = official_adjustments(table, espn_table(official_code, cache_dir))
        except (team_sports.FeedError, KeyError, IndexError, ValueError, TypeError) as exc:
            print(f"{season.payload_id}: deductions not checked ({exc})")
    for team, change in adjustments.items():
        table[team]["points"] += change
        table[team]["adjustment"] = change
    order = ranked(table, games, config.get("tiebreak"))
    split = None
    if config.get("split"):

        def split_order(subset: list[Game]) -> list[str]:
            rows = standings(subset, teams, **points)
            for team, change in adjustments.items():
                rows[team]["points"] += change
            return ranked(rows, subset, config.get("tiebreak"))

        split = football_split.plan(config["split"], games, teams, split_order)
        if split.sections is not None:
            order.sort(key=split.sections.get)
    meta = team_sports.team_meta(config, teams)

    model_teams = sorted(set(teams) | previous_teams)
    promoted = set(teams) - previous_teams if previous_teams else set()
    # Weights decay from the latest result rather than from today, so ratings only change when results do.
    latest = max((game.date for game in previous_games + games if game.played), default=now)
    model = fit_goal_model(previous_games + games, model_teams, promoted, min(latest, now), FIRST_SEASON_RIDGE if first_season else None)
    remaining = [game for game in games if not game.played]
    # A past kick-off without a score is postponed or not yet updated at the source.
    pending = [game for game in remaining if game.date < now - timedelta(hours=6)]
    if pending:
        warnings.append(
            f"{len(pending)} past fixture{'s have' if len(pending) > 1 else ' has'} no result yet "
            f"(postponed, or not yet updated at {team_sports.FEED_SOURCE}); they are simulated as still to play."
        )
    tiers = football_split.settled_tiers(config["tiers"], split)
    # Post-split games not in the feed yet are still to play.
    missing = split.missing if split else 0
    simulation = simulate(
        model, teams, table, remaining, tiers, points, season_left=(len(remaining) + missing) / (len(games) + missing), split=split
    )

    standings_rows = []
    for rank, team in enumerate(order, start=1):
        row = table[team]
        standings_rows.append(
            {
                "teamKey": team,
                "shortName": meta[team]["shortName"],
                "fullName": meta[team]["fullName"],
                "rank": rank,
                **row,
                "form": team_sports.form_strings(games, team),
                "remaining": sum(1 for game in remaining if team in (game.home, game.away)),
            }
        )

    fixtures = []
    for game in sorted(remaining, key=lambda item: item.date):
        home, draw, away = model.outcome(game.home, game.away)
        fixtures.append(
            {
                "id": game.id,
                "round": game.round,
                "date": iso(game.date),
                "home": game.home,
                "away": game.away,
                "venue": game.venue,
                "probabilities": {"home": round(home, 3), "draw": round(draw, 3), "away": round(away, 3)},
            }
        )
    results = [
        {
            "id": game.id,
            "round": game.round,
            "date": iso(game.date),
            "home": game.home,
            "away": game.away,
            "homeScore": game.home_score,
            "awayScore": game.away_score,
        }
        for game in [game for game in games if game.played][::-1]
    ]

    return {
        "metadata": {
            "season": season.label,
            "generated_at": iso(now),
            "source": team_sports.FEED_SOURCE,
            "source_url": team_sports.FEED_SOURCE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": "complete" if not remaining and not missing else "in_progress",
            "warnings": warnings,
        },
        "league": {
            "id": season.payload_id,
            "configId": config["id"],
            "sport": "football",
            "name": config["name"],
            "shortName": config["shortName"],
            "season": season.label,
            "seasonLabel": season.label,
            "priority": config.get("priority", 100),
            "tiers": tiers,
            "columns": [
                {"key": "played", "label": "P"},
                {"key": "wins", "label": "W"},
                {"key": "draws", "label": "D"},
                {"key": "losses", "label": "L"},
                {"key": "goalDifference", "label": "GD", "signed": True},
                {"key": "points", "label": "Pts", "strong": True},
            ],
            "outcomes": ["home", "draw", "away"],
            "teams": [meta[team] for team in teams],
            **({"cutoffs": football_split.cutoffs(split, len(teams))} if split else {}),
            **({"headline": config["headline"]} if config.get("headline") else {}),
        },
        "standings": standings_rows,
        "fixtures": fixtures,
        "results": results,
        "analysis": {
            "method": "Monte Carlo",
            "simulations": simulation["simulations"],
            "model": "Poisson goals model",
            "modelNotes": [
                f"Each remaining match is simulated {SIMULATIONS:,} times from a Poisson goals model: team attack and "
                f"defence ratings plus home advantage, fitted on {'this season' if first_season else 'this and last season'} "
                f"with a {HALF_LIFE_DAYS}-day half-life.",
                *(
                    [
                        f"{team_sports.FEED_SOURCE} has no {config['name']} season before {season.label}, so every team, "
                        "promoted or relegated, started this season from the same average rating, and ratings are held "
                        "closer to it than usual (backtests without a previous season scored better that way)."
                    ]
                    if first_season
                    else []
                ),
                "Every simulated season also lets team strength drift (more when more of the season is left), because "
                "form, injuries and transfers change teams; without it, early-season odds were overconfident in backtests.",
                tiebreak_note(config.get("tiebreak")),
                *(football_split.notes(config["split"], split) if split else []),
                *(
                    [
                        "Points deductions in the official table: "
                        + ", ".join(f"{meta[team]['fullName']} {change:+d}" for team, change in sorted(adjustments.items()))
                        + "."
                    ]
                    if adjustments
                    else []
                ),
                "Backtested on 2025-26 in five leagues: match predictions score 0.20-0.21 (ranked probability score) "
                "against 0.22-0.23 for home/draw/away base rates; season odds were calibrated on 18 league-seasons since 2022-23.",
                *config.get("notes", []),
            ],
            "probabilities": simulation["probabilities"],
            "positions": simulation["positions"],
            "expected": simulation["expected"],
            "ratings": {
                team: {"attack": round(model.attack[team], 3), "defence": round(model.defence[team], 3)} for team in teams
            },
        },
        "matchesThatMatter": simulation["matchesThatMatter"],
    }
