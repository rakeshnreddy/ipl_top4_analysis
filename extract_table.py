#!/usr/bin/env python3
"""Generate the canonical IPL 2026 season payload.

The deployed site is static, so this script does all data fetching, validation
and projection ahead of the frontend build. Two sources are supported:

* ``cricketdata`` (default): live standings and upcoming fixtures during the season.
* ``cricsheet``: completed seasons rebuilt from Cricsheet ball-by-ball data,
  including exact NRR and playoff results.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import os
import random
import traceback
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import numpy as np

import cricsheet
import team_sports
from leagues import (
    DEFAULT_LEAGUE_ID,
    League,
    TeamMeta,
    available_league_ids,
    is_cricket,
    load_league,
    parse_league,
    read_config,
    rolled_league_ids,
)


CRICDATA_API_BASE = "https://api.cricapi.com/v1"
CRICDATA_SERIES_LIST_URL = f"{CRICDATA_API_BASE}/series"
CRICDATA_SERIES_INFO_URL = f"{CRICDATA_API_BASE}/series_info"
CRICDATA_SERIES_POINTS_URL = f"{CRICDATA_API_BASE}/series_points"
CRICDATA_SOURCE_URL = "https://cricketdata.org/"

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_PUBLIC_DIR = ROOT_DIR / "frontend" / "ipl-analyzer-frontend" / "public"
DATA_DIR = FRONTEND_PUBLIC_DIR / "data"
LEAGUE_INDEX_OUTPUT = DATA_DIR / "leagues.json"
CRICSHEET_CACHE_DIR = Path(os.getenv("CRICSHEET_CACHE_DIR", ROOT_DIR / ".cache" / "cricsheet"))
FIXTURES_CACHE_DIR = Path(os.getenv("FIXTURES_CACHE_DIR", ROOT_DIR / ".cache" / "fixtures"))
# Module that builds each non-cricket sport's payload from a rolling config.
SPORT_MODULES = {
    "football": "football",
    "american-football": "us_sports",
    "basketball": "us_sports",
    "ice-hockey": "us_sports",
    "baseball": "us_sports",
}
LIVE_STATUSES = {"league_stage", "playoffs", "in_progress", "postseason"}

REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_MONTE_CARLO_SIMULATIONS = int(os.getenv("IPL_MONTE_CARLO_SIMULATIONS", "40000"))
RANDOM_SEED = int(os.getenv("IPL_RANDOM_SEED", "20260501"))
EXACT_MAX_FIXTURES = int(os.getenv("IPL_EXACT_MAX_FIXTURES", "27"))
IMPACT_FIXTURE_WINDOW = int(os.getenv("IPL_IMPACT_FIXTURE_WINDOW", "1"))
# After a season ends, keep retrying the Cricsheet rebuild until its final is published.
# Days after a cricket season ends that the Cricsheet rebuild is retried; Cricsheet can
# take weeks to add the playoffs of smaller leagues.
FINALIZE_DAYS = 45

# The active league. use_league() swaps these so one run can build several leagues.
LEAGUE: League
SEASON: str
LEAGUE_MATCHES_PER_TEAM: int
SEASON_END_UTC: datetime
TEAM_META: dict[str, TeamMeta]
TEAM_ALIASES: dict[str, str]
LEAGUE_MATCH_COUNT: int
QUALIFICATION_SIZES: list[int]
CANONICAL_OUTPUT: Path


class SourceValidationError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_name(name: str) -> str:
    raw = clean_text(name).lower().replace("\xa0", " ")
    return clean_text(re.sub(r"[^a-z0-9 ]+", "", raw))


def use_league(league: League) -> None:
    global LEAGUE, SEASON, LEAGUE_MATCHES_PER_TEAM, SEASON_END_UTC, TEAM_META, TEAM_ALIASES
    global LEAGUE_MATCH_COUNT, QUALIFICATION_SIZES, CANONICAL_OUTPUT
    LEAGUE = league
    SEASON = league.season_label
    LEAGUE_MATCHES_PER_TEAM = league.matches_per_team
    SEASON_END_UTC = league.season_end
    TEAM_META = league.team_meta
    TEAM_ALIASES = {
        normalize_name(alias): meta.key
        for meta in league.teams
        for alias in (meta.key, meta.short_name, meta.full_name, *meta.aliases)
    }
    LEAGUE_MATCH_COUNT = league.league_match_count
    QUALIFICATION_SIZES = league.qualification_sizes
    CANONICAL_OUTPUT = DATA_DIR / f"{league.id}.json"


def team_key(name: str) -> str | None:
    raw = normalize_name(name)
    if raw in TEAM_ALIASES:
        return TEAM_ALIASES[raw]
    for alias, key in TEAM_ALIASES.items():
        if len(alias) > 3 and (alias in raw or raw in alias):
            return key
    return None


use_league(load_league(DEFAULT_LEAGUE_ID))


def numeric_token(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", clean_text(value)))


def parse_int(value: str) -> int:
    return int(float(clean_text(value)))


def parse_float(value: str) -> float:
    return float(clean_text(value).replace("+", ""))


def parse_match_number(text: str) -> int | None:
    match = re.search(r"\b(\d+)(?:st|nd|rd|th)\s+Match\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_fixture_teams(text: str) -> tuple[str, str] | None:
    cleaned = clean_text(text)
    if " vs " not in cleaned:
        return None
    before_match_no = re.split(r"\b\d+(?:st|nd|rd|th)\s+Match\b", cleaned, flags=re.I)[0]
    before_status = before_match_no.split(" - ")[0]
    parts = [clean_text(part) for part in before_status.split(" vs ", 1)]
    if len(parts) != 2:
        return None
    left = team_key(parts[0])
    right = team_key(parts[1])
    if not left or not right or left == right:
        return None
    return left, right


def first_present(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def cricdata_api_key() -> str | None:
    return os.getenv("CRICDATA_API_KEY") or os.getenv("CRICAPI_KEY")


def cricdata_series_id() -> str | None:
    """A fixed series id: the league config first, then the env var, which only means the default season."""
    if LEAGUE.cricketdata_series_id:
        return LEAGUE.cricketdata_series_id
    if LEAGUE.id == DEFAULT_LEAGUE_ID:
        return os.getenv("CRICDATA_SERIES_ID") or os.getenv("CRICAPI_SERIES_ID")
    return None


def fetch_cricdata_json(
    session: requests.Session,
    endpoint: str,
    api_key: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{CRICDATA_API_BASE}/{endpoint}"
    query = {"apikey": api_key}
    if params:
        query.update(params)

    response = session.get(url, params=query, timeout=REQUEST_TIMEOUT_SECONDS)
    if not response.ok:
        raise SourceValidationError(f"CricketData {endpoint} returned HTTP {response.status_code}")

    payload = response.json()
    status = payload.get("status")
    if isinstance(status, str) and status.lower() not in {"success", "ok"}:
        reason = payload.get("reason") or payload.get("message") or f"status={status}"
        raise SourceValidationError(f"CricketData {endpoint} returned {reason}")
    return payload


def is_womens_series(name: str) -> bool:
    return bool(re.search(r"\bwomens?\b", normalize_name(name)))


def find_cricdata_series_id(session: requests.Session, api_key: str) -> str:
    explicit = cricdata_series_id()
    if explicit:
        return explicit

    # "Big Bash League" also matches "Women's Big Bash League": a men's league skips women's series.
    womens = LEAGUE.gender == "female" or any(is_womens_series(series) for series in LEAGUE.cricketdata_series_names)
    candidates: list[dict[str, Any]] = []
    for offset in range(0, 100, 25):
        payload = fetch_cricdata_json(session, "series", api_key, {"offset": offset})
        data = payload.get("data", [])
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            name = normalize_name(str(item.get("name", "")))
            if is_womens_series(name) and not womens:
                continue
            # Normalised on both sides, so "2026-27" also matches "2026/27".
            if normalize_name(SEASON) in name and any(
                re.search(rf"\b{re.escape(normalize_name(series))}\b", name)
                for series in LEAGUE.cricketdata_series_names
            ):
                candidates.append(item)

    if not candidates:
        raise SourceValidationError(
            f"Could not discover CricketData {LEAGUE.short_name} {SEASON} series id. Set CRICDATA_SERIES_ID."
        )

    return str(first_present(candidates[0], ("id", "series_id", "seriesId")))


def nested_lists(value: Any):
    if isinstance(value, list):
        yield value
        for item in value:
            yield from nested_lists(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from nested_lists(item)


def extract_cricdata_points_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for rows in nested_lists(payload.get("data")):
        dict_rows = [row for row in rows if isinstance(row, dict)]
        if not dict_rows:
            continue
        if any(
            first_present(row, ("teamname", "teamName", "team", "team_name", "name")) is not None
            and first_present(row, ("matches", "match", "played", "all")) is not None
            and first_present(row, ("wins", "won", "w")) is not None
            for row in dict_rows
        ):
            return dict_rows
    raise SourceValidationError("CricketData points payload did not contain a standings table")


def parse_cricdata_standings(
    payload: dict[str, Any],
    nrr_overrides: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    standings: list[dict[str, Any]] = []
    for idx, item in enumerate(extract_cricdata_points_rows(payload), start=1):
        raw_name = first_present(item, ("teamname", "teamName", "team", "team_name", "name"), "")
        mapped = team_key(str(raw_name))
        if not mapped:
            continue

        nrr_raw = first_present(item, ("nrr", "netRunRate", "net_run_rate"))
        nrr = nrr_overrides.get(mapped) if nrr_overrides and mapped in nrr_overrides else None
        if nrr_raw not in (None, ""):
            try:
                nrr = parse_float(str(nrr_raw))
            except ValueError:
                nrr = None

        matches = parse_int(str(first_present(item, ("matches", "match", "played", "all"), 0)))
        wins = parse_int(str(first_present(item, ("wins", "won", "w"), 0)))
        losses = parse_int(str(first_present(item, ("losses", "loss", "lost", "l"), max(0, matches - wins))))
        ties = parse_int(str(first_present(item, ("ties", "tied", "tie"), 0)))
        no_result = parse_int(str(first_present(item, ("nr", "noResult", "no_result", "noresult"), 0)))
        default_points = wins * LEAGUE.points_win + ties * LEAGUE.points_tie + no_result * LEAGUE.points_no_result
        points = parse_int(str(first_present(item, ("points", "pts"), default_points)))
        rank = parse_int(str(first_present(item, ("rank", "pos", "position"), idx)))
        meta = TEAM_META[mapped]

        standings.append(
            {
                "teamKey": meta.key,
                "shortName": meta.short_name,
                "fullName": meta.full_name,
                "matches": matches,
                "wins": wins,
                "losses": losses,
                "noResult": no_result,
                "points": points,
                "nrr": nrr,
                "rank": rank,
                "remainingMatches": max(0, LEAGUE_MATCHES_PER_TEAM - matches),
            }
        )

    return sorted(standings, key=lambda row: row["rank"])


def normalize_cricdata_datetime(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return iso_utc(dt)


def extract_match_teams(item: dict[str, Any]) -> tuple[str, str] | None:
    teams = item.get("teams")
    if isinstance(teams, list) and len(teams) >= 2:
        left = team_key(str(teams[0]))
        right = team_key(str(teams[1]))
        if left and right and left != right:
            return left, right

    team_info = item.get("teamInfo")
    if isinstance(team_info, list) and len(team_info) >= 2:
        names = [
            first_present(team, ("name", "shortname", "shortName"), "")
            for team in team_info
            if isinstance(team, dict)
        ]
        if len(names) >= 2:
            left = team_key(str(names[0]))
            right = team_key(str(names[1]))
            if left and right and left != right:
                return left, right

    direct_pairs = (
        ("teamA", "teamB"),
        ("homeTeam", "awayTeam"),
        ("homeTeamName", "awayTeamName"),
        ("homeTeamShortName", "awayTeamShortName"),
    )
    for left_key, right_key in direct_pairs:
        left = team_key(str(item.get(left_key, "")))
        right = team_key(str(item.get(right_key, "")))
        if left and right and left != right:
            return left, right

    name = str(first_present(item, ("name", "matchName"), ""))
    return parse_fixture_teams(name)


def extract_cricdata_match_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for rows in nested_lists(payload.get("data")):
        dict_rows = [row for row in rows if isinstance(row, dict)]
        if not dict_rows:
            continue
        if any(extract_match_teams(row) for row in dict_rows):
            return dict_rows
    return []


def cricdata_match_number(item: dict[str, Any]) -> int | None:
    raw_name = str(first_present(item, ("name", "matchName"), ""))
    match_no = first_present(item, ("matchNumber", "matchNo", "match_no"))
    if match_no not in (None, "") and numeric_token(str(match_no)):
        return parse_int(str(match_no))
    return parse_match_number(raw_name)


def cricdata_winner(item: dict[str, Any], teams: tuple[str, str], status: str) -> str | None:
    winner_raw = first_present(item, ("winner", "winningTeam", "matchWinner"))
    if winner_raw:
        winner = team_key(str(winner_raw))
        if winner in teams:
            return winner

    lower_status = normalize_name(status)
    if "won" not in lower_status:
        return None
    for team in teams:
        meta = TEAM_META[team]
        # Aliases too, without punctuation: CricketData writes "Central Districts won" for the
        # Central Stags and "Durbans Super Giants won" for Durban's Super Giants.
        candidates = {normalize_name(name) for name in (team, meta.short_name, meta.full_name, *meta.aliases)} - {""}
        # Whole words only: short names such as "CK" or "OV" hide in "wickets" and "Super Over".
        if any(re.search(rf"\b{re.escape(candidate)}\b", lower_status) for candidate in candidates):
            return team
    return None


def cricdata_no_result(status: str) -> bool:
    lower_status = status.lower()
    return any(token in lower_status for token in ("no result", "no-result", "abandoned", "washed out"))


def cricdata_tie(status: str) -> bool:
    """A tie that stands (The Hundred, Super Smash); a Super Over winner is found first."""
    return bool(re.search(r"\btied\b", status.lower()))


def derive_cricdata_standings_from_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    table = {
        meta.key: {
            "teamKey": meta.key,
            "shortName": meta.short_name,
            "fullName": meta.full_name,
            "matches": 0,
            "wins": 0,
            "losses": 0,
            "noResult": 0,
            "points": 0,
            "nrr": None,
            "rank": 999,
            "remainingMatches": LEAGUE_MATCHES_PER_TEAM,
        }
        for meta in TEAM_META.values()
    }

    rows = extract_cricdata_match_rows(payload)
    if not rows:
        raise SourceValidationError("CricketData series_info did not list any matches")

    for item in rows:
        teams = extract_match_teams(item)
        if not teams:
            continue
        match_no = cricdata_match_number(item)
        if match_no is not None and match_no > LEAGUE_MATCH_COUNT:
            continue

        status = clean_text(str(first_present(item, ("status", "matchStatus", "state"), "")))
        winner = cricdata_winner(item, teams, status)
        tie = winner is None and cricdata_tie(status)
        no_result = cricdata_no_result(status)
        match_ended = bool(item.get("matchEnded") or item.get("completed"))
        has_result = winner is not None or tie or no_result
        if not has_result and not match_ended:
            continue
        if not has_result:
            continue

        left, right = teams
        table[left]["matches"] += 1
        table[right]["matches"] += 1

        if winner:
            loser = right if winner == left else left
            table[winner]["wins"] += 1
            table[winner]["points"] += LEAGUE.points_win
            table[loser]["losses"] += 1
        elif tie:
            for key in teams:
                table[key]["ties"] = table[key].get("ties", 0) + 1
                table[key]["points"] += LEAGUE.points_tie
        else:
            table[left]["noResult"] += 1
            table[right]["noResult"] += 1
            table[left]["points"] += LEAGUE.points_no_result
            table[right]["points"] += LEAGUE.points_no_result

    for row in table.values():
        row["remainingMatches"] = max(0, LEAGUE_MATCHES_PER_TEAM - row["matches"])
    return list(table.values())


def apply_deductions(standings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Take configured points deductions off the league-stage totals."""
    by_key = {row["teamKey"]: row for row in standings}
    for item in LEAGUE.deductions:
        row = by_key[item.team]
        row["points"] -= item.points
        row["deductedPoints"] = row.get("deductedPoints", 0) + item.points
    return standings


