"""ICC World Test Championship engine: points table, exact claims and season odds.

The config (``leagues/wtc-2025-27.json``) holds the format and the whole schedule: every
series and every Test, with the country it is played in (a "home" series at a neutral
ground is played in the UAE, say), so a rescheduled, cancelled or added Test is a config
edit. Results come from three places, in this order of precedence:

1. ``results`` in the config: Tests Cricsheet cannot describe (abandoned without a ball
   bowled, an unfit pitch, a match awarded or forfeited), each with its source.
2. Cricsheet's men's Test archive (ODC-By 1.0), matched to the schedule by teams and date.
3. CricketData (with ``CRICDATA_API_KEY``), for Tests Cricsheet has not added yet and for
   Tests in progress, which are shown but never counted.

Rules (ICC World Test Championship 2025-2027 Playing Conditions, clauses 16.9-16.13):
12 points a win, 6 a tie, 4 a draw; an abandoned Test is a draw, unless the pitch or
outfield is rated unfit, when the visitors take the win's points. One point is deducted
per penalty over (16.11). Teams are ranked by percentage of points (PCT), then series
wins, away PCT, and the ICC Test ranking on 30 April 2027 (16.12). The top two meet in
the final (16.13).
"""

from __future__ import annotations

import itertools
import json
import math
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import requests

import cricsheet
import team_sports
import wtc_model
from wtc_model import ModelSettings, Ratings, TestMatch


SOURCE = "Cricsheet"
SOURCE_URL = "https://cricsheet.org/"
CRICDATA_API_BASE = "https://api.cricapi.com/v1"
CRICDATA_SOURCE_URL = "https://cricketdata.org/"
SIMULATIONS = int(os.getenv("WTC_SIMULATIONS", "20000"))
RANDOM_SEED = int(os.getenv("WTC_RANDOM_SEED", "20251127"))
# Days a Test can run (five, plus one for a time zone) before a missing result is a lag.
TEST_DAYS = 5
# Days after a Test's last day that CricketData is asked for its result.
LAG_DAYS = 21
# Upcoming Tests checked for "the Tests that swing the race".
SWING_WINDOW = 12
SWING_SHOWN = 6
# Exact searches give up above this many search nodes (the claim is then left out).
SEARCH_LIMIT = 400_000
# Seasons are rebuilt this long after the final, while Cricsheet adds it.
FINALIZE_DAYS = 45
RESULT_KINDS = ("host", "visitor", "draw", "tie", "abandoned", "unfit", "awarded", "forfeit")

# Random-walk drift of team ratings per square-root year in the simulation. Set by
# scripts/backtest_wtc.py: final-place odds at 25%, 50% and 75% of 2021-23 and 2023-25 scored a
# Brier score of 0.0627 with no drift, 0.0627 at 0.1, 0.0632 at 0.2, 0.0634 at 0.3 and 0.0653 at 0.5.
DRIFT_PER_YEAR = 0.0

# scripts/backtest_wtc.py, run on 22 November 2026 (Cricsheet archive of 3 November 2026).
BACKTEST = {
    "tests": 242,
    "model_rps": 0.2048,
    "base_rps": 0.2379,
    "model_log_loss": 0.8786,
    "base_log_loss": 0.9628,
    "season_brier": 0.0627,
    "season_table": 0.2222,
    "season_base": 0.1728,
}
BACKTEST_NOTE = (
    "Backtest: before each of the {tests} championship Tests of 2019-21, 2021-23, 2023-25 and 2025-27 so far, the model, "
    "fitted on the Tests before it, scored {model_rps:.4f} (ranked probability score) and {model_log_loss:.3f} (log loss), "
    "against {base_rps:.4f} and {base_log_loss:.3f} for home-win, draw and away-win base rates. Final-place odds at 25%, 50% "
    "and 75% of 2021-23 and 2023-25 scored a Brier score of {season_brier:.3f}, against {season_table:.3f} for the table at "
    "the time and {season_base:.3f} for a no-skill guess."
)


class WtcError(team_sports.FeedError):
    pass


# ---------------------------------------------------------------------------
# Config


@dataclass(frozen=True)
class Fixture:
    """One scheduled Test of a championship series."""

    key: str
    series: str
    number: int
    host: str
    visitor: str
    start: date
    end: date
    venue: str | None
    country: str | None
    status: str = "scheduled"
    note: str = ""
    tentative: bool = False
    # "month" when only the month is known: such a Test is never assumed to be under way.
    precision: str = "day"

    @property
    def teams(self) -> tuple[str, str]:
        return self.host, self.visitor

    @property
    def neutral(self) -> bool:
        return self.country is not None and self.country not in self.teams

    @property
    def counts(self) -> bool:
        """Cancelled and postponed-out-of-window Tests are not in the points percentage (16.12.1)."""
        return self.status not in ("cancelled", "postponed")


@dataclass(frozen=True)
class Series:
    id: str
    name: str
    host: str
    visitor: str
    fixtures: tuple[Fixture, ...]
    cricketdata: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Deduction:
    team: str
    points: int
    test: str
    note: str
    source: str = ""


@dataclass(frozen=True)
class Result:
    """A counted Test result. ``kind`` is one of RESULT_KINDS; awarded and forfeited Tests name a winner."""

    fixture: str
    kind: str
    winner: str | None = None
    margin: str = ""
    source: str = SOURCE
    note: str = ""
    end: date | None = None

    def points(self, fixture: Fixture, rules: "Rules") -> dict[str, int]:
        host, visitor = fixture.teams
        if self.kind == "host":
            return {host: rules.win, visitor: rules.loss}
        if self.kind == "visitor":
            return {host: rules.loss, visitor: rules.win}
        if self.kind == "tie":
            return {host: rules.tie, visitor: rules.tie}
        if self.kind in ("draw", "abandoned"):
            return {host: rules.draw, visitor: rules.draw}
        if self.kind == "unfit":
            # 16.10.2: points as if the visitors had won.
            return {host: rules.loss, visitor: rules.win}
        winner = self.winner
        return {winner: rules.win, (visitor if winner == host else host): rules.loss}

    def series_winner(self, fixture: Fixture) -> str | None:
        """The side this Test counts as a win for in its series; abandoned Tests are draws (16.10.2)."""
        if self.kind == "host":
            return fixture.host
        if self.kind == "visitor":
            return fixture.visitor
        if self.kind in ("awarded", "forfeit"):
            return self.winner
        return None

    def letter(self, fixture: Fixture, team: str) -> str:
        """W, L, D or T for a team's record; an abandoned Test (unfit pitch included) is a draw."""
        if self.kind == "tie":
            return "T"
        winner = self.series_winner(fixture)
        if winner is None:
            return "D"
        return "W" if winner == team else "L"


@dataclass(frozen=True)
class Rules:
    win: int = 12
    tie: int = 6
    draw: int = 4
    loss: int = 0
    finalists: int = 2


@dataclass(frozen=True)
class Final:
    venue: str | None
    city: str | None
    country: str
    start: date | None
    end: date | None
    reserve_day: date | None
    # "joint": a drawn or tied final makes the two finalists joint champions.
    draw_result: str = "joint"
    tentative: bool = False
    note: str = ""


@dataclass(frozen=True)
class Cycle:
    id: str
    name: str
    short_name: str
    season_label: str
    teams: dict[str, dict[str, Any]]
    series: tuple[Series, ...]
    rules: Rules
    standings_close: date
    season_start: date
    season_end: date
    final: Final
    deductions: tuple[Deduction, ...]
    results: tuple[Result, ...]
    rankings: tuple[str, ...]
    rankings_as_of: str | None
    rankings_source: str | None
    config: dict[str, Any]
    # Tests between championship teams in the window that are not part of it (an anniversary Test).
    other_tests: tuple[tuple[frozenset[str], date, date], ...] = ()

    @property
    def fixtures(self) -> list[Fixture]:
        return sorted((fixture for series in self.series for fixture in series.fixtures), key=lambda item: (item.start, item.key))

    @property
    def team_keys(self) -> list[str]:
        return list(self.teams)


def _day(value: str) -> date:
    return date.fromisoformat(value)


