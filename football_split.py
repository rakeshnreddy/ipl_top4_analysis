"""Football leagues that split in two part-way through the season (the Scottish Premiership).

A config turns it on with ``"split": {"after": 33, "size": 6}``. After 33 games each (every
pair has met three times), the table splits into sections of six. Each team then plays the
other five in its section once more, and no team can leave its section, however many points
it gains or drops afterwards (SPFL Rules C15-C17:
https://spfl.co.uk/admin/filemanager/images/shares/pdfs/June%202026%20Rules%20and%20Regs.pdf).

The post-split fixtures are published only once the split is known. Until they are in the
feed, every simulated season splits its own table and plays the missing games itself. The
home side is chosen the way the SPFL does where it can: the team that had fewer home games
against that opponent before the split hosts it. That picks 102 of the 120 post-split home
sides of 2021-22, 2022-23, 2024-25 and 2025-26; the SPFL swapped the rest so that every club
has two or three home games after the split.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

import numpy as np

import team_sports
from team_sports import Game


@dataclass(frozen=True)
class Split:
    size: int
    # Each team's section (0 = top) once the split has happened; None while it is still open.
    sections: dict[str, int] | None
    # Post-split meetings that are not in the feed yet, one per pair with its likely home side.
    # While the sections are open they cover every pair, and each simulated season keeps only
    # the meetings of teams in the same section.
    games: list[Game]
    # How many post-split games the feed still lacks.
    missing: int


def before_and_after(games: list[Game], teams: list[str], after: int) -> tuple[list[Game], list[Game]]:
    """Games before and after the split: each pair's first after / (teams - 1) meetings come before it."""
    per_pair = after // (len(teams) - 1)
    met: Counter[frozenset[str]] = Counter()
    before, later = [], []
    for game in sorted(games, key=lambda item: item.date):
        pair = frozenset((game.home, game.away))
        met[pair] += 1
        (before if met[pair] <= per_pair else later).append(game)
    return before, later


def sections_from_fixtures(later: list[Game], order: list[str], size: int) -> dict[str, int] | None:
    """The sections as published: post-split fixtures link every team to the rest of its section."""
    linked = {team: frozenset([team]) for team in order}
    for game in later:
        merged = linked[game.home] | linked[game.away]
        for team in merged:
            linked[team] = merged
    groups = set(linked.values())
    if any(len(group) != size for group in groups):
        return None
    groups_in_order = sorted(groups, key=lambda group: min(order.index(team) for team in group))
    return {team: section for section, group in enumerate(groups_in_order) for team in group}


def plan(rule: dict[str, Any], games: list[Game], teams: list[str], rank: Callable[[list[Game]], list[str]]) -> Split:
    """The split as far as it is known; ``rank`` orders the teams on a list of games (with deductions)."""
    size = rule["size"]
    before, later = before_and_after(games, teams, rule["after"])
    # Positions after the 33rd game decide the sections (SPFL Rule C16), with tiebreakers on those games only (C36).
    order = rank(before)
    sections = sections_from_fixtures(later, order, size)
    if sections is None and len(before) * 2 == len(teams) * rule["after"] and all(game.played for game in before):
        sections = {team: place // size for place, team in enumerate(order)}

    scheduled = {frozenset((game.home, game.away)) for game in later}
    hosted_against = Counter((game.home, game.away) for game in before)
    hosted = Counter(game.home for game in before)
    kickoff = max(game.date for game in games) + timedelta(days=7)
    unscheduled = []
    for first, second in itertools.combinations(sorted(teams), 2):
        if frozenset((first, second)) in scheduled or (sections is not None and sections[first] != sections[second]):
            continue
        other = {first: second, second: first}
        # Fewer home games against this opponent, then fewer home games overall.
        host, guest = sorted(other, key=lambda team: (hosted_against[team, other[team]], hosted[team], team))
        unscheduled.append(Game(f"split-{host}-{guest}", None, kickoff, host, guest, None, None, None))
    missing = max(len(teams) * (size - 1) // 2 - len(later), 0)
    return Split(size=size, sections=sections, games=unscheduled, missing=missing)


def known_sections(split: Split | None, teams: list[str]) -> np.ndarray | None:
    """Each team's section as a row for every simulated season, once the split has happened."""
    if split is None or split.sections is None:
        return None
    return np.array([[split.sections[team] for team in teams]])


def split_each_season(
    split: Split,
    teams: list[str],
    real: int,
    base: tuple[np.ndarray, np.ndarray, np.ndarray],
    goals: tuple[np.ndarray, np.ndarray],
    game_points: tuple[np.ndarray, np.ndarray],
    sides: tuple[np.ndarray, np.ndarray],
    rng: np.random.Generator,
) -> np.ndarray:
    """Each team's section in every simulated season while the split is still open.

    The first ``real`` simulated games are the feed's (all before the split); the rest are
    ``split.games``. Each season ranks its table after the real games as ``football.simulate``
    does, and the post-split games between teams in different sections are wiped, in place,
    from its goals and points.
    """
    (base_points, base_for, base_against), (home_goals, away_goals) = base, goals
    (home_points, away_points), (home_side, away_side) = game_points, sides
    points = base_points + home_points[:, :real] @ home_side[:real] + away_points[:, :real] @ away_side[:real]
    goals_for = base_for + home_goals[:, :real] @ home_side[:real] + away_goals[:, :real] @ away_side[:real]
    goals_against = base_against + away_goals[:, :real] @ home_side[:real] + home_goals[:, :real] @ away_side[:real]
    keys = (
        points.astype(np.float64) * 1e6
        + (goals_for - goals_against + 1000).astype(np.float64) * 1e3
        + goals_for
        + rng.random(points.shape)
    )
    sections = team_sports.positions_from_keys(keys) // split.size
    index = {team: i for i, team in enumerate(teams)}
    home = sections[:, [index[game.home] for game in split.games]]
    away = sections[:, [index[game.away] for game in split.games]]
    meet = (home == away).astype(np.float32)
    for values in (home_goals, away_goals, home_points, away_points):
        values[:, real:] *= meet
    return sections


def settled_tiers(tiers: list[dict[str, Any]], split: Split | None) -> list[dict[str, Any]]:
    """Once the sections are known, the race for the top section is over."""
    if split is None or split.sections is None:
        return tiers
    return [dict(tier, settled=True) if tier.get("kind", "top") == "top" and tier.get("size") == split.size else tier for tier in tiers]


def cutoffs(split: Split | None, team_count: int) -> list[dict[str, Any]]:
    """Lines between the sections on the league table."""
    return [{"after": split.size * section, "label": "Split"} for section in range(1, team_count // split.size)] if split else []


def notes(rule: dict[str, Any], split: Split) -> list[str]:
    if split.sections is None:
        state = (
            "Until then, every simulated season splits its own table and plays the post-split games itself; the home "
            "side is the team that had fewer home games against that opponent before the split, as the league "
            "arranges it where it can."
        )
    elif split.missing:
        state = (
            "The split has happened. Until the post-split fixtures are published, the home side of each is taken to "
            "be the team that had fewer home games against that opponent before the split."
        )
    else:
        state = "The split has happened and the post-split fixtures are published."
    return [
        f"After {rule['after']} games the league splits into sections of {rule['size']}: each team plays the others in "
        "its section once more and cannot leave it, so a bottom-section team finishes below every top-section team "
        f"whatever its points. {state}"
    ]
