import { arr, iso, num, obj, part, SOURCES, str, unavailable } from "../domain";
import type { Bookmaker, MatchSummary, Part } from "../domain";

export interface MarketScope {
  sportKey: string;
  competitionIds: string[];
  format: string;
  gender: string;
}
export interface OddsEvent {
  id: string;
  sport_key: string;
  commence_time: string;
  home_team: string;
  away_team: string;
  bookmakers?: unknown[];
}
export function normalizeOdds(
  input: unknown,
  fetchedAt: string,
): Part<Bookmaker[]> {
  const event = obj(input),
    books: Bookmaker[] = arr(event.bookmakers).flatMap((value) => {
      const b = obj(value);
      if (!str(b.key) || !str(b.title)) return [];
      const markets = arr(b.markets).flatMap((value) => {
        const m = obj(value);
        if (!["h2h", "h2h_lay"].includes(str(m.key))) return [];
        const outcomes = arr(m.outcomes).flatMap((value) => {
          const o = obj(value),
            price = num(o.price);
          return price !== null && price > 1 && str(o.name)
            ? [{ name: str(o.name), price }]
            : [];
        });
        if (outcomes.length < 2) return [];
        // V4 does not guarantee a suspension indicator or cricket settlement rules.
        return [
          {
            key: str(m.key),
            name: m.key === "h2h_lay" ? "Match winner (lay)" : "Match winner",
            state: "unknown" as const,
            updatedAt: iso(m.last_update) ?? iso(b.last_update),
            settlement: null,
            outcomes,
          },
        ];
      });
      return markets.length
        ? [
            {
              key: str(b.key),
              title: str(b.title),
              updatedAt: iso(b.last_update),
              markets,
            },
          ]
        : [];
    });
  if (!books.length)
    return unavailable(
      SOURCES.odds.name,
      "No complete bookmaker match-winner quotes were supplied.",
    );
  // Conservative aggregate clock: an older returned market remains visibly old.
  const clocks = books
    .flatMap((b) => b.markets.map((m) => m.updatedAt))
    .filter((v): v is string => v !== null)
    .sort();
  return part(SOURCES.odds.name, books, clocks[0] ?? null, fetchedAt);
}
const identity = (s: string) =>
  s
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
export function matchMarketEvent(
  match: MatchSummary,
  events: unknown[],
  scope: MarketScope,
): string | null {
  if (
    !scope.competitionIds.includes(match.competition.id) ||
    match.format !== scope.format ||
    match.gender === "unknown" ||
    match.gender !== scope.gender ||
    !match.startTime ||
    match.teams.length !== 2
  )
    return null;
  const teams = match.teams.map((t) => identity(t.name)).sort();
  if (teams.some((t) => !t)) return null;
  const found = events
    .map(obj)
    .filter(
      (e) =>
        str(e.sport_key) === scope.sportKey &&
        str(e.id) &&
        iso(e.commence_time) &&
        Math.abs(
          Date.parse(str(e.commence_time)) - Date.parse(match.startTime!),
        ) <=
          5 * 60 * 1000 &&
        [identity(str(e.home_team)), identity(str(e.away_team))]
          .sort()
          .every((name, i) => name === teams[i]),
    );
  return found.length === 1 ? str(found[0].id) : null;
}