def parse_config(config: dict[str, Any]) -> Cycle:
    """Read and check a championship config; any inconsistency fails before a build."""
    teams = {item["key"]: item for item in config["teams"]}
    rules_raw = (config.get("format") or {}).get("points") or {}
    rules = Rules(
        win=rules_raw.get("win", 12),
        tie=rules_raw.get("tie", 6),
        draw=rules_raw.get("draw", 4),
        loss=rules_raw.get("loss", 0),
        finalists=(config.get("format") or {}).get("finalists", 2),
    )
    series = []
    for item in config["series"]:
        fixtures = []
        for test in item["tests"]:
            month_only = len(test["start"]) == 7
            start = _day(f"{test['start']}-01") if month_only else _day(test["start"])
            if test.get("end"):
                end = _day(test["end"])
            elif month_only:
                end = date(start.year + start.month // 12, start.month % 12 + 1, 1) - timedelta(days=1)
            else:
                end = start + timedelta(days=TEST_DAYS - 1)
            fixtures.append(
                Fixture(
                    key=f"{item['id']}-{test['number']}",
                    series=item["id"],
                    number=test["number"],
                    host=item["host"],
                    visitor=item["visitor"],
                    start=start,
                    end=end,
                    venue=test.get("venue"),
                    country=test.get("country", item["host"]),
                    status=test.get("status", "scheduled"),
                    note=test.get("note", ""),
                    tentative=bool(test.get("tentative") or item.get("tentative") or month_only),
                    precision="month" if month_only else "day",
                )
            )
        series.append(
            Series(
                id=item["id"],
                name=item.get("name") or f"{teams[item['visitor']]['fullName']} tour of {teams[item['host']]['fullName']}",
                host=item["host"],
                visitor=item["visitor"],
                fixtures=tuple(fixtures),
                cricketdata=item.get("cricketdata") or {},
                note=item.get("note", ""),
            )
        )
    final_raw = config.get("final") or {}
    rankings = config.get("rankings") or {}
    cycle = Cycle(
        id=config["id"],
        name=config["name"],
        short_name=config["shortName"],
        season_label=config.get("seasonLabel", config.get("season", "")),
        teams=teams,
        series=tuple(series),
        rules=rules,
        standings_close=_day(config["standingsClose"]),
        season_start=_day(config["seasonStart"]),
        season_end=_day(config["seasonEnd"]),
        final=Final(
            venue=final_raw.get("venue"),
            city=final_raw.get("city"),
            country=final_raw.get("country", "ENG"),
            start=_day(final_raw["start"]) if final_raw.get("start") else None,
            end=_day(final_raw["end"]) if final_raw.get("end") else None,
            reserve_day=_day(final_raw["reserveDay"]) if final_raw.get("reserveDay") else None,
            draw_result=final_raw.get("drawResult", "joint"),
            tentative=bool(final_raw.get("tentative")),
            note=final_raw.get("note", ""),
        ),
        deductions=tuple(
            Deduction(team=item["team"], points=item["points"], test=item["test"], note=item.get("note", ""), source=item.get("source", ""))
            for item in config.get("deductions", ())
        ),
        results=tuple(
            Result(
                fixture=item["test"],
                kind=item["result"],
                winner=item.get("winner"),
                margin=item.get("margin", ""),
                source=item.get("source", "config"),
                note=item.get("note", ""),
            )
            for item in config.get("results", ())
        ),
        rankings=tuple(rankings.get("order", ())),
        rankings_as_of=rankings.get("asOf"),
        rankings_source=rankings.get("source"),
        config=config,
        other_tests=tuple(_other_test(item) for item in config.get("otherTests", ())),
    )
    validate(cycle)
    return cycle


def _other_test(item: dict[str, Any]) -> tuple[frozenset[str], date, date]:
    """A Test outside the championship, by its teams and its date (or month)."""
    if len(item["start"]) == 7:
        first = _day(f"{item['start']}-01")
        last = date(first.year + first.month // 12, first.month % 12 + 1, 1) - timedelta(days=1)
    else:
        first = last = _day(item["start"])
    return frozenset(item["teams"]), first - timedelta(days=3), last + timedelta(days=3)


def validate(cycle: Cycle) -> None:
    keys = set(cycle.teams)
    if len({team["shortName"] for team in cycle.teams.values()}) != len(keys):
        raise ValueError(f"{cycle.id}: team short names must be unique")
    fixtures = cycle.fixtures
    known = {fixture.key for fixture in fixtures}
    if len(known) != len(fixtures):
        raise ValueError(f"{cycle.id}: Test keys must be unique")
    for series in cycle.series:
        if series.host not in keys or series.visitor not in keys or series.host == series.visitor:
            raise ValueError(f"{cycle.id}: series {series.id} needs two different championship teams")
        if [fixture.number for fixture in series.fixtures] != list(range(1, len(series.fixtures) + 1)):
            raise ValueError(f"{cycle.id}: series {series.id} Tests must be numbered 1, 2, ...")
        for fixture in series.fixtures:
            if fixture.status not in ("scheduled", "cancelled", "postponed"):
                raise ValueError(f"{cycle.id}: {fixture.key} has an unknown status {fixture.status!r}")
            if fixture.end < fixture.start:
                raise ValueError(f"{cycle.id}: {fixture.key} ends before it starts")
    homes = defaultdict(int)
    aways = defaultdict(int)
    for series in cycle.series:
        homes[series.host] += 1
        aways[series.visitor] += 1
    expected = (cycle.config.get("format") or {}).get("seriesPerTeam")
    if expected:
        for team in keys:
            if homes[team] + aways[team] != expected:
                raise ValueError(f"{cycle.id}: {team} has {homes[team] + aways[team]} series, not {expected}")
    for item in cycle.deductions:
        if item.team not in keys or item.test not in known or item.points <= 0:
            raise ValueError(f"{cycle.id}: a deduction needs a team, a positive number of points and the Test it was for")
        fixture = next(f for f in fixtures if f.key == item.test)
        if item.team not in fixture.teams:
            raise ValueError(f"{cycle.id}: {item.team} did not play {item.test}")
    for item in cycle.results:
        if item.fixture not in known or item.kind not in RESULT_KINDS:
            raise ValueError(f"{cycle.id}: result for {item.fixture}: unknown Test or result {item.kind!r}")
        fixture = next(f for f in fixtures if f.key == item.fixture)
        if item.kind in ("awarded", "forfeit") and item.winner not in fixture.teams:
            raise ValueError(f"{cycle.id}: {item.fixture} was {item.kind}; name the winner")
        if not item.source or item.source == "config":
            raise ValueError(f"{cycle.id}: result for {item.fixture} needs a source")
    if cycle.rankings and sorted(cycle.rankings) != sorted(keys):
        raise ValueError(f"{cycle.id}: rankings must list every team once")
    if cycle.final.draw_result not in ("joint",):
        raise ValueError(f"{cycle.id}: the final's draw result must be 'joint'")


def in_season(config: dict[str, Any], now: datetime) -> bool:
    """Built from the first Test until the final has been on Cricsheet for a while."""
    start = _day(config["seasonStart"]) - timedelta(days=30)
    end = _day(config["seasonEnd"]) + timedelta(days=FINALIZE_DAYS)
    return start <= now.date() <= end


def validate_config(config: dict[str, Any]) -> None:
    parse_config(config)


# ---------------------------------------------------------------------------
# Results


def match_cricsheet(cycle: Cycle, tests: Iterable[TestMatch], warnings: list[str]) -> dict[str, Result]:
    """Cricsheet Tests of the schedule: same two teams, starting within three days of the scheduled date."""
    fixtures = [fixture for fixture in cycle.fixtures if fixture.counts]
    by_pair: dict[frozenset[str], list[Fixture]] = defaultdict(list)
    for fixture in fixtures:
        by_pair[frozenset(fixture.teams)].append(fixture)
    found: dict[str, Result] = {}
    keys = set(cycle.teams)
    window_end = cycle.standings_close
    for test in tests:
        if not set(test.teams) <= keys or test.start < cycle.season_start or test.start > window_end:
            continue
        if any(set(test.teams) == teams and first <= test.start <= last for teams, first, last in cycle.other_tests):
            continue
        candidates = [
            fixture
            for fixture in by_pair.get(frozenset(test.teams), [])
            if abs((test.start - fixture.start).days) <= 3 and fixture.key not in found
        ]
        if not candidates:
            if not any(abs((test.start - fixture.start).days) <= 3 for fixture in by_pair.get(frozenset(test.teams), [])):
                warnings.append(
                    f"Cricsheet has a {test.teams[0]} v {test.teams[1]} Test from {test.start.isoformat()} that is not in "
                    "the championship schedule; check the config."
                )
            continue
        fixture = min(candidates, key=lambda item: abs((test.start - item.start).days))
        if test.tie:
            kind = "tie"
        elif test.winner is None:
            kind = "draw"
        elif test.awarded:
            found[fixture.key] = Result(fixture.key, "awarded", winner=test.winner, margin="awarded", end=test.end)
            continue
        else:
            kind = "host" if test.winner == fixture.host else "visitor"
        found[fixture.key] = Result(fixture.key, kind, winner=test.winner, margin=test.margin, end=test.end)
    return found


# CricketData: Tests Cricsheet has not added yet, and Tests in progress.


@dataclass(frozen=True)
class LiveState:
    fixture: str
    status: str


def cricdata_key() -> str | None:
    return os.getenv("CRICDATA_API_KEY") or os.getenv("CRICAPI_KEY")


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def team_from_name(cycle: Cycle, name: str) -> str | None:
    target = _normal(name)
    for key, team in cycle.teams.items():
        names = {key, team["shortName"], team["fullName"], *team.get("aliases", ())}
        if target in {_normal(item) for item in names}:
            return key
    return None


def parse_cricdata_status(cycle: Cycle, fixture: Fixture, status: str) -> Result | None:
    """A finished Test's result from CricketData's status text; None if it cannot be read safely."""
    text = _normal(status)
    if not text:
        return None
    if re.search(r"\b(abandoned|called off)\b", text):
        return Result(fixture.key, "abandoned", source="CricketData", note=status)
    if re.search(r"\b(drawn|draw)\b", text):
        return Result(fixture.key, "draw", source="CricketData")
    if re.search(r"\btied?\b", text):
        return Result(fixture.key, "tie", source="CricketData")
    match = re.search(r"^(.*?)\bwon\b(.*)$", text)
    if not match:
        return None
    winners = []
    for team in fixture.teams:
        meta = cycle.teams[team]
        names = {meta["fullName"], *meta.get("aliases", ()), team}
        if any(re.search(rf"\b{re.escape(_normal(item))}\b", match.group(1)) for item in names if _normal(item)):
            winners.append(team)
    if len(winners) != 1:
        return None
    winner = winners[0]
    margin = re.sub(r"^by ", "", match.group(2).strip())
    margin = margin.replace("wkts", "wickets").replace("wkt", "wicket").replace("inns", "innings")
    return Result(fixture.key, "host" if winner == fixture.host else "visitor", winner=winner, margin=margin, source="CricketData")


def _cricdata_get(session: requests.Session, endpoint: str, key: str, params: dict[str, Any]) -> dict[str, Any]:
    response = session.get(f"{CRICDATA_API_BASE}/{endpoint}", params={"apikey": key, **params}, timeout=20)
    if not response.ok:
        raise WtcError(f"CricketData {endpoint} returned HTTP {response.status_code}")
    payload = response.json()
    status = payload.get("status")
    if isinstance(status, str) and status.lower() not in ("success", "ok"):
        raise WtcError(f"CricketData {endpoint}: {payload.get('reason') or status}")
    return payload


def _series_names(cycle: Cycle, series: Series) -> list[str]:
    host = cycle.teams[series.host]["fullName"]
    visitor = cycle.teams[series.visitor]["fullName"]
    names = [series.cricketdata.get("name")] if series.cricketdata.get("name") else []
    return [*names, f"{visitor} tour of {host}", series.name]


def find_cricdata_series(cycle: Cycle, series: Series, session: requests.Session, key: str, cache: dict[str, str]) -> str | None:
    """The series id: fixed in the config, found earlier, or searched by name and year."""
    if series.cricketdata.get("seriesId"):
        return str(series.cricketdata["seriesId"])
    if series.id in cache:
        return cache[series.id]
    years = {str(fixture.start.year) for fixture in series.fixtures}
    wanted = [_normal(name) for name in _series_names(cycle, series)]
    for offset in range(0, 100, 25):
        payload = _cricdata_get(session, "series", key, {"offset": offset})
        for item in payload.get("data") or []:
            if not isinstance(item, dict):
                continue
            name = _normal(str(item.get("name", "")))
            if "women" in name or not any(year in name for year in years):
                continue
            if any(re.search(rf"\b{re.escape(target)}\b", name) for target in wanted):
                cache[series.id] = str(item.get("id"))
                return cache[series.id]
    return None


def fetch_cricdata(
    cycle: Cycle,
    pending: list[Fixture],
    now: datetime,
    cache_dir: Path,
    warnings: list[str],
    session: requests.Session | None = None,
) -> tuple[dict[str, Result], dict[str, LiveState]]:
    """Results and live states of ``pending`` Tests from each of their series' CricketData match lists."""
    key = cricdata_key()
    if not pending or not key:
        return {}, {}
    session = session or requests.Session()
    cache_path = cache_dir / "cricketdata-wtc-series.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except ValueError:
        cache = {}
    results: dict[str, Result] = {}
    live: dict[str, LiveState] = {}
    by_series: dict[str, list[Fixture]] = defaultdict(list)
    for fixture in pending:
        by_series[fixture.series].append(fixture)
    series_by_id = {series.id: series for series in cycle.series}
    for series_id, fixtures in sorted(by_series.items()):
        series = series_by_id[series_id]
        try:
            cricdata_id = find_cricdata_series(cycle, series, session, key, cache)
            if not cricdata_id:
                warnings.append(f"CricketData does not list {series.name} yet.")
                continue
            info = _cricdata_get(session, "series_info", key, {"id": cricdata_id})
        except (requests.RequestException, ValueError, WtcError) as exc:
            warnings.append(f"CricketData could not be read for {series.name} ({exc}).")
            continue
        matches = (info.get("data") or {}).get("matchList") or []
        for item in matches:
            if not isinstance(item, dict):
                continue
            if str(item.get("matchType", "test")).lower() != "test":
                continue
            names = item.get("teams") or []
            teams = {team_from_name(cycle, str(name)) for name in names}
            when = str(item.get("dateTimeGMT") or item.get("date") or "")[:10]
            try:
                day = date.fromisoformat(when)
            except ValueError:
                continue
            fixture = next(
                (f for f in fixtures if teams == set(f.teams) and abs((day - f.start).days) <= 3),
                None,
            )
            if fixture is None:
                continue
            status = str(item.get("status") or "")
            if item.get("matchEnded"):
                result = parse_cricdata_status(cycle, fixture, status)
                if result is None:
                    warnings.append(f"CricketData's result for {series.name}, Test {fixture.number} could not be read ({status!r}).")
                else:
                    results[fixture.key] = result
            elif item.get("matchStarted"):
                live[fixture.key] = LiveState(fixture.key, status or "In progress")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
    return results, live


def fetch_cricdata_final(
    cycle: Cycle,
    finalists: list[str],
    today: date,
    cache_dir: Path,
    warnings: list[str],
    session: requests.Session | None = None,
) -> tuple[Result | None, str | None]:
    """The final's result (or its live state) from CricketData while Cricsheet has not added it."""
    key = cricdata_key()
    if not key or not cycle.final.start or today > (cycle.final.end or cycle.final.start) + timedelta(days=LAG_DAYS):
        return None, None
    a, b = finalists
    year = str(cycle.final.start.year)
    final_series = Series(
        id="final",
        name="ICC World Test Championship Final",
        host=a,
        visitor=b,
        fixtures=(),
        cricketdata=(cycle.config.get("final") or {}).get("cricketdata") or {"name": "World Test Championship Final"},
    )
    session = session or requests.Session()
    try:
        cache: dict[str, str] = {}
        series_id = final_series.cricketdata.get("seriesId")
        if not series_id:
            for offset in range(0, 100, 25):
                payload = _cricdata_get(session, "series", key, {"offset": offset})
                for item in payload.get("data") or []:
                    name = _normal(str(item.get("name", "")))
                    if "women" not in name and year in name and "world test championship" in name:
                        series_id = str(item.get("id"))
                        break
                if series_id:
                    break
        if not series_id:
            return None, None
        info = _cricdata_get(session, "series_info", key, {"id": series_id})
    except (requests.RequestException, ValueError, WtcError) as exc:
        warnings.append(f"CricketData could not be read for the final ({exc}).")
        return None, None
    fixture = Fixture("final", "final", 1, a, b, cycle.final.start, cycle.final.end or cycle.final.start, cycle.final.venue, cycle.final.country)
    for item in (info.get("data") or {}).get("matchList") or []:
        if not isinstance(item, dict) or str(item.get("matchType", "test")).lower() != "test":
            continue
        if {team_from_name(cycle, str(name)) for name in item.get("teams") or []} != set(finalists):
            continue
        status = str(item.get("status") or "")
        if item.get("matchEnded"):
            result = parse_cricdata_status(cycle, fixture, status)
            if result is None:
                warnings.append(f"CricketData's result for the final could not be read ({status!r}).")
                return None, None
            if result.kind in ("host", "visitor"):
                return replace(result, kind="host", winner=result.winner), None
            return result, None
        if item.get("matchStarted"):
            return None, status or "In progress"
    return None, None


# ---------------------------------------------------------------------------
# Table


@dataclass
class Row:
    team: str
    played: int = 0
    won: int = 0
    lost: int = 0
    drawn: int = 0
    tied: int = 0
    points_won: int = 0
    deducted: int = 0
    away_played: int = 0
    away_points: int = 0
    series_won: int = 0
    series_played: int = 0

    @property
    def points(self) -> int:
        return self.points_won - self.deducted

    def pct(self, rules: Rules) -> Fraction | None:
        return Fraction(self.points, rules.win * self.played) if self.played else None

    def away_pct(self, rules: Rules) -> Fraction | None:
        return Fraction(self.away_points, rules.win * self.away_played) if self.away_played else None


def series_state(cycle: Cycle, series: Series, results: dict[str, Result]) -> dict[str, Any]:
    """Wins each side has, and the series winner once every counted Test has a result."""
    counted = [fixture for fixture in series.fixtures if fixture.counts]
    wins = {series.host: 0, series.visitor: 0}
    draws = 0
    for fixture in counted:
        result = results.get(fixture.key)
        if result is None:
            continue
        winner = result.series_winner(fixture)
        if winner:
            wins[winner] += 1
        else:
            draws += 1
    complete = bool(counted) and all(fixture.key in results for fixture in counted)
    winner = None
    if complete and wins[series.host] != wins[series.visitor]:
        winner = series.host if wins[series.host] > wins[series.visitor] else series.visitor
    return {"wins": wins, "draws": draws, "complete": complete, "winner": winner, "played": sum(f.key in results for f in counted)}


def table(cycle: Cycle, results: dict[str, Result]) -> dict[str, Row]:
    rows = {team: Row(team) for team in cycle.teams}
    fixtures = {fixture.key: fixture for fixture in cycle.fixtures}
    for key, result in results.items():
        fixture = fixtures[key]
        if not fixture.counts:
            continue
        points = result.points(fixture, cycle.rules)
        for team in fixture.teams:
            row = rows[team]
            row.played += 1
            row.points_won += points[team]
            letter = result.letter(fixture, team)
            row.won += letter == "W"
            row.lost += letter == "L"
            row.drawn += letter == "D"
            row.tied += letter == "T"
            if team == fixture.visitor:
                row.away_played += 1
                row.away_points += points[team]
    for item in cycle.deductions:
        rows[item.team].deducted += item.points
        if fixtures[item.test].visitor == item.team:
            rows[item.team].away_points -= item.points
    for series in cycle.series:
        state = series_state(cycle, series, results)
        if state["complete"]:
            for team in (series.host, series.visitor):
                rows[team].series_played += 1
            if state["winner"]:
                rows[state["winner"]].series_won += 1
    return rows


def rank(cycle: Cycle, rows: dict[str, Row]) -> list[str]:
    """16.12: PCT, then series wins, away PCT and the ICC Test ranking (the latest in the config)."""
    ranking = {team: index for index, team in enumerate(cycle.rankings)}

    def key(team: str) -> tuple:
        row = rows[team]
        pct = row.pct(cycle.rules)
        away = row.away_pct(cycle.rules)
        return (
            -(pct if pct is not None else Fraction(-1)),
            -row.series_won,
            -(away if away is not None else Fraction(-1)),
            ranking.get(team, len(ranking)),
            team,
        )

    return sorted(rows, key=key)


def tie_notes(cycle: Cycle, rows: dict[str, Row], order: list[str]) -> list[str]:
    """How teams level on PCT were split, in the words of clause 16.12."""
    notes = []
    groups: dict[Fraction, list[str]] = defaultdict(list)
    for team in order:
        pct = rows[team].pct(cycle.rules)
        if pct is not None:
            groups[pct].append(team)
    short = {team: cycle.teams[team]["shortName"] for team in cycle.teams}
    for pct, teams in groups.items():
        if len(teams) < 2:
            continue
        names = ", ".join(short[team] for team in teams)
        series = [rows[team].series_won for team in teams]
        aways = [rows[team].away_pct(cycle.rules) for team in teams]
        if len(set(series)) == len(series):
            how = "series wins"
        elif len(set(aways)) == len(aways):
            how = "series wins, then away PCT"
        else:
            how = f"series wins, away PCT and then the ICC Test ranking{f' of {cycle.rankings_as_of}' if cycle.rankings_as_of else ''}"
        notes.append(f"{names} are level on {float(pct) * 100:.2f}% and are ordered by {how} (clause 16.12).")
    return notes


# ---------------------------------------------------------------------------
# Exact claims about the final places, on results alone


@dataclass(frozen=True)
class Remaining:
    """A Test still to be played, as the teams in it."""

    key: str
    host: str
    visitor: str


def _ge(points_a: int, played_a: int, points_b: int, played_b: int) -> bool:
    """PCT of a >= PCT of b, exactly."""
    return points_a * played_b >= points_b * played_a


def _gt(points_a: int, played_a: int, points_b: int, played_b: int) -> bool:
    return points_a * played_b > points_b * played_a


class Exact:
    """Best and worst cases for each team's final place, by search over the remaining results.

    Over-rate penalties still to come are not known, so the claims are on results alone.
    Every result is in play, ties included. A team in a top-two place on the same PCT as a
    team just outside it is "level": the tie-breakers of clause 16.12 then decide.
    """

    def __init__(self, cycle: Cycle, rows: dict[str, Row], remaining: list[Remaining]):
        self.rules = cycle.rules
        self.teams = list(cycle.teams)
        self.points = {team: rows[team].points for team in self.teams}
        self.remaining = remaining
        self.left = {team: sum(team in (game.host, game.visitor) for game in remaining) for team in self.teams}
        self.final_played = {team: rows[team].played + self.left[team] for team in self.teams}
        self.places = cycle.rules.finalists
        self.nodes = 0

    # Two other teams can both reach (or pass) a team's PCT.
    def _pair_can_pass(self, team: str, base: dict[str, int], fixed: set[str], strict: bool) -> bool | None:
        played = self.final_played
        others = [other for other in self.teams if other != team]
        target = (base[team], played[team])
        for first, second in itertools.combinations(others, 2):
            points = dict(base)
            mutual = 0
            for game in self.remaining:
                if game.key in fixed:
                    continue
                pair = {game.host, game.visitor}
                if pair == {first, second}:
                    mutual += 1
                elif first in pair:
                    points[first] += self.rules.win
                elif second in pair:
                    points[second] += self.rules.win
            outcomes = [(self.rules.win, self.rules.loss), (self.rules.loss, self.rules.win), (self.rules.draw, self.rules.draw), (self.rules.tie, self.rules.tie)]
            for combo in itertools.combinations_with_replacement(range(len(outcomes)), mutual):
                a = points[first] + sum(outcomes[index][0] for index in combo)
                b = points[second] + sum(outcomes[index][1] for index in combo)
                compare = _gt if strict else _ge
                if compare(a, played[first], *target) and compare(b, played[second], *target):
                    return True
        return False

    def _base(self, team: str, wins: set[str], draws: set[str] = frozenset()) -> tuple[dict[str, int], set[str]]:
        """Points with a team's own remaining Tests fixed: won in ``wins``, drawn in ``draws``, lost otherwise."""
        points = dict(self.points)
        fixed = set()
        for game in self.remaining:
            if team not in (game.host, game.visitor):
                continue
            other = game.visitor if game.host == team else game.host
            fixed.add(game.key)
            if game.key in wins:
                points[team] += self.rules.win
            elif game.key in draws:
                points[team] += self.rules.draw
                points[other] += self.rules.draw
            else:
                points[other] += self.rules.win
        return points, fixed

    def own_games(self, team: str) -> list[Remaining]:
        return [game for game in self.remaining if team in (game.host, game.visitor)]

    def guaranteed(self, team: str, wins: set[str]) -> str:
        """'yes' if a top-two place is certain with these wins (other own Tests lost), 'level' if a tie is the worst case."""
        base, fixed = self._base(team, wins)
        if self._pair_can_pass(team, base, fixed, strict=True):
            return "no"
        if self._pair_can_pass(team, base, fixed, strict=False):
            return "level"
        return "yes"

    def possible(self, team: str, wins: set[str] | None = None, draws: set[str] = frozenset()) -> str | None:
        """'outright' if some completion puts the team in the top two outright, 'level' if only tied, else 'no'.

        ``wins`` defaults to all of the team's remaining Tests. None means the search gave up.
        """
        if wins is None:
            wins = {game.key for game in self.own_games(team)}
        base, fixed = self._base(team, wins, draws)
        outright = self._can_keep_below(team, base, fixed, strict=True)
        if outright is None:
            return None
        if outright:
            return "outright"
        level = self._can_keep_below(team, base, fixed, strict=False)
        if level is None:
            return None
        return "level" if level else "no"

    def _can_keep_below(self, team: str, base: dict[str, int], fixed: set[str], strict: bool) -> bool | None:
        """Can all but ``places - 1`` other teams finish below (strict) or not above the team?"""
        played = self.final_played
        free = [game for game in self.remaining if game.key not in fixed]
        others = [other for other in self.teams if other != team]
        for exempt in itertools.combinations(others, self.places - 1):
            points = dict(base)
            games = []
            for game in free:
                if game.host in exempt or game.visitor in exempt:
                    # An exempt side wins: the best result for keeping its opponent down.
                    loser = game.visitor if game.host in exempt else game.host
                    if loser in exempt:
                        continue
                    points[loser] += self.rules.loss
                    continue
                games.append(game)
            caps = {}
            feasible = True
            for other in others:
                if other in exempt:
                    continue
                # Most points ``other`` can end with and still be below (or level with) the team.
                limit = Fraction(base[team] * played[other], played[team]) if played[team] else Fraction(0)
                cap = math.floor(limit)
                if strict and limit.denominator == 1:
                    cap -= 1
                caps[other] = cap - points[other]
                if caps[other] < 0:
                    feasible = False
                    break
            if not feasible:
                continue
            verdict = self._assign(games, caps)
            if verdict is None:
                return None
            if verdict:
                return True
        return False

    def _assign(self, games: list[Remaining], caps: dict[str, int]) -> bool | None:
        """Do results exist for ``games`` that keep every team within its cap? (Draw 4-4, win 12-0.)"""
        win, draw, loss = self.rules.win, self.rules.draw, self.rules.loss
        # Points-cheapest results: every Test gives at least 2 x draw in total (or a win's).
        least = min(2 * draw, win + loss)
        if sum(caps.values()) < least * len(games):
            return False
        order = sorted(games, key=lambda game: (caps[game.host] + caps[game.visitor]))
        memo: dict[tuple, bool] = {}

        def search(index: int, budget: tuple[int, ...]) -> bool:
            self.nodes += 1
            if self.nodes > SEARCH_LIMIT:
                raise TimeoutError
            if index == len(order):
                return True
            state = (index, budget)
            if state in memo:
                return memo[state]
            game = order[index]
            remaining_least = least * (len(order) - index)
            if sum(budget) < remaining_least:
                memo[state] = False
                return False
            host, visitor = positions[game.host], positions[game.visitor]
            options = [(draw, draw), (win, loss), (loss, win)]
            # Give the points to whoever has more room first.
            if budget[visitor] > budget[host]:
                options = [(draw, draw), (loss, win), (win, loss)]
            for gain_host, gain_visitor in options:
                if budget[host] >= gain_host and budget[visitor] >= gain_visitor:
                    following = list(budget)
                    following[host] -= gain_host
                    following[visitor] -= gain_visitor
                    if search(index + 1, tuple(following)):
                        memo[state] = True
                        return True
            memo[state] = False
            return False

        names = sorted(caps)
        positions = {name: index for index, name in enumerate(names)}
        try:
            return search(0, tuple(caps[name] for name in names))
        except TimeoutError:
            return None


def needs(cycle: Cycle, rows: dict[str, Row], remaining: list[Remaining]) -> dict[str, dict[str, Any]]:
    """What each team needs, stated exactly, on results alone."""
    exact = Exact(cycle, rows, remaining)
    out = {}
    finalists = cycle.rules.finalists
    for team in cycle.teams:
        own = exact.own_games(team)
        left = len(own)
        played = exact.final_played[team]
        best = Fraction(exact.points[team] + cycle.rules.win * left, cycle.rules.win * played) if played else None
        worst = Fraction(exact.points[team], cycle.rules.win * played) if played else None
        all_keys = {game.key for game in own}
        clinched = exact.guaranteed(team, set())
        destiny = exact.guaranteed(team, all_keys)
        reach = exact.possible(team) if clinched != "yes" else "outright"
        if clinched == "yes":
            status = "clinched"
        elif clinched == "level":
            status = "clinched-unless-level"
        elif reach == "no":
            status = "eliminated"
        elif reach == "level":
            status = "level-only"
        elif destiny == "yes":
            status = "in-control"
        elif reach is None:
            status = "undetermined"
        else:
            status = "needs-help"
        entry: dict[str, Any] = {
            "status": status,
            "testsLeft": left,
            "bestPct": round(float(best) * 100, 2) if best is not None else None,
            "worstPct": round(float(worst) * 100, 2) if worst is not None else None,
            "ownDestiny": destiny,
        }
        # Fewest wins (other Tests drawn) that keep a chance, and wins that make sure of it.
        if status in ("needs-help", "in-control", "level-only") and left <= 10:
            fewest = None
            for count in range(0, left + 1):
                verdicts = []
                for chosen in itertools.combinations(sorted(all_keys), count):
                    verdict = exact.possible(team, set(chosen), all_keys - set(chosen))
                    if verdict is None:
                        verdicts = None
                        break
                    verdicts.append(verdict)
                    if verdict == "outright":
                        break
                if verdicts is None:
                    break
                if "outright" in verdicts:
                    fewest = count
                    break
            if fewest is not None:
                entry["fewestWins"] = fewest
        if status in ("needs-help", "in-control", "clinched-unless-level") and left <= 12:
            sure = None
            for count in range(0, left + 1):
                if all(exact.guaranteed(team, set(chosen)) == "yes" for chosen in itertools.combinations(sorted(all_keys), count)):
                    sure = count
                    break
            if sure is not None:
                entry["winsToClinch"] = sure
        out[team] = entry
    return out


def need_statements(cycle: Cycle, entry: dict[str, Any], team: str) -> list[str]:
    """Plain sentences for one team's exact situation."""
    left = entry["testsLeft"]
    tests = f"{left} remaining Test{'s' if left != 1 else ''}"
    statements = []
    status = entry["status"]
    if status == "clinched":
        statements.append("Through to the final, whatever the remaining results.")
    elif status == "clinched-unless-level":
        statements.append("Can only miss the final on a tie-breaker: at worst they finish level on PCT with the team in the last place, and series wins, away PCT and the ICC ranking would decide.")
    elif status == "eliminated":
        statements.append("Cannot reach the final on results: at least two teams will finish above them whatever happens.")
    elif status == "level-only":
        statements.append("Can still finish level on PCT for a final place, but not above: the tie-breakers would decide.")
    elif status == "in-control":
        statements.append(f"In control: winning all {tests} would take them to the final, whatever else happens.")
    elif status == "needs-help":
        if entry["ownDestiny"] == "level":
            statements.append(f"Winning all {tests} would at worst leave them level on PCT for a final place; the tie-breakers would decide.")
        else:
            statements.append(f"Needs help: even winning all {tests} could leave two teams above them.")
    if left and entry.get("bestPct") is not None:
        statements.append(f"Their PCT can finish anywhere from {entry['worstPct']:.2f}% to {entry['bestPct']:.2f}%.")
    elif not left and entry.get("bestPct") is not None:
        statements.append(f"No Tests left: they finish on {entry['bestPct']:.2f}%.")
    if "fewestWins" in entry and entry["fewestWins"] > 0 and status not in ("clinched",):
        count = entry["fewestWins"]
        statements.append(f"Need at least {count} win{'s' if count != 1 else ''} from {tests} (drawing the rest) to keep a chance of finishing in the top two outright.")
    if "winsToClinch" in entry and 0 < entry["winsToClinch"] <= left and status != "in-control":
        count = entry["winsToClinch"]
        statements.append(f"Any {count} win{'s' if count != 1 else ''} from {tests} would guarantee a final place.")
    elif "winsToClinch" in entry and 0 < entry["winsToClinch"] < left and status == "in-control":
        count = entry["winsToClinch"]
        statements.append(f"Any {count} win{'s' if count != 1 else ''} from {tests} would be enough, whichever they are.")
    return statements


# ---------------------------------------------------------------------------
# Simulation


@dataclass
class Simulation:
    simulations: int
    positions: dict[str, list[float]]
    final: dict[str, float]
    title: dict[str, float]
    joint: dict[str, float]
    pct: dict[str, float]
    fixtures: dict[str, tuple[float, float, float]]
    swing: list[dict[str, Any]]
    matchups: list[dict[str, Any]]
    final_odds: dict[str, Any] | None = None


def simulate(
    cycle: Cycle,
    rows: dict[str, Row],
    results: dict[str, Result],
    remaining: list[Fixture],
    ratings: Ratings,
    today: date,
    simulations: int = SIMULATIONS,
    drift: float = DRIFT_PER_YEAR,
    seed: int = RANDOM_SEED,
    finalists: list[str] | None = None,
) -> Simulation:
    """Play the remaining Tests ``simulations`` times, then the final in the final's country.

    Each simulated cycle draws a random walk for every team's rating (``drift`` per sqrt
    year), so a Test a year away is less certain than next week's. Teams level on PCT are
    split by series wins, away PCT, then the ranking in the config (clause 16.12).
    """
    rng = np.random.default_rng(seed)
    teams = cycle.team_keys
    index = {team: i for i, team in enumerate(teams)}
    n_teams = len(teams)
    games = len(remaining)
    rules = cycle.rules

    # Rating paths: one step per distinct Test date, plus the final.
    dates = sorted({fixture.start for fixture in remaining} | ({cycle.final.start} if cycle.final.start else set()))
    if not dates:
        dates = [today]
    steps = np.array([max((day - previous).days, 0) / 365.25 for previous, day in zip([today, *dates[:-1]], dates)])
    if drift:
        noise = rng.standard_normal((simulations, len(dates), n_teams)) * drift * np.sqrt(steps)[None, :, None]
        paths = np.cumsum(noise, axis=1)
    else:
        paths = np.zeros((simulations, len(dates), n_teams))
    base = np.array([ratings.rating.get(team, 0.0) for team in teams])
    date_index = {day: i for i, day in enumerate(dates)}

    points = np.tile(np.array([rows[team].points for team in teams], dtype=np.int64), (simulations, 1))
    played = np.array([rows[team].played for team in teams], dtype=np.int64)
    away_points = np.tile(np.array([rows[team].away_points for team in teams], dtype=np.int64), (simulations, 1))
    away_played = np.array([rows[team].away_played for team in teams], dtype=np.int64)
    outcomes = np.zeros((simulations, games), dtype=np.int8)
    fixture_odds = {}
    for g, fixture in enumerate(remaining):
        h, v = index[fixture.host], index[fixture.visitor]
        when = date_index[fixture.start]
        rating_h = base[h] + paths[:, when, h]
        rating_v = base[v] + paths[:, when, v]
        advantage = ratings.home + ratings.home_by_country.get(fixture.country or "", 0.0)
        strength_h = rating_h + (advantage if fixture.country == fixture.host else 0.0)
        strength_v = rating_v + (advantage if fixture.country == fixture.visitor else 0.0)
        drawish = ratings.draw + ratings.draw_by_country.get(fixture.country or "", 0.0) + (strength_h + strength_v) / 2
        logits = np.stack([strength_h, drawish, strength_v], axis=1)
        logits -= logits.max(axis=1, keepdims=True)
        prob = np.exp(logits)
        prob /= prob.sum(axis=1, keepdims=True)
        draw_u = rng.random(simulations)
        outcome = np.where(draw_u < prob[:, 0], 0, np.where(draw_u < prob[:, 0] + prob[:, 1], 1, 2)).astype(np.int8)
        outcomes[:, g] = outcome
        fixture_odds[fixture.key] = tuple(float(x) for x in ratings.probabilities(fixture.host, fixture.visitor, fixture.country))
        host_points = np.where(outcome == 0, rules.win, np.where(outcome == 1, rules.draw, rules.loss))
        visitor_points = np.where(outcome == 2, rules.win, np.where(outcome == 1, rules.draw, rules.loss))
        points[:, h] += host_points
        points[:, v] += visitor_points
        away_points[:, v] += visitor_points
    final_played = played + np.array([sum(team in f.teams for f in remaining) for team in teams])
    final_away = away_played + np.array([sum(team == f.visitor for f in remaining) for team in teams])

    # Series wins: completed series count once all their Tests are in.
    series_wins = np.zeros((simulations, n_teams), dtype=np.int64)
    remaining_index = {fixture.key: g for g, fixture in enumerate(remaining)}
    for series in cycle.series:
        counted = [fixture for fixture in series.fixtures if fixture.counts]
        if not counted:
            continue
        host_wins = np.zeros(simulations, dtype=np.int64)
        visitor_wins = np.zeros(simulations, dtype=np.int64)
        for fixture in counted:
            if fixture.key in results:
                winner = results[fixture.key].series_winner(fixture)
                host_wins += winner == series.host
                visitor_wins += winner == series.visitor
            elif fixture.key in remaining_index:
                outcome = outcomes[:, remaining_index[fixture.key]]
                host_wins += outcome == 0
                visitor_wins += outcome == 2
        series_wins[:, index[series.host]] += host_wins > visitor_wins
        series_wins[:, index[series.visitor]] += visitor_wins > host_wins

    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(final_played > 0, points / (rules.win * np.maximum(final_played, 1)), -1.0)
        away_pct = np.where(final_away > 0, away_points / (rules.win * np.maximum(final_away, 1)), -1.0)
    ranking = np.array([cycle.rankings.index(team) if team in cycle.rankings else n_teams for team in teams])
    rank_key = np.tile(ranking, (simulations, 1))
    order = np.lexsort((rank_key, -away_pct, -series_wins, -pct), axis=1)
    position = np.empty_like(order)
    rows_index = np.arange(simulations)[:, None]
    position[rows_index, order] = np.arange(n_teams)[None, :]

    if finalists:
        first = np.full(simulations, index[finalists[0]])
        second = np.full(simulations, index[finalists[1]])
    else:
        first, second = order[:, 0], order[:, 1]
    # The final, in the final's country (England's home Test if England are in it).
    final_index = date_index.get(cycle.final.start) if cycle.final.start else None
    drift_a = paths[np.arange(simulations), final_index, first] if final_index is not None else 0.0
    drift_b = paths[np.arange(simulations), final_index, second] if final_index is not None else 0.0
    rating_a = base[first] + drift_a
    rating_b = base[second] + drift_b
    country = cycle.final.country
    advantage = ratings.home + ratings.home_by_country.get(country, 0.0)
    team_array = np.array(teams)
    strength_a = rating_a + np.where(team_array[first] == country, advantage, 0.0)
    strength_b = rating_b + np.where(team_array[second] == country, advantage, 0.0)
    drawish = ratings.draw + ratings.draw_by_country.get(country, 0.0) + (strength_a + strength_b) / 2
    logits = np.stack([strength_a, drawish, strength_b], axis=1)
    logits -= logits.max(axis=1, keepdims=True)
    prob = np.exp(logits)
    prob /= prob.sum(axis=1, keepdims=True)
    u = rng.random(simulations)
    final_outcome = np.where(u < prob[:, 0], 0, np.where(u < prob[:, 0] + prob[:, 1], 1, 2))

    def share(mask: np.ndarray) -> float:
        return float(mask.mean() * 100)

    positions = {team: [share(position[:, index[team]] == place) for place in range(n_teams)] for team in teams}
    final = {}
    title = {}
    joint = {}
    for team in teams:
        i = index[team]
        in_final = (first == i) | (second == i)
        final[team] = share(in_final)
        won = ((first == i) & (final_outcome == 0)) | ((second == i) & (final_outcome == 2))
        title[team] = share(won)
        joint[team] = share(in_final & (final_outcome == 1))
    mean_pct = {team: float(np.mean(pct[:, index[team]]) * 100) for team in teams}

    # The matchups most likely to be the final.
    pairs: dict[tuple[str, str], int] = defaultdict(int)
    a_names = team_array[np.minimum(first, second)]
    b_names = team_array[np.maximum(first, second)]
    for a, b in zip(a_names, b_names):
        pairs[(a, b)] += 1
    matchups = [
        {"teams": [str(a), str(b)], "chance": count / simulations * 100}
        for (a, b), count in sorted(pairs.items(), key=lambda item: -item[1])[:6]
    ]

    # Tests that swing a team's final chance most: the final chance after each result.
    swing = []
    in_final = np.zeros((simulations, n_teams), dtype=bool)
    in_final[np.arange(simulations), first] = True
    in_final[np.arange(simulations), second] = True
    for g, fixture in enumerate(remaining[:SWING_WINDOW]):
        outcome = outcomes[:, g]
        best = None
        for team in teams:
            column = in_final[:, index[team]]
            chances = []
            for value in (0, 1, 2):
                mask = outcome == value
                chances.append(float(column[mask].mean() * 100) if mask.sum() >= 200 else None)
            known = [value for value in chances if value is not None]
            if len(known) < 2:
                continue
            spread = max(known) - min(known)
            if best is None or spread > best["swing"]:
                best = {
                    "fixture": fixture.key,
                    "team": team,
                    "ifHost": chances[0],
                    "ifDraw": chances[1],
                    "ifVisitor": chances[2],
                    "swing": spread,
                }
        if best:
            swing.append(best)
    swing.sort(key=lambda item: -item["swing"])
    return Simulation(
        simulations=simulations,
        positions=positions,
        final=final,
        title=title,
        joint=joint,
        pct=mean_pct,
        fixtures=fixture_odds,
        swing=swing[:SWING_SHOWN],
        matchups=matchups,
    )


# ---------------------------------------------------------------------------
# Payload


def _percent(value: float) -> float:
    return round(value, 2)


def _pct_value(value: Fraction | None) -> float | None:
    return round(float(value) * 100, 2) if value is not None else None


def classify(cycle: Cycle, results: dict[str, Result], live: dict[str, LiveState], today: date) -> dict[str, str]:
    """Each Test's state: result, in_progress, awaiting (finished, result not in yet), scheduled or cancelled."""
    states = {}
    for fixture in cycle.fixtures:
        if not fixture.counts:
            states[fixture.key] = fixture.status
        elif fixture.key in results:
            states[fixture.key] = "result"
        elif fixture.key in live or (fixture.precision == "day" and fixture.start <= today <= fixture.end + timedelta(days=1)):
            states[fixture.key] = "in_progress"
        elif fixture.end + timedelta(days=1) < today:
            states[fixture.key] = "awaiting"
        else:
            states[fixture.key] = "scheduled"
    return states


def season_status(cycle: Cycle, states: dict[str, str], today: date, final_result: Result | None, final_teams: list[str] | None) -> str:
    if final_result is not None:
        return "complete"
    if not any(state == "result" for state in states.values()):
        return "pre_season" if today < cycle.season_start else "league_stage"
    open_tests = [key for key, state in states.items() if state in ("scheduled", "in_progress", "awaiting")]
    if not open_tests and (today > cycle.standings_close or final_teams):
        return "playoffs"
    return "league_stage"


def find_final(cycle: Cycle, tests: list[TestMatch], finalists: list[str]) -> TestMatch | None:
    """The final on Cricsheet: the two finalists, in the final's country, in its window."""
    if not cycle.final.start or len(finalists) != 2:
        return None
    for test in tests:
        if set(test.teams) == set(finalists) and test.country == cycle.final.country and abs((test.start - cycle.final.start).days) <= 7:
            return test
    return None


def build_payload(
    config: dict[str, Any],
    now: datetime,
    cache_dir: Path,
    archive: Path | None = None,
    settings: ModelSettings = ModelSettings(),
    simulations: int = SIMULATIONS,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    cycle = parse_config(config)
    today = now.astimezone(timezone.utc).date()
    warnings: list[str] = []
    notes: list[str] = []
    cricsheet_dir = Path(os.getenv("CRICSHEET_CACHE_DIR", cache_dir.parent / "cricsheet"))
    archive = archive or wtc_model.fetch_tests_archive(cricsheet_dir)
    tests = wtc_model.load_tests(archive)
    unknown_grounds = sorted({f"{test.venue} ({test.city})" for test in tests if test.country is None and test.start >= cycle.season_start})
    if unknown_grounds:
        warnings.append(f"Unknown Test grounds, rated without home advantage: {', '.join(unknown_grounds)}.")

    results = match_cricsheet(cycle, tests, warnings)
    sources = {SOURCE}
    for item in cycle.results:
        results[item.fixture] = item
        notes.append(f"{item.fixture}: {item.note or item.kind} (source: {item.source}).")
    fixtures = {fixture.key: fixture for fixture in cycle.fixtures}
    # Tests whose result is due or that may be under way, missing from Cricsheet.
    pending = [
        fixture
        for fixture in cycle.fixtures
        if fixture.counts and fixture.key not in results and fixture.start <= today + timedelta(days=1) and fixture.end + timedelta(days=LAG_DAYS) >= today
    ]
    live_results, live = fetch_cricdata(cycle, pending, now, cache_dir, warnings, session)
    if live_results or live:
        sources.add("CricketData")
    for key, result in live_results.items():
        results.setdefault(key, result)
    # Results after the standings close (a late Test) still count only if played in the window.
    results = {key: result for key, result in results.items() if fixtures[key].start <= cycle.standings_close and fixtures[key].counts}

    states = classify(cycle, results, live, today)
    awaiting = [fixtures[key] for key, state in states.items() if state == "awaiting"]
    if awaiting:
        names = ", ".join(f"{fixtures[f.key].series} Test {f.number}" for f in awaiting)
        warnings.append(
            f"No result yet for {names}: Cricsheet adds Tests a few days after they finish"
            + ("" if cricdata_key() else ", and CricketData is not configured here")
            + ". Simulated as still to play."
        )
    rows = table(cycle, results)
    order = rank(cycle, rows)
    remaining = [fixtures[key] for key, state in sorted(states.items(), key=lambda item: (fixtures[item[0]].start, item[0])) if state in ("scheduled", "in_progress", "awaiting")]
    remaining = [fixture for fixture in remaining if fixture.start <= cycle.standings_close]

    # Ratings and drift run from the latest known result, not from today, so a day without
    # cricket rewrites nothing (the nightly build only commits real changes).
    known = [test.end for test in tests if test.end <= today] + [result.end or fixtures[key].end for key, result in results.items()]
    anchor = min(max(known, default=cycle.season_start), today, cycle.final.end or today)
    ratings = wtc_model.fit(tests, anchor + timedelta(days=1), settings)
    # Every Test is in (or the window has closed): the top two are the finalists. A tie-break
    # by the ICC ranking uses the latest ranking in the config until the window's ranking date.
    standings_final = not remaining and (bool(results) or today > cycle.standings_close)
    finalists = order[: cycle.rules.finalists] if standings_final else None
    final_test = find_final(cycle, tests, finalists) if finalists else None
    final_result = None
    final_live = None
    if final_test is not None:
        if final_test.winner is None:
            final_result = Result("final", "tie" if final_test.tie else "draw", margin="tied" if final_test.tie else "drawn", end=final_test.end)
        else:
            final_result = Result("final", "host", winner=final_test.winner, margin=final_test.margin, end=final_test.end)
    elif finalists and cycle.final.start and today >= cycle.final.start - timedelta(days=1):
        final_result, final_live = fetch_cricdata_final(cycle, finalists, today, cache_dir, warnings, session)
        if final_result is not None or final_live:
            sources.add("CricketData")
    final_override = (config.get("final") or {}).get("result")
    if final_override and finalists:
        final_result = Result(
            "final",
            final_override["result"],
            winner=final_override.get("winner"),
            margin=final_override.get("margin", ""),
            source=final_override.get("source", "config"),
        )
    status = season_status(cycle, states, today, final_result, finalists)

    simulation = None
    if status != "complete":
        simulation = simulate(cycle, rows, results, remaining, ratings, anchor, simulations, finalists=finalists)
    exact_needs = needs(cycle, rows, [Remaining(f.key, f.host, f.visitor) for f in remaining])
    if any(item["status"] == "undetermined" for item in exact_needs.values()):
        warnings.append("Some exact claims were too large to settle this time and are left out.")

    short = {team: cycle.teams[team]["shortName"] for team in cycle.teams}
    champion = None
    joint = None
    if final_result is not None:
        # Competition Regulations 10.4: a drawn, tied or abandoned final makes joint champions.
        if final_result.kind in ("draw", "tie", "abandoned", "unfit"):
            joint = list(finalists)
        else:
            champion = final_result.winner

    def probabilities(team: str) -> dict[str, float]:
        if status == "complete":
            in_final = team in (finalists or [])
            won = team == champion or (joint is not None and team in joint)
            return {"final": 100.0 if in_final else 0.0, "title": 100.0 if team == champion else 0.0, "joint": 100.0 if joint and team in joint else 0.0, "champion": 100.0 if won else 0.0}
        return {
            "final": _percent(simulation.final[team]),
            "title": _percent(simulation.title[team]),
            "joint": _percent(simulation.joint[team]),
            "champion": _percent(simulation.title[team] + simulation.joint[team]),
        }

    standings = []
    for place, team in enumerate(order, start=1):
        row = rows[team]
        meta = cycle.teams[team]
        need = exact_needs[team]
        standings.append(
            {
                "teamKey": team,
                "shortName": meta["shortName"],
                "fullName": meta["fullName"],
                "color": meta.get("color", "#2d405f"),
                "textColor": meta.get("textColor", "#ffffff"),
                "rank": place,
                "played": row.played,
                "matches": row.played,
                "won": row.won,
                "wins": row.won,
                "lost": row.lost,
                "drawn": row.drawn,
                "tied": row.tied,
                "pointsWon": row.points_won,
                "deducted": row.deducted,
                "points": row.points,
                "pct": _pct_value(row.pct(cycle.rules)),
                "pctExact": [row.points, cycle.rules.win * row.played] if row.played else None,
                "seriesWon": row.series_won,
                "seriesPlayed": row.series_played,
                "awayPlayed": row.away_played,
                "awayPct": _pct_value(row.away_pct(cycle.rules)),
                "testsLeft": need["testsLeft"],
                "bestPct": need["bestPct"],
                "worstPct": need["worstPct"],
                "form": _form(cycle, results, team),
            }
        )

    series_blocks = []
    for series in cycle.series:
        state = series_state(cycle, series, results)
        tests_block = []
        for fixture in series.fixtures:
            result = results.get(fixture.key)
            item = {
                "key": fixture.key,
                "number": fixture.number,
                "start": fixture.start.isoformat(),
                "end": fixture.end.isoformat(),
                "venue": fixture.venue,
                "country": fixture.country,
                "neutral": fixture.neutral,
                "state": states[fixture.key],
                "tentative": fixture.tentative,
                "precision": fixture.precision,
            }
            if fixture.note:
                item["note"] = fixture.note
            if result is not None:
                points = result.points(fixture, cycle.rules)
                item["result"] = {
                    "kind": result.kind,
                    "winner": result.series_winner(fixture) if result.kind not in ("unfit",) else None,
                    "margin": result.margin,
                    "points": {fixture.host: points[fixture.host], fixture.visitor: points[fixture.visitor]},
                    "source": result.source,
                    **({"note": result.note} if result.note else {}),
                }
            if fixture.key in live:
                item["live"] = live[fixture.key].status
            if simulation and fixture.key in simulation.fixtures:
                h, d, v = simulation.fixtures[fixture.key]
                item["odds"] = {"host": _percent(h * 100), "draw": _percent(d * 100), "visitor": _percent(v * 100)}
            deductions = [{"team": d.team, "points": d.points, "note": d.note, "source": d.source} for d in cycle.deductions if d.test == fixture.key]
            if deductions:
                item["deductions"] = deductions
            tests_block.append(item)
        counted = [t for t in tests_block if t["state"] not in ("cancelled", "postponed")]
        if counted and all(t["state"] == "result" for t in counted):
            series_status = "complete"
        elif any(t["state"] in ("result", "in_progress", "awaiting") for t in counted):
            series_status = "in_progress"
        elif not counted:
            series_status = "cancelled"
        else:
            series_status = "scheduled"
        series_blocks.append(
            {
                "id": series.id,
                "name": series.name,
                "host": series.host,
                "visitor": series.visitor,
                "status": series_status,
                "start": min(f.start for f in series.fixtures).isoformat(),
                "end": max(f.end for f in series.fixtures).isoformat(),
                "scheduled": len(series.fixtures),
                "counted": len(counted),
                "score": {series.host: state["wins"][series.host], series.visitor: state["wins"][series.visitor], "draws": state["draws"]},
                "winner": state["winner"],
                "tests": tests_block,
                **({"note": series.note} if series.note else {}),
            }
        )
    series_blocks.sort(key=lambda item: (item["start"], item["id"]))

    fixtures_out = []
    for fixture in remaining:
        entry = {
            "id": fixture.key,
            "series": fixture.series,
            "number": fixture.number,
            "teamA": fixture.host,
            "teamB": fixture.visitor,
            "host": fixture.host,
            "visitor": fixture.visitor,
            "dateTimeGMT": f"{fixture.start.isoformat()}T00:00:00Z",
            "start": fixture.start.isoformat(),
            "end": fixture.end.isoformat(),
            "venue": fixture.venue,
            "country": fixture.country,
            "neutral": fixture.neutral,
            "state": states[fixture.key],
            "status": "in_progress" if states[fixture.key] == "in_progress" else "scheduled",
            "precision": fixture.precision,
            "tentative": fixture.tentative,
        }
        if simulation:
            h, d, v = simulation.fixtures[fixture.key]
            entry["odds"] = {"host": _percent(h * 100), "draw": _percent(d * 100), "visitor": _percent(v * 100)}
        fixtures_out.append(entry)

    recent = sorted((key for key in results if key in fixtures), key=lambda key: (fixtures[key].start, key), reverse=True)[:10]
    results_out = []
    for key in recent:
        fixture = fixtures[key]
        result = results[key]
        results_out.append(
            {
                "id": key,
                "series": fixture.series,
                "number": fixture.number,
                "host": fixture.host,
                "visitor": fixture.visitor,
                "start": fixture.start.isoformat(),
                "venue": fixture.venue,
                "kind": result.kind,
                "winner": result.series_winner(fixture),
                "margin": result.margin,
            }
        )

    needs_out = {team: {**entry, "statements": need_statements(cycle, entry, team)} for team, entry in exact_needs.items()}
    model_notes = model_notes_for(cycle, ratings, settings, simulation, remaining)
    model_notes += config.get("notes", [])
    notes += tie_notes(cycle, rows, order)

    final_block = {
        "venue": cycle.final.venue,
        "city": cycle.final.city,
        "country": cycle.final.country,
        "start": cycle.final.start.isoformat() if cycle.final.start else None,
        "end": cycle.final.end.isoformat() if cycle.final.end else None,
        "reserveDay": cycle.final.reserve_day.isoformat() if cycle.final.reserve_day else None,
        "drawResult": cycle.final.draw_result,
        "tentative": cycle.final.tentative,
        "note": cycle.final.note,
        "sources": (config.get("final") or {}).get("sources", []),
        "finalists": finalists,
        "standingsClose": cycle.standings_close.isoformat(),
    }
    if finalists and status != "complete":
        a, b = finalists
        h, d, v = ratings.probabilities(a, b, cycle.final.country)
        final_block["odds"] = {a: _percent(h * 100), "draw": _percent(d * 100), b: _percent(v * 100)}
    if final_live:
        final_block["live"] = final_live
    if final_result is not None:
        final_block["result"] = {
            "kind": "joint" if joint else "win",
            "winner": champion,
            "joint": joint,
            "margin": final_result.margin,
        }
    if simulation is not None:
        final_block["matchups"] = [{"teams": item["teams"], "chance": _percent(item["chance"])} for item in simulation.matchups]

    payload = {
        "metadata": {
            "season": cycle.season_label,
            "generated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "source": " and ".join(sorted(sources)),
            "source_url": SOURCE_URL,
            "license": cricsheet.CRICSHEET_LICENSE,
            "license_url": cricsheet.CRICSHEET_LICENSE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": status,
            "warnings": warnings,
            "notes": notes,
        },
        "league": {
            "id": cycle.id,
            "configId": cycle.id,
            "sport": config.get("sport", "cricket"),
            "engine": "wtc",
            "name": cycle.name,
            "shortName": cycle.short_name,
            "headline": config.get("headline"),
            "season": cycle.season_label,
            "seasonLabel": cycle.season_label,
            "priority": config.get("priority", 100),
            "points": {"win": cycle.rules.win, "tie": cycle.rules.tie, "draw": cycle.rules.draw, "loss": cycle.rules.loss},
            "finalists": cycle.rules.finalists,
            "tiers": [
                {"key": "final", "label": "Reach the final", "shortLabel": "Final", "kind": "top", "size": cycle.rules.finalists},
                {"key": "title", "label": "Win the title", "shortLabel": "Title", "kind": "champion"},
            ],
            "columns": [
                {"key": "played", "label": "M"},
                {"key": "won", "label": "W"},
                {"key": "lost", "label": "L"},
                {"key": "drawn", "label": "D"},
                {"key": "deducted", "label": "Ded"},
                {"key": "points", "label": "Pts"},
                {"key": "pct", "label": "PCT", "decimals": 2},
            ],
            "teams": [
                {
                    "key": team,
                    "shortName": cycle.teams[team]["shortName"],
                    "fullName": cycle.teams[team]["fullName"],
                    "color": cycle.teams[team].get("color", "#2d405f"),
                    "textColor": cycle.teams[team].get("textColor", "#ffffff"),
                }
                for team in cycle.teams
            ],
            "tiebreakers": [
                "Percentage of points (PCT)",
                "Series wins",
                "Away PCT",
                "ICC Test ranking at the end of the competition window",
            ],
            "rankings": {"order": list(cycle.rankings), "asOf": cycle.rankings_as_of, "source": cycle.rankings_source} if cycle.rankings else None,
            "testsTotal": sum(1 for f in cycle.fixtures if f.counts),
            "testsLeft": len(remaining),
            "seasonStart": cycle.season_start.isoformat(),
            "seasonEnd": cycle.season_end.isoformat(),
            "rules": config.get("rules"),
            "deductions": [
                {"team": d.team, "points": d.points, "test": d.test, "note": d.note, "source": d.source} for d in cycle.deductions
            ],
        },
        "standings": standings,
        "series": series_blocks,
        "fixtures": fixtures_out,
        "results": results_out,
        "final": final_block,
        "analysis": {
            "method": "Monte Carlo" if simulation else "Final standings",
            "simulations": simulation.simulations if simulation else 0,
            "model": "Davidson Test rating model",
            "modelNotes": model_notes,
            "probabilities": {team: probabilities(team) for team in order},
            "positions": (
                {team: [_percent(value) for value in simulation.positions[team]] for team in order}
                if simulation
                else {team: [100.0 if place == order.index(team) else 0.0 for place in range(len(order))] for team in order}
            ),
            "expectedPct": {team: _percent(simulation.pct[team]) for team in order} if simulation else None,
            "needs": needs_out,
            "swing": [
                {
                    "fixtureId": item["fixture"],
                    "series": fixtures[item["fixture"]].series,
                    "number": fixtures[item["fixture"]].number,
                    "date": fixtures[item["fixture"]].start.isoformat(),
                    "host": fixtures[item["fixture"]].host,
                    "visitor": fixtures[item["fixture"]].visitor,
                    "team": item["team"],
                    "ifHost": None if item["ifHost"] is None else _percent(item["ifHost"]),
                    "ifDraw": None if item["ifDraw"] is None else _percent(item["ifDraw"]),
                    "ifVisitor": None if item["ifVisitor"] is None else _percent(item["ifVisitor"]),
                    "swing": _percent(item["swing"]),
                }
                for item in (simulation.swing if simulation else [])
            ],
            "ratings": {
                team: round(ratings.rating.get(team, 0.0), 3) for team in order
            },
            "homeAdvantage": {country: round(ratings.home + value, 3) for country, value in sorted(ratings.home_by_country.items())},
        },
    }
    if champion or joint:
        payload["playoffs"] = {"champion": champion, "jointChampions": joint}
    return payload


def _form(cycle: Cycle, results: dict[str, Result], team: str, limit: int = 5) -> list[str]:
    fixtures = {fixture.key: fixture for fixture in cycle.fixtures}
    mine = sorted((key for key in results if team in fixtures[key].teams), key=lambda key: fixtures[key].start, reverse=True)
    return [results[key].letter(fixtures[key], team) for key in mine[:limit]]


def model_notes_for(cycle: Cycle, ratings: Ratings, settings: ModelSettings, simulation: Simulation | None, remaining: list[Fixture]) -> list[str]:
    notes = [
        "Each Test's win, draw and loss chances come from a Davidson rating model fitted on every men's Test in Cricsheet's "
        f"archive since 2001, results losing half their weight every {settings.half_life_years:g} years. Home advantage "
        "goes to the side playing in its own country, whatever the series calls home, so a neutral ground gives none.",
        "Draws are likelier between evenly matched sides, and their rate depends on the country the Test is played in and on "
        "the era: the rate is fitted on recent Tests, which are drawn far less often than in the 2000s.",
    ]
    if BACKTEST.get("tests"):
        notes.append(BACKTEST_NOTE.format(**BACKTEST))
    if simulation:
        notes.append(
            f"The remaining {len(remaining)} Test{'s are' if len(remaining) != 1 else ' is'} simulated {simulation.simulations:,} times. "
            + (
                f"Team strength drifts as the cycle goes on ({DRIFT_PER_YEAR:g} rating points per square-root year). "
                if DRIFT_PER_YEAR
                else "Ratings are held for the rest of the cycle: in the backtest, letting them drift did not improve the season odds. "
            )
            + "Teams level on PCT are split by series wins, away PCT, then the latest ICC Test ranking in the config."
        )
        notes.append(
            f"The final is played in {cycle.teams.get(cycle.final.country, {}).get('fullName', cycle.final.country) if cycle.final.country in cycle.teams else cycle.final.country}"
            f"{f' at {cycle.final.venue}' if cycle.final.venue else ''}: England would be at home, any other pair on neutral ground. "
            "A drawn or tied final makes both finalists joint champions; the reserve day is not modelled."
        )
    notes.append(
        "Exact claims (clinched, eliminated, can finish level) consider every remaining result, ties included, and the "
        "over-rate deductions already made; later deductions could still change them. The simulation does not invent future deductions."
    )
    return notes


def is_rolled(config: dict[str, Any]) -> bool:
    """The next cycle is never rolled forward: its format has to be known first."""
    return False
