"""Football leagues that end in playoffs (MLS, NWSL): tables, seeding and a bracket.

A config with ``"engine": "football_playoffs"`` is a rolling football config (see
football.py) with four additions:

* ``conferences``, and a ``conference`` for every team: the tables playoff seeds come
  from. A league seeded as one table (the NWSL) leaves them out.
* ``tiebreakers``: the order that separates teams level on points (``wins``,
  ``goal-difference``, ``goals-for``, ``head-to-head``, ``head-to-head-points``,
  ``head-to-head-goals``, ``away-goal-difference``, ``away-goals``,
  ``home-goal-difference``, ``home-goals``).
* ``playoffs.rounds``: the bracket, round by round (see ``parse_rounds``). A round is
  single matches, best-of series or two-legged ties; it is played in every conference
  or once across them (a final); its pairs are fixed seeds and earlier winners (or
  losers), or its teams are reseeded highest against lowest. Teams that start in a
  later round have a bye. A round at a neutral ground can name, per season, the club
  whose home that ground is (``homeGround``).
* ``sources.espn``: ESPN's league code. ESPN's public scoreboard supplies the playoff
  results and cross-checks FixtureDownload's scores; ESPN's table supplies the official
  order of teams our tiebreakers cannot separate, and any points deductions. A
  FixtureDownload feed that also lists the playoffs (the NWSL's) is cut to its regular
  season (``split_postseason``).

The regular season is simulated with football.py's goals model, letting team strength
drift; each simulated table is seeded and the bracket is played out on the same
simulated strengths. Penalties are a coin flip. Real results replace simulated ones as
they happen.
"""

from __future__ import annotations

import dataclasses
import json
import math
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

import football
import team_sports
from team_sports import Game


SIMULATIONS = 20_000
SEED = 20261003
# Extra time is a third of a match.
EXTRA_TIME_SHARE = 1 / 3
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={year}&limit=1000"
ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings?season={year}"
ESPN_SITE_URL = "https://www.espn.com/soccer/"
# A FixtureDownload game and an ESPN game are the same match when the same home and away
# teams meet within this many hours.
SAME_MATCH_HOURS = 36
MATCH_TYPES = {"single", "series", "two-legged"}
DECIDERS = {"extra-time", "penalties", "higher-seed"}
# Tiebreakers that are season totals, so simulated tables can use them directly.
TOTAL_STEPS = {
    "wins": "wins",
    "goal-difference": "goalDifference",
    "goals-for": "goalsFor",
}
TIEBREAK_TEXT = {
    "wins": "wins",
    "goal-difference": "goal difference",
    "goals-for": "goals scored",
    "head-to-head": "head-to-head points and goal difference",
    "head-to-head-points": "head-to-head points",
    "head-to-head-goals": "head-to-head goals",
    "away-goal-difference": "away goal difference",
    "away-goals": "away goals",
    "home-goal-difference": "home goal difference",
    "home-goals": "home goals",
}


# ---------------------------------------------------------------------------
# The bracket


@dataclass(frozen=True)
class Slot:
    """One side of a tie: a seed, or the winner (or loser) of an earlier tie.

    Written in a config as ``8`` (the 8th seed), ``"WC.1"`` (the winner of tie 1 of round
    WC), ``"R1.2.loser"`` and, in a round played across conferences, ``"East:CF.1"`` or
    ``"East:1"``.
    """

    group: str | None
    seed: int | None = None
    round: str | None = None
    tie: int | None = None
    loser: bool = False


def parse_slot(value: Any) -> Slot:
    text = str(value)
    group = None
    if ":" in text:
        group, text = text.split(":", 1)
    if text.isdigit():
        return Slot(group, seed=int(text))
    loser = text.endswith(".loser")
    if loser:
        text = text[: -len(".loser")]
    round_key, _, number = text.rpartition(".")
    if not round_key or not number.isdigit():
        raise ValueError(f"unreadable bracket slot {value!r}")
    return Slot(group, round=round_key, tie=int(number), loser=loser)


@dataclass(frozen=True)
class Round:
    key: str
    label: str
    match: str
    pairs: tuple[tuple[Slot, Slot], ...]
    teams: tuple[Slot, ...]
    across: bool
    best_of: int
    # For series: does the higher seed host game n?
    hosts: tuple[bool, ...]
    # What settles a level match or tie: extra time then penalties, penalties at once, or the higher seed.
    decider: str
    neutral: bool
    # A neutral round's ground can be one club's home (the 2026 NWSL Championship at the
    # Washington Spirit's Audi Field): that club plays the round at home.
    host: str | None = None

    @property
    def reseed(self) -> bool:
        return bool(self.teams)

    @property
    def tie_count(self) -> int:
        return len(self.teams) // 2 if self.reseed else len(self.pairs)


def host_pattern(pattern: str, best_of: int) -> tuple[bool, ...]:
    """'1-1-1' -> higher seed hosts games 1 and 3; '2-2-1' -> games 1, 2 and 5."""
    hosts: list[bool] = []
    for block, size in enumerate(int(part) for part in pattern.split("-")):
        hosts += [block % 2 == 0] * size
    if len(hosts) != best_of:
        raise ValueError(f"host pattern {pattern} does not cover {best_of} games")
    return tuple(hosts)


def parse_rounds(config: dict[str, Any], year: int | None = None) -> list[Round]:
    """The bracket from ``playoffs.rounds``, checked so a bad config fails before its first run.

    ``year`` picks each neutral round's ``homeGround`` for that season (none without it).
    """
    name = config.get("id", "?")
    groups = {conference["key"] for conference in group_list(config)}
    rounds: list[Round] = []
    seen: dict[str, Round] = {}
    for raw in (config.get("playoffs") or {}).get("rounds", []):
        match = raw.get("match", "single")
        if match not in MATCH_TYPES:
            raise ValueError(f"{name}: round {raw.get('key')} has an unknown match type {match!r}")
        best_of = raw.get("bestOf", 1 if match == "single" else 3 if match == "series" else 2)
        decider = raw.get("decider", "extra-time")
        if decider not in DECIDERS:
            raise ValueError(f"{name}: round {raw.get('key')} has an unknown decider {decider!r}")
        if match == "series" and decider == "higher-seed":
            raise ValueError(f"{name}: every series game needs a winner")
        if bool(raw.get("pairs")) == bool(raw.get("teams")):
            raise ValueError(f"{name}: round {raw.get('key')} needs either pairs (a fixed bracket) or teams (reseeded)")
        teams = tuple(parse_slot(slot) for slot in raw.get("teams", []))
        if len(teams) % 2:
            raise ValueError(f"{name}: round {raw.get('key')} needs an even number of teams")
        grounds = raw.get("homeGround") or {}
        if grounds and (not raw.get("neutral") or match != "single"):
            raise ValueError(f"{name}: only a neutral round of single matches can name a homeGround")
        item = Round(
            key=raw["key"],
            label=raw["label"],
            match=match,
            pairs=tuple((parse_slot(a), parse_slot(b)) for a, b in raw.get("pairs", [])),
            teams=teams,
            across=bool(raw.get("across")) or len(groups) == 1,
            best_of=best_of,
            hosts=host_pattern(raw.get("hosts", "-".join("1" * best_of)), best_of) if match == "series" else (),
            decider=decider,
            neutral=bool(raw.get("neutral")),
            host=grounds.get(str(year)) if year is not None else None,
        )
        if item.key in seen:
            raise ValueError(f"{name}: round {item.key} appears twice")
        slots = [slot for pair in item.pairs for slot in pair] + list(item.teams)
        for slot in slots:
            if item.across and len(groups) > 1 and slot.group is None and slot.round not in {key for key, r in seen.items() if r.across}:
                raise ValueError(f"{name}: round {item.key} is played across conferences, so {slot} needs a conference")
            if slot.group is not None and slot.group not in groups:
                raise ValueError(f"{name}: unknown conference {slot.group} in round {item.key}")
            if slot.round is not None:
                earlier = seen.get(slot.round)
                if earlier is None:
                    raise ValueError(f"{name}: round {item.key} uses round {slot.round} before it is played")
                if not 1 <= slot.tie <= earlier.tie_count:
                    raise ValueError(f"{name}: round {slot.round} has no tie {slot.tie}")
                if earlier.across and not item.across:
                    raise ValueError(f"{name}: a conference round cannot follow a round played across conferences")
        seen[item.key] = item
        rounds.append(item)
    if rounds:
        last = rounds[-1]
        if last.tie_count != 1 or not last.across:
            raise ValueError(f"{name}: the last round must be a single tie (the final)")
    return rounds


