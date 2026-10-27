import type {
  Availability,
  MatchDetailSnapshot,
  MatchSummary,
  Part,
  Source,
} from "../../../frontend/ipl-analyzer-frontend/src/live/types";
export type {
  MatchListSnapshot,
  MatchDetailSnapshot,
  MatchSummary,
  Part,
  Source,
  ScorecardInnings,
  Delivery,
  Bookmaker,
} from "../../../frontend/ipl-analyzer-frontend/src/live/types";

export const SOURCES = {
  service: {
    id: "playoff-pulse",
    name: "Playoff Pulse",
    url: "https://ipl-playoff-pulse.pages.dev/cricket/",
  },
  cricketdata: {
    id: "cricketdata",
    name: "CricketData",
    url: "https://cricketdata.org/",
  },
  sportmonks: {
    id: "sportmonks",
    name: "Sportmonks",
    url: "https://www.sportmonks.com/cricket-api/",
  },
  sportscore: {
    id: "sportscore",
    name: "SportScore",
    url: "https://sportscore.com/",
  },
  odds: {
    id: "the-odds-api",
    name: "The Odds API",
    url: "https://the-odds-api.com/",
  },
} satisfies Record<string, Source>;

export type Obj = Record<string, unknown>;
export const obj = (value: unknown): Obj =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Obj)
    : {};
export const arr = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];
export const str = (value: unknown, fallback = ""): string =>
  typeof value === "string"
    ? value.slice(0, 1000)
    : typeof value === "number" && Number.isFinite(value)
      ? String(value)
      : fallback;
export const num = (value: unknown): number | null =>
  (typeof value === "number" ||
    (typeof value === "string" && value.trim() !== "")) &&
  Number.isFinite(Number(value)) &&
  Number(value) >= 0
    ? Number(value)
    : null;
export const integer = (value: unknown): number | null => {
  const n = num(value);
  return n !== null && Number.isSafeInteger(n) ? n : null;
};
export function iso(value: unknown): string | null {
  if (
    typeof value !== "string" ||
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(value)
  )
    return null;
  // Providers label these GMT even when omitting the zone; never use Worker locale.
  const s = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?$/.test(value)
    ? `${value}Z`
    : value;
  const t = Date.parse(s);
  return Number.isFinite(t) ? new Date(t).toISOString() : null;
}
export function legalBalls(overs: unknown, format = "T20"): number | null {
  if (overs === null || overs === undefined || /HUNDRED|100/i.test(format))
    return null;
  const s = str(overs);
  if (!/^\d{1,4}(?:\.[0-5])?$/.test(s)) return null;
  const [o, b = "0"] = s.split(".");
  return Number(o) * 6 + Number(b);
}
export function format(value: unknown): string {
  const s = str(value).toUpperCase();
  if (s === "T20I") return "T20";
  if (s === "TEST/5DAY" || s === "TEST") return "TEST";
  return s || "unknown";
}
export function gender(value: unknown): string {
  const s = str(value).toLowerCase();
  return ["m", "male", "men"].includes(s)
    ? "male"
    : ["f", "female", "women"].includes(s)
      ? "female"
      : s === "mixed"
        ? "mixed"
        : "unknown";
}
export function revision(value: unknown): string {
  // Non-security content revision. Clock-independent, bounded and deterministic.
  const s = JSON.stringify(value);
  let a = 2166136261,
    b = 0x9e3779b9;
  for (let i = 0; i < s.length; i++) {
    a = Math.imul(a ^ s.charCodeAt(i), 16777619);
    b = Math.imul(b ^ s.charCodeAt(i), 2246822519);
  }
  return `r-${(a >>> 0).toString(16)}${(b >>> 0).toString(16)}`;
}
export function unavailable<T>(source: string, reason: string): Part<T> {
  return {
    status: "unavailable",
    source,
    observedAt: null,
    fetchedAt: null,
    reason,
    data: null,
  };
}
export function part<T>(
  source: string,
  data: T,
  observedAt: string | null,
  fetchedAt: string,
): Part<T> {
  return {
    status: "available",
    source,
    observedAt,
    fetchedAt,
    reason: null,
    data,
  };
}
export function refreshPart<T>(
  p: Part<T>,
  now: number,
  staleSeconds: number,
): Part<T> {
  if (!p.data || p.status === "unavailable") return p;
  const clock = p.observedAt ?? p.fetchedAt;
  const stale = !clock || now - Date.parse(clock) > staleSeconds * 1000;
  const status: Availability = stale ? "stale" : p.status;
  return {
    ...p,
    status,
    reason: stale
      ? (p.reason ?? "The last available source snapshot is stale.")
      : p.reason,
  };
}
export function latestTime(...values: unknown[]): string | null {
  const dates = values.map(iso).filter((v): v is string => v !== null);
  return dates.length ? dates.sort().at(-1)! : null;
}
export function baseDetail(
  match: MatchSummary,
  refreshAfterSeconds = 60,
  staleAfterSeconds = 180,
): MatchDetailSnapshot {
  return {
    schemaVersion: 1,
    status: "partial",
    message: null,
    source: match.source,
    generatedAt: match.fetchedAt,
    refreshAfterSeconds,
    staleAfterSeconds,
    match,
    scorecard: unavailable(
      match.source.name,
      "A detailed scorecard is not supplied for this match.",
    ),
    commentary: unavailable(
      match.source.name,
      "Delivery coverage is not supplied for this match.",
    ),
    model: unavailable(
      "Playoff Pulse",
      "The match-win model has not been released for this state.",
    ),
    markets: unavailable(
      SOURCES.odds.name,
      "Bookmaker access and redisplay rights are not configured.",
    ),
  };
}
export function validPublicId(id: string): boolean {
  return /^(?:cd-[a-zA-Z0-9-]{1,80}|sm-\d{1,15}|ss-\d{10,13}-[a-z0-9-]{1,160})$/.test(
    id,
  );
}
