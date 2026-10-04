"""Formula 1: the drivers' and constructors' championships, with title odds.

Data comes from the Jolpica F1 API (https://api.jolpi.ca/ergast/f1/, the Ergast
successor): no key, and every download is cached so a failed refresh falls back to
the last good copy. The championship tables are computed from the race and sprint
results with the FIA points system and countback (race places only), then checked
against Jolpica's published standings.

Pace comes from a rank-ordered logit (Plackett-Luce) fitted on finishing orders:
each driver's strength is their own skill plus their car's, the car being rated
per team and season. Retirements are modelled separately as a per-driver DNF chance.
The rest of the season is then simulated race by race and sprint by sprint.
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import requests

import team_sports


API_URL = "https://api.jolpi.ca/ergast/f1"
SOURCE = "Jolpica F1 API"
SOURCE_URL = "https://github.com/jolpica/jolpica-f1"
PAGE_LIMIT = 100
# Jolpica allows 4 requests a second and 500 an hour; stay well inside both.
REQUEST_GAP_SECONDS = 0.35
HOURLY_BUDGET = 450
_request_times: deque[float] = deque()


# --- Downloads ----------------------------------------------------------------------------


def _throttle() -> None:
    now = time.monotonic()
    while _request_times and now - _request_times[0] > 3600:
        _request_times.popleft()
    if len(_request_times) >= HOURLY_BUDGET:
        raise team_sports.FeedError(f"{SOURCE}: hourly request budget used up")
    if _request_times:
        wait = REQUEST_GAP_SECONDS - (now - _request_times[-1])
        if wait > 0:
            time.sleep(wait)
    _request_times.append(time.monotonic())


def _get_page(url: str) -> dict[str, Any]:
    _throttle()
    data = team_sports.get_json(url)
    if not isinstance(data, dict) or "MRData" not in data:
        raise team_sports.FeedError(f"{SOURCE}: unexpected response from {url}")
    return data["MRData"]


def _download(season: int, endpoint: str) -> dict[str, Any]:
    """Every page of a season endpoint (results, sprint, races, ...), merged into one table."""
    pages = []
    offset = 0
    while True:
        page = _get_page(f"{API_URL}/{season}/{endpoint}/?format=json&limit={PAGE_LIMIT}&offset={offset}")
        pages.append(page)
        offset += PAGE_LIMIT
        if offset >= int(page.get("total", 0)):
            break
    return _merge_pages(pages)


def _merge_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Pages split a race's results (or a standings list) across page boundaries; join them up."""
    first = pages[0]
    table_key = next(key for key in first if key.endswith("Table"))
    list_key = "StandingsLists" if table_key == "StandingsTable" else "Races"
    merged: dict[str, dict[str, Any]] = {}
    for page in pages:
        for item in page[table_key].get(list_key, []):
            key = f"{item.get('season')}-{item.get('round')}"
            if key not in merged:
                merged[key] = json.loads(json.dumps(item))
                continue
            for field_name, value in item.items():
                if isinstance(value, list):
                    merged[key].setdefault(field_name, []).extend(value)
    return {"total": first.get("total"), list_key: list(merged.values())}


def fetch_season(season: int, endpoint: str, cache_dir: Path, max_age_hours: float = 3) -> dict[str, Any]:
    """A season endpoint, cached under ``cache_dir/jolpica``; a failed refresh uses the cached copy."""
    path = cache_dir / "jolpica" / f"{season}-{endpoint}.json"
    fresh = path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600
    if not fresh:
        try:
            data = _download(season, endpoint)
            if endpoint in ("results", "sprint") and path.exists() and len(data.get("Races", [])) < len(json.loads(path.read_text(encoding="utf-8")).get("Races", [])):
                # A season never loses results (the calendar can lose a race): a short answer is a source problem.
                raise team_sports.FeedError("fewer events with results than the cached copy")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (requests.RequestException, ValueError, KeyError, StopIteration, team_sports.FeedError) as exc:
            if not path.exists():
                raise team_sports.FeedError(f"{SOURCE} {season} {endpoint}: {exc}") from exc
            print(f"{SOURCE} {season} {endpoint}: using the cached copy ({exc})")
    return json.loads(path.read_text(encoding="utf-8"))


# --- Parsed data --------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One car in a race or sprint classification."""

    driver: str
    constructor: str
    # Order in the published classification, unclassified cars included (1 = winner).
    order: int
    # Finishing position when classified ("1", "17"); None for R, D, E, W, F, N.
    position: int | None
    position_text: str
    status: str
    # Points as published, for cross-checks.
    points: float
    grid: int | None = None
    fastest_lap_rank: int | None = None

    @property
    def classified(self) -> bool:
        return self.position is not None

    @property
    def started(self) -> bool:
        return self.position_text not in ("W", "F") and self.status not in ("Did not start", "Withdrew", "Did not qualify", "Not qualified")

    @property
    def finished(self) -> bool:
        """Saw the flag: classified, and running at the end (a car that retired late can still be classified)."""
        return self.classified and (self.status in ("Finished", "Lapped") or self.status.startswith("+"))

    @property
    def retired(self) -> bool:
        """Started but did not finish; disqualifications are not retirements."""
        return self.started and not self.finished and self.position_text not in ("D", "E")


@dataclass(frozen=True)
class Event:
    """A race or a sprint with its classification (empty until run)."""

    season: int
    round: int
    kind: str  # "race" or "sprint"
    name: str
    date: datetime
    entries: tuple[Entry, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.season}-{self.round:02d}-{self.kind}"

    @property
    def done(self) -> bool:
        return bool(self.entries)


@dataclass(frozen=True)
class Person:
    id: str
    code: str
    given_name: str
    family_name: str
    number: str | None = None

    @property
    def name(self) -> str:
        return f"{self.given_name} {self.family_name}"


@dataclass
class SeasonData:
    season: int
    events: list[Event]
    drivers: dict[str, Person] = field(default_factory=dict)
    constructors: dict[str, str] = field(default_factory=dict)
    # Weekend details for the page: round -> {name, circuit, locality, country}.
    weekends: dict[int, dict[str, str]] = field(default_factory=dict)