def qualifiers(rounds: list[Round]) -> int:
    """Teams per conference that reach the playoffs: the deepest seed the bracket names."""
    seeds = [slot.seed for item in rounds for pair in item.pairs for slot in pair] + [slot.seed for item in rounds for slot in item.teams]
    return max((seed for seed in seeds if seed), default=0)


def group_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    return config.get("conferences") or [{"key": "League", "label": config.get("shortName", "League")}]


def team_group(config: dict[str, Any], team: str) -> str:
    groups = group_list(config)
    if len(groups) == 1:
        return groups[0]["key"]
    conference = (config.get("teams", {}).get(team) or {}).get("conference")
    if conference not in {group["key"] for group in groups}:
        raise team_sports.FeedError(f"{team} has no conference in leagues/{config['id']}.json; add it to the config")
    return conference


# ---------------------------------------------------------------------------
# Sources


def rename(games: list[Game], aliases: dict[str, str]) -> list[Game]:
    """The same team is written differently by different feeds and seasons."""
    return [dataclasses.replace(game, home=aliases.get(game.home, game.home), away=aliases.get(game.away, game.away)) for game in games]


def split_postseason(games: list[Game], playoff_teams: int) -> tuple[list[Game], list[Game]]:
    """A feed's regular season, and the playoff games some feeds also list (the NWSL's do).

    Every club plays the same number of regular-season games and those that miss the playoffs
    play no more, so with the clubs ordered by their games in the feed, the one just below the
    ``playoff_teams`` busiest has played exactly a season (a game missing from the feed leaves
    two clubs a game short without changing that). A club's games beyond that many are playoff
    games, and so is every game of a side with under half the busiest club's games (a
    placeholder such as "To be announced"). A feed of only the regular season is unchanged.
    """
    counts = Counter(team for game in games for team in (game.home, game.away))
    if not counts:
        return list(games), []
    busiest = max(counts.values())
    clubs = {team for team, count in counts.items() if 2 * count >= busiest}
    fewest_first = sorted(counts[team] for team in clubs)
    length = fewest_first[max(len(fewest_first) - playoff_teams, 1) - 1]
    played: Counter = Counter()
    regular, postseason = [], []
    for game in sorted(games, key=lambda item: (item.date, item.id)):
        if game.home in clubs and game.away in clubs and played[game.home] < length and played[game.away] < length:
            played[game.home] += 1
            played[game.away] += 1
            regular.append(game)
        else:
            postseason.append(game)
    return regular, postseason


@dataclass(frozen=True)
class EspnMatch:
    date: datetime
    home: str
    away: str
    # Goals including extra time; None until played.
    home_score: int | None
    away_score: int | None
    home_shootout: int | None
    away_shootout: int | None
    completed: bool
    # "pre", "in" or "post"; cancelled "if necessary" games are left out.
    state: str
    extra_time: bool
    season: str

    @property
    def regular(self) -> bool:
        return "regular" in self.season

    @property
    def winner(self) -> str | None:
        if not self.completed or self.home_score is None or self.away_score is None:
            return None
        if self.home_score != self.away_score:
            return self.home if self.home_score > self.away_score else self.away
        if self.home_shootout is not None and self.away_shootout is not None and self.home_shootout != self.away_shootout:
            return self.home if self.home_shootout > self.away_shootout else self.away
        return None


def parse_scoreboard(data: dict[str, Any]) -> list[dict[str, Any]]:
    """ESPN's scoreboard reduced to what the engine reads (raises if the format changed)."""
    rows = []
    for event in data["events"]:
        competition = event["competitions"][0]
        status = competition["status"]["type"]
        if "CANCEL" in status.get("name", "") or "POSTPONED" in status.get("name", ""):
            continue
        sides = {item["homeAway"]: item for item in competition["competitors"]}
        if set(sides) != {"home", "away"}:
            continue
        completed = bool(status.get("completed"))

        def score(side: str, key: str = "score") -> int | None:
            value = sides[side].get(key)
            return int(float(value)) if completed and value not in (None, "") else None

        rows.append(
            {
                "date": event["date"],
                "home": sides["home"]["team"]["displayName"],
                "away": sides["away"]["team"]["displayName"],
                "homeScore": score("home"),
                "awayScore": score("away"),
                "homeShootout": score("home", "shootoutScore"),
                "awayShootout": score("away", "shootoutScore"),
                "completed": completed,
                "state": status.get("state", "pre"),
                "extraTime": "AET" in status.get("name", "") or "PEN" in status.get("name", ""),
                "season": (event.get("season") or {}).get("slug", ""),
            }
        )
    if not rows and data["events"]:
        raise ValueError("no readable games")
    return rows