def apply_cricdata_nrr_from_points(
    standings: list[dict[str, Any]],
    points_payload: dict[str, Any],
    warnings: list[str],
) -> None:
    by_key = {row["teamKey"]: row for row in standings}
    try:
        points_rows = parse_cricdata_standings(points_payload)
    except SourceValidationError as exc:
        warnings.append(f"CricketData points table could not be used for NRR: {exc}")
        return

    attached = 0
    mismatched: list[str] = []
    for points_row in points_rows:
        derived = by_key.get(points_row["teamKey"])
        if not derived:
            continue
        # Bonus points can't be derived from match results, so for bonus leagues the
        # official points total is taken from the table once the W/L/NR record agrees.
        fields = ("matches", "wins", "losses", "noResult") + (() if LEAGUE.has_bonus_points else ("points",))
        if not all(derived[field] == points_row[field] for field in fields):
            mismatched.append(points_row["shortName"])
            continue
        bonus = points_row["points"] - derived["points"]
        if LEAGUE.has_bonus_points and bonus >= 0:
            derived["points"] = points_row["points"]
            derived["bonusPoints"] = bonus
        if points_row.get("nrr") is not None:
            derived["nrr"] = points_row["nrr"]
            attached += 1

    if mismatched:
        warnings.append(
            "CricketData points table record did not match match results for "
            f"{', '.join(mismatched)}; standings were derived from match results."
        )

