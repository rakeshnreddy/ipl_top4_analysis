"""Shared pieces for team sports with rolling seasons from FixtureDownload feeds.

A rolling config (for example ``leagues/epl.json``) describes a competition rather
than one season: each season's feed name, label and date window come from the
``season`` rule, so a new season is picked up without a new config file.
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests


FEED_URL = "https://fixturedownload.com/feed/json/{feed}"
FEED_SOURCE = "FixtureDownload"
FEED_SOURCE_URL = "https://fixturedownload.com/"
REQUEST_TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 5
USER_AGENT = "PlayoffPulse/1.0 (+https://github.com/rakeshnreddy/ipl_top4_analysis)"


class FeedError(RuntimeError):
    pass


@dataclass(frozen=True)
class Game:
    id: str
    round: int | None
    date: datetime
    home: str
    away: str
    venue: str | None
    home_score: int | None
    away_score: int | None
    # How a decided game ended when that matters, e.g. "OT" or "SO" in the NHL.
    note: str | None = None

    @property
    def played(self) -> bool:
        return self.home_score is not None and self.away_score is not None


@dataclass(frozen=True)
class Season:
    config_id: str
    year: int
    payload_id: str
    label: str
    feed: str
    start: datetime
    end: datetime

    def contains(self, now: datetime) -> bool:
        return self.start <= now <= self.end


def _end_of_month(year: int, month: int) -> datetime:
    next_month = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=timezone.utc)
    return datetime.fromtimestamp(next_month.timestamp() - 1, tz=timezone.utc)


def resolve_season(config: dict[str, Any], now: datetime, offset: int = 0) -> Season:
    """The season in progress (or most recently started) at ``now``; ``offset=-1`` is the one before."""
    rule = config["season"]
    start_month, end_month = rule["startMonth"], rule["endMonth"]
    year = (now.year if now.month >= start_month else now.year - 1) + offset
    end_year = year + 1 if end_month < start_month else year
    values = {"year": year, "next": year + 1, "yy": f"{(year + 1) % 100:02d}"}
    label = rule.get("label", "{year}").format(**values)
    return Season(
        config_id=config["id"],
        year=year,
        payload_id=f"{config['id']}-{label}",
        label=label,
        feed=rule["feed"].format(**values),
        start=datetime(year, start_month, 1, tzinfo=timezone.utc),
        end=_end_of_month(end_year, end_month),
    )


# Table places from the top or bottom (football), playoff outcomes (leagues with conferences),
# or reaching a knockout round (European cups).
TIER_KINDS = {"top", "bottom", "playoffs", "division", "seed", "best-record", "champion", "round"}


def validate_config(config: dict[str, Any]) -> None:
    """Fail fast on a malformed rolling config instead of on the night it first runs."""
    name = config.get("id", "?")
    rule = config.get("season") or {}
    if not {"startMonth", "endMonth", "feed"} <= set(rule):
        raise ValueError(f"{name}: season needs startMonth, endMonth and feed")
    if not (1 <= rule["startMonth"] <= 12 and 1 <= rule["endMonth"] <= 12):
        raise ValueError(f"{name}: season months must be 1-12")
    if not isinstance(rule.get("firstYear", 0), int):
        raise ValueError(f"{name}: season firstYear must be a year")
    keys = set()
    for tier in config.get("tiers", []):
        kind = tier.get("kind", "top")
        if kind not in TIER_KINDS or not tier.get("label"):
            raise ValueError(f"{name}: every tier needs a label and a kind from {', '.join(sorted(TIER_KINDS))}")
        if kind in ("top", "bottom", "seed") and tier.get("size", 0) < 1:
            raise ValueError(f"{name}: {kind} tiers need a positive size")
        keys.add(tier["key"])
    if not keys or len(keys) != len(config["tiers"]):
        raise ValueError(f"{name}: tiers need unique keys")
    short_names = [team["shortName"] for team in config.get("teams", {}).values() if "shortName" in team]
    if len(short_names) != len(set(short_names)):
        raise ValueError(f"{name}: team short names must be unique")


def parse_game(row: dict[str, Any]) -> Game:
    date = datetime.fromisoformat(str(row["DateUtc"]).replace(" ", "T").replace("Z", "+00:00"))
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return Game(
        id=str(row.get("MatchNumber")),
        round=row.get("RoundNumber"),
        date=date,
        home=row["HomeTeam"],
        away=row["AwayTeam"],
        venue=row.get("Location"),
        home_score=row.get("HomeTeamScore"),
        away_score=row.get("AwayTeamScore"),
    )


def get_json(url: str, session: requests.Session | None = None, attempts: int = 3) -> Any:
    """GET a JSON document, retrying timeouts and server errors with a short backoff."""
    for attempt in range(attempts):
        try:
            response = (session or requests).get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
            if response.status_code < 500 or attempt == attempts - 1:
                response.raise_for_status()
                return response.json()
        except (requests.ConnectionError, requests.Timeout):
            if attempt == attempts - 1:
                raise
        time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    raise FeedError(f"{url}: no response")


def fetch_games(feed: str, cache_dir: Path, max_age_hours: float = 3, session: requests.Session | None = None) -> list[Game]:
    """Download a season feed, falling back to the cached copy if the site is unreachable."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{feed}.json"
    fresh = path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600
    if not fresh:
        try:
            rows = get_json(FEED_URL.format(feed=feed), session)
            if not isinstance(rows, list):
                raise FeedError(f"{feed}: unexpected feed format")
            path.write_text(json.dumps(rows), encoding="utf-8")
        except (requests.RequestException, ValueError, FeedError) as exc:
            if not path.exists():
                raise FeedError(f"{feed}: {exc}") from exc
            print(f"{feed}: using the cached copy ({exc})")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not rows:
        raise FeedError(f"{feed}: the feed has no fixtures yet")
    return sorted((parse_game(row) for row in rows), key=lambda game: (game.date, game.id))