def _cached(path: Path, url: str, parse, max_age_hours: float) -> tuple[Any, str | None]:
    """A parsed download, refreshed when stale; the last good copy (and a warning) if the source fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return json.loads(path.read_text(encoding="utf-8")), None
    try:
        parsed = parse(team_sports.get_json(url))
        path.write_text(json.dumps(parsed), encoding="utf-8")
        return parsed, None
    except Exception as exc:  # noqa: BLE001 - a changed or unreachable source falls back to the last copy
        if not path.exists():
            raise team_sports.FeedError(f"{url}: {exc}") from exc
        saved = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%d %b %H:%M UTC")
        print(f"{url}: using the cached copy ({exc})")
        return json.loads(path.read_text(encoding="utf-8")), f"ESPN could not be read ({type(exc).__name__}); using its copy from {saved}."


def fetch_espn_matches(league: str, year: int, cache_dir: Path, aliases: dict[str, str], max_age_hours: float = 3) -> tuple[list[EspnMatch], str | None]:
    rows, warning = _cached(
        cache_dir / f"espn-{league}-scoreboard-{year}.json", ESPN_SCOREBOARD_URL.format(league=league, year=year), parse_scoreboard, max_age_hours
    )
    matches = [
        EspnMatch(
            date=datetime.fromisoformat(row["date"].replace("Z", "+00:00")),
            home=aliases.get(row["home"], row["home"]),
            away=aliases.get(row["away"], row["away"]),
            home_score=row["homeScore"],
            away_score=row["awayScore"],
            home_shootout=row["homeShootout"],
            away_shootout=row["awayShootout"],
            completed=row["completed"],
            state=row["state"],
            extra_time=row["extraTime"],
            season=row["season"],
        )
        for row in rows
    ]
    return sorted(matches, key=lambda match: match.date), warning


def parse_standings(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for child in data["children"]:
        for entry in child["standings"]["entries"]:
            stats = {item["name"]: item.get("value") for item in entry["stats"]}
            rows.append(
                {
                    "team": entry["team"]["displayName"],
                    "group": child.get("abbreviation") or child.get("name"),
                    "rank": int(stats["rank"]),
                    "played": int(stats["gamesPlayed"]),
                    "wins": int(stats["wins"]),
                    "draws": int(stats["ties"]),
                    "losses": int(stats["losses"]),
                    "goalsFor": int(stats["pointsFor"]),
                    "goalsAgainst": int(stats["pointsAgainst"]),
                    "points": int(stats["points"]),
                }
            )
    return rows


def fetch_espn_table(league: str, year: int, cache_dir: Path, aliases: dict[str, str]) -> list[dict[str, Any]]:
    rows, _ = _cached(cache_dir / f"espn-{league}-standings-{year}.json", ESPN_STANDINGS_URL.format(league=league, year=year), parse_standings, 3)
    return [dict(row, team=aliases.get(row["team"], row["team"])) for row in rows]


def corrected_games(games: list[Game], espn: list[EspnMatch]) -> tuple[list[Game], list[tuple[Game, Game]]]:
    """FixtureDownload's results, with ESPN's score where the two differ or only ESPN has one.

    FixtureDownload occasionally swaps or mistypes a score; ESPN's scores agree with the
    official standings, so they win. Each changed result is returned as (before, after).
    """
    by_pair: dict[tuple[str, str], list[EspnMatch]] = {}
    for match in espn:
        if match.regular and match.completed and match.home_score is not None:
            by_pair.setdefault((match.home, match.away), []).append(match)
    fixed, changes = [], []
    for game in games:
        candidates = [match for match in by_pair.get((game.home, game.away), []) if abs((match.date - game.date).total_seconds()) <= SAME_MATCH_HOURS * 3600]
        if len(candidates) == 1 and (game.home_score, game.away_score) != (candidates[0].home_score, candidates[0].away_score):
            corrected = dataclasses.replace(game, home_score=candidates[0].home_score, away_score=candidates[0].away_score)
            if game.played:
                changes.append((game, corrected))
            game = corrected
        fixed.append(game)
    return fixed, changes


def local_day(value: datetime, config: dict[str, Any]) -> str:
    """A match day as the league's fans know it (an evening kick-off in the US is the next day in UTC)."""
    zone = ZoneInfo(config["timezone"]) if config.get("timezone") else timezone.utc
    local = value.astimezone(zone)
    return f"{local.day} {local.strftime('%b')}"


# ---------------------------------------------------------------------------
# Tables


def table_rows(games: list[Game], teams: list[str], points: dict[str, int]) -> dict[str, dict[str, int]]:
    """football.standings plus the home and away splits that MLS's late tiebreakers use."""
    rows = football.standings(games, teams, points["win"], points["draw"])
    for row in rows.values():
        row.update(homeGoalsFor=0, homeGoalsAgainst=0, awayGoalsFor=0, awayGoalsAgainst=0)
    for game in games:
        if game.played and game.home in rows and game.away in rows:
            rows[game.home]["homeGoalsFor"] += game.home_score
            rows[game.home]["homeGoalsAgainst"] += game.away_score
            rows[game.away]["awayGoalsFor"] += game.away_score
            rows[game.away]["awayGoalsAgainst"] += game.home_score
    return rows


def rank_teams(
    teams: list[str],
    rows: dict[str, dict[str, int]],
    games: list[Game],
    steps: list[str],
    group_of: dict[str, str],
    fallback: dict[str, int] | None = None,
) -> list[str]:
    """Points, then the league's tiebreakers, applied in turn to the teams still level.

    Head-to-head (points, then goal difference in games among the tied teams; or points and
    goals as separate steps, as in the NWSL) applies only when they are all in one
    conference, as in MLS. Each step is taken among the teams the previous one left level.
    With ``fallback`` (each team's place in its conference table), teams of one conference
    that are level keep their conference order, so the league table never contradicts the
    conference tables; teams level on everything else are ordered by name.
    """

    def value(step: str, team: str, group: list[str]) -> tuple[int, ...]:
        row = rows[team]
        if step in TOTAL_STEPS:
            return (row[TOTAL_STEPS[step]],)
        if step == "away-goal-difference":
            return (row["awayGoalsFor"] - row["awayGoalsAgainst"],)
        if step == "away-goals":
            return (row["awayGoalsFor"],)
        if step == "home-goal-difference":
            return (row["homeGoalsFor"] - row["homeGoalsAgainst"],)
        if step == "home-goals":
            return (row["homeGoalsFor"],)
        if step in ("head-to-head", "head-to-head-points", "head-to-head-goals"):
            if len({group_of[other] for other in group}) > 1:
                return (0,)
            members = set(group)
            among = football.standings([game for game in games if game.played and game.home in members and game.away in members], group)
            if step == "head-to-head-points":
                return (among[team]["points"],)
            if step == "head-to-head-goals":
                return (among[team]["goalsFor"],)
            return (among[team]["points"], among[team]["goalDifference"])
        raise ValueError(f"unknown tiebreaker {step}")

    def order(group: list[str], remaining: list[str]) -> list[str]:
        if len(group) < 2:
            return group
        if fallback and len({group_of[team] for team in group}) == 1:
            return sorted(group, key=lambda team: (fallback[team], team))
        if not remaining:
            return sorted(group)
        step, rest = remaining[0], remaining[1:]
        values = {team: value(step, team, group) for team in group}
        result = []
        for level in sorted(set(values.values()), reverse=True):
            result += order([team for team in group if values[team] == level], rest)
        return result

    result = []
    for level in sorted({rows[team]["points"] for team in teams}, reverse=True):
        result += order(sorted(team for team in teams if rows[team]["points"] == level), list(steps))
    return result


