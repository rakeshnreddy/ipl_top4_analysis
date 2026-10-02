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
import json
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import numpy as np

import cricsheet
from leagues import DEFAULT_LEAGUE_ID, League, TeamMeta, available_league_ids, load_league


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

REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_MONTE_CARLO_SIMULATIONS = int(os.getenv("IPL_MONTE_CARLO_SIMULATIONS", "40000"))
RANDOM_SEED = int(os.getenv("IPL_RANDOM_SEED", "20260501"))
EXACT_MAX_FIXTURES = int(os.getenv("IPL_EXACT_MAX_FIXTURES", "27"))
IMPACT_FIXTURE_WINDOW = int(os.getenv("IPL_IMPACT_FIXTURE_WINDOW", "1"))

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
    return os.getenv("CRICDATA_SERIES_ID") or os.getenv("CRICAPI_SERIES_ID")


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


def find_cricdata_series_id(session: requests.Session, api_key: str) -> str:
    explicit = cricdata_series_id()
    if explicit:
        return explicit

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
            if SEASON in name and any(
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
        points = parse_int(str(first_present(item, ("points", "pts"), wins * 2 + ties + no_result)))
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

    lower_status = status.lower()
    if "won" not in lower_status:
        return None
    for team in teams:
        meta = TEAM_META[team]
        candidates = (team.lower(), meta.short_name.lower(), meta.full_name.lower())
        if any(candidate in lower_status for candidate in candidates):
            return team
    return None


def cricdata_no_result(status: str) -> bool:
    lower_status = status.lower()
    return any(token in lower_status for token in ("no result", "no-result", "abandoned", "washed out"))


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

    completed = 0
    for item in extract_cricdata_match_rows(payload):
        teams = extract_match_teams(item)
        if not teams:
            continue
        match_no = cricdata_match_number(item)
        if match_no is not None and match_no > LEAGUE_MATCH_COUNT:
            continue

        status = clean_text(str(first_present(item, ("status", "matchStatus", "state"), "")))
        winner = cricdata_winner(item, teams, status)
        no_result = cricdata_no_result(status)
        match_ended = bool(item.get("matchEnded") or item.get("completed"))
        has_result = winner is not None or no_result
        if not has_result and not match_ended:
            continue
        if not has_result:
            continue

        left, right = teams
        table[left]["matches"] += 1
        table[right]["matches"] += 1
        completed += 1

        if winner:
            loser = right if winner == left else left
            table[winner]["wins"] += 1
            table[winner]["points"] += 2
            table[loser]["losses"] += 1
        else:
            table[left]["noResult"] += 1
            table[right]["noResult"] += 1
            table[left]["points"] += 1
            table[right]["points"] += 1

    if completed == 0:
        raise SourceValidationError("CricketData series_info did not contain completed match results")

    for row in table.values():
        row["remainingMatches"] = max(0, LEAGUE_MATCHES_PER_TEAM - row["matches"])
    return list(table.values())


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
        same_record = all(
            derived[field] == points_row[field]
            for field in ("matches", "wins", "losses", "noResult", "points")
        )
        if not same_record:
            mismatched.append(points_row["shortName"])
            continue
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
    standings = derive_cricdata_standings_from_matches(info_payload)
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
        if row["matches"] != row["wins"] + row["losses"] + row["noResult"]
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
    bad_points = [
        row
        for row in standings
        if row["points"] != (row["wins"] * 2) + row["noResult"]
    ]
    if bad_points:
        details = ", ".join(
            (
                f"{row['shortName']} points={row['points']} "
                f"expected={(row['wins'] * 2) + row['noResult']}"
            )
            for row in bad_points
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


def ranked_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    has_complete_nrr = all(isinstance(row.get("nrr"), float) for row in rows)
    has_source_rank = all(isinstance(row.get("rank"), int) and 0 < row["rank"] <= len(TEAM_META) for row in rows)
    if has_complete_nrr:
        ranked = sorted(
            rows,
            key=lambda row: (-row["points"], -row["nrr"], -row["wins"], row["fullName"]),
        )
    elif has_source_rank:
        ranked = sorted(rows, key=lambda row: row["rank"])
    else:
        ranked = sorted(rows, key=lambda row: (-row["points"], -row["wins"], row["fullName"]))
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
    return [key for key, _ in rows]


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
    final_points = states * 2 + np.array(base_points, dtype=np.int16)
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
    if len(fixtures) <= EXACT_MAX_FIXTURES:
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
            table[winner]["points"] += 2
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
    # Cricsheet can repeat a stage name (PSL has two "Eliminator" games), so use
    # the league's configured labels whenever the number of games lines up.
    labels = list(LEAGUE.playoff_stages)
    if labels and len(labels) != len(playoff_matches):
        if playoff_matches:
            warnings.append(
                f"Expected {len(labels)} playoff matches but Cricsheet has {len(playoff_matches)}; "
                "kept Cricsheet stage names."
            )
        labels = []

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
            target_runs=None,
            target_balls=None,
            innings=(),
        )
        for index, item in enumerate(LEAGUE.extra_results, start=1)
    ]


