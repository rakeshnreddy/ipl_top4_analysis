"""Test-match ratings for the World Test Championship.

A Davidson model of the three Test results: with strengths ``a`` and ``b`` (team rating
plus home advantage when the Test is in that team's country) and a draw propensity
``d`` for the venue's country,

    P(a wins) = e^a / Z,   P(b wins) = e^b / Z,   P(draw) = e^(d + (a + b) / 2) / Z.

Close sides draw more often than mismatched ones, and the draw propensity follows the
venue's country (pitches, weather) and the era: results lose weight with age, so the
fit reflects recent seasons, when Tests have been drawn far less often than in the
2000s. Home advantage also has a per-country part, shrunk towards the overall one.

Ratings come from every men's Test in Cricsheet's archive (ODC-By 1.0), weighted by
age. Settings were chosen by ``scripts/backtest_wtc.py``; see ``ModelSettings``.
"""

from __future__ import annotations

import json
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import requests


CRICSHEET_TESTS = "tests_male"
CRICSHEET_TESTS_URL = f"https://cricsheet.org/downloads/{CRICSHEET_TESTS}_json.zip"
REQUEST_TIMEOUT_SECONDS = 90
USER_AGENT = "PlayoffPulse/1.0 (+https://github.com/rakeshnreddy/ipl_top4_analysis)"

# Cricsheet's team names, keyed by the codes used here. ZIM and IRE play Tests outside the
# championship; their games still inform the ratings of the teams they meet.
TEAM_CODES = {
    "Australia": "AUS",
    "Bangladesh": "BAN",
    "England": "ENG",
    "India": "IND",
    "New Zealand": "NZ",
    "Pakistan": "PAK",
    "South Africa": "SA",
    "Sri Lanka": "SL",
    "West Indies": "WI",
    "Zimbabwe": "ZIM",
    "Ireland": "IRE",
    "Afghanistan": "AFG",
}
# The UAE hosts Tests as a neutral country (Pakistan's and Afghanistan's "home" Tests).
NEUTRAL = "UAE"

# Where each Test ground is. Cricsheet gives a city for most Tests and only the venue for some.
CITY_COUNTRY = {
    **dict.fromkeys(
        ["Adelaide", "Brisbane", "Cairns", "Canberra", "Darwin", "Hobart", "Mackay", "Melbourne", "Perth", "Sydney"],
        "AUS",
    ),
    **dict.fromkeys(
        ["Birmingham", "Bristol", "Cardiff", "Chester-le-Street", "Leeds", "London", "Manchester", "Nottingham", "Southampton", "Taunton"],
        "ENG",
    ),
    **dict.fromkeys(
        [
            "Ahmedabad", "Bangalore", "Bengaluru", "Chandigarh", "Chennai", "Cuttack", "Delhi", "Dharamsala", "Guwahati",
            "Hyderabad", "Indore", "Kanpur", "Kolkata", "Lucknow", "Mohali", "Mumbai", "Nagpur", "Pune", "Raipur", "Rajkot",
            "Ranchi", "Thiruvananthapuram", "Visakhapatnam",
        ],
        "IND",
    ),
    **dict.fromkeys(
        ["Auckland", "Christchurch", "Dunedin", "Hamilton", "Mount Maunganui", "Napier", "Nelson", "Queenstown", "Wellington"],
        "NZ",
    ),
    **dict.fromkeys(["Faisalabad", "Karachi", "Lahore", "Multan", "Peshawar", "Rawalpindi"], "PAK"),
    **dict.fromkeys(
        [
            "Benoni", "Bloemfontein", "Cape Town", "Centurion", "Durban", "East London", "Gqeberha", "Johannesburg", "Paarl",
            "Port Elizabeth", "Potchefstroom",
        ],
        "SA",
    ),
    **dict.fromkeys(["Colombo", "Dambulla", "Galle", "Hambantota", "Kandy", "Pallekele"], "SL"),
    **dict.fromkeys(
        [
            "Antigua", "Barbados", "Basseterre", "Bridgetown", "Dominica", "Grenada", "Gros Islet", "Guyana", "Jamaica",
            "Kingston", "Kingstown", "North Sound", "Port of Spain", "Providence", "Roseau", "St George's", "St John's",
            "St Kitts", "St Lucia", "St Vincent", "Tarouba", "Trinidad",
        ],
        "WI",
    ),
    **dict.fromkeys(["Bogra", "Chattogram", "Chittagong", "Dhaka", "Fatullah", "Khulna", "Mirpur", "Sylhet"], "BAN"),
    **dict.fromkeys(["Bulawayo", "Harare"], "ZIM"),
    **dict.fromkeys(["Belfast", "Dublin", "Malahide"], "IRE"),
    **dict.fromkeys(["Abu Dhabi", "Dubai", "Sharjah"], NEUTRAL),
}
# Venues Cricsheet lists without a city: the city is the venue's last part, or one of these.
VENUE_CITY = {
    "Adelaide Oval": "Adelaide",
    "Dubai International Cricket Stadium": "Dubai",
    "Galle International Stadium": "Galle",
    "Harare Sports Club": "Harare",
    "Melbourne Cricket Ground": "Melbourne",
    "Multan Cricket Stadium": "Multan",
    "Pallekele International Cricket Stadium": "Pallekele",
    "Perth Stadium": "Perth",
    "Sharjah Cricket Stadium": "Sharjah",
    "Sydney Cricket Ground": "Sydney",
    "Sylhet International Cricket Stadium": "Sylhet",
}

