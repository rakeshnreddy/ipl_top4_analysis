"""NFL, NBA, NHL and MLB: regular-season tables, playoff races and title odds.

Team ratings come from a margin model (score margins, capped so blowouts do not
dominate, with home advantage and a time decay) fitted on this and last season.
The rest of the regular season is simulated with season-long strength drift,
each simulated table is turned into playoff seeds with the league's format, and
the playoff bracket is simulated too, which gives title odds.

Tiebreakers are simplified: win percentage (points in the NHL), then division or
conference record (regulation wins in the NHL), then a coin flip. Head-to-head
and common-games rules are not modelled.
"""

from __future__ import annotations

import dataclasses
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

import team_sports
from team_sports import Game

SIMULATIONS = 20_000
SEED = 20261003
# Simulations per block when playing out the regular season, to bound memory.
CHUNK = 2_000
MATCHES_THAT_MATTER = 10
# Upcoming games considered for "matches that matter".
MATTER_WINDOW_DAYS = 4
NHL_GAMES_URL = "https://api.nhle.com/stats/rest/en/game?cayenneExp=season={code}%20and%20gameType=2"
NHL_TEAMS_URL = "https://api.nhle.com/stats/rest/en/team"
NHL_SOURCE = "NHL"
NHL_SOURCE_URL = "https://www.nhl.com/"
NHL_PLAYOFF_GAMES_URL = "https://api.nhle.com/stats/rest/en/game?cayenneExp=season={code}%20and%20gameType=3"
MLB_POSTSEASON_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={year}&gameType=F,D,L,W"

# Playoff rounds per format: stage code, name on the page.
STAGES = {
    "nfl": [("WC", "Wild Card"), ("DIV", "Divisional Round"), ("CONF", "Conference Championship"), ("SB", "Super Bowl")],
    "nba": [("PI", "Play-In"), ("R1", "First Round"), ("R2", "Conference Semifinals"), ("CF", "Conference Finals"), ("F", "NBA Finals")],
    "nhl": [("R1", "First Round"), ("R2", "Second Round"), ("CF", "Conference Final"), ("F", "Stanley Cup Final")],
    "mlb": [("F", "Wild Card Series"), ("D", "Division Series"), ("L", "Championship Series"), ("W", "World Series")],
}
# NHL playoff game ids encode the round in their seventh digit: 2025030111 is round 1.
NHL_ROUND_STAGES = {"1": "R1", "2": "R2", "3": "CF", "4": "F"}


@dataclass(frozen=True)
class SportModel:
    """Model settings per sport, chosen by backtesting past seasons."""

    margin_cap: float
    half_life_days: float
    # Weight on last season's games on top of the time decay (rosters change in the off-season).
    previous_weight: float
    # Ridge penalty on team ratings, in units of fully weighted games.
    ridge: float
    # Standard deviation of each team's strength drift over a whole season, in margin units.
    drift: float
    # Spread of results around the predicted margin, as used in the win probability.
    sigma: float
    tie_rate: float = 0.0
    overtime_rate: float = 0.0


# Backtested on the 2023-24 to 2025-26 seasons (MLB: 2024 and 2025). Game-level settings
# minimise the log loss of week-ahead predictions; drift gives the best calibrated
# playoff odds at 25%, 50% and 75% of the season.
SPORT_MODELS = {
    "american-football": SportModel(margin_cap=21, half_life_days=120, previous_weight=1.0, ridge=3.0, drift=5.0, sigma=11.8, tie_rate=0.003),
    "basketball": SportModel(margin_cap=25, half_life_days=60, previous_weight=1.0, ridge=2.0, drift=4.0, sigma=11.5),
    "ice-hockey": SportModel(margin_cap=3, half_life_days=480, previous_weight=0.6, ridge=60.0, drift=0.25, sigma=1.43, overtime_rate=0.23),
    "baseball": SportModel(margin_cap=6, half_life_days=240, previous_weight=1.0, ridge=100.0, drift=0.75, sigma=2.41),
}

TEAM_SPORT_NAMES = {"american-football": "NFL", "basketball": "NBA", "ice-hockey": "NHL", "baseball": "MLB"}


# --------------------------------------------------------------------------- data


def nhl_season_code(year: int) -> str:
    return f"{year}{year + 1}"