def _when(day: str | None, clock: str | None) -> datetime | None:
    if not day:
        return None
    return datetime.fromisoformat(f"{day}T{(clock or '12:00:00Z').replace('Z', '')}").replace(tzinfo=timezone.utc)


def _int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def parse_entries(rows: Iterable[dict[str, Any]], drivers: dict[str, Person], constructors: dict[str, str]) -> tuple[Entry, ...]:
    entries = []
    for row in rows:
        driver = row["Driver"]
        driver_id = driver["driverId"]
        drivers[driver_id] = Person(
            id=driver_id,
            code=driver.get("code") or driver.get("familyName", driver_id)[:3].upper(),
            given_name=driver.get("givenName", ""),
            family_name=driver.get("familyName", driver_id),
            number=driver.get("permanentNumber") or row.get("number"),
        )
        constructor = row["Constructor"]
        constructors[constructor["constructorId"]] = constructor.get("name", constructor["constructorId"])
        text = str(row.get("positionText", ""))
        status = row.get("status", "")
        # Older seasons list a disqualified car with a number ("19") and the status only.
        disqualified = status in ("Disqualified", "Excluded")
        entries.append(
            Entry(
                driver=driver_id,
                constructor=constructor["constructorId"],
                order=_int(row.get("position")) or len(entries) + 1,
                position=int(text) if text.isdigit() and not disqualified else None,
                position_text="D" if disqualified else text,
                status=status,
                points=float(row.get("points", 0) or 0),
                grid=_int(row.get("grid")),
                fastest_lap_rank=_int((row.get("FastestLap") or {}).get("rank")),
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.order))


def parse_season(season: int, schedule: dict[str, Any], results: dict[str, Any], sprints: dict[str, Any]) -> SeasonData:
    """Races and sprints of a season in date order, with results where they exist."""
    drivers: dict[str, Person] = {}
    constructors: dict[str, str] = {}
    race_results = {int(race["round"]): race.get("Results", []) for race in results.get("Races", [])}
    sprint_results = {int(race["round"]): race.get("SprintResults", []) for race in sprints.get("Races", [])}
    events: list[Event] = []
    weekends: dict[int, dict[str, str]] = {}
    rounds = {int(race["round"]): race for race in schedule.get("Races", [])}
    # Results of a round missing from the schedule still count.
    for round_number in sorted(set(rounds) | set(race_results) | set(sprint_results)):
        race = rounds.get(round_number) or next(item for item in results.get("Races", []) + sprints.get("Races", []) if int(item["round"]) == round_number)
        circuit = race.get("Circuit") or {}
        location = circuit.get("Location") or {}
        weekends[round_number] = {
            "name": race.get("raceName", f"Round {round_number}"),
            "circuit": circuit.get("circuitName", ""),
            "locality": location.get("locality", ""),
            "country": location.get("country", ""),
        }
        race_date = _when(race.get("date"), race.get("time"))
        sprint_block = race.get("Sprint")
        if round_number in sprint_results or sprint_block:
            sprint_date = _when((sprint_block or {}).get("date"), (sprint_block or {}).get("time")) or (race_date - timedelta(days=1))
            events.append(
                Event(season, round_number, "sprint", weekends[round_number]["name"], sprint_date, parse_entries(sprint_results.get(round_number, []), drivers, constructors))
            )
        events.append(Event(season, round_number, "race", weekends[round_number]["name"], race_date, parse_entries(race_results.get(round_number, []), drivers, constructors)))
    events.sort(key=lambda event: (event.date, event.round, event.kind != "sprint"))
    return SeasonData(season=season, events=events, drivers=drivers, constructors=constructors, weekends=weekends)


def load_season(season: int, cache_dir: Path, current: bool) -> SeasonData:
    """A season's schedule, race and sprint results; a past season is refreshed monthly."""
    max_age = 3 if current else 24 * 30
    schedule = fetch_season(season, "races", cache_dir, max_age)
    results = fetch_season(season, "results", cache_dir, max_age)
    sprints = fetch_season(season, "sprint", cache_dir, max_age)
    return parse_season(season, schedule, results, sprints)


# --- Championship tables ------------------------------------------------------------------


@dataclass(frozen=True)
class PointsRules:
    """The FIA points system (2026 Formula 1 Regulations, Section A, Article A2.2)."""

    race: tuple[float, ...] = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)
    sprint: tuple[float, ...] = (8, 7, 6, 5, 4, 3, 2, 1)
    # A point for the fastest lap, to a classified driver in the top ten (2019-2024 only).
    fastest_lap: float = 0.0
    fastest_lap_max_position: int = 10

    @classmethod
    def from_config(cls, config: dict[str, Any], season: int) -> "PointsRules":
        points = config.get("points") or {}
        fastest = points.get("fastestLap") or {}
        first, last = fastest.get("seasons", [0, -1])
        return cls(
            race=tuple(points.get("race", cls.race)),
            sprint=tuple(points.get("sprint", cls.sprint)),
            fastest_lap=float(fastest.get("points", 0)) if first <= season <= last else 0.0,
            fastest_lap_max_position=int(fastest.get("maxPosition", 10)),
        )

    def table(self, kind: str) -> tuple[float, ...]:
        return self.race if kind == "race" else self.sprint

    def points(self, event: Event, entry: Entry) -> float:
        if not entry.classified:
            return 0.0
        table = self.table(event.kind)
        value = table[entry.position - 1] if entry.position <= len(table) else 0.0
        if event.kind == "race" and self.fastest_lap and entry.fastest_lap_rank == 1 and entry.position <= self.fastest_lap_max_position:
            value += self.fastest_lap
        return float(value)


@dataclass
class Row:
    key: str
    points: float = 0.0
    # Grand Prix wins and podiums; sprints are counted apart and are not in the countback.
    wins: int = 0
    podiums: int = 0
    sprint_wins: int = 0
    starts: int = 0
    places: dict[int, int] = field(default_factory=dict)

    def countback(self) -> tuple[int, ...]:
        """Race places, best first: most wins, then most second places, and so on (Article A2.1.4 c)."""
        return tuple(self.places.get(place, 0) for place in range(1, max(max(self.places, default=0), 30) + 1))