# Result codes, always from the first team's point of view in a Test record.
WIN, DRAW, LOSS = 0, 1, 2


class TestDataError(RuntimeError):
    pass


def venue_country(city: str | None, venue: str | None) -> str | None:
    """The country code of a Test ground, or None when the ground is unknown."""
    if city and city in CITY_COUNTRY:
        return CITY_COUNTRY[city]
    if venue:
        if venue in VENUE_CITY:
            return CITY_COUNTRY.get(VENUE_CITY[venue])
        tail = venue.rsplit(",", 1)[-1].strip()
        if tail in CITY_COUNTRY:
            return CITY_COUNTRY[tail]
    return None


@dataclass(frozen=True)
class TestMatch:
    """A finished Test from Cricsheet."""

    match_id: str
    start: date
    end: date
    teams: tuple[str, str]
    venue: str
    city: str | None
    country: str | None
    # None for a draw (or a Test abandoned as a draw).
    winner: str | None
    tie: bool = False
    event: str | None = None
    event_match: int | None = None
    margin: str = ""
    awarded: bool = False

    @property
    def result_for_first(self) -> int:
        if self.winner is None:
            return DRAW
        return WIN if self.winner == self.teams[0] else LOSS


def _margin_text(outcome: dict[str, Any]) -> str:
    by = outcome.get("by") or {}
    if outcome.get("method") == "Awarded":
        return "awarded"
    if "innings" in by:
        return f"an innings and {by.get('runs', 0)} runs"
    if "runs" in by:
        return f"{by['runs']} run{'s' if by['runs'] != 1 else ''}"
    if "wickets" in by:
        return f"{by['wickets']} wicket{'s' if by['wickets'] != 1 else ''}"
    return ""


def parse_test(match_id: str, info: dict[str, Any]) -> TestMatch | None:
    """One Cricsheet Test record; None for sides outside the code list (the World XI)."""
    names = info.get("teams") or []
    if len(names) != 2 or any(name not in TEAM_CODES for name in names):
        return None
    teams = (TEAM_CODES[names[0]], TEAM_CODES[names[1]])
    outcome = info.get("outcome") or {}
    winner_name = outcome.get("winner")
    result = outcome.get("result")
    if winner_name is None and result not in ("draw", "tie"):
        return None
    dates = sorted(info.get("dates") or [])
    if not dates:
        return None
    event = info.get("event") or {}
    return TestMatch(
        match_id=match_id,
        start=date.fromisoformat(dates[0]),
        end=date.fromisoformat(dates[-1]),
        teams=teams,
        venue=info.get("venue") or "",
        city=info.get("city"),
        country=venue_country(info.get("city"), info.get("venue")),
        winner=TEAM_CODES.get(winner_name) if winner_name else None,
        tie=result == "tie",
        event=event.get("name"),
        event_match=event.get("match_number"),
        margin=_margin_text(outcome),
        awarded=outcome.get("method") == "Awarded",
    )