def official_order(
    rows: dict[str, dict[str, int]], official: list[dict[str, Any]], groups: dict[str, list[str]]
) -> tuple[dict[str, list[str]] | None, dict[str, int]]:
    """The published conference order and points deductions, when every record agrees.

    The order settles ties our data cannot (MLS's fifth tiebreaker is disciplinary points).
    A team whose points differ from its record has had points deducted.
    """
    fields = ("played", "wins", "draws", "losses", "goalsFor", "goalsAgainst")
    published = {row["team"]: row for row in official}
    if set(published) != set(rows) or any(tuple(published[team][f] for f in fields) != tuple(rows[team][f] for f in fields) for team in rows):
        return None, {}
    adjustments = {team: published[team]["points"] - rows[team]["points"] for team in rows if published[team]["points"] != rows[team]["points"]}
    order = {}
    for key, members in groups.items():
        order[key] = sorted(members, key=lambda team: published[team]["rank"])
    return order, adjustments


# ---------------------------------------------------------------------------
# Simulation


class Bracket:
    """Plays the bracket in every simulation at once.

    ``seeds[group]`` holds each simulation's teams in seed order, ``position`` each team's
    place in its conference and ``overall`` its place in the league table (both 0-based):
    the higher seed hosts within a conference, and the better overall record across them.
    """

    def __init__(self, rng, mu, home, attack, defence, seeds, position, overall, real=None, hosts=None):
        self.rng, self.mu, self.home = rng, mu, home
        self.attack, self.defence = attack, defence
        self.seeds, self.position, self.overall = seeds, position, overall
        self.real = real or {}
        # Round key -> index of the club whose home a neutral round is played at.
        self.hosts = hosts or {}
        self.sims, self.count = position.shape
        self.rows = np.arange(self.sims)

    def goals(self, home: np.ndarray, away: np.ndarray, share: float = 1.0, neutral: bool = False, advantage=None) -> tuple[np.ndarray, np.ndarray]:
        if advantage is None:
            advantage = 0.0 if neutral else self.home
        home_rate = np.exp(self.mu + advantage + self.attack[self.rows, home] - self.defence[self.rows, away]) * share
        away_rate = np.exp(self.mu + self.attack[self.rows, away] - self.defence[self.rows, home]) * share
        return self.rng.poisson(home_rate), self.rng.poisson(away_rate)

    def settle(self, home_goals, away_goals, home, away, decider: str, neutral: bool, home_is_top: np.ndarray | bool, advantage=None) -> np.ndarray:
        """Whether the home side wins a level-or-not match after its decider."""
        home_wins = home_goals > away_goals
        level = home_goals == away_goals
        if decider == "extra-time":
            extra_home, extra_away = self.goals(home, away, EXTRA_TIME_SHARE, neutral, advantage)
            home_wins |= level & (extra_home > extra_away)
            level &= extra_home == extra_away
        elif decider == "higher-seed":
            home_wins |= level & home_is_top
            level &= False
        return home_wins | (level & (self.rng.random(self.sims) < 0.5))

    def single(self, item: Round, top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
        host = self.hosts.get(item.key)
        if host is None:
            home_goals, away_goals = self.goals(top, bottom, neutral=item.neutral)
            return self.settle(home_goals, away_goals, top, bottom, item.decider, item.neutral, True)
        # A neutral ground that is one side's home: that side plays at home, any other pair on neutral ground.
        swap = bottom == host
        home, away = np.where(swap, bottom, top), np.where(swap, top, bottom)
        advantage = np.where(home == host, self.home, 0.0)
        home_goals, away_goals = self.goals(home, away, advantage=advantage)
        home_wins = self.settle(home_goals, away_goals, home, away, item.decider, item.neutral, ~swap, advantage)
        return np.where(swap, ~home_wins, home_wins)

    def series(self, item: Round, top, bottom, top_wins, bottom_wins) -> np.ndarray:
        need = item.best_of // 2 + 1
        top_wins, bottom_wins = top_wins.copy(), bottom_wins.copy()
        for game, top_hosts in enumerate(item.hosts):
            active = (top_wins < need) & (bottom_wins < need) & (top_wins + bottom_wins == game)
            if not active.any():
                continue
            home, away = (top, bottom) if top_hosts else (bottom, top)
            home_goals, away_goals = self.goals(home, away, neutral=item.neutral)
            home_wins = self.settle(home_goals, away_goals, home, away, item.decider, item.neutral, top_hosts)
            top_won = home_wins if top_hosts else ~home_wins
            top_wins += active & top_won
            bottom_wins += active & ~top_won
        return top_wins >= need

    def two_legged(self, item: Round, top, bottom, first_leg) -> np.ndarray:
        """The lower seed hosts the first leg; ``first_leg`` holds real first-leg goals (top, bottom) or -1."""
        first_bottom, first_top = self.goals(bottom, top, neutral=item.neutral)
        played = first_leg[0] >= 0
        first_top = np.where(played, first_leg[0], first_top)
        first_bottom = np.where(played, first_leg[1], first_bottom)
        second_top, second_bottom = self.goals(top, bottom, neutral=item.neutral)
        top_total, bottom_total = first_top + second_top, first_bottom + second_bottom
        # The decider is played at the second leg, at the higher seed's ground.
        return self.settle(top_total, bottom_total, top, bottom, item.decider, item.neutral, True)

    def play(self, item: Round, top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
        """Whether the higher seed goes through, with real results in place of simulated ones."""
        fixed = np.full(self.sims, -1)
        top_wins = np.zeros(self.sims, dtype=np.int64)
        bottom_wins = np.zeros(self.sims, dtype=np.int64)
        first_leg = np.full((2, self.sims), -1)
        if self.real:
            codes = top * self.count + bottom
            for code in np.unique(codes):
                a, b = divmod(int(code), self.count)
                games = self.real.get(frozenset((a, b)))
                if not games:
                    continue
                mask = codes == code
                state = real_state(item, a, b, games)
                if state["winner"] is not None:
                    fixed[mask] = int(state["winner"] == a)
                top_wins[mask], bottom_wins[mask] = state["topWins"], state["bottomWins"]
                if state["firstLeg"] is not None:
                    first_leg[0, mask], first_leg[1, mask] = state["firstLeg"]
        if item.match == "series":
            simulated = self.series(item, top, bottom, top_wins, bottom_wins)
        elif item.match == "two-legged":
            simulated = self.two_legged(item, top, bottom, first_leg)
        else:
            simulated = self.single(item, top, bottom)
        return np.where(fixed >= 0, fixed == 1, simulated)

    def run(self, rounds: list[Round]) -> tuple[dict[str, np.ndarray], np.ndarray]:
        results: dict[tuple[str | None, str, int], tuple[np.ndarray, np.ndarray]] = {}
        reached = {item.key: np.zeros((self.sims, self.count), dtype=bool) for item in rounds}

        def resolve(slot: Slot, context: str | None) -> np.ndarray:
            group = slot.group or context
            if group is None and slot.seed is not None:
                # A league seeded as one table.
                group = next(iter(self.seeds))
            if slot.seed is not None:
                return self.seeds[group][:, slot.seed - 1]
            winner, loser = results[(group, slot.round, slot.tie)]
            return loser if slot.loser else winner

        last = None
        for item in rounds:
            rank = self.overall if item.across else self.position
            for context in [None] if item.across else list(self.seeds):
                if item.reseed:
                    sides = np.stack([resolve(slot, context) for slot in item.teams], axis=1)
                    order = np.argsort(np.take_along_axis(rank, sides, axis=1), axis=1, kind="stable")
                    ranked = np.take_along_axis(sides, order, axis=1)
                    pairs = [(ranked[:, i], ranked[:, -1 - i]) for i in range(item.tie_count)]
                else:
                    pairs = [(resolve(a, context), resolve(b, context)) for a, b in item.pairs]
                for number, (a, b) in enumerate(pairs, start=1):
                    a_first = rank[self.rows, a] <= rank[self.rows, b]
                    top, bottom = np.where(a_first, a, b), np.where(a_first, b, a)
                    top_through = self.play(item, top, bottom)
                    results[(context, item.key, number)] = (np.where(top_through, top, bottom), np.where(top_through, bottom, top))
                    reached[item.key][self.rows, top] = True
                    reached[item.key][self.rows, bottom] = True
                    last = (context, item.key, number)
        champion = results[last][0] if last else np.full(self.sims, -1)
        return reached, champion


def real_state(item: Round, top: Any, bottom: Any, games: list[Any]) -> dict[str, Any]:
    """Where a tie stands from its real games: series wins, a first leg, or its winner.

    ``games`` are completed matches between the two teams, oldest first; teams are compared
    by whatever identifies them (names, or indices in the simulation).
    """
    state: dict[str, Any] = {"winner": None, "topWins": 0, "bottomWins": 0, "firstLeg": None, "top": 0, "bottom": 0}

    def goals(game, team) -> int:
        return game.home_score if game.home == team else game.away_score

    if item.match == "series":
        for game in games:
            state["topWins" if game.winner == top else "bottomWins"] += game.winner is not None
        need = item.best_of // 2 + 1
        if state["topWins"] >= need or state["bottomWins"] >= need:
            state["winner"] = top if state["topWins"] >= need else bottom
        return state
    for game in games[: item.best_of if item.match == "two-legged" else 1]:
        state["top"] += goals(game, top)
        state["bottom"] += goals(game, bottom)
    if item.match == "two-legged":
        if len(games) == 1:
            state["firstLeg"] = (goals(games[0], top), goals(games[0], bottom))
        elif len(games) >= 2:
            # The aggregate decides, not who won the second leg; when it is level, the
            # second leg's shoot-out does (its score includes extra time).
            if state["top"] != state["bottom"]:
                state["winner"] = top if state["top"] > state["bottom"] else bottom
            else:
                second = games[1]
                if second.home_shootout is not None and second.away_shootout is not None and second.home_shootout != second.away_shootout:
                    state["winner"] = second.home if second.home_shootout > second.away_shootout else second.away
                elif item.decider == "higher-seed":
                    state["winner"] = top
    elif games:
        state["winner"] = games[0].winner
    return state


@dataclass(frozen=True)
class SimGame:
    """A real playoff game in the simulation's terms (team indices)."""

    home: int
    away: int
    home_score: int
    away_score: int
    winner: int | None
    home_shootout: int | None = None
    away_shootout: int | None = None


def simulate(
    model: football.GoalModel,
    teams: list[str],
    group_of: dict[str, str],
    table: dict[str, dict[str, int]],
    remaining: list[Game],
    tiers: list[dict[str, Any]],
    points: dict[str, int],
    steps: list[str],
    rounds: list[Round],
    drift: float,
    order: dict[str, list[str]] | None = None,
    overall: list[str] | None = None,
    real: dict[frozenset, list[SimGame]] | None = None,
    simulations: int = SIMULATIONS,
    seed: int = SEED,
    season_left: float = 1.0,
) -> dict[str, Any]:
    """The rest of the regular season, then the playoffs, in every simulation.

    Once the regular season is over, ``order`` (each conference's final order) and
    ``overall`` (the league table) fix the seeding and only the playoffs are simulated.
    """
    count = len(teams)
    index = {team: i for i, team in enumerate(teams)}
    rng = np.random.default_rng(seed)
    base_attack = np.array([model.attack[team] for team in teams])
    base_defence = np.array([model.defence[team] for team in teams])
    scale = drift * math.sqrt(min(max(season_left, 0.0), 1.0))
    attack = base_attack + rng.normal(0.0, scale, (simulations, count))
    defence = base_defence + rng.normal(0.0, scale, (simulations, count))

    def totals(field: str) -> np.ndarray:
        return np.array([table[team][field] for team in teams], dtype=np.float64)

    final = {field: np.broadcast_to(totals(field), (simulations, count)).copy() for field in ("points", "wins", "goalsFor", "goalsAgainst")}
    home_goals = away_goals = np.zeros((simulations, 0))
    if remaining:
        home_index = np.array([index[game.home] for game in remaining])
        away_index = np.array([index[game.away] for game in remaining])
        home_rates = np.exp(model.mu + model.home + attack[:, home_index] - defence[:, away_index])
        away_rates = np.exp(model.mu + attack[:, away_index] - defence[:, home_index])
        home_goals = rng.poisson(home_rates).astype(np.float32)
        away_goals = rng.poisson(away_rates).astype(np.float32)
        del home_rates, away_rates
        home_side = np.zeros((len(remaining), count), dtype=np.float32)
        away_side = np.zeros((len(remaining), count), dtype=np.float32)
        home_side[np.arange(len(remaining)), home_index] = 1
        away_side[np.arange(len(remaining)), away_index] = 1
        home_win = (home_goals > away_goals).astype(np.float32)
        away_win = (away_goals > home_goals).astype(np.float32)
        drawn = (home_goals == away_goals).astype(np.float32)
        final["wins"] += home_win @ home_side + away_win @ away_side
        final["points"] += (points["win"] * home_win + points["draw"] * drawn) @ home_side + (points["win"] * away_win + points["draw"] * drawn) @ away_side
        final["goalsFor"] += home_goals @ home_side + away_goals @ away_side
        final["goalsAgainst"] += away_goals @ home_side + home_goals @ away_side

    groups: dict[str, list[int]] = {}
    for team in teams:
        groups.setdefault(group_of[team], []).append(index[team])
    position = np.zeros((simulations, count), dtype=np.int64)
    seeds: dict[str, np.ndarray] = {}
    if order is not None and overall is not None and not remaining:
        for key, members in order.items():
            seeds[key] = np.broadcast_to(np.array([index[team] for team in members]), (simulations, len(members)))
            for place, team in enumerate(members):
                position[:, index[team]] = place
        overall_position = np.broadcast_to(np.array([overall.index(team) for team in teams]), (simulations, count))
    else:
        # Points, then the tiebreakers that are season totals (each well inside +-500), then at random.
        keys = final["points"].copy()
        for step in steps:
            if step not in TOTAL_STEPS:
                break
            values = final["goalsFor"] - final["goalsAgainst"] if step == "goal-difference" else final[TOTAL_STEPS[step]]
            keys = keys * 1000 + values + 500
        keys = keys + rng.random(keys.shape)
        for key, members in groups.items():
            member_index = np.array(members)
            local = team_sports.positions_from_keys(keys[:, member_index])
            position[:, member_index] = local
            seeds[key] = member_index[np.argsort(local, axis=1)]
        overall_position = team_sports.positions_from_keys(keys)

    hosts = {item.key: index[item.host] for item in rounds if item.host in index}
    bracket = Bracket(rng, model.mu, model.home, attack, defence, seeds, position, overall_position, real, hosts)
    reached, champion = bracket.run(rounds) if rounds else ({}, np.full(simulations, -1))
    places = qualifiers(rounds)
    flags = {}
    for tier in tiers:
        kind = tier.get("kind", "top")
        if kind == "playoffs":
            flags[tier["key"]] = position < places
        elif kind == "seed":
            flags[tier["key"]] = position < tier["size"]
        elif kind == "top":
            flags[tier["key"]] = overall_position < tier["size"]
        elif kind == "bottom":
            flags[tier["key"]] = overall_position >= count - tier["size"]
        elif kind == "best-record":
            flags[tier["key"]] = overall_position == 0
        elif kind == "champion":
            flags[tier["key"]] = np.zeros((simulations, count), dtype=bool)
            flags[tier["key"]][np.arange(simulations), champion] = champion >= 0
        elif kind == "round":
            flags[tier["key"]] = reached[tier["round"]]
        else:
            raise ValueError(f"tier kind {kind} is not supported by football_playoffs")

    largest = max(len(members) for members in groups.values())
    probabilities = {team: {key: round(float(flag[:, i].mean()) * 100, 2) for key, flag in flags.items()} for team, i in index.items()}
    position_odds = {
        team: [round(value * 100, 2) for value in np.bincount(position[:, i], minlength=largest)[:largest] / simulations] for team, i in index.items()
    }
    expected = {
        team: {"points": round(float(final["points"][:, i].mean()), 1), "position": round(float(position[:, i].mean()) + 1, 1)}
        for team, i in index.items()
    }
    return {
        "simulations": simulations,
        "probabilities": probabilities,
        "positions": position_odds,
        "expected": expected,
        "matchesThatMatter": football.matches_that_matter(remaining, home_goals, away_goals, flags, tiers, teams) if remaining else [],
    }


# ---------------------------------------------------------------------------
# The real bracket


def score_note(top: str, games: list[EspnMatch], item: Round) -> str | None:
    """Penalties and extra time, or the game scores of a series, from the higher seed's side."""

    def side(game: EspnMatch, team: str, home_value, away_value):
        return home_value if game.home == team else away_value

    if item.match == "series":
        parts = []
        for game in games:
            text = f"{side(game, top, game.home_score, game.away_score)}-{side(game, top, game.away_score, game.home_score)}"
            if game.home_shootout is not None:
                text += f" ({side(game, top, game.home_shootout, game.away_shootout)}-{side(game, top, game.away_shootout, game.home_shootout)} pens)"
            parts.append(text)
        return ", ".join(parts) or None
    decider = games[-1] if games else None
    if decider is None or len(games) < (2 if item.match == "two-legged" else 1):
        return None
    if decider.home_shootout is not None:
        return f"{side(decider, top, decider.home_shootout, decider.away_shootout)}-{side(decider, top, decider.away_shootout, decider.home_shootout)} on penalties"
    if decider.extra_time:
        return "After extra time"
    return None


def real_bracket(
    rounds: list[Round],
    order: dict[str, list[str]],
    overall: list[str],
    games: list[EspnMatch],
    labels: dict[str, str],
) -> dict[str, Any]:
    """The bracket from the final table and the real playoff games, round by round.

    Ties whose teams are not known yet show as to be decided. Every completed playoff game
    must belong to a tie of this bracket; ``unplaced`` lists those that do not.
    """
    position = {team: place for members in order.values() for place, team in enumerate(members)}
    overall_place = {team: place for place, team in enumerate(overall)}
    between: dict[frozenset, list[EspnMatch]] = {}
    for game in games:
        between.setdefault(frozenset((game.home, game.away)), []).append(game)
    decided: dict[tuple[str | None, str, int], tuple[str, str] | None] = {}
    placed: set[int] = set()
    stage_of: dict[int, str] = {}
    round_of: dict[int, Round] = {}
    payload_rounds = []
    champion = None
    for item in rounds:
        rank = overall_place if item.across else position
        series_list = []
        for context in [None] if item.across else list(order):

            def resolve(slot: Slot) -> str | None:
                group = slot.group or context
                if slot.seed is not None:
                    members = order[group if group is not None else next(iter(order))]
                    return members[slot.seed - 1] if slot.seed <= len(members) else None
                result = decided.get((group, slot.round, slot.tie))
                return None if result is None else result[1 if slot.loser else 0]

            if item.reseed:
                entrants = [resolve(slot) for slot in item.teams]
                if all(entrants):
                    ranked = sorted(entrants, key=lambda team: rank[team])
                    pairs = [(ranked[i], ranked[-1 - i]) for i in range(item.tie_count)]
                else:
                    pairs = [(None, None)] * item.tie_count
            else:
                pairs = [(resolve(a), resolve(b)) for a, b in item.pairs]
            for number, (a, b) in enumerate(pairs, start=1):
                top, bottom = (a, b) if a is None or b is None or rank[a] <= rank[b] else (b, a)
                played = []
                upcoming = []
                if top and bottom:
                    for number_in_tie, game in enumerate(between.get(frozenset((top, bottom)), []), start=1):
                        (played if game.completed else upcoming).append(game)
                        placed.add(id(game))
                        round_of[id(game)] = item
                        stage_of[id(game)] = (
                            f"{item.label}, game {number_in_tie}"
                            if item.match == "series"
                            else f"{item.label}, leg {number_in_tie}"
                            if item.match == "two-legged"
                            else item.label
                        )
                state = real_state(item, top, bottom, played)
                winner = state["winner"]
                decided[(context, item.key, number)] = (winner, bottom if winner == top else top) if winner else None
                entry = {
                    "stage": item.label,
                    "conference": labels.get(context) if context else None,
                    "top": top,
                    "bottom": bottom,
                    "topSeed": position[top] + 1 if top else None,
                    "bottomSeed": position[bottom] + 1 if bottom else None,
                    "topWins": state["topWins"] if item.match == "series" else int(winner == top and winner is not None),
                    "bottomWins": state["bottomWins"] if item.match == "series" else int(winner == bottom and winner is not None),
                    "bestOf": item.best_of,
                    "winner": winner,
                }
                if item.match != "series":
                    entry["aggregate"] = {"top": state["top"], "bottom": state["bottom"]} if played else None
                note = score_note(top, played, item) if top else None
                if note:
                    entry["note"] = note
                series_list.append(entry)
                if item is rounds[-1] and winner:
                    champion = winner
        payload_rounds.append({"key": item.key, "label": item.label, "series": series_list})
    unplaced = [game for game in games if game.completed and id(game) not in placed]
    return {"rounds": payload_rounds, "champion": champion, "unplaced": unplaced, "stages": stage_of, "roundOf": round_of, "decided": decided}


# ---------------------------------------------------------------------------
# Payload


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(row: dict[str, int]) -> str:
    return f"{row['wins']}-{row['losses']}-{row['draws']}"


def build_payload(config: dict[str, Any], now: datetime, cache_dir: Path) -> dict[str, Any]:
    season = team_sports.resolve_season(config, now)
    aliases = config.get("aliases", {})
    rounds = parse_rounds(config, season.year)
    playoff_teams = qualifiers(rounds) * len(group_list(config))
    warnings: list[str] = []
    notes: list[str] = []
    # Playoff results come from ESPN, which has shoot-out scores; a feed's own playoff games are left out.
    games, _ = split_postseason(rename(team_sports.fetch_games(season.feed, cache_dir), aliases), playoff_teams)
    previous_season = team_sports.resolve_season(config, now, offset=-1)
    try:
        previous_games, _ = split_postseason(
            rename(team_sports.fetch_games(previous_season.feed, cache_dir, max_age_hours=24 * 30), aliases), playoff_teams
        )
    except team_sports.FeedError as exc:
        previous_games = []
        warnings.append(f"Previous season unavailable ({exc}); ratings use this season only.")

    espn_code = config.get("sources", {}).get("espn")
    espn: list[EspnMatch] | None = None
    stale = None
    corrections: list[tuple[Game, Game]] = []
    if espn_code:
        try:
            espn, stale = fetch_espn_matches(espn_code, season.year, cache_dir, aliases)
        except team_sports.FeedError as exc:
            print(f"{season.payload_id}: ESPN scoreboard unavailable ({exc})")
    if espn:
        games, corrections = corrected_games(games, espn)

    teams = sorted({game.home for game in games} | {game.away for game in games})
    group_of = {team: team_group(config, team) for team in teams}
    group_labels = {group["key"]: group.get("shortLabel", group["label"]) for group in group_list(config)}
    members = {group["key"]: [team for team in teams if group_of[team] == group["key"]] for group in group_list(config)}
    points = {"win": config.get("points", {}).get("win", 3), "draw": config.get("points", {}).get("draw", 1)}
    steps = config.get("tiebreakers", ["goal-difference", "goals-for"])
    table = table_rows(games, teams, points)

    published = None
    adjustments: dict[str, int] = {}
    if espn_code:
        try:
            published, adjustments = official_order(table, fetch_espn_table(espn_code, season.year, cache_dir, aliases), members)
        except (team_sports.FeedError, KeyError, IndexError, ValueError, TypeError) as exc:
            print(f"{season.payload_id}: official order not checked ({exc})")
    for team, change in adjustments.items():
        table[team]["points"] += change
        table[team]["adjustment"] = change
    order = {key: rank_teams(group, table, games, steps, group_of) for key, group in members.items()}
    if published:
        order = published
    conference_place = {team: place for group in order.values() for place, team in enumerate(group)}
    overall = rank_teams(teams, table, games, steps, group_of, fallback=conference_place)
    meta = team_sports.team_meta(config, teams)
    if corrections:
        notes.append(
            f"{len(corrections)} FixtureDownload score{'s differ' if len(corrections) > 1 else ' differs'} from ESPN's, which agree "
            "with the official standings, so ESPN's are used: "
            + "; ".join(
                f"{meta[after.home]['fullName']} {after.home_score}-{after.away_score} {meta[after.away]['fullName']} on "
                f"{local_day(after.date, config)} (not {before.home_score}-{before.away_score})"
                for before, after in corrections
            )
            + "."
        )

    model_teams = sorted(set(teams) | {game.home for game in previous_games} | {game.away for game in previous_games})
    previous_teams = {game.home for game in previous_games} | {game.away for game in previous_games}
    promoted = set(teams) - previous_teams if previous_teams else set()
    latest = max((game.date for game in previous_games + games if game.played), default=now)
    model = football.fit_goal_model(previous_games + games, model_teams, promoted, min(latest, now))
    remaining = [game for game in games if not game.played]
    pending = [game for game in remaining if game.date < now - timedelta(hours=6)]
    if pending:
        warnings.append(
            f"{len(pending)} past fixture{'s have' if len(pending) > 1 else ' has'} no result yet "
            f"(postponed, or not yet updated at {team_sports.FEED_SOURCE}); they are simulated as still to play."
        )
    drift = (config.get("model") or {}).get("drift", football.STRENGTH_DRIFT)
    tiers = config["tiers"]
    index = {team: i for i, team in enumerate(teams)}

    # After the regular season, the bracket comes from the final table and ESPN's playoff games.
    bracket = None
    playoff_games: list[EspnMatch] = []
    real: dict[frozenset, list[SimGame]] = {}
    if not remaining and rounds:
        if espn is None:
            warnings.append("Playoff results unavailable (ESPN's scoreboard could not be read); title odds are left out.")
        else:
            if stale:
                # Only the playoffs depend on a fresh scoreboard; in season it just checks scores.
                warnings.append(stale)
            # Postseason games between league teams (the All-Star game is neither), after the regular season.
            last_regular = max(game.date for game in games)
            playoff_games = [game for game in espn if not game.regular and game.home in index and game.away in index and game.date > last_regular]
            bracket = real_bracket(rounds, order, overall, playoff_games, group_labels)
            if bracket["unplaced"]:
                odd = bracket["unplaced"][0]
                warnings.append(
                    f"ESPN's playoff games do not fit the bracket from the final table ({odd.home} v {odd.away} on "
                    f"{odd.date.strftime('%-d %b')}), so title odds are left out."
                )
                bracket = None
            else:
                for game in playoff_games:
                    if game.completed:
                        real.setdefault(frozenset((index[game.home], index[game.away])), []).append(
                            SimGame(
                                index[game.home],
                                index[game.away],
                                game.home_score,
                                game.away_score,
                                index.get(game.winner) if game.winner else None,
                                game.home_shootout,
                                game.away_shootout,
                            )
                        )
    simulation = simulate(
        model,
        teams,
        group_of,
        table,
        remaining,
        tiers,
        points,
        steps,
        rounds,
        drift,
        order=order,
        overall=overall,
        real=real,
        season_left=len(remaining) / max(len(games), 1),
    )

    probabilities = simulation["probabilities"]
    if remaining:
        status = "in_progress"
    elif bracket:
        status = "complete" if bracket["champion"] else "postseason"
        tiers = [
            dict(tier, settled=True) if all(values[tier["key"]] in (0.0, 100.0) for values in probabilities.values()) else tier for tier in tiers
        ]
    else:
        status = "complete" if not rounds else "postseason"
        tiers = [dict(tier, settled=True) for tier in tiers if tier.get("kind") not in ("champion", "round")]
        keys = {tier["key"] for tier in tiers}
        probabilities = {team: {key: value for key, value in values.items() if key in keys} for team, values in probabilities.items()}

    standings_rows = []
    for rank, team in enumerate(overall, start=1):
        row = table[team]
        standings_rows.append(
            {
                "teamKey": team,
                "shortName": meta[team]["shortName"],
                "fullName": meta[team]["fullName"],
                "rank": rank,
                **{key: value for key, value in row.items() if not key.startswith(("home", "away"))},
                "record": record(row),
                "conference": group_labels[group_of[team]],
                "seed": conference_place[team] + 1,
                "form": team_sports.form_strings(games, team),
                "remaining": sum(1 for game in remaining if team in (game.home, game.away)),
            }
        )

    fixtures = [
        {
            "id": game.id,
            "round": game.round,
            "date": iso(game.date),
            "home": game.home,
            "away": game.away,
            "venue": game.venue,
            "probabilities": dict(zip(("home", "draw", "away"), (round(value, 3) for value in model.outcome(game.home, game.away)))),
        }
        for game in sorted(remaining, key=lambda item: item.date)
    ]
    results = [
        {
            "id": game.id,
            "round": game.round,
            "date": iso(game.date),
            "home": game.home,
            "away": game.away,
            "homeScore": game.home_score,
            "awayScore": game.away_score,
        }
        for game in [game for game in games if game.played][::-1]
    ]
    if bracket:
        decided_pairs = {frozenset(result) for result in bracket["decided"].values() if result}
        # Games of known ties only; "if necessary" games of a decided series will not be played.
        upcoming = [
            game
            for game in playoff_games
            if not game.completed and id(game) in bracket["stages"] and frozenset((game.home, game.away)) not in decided_pairs
        ]

        def playoff_outcome(game: EspnMatch) -> tuple[float, float, float]:
            """Home, draw and away chances; at a neutral ground only its own club has home advantage."""
            item = bracket["roundOf"].get(id(game))
            if item is None or not item.neutral or item.host == game.home:
                return model.outcome(game.home, game.away)
            if item.host == game.away:
                return model.outcome(game.away, game.home)[::-1]
            return dataclasses.replace(model, home=0.0).outcome(game.home, game.away)

        fixtures = [
            {
                "id": f"playoff-{i}",
                "round": None,
                "date": iso(game.date),
                "home": game.home,
                "away": game.away,
                "venue": None,
                "stage": bracket["stages"].get(id(game)),
                "probabilities": dict(zip(("home", "draw", "away"), (round(value, 3) for value in playoff_outcome(game)))),
            }
            for i, game in enumerate(upcoming)
        ]
        played_playoffs = [game for game in playoff_games if game.completed][::-1]
        results = [
            {
                "id": f"playoff-result-{i}",
                "round": None,
                "date": iso(game.date),
                "home": game.home,
                "away": game.away,
                "homeScore": game.home_score,
                "awayScore": game.away_score,
                "note": (bracket["stages"].get(id(game)) or "Playoffs")
                + (f", {game.home_shootout}-{game.away_shootout} pens" if game.home_shootout is not None else ", aet" if game.extra_time else ""),
            }
            for i, game in enumerate(played_playoffs)
        ] + results

    steps_text = ", ".join(TIEBREAK_TEXT[step] for step in steps)
    simulated_steps = [TIEBREAK_TEXT[step] for step in steps if step in TOTAL_STEPS]
    model_notes = [
        f"Each remaining match is simulated {SIMULATIONS:,} times from a Poisson goals model: team attack and defence "
        f"ratings plus home advantage, fitted on this and last season with a {football.HALF_LIFE_DAYS}-day half-life.",
        "Every simulated season also lets team strength drift (more when more of the season is left), and the playoffs "
        "are then played out from each simulated table with the same strengths; penalties are a coin flip.",
        f"Teams level on points are ranked by {steps_text}"
        + (", with the official order used where it is published" if espn_code else "")
        + f". Simulated seasons separate them by {', '.join(simulated_steps) or 'nothing'}, then at random.",
        *config.get("notes", []),
        *notes,
    ]
    if adjustments:
        model_notes.append(
            "Points deductions in the official table: "
            + ", ".join(f"{meta[team]['fullName']} {change:+d}" for team, change in sorted(adjustments.items()))
            + "."
        )
    if bracket:
        model_notes.append(f"Playoffs: ties still to play are simulated {SIMULATIONS:,} times, starting from the real results.")
    credits = [{"name": "ESPN", "url": ESPN_SITE_URL, "note": "Playoff results and score checks: ESPN"}] if espn else []
    cutoffs = (config.get("playoffs") or {}).get("cutoffs", [{"after": qualifiers(rounds), "label": "Playoff line"}])
    single_table = len(group_list(config)) == 1
    groups = [] if single_table else [
        {"key": key, "label": group_labels[key], "teams": order[key], "cutoffs": cutoffs} for key in members
    ]

    return {
        "metadata": {
            "season": season.label,
            "generated_at": iso(now),
            "source": team_sports.FEED_SOURCE,
            "source_url": team_sports.FEED_SOURCE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": status,
            "warnings": warnings,
            **({"credits": credits} if credits else {}),
        },
        "league": {
            "id": season.payload_id,
            "configId": config["id"],
            "sport": "football",
            "name": config["name"],
            "shortName": config["shortName"],
            **({"headline": config["headline"]} if config.get("headline") else {}),
            "season": season.label,
            "seasonLabel": season.label,
            "priority": config.get("priority", 100),
            "tiers": tiers,
            "columns": config.get("columns")
            or [
                {"key": "played", "label": "P"},
                {"key": "wins", "label": "W"},
                {"key": "draws", "label": "D"},
                {"key": "losses", "label": "L"},
                {"key": "goalDifference", "label": "GD", "signed": True},
                {"key": "points", "label": "Pts", "strong": True},
            ],
            "outcomes": ["home", "draw", "away"],
            "teams": [meta[team] for team in teams],
            "groups": groups,
            **({"cutoffs": cutoffs} if single_table else {}),
            "rankLabel": (config.get("playoffs") or {}).get("rankLabel", "League"),
            "positionLabel": (config.get("playoffs") or {}).get("positionLabel", "Conference position" if not single_table else "Position"),
            "positionZones": (config.get("playoffs") or {}).get("zones", [{"to": qualifiers(rounds), "kind": "top"}]),
        },
        "standings": standings_rows,
        "fixtures": fixtures,
        "results": results,
        "analysis": {
            "method": "Monte Carlo",
            "simulations": simulation["simulations"],
            "model": "Poisson goals model",
            "modelNotes": model_notes,
            "probabilities": probabilities,
            "positions": simulation["positions"],
            "expected": simulation["expected"],
            "ratings": {team: {"attack": round(model.attack[team], 3), "defence": round(model.defence[team], 3)} for team in teams},
        },
        "matchesThatMatter": simulation["matchesThatMatter"],
        **({"bracket": {"rounds": bracket["rounds"], "champion": bracket["champion"]}} if bracket else {}),
        **({"playoffs": {"champion": bracket["champion"]}} if bracket and bracket["champion"] else {}),
    }