def parse_cricdata_fixtures(payload: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []

    for item in extract_cricdata_match_rows(payload):
        teams = extract_match_teams(item)
        if not teams:
            continue

        status = clean_text(str(first_present(item, ("status", "matchStatus", "state"), ""))).lower()
        has_result = bool(first_present(item, ("winner", "winningTeam", "matchWinner", "matchResult", "result")))
        match_started = bool(item.get("matchStarted") or item.get("started"))
        match_ended = bool(item.get("matchEnded") or item.get("completed"))
        date_iso = normalize_cricdata_datetime(first_present(item, ("dateTimeGMT", "dateTimeGmt", "matchdate")))

        is_future_date = False
        if date_iso:
            is_future_date = datetime.fromisoformat(date_iso.replace("Z", "+00:00")) >= now

        if has_result or match_ended or (match_started and not is_future_date):
            continue
        if status and not any(token in status for token in ("not started", "upcoming", "scheduled")) and not is_future_date:
            continue

        match_no_int = cricdata_match_number(item)

        fixtures.append(
            {
                "id": str(first_present(item, ("id", "matchId", "match_id"), f"cricdata-{len(fixtures) + 1}")),
                "matchNo": match_no_int,
                "teamA": teams[0],
                "teamB": teams[1],
                "dateTimeGMT": date_iso,
                "dateTimeLocal": None,
                "venue": first_present(item, ("venue", "ground", "stadium")),
                "status": "scheduled",
                "sourceUrl": CRICDATA_SERIES_INFO_URL,
            }
        )

    fixtures.sort(key=lambda item: (item["dateTimeGMT"] or "", item["matchNo"] or 999))
    return fixtures


def fetch_cricdata_data(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if not LEAGUE.cricketdata_series_names:
        raise SourceValidationError(f"{LEAGUE.id} has no CricketData source configured")
    api_key = cricdata_api_key()
    if not api_key:
        raise SourceValidationError("CRICDATA_API_KEY is not configured")

    session = requests.Session()
    series_id = find_cricdata_series_id(session, api_key)
    info_payload = fetch_cricdata_json(session, "series_info", api_key, {"offset": 0, "id": series_id})

    warnings: list[str] = []
    standings = apply_deductions(derive_cricdata_standings_from_matches(info_payload))
    # Before the first result there is no points table or NRR to read.
    if any(row["matches"] for row in standings):
        try:
            points_payload = fetch_cricdata_json(session, "series_points", api_key, {"id": series_id})
            apply_cricdata_nrr_from_points(standings, points_payload, warnings)
        except SourceValidationError as exc:
            warnings.append(f"CricketData points table could not be used for NRR: {exc}")
        missing_nrr = [row["shortName"] for row in standings if row.get("nrr") is None]
        if missing_nrr:
            warnings.append(
                "CricketData did not provide usable NRR for "
                f"{', '.join(missing_nrr)}; probabilities were generated without NRR."
            )
    fixtures = parse_cricdata_fixtures(info_payload, now)
    return standings, fixtures, warnings


def expected_remaining_fixture_count(standings: list[dict[str, Any]]) -> int:
    return sum(row["remainingMatches"] for row in standings) // 2


def validate_source_data(
    standings: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    now: datetime,
    strict_zero_fixtures: bool,
    strict_partial_fixtures: bool = False,
) -> None:
    if len(standings) != len(TEAM_META):
        raise SourceValidationError(f"Expected {len(TEAM_META)} teams, found {len(standings)}")
    keys = {row["teamKey"] for row in standings}
    missing = sorted(set(TEAM_META) - keys)
    if missing:
        raise SourceValidationError(f"Missing teams in standings: {', '.join(missing)}")
    too_many = [row for row in standings if row["matches"] > LEAGUE_MATCHES_PER_TEAM]
    if too_many:
        details = ", ".join(f"{row['shortName']}={row['matches']}" for row in too_many)
        raise SourceValidationError(f"Invalid match counts above {LEAGUE_MATCHES_PER_TEAM}: {details}")
    bad_row_totals = [
        row
        for row in standings
        if row["matches"] != row["wins"] + row["losses"] + row["noResult"] + row.get("ties", 0)
    ]
    if bad_row_totals:
        details = ", ".join(
            (
                f"{row['shortName']} matches={row['matches']} "
                f"W-L-NR={row['wins']}-{row['losses']}-{row['noResult']}"
            )
            for row in bad_row_totals
        )
        raise SourceValidationError(f"Invalid standings row totals: {details}")
    def expected_points(row: dict[str, Any]) -> int:
        return (
            row["wins"] * LEAGUE.points_win
            + row["noResult"] * LEAGUE.points_no_result
            + row.get("ties", 0) * LEAGUE.points_tie
            + row.get("bonusPoints", 0)
            - row.get("deductedPoints", 0)
        )

    bad_points = [row for row in standings if row["points"] != expected_points(row)]
    if bad_points:
        details = ", ".join(
            f"{row['shortName']} points={row['points']} expected={expected_points(row)}" for row in bad_points
        )
        raise SourceValidationError(f"Invalid standings points totals: {details}")
    bad_remaining = [
        row
        for row in standings
        if row["remainingMatches"] != max(0, LEAGUE_MATCHES_PER_TEAM - row["matches"])
    ]
    if bad_remaining:
        details = ", ".join(
            (
                f"{row['shortName']} remaining={row['remainingMatches']} "
                f"expected={max(0, LEAGUE_MATCHES_PER_TEAM - row['matches'])}"
            )
            for row in bad_remaining
        )
        raise SourceValidationError(f"Invalid remaining-match totals: {details}")
    total_wins = sum(row["wins"] for row in standings)
    total_losses = sum(row["losses"] for row in standings)
    if total_wins != total_losses:
        raise SourceValidationError(
            f"Inconsistent league result totals: wins={total_wins}, losses={total_losses}"
        )
    total_no_results = sum(row["noResult"] for row in standings)
    if total_no_results % 2 != 0:
        raise SourceValidationError(f"Inconsistent no-result total: {total_no_results}")
    expected_remaining = expected_remaining_fixture_count(standings)
    if strict_zero_fixtures and now < SEASON_END_UTC and expected_remaining > 0 and not fixtures:
        raise SourceValidationError("No future fixtures found before league-stage end")
    if (
        strict_partial_fixtures
        and now < SEASON_END_UTC
        and expected_remaining > 0
        and len(fixtures) < expected_remaining
    ):
        raise SourceValidationError(
            f"Fixture feed appears partial: found {len(fixtures)} scheduled match(es), "
            f"but standings imply about {expected_remaining} league match(es) remaining."
        )


def seed_order(order: list[str]) -> list[str]:
    """Team keys in seed order. Without groups that is the table order; with groups, the
    group winners come first (in table order), then the second-placed teams, and so on.
    """
    if not LEAGUE.groups:
        return order
    group_of = LEAGUE.team_group
    filled: dict[str, int] = {}
    place: dict[str, int] = {}
    for key in order:
        filled[group_of[key]] = filled.get(group_of[key], 0) + 1
        place[key] = filled[group_of[key]]
    position = {key: index for index, key in enumerate(order)}
    return sorted(order, key=lambda key: (place[key], position[key]))


def ranked_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    has_complete_nrr = all(isinstance(row.get("nrr"), float) for row in rows)
    # A feed's rank means little across groups, so group stages are ranked on points.
    has_source_rank = not LEAGUE.groups and all(
        isinstance(row.get("rank"), int) and 0 < row["rank"] <= len(TEAM_META) for row in rows
    )
    if has_complete_nrr:
        ranked = sorted(
            rows,
            key=lambda row: (-row["points"], -row["nrr"], -row["wins"], row["fullName"]),
        )
    elif has_source_rank:
        ranked = sorted(rows, key=lambda row: row["rank"])
    else:
        ranked = sorted(rows, key=lambda row: (-row["points"], -row["wins"], row["fullName"]))
    if LEAGUE.groups:
        by_key = {row["teamKey"]: row for row in ranked}
        group_of = LEAGUE.team_group
        for row in ranked:
            row["group"] = group_of[row["teamKey"]]
            row["groupRank"] = 1 + sum(1 for other in ranked[: ranked.index(row)] if group_of[other["teamKey"]] == row["group"])
        ranked = [by_key[key] for key in seed_order(list(by_key))]
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def simulation_rank(table: dict[str, dict[str, Any]]) -> list[str]:
    rows = list(table.items())
    rows.sort(
        key=lambda item: (
            -item[1]["points"],
            -(item[1].get("nrr") or 0.0),
            -item[1]["wins"],
            TEAM_META[item[0]].full_name,
        )
    )
    return seed_order([key for key, _ in rows])


def fixture_label(fixture: dict[str, Any]) -> str:
    match_no = fixture.get("matchNo")
    prefix = f"M{match_no}: " if match_no else ""
    return f"{prefix}{TEAM_META[fixture['teamA']].short_name} vs {TEAM_META[fixture['teamB']].short_name}"


def top_share_matrix(points: np.ndarray, wins: np.ndarray, target: int) -> np.ndarray:
    shares = np.zeros(points.shape, dtype=np.float32)
    for team_idx in range(points.shape[1]):
        team_points = points[:, team_idx : team_idx + 1]
        team_wins = wins[:, team_idx : team_idx + 1]
        ahead = ((points > team_points) | ((points == team_points) & (wins > team_wins))).sum(axis=1)
        tied = ((points == team_points) & (wins == team_wins)).sum(axis=1)
        slots = target - ahead
        shares[:, team_idx] = np.where(
            slots <= 0,
            0.0,
            np.where(slots >= tied, 1.0, slots / tied),
        )
    return shares


def build_state_counts(
    fixture_pairs: list[tuple[str, str]],
    team_index: dict[str, int],
    team_count: int,
    forced_outcomes: dict[int, int] | None = None,
) -> dict[tuple[int, ...], int]:
    state_counts: dict[tuple[int, ...], int] = {tuple([0] * team_count): 1}
    forced_outcomes = forced_outcomes or {}

    for fixture_idx, (left_key, right_key) in enumerate(fixture_pairs):
        left = team_index[left_key]
        right = team_index[right_key]
        outcomes = (forced_outcomes[fixture_idx],) if fixture_idx in forced_outcomes else (0, 1)
        next_counts: dict[tuple[int, ...], int] = {}

        for state, count in state_counts.items():
            for outcome in outcomes:
                mutable = list(state)
                mutable[left if outcome == 0 else right] += 1
                next_state = tuple(mutable)
                next_counts[next_state] = next_counts.get(next_state, 0) + count

        state_counts = next_counts

    return state_counts


def top_share_for_state(points: list[int], wins: list[int], target: int) -> list[float]:
    shares: list[float] = []
    for team_idx, team_points in enumerate(points):
        team_wins = wins[team_idx]
        ahead = sum(
            1
            for other_idx, other_points in enumerate(points)
            if other_points > team_points
            or (other_points == team_points and wins[other_idx] > team_wins)
        )
        tied = sum(
            1
            for other_idx, other_points in enumerate(points)
            if other_points == team_points and wins[other_idx] == team_wins
        )
        slots = target - ahead
        if slots <= 0:
            shares.append(0.0)
        elif slots >= tied:
            shares.append(1.0)
        else:
            shares.append(slots / tied)
    return shares


def accumulate_exact_state_counts(
    state_counts: dict[tuple[int, ...], int],
    base_points: list[int],
    base_wins: list[int],
    own_remaining: dict[str, int],
    team_keys: list[str],
    include_buckets: bool,
) -> dict[str, Any]:
    team_count = len(team_keys)
    target_sizes = {str(size): size for size in QUALIFICATION_SIZES}
    states = np.array(list(state_counts.keys()), dtype=np.int16)
    counts = np.array(list(state_counts.values()), dtype=np.float64)
    count_ints = counts.astype(np.int64)
    final_wins = states + np.array(base_wins, dtype=np.int16)
    final_points = states * LEAGUE.points_win + np.array(base_points, dtype=np.int16)
    weighted_totals = {target: [0.0] * team_count for target in target_sizes}
    exact_totals = {target: [0] * team_count for target in target_sizes}
    possible_totals = {target: [0] * team_count for target in target_sizes}
    own_buckets: dict[str, dict[str, dict[str, list[float | int]]]] = {}

    if include_buckets:
        own_buckets = {
            target: {
                key: {
                    "total": [0] * (own_remaining[key] + 1),
                    "weighted": [0.0] * (own_remaining[key] + 1),
                    "possible": [0] * (own_remaining[key] + 1),
                    "guaranteed": [0] * (own_remaining[key] + 1),
                }
                for key in team_keys
            }
            for target in target_sizes
        }

    for target, target_size in target_sizes.items():
        shares = top_share_matrix(final_points, final_wins, target_size)
        weighted_totals[target] = (shares * counts[:, None]).sum(axis=0).tolist()
        exact_totals[target] = ((shares >= 1.0) * counts[:, None]).sum(axis=0).astype(np.int64).tolist()
        possible_totals[target] = ((shares > 0.0) * counts[:, None]).sum(axis=0).astype(np.int64).tolist()

        if include_buckets:
            for team_idx, key in enumerate(team_keys):
                minlength = own_remaining[key] + 1
                wins_added = states[:, team_idx]
                bucket = own_buckets[target][key]
                bucket["total"] = np.bincount(wins_added, weights=count_ints, minlength=minlength)[:minlength].astype(np.int64).tolist()
                bucket["weighted"] = np.bincount(
                    wins_added,
                    weights=counts * shares[:, team_idx],
                    minlength=minlength,
                )[:minlength].tolist()
                bucket["possible"] = np.bincount(
                    wins_added,
                    weights=count_ints * (shares[:, team_idx] > 0.0),
                    minlength=minlength,
                )[:minlength].astype(np.int64).tolist()
                bucket["guaranteed"] = np.bincount(
                    wins_added,
                    weights=count_ints * (shares[:, team_idx] >= 1.0),
                    minlength=minlength,
                )[:minlength].astype(np.int64).tolist()

    return {
        "weightedTotals": weighted_totals,
        "exactTotals": exact_totals,
        "possibleTotals": possible_totals,
        "ownBuckets": own_buckets,
    }


def run_exact_dp_analysis(
    standings_rows: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    team_keys = [row["teamKey"] for row in standings_rows]
    team_count = len(team_keys)
    team_index = {key: idx for idx, key in enumerate(team_keys)}
    fixture_pairs = [(item["teamA"], item["teamB"]) for item in fixtures]
    fixture_count = len(fixture_pairs)
    total_scenarios = 2**fixture_count
    base_points = [row["points"] for row in standings_rows]
    base_wins = [row["wins"] for row in standings_rows]
    own_remaining = {
        key: sum(1 for left, right in fixture_pairs if key in (left, right))
        for key in team_keys
    }

    state_counts = build_state_counts(fixture_pairs, team_index, team_count)
    accumulated = accumulate_exact_state_counts(
        state_counts,
        base_points,
        base_wins,
        own_remaining,
        team_keys,
        include_buckets=True,
    )

    targets = [str(size) for size in QUALIFICATION_SIZES]
    overall: dict[str, dict[str, float]] = {}
    for team_idx, key in enumerate(team_keys):
        overall[key] = {}
        for prefix, totals in (("", "weightedTotals"), ("Clear", "exactTotals"), ("Possible", "possibleTotals")):
            for target in targets:
                share = accumulated[totals][target][team_idx] / total_scenarios
                overall[key][f"top{target}{prefix}"] = round(share * 100, 2)

    impact_fixture_count = min(len(fixtures), IMPACT_FIXTURE_WINDOW)
    fixture_impacts: dict[str, dict[str, list[list[dict[str, Any]]]]] = {
        target: {key: [] for key in team_keys}
        for target in targets
    }

    for fixture_idx, fixture in enumerate(fixtures[:impact_fixture_count]):
        left_counts = build_state_counts(fixture_pairs, team_index, team_count, {fixture_idx: 0})
        right_counts = build_state_counts(fixture_pairs, team_index, team_count, {fixture_idx: 1})
        left_total = 2 ** (fixture_count - 1)
        right_total = 2 ** (fixture_count - 1)
        left_acc = accumulate_exact_state_counts(
            left_counts,
            base_points,
            base_wins,
            own_remaining,
            team_keys,
            include_buckets=False,
        )
        right_acc = accumulate_exact_state_counts(
            right_counts,
            base_points,
            base_wins,
            own_remaining,
            team_keys,
            include_buckets=False,
        )

        for target in targets:
            for team_idx, key in enumerate(team_keys):
                left_avg = left_acc["weightedTotals"][target][team_idx] / left_total
                right_avg = right_acc["weightedTotals"][target][team_idx] / right_total
                diff = left_avg - right_avg
                if abs(diff) < 0.0001:
                    preferred = "neutral"
                    preferred_label = "Either result"
                elif diff > 0:
                    preferred = fixture["teamA"]
                    preferred_label = f"{TEAM_META[fixture['teamA']].short_name} beat {TEAM_META[fixture['teamB']].short_name}"
                else:
                    preferred = fixture["teamB"]
                    preferred_label = f"{TEAM_META[fixture['teamB']].short_name} beat {TEAM_META[fixture['teamA']].short_name}"
                fixture_impacts[target][key].append(
                    {
                        "fixtureId": fixture["id"],
                        "matchNo": fixture.get("matchNo"),
                        "label": fixture_label(fixture),
                        "teamA": fixture["teamA"],
                        "teamB": fixture["teamB"],
                        "preferredWinner": preferred,
                        "preferredLabel": preferred_label,
                        "teamAWinProbability": round(left_avg * 100, 2),
                        "teamBWinProbability": round(right_avg * 100, 2),
                        "impact": round(abs(diff) * 100, 2),
                    }
                )

    team_analysis: dict[str, dict[str, Any]] = {target: {} for target in targets}
    qualification_path: dict[str, dict[str, Any]] = {target: {} for target in targets}
    scenario_breakdown: dict[str, dict[str, Any]] = {target: {} for target in targets}

    for target in targets:
        for team_idx, key in enumerate(team_keys):
            bucket = accumulated["ownBuckets"][target][key]
            rows = []
            possible = None
            likely = None
            guaranteed = None
            for wins_added in range(own_remaining[key] + 1):
                total = int(bucket["total"][wins_added])
                if total == 0:
                    continue
                probability = float(bucket["weighted"][wins_added] / total)
                possible_rate = float(bucket["possible"][wins_added] / total)
                guaranteed_rate = float(bucket["guaranteed"][wins_added] / total)
                if possible is None and possible_rate > 0:
                    possible = wins_added
                if likely is None and probability >= 0.5:
                    likely = wins_added
                if guaranteed is None and guaranteed_rate >= 1.0:
                    guaranteed = wins_added
                rows.append(
                    {
                        "wins": wins_added,
                        "scenarios": total,
                        "probability": round(probability * 100, 2),
                        "possibleRate": round(possible_rate * 100, 2),
                        "guaranteedRate": round(guaranteed_rate * 100, 2),
                    }
                )

            impacts = sorted(fixture_impacts[target][key], key=lambda item: item["impact"], reverse=True)
            result_outcomes = {
                item["label"]: {
                    "Outcome": item["preferredLabel"],
                    "Impact": item["impact"],
                }
                for item in impacts[:12]
            }

            team_analysis[target][key] = {
                "percentage": overall[key][f"top{target}"],
                "results_df": result_outcomes,
            }
            qualification_path[target][key] = {
                "possible": possible,
                "likely": likely,
                "guaranteed": guaranteed,
                "target_matches": own_remaining[key],
                "method": "Exact all-combinations",
                "ownWinBuckets": rows,
                "fixtureImpacts": impacts[:12],
                "nextFixtureImpacts": fixture_impacts[target][key],
                "impactFixtureWindow": impact_fixture_count,
            }
            scenario_breakdown[target][key] = {
                "clearRate": overall[key][f"top{target}Clear"],
                "possibleRate": overall[key][f"top{target}Possible"],
                "sharedTieAdjustedRate": overall[key][f"top{target}"],
                "ownWinBuckets": rows,
                "fixtureImpacts": impacts[:12],
            }

    return {
        "method": "Exact all-combinations",
        "simulationCount": total_scenarios,
        "generatedAt": iso_utc(now),
        "stateCount": len(state_counts),
        "modelNotes": [
            "Every remaining fixture winner combination is evaluated exactly through a compressed final-state dynamic program.",
            "Future NRR movement is excluded; teams tied on points and wins share open top-N slots fractionally.",
            "Teams with identical records can have different probabilities because remaining fixtures and direct rival games change the exact scenario tree.",
            "Current NRR is displayed when the source provides it; probability math does not require NRR.",
            f"Fixture-impact guidance is computed for the next {impact_fixture_count} fixture(s).",
        ],
        "overallProbabilities": overall,
        "teamAnalysis": team_analysis,
        "qualificationPath": qualification_path,
        "scenarioBreakdown": scenario_breakdown,
    }


def final_table_analysis(standings_rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Qualification once the league stage is over: decided by the final ranked table."""
    targets = [str(size) for size in QUALIFICATION_SIZES]
    overall: dict[str, dict[str, float]] = {}
    team_analysis: dict[str, dict[str, Any]] = {target: {} for target in targets}
    qualification_path: dict[str, dict[str, Any]] = {target: {} for target in targets}
    scenario_breakdown: dict[str, dict[str, Any]] = {target: {} for target in targets}

    for row in standings_rows:
        key = row["teamKey"]
        overall[key] = {}
        for target in targets:
            value = 100.0 if row["rank"] <= int(target) else 0.0
            for prefix in ("", "Clear", "Possible"):
                overall[key][f"top{target}{prefix}"] = value
            settled = 0 if value else None
            team_analysis[target][key] = {"percentage": value, "results_df": {}}
            qualification_path[target][key] = {
                "possible": settled,
                "likely": settled,
                "guaranteed": settled,
                "target_matches": 0,
                "method": "Final standings",
                "ownWinBuckets": [],
                "fixtureImpacts": [],
                "nextFixtureImpacts": [],
                "impactFixtureWindow": 0,
            }
            scenario_breakdown[target][key] = {
                "clearRate": value,
                "possibleRate": value,
                "sharedTieAdjustedRate": value,
                "ownWinBuckets": [],
                "fixtureImpacts": [],
            }

    return {
        "method": "Final standings",
        "simulationCount": 1,
        "generatedAt": iso_utc(now),
        "stateCount": 1,
        "modelNotes": [
            "The league stage is complete, so qualification is decided by the final table: points, then net run rate.",
        ],
        "overallProbabilities": overall,
        "teamAnalysis": team_analysis,
        "qualificationPath": qualification_path,
        "scenarioBreakdown": scenario_breakdown,
    }


def run_analysis(
    standings_rows: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    league_complete = all(row["remainingMatches"] == 0 for row in standings_rows)
    has_nrr = all(isinstance(row.get("nrr"), float) for row in standings_rows)
    if not fixtures and league_complete and has_nrr:
        return final_table_analysis(standings_rows, now)
    # Without NRR, teams level on points and wins keep sharing slots fractionally.
    # Bonus points are random per win, which the exact solver cannot express; nor can it
    # rank teams within groups, so group stages are always sampled.
    if (
        len(fixtures) <= EXACT_MAX_FIXTURES
        and not (LEAGUE.bonus_simulation_rate or LEAGUE.bonus_loser_simulation_rate)
        and not LEAGUE.groups
    ):
        return run_exact_dp_analysis(standings_rows, fixtures, now)

    team_keys = [row["teamKey"] for row in standings_rows]
    base = {
        row["teamKey"]: {
            "matches": row["matches"],
            "wins": row["wins"],
            "points": row["points"],
            "nrr": row["nrr"],
        }
        for row in standings_rows
    }
    fixture_pairs = [(item["teamA"], item["teamB"]) for item in fixtures]
    fixture_labels = [f"{left} vs {right}" for left, right in fixture_pairs]

    # Too many fixtures for the exact solver: sample outcomes instead.
    random.seed(RANDOM_SEED)
    simulation_count = DEFAULT_MONTE_CARLO_SIMULATIONS
    scenario_iterable = [
        tuple(random.randint(0, 1) for _ in fixture_pairs)
        for _ in range(simulation_count)
    ]
    method = "Monte Carlo"

    targets = [str(size) for size in QUALIFICATION_SIZES]
    top_counts = {key: {target: 0 for target in targets} for key in team_keys}
    team_analysis_counts: dict[str, dict[str, dict[str, list[int]]]] = {
        key: {
            target: {label: [0, 0] for label in fixture_labels}
            for target in targets
        }
        for key in team_keys
    }
    own_win_buckets = {
        key: {target: {} for target in targets}
        for key in team_keys
    }

    for scenario in scenario_iterable:
        table = {key: dict(values) for key, values in base.items()}
        own_wins = {key: 0 for key in team_keys}
        for idx, outcome in enumerate(scenario):
            left, right = fixture_pairs[idx]
            winner, loser = (left, right) if outcome == 0 else (right, left)
            table[winner]["wins"] += 1
            table[winner]["points"] += LEAGUE.points_win
            if LEAGUE.bonus_simulation_rate and random.random() < LEAGUE.bonus_simulation_rate:
                table[winner]["points"] += 1
            if LEAGUE.bonus_loser_simulation_rate and random.random() < LEAGUE.bonus_loser_simulation_rate:
                table[loser]["points"] += 1
            table[winner]["matches"] += 1
            table[loser]["matches"] += 1
            own_wins[winner] += 1

        ordered = simulation_rank(table)
        qualified_sets = {target: set(ordered[: int(target)]) for target in targets}

        for key in team_keys:
            for target in targets:
                qualified = key in qualified_sets[target]
                bucket = own_win_buckets[key][target].setdefault(
                    own_wins[key], {"total": 0, "qualified": 0}
                )
                bucket["total"] += 1
                if qualified:
                    bucket["qualified"] += 1
                    top_counts[key][target] += 1
                    for idx, outcome in enumerate(scenario):
                        team_analysis_counts[key][target][fixture_labels[idx]][outcome] += 1

    overall = {}
    team_analysis: dict[str, dict[str, Any]] = {target: {} for target in targets}
    qualification_path: dict[str, dict[str, Any]] = {target: {} for target in targets}

    for key in team_keys:
        overall[key] = {
            f"top{target}": round((top_counts[key][target] / simulation_count) * 100, 2) for target in targets
        }
        own_remaining = sum(1 for left, right in fixture_pairs if key in (left, right))
        for target in targets:
            success_count = top_counts[key][target]
            outcomes = {}
            if success_count:
                for label, counts in team_analysis_counts[key][target].items():
                    left_wins, right_wins = counts
                    if left_wins == right_wins:
                        outcome = "Result does not matter"
                    else:
                        left, right = label.split(" vs ")
                        outcome = f"{left if left_wins > right_wins else right} wins"
                    outcomes[label] = {"Outcome": outcome}
            team_analysis[target][key] = {
                "percentage": round((success_count / simulation_count) * 100, 2),
                "results_df": outcomes,
            }

            possible = None
            guaranteed = None
            for wins in range(own_remaining + 1):
                bucket = own_win_buckets[key][target].get(wins)
                if not bucket:
                    continue
                if possible is None and bucket["qualified"] > 0:
                    possible = wins
                if guaranteed is None and bucket["qualified"] == bucket["total"]:
                    guaranteed = wins
            qualification_path[target][key] = {
                "possible": possible,
                "guaranteed": guaranteed,
                "target_matches": own_remaining,
                "method": method,
            }

    return {
        "method": method,
        "simulationCount": simulation_count,
        "generatedAt": iso_utc(now),
        "overallProbabilities": overall,
        "teamAnalysis": team_analysis,
        "qualificationPath": qualification_path,
    }


def league_stage_fixtures(
    fixtures: list[dict[str, Any]],
    standings: list[dict[str, Any]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    """Drop fixtures that cannot be league matches, such as playoffs.

    Feeds list playoff games next to league games; simulating them as league
    fixtures awards points the playoffs never give.
    """
    remaining = {row["teamKey"]: row["remainingMatches"] for row in standings}
    kept = [
        fixture
        for fixture in fixtures
        if remaining.get(fixture["teamA"], 0) > 0
        and remaining.get(fixture["teamB"], 0) > 0
        and (fixture.get("matchNo") is None or fixture["matchNo"] <= LEAGUE_MATCH_COUNT)
    ]
    if len(kept) < len(fixtures):
        warnings.append(
            f"Ignored {len(fixtures) - len(kept)} non-league fixture(s), such as playoffs, from the fixture feed."
        )
    expected = expected_remaining_fixture_count(standings)
    if len(kept) > expected:
        raise SourceValidationError(
            f"Fixture feed lists {len(kept)} league match(es), but standings imply only {expected} remain."
        )
    return kept


def build_payload() -> dict[str, Any]:
    now = utc_now()
    standings, fixtures, warnings = fetch_cricdata_data(now)
    standings = ranked_standings(standings)
    validate_source_data(
        standings,
        fixtures,
        now,
        strict_zero_fixtures=True,
        strict_partial_fixtures=True,
    )
    fixtures = league_stage_fixtures(fixtures, standings, warnings)
    league_complete = expected_remaining_fixture_count(standings) == 0

    if not fixtures and not league_complete and now < SEASON_END_UTC:
        warnings.append("No future fixtures were found; probabilities are current-table only.")

    analysis = run_analysis(standings, fixtures, now)
    freshness = "fresh" if not warnings else "warning"

    return {
        "metadata": {
            "season": SEASON,
            "generated_at": iso_utc(now),
            "source": "CricketData",
            "source_url": CRICDATA_SOURCE_URL,
            "data_freshness_status": freshness,
            "season_status": "playoffs" if league_complete else "league_stage",
            "warnings": warnings,
        },
        "league": LEAGUE.payload_block(),
        "standings": standings,
        "fixtures": fixtures,
        "analysis": analysis,
    }


def describe_result(match: cricsheet.Match, winner: str | None) -> str:
    if winner is None:
        return "No result"
    short_name = TEAM_META[winner].short_name
    if match.super_over:
        return f"{short_name} won the Super Over"
    if "runs" in match.margin:
        runs = match.margin["runs"]
        text = f"{short_name} won by {runs} run{'' if runs == 1 else 's'}"
    elif "wickets" in match.margin:
        wickets = match.margin["wickets"]
        text = f"{short_name} won by {wickets} wicket{'' if wickets == 1 else 's'}"
    else:
        text = f"{short_name} won"
    return f"{text} ({match.method})" if match.method else text


def build_playoffs(matches: list[cricsheet.Match], warnings: list[str]) -> dict[str, Any]:
    playoff_matches = [match for match in matches if not match.is_league]
    # Cricsheet can repeat a stage name (PSL has two "Eliminator" games). Only then
    # are the league's configured labels used, matched by date order; unique
    # Cricsheet names are kept because two playoff games can share a date.
    stages = [match.stage for match in playoff_matches]
    labels = list(LEAGUE.playoff_stages) if len(set(stages)) < len(stages) else []
    if labels and len(labels) != len(playoff_matches):
        warnings.append(
            f"Expected {len(labels)} playoff matches but Cricsheet has {len(playoff_matches)}; "
            "kept Cricsheet stage names."
        )
        labels = []
    elif not labels and LEAGUE.playoff_stages and playoff_matches and len(stages) != len(LEAGUE.playoff_stages):
        warnings.append(f"Expected {len(LEAGUE.playoff_stages)} playoff matches but Cricsheet has {len(stages)}.")

    rows: list[dict[str, Any]] = []
    champion = None
    runner_up = None
    for index, match in enumerate(playoff_matches):
        stage = labels[index] if labels else match.stage
        team_a, team_b = (team_key(name) for name in match.teams)
        if not team_a or not team_b:
            raise SourceValidationError(f"Unknown team in Cricsheet playoff match {match.match_id}")
        winner = team_key(match.winner) if match.winner else None
        rows.append(
            {
                "id": match.match_id,
                "stage": stage,
                "date": match.date,
                "teamA": team_a,
                "teamB": team_b,
                "winner": winner,
                "result": describe_result(match, winner),
                "venue": match.venue,
            }
        )
        if stage == "Final" and winner:
            champion = winner
            runner_up = team_b if winner == team_a else team_a
    return {"matches": rows, "champion": champion, "runnerUp": runner_up}


def extra_result_matches() -> list[cricsheet.Match]:
    """League matches with no Cricsheet file (abandoned before a ball), recorded as no results."""
    return [
        cricsheet.Match(
            match_id=f"extra-{index}",
            date=item.date,
            season=LEAGUE.season,
            match_number=None,
            stage=None,
            teams=item.teams,
            venue=None,
            winner=None,
            result="no result",
            super_over=False,
            method=None,
            margin={},
            scheduled_overs=20,
            balls_per_over=6,
            gender=LEAGUE.gender,
            target_runs=None,
            target_balls=None,
            innings=(),
        )
        for index, item in enumerate(LEAGUE.extra_results, start=1)
    ]


def with_targets(matches: list[cricsheet.Match]) -> list[cricsheet.Match]:
    """Add the configured targets of shortened matches whose Cricsheet file has none.

    NRR needs a shortened match's overs (and its D/L target); the 2026 Blast files omit both.
    """
    pending = list(LEAGUE.targets)
    filled = []
    for match in matches:
        teams = {team_key(name) for name in match.teams}
        item = next((item for item in pending if item.date == match.date and {team_key(name) for name in item.teams} == teams), None)
        if item:
            pending.remove(item)
            if match.target_runs is None:
                match = dataclasses.replace(match, target_runs=item.runs, target_balls=item.overs * match.balls_per_over)
        filled.append(match)
    if pending:
        missing = ", ".join(f"{item.teams[0]} v {item.teams[1]} ({item.date})" for item in pending)
        raise SourceValidationError(f"Configured targets match no Cricsheet match: {missing}")
    return filled


def build_cricsheet_payload(archive: Path | None = None) -> dict[str, Any]:
    """Rebuild a season from Cricsheet: final table with exact NRR, plus playoffs."""
    now = utc_now()
    if not LEAGUE.cricsheet_competition:
        raise SourceValidationError(f"{LEAGUE.id} has no Cricsheet source configured")
    archive = archive or cricsheet.fetch_archive(LEAGUE.cricsheet_competition, CRICSHEET_CACHE_DIR)
    matches = with_targets(cricsheet.load_season(archive, LEAGUE.season, gender=LEAGUE.gender))
    if not matches:
        raise SourceValidationError(f"Cricsheet archive has no {LEAGUE.short_name} {LEAGUE.season} matches")

    try:
        rule = cricsheet.PointsRule(
            win=LEAGUE.points_win,
            no_result=LEAGUE.points_no_result,
            tie=LEAGUE.points_tie,
            bonus_run_rate_ratio=LEAGUE.bonus_run_rate_ratio,
            rate_balls=LEAGUE.nrr_balls_per_unit,
            bonus_runs=LEAGUE.bonus_runs,
            bonus_chase_run_rate_ratio=LEAGUE.bonus_chase_run_rate_ratio,
        )
        table = cricsheet.league_table(matches + extra_result_matches(), team_key, rule)
    except ValueError as exc:
        raise SourceValidationError(str(exc)) from exc

    standings = []
    for key, meta in TEAM_META.items():
        row = table.get(key, cricsheet.TableRow())
        standings.append(
            {
                "teamKey": key,
                "shortName": meta.short_name,
                "fullName": meta.full_name,
                "matches": row.matches,
                "wins": row.wins,
                "losses": row.losses,
                "noResult": row.no_result,
                "ties": row.ties,
                "bonusPoints": row.bonus_points,
                "points": row.points,
                "nrr": row.nrr,
                "rank": 0,
                "remainingMatches": max(0, LEAGUE_MATCHES_PER_TEAM - row.matches),
            }
        )
    standings = apply_deductions(standings)
    validate_source_data(standings, [], now, strict_zero_fixtures=False)
    if expected_remaining_fixture_count(standings):
        raise SourceValidationError(
            "Cricsheet only publishes completed matches and the league stage is still in progress; "
            "use --source cricketdata for live fixtures."
        )

    standings = ranked_standings(standings)
    warnings: list[str] = []
    playoffs = build_playoffs(matches, warnings)
    return {
        "metadata": {
            "season": SEASON,
            "generated_at": iso_utc(now),
            "source": "Cricsheet",
            "source_url": cricsheet.CRICSHEET_URL,
            "source_license": cricsheet.CRICSHEET_LICENSE,
            "source_license_url": cricsheet.CRICSHEET_LICENSE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": "complete" if playoffs["champion"] else "playoffs",
            "warnings": warnings,
            "notes": [
                f"{item.teams[0]} v {item.teams[1]} ({item.date}): {item.note}" for item in LEAGUE.extra_results
            ]
            + [f"{TEAM_META[item.team].full_name}: {item.points} points deducted ({item.note})" for item in LEAGUE.deductions],
        },
        "league": LEAGUE.payload_block(),
        "standings": standings,
        "fixtures": [],
        "playoffs": playoffs,
        "analysis": run_analysis(standings, [], now),
    }


def chance_text(value: float) -> str:
    """The site's rounding: a Monte Carlo estimate is never printed as a certainty."""
    if value >= 99.95:
        return ">99.9%"
    if value > 99:
        return f"{value:.1f}%"
    if value >= 1:
        return f"{round(value)}%"
    if value >= 0.1:
        return f"{value:.1f}%"
    return "<0.1%" if value > 0 else "0%"


def league_facts(payload: dict[str, Any], champion: str | None) -> list[dict[str, str]]:
    """One or two headline numbers for the home page's league cards (none if the payload is unusual)."""
    try:
        return _league_facts(payload, champion)
    except (KeyError, IndexError, TypeError, ValueError):
        return []


def _league_facts(payload: dict[str, Any], champion: str | None) -> list[dict[str, str]]:
    league = payload["league"]
    status = payload["metadata"].get("season_status")
    short = {row["teamKey"]: row["shortName"] for row in payload["standings"]}
    if status == "complete":
        return [{"label": "Champions", "value": champion}] if champion else []

    if league.get("sport", "cricket") == "cricket":
        tier = (league.get("qualification") or [{"size": 4, "label": "Top 4"}])[0]
        odds = {team: values.get(f"top{tier['size']}", 0.0) for team, values in payload["analysis"]["overallProbabilities"].items()}
        if not any(row["matches"] for row in payload["standings"]):
            first = payload["fixtures"][0]["dateTimeGMT"] if payload["fixtures"] and payload["fixtures"][0].get("dateTimeGMT") else None
            return [{"label": "Season starts", "value": first[:10]}] if first else []
        likely = sorted(odds, key=lambda team: -odds[team])[: tier["size"]]
        names = ", ".join(short.get(team, team) for team in likely)
        if status == "playoffs":
            return [{"label": "In the playoffs", "value": names}]
        facts = [{"label": f"Likely {tier['label']}", "value": names}]
        bubble = min(odds, key=lambda team: abs(odds[team] - 50))
        if 1 < odds[bubble] < 99:
            facts.append({"label": "On the bubble", "value": f"{short.get(bubble, bubble)} {chance_text(odds[bubble])}"})
        return facts

    probabilities = payload["analysis"]["probabilities"]
    live = [tier for tier in league["tiers"] if not tier.get("settled")]
    facts = []
    favourite = next((tier for tier in live if tier.get("kind") == "champion"), None) or next((tier for tier in live if tier.get("size") == 1), None)
    if favourite:
        team = max(probabilities, key=lambda key: probabilities[key].get(favourite["key"], 0.0))
        facts.append({"label": f"{favourite['label']} favourite", "value": f"{short.get(team, team)} {chance_text(probabilities[team][favourite['key']])}"})
    risk = next((tier for tier in live if tier.get("kind") == "bottom"), None)
    if risk:
        team = max(probabilities, key=lambda key: probabilities[key].get(risk["key"], 0.0))
        facts.append({"label": f"{risk['label']} risk", "value": f"{short.get(team, team)} {chance_text(probabilities[team][risk['key']])}"})
    else:
        # A playoff race, or else the first table-place race wider than one place (the European cups' top 8).
        race = next((tier for tier in live if tier.get("kind") == "playoffs"), None) or next(
            (tier for tier in live if tier.get("kind") == "top" and tier.get("size", 0) > 1), None
        )
        if race:
            team = min(probabilities, key=lambda key: abs(probabilities[key].get(race["key"], 0.0) - 50))
            if 1 < probabilities[team][race["key"]] < 99:
                facts.append({"label": f"{race['label']} bubble", "value": f"{short.get(team, team)} {chance_text(probabilities[team][race['key']])}"})
    return facts[:2]


def index_entry(payload: dict[str, Any]) -> dict[str, Any]:
    league = payload["league"]
    metadata = payload["metadata"]
    complete = metadata.get("season_status") == "complete"
    champion_key = (payload.get("playoffs") or {}).get("champion")
    if not champion_key and complete and league.get("sport") == "football" and payload["standings"]:
        # A football league's champion tops the table; other sports name theirs in "playoffs".
        champion_key = payload["standings"][0]["teamKey"]
    champion = next((row["shortName"] for row in payload["standings"] if row["teamKey"] == champion_key), None)
    return {
        "id": league["id"],
        "sport": league.get("sport", "cricket"),
        "name": league.get("name", league["id"]),
        "shortName": league.get("shortName", league["id"].upper()),
        "seasonLabel": league.get("seasonLabel", str(metadata.get("season", ""))),
        "status": metadata.get("season_status", "league_stage"),
        "champion": champion,
        "started": any(row.get("played", row.get("matches", 0)) for row in payload["standings"]),
        "facts": league_facts(payload, champion),
        "generatedAt": metadata["generated_at"],
        "path": f"data/{league['id']}.json",
    }


def write_league_index() -> None:
    """List every published payload so the site can offer a league switcher."""
    found = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == LEAGUE_INDEX_OUTPUT.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if "id" not in (payload.get("league") or {}):
            continue
        found.append(payload)

    # In-season leagues first, then by priority, then the newest season first.
    found.sort(key=lambda item: str(item["league"].get("season", "")), reverse=True)
    found.sort(
        key=lambda item: (
            0 if item["metadata"].get("season_status") in LIVE_STATUSES else 1,
            item["league"].get("priority", 100),
        )
    )
    entries = [index_entry(payload) for payload in found]
    write_json(
        LEAGUE_INDEX_OUTPUT,
        {"default": default_league_id(entries), "ipl": newest_ipl_id(entries), "leagues": entries},
    )


HUB_ID = "hub"


def newest_ipl_id(entries: list[dict[str, Any]]) -> str:
    ipl = [entry for entry in entries if entry["sport"] == "cricket" and entry["shortName"] == "IPL"]
    return max(ipl, key=lambda entry: entry["seasonLabel"])["id"] if ipl else DEFAULT_LEAGUE_ID


def default_league_id(entries: list[dict[str, Any]]) -> str:
    """The home page: the IPL while its season is on, otherwise the all-sports hub."""
    live_ipl = [
        entry
        for entry in entries
        if entry["sport"] == "cricket" and entry["shortName"] == "IPL" and entry["status"] in ("league_stage", "playoffs")
    ]
    return max(live_ipl, key=lambda entry: entry["seasonLabel"])["id"] if live_ipl else HUB_ID


def published_payload(league_id: str) -> dict[str, Any] | None:
    path = DATA_DIR / f"{league_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def published_status(league_id: str) -> str | None:
    payload = published_payload(league_id)
    return payload["metadata"].get("season_status") if payload else None


def probability_movement(previous: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Change in each team's playoff-tier chance since the previously published payload.

    If no match has finished since then, the previous movement still describes the
    latest change, so it is carried forward instead of reporting zeros.
    """
    if not previous or (previous.get("league") or {}).get("id") != payload["league"]["id"]:
        return None

    def matches_played(data: dict[str, Any]) -> int:
        return sum(row["matches"] for row in data.get("standings", []))

    if matches_played(previous) == matches_played(payload):
        return previous.get("movement")

    tier = f"top{QUALIFICATION_SIZES[0]}"
    before = previous.get("analysis", {}).get("overallProbabilities", {})
    changes = {
        team: round(values[tier] - before[team][tier], 2)
        for team, values in payload["analysis"]["overallProbabilities"].items()
        if tier in values and tier in before.get(team, {})
    }
    return {"since": previous["metadata"]["generated_at"], "tier": tier, "changes": changes} if changes else None


def league_plan(now: datetime) -> list[tuple[str, str]]:
    """Leagues to build now: in-season ones live, recently finished cricket from Cricsheet."""
    plan = []
    # Cricket competitions roll forward a season at a time once their newest config is over.
    for league_id in available_league_ids() + rolled_league_ids(now, FINALIZE_DAYS):
        config = read_config(league_id)
        if not is_cricket(config):
            if team_sports.resolve_season(config, now).contains(now):
                plan.append((league_id, "feed"))
            continue
        league = parse_league(config)
        if league.season_start and league.season_start <= now <= league.season_end:
            if league.cricketdata_series_names:
                plan.append((league_id, "cricketdata"))
        elif league.season_end < now <= league.season_end + timedelta(days=FINALIZE_DAYS):
            if published_status(league_id) != "complete":
                plan.append((league_id, "cricsheet"))
    return plan


VOLATILE_FIELDS = (("metadata", "generated_at"), ("analysis", "generatedAt"))


def same_content(previous: dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    """True when only timestamps differ, so a day without games writes nothing."""
    if previous is None:
        return False

    def stripped(data: dict[str, Any]) -> dict[str, Any]:
        copy = json.loads(json.dumps(data))
        for section, field in VOLATILE_FIELDS:
            (copy.get(section) or {}).pop(field, None)
        return copy

    return stripped(previous) == stripped(payload)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate league season payloads for the site.")
    parser.add_argument(
        "--league",
        action="append",
        dest="leagues",
        metavar="ID",
        help=(
            "League config id from leagues/ (repeatable), 'all', or 'active' for leagues in season "
            f"or awaiting their final Cricsheet rebuild. Default: {DEFAULT_LEAGUE_ID}."
        ),
    )
    parser.add_argument(
        "--source",
        choices=("auto", "cricketdata", "cricsheet"),
        default="auto",
        help="auto uses CricketData when the league has it configured, otherwise Cricsheet.",
    )
    parser.add_argument(
        "--cricsheet-archive",
        type=Path,
        help="Use a local Cricsheet JSON zip instead of downloading it (single league only).",
    )
    return parser.parse_args(argv)


def build_league(league_id: str, source: str, archive: Path | None = None) -> dict[str, Any]:
    config = read_config(league_id)
    if not is_cricket(config):
        # A config can name its own engine (European cups are football with a knockout bracket).
        module = importlib.import_module(config.get("engine") or SPORT_MODULES[config["sport"]])
        return module.build_payload(config, utc_now(), FIXTURES_CACHE_DIR)
    league = parse_league(config)
    use_league(league)
    if source == "auto":
        source = "cricketdata" if league.cricketdata_series_names else "cricsheet"
    if source == "cricsheet":
        return build_cricsheet_payload(archive)
    return build_payload()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    requested = args.leagues or [DEFAULT_LEAGUE_ID]
    active = "active" in requested
    if active:
        builds = league_plan(utc_now())
        if not builds:
            print("No league is in season or awaiting its final rebuild; nothing to build.")
            return
    else:
        league_ids = available_league_ids() if "all" in requested else requested
        builds = [(league_id, args.source) for league_id in league_ids]
    if args.cricsheet_archive and (active or len(builds) > 1):
        raise SystemExit("--cricsheet-archive works with a single --league")

    failures = []
    succeeded = 0
    for league_id, source in builds:
        try:
            payload = build_league(league_id, source, args.cricsheet_archive)
        except (SourceValidationError, team_sports.FeedError) as exc:
            if active and source == "cricsheet":
                # Cricsheet lags a few days; keep the live payload and retry tomorrow.
                print(f"{league_id}: final rebuild not possible yet ({exc})")
                continue
            # One broken source should not stop the other leagues; GitHub shows this as an annotation.
            print(f"::warning::{league_id}: {exc}")
            failures.append(f"{league_id}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            # Neither should a source changing its format or a bug in one sport's code.
            traceback.print_exc()
            print(f"::warning::{league_id}: unexpected {type(exc).__name__}: {exc}")
            failures.append(f"{league_id}: unexpected {type(exc).__name__}: {exc}")
            continue
        succeeded += 1
        payload_id = payload["league"]["id"]
        previous = published_payload(payload_id)
        if active and source == "cricsheet" and payload["metadata"].get("season_status") != "complete":
            if previous is not None:
                # Keep the published page (often the live one) until Cricsheet has the final.
                print(f"{league_id}: Cricsheet does not have the final yet; retrying on the next run")
                continue
            # Nothing published yet: the league table and playoff results so far beat no page.
            print(f"{league_id}: publishing the season so far; Cricsheet does not have the final yet")
        if payload["metadata"].get("season_status") != "complete":
            if payload["league"].get("sport", "cricket") == "cricket":
                payload["movement"] = probability_movement(previous, payload)
            else:
                payload["movement"] = team_sports.probability_movement(previous, payload)
        if same_content(previous, payload):
            print(f"{payload_id}: unchanged")
            continue
        write_json(DATA_DIR / f"{payload_id}.json", payload)
    write_league_index()
    # A nightly run fails only when nothing could be built; single-league problems stay warnings.
    if failures and (not active or not succeeded):
        raise SystemExit("Some leagues failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
