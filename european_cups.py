"""Champions League, Europa League and Conference League: league phase and knockouts.

Since 2024-25 each competition starts with a 36-team league phase (eight games
each, six in the Conference League). The top eight go straight to the round of
16; places 9-24 meet in a two-legged knockout play-off whose pairings and later
bracket are fixed by league-phase position.

Team strength comes from a Poisson goals model (attack, defence, home advantage)
fitted on every UEFA club match, qualifiers included, from this season and the
two before. The qualifiers and the three competitions link clubs from every
league. The rest of the league phase is then simulated, the knockout draws are
made by UEFA's seeding rules, and every tie is played out over two legs with
extra time and penalties, which gives the odds of each round and the title.
"""

from __future__ import annotations

import dataclasses
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

import football
import team_sports
import uefa
from team_sports import Game


SIMULATIONS = 20_000
SEED = 20260908
# Chosen by week-ahead backtests of 2024-25 and 2025-26 main-draw matches in all
# three competitions (1,062 games): ranked probability score 0.2033 against 0.2323
# for home/draw/away base rates. A club's strength is its country's level plus its
# own difference from it, shrunk hard (TEAM_RIDGE): a club with three European games
# and no domestic results then sits near its compatriots instead of being rated on
# three scores (0.2065 with one flat ridge, 0.2082 also without domestic results).
HISTORY_SEASONS = 4
HALF_LIFE_DAYS = 730
TEAM_RIDGE = 20.0
COUNTRY_RIDGE = 0.5
# Domestic league results (FixtureDownload) sharpen ratings within a country; the
# European matches tie the countries together. A quarter weight scored best.
DOMESTIC_WEIGHT = 0.25
DOMESTIC_FEEDS = {
    "ENG": ("epl-{year}", "championship-{year}"),
    "ESP": ("la-liga-{year}",),
    "GER": ("bundesliga-{year}",),
    "ITA": ("serie-a-{year}",),
    "FRA": ("ligue-1-{year}",),
    "NED": ("eredivisie-{year}",),
    "POR": ("primeira-liga-{year}",),
    "SCO": ("scottish-premiership-{year}",),
    "TUR": ("super-lig-{year}",),
}
# UEFA short names whose words do not appear in the FixtureDownload name.
DOMESTIC_ALIASES = {
    "Atleti": "atletico madrid",
    "Paris": "paris saint germain",
    "Lyon": "lyonnais",
    "Tottenham": "spurs",
    "B. Dortmund": "borussia dortmund",
    "AZ Alkmaar": "az",
    "Leverkusen": "bayer leverkusen",
    "Brest": "brestois",
    "Rennes": "rennais",
    "Hearts": "heart midlothian",
}
# Primary club colours by UEFA team id (the table's team chips); other clubs get a generated colour.
CLUB_COLOURS = {
    # England
    "52280": "#EF0107", "52683": "#670E36", "2601124": "#DA291C", "2601105": "#0057B8", "52914": "#034694",
    "52916": "#1B458F", "7889": "#C8102E", "52919": "#6CABDD", "52682": "#DA291C", "59324": "#241F20",
    "52681": "#DD0000", "53360": "#EB172B", "1652": "#132257",
    # Spain
    "50125": "#EE2523", "50124": "#CB3524", "50080": "#A50044", "53043": "#8AC3EE", "87960": "#005999",
    "74070": "#E53027", "52265": "#00954C", "50051": "#FEBE10", "50123": "#0067B1", "70691": "#FFE667",
    # Germany
    "52758": "#FDE100", "50037": "#DC052D", "50072": "#E1000F", "59880": "#E30613", "2600431": "#1961B5",
    "2603790": "#DD0741", "50109": "#E32221", "70853": "#C3141E", "50107": "#E32219",
    # Italy
    "52816": "#1E71B8", "52969": "#1A2F48", "79946": "#1C4E9D", "52817": "#482E92", "50138": "#0068A8",
    "50139": "#000000", "50058": "#FB090B", "50136": "#12A0D7", "50137": "#8E1F2F",
    # France
    "52277": "#FFD100", "75797": "#E01E13", "5312": "#14387F", "52748": "#2FAEE0", "50023": "#E51B22",
    "52355": "#E20E1C", "52747": "#004170", "55031": "#E13327", "59857": "#009FE3",
    # Netherlands and Portugal
    "52327": "#DB0021", "50143": "#D2122E", "52749": "#E40421", "50062": "#ED1C24", "52818": "#E30613",
    "52323": "#D3172E", "50147": "#E83030", "52336": "#E20E0E", "50064": "#00428C", "50149": "#008057",
    # Scotland and Turkey
    "50050": "#018749", "50121": "#1B458F", "50122": "#E2231A", "50120": "#9E1B32", "50067": "#A90432",
    "52692": "#002D72", "50157": "#000000", "52731": "#8B1D41",
    # Elsewhere
    "50043": "#005BAC", "50074": "#4C2683", "64125": "#FCD116", "61582": "#0055A5", "4608": "#00539F",
    "50030": "#D11241", "50042": "#009640", "52707": "#F26522", "52723": "#002F87", "2610": "#E2001A",
    "50130": "#000000", "50084": "#00843D", "50129": "#FDB913", "50069": "#DA291C", "50164": "#0053A0",
    "52498": "#E30613", "50033": "#9E1B32", "64388": "#ED1C24", "52709": "#0C2340", "59333": "#FFE500",
    "59856": "#E2001A", "50031": "#FFD500", "52298": "#00843D", "60609": "#000000", "50146": "#00843D",
    "50152": "#6CACE4", "2603104": "#00843D",
}
_NAME_NOISE = {
    "fc", "sc", "cf", "ac", "as", "rc", "rcd", "ud", "sl", "cd", "afc", "sv", "vfb", "vfl", "tsg", "fsv", "bsc", "ogc",
    "losc", "sco", "de", "club", "cp", "ca", "sad", "calcio", "ssc", "us", "bv", "stade", "olympique", "r", "cfc",
}
MAX_GOALS = 10
MATCHES_THAT_MATTER = 10
# Extra time is a third of a match.
EXTRA_TIME_SHARE = 1 / 3
# Main-draw knockout matches after the league phase: 8 + 8 + 4 + 2 two-legged ties and a final.
KNOCKOUT_MATCHES = 45
# Season-long strength drift, as in football.py. Season odds at five checkpoints of the six
# 2024-25 and 2025-26 competitions scored within 0.2% (log loss) at 0 and 0.1, and worse at
# 0.2; 0.1 is kept as a guard against early-season overconfidence.
STRENGTH_DRIFT = 0.1