def fetch_tests_archive(cache_dir: Path, max_age_hours: float = 6, session: requests.Session | None = None) -> Path:
    """Cricsheet's men's Test archive, refreshed every few hours; a failed refresh keeps the cached copy."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{CRICSHEET_TESTS}_json.zip"
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return path
    try:
        response = (session or requests).get(CRICSHEET_TESTS_URL, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        partial = path.with_suffix(".part")
        partial.write_bytes(response.content)
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip() is not None:
                raise TestDataError("the downloaded archive is corrupt")
        partial.replace(path)
    except (requests.RequestException, zipfile.BadZipFile, TestDataError) as exc:
        if not path.exists():
            raise TestDataError(f"Cricsheet Tests: {exc}") from exc
        print(f"Cricsheet Tests: using the cached archive ({exc})")
    return path


def load_tests(archive: Path) -> list[TestMatch]:
    """Every finished men's Test in the archive, oldest first."""
    tests = []
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not name.endswith(".json"):
                continue
            info = json.loads(bundle.read(name)).get("info") or {}
            if (info.get("match_type") or "Test") != "Test":
                continue
            test = parse_test(name.rsplit("/", 1)[-1].removesuffix(".json"), info)
            if test:
                tests.append(test)
    return sorted(tests, key=lambda test: (test.start, test.match_id))


def home_of(team: str) -> str:
    """The country a team plays its home Tests in (the West Indies' grounds are all "WI")."""
    return team


@dataclass(frozen=True)
class ModelSettings:
    """Model settings, chosen by ``scripts/backtest_wtc.py --tune`` on four championship cycles.

    A two-pass coordinate search on the log loss of every championship Test, each predicted from
    the Tests before it. On the final set of 242 Tests these settings score 0.8786, and changing
    any one of them scores worse (figures below). Shorter memories were clearly worse in the
    search (half-life 2 years 0.9008, 4 years 0.8863), and so was no draw trend (0.8999).
    """

    # Results lose half their weight in this many years (8: 0.8795, 20: 0.8788).
    half_life_years: float = 12.0
    # Ridge (prior precision) on team ratings: pulls sides with few Tests to the average (1: 0.8791, 4: 0.8808).
    rating_ridge: float = 2.0
    # Ridge on each country's own home advantage, around the overall one. The backtest shrinks it
    # almost to the overall advantage (64: 0.8786, the same; 4 and 16 were worse in the search).
    home_ridge: float = 256.0
    # Ridge on each country's draw propensity, around the overall one (0.5: 0.8792, 8: 0.8789).
    draw_ridge: float = 2.0
    # Draw propensity changes by this much per year back in time (fitted when True).
    draw_trend: bool = True


@dataclass
class Ratings:
    """A fitted model: team ratings, home advantage and draw propensity by country."""

    teams: list[str]
    countries: list[str]
    rating: dict[str, float]
    home: float
    home_by_country: dict[str, float]
    draw: float
    draw_by_country: dict[str, float]
    trend: float = 0.0
    as_of: date | None = None
    weight: float = 0.0
    games: dict[str, float] = field(default_factory=dict)

    def strengths(self, team_a: str, team_b: str, country: str | None, rating_a: float | None = None, rating_b: float | None = None) -> tuple[float, float, float]:
        """Linear predictors (a wins, draw, b wins) for a Test in ``country`` (None for unknown or neutral)."""
        a = self.rating.get(team_a, 0.0) if rating_a is None else rating_a
        b = self.rating.get(team_b, 0.0) if rating_b is None else rating_b
        advantage = self.home + self.home_by_country.get(country or "", 0.0)
        if country and home_of(team_a) == country:
            a += advantage
        if country and home_of(team_b) == country:
            b += advantage
        d = self.draw + self.draw_by_country.get(country or "", 0.0) + (a + b) / 2
        return a, d, b

    def probabilities(self, team_a: str, team_b: str, country: str | None) -> tuple[float, float, float]:
        """P(a wins), P(draw), P(b wins)."""
        values = np.array(self.strengths(team_a, team_b, country))
        values = np.exp(values - values.max())
        values /= values.sum()
        return float(values[0]), float(values[1]), float(values[2])


def _years(day: date, reference: date) -> float:
    return (reference - day).days / 365.25