def fetch_nhl_games(year: int, cache_dir: Path, max_age_hours: float = 3) -> list[Game]:
    """Regular-season games from the NHL stats API; `round` is unused and `note` marks OT and SO."""
    import json
    import time

    cache_dir.mkdir(parents=True, exist_ok=True)
    teams_path = cache_dir / "nhl-teams.json"
    games_path = cache_dir / f"nhl-api-{year}.json"
    for path, url, age in ((teams_path, NHL_TEAMS_URL, 24 * 30), (games_path, NHL_GAMES_URL.format(code=nhl_season_code(year)), max_age_hours)):
        if path.exists() and time.time() - path.stat().st_mtime < age * 3600:
            continue
        try:
            data = team_sports.get_json(url)
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                raise team_sports.FeedError(f"{url}: unexpected format")
            path.write_text(json.dumps(data), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the cached copy
            if not path.exists():
                raise team_sports.FeedError(f"NHL API: {exc}") from exc
            print(f"NHL API: using the cached copy ({exc})")

    names = {item["id"]: item["fullName"] for item in json.loads(teams_path.read_text(encoding="utf-8"))["data"]}
    eastern = ZoneInfo("America/New_York")
    games = []
    for item in json.loads(games_path.read_text(encoding="utf-8"))["data"]:
        if item.get("gameType") != 2:
            continue
        start = datetime.fromisoformat(item["easternStartTime"]).replace(tzinfo=eastern).astimezone(timezone.utc)
        final = item.get("gameStateId") in (6, 7)
        period = item.get("period") or 3
        games.append(
            Game(
                id=str(item["id"]),
                round=None,
                date=start,
                home=names.get(item["homeTeamId"], str(item["homeTeamId"])),
                away=names.get(item["visitingTeamId"], str(item["visitingTeamId"])),
                venue=None,
                home_score=item["homeScore"] if final else None,
                away_score=item["visitingScore"] if final else None,
                note=("SO" if period >= 5 else "OT" if period == 4 else None) if final else None,
            )
        )
    if not games:
        raise team_sports.FeedError(f"NHL API: no games for {nhl_season_code(year)}")
    return sorted(games, key=lambda game: (game.date, game.id))


@dataclass(frozen=True)
class PlayoffGame:
    stage: str
    date: datetime
    home: str
    away: str
    home_score: int | None
    away_score: int | None

    @property
    def played(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def winner(self) -> str | None:
        if not self.played or self.home_score == self.away_score:
            return None
        return self.home if self.home_score > self.away_score else self.away


def _cached_json(url: str, path: Path, max_age_hours: float) -> Any:
    import json
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    if not (path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600):
        try:
            data = team_sports.get_json(url)
            path.write_text(json.dumps(data), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - fall back to the last good copy
            if not path.exists():
                raise team_sports.FeedError(f"{url}: {exc}") from exc
            print(f"{url}: using the cached copy ({exc})")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_mlb_postseason(year: int, cache_dir: Path) -> list[PlayoffGame]:
    data = _cached_json(MLB_POSTSEASON_URL.format(year=year), cache_dir / f"mlb-postseason-{year}.json", 3)
    games = []
    for day in data.get("dates", []):
        for item in day.get("games", []):
            status = item.get("status", {})
            if status.get("codedGameState") == "C" or "cancel" in status.get("detailedState", "").lower():
                continue
            final = status.get("abstractGameState") == "Final"
            home, away = item["teams"]["home"], item["teams"]["away"]
            games.append(
                PlayoffGame(
                    stage=item["gameType"],
                    date=datetime.fromisoformat(item["gameDate"].replace("Z", "+00:00")),
                    home=home["team"]["name"],
                    away=away["team"]["name"],
                    home_score=home.get("score") if final else None,
                    away_score=away.get("score") if final else None,
                )
            )
    return games


def fetch_nhl_playoffs(year: int, cache_dir: Path) -> list[PlayoffGame]:
    import json

    teams_path = cache_dir / "nhl-teams.json"
    if not teams_path.exists():
        fetch_nhl_games(year, cache_dir)
    names = {item["id"]: item["fullName"] for item in json.loads(teams_path.read_text(encoding="utf-8"))["data"]}
    data = _cached_json(NHL_PLAYOFF_GAMES_URL.format(code=nhl_season_code(year)), cache_dir / f"nhl-playoffs-{year}.json", 3)
    eastern = ZoneInfo("America/New_York")
    games = []
    for item in data.get("data", []):
        final = item.get("gameStateId") in (6, 7)
        games.append(
            PlayoffGame(
                stage=NHL_ROUND_STAGES.get(str(item["id"])[6], "R1"),
                date=datetime.fromisoformat(item["easternStartTime"]).replace(tzinfo=eastern).astimezone(timezone.utc),
                home=names.get(item["homeTeamId"], str(item["homeTeamId"])),
                away=names.get(item["visitingTeamId"], str(item["visitingTeamId"])),
                home_score=item["homeScore"] if final else None,
                away_score=item["visitingScore"] if final else None,
            )
        )
    return games


def playoff_games(config: dict[str, Any], season: team_sports.Season, cache_dir: Path, feed_games: list[Game]) -> list[PlayoffGame] | None:
    """Playoff games so far and scheduled, or None when the league has no playoff source."""
    source = config.get("postseason", {})
    kind = source.get("provider")
    if kind == "mlb":
        return fetch_mlb_postseason(season.year, cache_dir)
    if kind == "nhl":
        return fetch_nhl_playoffs(season.year, cache_dir)
    if kind == "feed-rounds":
        rounds = {int(number): stage for number, stage in source["rounds"].items()}
        return [
            PlayoffGame(rounds[game.round], game.date, game.home, game.away, game.home_score, game.away_score)
            for game in feed_games
            if game.round in rounds
        ]
    return None


def season_games(config: dict[str, Any], season: team_sports.Season, cache_dir: Path, previous: bool = False) -> list[Game]:
    if config.get("sources", {}).get("provider") == "nhl":
        return fetch_nhl_games(season.year, cache_dir, max_age_hours=24 * 30 if previous else 3)
    return team_sports.fetch_games(season.feed, cache_dir, max_age_hours=24 * 30 if previous else 3)


def regular_season(config: dict[str, Any], games: list[Game]) -> list[Game]:
    """Drop playoff rounds, placeholder teams and games that do not count (the NBA Cup final)."""
    aliases = config.get("aliases", {})
    if aliases:
        games = [
            dataclasses.replace(game, home=aliases.get(game.home, game.home), away=aliases.get(game.away, game.away))
            for game in games
        ]
    teams = set(config["teams"])
    rounds = config.get("regularSeasonRounds")
    kept = [
        game
        for game in games
        if game.home in teams and game.away in teams and (rounds is None or game.round is None or game.round <= rounds)
    ]
    per_team = config.get("gamesPerTeam")
    if per_team:
        counts: dict[str, int] = defaultdict(int)
        for game in kept:
            counts[game.home] += 1
            counts[game.away] += 1
        # A game between two teams that both exceed the schedule is an extra (the NBA Cup final).
        for game in sorted(kept, key=lambda item: int(item.id) if item.id.isdigit() else 0, reverse=True):
            if counts[game.home] > per_team and counts[game.away] > per_team:
                kept.remove(game)
                counts[game.home] -= 1
                counts[game.away] -= 1
    return kept


# --------------------------------------------------------------------------- structure


@dataclass(frozen=True)
class Structure:
    teams: list[str]
    conference: np.ndarray  # conference index per team
    division: np.ndarray  # division index per team
    conferences: list[str]
    divisions: list[str]
    division_conference: list[int]


def league_structure(config: dict[str, Any]) -> Structure:
    teams = sorted(config["teams"])
    conferences = [item["key"] for item in config["conferences"]]
    divisions = [division for item in config["conferences"] for division in item["divisions"]]
    division_conference = [conferences.index(item["key"]) for item in config["conferences"] for _ in item["divisions"]]
    return Structure(
        teams=teams,
        conference=np.array([conferences.index(config["teams"][team]["conference"]) for team in teams]),
        division=np.array([divisions.index(config["teams"][team]["division"]) for team in teams]),
        conferences=conferences,
        divisions=divisions,
        division_conference=division_conference,
    )


# --------------------------------------------------------------------------- ratings


@dataclass(frozen=True)
class Ratings:
    home: float
    sigma: float
    rating: dict[str, float]

    def win_probability(self, home: str, away: str, neutral: bool = False) -> float:
        margin = (0.0 if neutral else self.home) + self.rating.get(home, 0.0) - self.rating.get(away, 0.0)
        return normal_cdf(margin / self.sigma)


def normal_cdf(value: float) -> float:
    return 0.5 * math.erfc(-value / math.sqrt(2))


def _ndtr(values: np.ndarray) -> np.ndarray:
    """Standard normal CDF for arrays (Abramowitz and Stegun 7.1.26; error below 1.5e-7)."""
    z = np.abs(values) / math.sqrt(2)
    t = 1.0 / (1.0 + 0.3275911 * z)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    return 0.5 * (1.0 + np.sign(values) * (1.0 - poly * np.exp(-z * z)))


def fit_ratings(
    games: list[Game],
    previous: list[Game],
    teams: list[str],
    model: SportModel,
    anchor: datetime,
) -> Ratings:
    """Weighted ridge regression of capped margins on home advantage and team ratings."""
    index = {team: i for i, team in enumerate(teams)}
    size = len(teams) + 1
    rows, margins, weights = [], [], []
    for source_weight, pool in ((model.previous_weight, previous), (1.0, games)):
        for game in pool:
            if not game.played or game.home not in index or game.away not in index:
                continue
            age = max(0.0, (anchor - game.date).total_seconds() / 86400)
            weight = source_weight * 0.5 ** (age / model.half_life_days)
            if weight < 1e-3:
                continue
            row = np.zeros(size)
            row[0] = 1.0
            row[1 + index[game.home]] += 1.0
            row[1 + index[game.away]] -= 1.0
            rows.append(row)
            margins.append(max(-model.margin_cap, min(model.margin_cap, game.home_score - game.away_score)))
            weights.append(weight)
    if not rows:
        return Ratings(home=0.0, sigma=model.sigma, rating=dict.fromkeys(teams, 0.0))

    design, target, weight = np.array(rows), np.array(margins, dtype=float), np.array(weights)
    penalty = np.full(size, model.ridge)
    penalty[0] = 1e-6
    normal = (design * weight[:, None]).T @ design + np.diag(penalty)
    theta = np.linalg.solve(normal, (design * weight[:, None]).T @ target)
    return Ratings(home=float(theta[0]), sigma=model.sigma, rating={team: float(theta[1 + i]) for team, i in index.items()})


# --------------------------------------------------------------------------- tables


def team_records(games: list[Game], structure: Structure, sport: str) -> dict[str, dict[str, Any]]:
    """Current records, with the extra columns each sport's table shows."""
    division_of = {team: structure.division[i] for i, team in enumerate(structure.teams)}
    conference_of = {team: structure.conference[i] for i, team in enumerate(structure.teams)}
    rows = {
        team: {
            "played": 0, "wins": 0, "losses": 0, "ties": 0, "otLosses": 0, "regulationWins": 0,
            "scored": 0, "allowed": 0, "divisionWins": 0, "divisionLosses": 0, "divisionTies": 0,
            "conferenceWins": 0, "conferenceLosses": 0, "conferenceTies": 0,
            "homeWins": 0, "homeLosses": 0, "awayWins": 0, "awayLosses": 0, "results": [],
        }
        for team in structure.teams
    }
    for game in games:
        if not game.played:
            continue
        same_division = division_of[game.home] == division_of[game.away]
        same_conference = conference_of[game.home] == conference_of[game.away]
        for team, own, other, at_home in ((game.home, game.home_score, game.away_score, True), (game.away, game.away_score, game.home_score, False)):
            row = rows[team]
            row["played"] += 1
            row["scored"] += own
            row["allowed"] += other
            if own > other:
                outcome = "W"
                row["wins"] += 1
                if game.note is None:
                    row["regulationWins"] += 1
            elif own < other:
                outcome = "L"
                if game.note and sport == "ice-hockey":
                    row["otLosses"] += 1
                else:
                    row["losses"] += 1
            else:
                outcome = "T"
                row["ties"] += 1
            row["results"].append(outcome)
            suffix = {"W": "Wins", "L": "Losses", "T": "Ties"}[outcome]
            if same_division:
                row[f"division{suffix}"] += 1
            if same_conference:
                row[f"conference{suffix}"] += 1
            if outcome != "T":
                row[("home" if at_home else "away") + ("Wins" if outcome == "W" else "Losses")] += 1
    return rows


def pct(wins: float, losses: float, ties: float = 0.0) -> float:
    games = wins + losses + ties
    return (wins + 0.5 * ties) / games if games else 0.0


def record_string(wins: int, losses: int, extra: int = 0, show_extra: bool = False) -> str:
    return f"{wins}-{losses}-{extra}" if show_extra or extra else f"{wins}-{losses}"


# --------------------------------------------------------------------------- seeding


def rank_keys(sport: str, wins, losses, ties, otl, regulation_wins, division_pct, conference_pct, noise):
    """Sort keys (higher is better) for division and conference ranking."""
    if sport == "ice-hockey":
        points = 2 * wins + otl
        played = wins + losses + otl
        base = points * 1e7 + (200 - played) * 1e4 + regulation_wins * 10 + wins * 0.01
        return base + noise, base + noise
    record = (wins + 0.5 * ties) / np.maximum(wins + losses + ties, 1)
    division_key = record * 1e6 + division_pct * 1e3 + conference_pct + noise
    conference_key = record * 1e6 + conference_pct * 1e3 + noise
    return division_key, conference_key


def seed_conferences(config: dict[str, Any], structure: Structure, division_key: np.ndarray, conference_key: np.ndarray) -> dict[str, np.ndarray]:
    """Conference seeds, playoff places and division winners for every simulation (rows)."""
    sims, count = conference_key.shape
    fmt = config["playoffs"]["format"]
    division_winner = np.zeros((sims, count), dtype=bool)
    division_rank = np.zeros((sims, count), dtype=np.int16)
    for d in range(len(structure.divisions)):
        members = np.flatnonzero(structure.division == d)
        order = np.argsort(-division_key[:, members], axis=1, kind="stable")
        ranks = np.empty_like(order)
        ranks[np.arange(sims)[:, None], order] = np.arange(len(members))[None, :]
        division_rank[:, members] = ranks
        division_winner[np.arange(sims), members[order[:, 0]]] = True

    seed = np.zeros((sims, count), dtype=np.int16)
    playoff = np.zeros((sims, count), dtype=bool)
    big = 1e12
    for c in range(len(structure.conferences)):
        members = np.flatnonzero(structure.conference == c)
        key = conference_key[:, members].copy()
        if fmt in ("nfl", "mlb"):
            # Division winners take the top seeds, then wild cards by record.
            key += division_winner[:, members] * big
        elif fmt == "nhl":
            # Top three in each division, then two wild cards; seeds follow that order.
            top_three = division_rank[:, members] < 3
            key += top_three * big + division_winner[:, members] * big
        order = np.argsort(-key, axis=1, kind="stable")
        ranks = np.empty_like(order)
        ranks[np.arange(sims)[:, None], order] = np.arange(len(members))[None, :]
        seed[:, members] = ranks + 1
        playoff[:, members] = ranks < config["playoffs"]["teamsPerConference"]
    return {"seed": seed, "playoff": playoff, "division_winner": division_winner, "division_rank": division_rank}


# --------------------------------------------------------------------------- playoffs


SERIES_PATTERNS = {
    1: [True],
    3: [True, True, True],
    5: [True, True, False, False, True],
    7: [True, True, False, False, True, False, True],
}
MLB_SEVEN = [True, True, False, False, False, True, True]


def play_series(rng, strength, top, bottom, home_edge, sigma, games, pattern=None, neutral=False, top_wins=0, bottom_wins=0):
    """Winner of a series between `top` (home advantage) and `bottom`, per simulation.

    `top_wins` and `bottom_wins` are games already won in a series under way.
    """
    pattern = pattern or SERIES_PATTERNS[games]
    need = len(pattern) // 2 + 1
    rows = np.arange(len(top))
    gap = strength[rows, top] - strength[rows, bottom]
    top_count = np.full(len(top), top_wins, dtype=np.int16)
    bottom_count = np.full(len(top), bottom_wins, dtype=np.int16)
    for game, top_at_home in enumerate(pattern):
        if game < top_wins + bottom_wins:
            continue
        edge = 0.0 if neutral else (home_edge if top_at_home else -home_edge)
        won = rng.random(len(top)) < _ndtr((gap + edge) / sigma)
        live = (top_count < need) & (bottom_count < need)
        top_count += live & won
        bottom_count += live & ~won
    return np.where(top_count >= need, top, bottom)


def higher_seed_first(a, b, seed_of):
    rows = np.arange(len(a))
    a_better = seed_of[rows, a] <= seed_of[rows, b]
    return np.where(a_better, a, b), np.where(a_better, b, a)


def better_record_first(a, b, record):
    rows = np.arange(len(a))
    a_better = record[rows, a] >= record[rows, b]
    return np.where(a_better, a, b), np.where(a_better, b, a)


def team_at_seed(seed: np.ndarray, members: np.ndarray, wanted: int) -> np.ndarray:
    """Team index holding conference seed `wanted` in every simulation."""
    hits = seed[:, members] == wanted
    return members[np.argmax(hits, axis=1)]


def simulate_playoffs(config, structure, rng, strength, seeding, record, ratings: Ratings, results=None, recorded=None) -> np.ndarray:
    """Champion (team index) per simulation.

    During the playoffs `results` maps (stage, team pair) to games won so far, and the
    known series are appended to `recorded` for the bracket on the page.
    """
    fmt = config["playoffs"]["format"]
    seed = seeding["seed"].copy()
    sims = seed.shape[0]
    home, sigma = ratings.home, ratings.sigma
    teams = structure.teams
    finalists = []

    def play(stage, top, bottom, games, pattern=None, neutral=False, conference=None):
        pattern = pattern or SERIES_PATTERNS[games]
        known = bool(np.all(top == top[0]) and np.all(bottom == bottom[0]))
        top_wins = bottom_wins = 0
        if results is not None and known:
            won = results.get((stage, frozenset((teams[top[0]], teams[bottom[0]]))), {})
            top_wins, bottom_wins = won.get(teams[top[0]], 0), won.get(teams[bottom[0]], 0)
        winner = play_series(rng, strength, top, bottom, home, sigma, games, pattern, neutral, top_wins, bottom_wins)
        if recorded is not None:
            need = len(pattern) // 2 + 1
            recorded.append(
                {
                    "stage": stage,
                    "conference": conference,
                    "top": teams[top[0]] if known else None,
                    "bottom": teams[bottom[0]] if known else None,
                    "topSeed": int(seed[0, top[0]]) if known else None,
                    "bottomSeed": int(seed[0, bottom[0]]) if known else None,
                    "topWins": top_wins,
                    "bottomWins": bottom_wins,
                    "bestOf": len(pattern),
                    "winner": (teams[top[0]] if top_wins >= need else teams[bottom[0]] if bottom_wins >= need else None),
                }
            )
        return winner

    for c in range(len(structure.conferences)):
        members = np.flatnonzero(structure.conference == c)
        label = structure.conferences[c]
        at = lambda n: team_at_seed(seed, members, n)  # noqa: E731
        if fmt == "nfl":
            wild = [play("WC", at(a), at(b), 1, conference=label) for a, b in ((2, 7), (3, 6), (4, 5))]
            remaining = np.stack([at(1)] + wild, axis=1)
            order = np.argsort(seed[np.arange(sims)[:, None], remaining], axis=1)
            ranked = np.take_along_axis(remaining, order, axis=1)
            semi_a = play("DIV", ranked[:, 0], ranked[:, 3], 1, conference=label)
            semi_b = play("DIV", ranked[:, 1], ranked[:, 2], 1, conference=label)
            finalists.append(play("CONF", *higher_seed_first(semi_a, semi_b, seed), 1, conference=label))
        elif fmt == "nba":
            # Play-in: 7 v 8 for the 7 seed; the loser hosts the 9 v 10 winner for the 8 seed.
            seven, eight, nine, ten = at(7), at(8), at(9), at(10)
            first = play("PI", seven, eight, 1, conference=label)
            loser = np.where(first == seven, eight, seven)
            second = play("PI", nine, ten, 1, conference=label)
            last = play("PI", loser, second, 1, conference=label)
            bracket = {n: at(n) for n in range(1, 7)}
            bracket[7], bracket[8] = first, last
            seeds = playoff_seed(seed, bracket)
            r1 = {pair: play("R1", bracket[pair[0]], bracket[pair[1]], 7, conference=label) for pair in ((1, 8), (4, 5), (3, 6), (2, 7))}
            semi_a = play("R2", *higher_seed_first(r1[(1, 8)], r1[(4, 5)], seeds), 7, conference=label)
            semi_b = play("R2", *higher_seed_first(r1[(2, 7)], r1[(3, 6)], seeds), 7, conference=label)
            finalists.append(play("CF", *higher_seed_first(semi_a, semi_b, seeds), 7, conference=label))
            seeding["playoff"][np.arange(sims), last] = True
            seeding["playoff"][np.arange(sims), first] = True
        elif fmt == "nhl":
            divisions = [d for d in range(len(structure.divisions)) if structure.division_conference[d] == c]
            leaders = []
            for d in divisions:
                div_members = np.flatnonzero(structure.division == d)
                ranks = seeding["division_rank"][:, div_members]
                leaders.append([div_members[np.argmax(ranks == k, axis=1)] for k in range(3)])
            wild_one, wild_two = at(7), at(8)
            first_leader, _ = better_record_first(leaders[0][0], leaders[1][0], record)
            first_is_a = first_leader == leaders[0][0]
            a_opponent = np.where(first_is_a, wild_two, wild_one)
            b_opponent = np.where(first_is_a, wild_one, wild_two)
            division_winners = []
            for leader_set, opponent in ((leaders[0], a_opponent), (leaders[1], b_opponent)):
                first_round = play("R1", leader_set[0], opponent, 7, conference=label)
                second_round = play("R1", *better_record_first(leader_set[1], leader_set[2], record), 7, conference=label)
                division_winners.append(play("R2", *better_record_first(first_round, second_round, record), 7, conference=label))
            finalists.append(play("CF", *better_record_first(division_winners[0], division_winners[1], record), 7, conference=label))
        elif fmt == "mlb":
            wc_a = play("F", at(3), at(6), 3, conference=label)
            wc_b = play("F", at(4), at(5), 3, conference=label)
            ds_a = play("D", at(1), wc_b, 5, conference=label)
            ds_b = play("D", at(2), wc_a, 5, conference=label)
            finalists.append(play("L", *higher_seed_first(ds_a, ds_b, seed), 7, pattern=MLB_SEVEN, conference=label))
        else:
            raise ValueError(f"Unknown playoff format {fmt}")

    top, bottom = better_record_first(finalists[0], finalists[1], record)
    if fmt == "nfl":
        return play("SB", top, bottom, 1, neutral=True)
    if fmt == "mlb":
        return play("W", top, bottom, 7, pattern=MLB_SEVEN)
    return play("F", top, bottom, 7)


def playoff_seed(seed: np.ndarray, bracket: dict[int, np.ndarray]) -> np.ndarray:
    """Seeds after the NBA play-in: play-in winners take seeds 7 and 8."""
    adjusted = seed.copy()
    rows = np.arange(seed.shape[0])
    adjusted[rows, bracket[7]] = 7
    adjusted[rows, bracket[8]] = 8
    return adjusted


# --------------------------------------------------------------------------- simulation


def simulate(
    config: dict[str, Any],
    sport: str,
    structure: Structure,
    games: list[Game],
    ratings: Ratings,
    season_left: float,
    simulations: int = SIMULATIONS,
    seed: int = SEED,
) -> dict[str, Any]:
    model = SPORT_MODELS[sport]
    teams = structure.teams
    count = len(teams)
    index = {team: i for i, team in enumerate(teams)}
    rng = np.random.default_rng(seed)
    records = team_records(games, structure, sport)
    remaining = [game for game in games if not game.played]

    base = {
        name: np.array([records[team][name] for team in teams], dtype=np.float64)
        for name in ("wins", "losses", "ties", "otLosses", "regulationWins", "divisionWins", "divisionLosses", "divisionTies", "conferenceWins", "conferenceLosses", "conferenceTies")
    }
    rating = np.array([ratings.rating[team] for team in teams])
    scale = model.drift * math.sqrt(min(max(season_left, 0.0), 1.0))
    strength = rating[None, :] + rng.normal(0.0, scale, (simulations, count))

    totals = {name: np.repeat(values[None, :], simulations, axis=0) for name, values in base.items()}
    # Games a team still has to play that are not on the schedule yet (NBA Cup week) are
    # played against an average opponent at a neutral site.
    per_team = config.get("gamesPerTeam")
    if per_team:
        scheduled = np.zeros(count)
        for game in games:
            scheduled[index[game.home]] += 1
            scheduled[index[game.away]] += 1
        missing = np.maximum(per_team - scheduled, 0)
        if missing.any():
            p = _ndtr(strength / ratings.sigma)
            extra_wins = rng.binomial(missing.astype(int)[None, :].repeat(simulations, axis=0), p)
            totals["wins"] += extra_wins
            totals["losses"] += missing[None, :] - extra_wins

    window = matter_window(remaining)
    window_home_win = np.zeros((simulations, len(window)), dtype=bool)
    if remaining:
        home_index = np.array([index[game.home] for game in remaining])
        away_index = np.array([index[game.away] for game in remaining])
        home_side = np.zeros((len(remaining), count), dtype=np.float32)
        away_side = np.zeros((len(remaining), count), dtype=np.float32)
        home_side[np.arange(len(remaining)), home_index] = 1
        away_side[np.arange(len(remaining)), away_index] = 1
        masks = {
            "division": (structure.division[home_index] == structure.division[away_index]).astype(np.float32),
            "conference": (structure.conference[home_index] == structure.conference[away_index]).astype(np.float32),
        }
        for start in range(0, simulations, CHUNK):
            rows = slice(start, min(start + CHUNK, simulations))
            block = strength[rows]
            p_home = _ndtr((block[:, home_index] - block[:, away_index] + ratings.home) / ratings.sigma)
            home_win = rng.random(p_home.shape) < p_home
            tie = rng.random(p_home.shape) < model.tie_rate if model.tie_rate else np.zeros_like(home_win)
            home_win &= ~tie
            away_win = ~home_win & ~tie
            window_home_win[rows] = home_win[:, window]
            hw, aw, tw = home_win.astype(np.float32), away_win.astype(np.float32), tie.astype(np.float32)

            def add(name: str, home_part: np.ndarray, away_part: np.ndarray) -> None:
                totals[name][rows] += home_part @ home_side + away_part @ away_side

            add("wins", hw, aw)
            add("ties", tw, tw)
            if sport == "ice-hockey":
                ot = (rng.random(p_home.shape) < model.overtime_rate).astype(np.float32)
                add("losses", aw * (1 - ot), hw * (1 - ot))
                add("otLosses", aw * ot, hw * ot)
                add("regulationWins", hw * (1 - ot), aw * (1 - ot))
            else:
                add("losses", aw, hw)
            for scope, mask in masks.items():
                add(f"{scope}Wins", hw * mask, aw * mask)
                add(f"{scope}Losses", aw * mask, hw * mask)
                add(f"{scope}Ties", tw * mask, tw * mask)

    noise = rng.random((simulations, count)) * 1e-3
    division_pct = (totals["divisionWins"] + 0.5 * totals["divisionTies"]) / np.maximum(totals["divisionWins"] + totals["divisionLosses"] + totals["divisionTies"], 1)
    conference_pct = (totals["conferenceWins"] + 0.5 * totals["conferenceTies"]) / np.maximum(totals["conferenceWins"] + totals["conferenceLosses"] + totals["conferenceTies"], 1)
    division_key, conference_key = rank_keys(
        sport, totals["wins"], totals["losses"], totals["ties"], totals["otLosses"], totals["regulationWins"], division_pct, conference_pct, noise
    )
    seeding = seed_conferences(config, structure, division_key, conference_key)
    record = conference_key  # league-wide comparison for home advantage in finals
    champion = simulate_playoffs(config, structure, rng, strength, seeding, record, ratings)

    best_record = np.zeros((simulations, count), dtype=bool)
    best_record[np.arange(simulations), np.argmax(conference_key, axis=1)] = True

    flags = {}
    for tier in config["tiers"]:
        kind = tier["kind"]
        if kind == "playoffs":
            flags[tier["key"]] = seeding["playoff"]
        elif kind == "division":
            flags[tier["key"]] = seeding["division_winner"]
        elif kind == "seed":
            flags[tier["key"]] = seeding["seed"] <= tier["size"]
        elif kind == "best-record":
            flags[tier["key"]] = best_record
        elif kind == "champion":
            won = np.zeros((simulations, count), dtype=bool)
            won[np.arange(simulations), champion] = True
            flags[tier["key"]] = won
        else:
            raise ValueError(f"Unknown tier kind {kind}")

    conference_size = int(max(np.bincount(structure.conference)))
    probabilities = {team: {key: round(float(flag[:, i].mean()) * 100, 2) for key, flag in flags.items()} for team, i in index.items()}
    positions = {
        team: [round(value * 100, 2) for value in np.bincount(seeding["seed"][:, i] - 1, minlength=conference_size) / simulations]
        for team, i in index.items()
    }
    expected = {}
    for team, i in index.items():
        item = {"wins": round(float(totals["wins"][:, i].mean()), 1), "seed": round(float(seeding["seed"][:, i].mean()), 1)}
        if sport == "ice-hockey":
            item["points"] = round(float((2 * totals["wins"][:, i] + totals["otLosses"][:, i]).mean()), 1)
        expected[team] = item

    matter = matches_that_matter([remaining[i] for i in window], window_home_win, flags, config["tiers"], teams)
    return {"simulations": simulations, "probabilities": probabilities, "positions": positions, "expected": expected, "matchesThatMatter": matter}


def simulate_postseason(
    config: dict[str, Any],
    structure: Structure,
    seeding_now: dict[str, np.ndarray],
    ratings: Ratings,
    games: list[PlayoffGame],
    simulations: int = SIMULATIONS,
) -> dict[str, Any] | None:
    """Title odds from the playoff results so far, or None if the real bracket differs from our seeds."""
    fmt = config["playoffs"]["format"]
    teams = structure.teams
    known = set(teams)
    results: dict[tuple[str, frozenset[str]], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for game in games:
        if game.winner and game.home in known and game.away in known:
            results[(game.stage, frozenset((game.home, game.away)))][game.winner] += 1
    seeding = {key: np.repeat(value, simulations, axis=0) for key, value in seeding_now.items()}
    strength = np.repeat(np.array([ratings.rating[team] for team in teams])[None, :], simulations, axis=0)
    recorded: list[dict[str, Any]] = []
    rng = np.random.default_rng(SEED)
    champion = simulate_playoffs(config, structure, rng, strength, seeding, seeding["conference_key"], ratings, results=results, recorded=recorded)

    # Our tiebreakers are simplified; if the real first round pairs other teams, the odds would be wrong.
    first_stage = STAGES[fmt][0][0]
    expected = {frozenset((item["top"], item["bottom"])) for item in recorded if item["stage"] == first_stage and item["top"]}
    actual = {frozenset((game.home, game.away)) for game in games if game.stage == first_stage and game.home in known and game.away in known}
    if not actual <= expected:
        return None

    final = next((item for item in recorded if item["stage"] == STAGES[fmt][-1][0]), None)
    return {
        "title": {team: round(float((champion == i).mean()) * 100, 2) for i, team in enumerate(teams)},
        "rounds": [{"key": code, "label": label, "series": [item for item in recorded if item["stage"] == code]} for code, label in STAGES[fmt]],
        "champion": final["winner"] if final else None,
    }


def matter_window(remaining: list[Game]) -> list[int]:
    """Indexes of the remaining games played within a few days of the next one."""
    if not remaining:
        return []
    first = min(game.date for game in remaining)
    return [i for i, game in enumerate(remaining) if game.date <= first + timedelta(days=MATTER_WINDOW_DAYS)]


def matches_that_matter(window_games, home_win, flags, tiers, teams) -> list[dict[str, Any]]:
    """Upcoming games whose result moves one team's chances the most."""
    labels = {tier["key"]: tier["label"] for tier in tiers}
    found = []
    for column, game in enumerate(window_games):
        won = home_win[:, column]
        if won.sum() < 200 or (~won).sum() < 200:
            continue
        best = None
        for key, flag in flags.items():
            if_home = flag[won].mean(axis=0)
            if_away = flag[~won].mean(axis=0)
            swings = np.abs(if_home - if_away)
            team = int(swings.argmax())
            if best is None or swings[team] > best[0]:
                best = (float(swings[team]), key, team, float(if_home[team]), float(if_away[team]))
        if best and best[0] >= 0.02:
            swing, key, team, if_home, if_away = best
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
                    "ifHome": round(if_home * 100, 1),
                    "ifAway": round(if_away * 100, 1),
                }
            )
    return sorted(found, key=lambda item: -item["swing"])[:MATCHES_THAT_MATTER]


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- payload


COLUMNS = {
    "american-football": [
        {"key": "wins", "label": "W"},
        {"key": "losses", "label": "L"},
        {"key": "ties", "label": "T", "optional": True},
        {"key": "pct", "label": "PCT", "format": "pct", "strong": True},
        {"key": "pointDifferential", "label": "DIFF", "signed": True, "optional": True},
        {"key": "divisionRecord", "label": "DIV", "optional": True},
        {"key": "streak", "label": "STRK", "optional": True},
    ],
    "basketball": [
        {"key": "wins", "label": "W"},
        {"key": "losses", "label": "L"},
        {"key": "pct", "label": "PCT", "format": "pct", "strong": True},
        {"key": "gamesBack", "label": "GB", "title": "Games behind the conference leader", "format": "decimal", "optional": True},
        {"key": "pointDifferential", "label": "DIFF", "title": "Average points margin", "signed": True, "format": "decimal", "optional": True},
        {"key": "lastTen", "label": "L10", "optional": True},
        {"key": "streak", "label": "STRK", "optional": True},
    ],
    "ice-hockey": [
        {"key": "played", "label": "GP", "optional": True},
        {"key": "wins", "label": "W"},
        {"key": "losses", "label": "L"},
        {"key": "otLosses", "label": "OTL", "title": "Overtime and shootout losses"},
        {"key": "points", "label": "PTS", "strong": True},
        {"key": "regulationWins", "label": "RW", "title": "Regulation wins", "optional": True},
        {"key": "pointDifferential", "label": "DIFF", "title": "Goal differential", "signed": True, "optional": True},
        {"key": "lastTen", "label": "L10", "optional": True},
    ],
    "baseball": [
        {"key": "wins", "label": "W"},
        {"key": "losses", "label": "L"},
        {"key": "pct", "label": "PCT", "format": "pct", "strong": True},
        {"key": "gamesBack", "label": "GB", "title": "Games behind the division leader", "format": "decimal", "optional": True},
        {"key": "pointDifferential", "label": "RD", "title": "Run differential", "signed": True, "optional": True},
        {"key": "lastTen", "label": "L10", "optional": True},
        {"key": "streak", "label": "STRK", "optional": True},
    ],
}


def streak(results: list[str]) -> str:
    if not results:
        return "–"
    last = results[-1]
    length = 0
    for outcome in reversed(results):
        if outcome != last:
            break
        length += 1
    return f"{last}{length}"


def last_ten(results: list[str], otl_results: list[bool] | None = None) -> str:
    recent = results[-10:]
    wins = recent.count("W")
    losses = recent.count("L")
    ties = recent.count("T")
    return f"{wins}-{losses}-{ties}" if ties else f"{wins}-{losses}"


def current_seeding(
    config: dict[str, Any], structure: Structure, records: dict[str, dict[str, Any]], sport: str, projected: dict[str, float]
) -> dict[str, np.ndarray]:
    """Seeds if the season ended today; exact ties (every team before opening day) go to the stronger projection."""
    teams = structure.teams
    arrays = {name: np.array([[records[team][name] for team in teams]], dtype=float) for name in records[teams[0]] if name != "results"}
    division_pct = (arrays["divisionWins"] + 0.5 * arrays["divisionTies"]) / np.maximum(arrays["divisionWins"] + arrays["divisionLosses"] + arrays["divisionTies"], 1)
    conference_pct = (arrays["conferenceWins"] + 0.5 * arrays["conferenceTies"]) / np.maximum(arrays["conferenceWins"] + arrays["conferenceLosses"] + arrays["conferenceTies"], 1)
    noise = np.array([[projected[team] * 1e-6 for team in teams]])
    division_key, conference_key = rank_keys(
        sport, arrays["wins"], arrays["losses"], arrays["ties"], arrays["otLosses"], arrays["regulationWins"], division_pct, conference_pct, noise
    )
    seeding = seed_conferences(config, structure, division_key, conference_key)
    seeding["conference_key"] = conference_key
    return seeding


def build_payload(config: dict[str, Any], now: datetime, cache_dir: Path) -> dict[str, Any]:
    sport = config["sport"]
    model = SPORT_MODELS[sport]
    structure = league_structure(config)
    season = team_sports.resolve_season(config, now)
    feed_games = season_games(config, season, cache_dir)
    games = regular_season(config, feed_games)
    warnings: list[str] = []
    try:
        previous = regular_season(config, season_games(config, team_sports.resolve_season(config, now, offset=-1), cache_dir, previous=True))
    except team_sports.FeedError as exc:
        previous = []
        warnings.append(f"Last season unavailable ({exc}); ratings use this season only.")
    if not games:
        raise team_sports.FeedError(f"{season.payload_id}: no regular-season games in the feed yet")

    teams = structure.teams
    cancelled = []
    if max(game.date for game in games) < now - timedelta(days=2):
        # The schedule is over: games never played (rainouts not made up) will not be.
        cancelled = [game for game in games if not game.played]
        games = [game for game in games if game.played]
    played = [game for game in games if game.played]
    remaining = [game for game in games if not game.played]
    pending = [game for game in remaining if game.date < now - timedelta(hours=8)]
    if pending:
        warnings.append(
            f"{len(pending)} past game{'s have' if len(pending) > 1 else ' has'} no result yet "
            "(postponed, or not yet updated at the source); they are simulated as still to play."
        )
    latest = max((game.date for game in played + [g for g in previous if g.played]), default=now)
    ratings = fit_ratings(games, previous, teams, model, min(latest, now))
    per_team = config.get("gamesPerTeam") or (2 * len(games) / len(teams))
    season_left = len(remaining) / max(len(games), 1)
    simulation = simulate(config, sport, structure, games, ratings, season_left)

    records = team_records(games, structure, sport)
    projected = {team: simulation["expected"][team]["wins"] for team in teams}
    seeding = current_seeding(config, structure, records, sport, projected)
    meta = team_sports.team_meta(config, teams)
    index = {team: i for i, team in enumerate(teams)}
    conference_names = {item["key"]: item["label"] for item in config["conferences"]}

    def win_pct(team: str) -> float:
        row = records[team]
        return pct(row["wins"], row["losses"] + row["otLosses"], row["ties"])

    league_order = sorted(teams, key=lambda team: -seeding["conference_key"][0, index[team]])
    standings = []
    for rank, team in enumerate(league_order, start=1):
        row = records[team]
        i = index[team]
        conference = config["teams"][team]["conference"]
        division = config["teams"][team]["division"]
        group_teams = [other for other in teams if config["teams"][other][("division" if sport == "baseball" else "conference")] == (division if sport == "baseball" else conference)]
        leader = max(group_teams, key=lambda other: (records[other]["wins"] - records[other]["losses"]))
        games_back = ((records[leader]["wins"] - row["wins"]) + (row["losses"] - records[leader]["losses"])) / 2
        item = {
            "teamKey": team,
            "shortName": meta[team]["shortName"],
            "fullName": meta[team]["fullName"],
            "rank": rank,
            "played": row["played"],
            "wins": row["wins"],
            "losses": row["losses"],
            "record": record_string(row["wins"], row["losses"], row["ties"] + row["otLosses"], show_extra=sport == "ice-hockey"),
            "pct": round(win_pct(team), 3),
            "pointDifferential": row["scored"] - row["allowed"],
            "conference": conference,
            "conferenceLabel": conference_names[conference],
            "division": division,
            "seed": int(seeding["seed"][0, i]),
            "divisionRank": int(seeding["division_rank"][0, i]) + 1,
            "form": list(reversed(row["results"][-5:])),
            "lastTen": last_ten(row["results"]),
            "streak": streak(row["results"]),
            "divisionRecord": record_string(row["divisionWins"], row["divisionLosses"], row["divisionTies"]),
            "remaining": sum(1 for game in remaining if team in (game.home, game.away)),
        }
        if sport == "american-football":
            item["ties"] = row["ties"]
        if sport == "ice-hockey":
            item["otLosses"] = row["otLosses"]
            item["points"] = 2 * row["wins"] + row["otLosses"]
            item["regulationWins"] = row["regulationWins"]
        if sport in ("basketball", "baseball"):
            item["gamesBack"] = games_back
        if sport == "basketball" and row["played"]:
            item["pointDifferential"] = round((row["scored"] - row["allowed"]) / row["played"], 1)
        standings.append(item)

    groups = []
    for conference in config["conferences"]:
        members = [team for team in teams if config["teams"][team]["conference"] == conference["key"]]
        groups.append(
            {
                "key": conference["key"],
                "label": conference["label"],
                "teams": sorted(members, key=lambda team: seeding["seed"][0, index[team]]),
                "cutoffs": config["playoffs"].get("cutoffs", [{"after": config["playoffs"]["teamsPerConference"], "label": "Playoff line"}]),
            }
        )
    for conference in config["conferences"]:
        for division in conference["divisions"]:
            members = [team for team in teams if config["teams"][team]["division"] == division]
            groups.append(
                {
                    "key": division,
                    "label": division,
                    "teams": sorted(members, key=lambda team: seeding["division_rank"][0, index[team]]),
                }
            )

    fixtures = []
    for game in sorted(remaining, key=lambda item: item.date):
        p_home = ratings.win_probability(game.home, game.away)
        fixtures.append(
            {
                "id": game.id,
                "round": game.round,
                "date": iso(game.date),
                "home": game.home,
                "away": game.away,
                "venue": game.venue,
                "probabilities": {"home": round(p_home, 3), "away": round(1 - p_home, 3)},
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
            **({"note": game.note} if game.note else {}),
        }
        for game in reversed(played)
    ]

    # After the regular season, title odds come from the playoff results so far; without a
    # playoff source (or when the real bracket differs from our seeds) the title column goes.
    postseason = None
    playoff_list: list[PlayoffGame] = []
    if not remaining:
        try:
            found = playoff_games(config, season, cache_dir, feed_games)
        except team_sports.FeedError as exc:
            found = None
            warnings.append(f"Playoff results unavailable ({exc}); title odds are left out.")
        if found is not None:
            playoff_list = [game for game in found if game.home in index and game.away in index]
            postseason = simulate_postseason(config, structure, seeding, ratings, playoff_list)
            if postseason is None:
                warnings.append("The real playoff bracket differs from our simplified tiebreakers, so title odds are left out.")
    if remaining:
        tiers = config["tiers"]
    elif postseason:
        tiers = [tier if tier["kind"] == "champion" and not postseason["champion"] else dict(tier, settled=True) for tier in config["tiers"]]
    else:
        tiers = [tier for tier in config["tiers"] if tier["kind"] != "champion"]
    tier_keys = {tier["key"] for tier in tiers}
    probabilities = {team: {key: value for key, value in values.items() if key in tier_keys} for team, values in simulation["probabilities"].items()}
    if postseason:
        champion_key = next(tier["key"] for tier in config["tiers"] if tier["kind"] == "champion")
        for team in teams:
            probabilities[team][champion_key] = postseason["title"][team]
        stage_names = {code: label for code, label in STAGES[config["playoffs"]["format"]]}
        # "If necessary" games of a finished series will not be played.
        decided = {
            (item["stage"], frozenset((item["top"], item["bottom"])))
            for stage in postseason["rounds"]
            for item in stage["series"]
            if item["winner"]
        }
        upcoming = sorted(
            (game for game in playoff_list if not game.played and (game.stage, frozenset((game.home, game.away))) not in decided),
            key=lambda game: game.date,
        )
        fixtures = [
            {
                "id": f"playoff-{i}",
                "round": None,
                "date": iso(game.date),
                "home": game.home,
                "away": game.away,
                "venue": None,
                "stage": stage_names.get(game.stage, game.stage),
                "probabilities": {"home": round(ratings.win_probability(game.home, game.away), 3), "away": round(1 - ratings.win_probability(game.home, game.away), 3)},
            }
            for i, game in enumerate(upcoming)
        ]
        played_playoffs = sorted((game for game in playoff_list if game.played), key=lambda game: game.date, reverse=True)
        results = [
            {
                "id": f"playoff-result-{i}",
                "round": None,
                "date": iso(game.date),
                "home": game.home,
                "away": game.away,
                "homeScore": game.home_score,
                "awayScore": game.away_score,
                "note": stage_names.get(game.stage, game.stage),
            }
            for i, game in enumerate(played_playoffs)
        ] + results
    source = config.get("sources", {}).get("provider")
    started = bool(played)
    name = TEAM_SPORT_NAMES[sport]
    notes = [
        f"Team ratings come from score margins (capped at {model.margin_cap:g}) with home advantage, fitted on this and last "
        f"season with a {model.half_life_days:g}-day half-life; last season counts {model.previous_weight:g}x as much on top.",
        f"The rest of the regular season is simulated {SIMULATIONS:,} times, letting team strength drift (more when more of "
        "the season is left), then the playoffs are simulated from each simulated table for title odds.",
        "Tiebreakers are simplified: "
        + ("points, then regulation wins, then wins" if sport == "ice-hockey" else "win percentage, then division or conference record")
        + "; head-to-head and common-games rules are not modelled.",
    ]
    if not started:
        notes.insert(0, f"The {name} season has not started: odds come from last season's ratings, pulled toward average.")
    if config.get("gamesPerTeam"):
        notes.append("Games not yet on the published schedule are simulated against an average opponent.")
    if cancelled:
        notes.append(f"{len(cancelled)} scheduled game{'s were' if len(cancelled) > 1 else ' was'} never played and {'are' if len(cancelled) > 1 else 'is'} left out.")
    if postseason:
        notes.append(
            f"Playoffs: series still to play are simulated {SIMULATIONS:,} times from the regular-season ratings, "
            "starting from the real series scores."
        )
    if remaining:
        status = "in_progress"
    elif postseason and not postseason["champion"]:
        status = "postseason"
    else:
        status = "complete"
    credits = []
    if postseason and config.get("postseason", {}).get("provider") == "mlb":
        credits.append({"name": "MLB Stats API", "url": "https://statsapi.mlb.com/", "note": "Playoff results: MLB Stats API"})

    return {
        "metadata": {
            "season": season.label,
            "generated_at": iso(now),
            "source": NHL_SOURCE if source == "nhl" else team_sports.FEED_SOURCE,
            "source_url": NHL_SOURCE_URL if source == "nhl" else team_sports.FEED_SOURCE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": status,
            "warnings": warnings,
            **({"credits": credits} if credits else {}),
        },
        "league": {
            "id": season.payload_id,
            "configId": config["id"],
            "sport": sport,
            "name": config["name"],
            "shortName": config["shortName"],
            "headline": config.get("headline"),
            "season": season.label,
            "seasonLabel": season.label,
            "priority": config.get("priority", 100),
            "tiers": tiers,
            "columns": COLUMNS[sport],
            "outcomes": ["home", "away"],
            "teams": [meta[team] for team in teams],
            "groups": groups,
            "rankLabel": "League",
            "positionLabel": "Conference seed" if sport != "baseball" else "League seed",
            "positionZones": config["playoffs"].get("zones", [{"to": config["playoffs"]["teamsPerConference"], "kind": "top"}]),
        },
        "standings": standings,
        "fixtures": fixtures,
        "results": results,
        "analysis": {
            "method": "Monte Carlo",
            "simulations": simulation["simulations"],
            "model": "Margin ratings model",
            "modelNotes": notes,
            "probabilities": probabilities,
            "positions": simulation["positions"],
            "expected": simulation["expected"],
            "ratings": {team: round(ratings.rating[team], 2) for team in teams},
            "homeAdvantage": round(ratings.home, 2),
            "sigma": round(ratings.sigma, 2),
            "gamesPerTeam": per_team,
        },
        "matchesThatMatter": simulation["matchesThatMatter"] if remaining else [],
        **({"bracket": {"rounds": postseason["rounds"], "champion": postseason["champion"]}} if postseason else {}),
        **({"playoffs": {"champion": postseason["champion"]}} if postseason and postseason["champion"] else {}),
    }