def ranked_keys(rows: dict[str, Row]) -> list[str]:
    """Points, then the countback of race places. Anything still level stays in key order."""
    return sorted(rows, key=lambda key: (-rows[key].points, tuple(-count for count in rows[key].countback()), key))


def event_points(event: Event, rules: PointsRules) -> tuple[dict[int, float], bool]:
    """Points per entry (by index) under the rules, or as published when they differ.

    A race stopped early scores on a reduced scale (Article A2.2.1) that the results do not
    describe, so a published total that disagrees with the full scale is taken as it is.
    """
    computed = {index: rules.points(event, entry) for index, entry in enumerate(event.entries)}
    published = {index: entry.points for index, entry in enumerate(event.entries)}
    if all(abs(computed[index] - published[index]) < 1e-9 for index in computed):
        return computed, False
    return published, True


def championship(events: Iterable[Event], rules: PointsRules) -> tuple[dict[str, Row], dict[str, Row], list[Event]]:
    """Drivers' and constructors' tables from the finished events, and the events scored as published."""
    drivers: dict[str, Row] = {}
    constructors: dict[str, Row] = {}
    as_published = []
    for event in events:
        if not event.done:
            continue
        points, published = event_points(event, rules)
        if published:
            as_published.append(event)
        for index, entry in enumerate(event.entries):
            for rows, key in ((drivers, entry.driver), (constructors, entry.constructor)):
                row = rows.setdefault(key, Row(key))
                row.points += points[index]
                if event.kind == "sprint":
                    row.sprint_wins += int(entry.position == 1)
                    continue
                row.starts += int(entry.started)
                if entry.classified:
                    row.places[entry.position] = row.places.get(entry.position, 0) + 1
                    row.wins += int(entry.position == 1)
                    row.podiums += int(entry.position <= 3)
    return drivers, constructors, as_published


def published_standings(data: dict[str, Any], kind: str) -> tuple[int | None, list[dict[str, Any]]]:
    """Jolpica's driver or constructor standings: the round they follow and the rows in order."""
    lists = data.get("StandingsLists") or []
    if not lists:
        return None, []
    latest = max(lists, key=lambda item: int(item.get("round", 0)))
    rows = []
    for item in latest.get("DriverStandings" if kind == "drivers" else "ConstructorStandings", []):
        key = item["Driver"]["driverId"] if kind == "drivers" else item["Constructor"]["constructorId"]
        rows.append({"key": key, "position": _int(item.get("position")), "points": float(item.get("points", 0)), "wins": _int(item.get("wins")) or 0})
    return int(latest.get("round", 0)), rows


def standings_differences(rows: dict[str, Row], order: list[str], published: list[dict[str, Any]]) -> list[str]:
    """Where the computed table disagrees with the published one: points, wins or order."""
    problems = []
    published_keys = [item["key"] for item in published]
    for item in published:
        row = rows.get(item["key"])
        if row is None:
            problems.append(f"{item['key']} is in the published standings but has no results")
        elif abs(row.points - item["points"]) > 1e-9 or row.wins != item["wins"]:
            problems.append(f"{item['key']}: {row.points:g} pts, {row.wins} wins; published {item['points']:g} pts, {item['wins']} wins")
    extra = sorted(set(rows) - set(published_keys))
    if extra:
        problems.append(f"no published standing for {', '.join(extra)}")
    if not problems and order != published_keys:
        problems.append("order differs: " + ", ".join(f"{a}/{b}" for a, b in zip(order, published_keys) if a != b))
    return problems


# --- Pace model ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelSettings:
    """Pace and reliability model settings, chosen by backtesting 2022-2025 (scripts/backtest_formula1.py)."""

    # Results lose half their weight every this many days (120 scored best of 45-365).
    half_life_days: float = 120.0
    # Ridge penalties: driver skill toward the field average (barely: 0.05 scored best), a car
    # toward its prior.
    skill_ridge: float = 0.05
    car_ridge: float = 1.0
    # Share of a team's car rating carried into the next season, and into a season of new rules.
    # Both barely moved the backtest (by 0.001 and 0.007 in log loss); the best values are kept.
    carryover: float = 0.4
    carryover_new_rules: float = 0.15
    # Sprints count for this much of a race in the fit: a tenth scored best on Grand Prix winners.
    sprint_weight: float = 0.1
    # Seasons fitted: this one and the one before.
    history_seasons: int = 2
    # Weight (in starts) of the team and field retirement rates behind a driver's own. 0.5 scored
    # 0.002 better; 3 keeps a driver with no retirements yet from an almost-zero chance of one.
    dnf_prior: float = 3.0
    # How far a car's rating (development, upgrades) and a driver's (form) wander over a whole season,
    # chosen on the season odds at 25%, 50% and 75% of 2022-2025.
    drift: float = 1.5
    driver_drift: float = 0.25


@dataclass
class PaceModel:
    season: int
    skill: dict[str, float]
    car: dict[tuple[str, int], float]
    # Chance of retiring from a race, per driver; sprints scale it by sprint_dnf_factor.
    dnf: dict[str, float]
    field_dnf: float
    sprint_dnf_factor: float
    carryover: float
    predecessors: dict[str, str] = field(default_factory=dict)

    def car_rating(self, team: str, season: int | None = None) -> float:
        season = self.season if season is None else season
        if (team, season) in self.car:
            return self.car[(team, season)]
        before = self.predecessors.get(team, team)
        for candidate in (team, before):
            if (candidate, season - 1) in self.car:
                return self.carryover * self.car[(candidate, season - 1)]
        return 0.0

    def strength(self, driver: str, team: str) -> float:
        return self.skill.get(driver, 0.0) + self.car_rating(team)

    def retirement(self, driver: str, kind: str = "race") -> float:
        rate = self.dnf.get(driver, self.field_dnf)
        return rate * (self.sprint_dnf_factor if kind == "sprint" else 1.0)


