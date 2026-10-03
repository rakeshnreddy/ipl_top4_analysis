"""Cricsheet adapter: completed-match results, league tables and NRR.

Cricsheet (https://cricsheet.org/) publishes ball-by-ball data for completed
matches under the Open Data Commons Attribution License (ODC-By 1.0). Any public
use must credit Cricsheet and state the licence.

Matches usually appear a day or two after they finish, so this source suits
finished seasons, backfills and NRR checks rather than same-night updates.
"""

from __future__ import annotations

import json
import time
import zipfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable

import requests


CRICSHEET_URL = "https://cricsheet.org/"
CRICSHEET_DOWNLOADS_URL = "https://cricsheet.org/downloads"
CRICSHEET_LICENSE = "ODC-By 1.0"
CRICSHEET_LICENSE_URL = "https://opendatacommons.org/licenses/by/1-0/"
REQUEST_TIMEOUT_SECONDS = 60
# Retirements are not dismissals, so they never make a side "all out".
NON_DISMISSALS = frozenset({"retired hurt", "retired not out"})


@dataclass(frozen=True)
class Innings:
    team: str
    runs: int
    legal_balls: int
    wickets: int


@dataclass(frozen=True)
class Match:
    match_id: str
    date: str
    season: str
    gender: str | None
    match_number: int | None
    stage: str | None
    teams: tuple[str, str]
    venue: str | None
    winner: str | None
    result: str | None
    super_over: bool
    method: str | None
    margin: dict[str, int]
    scheduled_overs: int
    balls_per_over: int
    target_runs: int | None
    target_balls: int | None
    innings: tuple[Innings, ...]

    @property
    def is_league(self) -> bool:
        return self.stage is None

    @property
    def scheduled_balls(self) -> int:
        return self.scheduled_overs * self.balls_per_over

    @property
    def no_result(self) -> bool:
        return self.winner is None and self.result != "tie"


@dataclass
class TableRow:
    matches: int = 0
    wins: int = 0
    losses: int = 0
    no_result: int = 0
    points: int = 0
    runs_for: int = 0
    balls_faced: int = 0
    runs_against: int = 0
    balls_bowled: int = 0
    ties: int = 0
    bonus_points: int = 0
    # Balls per scoring unit for NRR: 6 (runs per over) for every format except The Hundred.
    rate_balls: int = 6
    results: list[str] = field(default_factory=list)

    @property
    def nrr(self) -> float | None:
        if not self.balls_faced or not self.balls_bowled:
            return None
        unit = self.rate_balls
        rate = Fraction(self.runs_for * unit, self.balls_faced) - Fraction(self.runs_against * unit, self.balls_bowled)
        return round(float(rate), 3)


def archive_url(competition: str) -> str:
    return f"{CRICSHEET_DOWNLOADS_URL}/{competition}_json.zip"