def build_cricsheet_payload(archive: Path | None = None) -> dict[str, Any]:
    """Rebuild a season from Cricsheet: final table with exact NRR, plus playoffs."""
    now = utc_now()
    if not LEAGUE.cricsheet_competition:
        raise SourceValidationError(f"{LEAGUE.id} has no Cricsheet source configured")
    archive = archive or cricsheet.fetch_archive(LEAGUE.cricsheet_competition, CRICSHEET_CACHE_DIR)
    matches = cricsheet.load_season(archive, LEAGUE.season)
    if not matches:
        raise SourceValidationError(f"Cricsheet archive has no {LEAGUE.short_name} {LEAGUE.season} matches")

    try:
        table = cricsheet.league_table(matches + extra_result_matches(), team_key)
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
                "points": row.points,
                "nrr": row.nrr,
                "rank": 0,
                "remainingMatches": max(0, LEAGUE_MATCHES_PER_TEAM - row.matches),
            }
        )
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
            ],
        },
        "league": LEAGUE.payload_block(),
        "standings": standings,
        "fixtures": [],
        "playoffs": playoffs,
        "analysis": run_analysis(standings, [], now),
    }


def write_league_index() -> None:
    """List every published league payload so the site can offer a league switcher."""
    entries = []
    for league_id in available_league_ids():
        path = DATA_DIR / f"{league_id}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        league = payload.get("league") or {}
        metadata = payload["metadata"]
        champion_key = (payload.get("playoffs") or {}).get("champion")
        champion = next((row["shortName"] for row in payload["standings"] if row["teamKey"] == champion_key), None)
        entries.append(
            {
                "id": league_id,
                "name": league.get("name", league_id),
                "shortName": league.get("shortName", league_id.upper()),
                "seasonLabel": league.get("seasonLabel", str(metadata.get("season", ""))),
                "status": metadata.get("season_status", "league_stage"),
                "champion": champion,
                "generatedAt": metadata["generated_at"],
                "path": f"data/{league_id}.json",
            }
        )
    write_json(LEAGUE_INDEX_OUTPUT, {"default": DEFAULT_LEAGUE_ID, "leagues": entries})


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
        help=f"League config id from leagues/ (repeatable), or 'all'. Default: {DEFAULT_LEAGUE_ID}.",
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


def build_league(league: League, source: str, archive: Path | None = None) -> dict[str, Any]:
    use_league(league)
    if source == "auto":
        source = "cricketdata" if league.cricketdata_series_names else "cricsheet"
    if source == "cricsheet":
        return build_cricsheet_payload(archive)
    return build_payload()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    requested = args.leagues or [DEFAULT_LEAGUE_ID]
    league_ids = available_league_ids() if "all" in requested else requested
    if args.cricsheet_archive and len(league_ids) > 1:
        raise SystemExit("--cricsheet-archive works with a single --league")

    failures = []
    for league_id in league_ids:
        try:
            payload = build_league(load_league(league_id), args.source, args.cricsheet_archive)
        except SourceValidationError as exc:
            failures.append(f"{league_id}: {exc}")
            continue
        write_json(CANONICAL_OUTPUT, payload)
    write_league_index()
    if failures:
        raise SystemExit("Some leagues failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
