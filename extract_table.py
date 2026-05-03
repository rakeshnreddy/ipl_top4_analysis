#!/usr/bin/env python3
"""Generate canonical IPL 2026 data and legacy JSON files.

The deployed site is static, so this script does all data fetching, validation,
projection, and JSON compatibility output ahead of the frontend build.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
import numpy as np


SEASON = 2026
LEAGUE_MATCHES_PER_TEAM = 14
SEASON_END_UTC = datetime(SEASON, 5, 31, 23, 59, tzinfo=timezone.utc)
CRICBUZZ_TABLE_URL = (
    "https://www.cricbuzz.com/cricket-series/9241/"
    "indian-premier-league-2026/points-table"
)
CRICBUZZ_MATCHES_URL = (
    "https://www.cricbuzz.com/cricket-series/9241/"
    "indian-premier-league-2026/matches"
)
CRICDATA_API_BASE = "https://api.cricapi.com/v1"
CRICDATA_SERIES_LIST_URL = f"{CRICDATA_API_BASE}/series"
CRICDATA_SERIES_INFO_URL = f"{CRICDATA_API_BASE}/series_info"
CRICDATA_SERIES_POINTS_URL = f"{CRICDATA_API_BASE}/series_points"
CRICDATA_SOURCE_URL = "https://cricketdata.org/"

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_PUBLIC_DIR = ROOT_DIR / "frontend" / "ipl-analyzer-frontend" / "public"
CANONICAL_OUTPUT = FRONTEND_PUBLIC_DIR / "data" / "ipl-2026.json"
ROOT_CANONICAL_OUTPUT = ROOT_DIR / "ipl-2026.json"
ROOT_STANDINGS_OUTPUT = ROOT_DIR / "current_standings.json"
ROOT_FIXTURES_OUTPUT = ROOT_DIR / "remaining_fixtures.json"
ROOT_ANALYSIS_OUTPUT = ROOT_DIR / "analysis_results.json"
PUBLIC_STANDINGS_OUTPUT = FRONTEND_PUBLIC_DIR / "current_standings.json"
PUBLIC_FIXTURES_OUTPUT = FRONTEND_PUBLIC_DIR / "remaining_fixtures.json"
PUBLIC_ANALYSIS_OUTPUT = FRONTEND_PUBLIC_DIR / "analysis_results.json"

REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_MONTE_CARLO_SIMULATIONS = int(os.getenv("IPL_MONTE_CARLO_SIMULATIONS", "40000"))
RANDOM_SEED = int(os.getenv("IPL_RANDOM_SEED", "20260501"))
EXACT_MAX_FIXTURES = int(os.getenv("IPL_EXACT_MAX_FIXTURES", "27"))
IMPACT_FIXTURE_WINDOW = int(os.getenv("IPL_IMPACT_FIXTURE_WINDOW", "1"))


@dataclass(frozen=True)
class TeamMeta:
    key: str
    short_name: str
    full_name: str


TEAM_META: dict[str, TeamMeta] = {
    "Chennai": TeamMeta("Chennai", "CSK", "Chennai Super Kings"),
    "Delhi": TeamMeta("Delhi", "DC", "Delhi Capitals"),
    "Gujarat": TeamMeta("Gujarat", "GT", "Gujarat Titans"),
    "Kolkata": TeamMeta("Kolkata", "KKR", "Kolkata Knight Riders"),
    "Lucknow": TeamMeta("Lucknow", "LSG", "Lucknow Super Giants"),
    "Mumbai": TeamMeta("Mumbai", "MI", "Mumbai Indians"),
    "Punjab": TeamMeta("Punjab", "PBKS", "Punjab Kings"),
    "Rajasthan": TeamMeta("Rajasthan", "RR", "Rajasthan Royals"),
    "Bangalore": TeamMeta("Bangalore", "RCB", "Royal Challengers Bengaluru"),
    "Hyderabad": TeamMeta("Hyderabad", "SRH", "Sunrisers Hyderabad"),
}


TEAM_ALIASES: dict[str, str] = {}
for meta in TEAM_META.values():
    TEAM_ALIASES[meta.key.lower()] = meta.key
    TEAM_ALIASES[meta.short_name.lower()] = meta.key
    TEAM_ALIASES[meta.full_name.lower()] = meta.key
TEAM_ALIASES.update(
    {
        "royal challengers bangalore": "Bangalore",
        "royal challengers bengaluru": "Bangalore",
        "rc bengaluru": "Bangalore",
        "sunrisers hyderabad": "Hyderabad",
        "sunrisers": "Hyderabad",
        "punjab kings": "Punjab",
        "pbks": "Punjab",
    }
)


class SourceValidationError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def team_key(name: str) -> str | None:
    raw = clean_text(name).lower()
    raw = raw.replace("\xa0", " ").strip()
    raw = re.sub(r"[^a-z0-9 ]+", "", raw)
    raw = clean_text(raw)
    if raw in TEAM_ALIASES:
        return TEAM_ALIASES[raw]
    for alias, key in TEAM_ALIASES.items():
        if len(alias) > 3 and (alias in raw or raw in alias):
            return key
    return None


def numeric_token(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", clean_text(value)))


def parse_int(value: str) -> int:
    return int(float(clean_text(value)))


def parse_float(value: str) -> float:
    return float(clean_text(value).replace("+", ""))


def text_tokens(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [clean_text(t) for t in soup.stripped_strings if clean_text(t)]


def parse_cricbuzz_standings(html: str) -> list[dict[str, Any]]:
    """Parse Cricbuzz's accessible text table.

    Expected row shape after the header:
    rank, team, P, W, L, NR, Pts, NRR
    """
    tokens = text_tokens(html)
    try:
        start = next(
            idx
            for idx in range(len(tokens) - 5)
            if tokens[idx : idx + 6] == ["Teams", "P", "W", "L", "NR", "Pts"]
        )
    except StopIteration as exc:
        raise SourceValidationError("Could not find Cricbuzz points table header") from exc

    idx = start + 7
    standings: list[dict[str, Any]] = []

    while idx < len(tokens) - 6 and len(standings) < len(TEAM_META):
        if not tokens[idx].isdigit():
            idx += 1
            continue

        rank = parse_int(tokens[idx])
        mapped_key = team_key(tokens[idx + 1])
        stat_tokens = tokens[idx + 2 : idx + 8]
        if not mapped_key or len(stat_tokens) < 6 or not all(
            numeric_token(token) for token in stat_tokens[:5]
        ):
            idx += 1
            continue

        played = parse_int(stat_tokens[0])
        wins = parse_int(stat_tokens[1])
        losses = parse_int(stat_tokens[2])
        no_result = parse_int(stat_tokens[3])
        points = parse_int(stat_tokens[4])
        nrr = parse_float(stat_tokens[5])
        meta = TEAM_META[mapped_key]
        standings.append(
            {
                "teamKey": meta.key,
                "shortName": meta.short_name,
                "fullName": meta.full_name,
                "matches": played,
                "wins": wins,
                "losses": losses,
                "noResult": no_result,
                "points": points,
                "nrr": nrr,
                "rank": rank,
                "remainingMatches": max(0, LEAGUE_MATCHES_PER_TEAM - played),
            }
        )
        idx += 8

    return sorted(standings, key=lambda row: row["rank"])


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


def parse_cricbuzz_fixtures(html: str, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    fixtures_by_pair: dict[tuple[str, str], dict[str, Any]] = {}

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", ""))
        label = clean_text(anchor.get_text(" "))
        if "live-cricket" not in href and "/cricket-match-facts/" not in href:
            continue
        if not label or " vs " not in label.lower():
            continue
        status_text = label.lower()
        if any(word in status_text for word in [" won", " live", " result", " abandoned"]):
            continue
        teams = parse_fixture_teams(label)
        if not teams:
            continue
        match_no = parse_match_number(label)
        pair_key = (teams[0], teams[1])
        existing = fixtures_by_pair.get(pair_key)
        if existing and (existing["matchNo"] is not None or match_no is None):
            continue
        path = href if href.startswith("http") else f"https://www.cricbuzz.com{href}"
        fixtures_by_pair[pair_key] = {
            "id": f"cricbuzz-{match_no or len(fixtures_by_pair) + 1}",
            "matchNo": match_no,
            "teamA": teams[0],
            "teamB": teams[1],
            "dateTimeGMT": None,
            "dateTimeLocal": None,
            "venue": None,
            "status": "scheduled",
            "sourceUrl": path or source_url,
        }

    fixtures = list(fixtures_by_pair.values())
    fixtures.sort(key=lambda item: (item["matchNo"] or 999, item["teamA"], item["teamB"]))
    return fixtures


def enrich_fixture_from_match_page(fixture: dict[str, Any], html: str) -> dict[str, Any]:
    tokens = text_tokens(html)
    joined = " ".join(tokens)
    lower_joined = joined.lower()

    if "match starts at" not in lower_joined and re.search(r"\b[a-z]{2,5}\s+won\b|\bwon by\b", lower_joined):
        fixture["status"] = "completed"
        return fixture

    starts = re.search(r"Match starts at ([A-Za-z]{3} \d{2}, \d{2}:\d{2}) GMT", joined)
    if starts:
        try:
            dt = datetime.strptime(f"{starts.group(1)} {SEASON}", "%b %d, %H:%M %Y").replace(
                tzinfo=timezone.utc
            )
            fixture["dateTimeGMT"] = iso_utc(dt)
        except ValueError:
            pass

    for idx, token in enumerate(tokens):
        if token == "Venue" and idx + 1 < len(tokens):
            fixture["venue"] = tokens[idx + 1]
            break
        if token.startswith("Venue:"):
            inline = clean_text(token.replace("Venue:", ""))
            fixture["venue"] = inline or (tokens[idx + 1] if idx + 1 < len(tokens) else None)
            break

    date_time = re.search(
        r"Date & Time:\s*([^•]+?)(?:Info|Live|Scorecard|Squads|Start Time|$)",
        joined,
        re.IGNORECASE,
    )
    if date_time:
        fixture["dateTimeLocal"] = clean_text(date_time.group(1))

    return fixture


def fetch_url(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


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
            name = clean_text(str(item.get("name", "")))
            lower_name = name.lower()
            if (
                ("indian premier league" in lower_name or re.search(r"\bipl\b", lower_name))
                and str(SEASON) in lower_name
            ):
                candidates.append(item)

    if not candidates:
        raise SourceValidationError(
            "Could not discover CricketData IPL 2026 series id. Set CRICDATA_SERIES_ID."
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


def fetch_cricbuzz_standings_only() -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        }
    )
    return parse_cricbuzz_standings(fetch_url(session, CRICBUZZ_TABLE_URL))


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
            nrr = parse_float(str(nrr_raw))
        if nrr is None:
            raise SourceValidationError("CricketData standings are missing NRR")

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

        raw_name = str(first_present(item, ("name", "matchName"), ""))
        match_no = first_present(item, ("matchNumber", "matchNo", "match_no"))
        match_no_int = parse_int(str(match_no)) if match_no not in (None, "") and numeric_token(str(match_no)) else parse_match_number(raw_name)

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
    api_key = cricdata_api_key()
    if not api_key:
        raise SourceValidationError("CRICDATA_API_KEY is not configured")

    session = requests.Session()
    series_id = find_cricdata_series_id(session, api_key)
    points_payload = fetch_cricdata_json(session, "series_points", api_key, {"id": series_id})
    info_payload = fetch_cricdata_json(session, "series_info", api_key, {"offset": 0, "id": series_id})

    warnings: list[str] = []
    rows = extract_cricdata_points_rows(points_payload)
    has_nrr = all(first_present(row, ("nrr", "netRunRate", "net_run_rate")) is not None for row in rows)
    nrr_overrides: dict[str, float] = {}
    if not has_nrr:
        nrr_overrides = {row["teamKey"]: row["nrr"] for row in fetch_cricbuzz_standings_only()}
        warnings.append("CricketData standings omitted NRR; NRR was enriched from Cricbuzz.")

    standings = parse_cricdata_standings(points_payload, nrr_overrides)
    fixtures = parse_cricdata_fixtures(info_payload, now)
    validate_source_data(standings, fixtures, now, strict_zero_fixtures=True)
    return standings, fixtures, warnings


def fetch_cricbuzz_data(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        }
    )

    table_html = fetch_url(session, CRICBUZZ_TABLE_URL)
    standings = parse_cricbuzz_standings(table_html)
    fixtures = parse_cricbuzz_fixtures(table_html, CRICBUZZ_TABLE_URL)

    try:
        matches_html = fetch_url(session, CRICBUZZ_MATCHES_URL)
        by_key = {
            (item["teamA"], item["teamB"], item["matchNo"]): item for item in fixtures
        }
        for item in parse_cricbuzz_fixtures(matches_html, CRICBUZZ_MATCHES_URL):
            by_key.setdefault((item["teamA"], item["teamB"], item["matchNo"]), item)
        fixtures = list(by_key.values())
    except Exception as exc:
        warnings.append(f"Cricbuzz fixtures page could not be parsed: {exc}")

    for fixture in fixtures[:8]:
        try:
            direct_html = fetch_url(session, fixture["sourceUrl"])
            enrich_fixture_from_match_page(fixture, direct_html)
        except Exception as exc:
            warnings.append(f"Could not enrich {fixture['teamA']} vs {fixture['teamB']}: {exc}")

    fixtures = [fixture for fixture in fixtures if fixture.get("status") == "scheduled"]
    validate_source_data(standings, fixtures, now, strict_zero_fixtures=True)
    return standings, fixtures, warnings


def validate_source_data(
    standings: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    now: datetime,
    strict_zero_fixtures: bool,
) -> None:
    if len(standings) != len(TEAM_META):
        raise SourceValidationError(f"Expected 10 teams, found {len(standings)}")
    keys = {row["teamKey"] for row in standings}
    missing = sorted(set(TEAM_META) - keys)
    if missing:
        raise SourceValidationError(f"Missing teams in standings: {', '.join(missing)}")
    too_many = [row for row in standings if row["matches"] > LEAGUE_MATCHES_PER_TEAM]
    if too_many:
        details = ", ".join(f"{row['shortName']}={row['matches']}" for row in too_many)
        raise SourceValidationError(f"Invalid match counts above 14: {details}")
    missing_nrr = [row["shortName"] for row in standings if not isinstance(row.get("nrr"), float)]
    if missing_nrr:
        raise SourceValidationError(f"Missing NRR for: {', '.join(missing_nrr)}")
    if strict_zero_fixtures and now < SEASON_END_UTC and not fixtures:
        raise SourceValidationError("No future fixtures found before league-stage end")


def ranked_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (-row["points"], -row["nrr"], -row["wins"], row["fullName"]),
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def simulation_rank(table: dict[str, dict[str, Any]]) -> list[str]:
    rows = list(table.items())
    rows.sort(
        key=lambda item: (
            -item[1]["points"],
            -item[1].get("nrr", 0.0),
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
    target_sizes = {"4": 4, "2": 2}
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

    overall: dict[str, dict[str, float]] = {}
    for team_idx, key in enumerate(team_keys):
        overall[key] = {
            "top4": round((accumulated["weightedTotals"]["4"][team_idx] / total_scenarios) * 100, 2),
            "top2": round((accumulated["weightedTotals"]["2"][team_idx] / total_scenarios) * 100, 2),
            "top4Clear": round((accumulated["exactTotals"]["4"][team_idx] / total_scenarios) * 100, 2),
            "top2Clear": round((accumulated["exactTotals"]["2"][team_idx] / total_scenarios) * 100, 2),
            "top4Possible": round((accumulated["possibleTotals"]["4"][team_idx] / total_scenarios) * 100, 2),
            "top2Possible": round((accumulated["possibleTotals"]["2"][team_idx] / total_scenarios) * 100, 2),
        }

    impact_fixture_count = min(len(fixtures), IMPACT_FIXTURE_WINDOW)
    fixture_impacts: dict[str, dict[str, list[list[dict[str, Any]]]]] = {
        target: {key: [] for key in team_keys}
        for target in ("4", "2")
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

        for target in ("4", "2"):
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

    team_analysis: dict[str, dict[str, Any]] = {"4": {}, "2": {}}
    qualification_path: dict[str, dict[str, Any]] = {"4": {}, "2": {}}
    scenario_breakdown: dict[str, dict[str, Any]] = {"4": {}, "2": {}}

    for target in ("4", "2"):
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
            "Current NRR is retained for the standings ladder only.",
            f"Fixture-impact guidance is computed for the next {impact_fixture_count} fixture(s).",
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
    if fixtures and len(fixtures) <= EXACT_MAX_FIXTURES:
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

    exhaustive = len(fixture_pairs) <= 20
    if not fixture_pairs:
        scenario_iterable: list[tuple[int, ...]] = [tuple()]
        method = "Exact"
        simulation_count = 1
    elif exhaustive:
        scenario_iterable = list(_binary_scenarios(len(fixture_pairs)))
        method = "Exhaustive"
        simulation_count = len(scenario_iterable)
    else:
        random.seed(RANDOM_SEED)
        simulation_count = DEFAULT_MONTE_CARLO_SIMULATIONS
        scenario_iterable = [
            tuple(random.randint(0, 1) for _ in fixture_pairs)
            for _ in range(simulation_count)
        ]
        method = "Monte Carlo"

    top_counts = {key: {"top4": 0, "top2": 0} for key in team_keys}
    team_analysis_counts: dict[str, dict[str, dict[str, list[int]]]] = {
        key: {
            "4": {label: [0, 0] for label in fixture_labels},
            "2": {label: [0, 0] for label in fixture_labels},
        }
        for key in team_keys
    }
    own_win_buckets = {
        key: {
            "4": {},
            "2": {},
        }
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
        top4 = set(ordered[:4])
        top2 = set(ordered[:2])

        for key in team_keys:
            for target, qualified in (("4", key in top4), ("2", key in top2)):
                bucket = own_win_buckets[key][target].setdefault(
                    own_wins[key], {"total": 0, "qualified": 0}
                )
                bucket["total"] += 1
                if qualified:
                    bucket["qualified"] += 1
                    if target == "4":
                        top_counts[key]["top4"] += 1
                    else:
                        top_counts[key]["top2"] += 1
                    for idx, outcome in enumerate(scenario):
                        team_analysis_counts[key][target][fixture_labels[idx]][outcome] += 1

    overall = {}
    team_analysis = {"4": {}, "2": {}}
    qualification_path = {"4": {}, "2": {}}

    for key in team_keys:
        overall[key] = {
            "top4": round((top_counts[key]["top4"] / simulation_count) * 100, 2),
            "top2": round((top_counts[key]["top2"] / simulation_count) * 100, 2),
        }
        own_remaining = sum(1 for left, right in fixture_pairs if key in (left, right))
        for target in ("4", "2"):
            success_count = top_counts[key]["top4" if target == "4" else "top2"]
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


def _binary_scenarios(width: int):
    for number in range(2**width):
        yield tuple((number >> idx) & 1 for idx in range(width))


def legacy_outputs(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    standings = {
        row["teamKey"]: {
            "Matches": row["matches"],
            "Wins": row["wins"],
            "Losses": row["losses"],
            "NR": row["noResult"],
            "Points": row["points"],
            "NRR": row["nrr"],
        }
        for row in payload["standings"]
    }
    fixtures = [[item["teamA"], item["teamB"]] for item in payload["fixtures"]]
    analysis = payload["analysis"]

    legacy_analysis_data = {
        "overall_probabilities": {
            team: {
                "Top 4 Probability": values["top4"],
                "Top 2 Probability": values["top2"],
            }
            for team, values in analysis["overallProbabilities"].items()
        },
        "team_analysis": analysis["teamAnalysis"],
        "qualification_path": analysis["qualificationPath"],
    }

    last_updated = payload["metadata"]["generated_at"]
    source = payload["metadata"]["source"]
    return (
        {
            "last_updated": last_updated,
            "source": source,
            "standings": standings,
        },
        {
            "last_updated": last_updated,
            "source": source,
            "fixtures": fixtures,
        },
        {
            "metadata": {
                "precomputed_at": analysis["generatedAt"],
                "num_fixtures": len(payload["fixtures"]),
                "last_data_update": last_updated,
                "data_source": source,
                "method_used": analysis["method"],
                "simulation_count": analysis["simulationCount"],
            },
            "analysis_data": legacy_analysis_data,
        },
    )


def build_payload() -> dict[str, Any]:
    now = utc_now()
    warnings: list[str] = []
    source = "CricketData"
    source_url = CRICDATA_SOURCE_URL

    try:
        standings, fixtures, source_warnings = fetch_cricdata_data(now)
        warnings.extend(source_warnings)
    except Exception as cricdata_error:
        warnings.append(f"CricketData source failed: {cricdata_error}")
        try:
            standings, fixtures, source_warnings = fetch_cricbuzz_data(now)
            warnings.extend(source_warnings)
            source = "Cricbuzz"
            source_url = CRICBUZZ_TABLE_URL
        except Exception as cricbuzz_error:
            raise SourceValidationError(
                f"All data sources failed. CricketData: {cricdata_error}; Cricbuzz: {cricbuzz_error}"
            ) from cricbuzz_error

    standings = ranked_standings(standings)
    try:
        validate_source_data(standings, fixtures, now, strict_zero_fixtures=False)
    except SourceValidationError as exc:
        warnings.append(str(exc))

    expected_remaining = sum(row["remainingMatches"] for row in standings) // 2
    if fixtures and now < SEASON_END_UTC and len(fixtures) < expected_remaining:
        warnings.append(
            f"Fixture feed appears partial: found {len(fixtures)} scheduled match(es), "
            f"but standings imply about {expected_remaining} league match(es) remaining."
        )

    if not fixtures and now < SEASON_END_UTC:
        warnings.append("No future fixtures were found; probabilities are current-table only.")

    analysis = run_analysis(standings, fixtures, now)
    freshness = "fresh" if not warnings else "warning"

    return {
        "metadata": {
            "season": SEASON,
            "generated_at": iso_utc(now),
            "source": source,
            "source_url": source_url,
            "data_freshness_status": freshness,
            "warnings": warnings,
        },
        "standings": standings,
        "fixtures": fixtures,
        "analysis": analysis,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    payload = build_payload()
    standings, fixtures, analysis = legacy_outputs(payload)
    write_json(CANONICAL_OUTPUT, payload)
    write_json(ROOT_CANONICAL_OUTPUT, payload)
    write_json(ROOT_STANDINGS_OUTPUT, standings)
    write_json(ROOT_FIXTURES_OUTPUT, fixtures)
    write_json(ROOT_ANALYSIS_OUTPUT, analysis)
    write_json(PUBLIC_STANDINGS_OUTPUT, standings)
    write_json(PUBLIC_FIXTURES_OUTPUT, fixtures)
    write_json(PUBLIC_ANALYSIS_OUTPUT, analysis)


if __name__ == "__main__":
    main()