_SHORT_NAME_SKIP = {"fc", "cf", "sc", "sv", "ac", "as", "rc", "rcd", "ud", "ca", "cd", "afc", "club", "de", "the"}


def auto_short_name(name: str, taken: set[str]) -> str:
    words = [word for word in re.findall(r"[A-Za-zÀ-ÿ]+", name) if word.lower() not in _SHORT_NAME_SKIP]
    base = (max(words, key=len) if words else name)[:3].upper()
    candidate, suffix = base, 2
    while candidate in taken:
        candidate, suffix = f"{base[:2]}{suffix}", suffix + 1
    return candidate


def hashed_colors(name: str) -> tuple[str, str]:
    """A stable, readable colour pair for teams without a configured colour."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    hue = digest[0] / 255
    red, green, blue = colorsys.hls_to_rgb(hue, 0.42, 0.65)
    color = "#{:02X}{:02X}{:02X}".format(int(red * 255), int(green * 255), int(blue * 255))
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return color, "#000000" if luminance > 0.6 else "#FFFFFF"


def relative_luminance(color: str) -> float:
    """WCAG relative luminance of a #RRGGBB colour (0 black, 1 white)."""
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def team_meta(config: dict[str, Any], names: list[str]) -> dict[str, dict[str, str]]:
    """Display metadata for every team in a feed: configured overrides, otherwise generated."""
    overrides = config.get("teams", {})
    taken = {item["shortName"] for item in overrides.values() if "shortName" in item}
    meta = {}
    for name in sorted(names):
        override = overrides.get(name, {})
        short_name = override.get("shortName") or auto_short_name(name, taken)
        taken.add(short_name)
        color, text = hashed_colors(name)
        meta[name] = {
            "key": name,
            "shortName": short_name,
            "fullName": override.get("fullName", name),
            "color": override.get("color", color),
            "textColor": override.get("textColor", text),
        }
    return meta


def form_strings(games: list[Game], team: str, limit: int = 5) -> list[str]:
    """Latest results first, as W/D/L."""
    played = [game for game in games if game.played and team in (game.home, game.away)]
    form = []
    for game in reversed(played[-limit:]):
        own, other = (game.home_score, game.away_score) if game.home == team else (game.away_score, game.home_score)
        form.append("W" if own > other else "D" if own == other else "L")
    return form


def positions_from_keys(keys: np.ndarray) -> np.ndarray:
    """Finishing position (0 = first) of every team in every simulation, highest key first."""
    order = np.argsort(-keys, axis=1, kind="stable")
    positions = np.empty_like(order)
    rows = np.arange(keys.shape[0])[:, None]
    positions[rows, order] = np.arange(keys.shape[1])[None, :]
    return positions


def tier_flags(positions: np.ndarray, tier: dict[str, Any], team_count: int) -> np.ndarray:
    size = tier["size"]
    return positions >= team_count - size if tier.get("kind") == "bottom" else positions < size


def probability_movement(previous: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Change in every tier chance since the previously published payload.

    When no game has finished since then, the previous movement still describes the
    latest change, so it is carried forward.
    """
    if not previous or (previous.get("league") or {}).get("id") != payload["league"]["id"]:
        return None

    def played(data: dict[str, Any]) -> int:
        return sum(row.get("played", 0) for row in data.get("standings", []))

    if played(previous) == played(payload):
        return previous.get("movement")

    before = (previous.get("analysis") or {}).get("probabilities", {})
    changes = {}
    for team, values in payload["analysis"]["probabilities"].items():
        old = before.get(team, {})
        deltas = {key: round(value - old[key], 2) for key, value in values.items() if key in old}
        if deltas:
            changes[team] = deltas
    return {"since": previous["metadata"]["generated_at"], "changes": changes} if changes else None