def fit(tests: Iterable[TestMatch], as_of: date, settings: ModelSettings = ModelSettings(), iterations: int = 30) -> Ratings:
    """Weighted penalised maximum likelihood (Newton's method) on Tests finished before ``as_of``."""
    games = [test for test in tests if test.end < as_of and test.country is not None]
    if not games:
        raise TestDataError("no finished Tests to rate")
    teams = sorted({team for test in games for team in test.teams})
    countries = sorted({test.country for test in games if test.country})
    t_index = {team: i for i, team in enumerate(teams)}
    c_index = {country: i for i, country in enumerate(countries)}
    n_t, n_c = len(teams), len(countries)
    # Parameters: ratings, home, home by country, draw, draw by country, draw trend.
    home_at = n_t
    home_c = n_t + 1
    draw_at = home_c + n_c
    draw_c = draw_at + 1
    trend_at = draw_c + n_c
    size = trend_at + 1
    n = len(games)
    design = np.zeros((n, 3, size))
    outcome = np.zeros(n, dtype=int)
    weights = np.zeros(n)
    for row, test in enumerate(games):
        a, b = test.teams
        for column, team in ((0, a), (2, b)):
            design[row, column, t_index[team]] = 1.0
            if home_of(team) == test.country:
                design[row, column, home_at] = 1.0
                design[row, column, home_c + c_index[test.country]] = 1.0
        design[row, 1] = (design[row, 0] + design[row, 2]) / 2
        design[row, 1, draw_at] = 1.0
        design[row, 1, draw_c + c_index[test.country]] = 1.0
        age = _years(test.end, as_of)
        if settings.draw_trend:
            design[row, 1, trend_at] = -age
        outcome[row] = test.result_for_first
        weights[row] = 0.5 ** (age / settings.half_life_years)
        if test.tie:
            # A tie counts half a win for each side; it is too rare to model on its own.
            weights[row] *= 0.5
    penalty = np.zeros(size)
    penalty[:n_t] = settings.rating_ridge
    penalty[home_c : home_c + n_c] = settings.home_ridge
    penalty[draw_c : draw_c + n_c] = settings.draw_ridge
    # Weak priors keep the overall terms finite with little data.
    penalty[[home_at, draw_at]] = 0.01
    penalty[trend_at] = 0.01 if settings.draw_trend else 1e9
    theta = np.zeros(size)
    theta[draw_at] = -0.5
    chosen = design[np.arange(n), outcome]
    ties = [row for row, test in enumerate(games) if test.tie]
    for _ in range(iterations):
        eta = np.einsum("nkp,p->nk", design, theta)
        eta -= eta.max(axis=1, keepdims=True)
        prob = np.exp(eta)
        prob /= prob.sum(axis=1, keepdims=True)
        mean = np.einsum("nk,nkp->np", prob, design)
        target = chosen.copy()
        if ties:
            # Half a win for each side (each half carries the row's halved weight twice over).
            target[ties] = (design[ties, 0] + design[ties, 2]) / 2
        gradient = weights @ (target - mean) - penalty * theta
        second = np.einsum("n,nk,nkp,nkq->pq", weights, prob, design, design) - np.einsum("n,np,nq->pq", weights, mean, mean)
        hessian = second + np.diag(penalty)
        step = np.linalg.solve(hessian, gradient)
        theta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    played = {team: 0.0 for team in teams}
    for test, weight in zip(games, weights):
        for team in test.teams:
            played[team] += weight
    return Ratings(
        teams=teams,
        countries=countries,
        rating={team: float(theta[t_index[team]]) for team in teams},
        home=float(theta[home_at]),
        home_by_country={country: float(theta[home_c + c_index[country]]) for country in countries},
        draw=float(theta[draw_at]),
        draw_by_country={country: float(theta[draw_c + c_index[country]]) for country in countries},
        trend=float(theta[trend_at]) if settings.draw_trend else 0.0,
        as_of=as_of,
        weight=float(weights.sum()),
        games=played,
    )


def ranked_probability_score(probabilities: tuple[float, float, float], result: int) -> float:
    """RPS of ordered outcomes (first side wins, draw, second side wins); 0 is perfect."""
    observed = np.zeros(3)
    observed[result] = 1.0
    cumulative = np.cumsum(probabilities)[:2] - np.cumsum(observed)[:2]
    return float(np.sum(cumulative**2) / 2)


def log_loss(probabilities: tuple[float, float, float], result: int) -> float:
    return float(-np.log(max(probabilities[result], 1e-12)))


def utc_date(moment: datetime) -> date:
    return moment.astimezone(timezone.utc).date()
