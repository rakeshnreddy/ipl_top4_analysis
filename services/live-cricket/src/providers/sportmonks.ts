import {
  arr,
  baseDetail,
  format,
  gender,
  integer,
  iso,
  latestTime,
  legalBalls,
  num,
  obj,
  part,
  revision,
  SOURCES,
  str,
  unavailable,
} from "../domain";
import type {
  Delivery,
  MatchDetailSnapshot,
  MatchSummary,
  Part,
  ScorecardInnings,
} from "../domain";

function state(status: string): MatchSummary["state"] {
  if (status === "Finished") return "completed";
  if (/Stump/i.test(status)) return "stumps";
  if (/Innings Break|Tea Break|Lunch|Dinner/i.test(status))
    return "innings-break";
  if (/^(?:1st|2nd|3rd|4th) Innings$/.test(status)) return "live";
  if (status === "NS") return "scheduled";
  if (/Postp|Delayed/i.test(status)) return "delayed";
  if (status === "Int.") return "suspended";
  if (/Aban|Cancl/i.test(status)) return "abandoned";
  return "unknown";
}
function teamName(fixture: unknown, id: unknown): string {
  const f = obj(fixture);
  return str(
    [f.localteam, f.visitorteam].map(obj).find((t) => str(t.id) === str(id))
      ?.name,
  );
}
function playerName(fixture: unknown, id: unknown): string {
  return str(
    arr(obj(fixture).lineup)
      .map(obj)
      .find((p) => str(p.id) === str(id))?.fullname,
  );
}
export function sportmonksMatch(
  input: unknown,
  fetchedAt: string,
): MatchSummary {
  const d = obj(input),
    id = str(d.id),
    fmt = format(d.type),
    teams = [obj(d.localteam), obj(d.visitorteam)],
    league = obj(d.league);
  if (!/^\d{1,15}$/.test(id) || teams.some((t) => !str(t.name)))
    throw new Error("invalid_provider_match");
  const scores = arr(d.runs).map((x, i) => {
    const r = obj(x),
      inning = str(r.inning, i + 1 + "");
    return {
      id: str(r.id, `${id}-${inning}`),
      team: teamName(d, r.team_id),
      label: `Innings ${inning}`,
      runs: integer(r.score),
      wickets: integer(r.wickets),
      legalBalls: legalBalls(r.overs, fmt),
      overs: r.overs === undefined || r.overs === null ? null : str(r.overs),
    };
  });
  const core = {
    id: `sm-${id}`,
    providerIds: { sportmonks: id },
    teams: teams.map((t) => ({
      id: str(t.id),
      name: str(t.name),
      shortName: str(t.code, str(t.name)),
    })),
    competition: {
      id: str(league.id, str(d.league_id, "unknown")),
      name: str(league.name, "Competition not supplied"),
    },
    format: fmt,
    gender: gender(league.gender ?? d.gender),
    state: state(str(d.status)),
    statusText: [str(d.status), str(d.note)].filter(Boolean).join(" · "),
    startTime: iso(d.starting_at),
    venue: str(obj(d.venue).name) || null,
    scores,
    capabilities: {
      scorecard: Array.isArray(d.batting) || Array.isArray(d.bowling),
      commentary: Array.isArray(d.balls),
      model: false,
      markets: false,
    },
    source: SOURCES.sportmonks,
  };
  return {
    ...core,
    observedAt: latestTime(
      d.updated_at,
      ...arr(d.runs).map((r) => obj(r).updated_at),
    ),
    fetchedAt,
    revision: revision(core),
  };
}
export function sportmonksCard(
  input: unknown,
  fetchedAt: string,
): Part<ScorecardInnings[]> {
  const d = obj(input),
    match = sportmonksMatch(d, fetchedAt),
    bat = arr(d.batting).map(obj),
    bowl = arr(d.bowling).map(obj);
  if (!bat.length && !bowl.length)
    return unavailable(
      SOURCES.sportmonks.name,
      "This response does not supply batting or bowling detail.",
    );
  const innings: ScorecardInnings[] = match.scores.map((s, i) => {
    const board = `S${str(obj(arr(d.runs)[i]).inning, i + 1 + "")}`;
    return {
      ...s,
      batting: bat
        .filter((b) => str(b.scoreboard) === board)
        .map((b, j) => ({
          id: str(b.player_id, `${board}-batter-${j}`),
          name: str(
            obj(b.batsman).fullname,
            str(
              obj(b.player).fullname,
              playerName(d, b.player_id) || "Name not supplied",
            ),
          ),
          dismissal: str(obj(b.result).name) || null,
          runs: integer(b.score),
          balls: integer(b.ball),
          fours: integer(b.four_x),
          sixes: integer(b.six_x),
          strikeRate: num(b.rate),
        })),
      bowling: bowl
        .filter((b) => str(b.scoreboard) === board)
        .map((b, j) => ({
          id: str(b.player_id, `${board}-bowler-${j}`),
          name: str(
            obj(b.bowler).fullname,
            str(
              obj(b.player).fullname,
              playerName(d, b.player_id) || "Name not supplied",
            ),
          ),
          overs:
            b.overs === null || b.overs === undefined ? null : str(b.overs),
          maidens: integer(b.medians),
          runs: integer(b.runs),
          wickets: integer(b.wickets),
          economy: num(b.rate),
        })),
      extras: null,
      fallOfWickets: bat
        .filter(
          (b) => str(b.scoreboard) === board && integer(b.fow_score) !== null,
        )
        .map((b) => `${str(b.fow_score)} (${str(b.fow_balls)} ov)`),
      partnerships: [],
    };
  });
  return part(
    SOURCES.sportmonks.name,
    innings,
    latestTime(
      ...bat.map((b) => b.updated_at),
      ...bowl.map((b) => b.updated_at),
    ),
    fetchedAt,
  );
}
export function sportmonksDeliveries(
  input: unknown,
  fetchedAt: string,
): Part<Delivery[]> {
  const d = obj(input),
    balls = arr(d.balls).map(obj);
  if (!balls.length)
    return unavailable(
      SOURCES.sportmonks.name,
      "No delivery records were supplied.",
    );
  // A fixture response is a full replacement: deleted/corrected balls do not accumulate.
  const sorted = balls
    .filter((b) => str(b.id) && Object.keys(obj(b.score)).length)
    .sort(
      (a, b) =>
        str(a.scoreboard).localeCompare(str(b.scoreboard), undefined, {
          numeric: true,
        }) ||
        (num(a.ball) ?? 0) - (num(b.ball) ?? 0) ||
        str(a.id).localeCompare(str(b.id), undefined, { numeric: true }),
    );
  if (!sorted.length)
    return unavailable(
      SOURCES.sportmonks.name,
      "Delivery IDs alone do not supply delivery detail.",
    );
  const data = sorted.map((b, sequence) => {
    const s = obj(b.score),
      core = {
        id: str(b.id),
        sequence,
        innings: str(b.scoreboard),
        over: str(b.ball),
        batter:
          str(obj(b.batsman).fullname, playerName(d, b.batsman_id)) || null,
        bowler: str(obj(b.bowler).fullname, playerName(d, b.bowler_id)) || null,
        runs: integer(s.runs),
        extras: null,
        wickets:
          typeof s.is_wicket === "boolean" ? (s.is_wicket ? 1 : 0) : null,
        text: str(s.name, "Delivery details not supplied"),
      };
    // Keep every event, including wides/no-balls with the same ball notation.
    return { ...core, observedAt: iso(b.updated_at), revision: revision(core) };
  });
  return part(
    SOURCES.sportmonks.name,
    data,
    latestTime(...data.map((b) => b.observedAt)),
    fetchedAt,
  );
}
export function sportmonksDetail(
  input: unknown,
  fetchedAt: string,
): MatchDetailSnapshot {
  const result = baseDetail(sportmonksMatch(input, fetchedAt));
  result.scorecard = sportmonksCard(input, fetchedAt);
  result.commentary = sportmonksDeliveries(input, fetchedAt);
  result.match.capabilities.scorecard = result.scorecard.data !== null;
  result.match.capabilities.commentary = result.commentary.data !== null;
  return result;
}