def fetch_archive(
    competition: str,
    cache_dir: Path,
    max_age_hours: float = 6,
    session: requests.Session | None = None,
) -> Path:
    """Download (or reuse a fresh cached copy of) a competition's JSON archive."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{competition}_json.zip"
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return path

    response = (session or requests).get(archive_url(competition), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    partial = path.with_suffix(".part")
    partial.write_bytes(response.content)
    partial.replace(path)
    return path


def overs_to_balls(overs: float | int, balls_per_over: int = 6) -> int:
    """Convert cricket notation (16.4 = 16 overs and 4 balls) to legal balls."""
    whole = int(overs)
    return whole * balls_per_over + round((float(overs) - whole) * 10)


def summarize_innings(innings: dict[str, Any]) -> Innings:
    runs = sum((innings.get("penalty_runs") or {}).values())
    legal_balls = 0
    wickets = 0
    for over in innings.get("overs", []):
        for delivery in over.get("deliveries", []):
            runs += delivery["runs"]["total"]
            extras = delivery.get("extras") or {}
            if "wides" not in extras and "noballs" not in extras:
                legal_balls += 1
            wickets += sum(
                1 for wicket in delivery.get("wickets", []) if wicket.get("kind") not in NON_DISMISSALS
            )
    return Innings(team=innings["team"], runs=runs, legal_balls=legal_balls, wickets=wickets)


def parse_match(match_id: str, data: dict[str, Any]) -> Match:
    info = data["info"]
    event = info.get("event") or {}
    outcome = info.get("outcome") or {}
    teams = info["teams"]
    balls_per_over = int(info.get("balls_per_over") or 6)
    main_innings = [item for item in data.get("innings", []) if not item.get("super_over")][:2]
    target = main_innings[1].get("target", {}) if len(main_innings) > 1 else {}

    return Match(
        match_id=match_id,
        date=info["dates"][0],
        season=str(info.get("season")),
        gender=info.get("gender"),
        match_number=event.get("match_number"),
        stage=event.get("stage"),
        teams=(teams[0], teams[1]),
        venue=info.get("venue"),
        winner=outcome.get("winner") or outcome.get("eliminator"),
        result=outcome.get("result"),
        super_over="eliminator" in outcome,
        method=outcome.get("method"),
        margin=dict(outcome.get("by") or {}),
        scheduled_overs=int(info.get("overs") or 20),
        balls_per_over=balls_per_over,
        target_runs=target.get("runs"),
        target_balls=overs_to_balls(target["overs"], balls_per_over) if target.get("overs") is not None else None,
        innings=tuple(summarize_innings(item) for item in main_innings),
    )


def load_season(archive: Path, season: str, gender: str | None = None) -> list[Match]:
    """Parse every match in a Cricsheet zip for ``season`` (and ``gender``, for mixed archives)."""
    matches: list[Match] = []
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not name.endswith(".json"):
                continue
            data = json.loads(bundle.read(name))
            info = data.get("info", {})
            if str(info.get("season")) != season or (gender and info.get("gender") != gender):
                continue
            matches.append(parse_match(Path(name).stem, data))
    matches.sort(key=lambda item: (item.date, item.match_number or 10_000, item.match_id))
    return matches


def nrr_lines(match: Match) -> list[tuple[str, int, int]] | None:
    """Return (batting team, runs, balls) per main innings as NRR counts them.

    Follows the IPL/ICC playing conditions: no-result matches are excluded,
    super overs are ignored, a side bowled out is charged its full allocation of
    overs, and in a D/L result the side batting first is credited with the
    revised target minus one off the chasing side's allocation.
    """
    if match.no_result or len(match.innings) < 2:
        return None

    scheduled = match.scheduled_balls
    chase_quota = match.target_balls or scheduled
    first, second = match.innings

    # A side that runs out of batters is all out even with fewer than ten wickets
    # recorded (absent hurt), so without a D/L result an innings that ends early is
    # charged its full quota: the first innings always, the chase only when it lost.
    if match.method and match.target_runs is not None and match.target_balls:
        first_runs, first_balls = match.target_runs - 1, match.target_balls
    else:
        # Without D/L a reduced chase means both sides had the same reduced quota.
        first_quota = min(chase_quota, scheduled)
        first_all_out = first.wickets >= 10 or first.legal_balls < first_quota
        first_runs = first.runs
        first_balls = first_quota if first_all_out else first.legal_balls

    chase_lost = match.winner is not None and match.winner != second.team and not match.super_over
    second_all_out = second.wickets >= 10 or (chase_lost and not match.method and second.legal_balls < chase_quota)
    second_balls = chase_quota if second_all_out else second.legal_balls
    return [(first.team, first_runs, first_balls), (second.team, second.runs, second_balls)]


@dataclass(frozen=True)
class PointsRule:
    win: int = 2
    no_result: int = 1
    tie: int = 1
    # SA20-style bonus: a win earns an extra point when the winner's run rate is at
    # least this multiple of the loser's. None disables bonus points.
    bonus_run_rate_ratio: float | None = None
    # Balls per scoring unit for NRR (6 = runs per over).
    rate_balls: int = 6


def earns_bonus_point(lines: list[tuple[str, int, int]], winner: str, ratio: float) -> bool:
    by_team = {team: Fraction(runs, balls) for team, runs, balls in lines if balls}
    loser_rate = next((rate for team, rate in by_team.items() if team != winner), None)
    winner_rate = by_team.get(winner)
    if winner_rate is None or loser_rate is None:
        return False
    return winner_rate >= loser_rate * Fraction(ratio).limit_denominator(1000)


def league_table(
    matches: Iterable[Match],
    team_key: Callable[[str], str | None],
    rule: PointsRule = PointsRule(),
) -> dict[str, TableRow]:
    """Build points-table rows (with NRR) from league-stage matches."""
    rows: dict[str, TableRow] = {}

    def key_for(name: str) -> str:
        key = team_key(name)
        if not key:
            raise ValueError(f"Unknown team in Cricsheet data: {name}")
        return key

    for match in matches:
        if not match.is_league:
            continue
        left, right = (key_for(name) for name in match.teams)
        for key in (left, right):
            rows.setdefault(key, TableRow(rate_balls=rule.rate_balls)).matches += 1

        lines = nrr_lines(match)
        if match.winner:
            winner = key_for(match.winner)
            loser = right if winner == left else left
            rows[winner].wins += 1
            rows[winner].points += rule.win
            rows[loser].losses += 1
            rows[winner].results.append("W")
            rows[loser].results.append("L")
            if (
                rule.bonus_run_rate_ratio
                and lines
                and not match.super_over
                and earns_bonus_point(lines, match.winner, rule.bonus_run_rate_ratio)
            ):
                rows[winner].points += 1
                rows[winner].bonus_points += 1
        elif match.result == "tie":
            for key in (left, right):
                rows[key].ties += 1
                rows[key].points += rule.tie
                rows[key].results.append("T")
        else:
            for key in (left, right):
                rows[key].no_result += 1
                rows[key].points += rule.no_result
                rows[key].results.append("NR")

        if not lines:
            continue
        for batting_name, runs, balls in lines:
            batting = key_for(batting_name)
            bowling = right if batting == left else left
            rows[batting].runs_for += runs
            rows[batting].balls_faced += balls
            rows[bowling].runs_against += runs
            rows[bowling].balls_bowled += balls

    return rows