def _event_weights(events: list[Event], reference: datetime, settings: ModelSettings) -> np.ndarray:
    ages = np.array([max(0.0, (reference - event.date).total_seconds() / 86400) for event in events])
    kinds = np.array([settings.sprint_weight if event.kind == "sprint" else 1.0 for event in events])
    return kinds * 0.5 ** (ages / settings.half_life_days)


def fit_model(
    events: list[Event],
    season: int,
    settings: ModelSettings = ModelSettings(),
    new_rules: Iterable[int] = (),
    predecessors: dict[str, str] | None = None,
    reference: datetime | None = None,
    teams: Iterable[str] = (),
) -> PaceModel:
    """Penalised, time-weighted Plackett-Luce fit of finishing orders, by Newton's method.

    A classified driver's strength is skill(driver) + car(team, season); the chance of finishing
    ahead of the rest of the cars still in the ranking is exp(strength) over their sum. Cars that
    retired are left out of that event's ranking and count toward the retirement rates instead.
    Each season's car is pulled toward the previous season's car times ``carryover`` (less after a
    change of rules), drivers toward the field average.
    """
    predecessors = predecessors or {}
    new_rules = set(new_rules)
    used = [event for event in events if event.done and event.season > season - settings.history_seasons and event.season <= season]
    reference = reference or max((event.date for event in used), default=datetime(season, 1, 1, tzinfo=timezone.utc))
    drivers = sorted({entry.driver for event in used for entry in event.entries})
    team_seasons = sorted({(entry.constructor, event.season) for event in used for entry in event.entries} | {(team, season) for team in teams})
    driver_index = {driver: i for i, driver in enumerate(drivers)}
    car_index = {key: len(drivers) + i for i, key in enumerate(team_seasons)}
    size = len(drivers) + len(team_seasons)

    # Prior: ridge on skills, and each car toward carryover x its predecessor's car.
    prior = np.zeros((size, size))
    prior[np.arange(len(drivers)), np.arange(len(drivers))] = settings.skill_ridge
    for (team, year), index in car_index.items():
        rho = settings.carryover_new_rules if year in new_rules else settings.carryover
        previous = car_index.get((team, year - 1)) or car_index.get((predecessors.get(team, ""), year - 1))
        vector = np.zeros(size)
        vector[index] = 1.0
        if previous is not None:
            vector[previous] = -rho
        prior += settings.car_ridge * np.outer(vector, vector)

    rankings = [[entry for entry in event.entries if entry.finished] for event in used]
    keep = [i for i, ranking in enumerate(rankings) if len(ranking) > 1]
    theta = np.zeros(size)
    if keep:
        width = max(len(rankings[i]) for i in keep)
        count = len(keep)
        driver_cols = np.zeros((count, width), dtype=int)
        car_cols = np.zeros((count, width), dtype=int)
        valid = np.zeros((count, width), dtype=bool)
        for row, i in enumerate(keep):
            for column, entry in enumerate(rankings[i]):
                driver_cols[row, column] = driver_index[entry.driver]
                car_cols[row, column] = car_index[(entry.constructor, used[i].season)]
                valid[row, column] = True
        weights = _event_weights([used[i] for i in keep], reference, settings)[:, None]
        lower = np.minimum.outer(np.arange(width), np.arange(width))
        pairs = [(a, b) for a in (driver_cols, car_cols) for b in (driver_cols, car_cols)]

        def evaluate(theta: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
            """Penalised log-likelihood, its gradient and Hessian."""
            strength = np.where(valid, theta[driver_cols] + theta[car_cols], -np.inf)
            top = strength.max(axis=1, keepdims=True)
            ex = np.where(valid, np.exp(strength - top), 0.0)
            # remaining[k]: the sum over the cars still in the ranking at stage k.
            remaining = np.cumsum(ex[:, ::-1], axis=1)[:, ::-1]
            safe = np.where(valid, remaining, 1.0)
            loglik = float((np.where(valid, strength - top - np.log(safe), 0.0) * weights).sum())
            inverse = np.where(valid, 1.0 / safe, 0.0)
            a_sum = np.cumsum(inverse, axis=1)
            b_sum = np.cumsum(inverse**2, axis=1)
            gradient_s = np.where(valid, 1.0 - ex * a_sum, 0.0) * weights
            hessian_s = ex[:, :, None] * ex[:, None, :] * b_sum[:, lower]
            hessian_s[:, np.arange(width), np.arange(width)] -= ex * a_sum
            hessian_s *= (valid[:, :, None] & valid[:, None, :]) * weights[:, :, None]
            gradient = np.bincount(driver_cols.ravel(), gradient_s.ravel(), minlength=size) + np.bincount(car_cols.ravel(), gradient_s.ravel(), minlength=size)
            hessian = np.zeros(size * size)
            for rows_index, cols_index in pairs:
                flat = (rows_index[:, :, None] * size + cols_index[:, None, :]).ravel()
                hessian += np.bincount(flat, hessian_s.ravel(), minlength=size * size)
            return (
                loglik - 0.5 * float(theta @ prior @ theta),
                gradient - prior @ theta,
                hessian.reshape(size, size) - prior,
            )

        # Damped Newton: the objective is concave, but a full step can overshoot from far away.
        objective, gradient, hessian = evaluate(theta)
        for _ in range(100):
            step = np.linalg.solve(hessian, gradient)
            scale = 1.0
            while True:
                candidate = theta - scale * step
                result = evaluate(candidate)
                if result[0] >= objective - 1e-10 or scale < 1e-6:
                    break
                scale /= 2
            theta = candidate
            objective, gradient, hessian = result
            if np.abs(scale * step).max() < 1e-8:
                break

    # Retirement rates: field, then team, then driver, each shrunk toward the level above.
    weights_all = _event_weights(used, reference, settings) if used else np.array([])
    field_counts = {"race": [0.0, 0.0], "sprint": [0.0, 0.0]}
    team_counts: dict[str, list[float]] = {}
    driver_counts: dict[str, list[float]] = {}
    latest_team: dict[str, str] = {}
    for event, weight in zip(used, weights_all):
        for entry in event.entries:
            if not entry.started or entry.position_text in ("D", "E"):
                continue
            field_counts[event.kind][0] += weight * entry.retired
            field_counts[event.kind][1] += weight
            if event.kind != "race":
                continue
            team_counts.setdefault(entry.constructor, [0.0, 0.0])
            driver_counts.setdefault(entry.driver, [0.0, 0.0])
            for bucket in (team_counts[entry.constructor], driver_counts[entry.driver]):
                bucket[0] += weight * entry.retired
                bucket[1] += weight
            latest_team[entry.driver] = entry.constructor
    race_rate = (field_counts["race"][0] + 1.0) / (field_counts["race"][1] + 10.0)
    sprint_rate = (field_counts["sprint"][0] + 0.5) / (field_counts["sprint"][1] + 10.0)
    team_rate = {team: (dnf + settings.dnf_prior * race_rate) / (starts + settings.dnf_prior) for team, (dnf, starts) in team_counts.items()}
    dnf = {
        driver: (retired + settings.dnf_prior * team_rate.get(latest_team[driver], race_rate)) / (starts + settings.dnf_prior)
        for driver, (retired, starts) in driver_counts.items()
    }
    return PaceModel(
        season=season,
        skill={driver: float(theta[i]) for driver, i in driver_index.items()},
        car={key: float(theta[i]) for key, i in car_index.items()},
        dnf=dnf,
        field_dnf=race_rate,
        sprint_dnf_factor=min(1.0, sprint_rate / race_rate),
        carryover=settings.carryover_new_rules if season in new_rules else settings.carryover,
        predecessors=dict(predecessors),
    )


def win_probabilities(model: PaceModel, lineup: dict[str, str], kind: str = "race", samples: int = 4000, seed: int = 7) -> dict[str, float]:
    """Each driver's chance of winning one event: finish, and beat every other finisher.

    The retirements are sampled; given who finishes, the Plackett-Luce winning chances are exact,
    so the chances add up to one.
    """
    drivers = list(lineup)
    strength = np.array([model.strength(driver, lineup[driver]) for driver in drivers])
    ex = np.exp(strength - strength.max())
    finish = 1.0 - np.array([model.retirement(driver, kind) for driver in drivers])
    rng = np.random.default_rng(seed)
    running = (rng.random((samples, len(drivers))) < finish) * ex[None, :]
    total = running.sum(axis=1, keepdims=True)
    chance = (running / np.where(total > 0, total, 1.0)).mean(axis=0)
    return {driver: float(value) for driver, value in zip(drivers, chance)}


# --- Simulation ---------------------------------------------------------------------------

SIMULATIONS = 20_000
SEED = 20261004
# Tie order inside a simulated season: points, then wins, second and third places, then by lot.
TIE_SCALES = (1e-3, 1e-5, 1e-7)


@dataclass
class SeasonOdds:
    simulations: int
    driver_title: dict[str, float]
    driver_top3: dict[str, float]
    driver_points: dict[str, float]
    constructor_title: dict[str, float]
    constructor_points: dict[str, float]
    # Event key -> driver -> (win, podium) chances.
    events: dict[str, dict[str, tuple[float, float]]]


def _ranked_positions(points: np.ndarray, places: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    keys = points.astype(np.float64).copy()
    for scale, counts in zip(TIE_SCALES, places):
        keys += scale * counts
    keys += 1e-9 * rng.random(keys.shape)
    return team_sports.positions_from_keys(keys)


def simulate_season(
    model: PaceModel,
    lineup: dict[str, str],
    remaining: list[Event],
    rules: PointsRules,
    drivers: dict[str, Row],
    constructors: dict[str, Row],
    drift: float,
    season_events: int,
    driver_drift: float = 0.0,
    simulations: int = SIMULATIONS,
    seed: int = SEED,
) -> SeasonOdds:
    """Play every remaining race and sprint ``simulations`` times.

    Ratings wander as the season goes on: every car's rating (development, upgrades, shared by
    team-mates) and every driver's take a random-walk step before each event, so that over a
    whole season of ``season_events`` events they drift by ``drift`` and ``driver_drift``. Then for
    each event: who retires, and the order of the rest by Plackett-Luce sampling (strength plus
    Gumbel noise). Countback inside a simulation uses wins, second and third places, then lots.
    """
    rng = np.random.default_rng(seed)
    everyone = sorted(set(drivers) | set(lineup))
    teams = sorted(set(constructors) | set(lineup.values()))
    index = {driver: i for i, driver in enumerate(everyone)}
    team_index = {team: i for i, team in enumerate(teams)}
    racing = [driver for driver in everyone if driver in lineup]
    columns = np.array([index[driver] for driver in racing], dtype=int)
    count, racers = simulations, len(racing)

    def base(rows: dict[str, Row], keys: list[str]) -> list[np.ndarray]:
        fields = [[rows[key].points if key in rows else 0.0 for key in keys]]
        fields += [[rows[key].places.get(place, 0) if key in rows else 0 for key in keys] for place in (1, 2, 3)]
        return [np.tile(np.array(values, dtype=np.float64), (count, 1)) for values in fields]

    driver_points, driver_wins, driver_seconds, driver_thirds = base(drivers, everyone)
    team_points, team_wins, team_seconds, team_thirds = base(constructors, teams)
    membership = np.zeros((racers, len(teams)))
    membership[np.arange(racers), [team_index[lineup[driver]] for driver in racing]] = 1.0

    car_step = drift / math.sqrt(max(season_events, 1))
    driver_step = driver_drift / math.sqrt(max(season_events, 1))
    strength = np.tile(np.array([model.strength(driver, lineup[driver]) for driver in racing]), (count, 1))
    rows = np.arange(count)[:, None]
    events: dict[str, dict[str, tuple[float, float]]] = {}
    for event in remaining:
        if car_step > 0:
            strength = strength + rng.normal(0.0, car_step, (count, len(teams))) @ membership.T
        if driver_step > 0:
            strength = strength + rng.normal(0.0, driver_step, (count, racers))
        retire = np.array([model.retirement(driver, event.kind) for driver in racing])
        out = rng.random((count, racers)) < retire[None, :]
        keys = np.where(out, -np.inf, strength + rng.gumbel(size=(count, racers)))
        order = np.argsort(-keys, axis=1, kind="stable")
        place = np.empty_like(order)
        place[rows, order] = np.arange(racers)[None, :]
        finished = ~out
        table = np.zeros(racers)
        values = rules.table(event.kind)[:racers]
        table[: len(values)] = values
        gained = np.where(finished, table[place], 0.0)
        if event.kind == "race" and rules.fastest_lap:
            eligible = finished & (place < rules.fastest_lap_max_position)
            fastest = np.argmax(np.where(eligible, strength + rng.gumbel(size=(count, racers)), -np.inf), axis=1)
            gained[np.arange(count), fastest] += rules.fastest_lap * eligible.any(axis=1)
        driver_points[:, columns] += gained
        team_points += gained @ membership
        winners = finished & (place == 0)
        podium = finished & (place < 3)
        if event.kind == "race":
            for target, team_target, position in ((driver_wins, team_wins, 0), (driver_seconds, team_seconds, 1), (driver_thirds, team_thirds, 2)):
                hits = (finished & (place == position)).astype(np.float64)
                target[:, columns] += hits
                team_target += hits @ membership
        win_rate, podium_rate = winners.mean(axis=0), podium.mean(axis=0)
        events[event.key] = {driver: (float(win_rate[i]), float(podium_rate[i])) for i, driver in enumerate(racing)}

    driver_rank = _ranked_positions(driver_points, [driver_wins, driver_seconds, driver_thirds], rng)
    team_rank = _ranked_positions(team_points, [team_wins, team_seconds, team_thirds], rng)

    def share(flags: np.ndarray, keys: list[str]) -> dict[str, float]:
        return {key: float(flags[:, i].mean()) for i, key in enumerate(keys)}

    return SeasonOdds(
        simulations=count,
        driver_title=share(driver_rank == 0, everyone),
        driver_top3=share(driver_rank < 3, everyone),
        driver_points={driver: float(driver_points[:, i].mean()) for i, driver in enumerate(everyone)},
        constructor_title=share(team_rank == 0, teams),
        constructor_points={team: float(team_points[:, i].mean()) for i, team in enumerate(teams)},
        events=events,
    )


# --- Payload ------------------------------------------------------------------------------

# Results more than this long overdue mean a cancelled event (or a source problem), not a late update.
OVERDUE = timedelta(days=3)
FAVOURITES = 6
RECENT_RESULTS = 8
# Backtest of the settings above (scripts/backtest_formula1.py), quoted in the page's notes.
BACKTEST_NOTE = (
    "Backtested on 2022-2025 (92 Grands Prix, each predicted from the results before it): race-winner log loss "
    "{race_model} against {race_points} for chances in proportion to championship points and {race_equal} for equal chances. "
    "Drivers' title, top-three and constructors' title odds at 25%, 50% and 75% of each season scored a Brier score of "
    "{season_model} against {season_table} for the table at the time and {season_base} for base rates; the top-three odds "
    "alone ({top3_model}) did slightly worse than the table at the time ({top3_table})."
)
BACKTEST = {
    "race_model": "1.49",
    "race_points": "1.89",
    "race_equal": "2.99",
    "season_model": "0.020",
    "season_table": "0.026",
    "season_base": "0.085",
    "top3_model": "0.026",
    "top3_table": "0.024",
}


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_config(config: dict[str, Any]) -> None:
    team_sports.validate_config(config)
    points = config.get("points") or {}
    for kind in ("race", "sprint"):
        values = points.get(kind)
        if not values or any(not isinstance(value, (int, float)) or value < 0 for value in values) or list(values) != sorted(values, reverse=True):
            raise ValueError(f"{config['id']}: points.{kind} must list each place's points, best first")
    if [tier["kind"] for tier in config["tiers"]] != ["champion", "top"] or [tier["kind"] for tier in config.get("constructorTiers", [])] != ["champion"]:
        raise ValueError(f"{config['id']}: tiers are the drivers' title and a top-N place; constructorTiers the constructors' title")


def constructor_meta(config: dict[str, Any], names: dict[str, str], teams: Iterable[str]) -> dict[str, dict[str, str]]:
    """Display names and colours: the config's, otherwise Jolpica's name and a generated colour."""
    overrides = config.get("teams", {})
    taken = {item["shortName"] for item in overrides.values() if "shortName" in item}
    meta = {}
    for team in sorted(teams):
        override = overrides.get(team, {})
        short = override.get("shortName") or team_sports.auto_short_name(names.get(team, team), taken)
        taken.add(short)
        color, _ = team_sports.hashed_colors(team)
        color = override.get("color", color)
        meta[team] = {
            "key": team,
            "shortName": short,
            "fullName": override.get("fullName", names.get(team, team)),
            "color": color,
            "textColor": "#000000" if team_sports.relative_luminance(color) > 0.179 else "#FFFFFF",
        }
    return meta


def _percent(value: float) -> float:
    return round(value * 100, 2)


def _event_block(event: Event, weekend: dict[str, str]) -> dict[str, Any]:
    return {
        "key": event.key,
        "round": event.round,
        "kind": event.kind,
        "name": event.name,
        "date": iso(event.date),
        "circuit": weekend.get("circuit", ""),
        "locality": weekend.get("locality", ""),
        "country": weekend.get("country", ""),
    }


def check_published(kind: str, rows: dict[str, Row], order: list[str], data: dict[str, Any], last_round: int, warnings: list[str]) -> list[str] | None:
    """The table order to publish when Jolpica's standings for the same round agree with the results.

    When every points and wins total agrees but the order of drivers level on points differs (the
    last tiebreak, qualifying, is not modelled), the published order is used. Any other difference
    is a warning, and the computed table stands.
    """
    published_round, published = published_standings(data, kind)
    if not published or published_round != last_round:
        return None
    problems = standings_differences(rows, order, published)
    published_order = [item["key"] for item in published]
    if problems and problems[0].startswith("order differs") and [rows[key].points for key in published_order] == [rows[key].points for key in order]:
        return published_order
    if problems:
        warnings.append(f"The {kind}' table computed from the results differs from {SOURCE}'s published standings ({'; '.join(problems[:3])}).")
        return None
    return order


def build_payload(config: dict[str, Any], now: datetime, cache_dir: Path, settings: ModelSettings = ModelSettings(), simulations: int = SIMULATIONS) -> dict[str, Any]:
    validate_config(config)
    season = team_sports.resolve_season(config, now)
    year = int(season.feed)
    current = load_season(year, cache_dir, current=True)
    if not current.events:
        raise team_sports.FeedError(f"{SOURCE}: no {year} calendar yet")
    warnings: list[str] = []
    try:
        previous = load_season(year - 1, cache_dir, current=False)
    except team_sports.FeedError as exc:
        previous = SeasonData(year - 1, [])
        warnings.append(f"Last season's results are unavailable ({exc}); the ratings use this season only.")
    rules = PointsRules.from_config(config, year)
    new_rules = set(config.get("regulationChanges", []))

    done = [event for event in current.events if event.done]
    overdue = [event for event in current.events if not event.done and event.date < now - OVERDUE]
    remaining = [event for event in current.events if not event.done and event not in overdue]
    pending = [event for event in remaining if event.date < now - timedelta(hours=6)]
    if overdue:
        names = ", ".join(f"{event.name}{' sprint' if event.kind == 'sprint' else ''}" for event in overdue)
        warnings.append(f"No results for {names}, more than three days on; left out of the simulation as if cancelled.")
    if pending:
        warnings.append(f"{len(pending)} event{'s have' if len(pending) > 1 else ' has'} no results yet at {SOURCE}; simulated as still to run.")

    drivers, constructors, as_published = championship(done, rules)
    driver_order = ranked_keys(drivers)
    team_order = ranked_keys(constructors)
    notes = [f"{event.name}{' sprint' if event.kind == 'sprint' else ''}: points as published (a shortened event scores on a reduced scale)." for event in as_published]
    checked = []
    if done:
        last_round = max(event.round for event in done)
        for kind, rows, order in (("drivers", drivers, driver_order), ("constructors", constructors, team_order)):
            try:
                data = fetch_season(year, f"{kind[:-1]}standings", cache_dir, 3)
            except team_sports.FeedError as exc:
                print(f"{season.payload_id}: published {kind}' standings unavailable ({exc})")
                continue
            agreed = check_published(kind, rows, order, data, last_round, warnings)
            if agreed is None:
                continue
            checked.append(kind)
            if agreed != order:
                notes.append(f"The {kind}' order of those level on points follows {SOURCE}'s published standings.")
                if kind == "drivers":
                    driver_order = agreed
                else:
                    team_order = agreed

    # The cars on the grid: the latest event's entry list (last season's before the first race).
    latest = done[-1] if done else next((event for event in reversed(previous.events) if event.done), None)
    if latest is None:
        raise team_sports.FeedError(f"{SOURCE}: no entry list for {year} yet")
    if not done:
        warnings.append("No results yet: the line-up is last season's final one until the first race.")
    lineup = {entry.driver: entry.constructor for entry in latest.entries}
    people = {**previous.drivers, **current.drivers}
    team_names = {**previous.constructors, **current.constructors}

    model = fit_model(
        previous.events + current.events,
        year,
        settings,
        new_rules=new_rules,
        predecessors=config.get("predecessors", {}),
        reference=max((event.date for event in done), default=latest.date),
        teams=set(lineup.values()),
    )
    odds = simulate_season(
        model, lineup, remaining, rules, drivers, constructors, settings.drift, len(done) + len(remaining),
        driver_drift=settings.driver_drift, simulations=simulations,
    )
    complete = not remaining
    status = "complete" if complete else "in_progress"

    # Each driver's team: the latest car they drove this season (the grid's, before the first race).
    team_of: dict[str, str] = {}
    teams_driven: dict[str, list[str]] = {}
    for event in done:
        for entry in event.entries:
            team_of[entry.driver] = entry.constructor
            if entry.constructor not in teams_driven.setdefault(entry.driver, []):
                teams_driven[entry.driver].append(entry.constructor)
    for driver, team in lineup.items():
        team_of.setdefault(driver, team)
    everyone = driver_order + [driver for driver in sorted(lineup) if driver not in drivers]
    team_keys = team_order + [team for team in sorted(set(lineup.values())) if team not in constructors]
    if not done:
        # Before the first race everyone is on zero: list them by their title chances.
        everyone.sort(key=lambda driver: -odds.driver_title.get(driver, 0.0))
        team_keys.sort(key=lambda team: -odds.constructor_title.get(team, 0.0))
    meta = constructor_meta(config, team_names, set(team_keys) | set(team_of.values()))

    def driver_row(rank: int, driver: str) -> dict[str, Any]:
        row = drivers.get(driver, Row(driver))
        person = people.get(driver) or Person(driver, driver[:3].upper(), "", driver)
        return {
            "teamKey": driver,
            "shortName": person.code,
            "fullName": person.name.strip(),
            "number": person.number,
            "team": team_of.get(driver),
            "teams": teams_driven.get(driver, [team_of[driver]] if driver in team_of else []),
            "rank": rank,
            "points": row.points if row.points % 1 else int(row.points),
            "wins": row.wins,
            "podiums": row.podiums,
            "sprintWins": row.sprint_wins,
            "played": row.starts,
            "racing": driver in lineup,
        }

    def team_row(rank: int, team: str) -> dict[str, Any]:
        row = constructors.get(team, Row(team))
        return {
            "teamKey": team,
            "shortName": meta[team]["shortName"],
            "fullName": meta[team]["fullName"],
            "rank": rank,
            "points": row.points if row.points % 1 else int(row.points),
            "wins": row.wins,
            "podiums": row.podiums,
            "drivers": [driver for driver in everyone if team_of.get(driver) == team and driver in lineup],
        }

    if complete:
        title = {driver: 100.0 if driver == driver_order[0] else 0.0 for driver in everyone}
        top3 = {driver: 100.0 if driver in driver_order[:3] else 0.0 for driver in everyone}
        team_title = {team: 100.0 if team == team_order[0] else 0.0 for team in team_keys}
    else:
        title = {driver: _percent(odds.driver_title.get(driver, 0.0)) for driver in everyone}
        top3 = {driver: _percent(odds.driver_top3.get(driver, 0.0)) for driver in everyone}
        team_title = {team: _percent(odds.constructor_title.get(team, 0.0)) for team in team_keys}

    upcoming = []
    for event in remaining:
        chances = odds.events.get(event.key, {})
        favourites = sorted(chances, key=lambda driver: (-chances[driver][0], -chances[driver][1], driver))[:FAVOURITES]
        upcoming.append(
            {
                **_event_block(event, current.weekends.get(event.round, {})),
                "favourites": [{"driver": driver, "win": _percent(chances[driver][0]), "podium": _percent(chances[driver][1])} for driver in favourites],
            }
        )
    results = []
    for event in sorted(done, key=lambda item: (item.date, item.kind == "race"), reverse=True)[:RECENT_RESULTS]:
        podium = [entry.driver for entry in event.entries if entry.classified and entry.position <= 3]
        results.append({**_event_block(event, current.weekends.get(event.round, {})), "podium": podium})

    races_left = sum(event.kind == "race" for event in remaining)
    sprints_left = len(remaining) - races_left
    carry = settings.carryover_new_rules if year in new_rules else settings.carryover
    model_notes = [
        "Pace comes from a rank-ordered logit (Plackett-Luce) model of finishing orders: each driver's strength is their own "
        "skill plus their car's, rated per team and season, fitted on this season's and last season's races and sprints, "
        f"with results losing half their weight every {settings.half_life_days:g} days.",
        (
            f"{year} brings new chassis and power-unit rules, so last season's car ratings carry over at only {carry:.0%} "
            f"(against {settings.carryover:.0%} when the rules are stable), and the cars are rated mainly on this season's races. "
            "Drivers keep their skill from one season to the next, less the time decay."
            if year in new_rules
            else f"Last season's car ratings carry over at {carry:.0%}; drivers keep their skill, less the time decay."
        ),
        "A car that does not see the flag is left out of that event's order and counts as a retirement instead. Each driver's "
        f"retirement chance blends their own, their team's and the field's rates (field: {model.field_dnf:.0%} of race starts, "
        f"sprints {model.field_dnf * model.sprint_dnf_factor:.0%}).",
        (
            f"The remaining {races_left} race{'s' if races_left != 1 else ''}"
            + (f" and {sprints_left} sprint{'s' if sprints_left != 1 else ''}" if sprints_left else "")
            + f" are simulated {simulations:,} times. Car and driver ratings drift as the season goes on (development and form), "
            "more for the races furthest away."
            if remaining
            else "The season is over: the odds columns show the final outcome."
        ),
        "Points: 25-18-15-12-10-8-6-4-2-1 in a Grand Prix and 8-7-6-5-4-3-2-1 in a sprint"
        + ("; no fastest-lap point since 2025." if not rules.fastest_lap else f", plus {rules.fastest_lap:g} for the fastest lap in the top ten.")
        + " Ties are split by race places: most wins, then most second places, and so on (sprints do not count). "
        "Simulated ties use wins, second and third places.",
        BACKTEST_NOTE.format(**BACKTEST),
    ]
    if checked:
        model_notes.append(
            f"The tables are computed from the race and sprint results and match {SOURCE}'s published standings "
            f"({' and '.join(checked)}) after round {max(event.round for event in done)}."
        )
    model_notes += config.get("notes", [])

    return {
        "metadata": {
            "season": season.label,
            "generated_at": iso(now),
            "source": SOURCE,
            "source_url": SOURCE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": status,
            "warnings": warnings,
            "notes": notes,
        },
        "league": {
            "id": season.payload_id,
            "configId": config["id"],
            "sport": config["sport"],
            "name": config["name"],
            "shortName": config["shortName"],
            "headline": config.get("headline"),
            "season": season.label,
            "seasonLabel": season.label,
            "priority": config.get("priority", 100),
            "tiers": config["tiers"],
            "constructorTiers": config.get("constructorTiers", []),
            "teams": [meta[team] for team in team_keys],
            "rounds": len({event.round for event in current.events if event not in overdue}),
            "eventsLeft": len(remaining),
            "rules": config.get("rules"),
        },
        "standings": [driver_row(rank, driver) for rank, driver in enumerate(everyone, start=1)],
        "constructorStandings": [team_row(rank, team) for rank, team in enumerate(team_keys, start=1)],
        "events": upcoming,
        "results": results,
        "fixtures": [],
        "analysis": {
            "method": "Monte Carlo",
            "simulations": simulations,
            "model": "Plackett-Luce pace model",
            "modelNotes": model_notes,
            "probabilities": {driver: {"title": title[driver], "top3": top3[driver]} for driver in everyone},
            "constructorProbabilities": {team: {"title": team_title[team]} for team in team_keys},
            "expected": {driver: {"points": round(odds.driver_points.get(driver, 0.0), 1)} for driver in everyone},
            "constructorExpected": {team: {"points": round(odds.constructor_points.get(team, 0.0), 1)} for team in team_keys},
            "ratings": {
                driver: {
                    "skill": round(model.skill.get(driver, 0.0), 3),
                    "car": round(model.car_rating(lineup[driver]), 3),
                    "retirement": round(model.retirement(driver), 3),
                }
                for driver in sorted(lineup)
            },
        },
        **({"playoffs": {"champion": driver_order[0]}} if complete and driver_order else {}),
    }