ROUND_LABELS = {
    "FINAL_TOURNAMENT_PLAY_OFF": "Knockout play-offs",
    "ROUND_OF_16": "Round of 16",
    "QUARTER_FINALS": "Quarter-finals",
    "SEMIFINAL": "Semi-finals",
    "FINAL": "Final",
}
# Teams still in at the start of each round, for "reach this round" tiers.
ROUND_ORDER = ("LEAGUE", *uefa.KNOCKOUT_ROUNDS, "CHAMPION")


@dataclass(frozen=True)
class CupModel:
    mu: float
    home: float
    # Country level plus the club's own difference, for every club in the data.
    attack: dict[str, float]
    defence: dict[str, float]
    # Country levels, for clubs with no matches in the data yet.
    country_attack: dict[str, float] = dataclasses.field(default_factory=dict)
    country_defence: dict[str, float] = dataclasses.field(default_factory=dict)
    country_of: dict[str, str] = dataclasses.field(default_factory=dict)

    def strength(self, team: str) -> tuple[float, float]:
        if team in self.attack:
            return self.attack[team], self.defence[team]
        country = self.country_of.get(team)
        return self.country_attack.get(country, 0.0), self.country_defence.get(country, 0.0)

    def rates(self, home: str, away: str, neutral: bool = False) -> tuple[float, float]:
        home_attack, home_defence = self.strength(home)
        away_attack, away_defence = self.strength(away)
        home_rate = math.exp(self.mu + (0.0 if neutral else self.home) + home_attack - away_defence)
        away_rate = math.exp(self.mu + away_attack - home_defence)
        return home_rate, away_rate

    def outcome(self, home: str, away: str, neutral: bool = False) -> tuple[float, float, float]:
        """Probabilities of a home win, a draw and an away win over 90 minutes."""
        home_rate, away_rate = self.rates(home, away, neutral)
        goals = np.arange(MAX_GOALS + 1)
        factorials = np.array([math.factorial(k) for k in goals], dtype=float)
        grid = np.outer(np.exp(-home_rate) * home_rate**goals / factorials, np.exp(-away_rate) * away_rate**goals / factorials)
        total = grid.sum()
        return float(np.tril(grid, -1).sum() / total), float(np.trace(grid) / total), float(np.triu(grid, 1).sum() / total)


@dataclass(frozen=True)
class Result:
    """One match for the goals model: UEFA or domestic, 90-minute score."""

    home: str
    away: str
    home_score: int
    away_score: int
    date: datetime
    neutral: bool = False
    weight: float = 1.0


def fit_model(results: list[Result], now: datetime, country_of: dict[str, str] | None = None) -> CupModel:
    """Penalised, time-weighted Poisson regression, fitted with Newton steps.

    log(goals) = mu + home advantage + attack(country) + attack(club) - defence(country) - defence(club),
    with ridge penalties pulling clubs toward their country (TEAM_RIDGE) and countries toward
    the average (COUNTRY_RIDGE). Every observation touches six parameters, so the gradient and
    Hessian are accumulated from those cells instead of a dense design matrix.
    """
    country_of = country_of or {}
    used = [result for result in results if result.date <= now]
    teams = sorted({result.home for result in used} | {result.away for result in used})
    countries = sorted({country_of.get(team, "") for team in teams})
    index = {team: i for i, team in enumerate(teams)}
    country_index = {country: i for i, country in enumerate(countries)}
    count, nations = len(teams), len(countries)
    # Layout: mu, home, country attack, country defence, club attack, club defence.
    country_attack, country_defence = 2, 2 + nations
    club_attack, club_defence = 2 + 2 * nations, 2 + 2 * nations + count
    size = 2 + 2 * nations + 2 * count
    theta = np.zeros(size)
    theta[0] = math.log(1.3)
    if used:
        home = np.array([index[result.home] for result in used])
        away = np.array([index[result.away] for result in used])
        home_country = np.array([country_index[country_of.get(result.home, "")] for result in used])
        away_country = np.array([country_index[country_of.get(result.away, "")] for result in used])
        edge = np.array([0.0 if result.neutral else 1.0 for result in used])
        ages = np.array([max(0.0, (now - result.date).total_seconds() / 86400) for result in used])
        weight = np.array([result.weight for result in used]) * 0.5 ** (ages / HALF_LIFE_DAYS)
        ones, zeros = np.ones(len(used)), np.zeros(len(used))
        columns = np.concatenate(
            [
                np.stack([zeros, ones, country_attack + home_country, country_defence + away_country, club_attack + home, club_defence + away], axis=1),
                np.stack([zeros, ones, country_attack + away_country, country_defence + home_country, club_attack + away, club_defence + home], axis=1),
            ]
        ).astype(int)
        values = np.concatenate(
            [np.stack([ones, edge, ones, -ones, ones, -ones], axis=1), np.stack([ones, zeros, ones, -ones, ones, -ones], axis=1)]
        )
        observed = np.array([result.home_score for result in used] + [result.away_score for result in used], dtype=float)
        weights = np.concatenate([weight, weight])
        penalty = np.zeros(size)
        penalty[country_attack:club_attack] = COUNTRY_RIDGE
        penalty[club_attack:] = TEAM_RIDGE
        pairs = (columns[:, :, None] * size + columns[:, None, :]).ravel()
        for _ in range(60):
            rate = np.exp((theta[columns] * values).sum(axis=1))
            gradient = np.bincount(columns.ravel(), (values * (weights * (observed - rate))[:, None]).ravel(), minlength=size) - penalty * theta
            curvature = (values[:, :, None] * values[:, None, :] * (weights * rate)[:, None, None]).ravel()
            hessian = np.bincount(pairs, curvature, minlength=size * size).reshape(size, size) + np.diag(penalty) + np.eye(size) * 1e-9
            step = np.linalg.solve(hessian, gradient)
            theta += step
            if np.abs(step).max() < 1e-7:
                break

    def level(team: str, offset: int) -> float:
        return float(theta[offset + country_index[country_of.get(team, "")]])

    return CupModel(
        mu=float(theta[0]),
        home=float(theta[1]),
        attack={team: level(team, country_attack) + float(theta[club_attack + i]) for team, i in index.items()},
        defence={team: level(team, country_defence) + float(theta[club_defence + i]) for team, i in index.items()},
        country_attack={country: float(theta[country_attack + i]) for country, i in country_index.items() if country},
        country_defence={country: float(theta[country_defence + i]) for country, i in country_index.items() if country},
        country_of=dict(country_of),
    )


