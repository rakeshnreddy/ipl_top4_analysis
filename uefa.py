"""UEFA club competition data from the public JSON services behind uefa.com.

No key is needed. These services are unofficial for third parties (like ESPN's), so
every download is cached and a failed refresh falls back to the last good copy.

- Matches (``match.uefa.com``): every qualifying and main-draw match of a season, with
  90-minute, extra-time and penalty scores and the winner of each two-legged tie.
- Standings (``standings.uefa.com``): the official league-phase table.

UEFA names a season by the year it ends: ``seasonYear=2027`` is 2026-27.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import team_sports


MATCHES_URL = "https://match.uefa.com/v5/matches?competitionId={competition}&seasonYear={season}&limit={limit}&offset={offset}&order=ASC"
STANDINGS_URL = "https://standings.uefa.com/v1/standings?competitionId={competition}&seasonYear={season}"
SOURCE = "UEFA.com"
SOURCE_URL = "https://www.uefa.com/"
PAGE_SIZE = 500
# Men's club competitions, all of which feed the strength model.
COMPETITIONS = {"UCL": 1, "UEL": 14, "UECL": 2019}

# round.metaData.type of the main-draw rounds, in order.
LEAGUE_PHASE = "GROUP_STANDINGS"
KNOCKOUT_ROUNDS = ("FINAL_TOURNAMENT_PLAY_OFF", "ROUND_OF_16", "QUARTER_FINALS", "SEMIFINAL", "FINAL")


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    code: str
    country: str


@dataclass(frozen=True)
class Match:
    id: str
    competition: int
    season: int
    # LEAGUE_PHASE, one of KNOCKOUT_ROUNDS, or a qualifying round type.
    round: str
    qualifying: bool
    # 1 or 2 for two-legged ties, None for league-phase games and the final.
    leg: int | None
    date: datetime
    home: str
    away: str
    status: str
    # Goals after 90 minutes (what the goals model is fitted on) ...
    home_score: int | None
    away_score: int | None
    # ... and after extra time, plus any shoot-out, for knockout results.
    home_total: int | None = None
    away_total: int | None = None
    home_penalties: int | None = None
    away_penalties: int | None = None
    # The match winner (league phase, final) or the tie winner (second legs).
    winner: str | None = None
    neutral: bool = False

    @property
    def played(self) -> bool:
        return self.status == "FINISHED" and self.home_score is not None and self.away_score is not None


def _cached(url: str, path: Path, max_age_hours: float) -> Any:
    fresh = path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600
    if not fresh:
        try:
            data = team_sports.get_json(url)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the last good copy
            if not path.exists():
                raise team_sports.FeedError(f"{SOURCE}: {exc}") from exc
            print(f"{path.name}: using the cached copy ({exc})")
    return json.loads(path.read_text(encoding="utf-8"))


def _score(score: dict[str, Any] | None, part: str) -> tuple[int | None, int | None]:
    values = (score or {}).get(part) or {}
    return values.get("home"), values.get("away")


def parse_team(raw: dict[str, Any]) -> Team | None:
    if not raw or raw.get("isPlaceHolder") or not raw.get("id"):
        return None
    return Team(
        id=str(raw["id"]),
        name=raw.get("internationalName") or raw.get("translations", {}).get("displayName", {}).get("EN") or str(raw["id"]),
        code=raw.get("teamCode") or "",
        country=raw.get("countryCode") or "",
    )


def parse_match(raw: dict[str, Any], competition: int, season: int) -> tuple[Match, Team, Team] | None:
    """A match and its two teams, or None while a team is still a placeholder ("Winner of ...")."""
    home, away = parse_team(raw.get("homeTeam")), parse_team(raw.get("awayTeam"))
    kickoff = raw.get("kickOffTime") or {}
    when = kickoff.get("dateTime") or (f"{kickoff['date']}T12:00:00Z" if kickoff.get("date") else None)
    if home is None or away is None or when is None:
        return None
    round_type = ((raw.get("round") or {}).get("metaData") or {}).get("type") or ""
    kind = raw.get("type")
    leg = 1 if kind == "FIRST_LEG" else 2 if kind == "SECOND_LEG" else None
    home_score, away_score = _score(raw.get("score"), "regular")
    home_total, away_total = _score(raw.get("score"), "total")
    home_pens, away_pens = _score(raw.get("score"), "penalty")
    winner_block = raw.get("winner") or {}
    winner = ((winner_block.get("aggregate") if leg == 2 else winner_block.get("match")) or {}).get("team") or {}
    match = Match(
        id=str(raw["id"]),
        competition=competition,
        season=season,
        round=round_type,
        qualifying=(raw.get("round") or {}).get("phase") == "QUALIFYING",
        leg=leg,
        date=datetime.fromisoformat(when.replace("Z", "+00:00")),
        home=home.id,
        away=away.id,
        status=raw.get("status", ""),
        home_score=home_score,
        away_score=away_score,
        home_total=home_total,
        away_total=away_total,
        home_penalties=home_pens,
        away_penalties=away_pens,
        winner=str(winner["id"]) if winner.get("id") else None,
        neutral=round_type == "FINAL",
    )
    return match, home, away


def fetch_matches(competition: int, season: int, cache_dir: Path, max_age_hours: float = 3) -> tuple[list[Match], dict[str, Team]]:
    """Every match of a competition season with known teams, oldest first."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        url = MATCHES_URL.format(competition=competition, season=season, limit=PAGE_SIZE, offset=offset)
        page = _cached(url, cache_dir / f"uefa-matches-{competition}-{season}-{offset}.json", max_age_hours)
        if not isinstance(page, list):
            raise team_sports.FeedError(f"{SOURCE} matches {competition}/{season}: unexpected format")
        rows += page
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    matches, teams = [], {}
    for raw in rows:
        parsed = parse_match(raw, competition, season)
        if parsed is None:
            continue
        match, home, away = parsed
        matches.append(match)
        teams[home.id], teams[away.id] = home, away
    return sorted(matches, key=lambda match: (match.date, match.id)), teams


def fetch_standings(competition: int, season: int, cache_dir: Path, max_age_hours: float = 3) -> list[dict[str, Any]]:
    """The official league-phase table rows (rank, team id, points and tiebreak figures)."""
    data = _cached(STANDINGS_URL.format(competition=competition, season=season), cache_dir / f"uefa-standings-{competition}-{season}.json", max_age_hours)
    groups = [group for group in data if (group.get("round") or {}).get("metaData", {}).get("type", LEAGUE_PHASE) == LEAGUE_PHASE] if isinstance(data, list) else []
    if not groups:
        raise team_sports.FeedError(f"{SOURCE} standings {competition}/{season}: no league-phase table")
    return [
        {
            "rank": item["rank"],
            "team": str(item["team"]["id"]),
            "played": item["played"],
            "wins": item["won"],
            "draws": item["drawn"],
            "losses": item["lost"],
            "goalsFor": item["goalsFor"],
            "goalsAgainst": item["goalsAgainst"],
            "points": item["points"],
        }
        for item in groups[0]["items"]
    ]
