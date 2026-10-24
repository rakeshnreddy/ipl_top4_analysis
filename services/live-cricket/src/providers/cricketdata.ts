import {
  arr,
  baseDetail,
  format,
  gender,
  integer,
  iso,
  num,
  obj,
  part,
  revision,
  SOURCES,
  str,
  unavailable,
  legalBalls,
} from "../domain";
import type {
  MatchSummary,
  Part,
  ScorecardInnings,
  MatchDetailSnapshot,
} from "../domain";

export function cricketDataMatch(
  input: unknown,
  fetchedAt: string,
): MatchSummary {
  const d = obj(input),
    fmt = format(d.matchType),
    names = arr(d.teams)
      .map((t) => str(t))
      .filter(Boolean);
  if (!/^[a-zA-Z0-9-]{1,80}$/.test(str(d.id)) || names.length !== 2)
    throw new Error("invalid_provider_match");
  const status = str(d.status);
  let state: MatchSummary["state"] = "unknown";
  if (/abandon|cancel|no result/i.test(status)) state = "abandoned";
  else if (
    d.matchEnded === true ||
    d.matchWinner ||
    (!/toss/i.test(status) && /\bwon by\b|\bdrawn\b|match tied/i.test(status))
  )
    state = "completed";
  else if (/toss/i.test(status) && d.matchStarted !== true) state = "toss";
  else if (/stump|end of day/i.test(status)) state = "stumps";
  else if (/innings break|lunch|tea break|dinner/i.test(status))
    state = "innings-break";
  else if (/rain|delay|postpon/i.test(status)) state = "delayed";
  else if (/suspend|interrupt/i.test(status)) state = "suspended";
  else if (d.matchStarted === true) state = "live";
  else if (d.matchStarted === false) state = "scheduled";
  const scores = arr(d.score).map((x, i) => {
    const s = obj(x),
      label = str(s.inning, `Innings ${i + 1}`);
    return {
      id: `${str(d.id)}-${i}`,
      team: names.find((n) => label.startsWith(n)) ?? "",
      label,
      runs: integer(s.r),
      wickets: integer(s.w),
      legalBalls: legalBalls(s.o, fmt),
      overs: s.o === null || s.o === undefined ? null : str(s.o),
    };
  });
  const core = {
    id: `cd-${str(d.id)}`,
    providerIds: { cricketdata: str(d.id) },
    teams: names.map((name, i) => ({
      id: `cd-${str(d.id)}-team-${i}`,
      name,
      shortName: str(obj(arr(d.teamInfo)[i]).shortname, name),
    })),
    competition: {
      id: str(d.series_id, "unknown"),
      name: str(d.series, "Competition not supplied"),
    },
    format: fmt,
    gender: gender(d.gender),
    state,
    statusText: status || "Status not supplied",
    startTime: iso(d.dateTimeGMT),
    venue: str(d.venue) || null,
    scores,
    capabilities: {
      scorecard: d.fantasyEnabled === true,
      commentary: false,
      model: false,
      markets: false,
    },
    source: SOURCES.cricketdata,
  };
  return {
    ...core,
    observedAt: iso(d.updated_at),
    fetchedAt,
    revision: revision(core),
  };
}
export function cricketDataCard(
  input: unknown,
  fetchedAt: string,
): Part<ScorecardInnings[]> {
  const d = obj(input),
    match = cricketDataMatch(input, fetchedAt),
    cards = arr(d.scorecard);
  if (!cards.length)
    return unavailable(
      SOURCES.cricketdata.name,
      "This response does not supply a detailed scorecard.",
    );
  return part(
    SOURCES.cricketdata.name,
    cards.map((x, i) => {
      const c = obj(x),
        t = obj(c.totals),
        score =
          match.scores.find((s) => s.label === str(c.inning)) ??
          match.scores[i];
      return {
        id: score?.id ?? `${match.id}-innings-${i}`,
        team: score?.team ?? "",
        label: str(c.inning, `Innings ${i + 1}`),
        runs: integer(t.R) ?? score?.runs ?? null,
        wickets: integer(t.W) ?? score?.wickets ?? null,
        legalBalls: legalBalls(t.O, match.format) ?? score?.legalBalls ?? null,
        overs: t.O === undefined ? (score?.overs ?? null) : str(t.O),
        batting: arr(c.batting).map((b, j) => {
          const v = obj(b),
            p = obj(v.batsman);
          return {
            id: str(p.id, `${i}-batter-${j}`),
            name: str(p.name, "Name not supplied"),
            dismissal: str(v["dismissal-text"]) || str(v.dismissal) || null,
            runs: integer(v.r),
            balls: integer(v.b),
            fours: integer(v["4s"]),
            sixes: integer(v["6s"]),
            strikeRate: num(v.sr),
          };
        }),
        bowling: arr(c.bowling).map((b, j) => {
          const v = obj(b),
            p = obj(v.bowler);
          return {
            id: str(p.id, `${i}-bowler-${j}`),
            name: str(p.name, "Name not supplied"),
            overs: v.o === undefined ? null : str(v.o),
            maidens: integer(v.m),
            runs: integer(v.r),
            wickets: integer(v.w),
            economy: num(v.eco),
          };
        }),
        extras: Object.keys(obj(c.extras)).length
          ? Object.entries(obj(c.extras))
              .filter(([, v]) => num(v) !== null)
              .map(([k, v]) => `${k}: ${str(v)}`)
              .join(", ")
          : null,
        fallOfWickets: [],
        partnerships: [],
      };
    }),
    iso(d.updated_at),
    fetchedAt,
  );
}
export function cricketDataDetail(
  info: unknown,
  card: unknown | null,
  fetchedAt: string,
): MatchDetailSnapshot {
  const result = baseDetail(cricketDataMatch(info, fetchedAt));
  result.scorecard = card
    ? cricketDataCard(card, fetchedAt)
    : unavailable(
        SOURCES.cricketdata.name,
        "Detailed scorecard access is disabled or not supplied for this match.",
      );
  result.match.capabilities.scorecard = result.scorecard.data !== null;
  result.commentary = unavailable(
    SOURCES.cricketdata.name,
    "Ball-by-ball is disabled until its current correction contract is verified.",
  );
  return result;
}