def name_words(name: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return {word for word in re.sub(r"[^a-z ]", " ", plain).split() if word not in _NAME_NOISE}


def domestic_names(teams: dict[str, uefa.Team], games: dict[str, list[Game]]) -> dict[tuple[str, str], str]:
    """(country, FixtureDownload name) -> UEFA team id, for clubs whose name words all appear.

    A feed name matched by two UEFA clubs, or a UEFA club matching names of two different
    clubs, is left unmatched: a wrong link would mix two teams' results.
    """
    links: dict[tuple[str, str], set[str]] = defaultdict(set)
    for country, items in games.items():
        names = {game.home for game in items} | {game.away for game in items}
        words = {name: name_words(name) for name in names}
        for team in teams.values():
            if team.country != country:
                continue
            wanted = name_words(DOMESTIC_ALIASES.get(team.name, team.name))
            if not wanted:
                continue
            found = [name for name, have in words.items() if wanted <= have]
            exact = [name for name in found if words[name] == wanted]
            for name in exact or found:
                links[(country, name)].add(team.id)
    return {key: next(iter(ids)) for key, ids in links.items() if len(ids) == 1}


def domestic_results(year: int, teams: dict[str, uefa.Team], cache_dir: Path) -> list[Result]:
    """Domestic league games of the seasons overlapping the model window, with UEFA ids where known."""
    games: dict[str, list[Game]] = defaultdict(list)
    for country, feeds in DOMESTIC_FEEDS.items():
        for template in feeds:
            for start_year in range(year - HISTORY_SEASONS, year):
                try:
                    games[country] += team_sports.fetch_games(template.format(year=start_year), cache_dir, max_age_hours=3 if start_year == year - 1 else 24 * 30)
                except team_sports.FeedError:
                    continue
    names = domestic_names(teams, games)
    return [
        Result(
            home=names.get((country, game.home), f"{country}:{game.home}"),
            away=names.get((country, game.away), f"{country}:{game.away}"),
            home_score=game.home_score,
            away_score=game.away_score,
            date=game.date,
            weight=DOMESTIC_WEIGHT,
        )
        for country, items in games.items()
        for game in items
        if game.played
    ]


def uefa_results(matches: list[uefa.Match]) -> list[Result]:
    return [
        Result(home=match.home, away=match.away, home_score=match.home_score, away_score=match.away_score, date=match.date, neutral=match.neutral)
        for match in matches
        if match.played
    ]


# --- League phase table -------------------------------------------------------------------


def league_table(matches: list[uefa.Match], teams: list[str]) -> dict[str, dict[str, int]]:
    rows = {
        team: {
            "played": 0, "wins": 0, "draws": 0, "losses": 0, "goalsFor": 0, "goalsAgainst": 0, "points": 0,
            "awayGoalsFor": 0, "awayWins": 0,
        }
        for team in teams
    }
    for match in matches:
        if not match.played:
            continue
        for team, scored, conceded, away in (
            (match.home, match.home_score, match.away_score, False),
            (match.away, match.away_score, match.home_score, True),
        ):
            row = rows[team]
            row["played"] += 1
            row["goalsFor"] += scored
            row["goalsAgainst"] += conceded
            row["awayGoalsFor"] += scored if away else 0
            if scored > conceded:
                row["wins"] += 1
                row["awayWins"] += int(away)
                row["points"] += 3
            elif scored == conceded:
                row["draws"] += 1
                row["points"] += 1
            else:
                row["losses"] += 1
    for row in rows.values():
        row["goalDifference"] = row["goalsFor"] - row["goalsAgainst"]
    return rows


def ranked(rows: dict[str, dict[str, int]], matches: list[uefa.Match]) -> list[str]:
    """UEFA's league-phase order: points, goal difference, goals scored, away goals scored,
    wins, away wins, then the league-phase opponents' combined points, goal difference and
    goals scored. (Disciplinary points and the club coefficient come after; not modelled.)"""
    opponents: dict[str, list[str]] = defaultdict(list)
    for match in matches:
        if match.played:
            opponents[match.home].append(match.away)
            opponents[match.away].append(match.home)

    def opponents_total(team: str, field: str) -> int:
        return sum(rows[other][field] for other in opponents[team])

    return sorted(
        rows,
        key=lambda team: (
            -rows[team]["points"],
            -rows[team]["goalDifference"],
            -rows[team]["goalsFor"],
            -rows[team]["awayGoalsFor"],
            -rows[team]["wins"],
            -rows[team]["awayWins"],
            -opponents_total(team, "points"),
            -opponents_total(team, "goalDifference"),
            -opponents_total(team, "goalsFor"),
            team,
        ),
    )


def official_order(rows: dict[str, dict[str, int]], official: list[dict[str, Any]]) -> list[str] | None:
    """UEFA's own ranking, when it agrees with the computed table on every team's record."""
    if len(official) != len(rows):
        return None
    fields = ("played", "wins", "draws", "losses", "goalsFor", "goalsAgainst", "points")
    for item in official:
        row = rows.get(item["team"])
        if row is None or any(row[field] != item[field] for field in fields):
            return None
    return [item["team"] for item in sorted(official, key=lambda item: item["rank"])]


# --- Knockout ties ------------------------------------------------------------------------


@dataclass
class Tie:
    """A knockout tie from the data: two legs (one in the final), possibly unfinished."""

    round: str
    first_home: str
    # The other team: home in the second leg (or the second-named team in the final).
    second_home: str
    legs: list[uefa.Match]
    winner: str | None

    @property
    def teams(self) -> frozenset[str]:
        return frozenset((self.first_home, self.second_home))


def knockout_ties(matches: list[uefa.Match]) -> dict[str, list[Tie]]:
    """Real knockout ties by round, once the draw has named both teams."""
    grouped: dict[tuple[str, frozenset[str]], list[uefa.Match]] = defaultdict(list)
    for match in matches:
        if match.round in uefa.KNOCKOUT_ROUNDS and not match.qualifying:
            grouped[(match.round, frozenset((match.home, match.away)))].append(match)
    ties: dict[str, list[Tie]] = defaultdict(list)
    for (round_type, _), legs in grouped.items():
        legs.sort(key=lambda match: (match.leg or 1, match.date))
        first = legs[0]
        deciding = legs[-1]
        two_legged = round_type != "FINAL"
        winner = deciding.winner if deciding.played and (not two_legged or deciding.leg == 2) else None
        ties[round_type].append(
            Tie(
                round=round_type,
                first_home=first.home,
                second_home=first.away,
                legs=legs,
                winner=winner,
            )
        )
    for items in ties.values():
        items.sort(key=lambda tie: min(leg.date for leg in tie.legs))
    return ties


def play_ties(
    rng: np.random.Generator,
    model: CupModel,
    attack: np.ndarray,
    defence: np.ndarray,
    sims: np.ndarray,
    first_home: np.ndarray,
    second_home: np.ndarray,
    single: bool = False,
    first_leg: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    """Winners of a batch of ties (one per row), each in simulation ``sims[row]``.

    Two legs, ``first_home`` at home first; level on aggregate goes to extra time at the
    second-leg ground, then penalties (a coin flip). ``single`` plays one neutral match
    (the final). ``first_leg`` gives first-leg goals already scored (NaN where unplayed).
    """
    if not len(sims):
        return first_home.copy()
    home_edge = 0.0 if single else model.home

    def goals(home: np.ndarray, away: np.ndarray, edge: float, share: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
        home_rate = np.exp(model.mu + edge + attack[sims, home] - defence[sims, away]) * share
        away_rate = np.exp(model.mu + attack[sims, away] - defence[sims, home]) * share
        return rng.poisson(home_rate), rng.poisson(away_rate)

    if single:
        a_goals, b_goals = goals(first_home, second_home, 0.0)
    else:
        a_first, b_first = goals(first_home, second_home, home_edge)
        if first_leg is not None:
            known = ~np.isnan(first_leg[0])
            a_first = np.where(known, np.nan_to_num(first_leg[0]), a_first)
            b_first = np.where(known, np.nan_to_num(first_leg[1]), b_first)
        b_second, a_second = goals(second_home, first_home, home_edge)
        a_goals, b_goals = a_first + a_second, b_first + b_second
    level = a_goals == b_goals
    extra_b, extra_a = goals(second_home, first_home, 0.0 if single else home_edge, EXTRA_TIME_SHARE)
    a_goals = a_goals + np.where(level, extra_a, 0)
    b_goals = b_goals + np.where(level, extra_b, 0)
    shootout = a_goals == b_goals
    a_wins = (a_goals > b_goals) | (shootout & (rng.random(len(sims)) < 0.5))
    return np.where(a_wins, first_home, second_home)


# --- Simulation ---------------------------------------------------------------------------
#
# UEFA's bracket since 2024-25, with 0-based league positions:
# - knockout play-off group k (0-3): positions 8+2k and 9+2k (seeded, second leg at home)
#   against 22-2k and 23-2k, paired by draw;
# - round-of-16 pair p (0-3): positions 2p and 2p+1 against the two play-off winners of
#   group 3-p, paired by draw;
# - the draw puts the two members of each top-eight pair in opposite halves; in each half
#   the quarter-finals are (pair 0 v pair 3) and (pair 1 v pair 2), and their winners meet
#   in the semi-final. The better-placed team hosts the second leg up to the semi-finals.

EXPECTED_TIES = {"FINAL_TOURNAMENT_PLAY_OFF": 8, "ROUND_OF_16": 8, "QUARTER_FINALS": 4, "SEMIFINAL": 2, "FINAL": 1}


def half_layouts(quarter_pairs: list[frozenset[int]], semi_groups: list[frozenset[int]]) -> list[tuple[int, ...]]:
    """Draws (one flip bit per top-eight pair) consistent with quarter-finals and semi-finals
    already known, in terms of the round-of-16 ties' top seeds (0-7). Seed s goes to half
    (s % 2) ^ bit[s // 2]."""
    layouts = []
    for bits in product((0, 1), repeat=4):
        quarters, semis = set(), set()
        for side in (0, 1):
            seed = {pair: 2 * pair + (side ^ bits[pair]) for pair in range(4)}
            first, second = frozenset((seed[0], seed[3])), frozenset((seed[1], seed[2]))
            quarters |= {first, second}
            semis.add(first | second)
        if all(pair in quarters for pair in quarter_pairs) and all(group in semis for group in semi_groups):
            layouts.append(bits)
    return layouts or list(product((0, 1), repeat=4))


class Knockouts:
    """Plays every knockout round of every simulation, using real ties where the draw is known."""

    def __init__(self, rng, model, attack, defence, positions, index, ties):
        self.rng, self.model, self.attack, self.defence = rng, model, attack, defence
        self.positions = positions  # positions[sim, team]
        self.order = np.argsort(positions, axis=1)  # team at each position
        self.index = index
        self.sims = np.arange(positions.shape[0])
        self.real = {
            name: items
            for name, items in ties.items()
            if len(items) == EXPECTED_TIES[name] and all(tie.teams <= set(index) for tie in items)
        }

    def play(self, top: np.ndarray, bottom: np.ndarray, single: bool = False) -> np.ndarray:
        """Winners of ties (simulations x ties); ``top`` hosts the second leg."""
        rows = np.repeat(self.sims, top.shape[1])
        return play_ties(self.rng, self.model, self.attack, self.defence, rows, bottom.ravel(), top.ravel(), single=single).reshape(top.shape)

    def better_first(self, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Each pair (simulations x ties) ordered better league position first."""
        rows = self.sims[:, None]
        a_better = self.positions[rows, a] < self.positions[rows, b]
        return np.where(a_better, a, b), np.where(a_better, b, a)

    def play_real(self, round_type: str) -> np.ndarray:
        """Winners (simulations x ties) of the real ties of a round, in data order."""
        items = self.real[round_type]
        count = len(self.sims)
        winners = np.empty((count, len(items)), dtype=int)
        for column, tie in enumerate(items):
            if tie.winner is not None and tie.winner in self.index:
                winners[:, column] = self.index[tie.winner]
                continue
            first_leg = None
            if round_type != "FINAL" and tie.legs and tie.legs[0].leg == 1 and tie.legs[0].played:
                leg = tie.legs[0]
                first_leg = (np.full(count, float(leg.home_score)), np.full(count, float(leg.away_score)))
            winners[:, column] = play_ties(
                self.rng, self.model, self.attack, self.defence, self.sims,
                np.full(count, self.index[tie.first_home]), np.full(count, self.index[tie.second_home]),
                single=round_type == "FINAL", first_leg=first_leg,
            )
        return winners

    def top_position(self, tie: Tie) -> int:
        """League position (0-based) of the better-placed team in a real tie."""
        return int(min(self.positions[0, self.index[tie.first_home]], self.positions[0, self.index[tie.second_home]]))

    def run(self) -> dict[str, np.ndarray]:
        sims, order = self.sims, self.order
        count = len(sims)
        reached = {name: np.zeros(self.positions.shape, dtype=bool) for name in ROUND_ORDER}
        reached["LEAGUE"][:] = True

        def mark(name: str, members: np.ndarray) -> None:
            reached[name][sims[:, None], members] = True

        # Knockout play-offs. group_columns[k]: the two play-off ties of bracket group k.
        mark("FINAL_TOURNAMENT_PLAY_OFF", order[:, 8:24])
        if "FINAL_TOURNAMENT_PLAY_OFF" in self.real:
            playoff_winners = self.play_real("FINAL_TOURNAMENT_PLAY_OFF")
            groups = [(self.top_position(tie) - 8) // 2 for tie in self.real["FINAL_TOURNAMENT_PLAY_OFF"]]
            group_columns = {k: [column for column, group in enumerate(groups) if group == k] for k in range(4)}
        else:
            flips = self.rng.random((count, 4)) < 0.5
            seeded, unseeded = [], []
            for k in range(4):
                for j in range(2):
                    seeded.append(order[:, 8 + 2 * k + j])
                    unseeded.append(np.where(flips[:, k], order[:, 23 - 2 * k - j], order[:, 22 - 2 * k + j]))
            playoff_winners = self.play(np.stack(seeded, axis=1), np.stack(unseeded, axis=1))
            group_columns = {k: [2 * k, 2 * k + 1] for k in range(4)}
        if any(len(columns) != 2 for columns in group_columns.values()):
            # The real pairings do not follow the bracket rules as computed; pair them in order.
            group_columns = {k: [2 * k, 2 * k + 1] for k in range(4)}

        # Round of 16. labels[column]: the top-eight position heading that tie.
        mark("ROUND_OF_16", order[:, :8])
        mark("ROUND_OF_16", playoff_winners)
        if "ROUND_OF_16" in self.real:
            r16_winners = self.play_real("ROUND_OF_16")
            labels = [self.top_position(tie) for tie in self.real["ROUND_OF_16"]]
        else:
            tops, bottoms, labels = [], [], []
            for pair in range(4):
                opponents = playoff_winners[:, group_columns[3 - pair]]
                swap = self.rng.random(count) < 0.5
                for j in range(2):
                    tops.append(order[:, 2 * pair + j])
                    bottoms.append(np.where(swap, opponents[:, 1 - j], opponents[:, j]))
                    labels.append(2 * pair + j)
            r16_winners = self.play(np.stack(tops, axis=1), np.stack(bottoms, axis=1))
        if sorted(labels) != list(range(8)):
            labels = list(range(8))
        column_of_label = {label: column for column, label in enumerate(labels)}
        mark("QUARTER_FINALS", r16_winners)

        # Halves of the bracket, consistent with real quarter- and semi-final draws.
        winner_label: dict[int, int] = {}
        if "ROUND_OF_16" in self.real:
            for tie, label in zip(self.real["ROUND_OF_16"], labels):
                if tie.winner in self.index:
                    winner_label[self.index[tie.winner]] = label
        real_quarters = self.real.get("QUARTER_FINALS", [])
        quarter_pairs = [
            frozenset(winner_label[self.index[team]] for team in tie.teams)
            for tie in real_quarters
            if all(self.index[team] in winner_label for team in tie.teams)
        ]
        semi_groups = []
        if len(quarter_pairs) == 4 and "SEMIFINAL" in self.real:
            pair_of = {self.index[team]: pair for tie, pair in zip(real_quarters, quarter_pairs) for team in tie.teams}
            for tie in self.real["SEMIFINAL"]:
                members = [pair_of.get(self.index[team]) for team in tie.teams]
                if all(members):
                    semi_groups.append(members[0] | members[1])
        layouts = np.array(half_layouts(quarter_pairs, semi_groups))
        bits = layouts[self.rng.integers(len(layouts), size=count)]  # (simulations, 4)
        # Quarter-final slots in bracket order: (half 0: pairs 0v3, 1v2), (half 1: pairs 0v3, 1v2).
        slot_labels = []
        for side in (0, 1):
            for first, second in ((0, 3), (1, 2)):
                slot_labels.append((2 * first + (side ^ bits[:, first]), 2 * second + (side ^ bits[:, second])))

        def r16_winner(label: np.ndarray) -> np.ndarray:
            columns = np.vectorize(column_of_label.get)(label)
            return r16_winners[sims, columns]

        if "QUARTER_FINALS" in self.real:
            quarter_winners = self.play_real("QUARTER_FINALS")
            if len(quarter_pairs) == 4:
                # Put the real ties in bracket order so the semi-finals pair the right winners.
                lookup = {pair: column for column, pair in enumerate(quarter_pairs)}
                ordered = []
                for a, b in slot_labels:
                    columns = np.array([lookup.get(frozenset((x, y)), 0) for x, y in zip(a, b)])
                    ordered.append(quarter_winners[sims, columns])
                quarter_winners = np.stack(ordered, axis=1)
        else:
            firsts = np.stack([r16_winner(a) for a, _ in slot_labels], axis=1)
            seconds = np.stack([r16_winner(b) for _, b in slot_labels], axis=1)
            quarter_winners = self.play(*self.better_first(firsts, seconds))
        mark("SEMIFINAL", quarter_winners)

        if "SEMIFINAL" in self.real:
            semi_winners = self.play_real("SEMIFINAL")
        else:
            top, bottom = self.better_first(quarter_winners[:, [0, 2]], quarter_winners[:, [1, 3]])
            semi_winners = self.play(top, bottom)
        mark("FINAL", semi_winners)

        if "FINAL" in self.real:
            champions = self.play_real("FINAL")[:, 0]
        else:
            champions = self.play(semi_winners[:, [0]], semi_winners[:, [1]], single=True)[:, 0]
        reached["CHAMPION"][sims, champions] = True
        return reached


def simulate(
    model: CupModel,
    teams: list[str],
    table: dict[str, dict[str, int]],
    league_matches: list[uefa.Match],
    ties: dict[str, list[Tie]],
    final_order: list[str] | None,
    tiers: list[dict[str, Any]],
    simulations: int = SIMULATIONS,
    seed: int = SEED,
    season_left: float = 1.0,
) -> dict[str, Any]:
    """Finish the league phase and play out the knockouts ``simulations`` times."""
    count = len(teams)
    index = {team: i for i, team in enumerate(teams)}
    rng = np.random.default_rng(seed)
    remaining = [match for match in league_matches if not match.played]

    # Strength per simulation: the fitted rating plus a season-long drift.
    scale = STRENGTH_DRIFT * math.sqrt(min(max(season_left, 0.0), 1.0))
    strengths = [model.strength(team) for team in teams]
    attack = np.array([value[0] for value in strengths])[None, :] + rng.normal(0.0, scale, (simulations, count))
    defence = np.array([value[1] for value in strengths])[None, :] + rng.normal(0.0, scale, (simulations, count))

    fields = ("points", "goalsFor", "goalsAgainst", "awayGoalsFor", "wins", "awayWins")
    totals = {field: np.tile(np.array([table[team][field] for team in teams], dtype=np.float64), (simulations, 1)) for field in fields}
    home_goals = away_goals = np.zeros((simulations, 0))
    if remaining:
        home_index = np.array([index[match.home] for match in remaining])
        away_index = np.array([index[match.away] for match in remaining])
        rows = np.arange(simulations)[:, None]
        home_goals = rng.poisson(np.exp(model.mu + model.home + attack[rows, home_index] - defence[rows, away_index])).astype(np.float64)
        away_goals = rng.poisson(np.exp(model.mu + attack[rows, away_index] - defence[rows, home_index])).astype(np.float64)
        home_win, draw, away_win = home_goals > away_goals, home_goals == away_goals, home_goals < away_goals
        home_side = np.zeros((len(remaining), count))
        away_side = np.zeros((len(remaining), count))
        home_side[np.arange(len(remaining)), home_index] = 1
        away_side[np.arange(len(remaining)), away_index] = 1
        totals["points"] += (3 * home_win + draw) @ home_side + (3 * away_win + draw) @ away_side
        totals["goalsFor"] += home_goals @ home_side + away_goals @ away_side
        totals["goalsAgainst"] += away_goals @ home_side + home_goals @ away_side
        totals["awayGoalsFor"] += away_goals @ away_side
        totals["wins"] += home_win @ home_side + away_win @ away_side
        totals["awayWins"] += away_win @ away_side
    if final_order is not None and not remaining:
        positions = np.tile(np.array([final_order.index(team) for team in teams]), (simulations, 1))
    else:
        # UEFA's first six criteria; the opponents' records (rarely needed) give way to a random draw.
        keys = totals["points"].copy()
        difference = totals["goalsFor"] - totals["goalsAgainst"]
        for value, span in ((difference + 200, 400), (totals["goalsFor"], 200), (totals["awayGoalsFor"], 100), (totals["wins"], 10), (totals["awayWins"], 10)):
            keys = keys * span + value
        positions = team_sports.positions_from_keys(keys + rng.random(keys.shape))

    reached = Knockouts(rng, model, attack, defence, positions, index, ties).run()
    flags = {}
    for tier in tiers:
        kind = tier.get("kind")
        if kind == "top":
            flags[tier["key"]] = positions < tier["size"]
        elif kind == "round":
            flags[tier["key"]] = reached[tier["round"]]
        elif kind == "champion":
            flags[tier["key"]] = reached["CHAMPION"]
    probabilities = {team: {key: round(float(flag[:, i].mean()) * 100, 2) for key, flag in flags.items()} for team, i in index.items()}
    position_odds = {
        team: [round(value * 100, 2) for value in np.bincount(positions[:, i], minlength=count) / simulations] for team, i in index.items()
    }
    expected = {
        team: {"points": round(float(totals["points"][:, i].mean()), 1), "position": round(float(positions[:, i].mean()) + 1, 1)}
        for team, i in index.items()
    }
    matter = (
        football.matches_that_matter([_as_game(match) for match in remaining], home_goals, away_goals, flags, tiers, teams)
        if remaining
        else []
    )
    return {
        "simulations": simulations,
        "probabilities": probabilities,
        "positions": position_odds,
        "expected": expected,
        "matchesThatMatter": matter,
        "flags": flags,
    }


def _as_game(match: uefa.Match) -> team_sports.Game:
    return team_sports.Game(
        id=match.id, round=None, date=match.date, home=match.home, away=match.away, venue=None,
        home_score=match.home_score, away_score=match.away_score,
    )


# --- Payload ------------------------------------------------------------------------------


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def model_results(
    competition: int, year: int, current: list[uefa.Match], info: dict[str, uefa.Team], cache_dir: Path, warnings: list[str]
) -> tuple[list[Result], dict[str, str]]:
    """Every UEFA club match of this season and the previous ones, plus domestic league games,
    and each club's country (domestic-only clubs are keyed "ENG:Name")."""
    found = list(current)
    teams = dict(info)
    for offset in range(HISTORY_SEASONS):
        for other in uefa.COMPETITIONS.values():
            if offset == 0 and other == competition:
                continue
            try:
                matches, more = uefa.fetch_matches(other, year - offset, cache_dir, max_age_hours=3 if offset == 0 else 24 * 30)
            except team_sports.FeedError as exc:
                warnings.append(f"Some past UEFA matches are unavailable ({exc}); ratings use the rest.")
                continue
            found += matches
            teams.update(more)
    results = uefa_results(found) + domestic_results(year, teams, cache_dir)
    country_of = {team.id: team.country for team in teams.values()}
    for result in results:
        for key in (result.home, result.away):
            if key not in country_of and ":" in key:
                country_of[key] = key.split(":", 1)[0]
    return results, country_of


def team_meta(config: dict[str, Any], info: dict[str, uefa.Team], teams: list[str]) -> dict[str, dict[str, str]]:
    """Display names from UEFA; colours from the config by UEFA team id, otherwise generated."""
    overrides = config.get("teams", {})
    taken: set[str] = set()
    meta = {}
    for team in sorted(teams, key=lambda key: info[key].name):
        override = overrides.get(team, {})
        short = override.get("shortName") or info[team].code
        if not short or short in taken:
            short = team_sports.auto_short_name(info[team].name, taken)
        taken.add(short)
        color, text = team_sports.hashed_colors(info[team].name)
        if team in CLUB_COLOURS:
            color = CLUB_COLOURS[team]
            # Black or white text, whichever contrasts more (they tie at luminance 0.179).
            text = "#000000" if team_sports.relative_luminance(color) > 0.179 else "#FFFFFF"
        meta[team] = {
            "key": team,
            "shortName": short,
            "fullName": override.get("fullName", info[team].name.strip()),
            "color": override.get("color", color),
            "textColor": override.get("textColor", text),
        }
    return meta


def stage_label(match: uefa.Match) -> str | None:
    if match.round == uefa.LEAGUE_PHASE:
        return None
    label = ROUND_LABELS.get(match.round, match.round)
    return f"{label}, {'1st' if match.leg == 1 else '2nd'} leg" if match.leg else label


def result_note(match: uefa.Match, ties: dict[str, list[Tie]]) -> str | None:
    """'Round of 16, 2nd leg · agg 5-3 (aet)' and the like for knockout matches."""
    label = stage_label(match)
    if label is None:
        return None
    parts = [label]
    extra_time = match.home_total is not None and (match.home_total, match.away_total) != (match.home_score, match.away_score)
    if extra_time:
        parts.append(f"{match.home_total}-{match.away_total} after extra time")
    if match.home_penalties is not None:
        parts.append(f"{match.home_penalties}-{match.away_penalties} on penalties")
    if match.leg == 2:
        tie = next((tie for tie in ties.get(match.round, []) if match in tie.legs), None)
        if tie and len(tie.legs) == 2 and all(leg.played for leg in tie.legs):
            home_total = sum((leg.home_total if leg.home_total is not None else leg.home_score) if leg.home == match.home else (leg.away_total if leg.away_total is not None else leg.away_score) for leg in tie.legs)
            away_total = sum((leg.home_total if leg.home_total is not None else leg.home_score) if leg.home == match.away else (leg.away_total if leg.away_total is not None else leg.away_score) for leg in tie.legs)
            parts.append(f"agg {home_total}-{away_total}")
    return " · ".join(parts)


def bracket(ties: dict[str, list[Tie]], positions: dict[str, int]) -> dict[str, Any] | None:
    """Real knockout ties, round by round, for the bracket panel."""
    rounds = []
    champion = None
    for round_type in uefa.KNOCKOUT_ROUNDS:
        items = ties.get(round_type, [])
        if not items:
            continue
        series = []
        for tie in items:
            a, b = tie.first_home, tie.second_home
            top, bottom = (a, b) if positions.get(a, 99) <= positions.get(b, 99) else (b, a)

            def goals(team: str) -> int:
                total = 0
                for leg in tie.legs:
                    if not leg.played:
                        continue
                    home_goals = leg.home_total if leg.home_total is not None else leg.home_score
                    away_goals = leg.away_total if leg.away_total is not None else leg.away_score
                    total += home_goals if leg.home == team else away_goals
                return total

            penalties = next(((leg.home_penalties, leg.away_penalties, leg.home) for leg in tie.legs if leg.home_penalties is not None), None)
            note = None
            if penalties:
                home_pens, away_pens, home = penalties
                top_pens, bottom_pens = (home_pens, away_pens) if home == top else (away_pens, home_pens)
                note = f"{top_pens}-{bottom_pens} on penalties"
            series.append(
                {
                    "stage": ROUND_LABELS[round_type],
                    "conference": None,
                    "top": top,
                    "bottom": bottom,
                    "topSeed": positions[top] + 1 if top in positions else None,
                    "bottomSeed": positions[bottom] + 1 if bottom in positions else None,
                    "topWins": 0,
                    "bottomWins": 0,
                    "bestOf": len(tie.legs) if round_type != "FINAL" else 1,
                    "winner": tie.winner,
                    "aggregate": {"top": goals(top), "bottom": goals(bottom)} if any(leg.played for leg in tie.legs) else None,
                    "legs": [
                        {
                            "date": iso(leg.date),
                            "home": leg.home,
                            "away": leg.away,
                            "homeScore": (leg.home_total if leg.home_total is not None else leg.home_score) if leg.played else None,
                            "awayScore": (leg.away_total if leg.away_total is not None else leg.away_score) if leg.played else None,
                        }
                        for leg in tie.legs
                    ],
                    **({"note": note} if note else {}),
                }
            )
            if round_type == "FINAL" and tie.winner:
                champion = tie.winner
        rounds.append({"key": round_type, "label": ROUND_LABELS[round_type], "series": series})
    return {"rounds": rounds, "champion": champion} if rounds else None


def build_payload(config: dict[str, Any], now: datetime, cache_dir: Path) -> dict[str, Any]:
    team_sports.validate_config(config)
    season = team_sports.resolve_season(config, now)
    year = int(season.feed)
    competition = int(config["sources"]["uefa"])
    matches, info = uefa.fetch_matches(competition, year, cache_dir)
    league_matches = [match for match in matches if match.round == uefa.LEAGUE_PHASE]
    if not league_matches:
        raise team_sports.FeedError(f"{season.payload_id}: no league-phase fixtures yet")
    teams = sorted({match.home for match in league_matches} | {match.away for match in league_matches}, key=lambda team: info[team].name)
    warnings: list[str] = []

    table = league_table(league_matches, teams)
    order = ranked(table, league_matches)
    try:
        official = official_order(table, uefa.fetch_standings(competition, year, cache_dir))
        if official is None:
            warnings.append("UEFA's published table differs from the results; the table is computed from the results.")
        else:
            order = official
    except team_sports.FeedError as exc:
        print(f"{season.payload_id}: official table unavailable ({exc})")
    positions = {team: rank for rank, team in enumerate(order)}

    history, country_of = model_results(competition, year, matches, info, cache_dir, warnings)
    latest = max((result.date for result in history), default=now)
    # Weights decay from the latest result rather than from today, so ratings only change when results do.
    model = fit_model(history, min(latest, now), country_of)

    ties = knockout_ties(matches)
    remaining = [match for match in league_matches if not match.played]
    knockout_played = sum(1 for match in matches if match.round in uefa.KNOCKOUT_ROUNDS and match.played)
    season_left = (len(remaining) + max(0, KNOCKOUT_MATCHES - knockout_played)) / (len(league_matches) + KNOCKOUT_MATCHES)
    pending = [match for match in remaining if match.date < now - timedelta(hours=6)]
    if pending:
        warnings.append(
            f"{len(pending)} past league-phase match{'es have' if len(pending) > 1 else ' has'} no result yet "
            f"(postponed, or not yet updated at {uefa.SOURCE}); {'they are' if len(pending) > 1 else 'it is'} simulated as still to play."
        )
    tiers = config["tiers"]
    simulation = simulate(model, teams, table, league_matches, ties, None if remaining else order, tiers, season_left=season_left)
    probabilities = simulation["probabilities"]

    knockout = bracket(ties, positions) if not remaining else None
    champion = knockout["champion"] if knockout else None
    if remaining:
        status = "in_progress"
    elif champion:
        status = "complete"
    else:
        status = "playoffs"
    if remaining:
        payload_tiers = tiers
    else:
        # League places are settled once the league phase ends; knockout rounds once decided for everyone.
        payload_tiers = [
            dict(tier, settled=True) if tier["kind"] == "top" or all(values[tier["key"]] in (0.0, 100.0) for values in probabilities.values()) else tier
            for tier in tiers
        ]

    meta = team_meta(config, info, teams)
    form_games = [_as_game(match) for match in league_matches]
    standings = [
        {
            "teamKey": team,
            "shortName": meta[team]["shortName"],
            "fullName": meta[team]["fullName"],
            "rank": rank,
            **{key: value for key, value in table[team].items() if key not in ("awayGoalsFor", "awayWins")},
            "form": team_sports.form_strings(form_games, team),
            "remaining": sum(1 for match in remaining if team in (match.home, match.away)),
        }
        for rank, team in enumerate(order, start=1)
    ]

    upcoming = sorted(
        [match for match in matches if not match.played and not match.qualifying and (match.round == uefa.LEAGUE_PHASE or match.round in uefa.KNOCKOUT_ROUNDS)],
        key=lambda match: match.date,
    )
    fixtures = []
    for match in upcoming:
        home, draw, away = model.outcome(match.home, match.away, match.neutral)
        fixtures.append(
            {
                "id": match.id,
                "round": None,
                "date": iso(match.date),
                "home": match.home,
                "away": match.away,
                "venue": None,
                **({"stage": stage_label(match)} if stage_label(match) else {}),
                "probabilities": {"home": round(home, 3), "draw": round(draw, 3), "away": round(away, 3)},
            }
        )
    played = sorted(
        [match for match in matches if match.played and not match.qualifying and (match.round == uefa.LEAGUE_PHASE or match.round in uefa.KNOCKOUT_ROUNDS)],
        key=lambda match: match.date,
        reverse=True,
    )
    results = [
        {
            "id": match.id,
            "round": None,
            "date": iso(match.date),
            "home": match.home,
            "away": match.away,
            "homeScore": match.home_score,
            "awayScore": match.away_score,
            **({"note": result_note(match, ties)} if match.round != uefa.LEAGUE_PHASE else {}),
        }
        for match in played
    ]
    games = len(league_matches) * 2 // len(teams)
    notes = [
        f"Team strength comes from a Poisson goals model (attack, defence, home advantage) fitted on every UEFA club "
        f"match from this season and the {HISTORY_SEASONS - 1} before, qualifiers included, plus domestic league games "
        f"from nine countries at a quarter weight, with a {HALF_LIFE_DAYS}-day half-life.",
        "Each club is rated as its country's level plus its own difference from it, so a club with only a few "
        "European games sits near its compatriots until its results say otherwise.",
        f"The rest of the league phase and every knockout round are simulated {SIMULATIONS:,} times, letting team "
        "strength drift (more when more of the season is left).",
        "League-phase ties follow UEFA's order: points, goal difference, goals scored, away goals scored, wins, away wins, "
        "then the opponents' combined record; simulated seasons settle anything still level by lot.",
        "Knockout draws follow UEFA's seeding: places 9-24 meet in the play-offs (9/10 v 23/24, 11/12 v 21/22, 13/14 v 19/20, "
        "15/16 v 17/18), the top eight meet the play-off winners from the matching pair, and the top eight pairs are split "
        "between the halves of the bracket. Ties level after two legs go to extra time, then penalties (a coin flip).",
        "Backtested on 2024-25 and 2025-26 (1,062 main-draw matches in the three competitions): week-ahead predictions score "
        "0.203 (ranked probability score) against 0.232 for home/draw/away base rates.",
    ]
    if games:
        notes.insert(0, f"{len(teams)} clubs play {games} league-phase games each.")
    return {
        "metadata": {
            "season": season.label,
            "generated_at": iso(now),
            "source": uefa.SOURCE,
            "source_url": uefa.SOURCE_URL,
            "data_freshness_status": "warning" if warnings else "fresh",
            "season_status": status,
            "warnings": warnings,
            "credits": [
                {"name": team_sports.FEED_SOURCE, "url": team_sports.FEED_SOURCE_URL, "note": "Domestic league results for the ratings: FixtureDownload"}
            ],
        },
        "league": {
            "id": season.payload_id,
            "configId": config["id"],
            "sport": "football",
            "name": config["name"],
            "shortName": config["shortName"],
            "headline": config.get("headline"),
            "season": season.label,
            "seasonLabel": season.label,
            "priority": config.get("priority", 100),
            "tiers": payload_tiers,
            "columns": [
                {"key": "played", "label": "P"},
                {"key": "wins", "label": "W"},
                {"key": "draws", "label": "D"},
                {"key": "losses", "label": "L"},
                {"key": "goalDifference", "label": "GD", "signed": True},
                {"key": "points", "label": "Pts", "strong": True},
            ],
            "outcomes": ["home", "draw", "away"],
            "teams": [meta[team] for team in teams],
            "positionLabel": "League-phase position",
            "positionZones": [{"to": 8, "kind": "top"}, {"to": 24, "kind": "mid"}],
        },
        "standings": standings,
        "fixtures": fixtures,
        "results": results,
        "analysis": {
            "method": "Monte Carlo",
            "simulations": simulation["simulations"],
            "model": "Poisson goals model",
            "modelNotes": notes,
            "probabilities": probabilities,
            "positions": simulation["positions"],
            "expected": simulation["expected"],
            "ratings": {team: {"attack": round(model.strength(team)[0], 3), "defence": round(model.strength(team)[1], 3)} for team in teams},
        },
        "matchesThatMatter": simulation["matchesThatMatter"],
        **({"bracket": knockout} if knockout else {}),
        **({"playoffs": {"champion": champion}} if champion else {}),
    }
