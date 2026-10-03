"""League configuration: one JSON file per competition season in ``leagues/``.

A config holds everything that differs between T20 leagues: teams and their
colours, games per team, how many teams qualify, playoff stage names, data
sources, and results Cricsheet cannot supply (matches abandoned before a
ball was bowled have no Cricsheet file).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEAGUES_DIR = Path(__file__).resolve().parent / "leagues"
DEFAULT_LEAGUE_ID = "ipl-2026"


@dataclass(frozen=True)
class TeamMeta:
    key: str
    short_name: str
    full_name: str
    color: str = "#2d405f"
    text_color: str = "#ffffff"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualificationTier:
    size: int
    label: str


@dataclass(frozen=True)
class ExtraResult:
    """A league match with no Cricsheet file, recorded as a no result."""

    date: str
    teams: tuple[str, str]
    note: str


@dataclass(frozen=True)
class League:
    id: str
    name: str
    short_name: str
    season: str
    season_label: str
    priority: int
    matches_per_team: int
    season_start: datetime | None
    season_end: datetime
    qualification: tuple[QualificationTier, ...]
    playoff_stages: tuple[str, ...]
    second_chance_stages: tuple[str, ...]
    cricsheet_competition: str | None
    cricketdata_series_names: tuple[str, ...]
    cricketdata_series_id: str | None
    extra_results: tuple[ExtraResult, ...]
    teams: tuple[TeamMeta, ...]
    points_win: int = 2
    points_no_result: int = 1
    points_tie: int = 1
    # SA20: a win earns a bonus point when the winner's run rate is this multiple of the loser's.
    bonus_run_rate_ratio: float | None = None
    # Share of wins that earned a bonus point last season; used when simulating.
    bonus_simulation_rate: float = 0.0
    # Balls per NRR unit: 6 (per over) except The Hundred, which uses 5-ball sets.
    nrr_balls_per_unit: int = 6
    # Mixed-gender Cricsheet archives (The Hundred) need a filter.
    gender: str | None = None

    @property
    def team_meta(self) -> dict[str, TeamMeta]:
        return {team.key: team for team in self.teams}

    @property
    def league_match_count(self) -> int:
        return len(self.teams) * self.matches_per_team // 2

    @property
    def qualification_sizes(self) -> list[int]:
        return [tier.size for tier in self.qualification]

    def payload_block(self) -> dict[str, Any]:
        """League details the frontend needs to render any league."""
        return {
            "id": self.id,
            "name": self.name,
            "shortName": self.short_name,
            "season": self.season,
            "seasonLabel": self.season_label,
            "matchesPerTeam": self.matches_per_team,
            "qualification": [{"size": tier.size, "label": tier.label} for tier in self.qualification],
            "secondChanceStages": list(self.second_chance_stages),
            "points": {
                "win": self.points_win,
                "noResult": self.points_no_result,
                "tie": self.points_tie,
                "bonus": self.bonus_run_rate_ratio is not None,
            },
            "teams": [
                {
                    "key": team.key,
                    "shortName": team.short_name,
                    "fullName": team.full_name,
                    "color": team.color,
                    "textColor": team.text_color,
                }
                for team in self.teams
            ],
        }


def parse_league(raw: dict[str, Any]) -> League:
    teams = tuple(
        TeamMeta(
            key=item["key"],
            short_name=item["shortName"],
            full_name=item["fullName"],
            color=item.get("color", "#2d405f"),
            text_color=item.get("textColor", "#ffffff"),
            aliases=tuple(item.get("aliases", ())),
        )
        for item in raw["teams"]
    )
    qualification = tuple(QualificationTier(size=item["size"], label=item["label"]) for item in raw["qualification"])
    playoffs = raw.get("playoffs", {})
    sources = raw.get("sources", {})
    points = raw.get("points", {})
    cricketdata = sources.get("cricketdata") or {}
    start = datetime.fromisoformat(raw["seasonStart"]).replace(tzinfo=timezone.utc) if raw.get("seasonStart") else None
    end = datetime.fromisoformat(raw["seasonEnd"]).replace(hour=23, minute=59, tzinfo=timezone.utc)

    league = League(
        id=raw["id"],
        name=raw["name"],
        short_name=raw["shortName"],
        season=raw["season"],
        season_label=raw.get("seasonLabel", raw["season"]),
        priority=raw.get("priority", 100),
        matches_per_team=raw["matchesPerTeam"],
        season_start=start,
        season_end=end,
        qualification=qualification,
        playoff_stages=tuple(playoffs.get("stages", ())),
        second_chance_stages=tuple(playoffs.get("secondChance", ())),
        cricsheet_competition=sources.get("cricsheet"),
        cricketdata_series_names=tuple(cricketdata.get("seriesNames", ())),
        cricketdata_series_id=cricketdata.get("seriesId"),
        extra_results=tuple(
            ExtraResult(date=item["date"], teams=(item["teams"][0], item["teams"][1]), note=item.get("note", ""))
            for item in raw.get("extraResults", ())
        ),
        teams=teams,
        points_win=points.get("win", 2),
        points_no_result=points.get("noResult", 1),
        points_tie=points.get("tie", 1),
        bonus_run_rate_ratio=points.get("bonusRunRateRatio"),
        bonus_simulation_rate=points.get("bonusSimulationRate", 0.0),
        nrr_balls_per_unit=raw.get("nrrBallsPerUnit", 6),
        gender=raw.get("gender"),
    )
    validate_league(league)
    return league


def validate_league(league: League) -> None:
    keys = [team.key for team in league.teams]
    short_names = [team.short_name for team in league.teams]
    if len(set(keys)) != len(keys) or len(set(short_names)) != len(short_names):
        raise ValueError(f"{league.id}: team keys and short names must be unique")
    if len(league.teams) * league.matches_per_team % 2:
        raise ValueError(f"{league.id}: teams x matchesPerTeam must be even")
    if league.season_start and league.season_start > league.season_end:
        raise ValueError(f"{league.id}: seasonStart must be on or before seasonEnd")
    sizes = league.qualification_sizes
    if not sizes or sizes != sorted(sizes, reverse=True) or sizes[0] > len(league.teams):
        raise ValueError(f"{league.id}: qualification sizes must be descending and fit the team count")


def load_league(league_id: str, directory: Path = LEAGUES_DIR) -> League:
    path = directory / f"{league_id}.json"
    if not path.exists():
        available = ", ".join(available_league_ids(directory)) or "none"
        raise ValueError(f"Unknown league '{league_id}'. Available: {available}")
    return parse_league(json.loads(path.read_text(encoding="utf-8")))


def available_league_ids(directory: Path = LEAGUES_DIR) -> list[str]:
    leagues = [parse_league(json.loads(path.read_text(encoding="utf-8"))) for path in directory.glob("*.json")]
    return [league.id for league in sorted(leagues, key=lambda item: (item.priority, item.id))]
