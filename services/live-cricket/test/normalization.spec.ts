import { describe, expect, it } from "vitest";
import {
  cricketDataMatch,
  cricketDataCard,
} from "../src/providers/cricketdata";
import {
  sportmonksMatch,
  sportmonksCard,
  sportmonksDeliveries,
} from "../src/providers/sportmonks";
import { normalizeOdds, matchMarketEvent } from "../src/providers/odds";
import { legalBalls, refreshPart, revision } from "../src/domain";

const now = "2026-10-23T12:00:00.000Z";
export const cd = {
  id: "a1234567-1234-1234-1234-123456789012",
  name: "A vs B",
  series_id: "series-a",
  teams: ["A", "B"],
  matchType: "t20",
  status: "A batting",
  matchStarted: true,
  matchEnded: false,
  dateTimeGMT: "2026-10-23T11:00:00",
  score: [{ r: 100, w: 3, o: 17.5, inning: "A Inning 1" }],
  fantasyEnabled: true,
};

describe("normalization preserves cricket semantics", () => {
  it("counts legal balls, never decimal overs or impossible over fractions", () => {
    expect(legalBalls(17.5)).toBe(107);
    expect(legalBalls("0.0")).toBe(0);
    expect(legalBalls("17.6")).toBeNull();
    expect(legalBalls(null)).toBeNull();
    expect(legalBalls("17.5", "HUNDRED")).toBeNull();
  });
  it("does not invent a source observation timestamp or complete details", () => {
    const m = cricketDataMatch(cd, now);
    expect(m.state).toBe("live");
    expect(m.observedAt).toBeNull();
    expect(m.fetchedAt).toBe(now);
    expect(m.scores[0].legalBalls).toBe(107);
    expect(m.capabilities.commentary).toBe(false);
    expect(
      cricketDataMatch(
        {
          ...cd,
          matchStarted: undefined,
          matchEnded: undefined,
          status: "",
          score: [],
        },
        now,
      ).state,
    ).toBe("unknown");
  });
  it("keeps revised lower scores and changes revision without using fetched time", () => {
    const first = cricketDataMatch(cd, now);
    const unchanged = cricketDataMatch(cd, "2026-10-23T12:01:00Z");
    const corrected = cricketDataMatch(
      { ...cd, score: [{ r: 99, w: 3, o: 17.5, inning: "A Inning 1" }] },
      now,
    );
    expect(first.revision).toBe(unchanged.revision);
    expect(corrected.revision).not.toBe(first.revision);
    expect(corrected.scores[0].runs).toBe(99);
  });
  it("normalizes CricketData scorecards, leaving absent data null", () => {
    const card = cricketDataCard(
      {
        ...cd,
        scorecard: [
          {
            inning: "A Inning 1",
            totals: { R: 100, O: 17.5, W: 3 },
            batting: [
              {
                batsman: { id: "p1", name: "P" },
                r: 25,
                b: 20,
                "4s": 2,
                "6s": 1,
                sr: 125,
                "dismissal-text": "not out",
              },
            ],
            bowling: [],
            extras: { r: 4, w: 2, b: 2 },
          },
        ],
      },
      now,
    );
    expect(card.data?.[0].batting[0].runs).toBe(25);
    expect(card.data?.[0].legalBalls).toBe(107);
    expect(card.data?.[0].partnerships).toEqual([]);
    expect(cricketDataCard(cd, now).status).toBe("unavailable");
  });
  it("keeps Test innings and ordered illegal deliveries from Sportmonks", () => {
    const fixture = {
      id: 23,
      starting_at: "2026-10-20T11:00:00Z",
      type: "Test",
      status: "Stump Day 3",
      localteam: { id: 1, name: "A", code: "A" },
      visitorteam: { id: 2, name: "B", code: "B" },
      league: { id: 3, name: "Test" },
      runs: [
        { id: 1, inning: 1, team_id: 1, score: 300, wickets: 10, overs: 90 },
        { id: 2, inning: 2, team_id: 2, score: 250, wickets: 10, overs: 80 },
        { id: 3, inning: 3, team_id: 1, score: 100, wickets: 2, overs: 30 },
      ],
      batting: [
        {
          id: 8,
          scoreboard: "S3",
          team_id: 1,
          player_id: 9,
          batsman: { id: 9, fullname: "P" },
          score: 30,
          ball: 50,
        },
      ],
      bowling: [],
      balls: [
        {
          id: 30,
          ball: 0.1,
          scoreboard: "S1",
          score: { name: "Wide", runs: 1, ball: false },
          updated_at: "2026-10-20T11:01:00Z",
        },
        {
          id: 31,
          ball: 0.1,
          scoreboard: "S1",
          score: { name: "No run", runs: 0, ball: true },
          updated_at: "2026-10-20T11:02:00Z",
        },
      ],
    };
    expect(sportmonksMatch(fixture, now).state).toBe("stumps");
    expect(sportmonksCard(fixture, now).data?.length).toBe(3);
    const log = sportmonksDeliveries(fixture, now);
    expect(log.data?.map((d) => d.id)).toEqual(["30", "31"]);
    expect(log.data?.map((d) => d.sequence)).toEqual([0, 1]);
  });
  it("does not re-date old quote or commentary after successful refetch", () => {
    const p = {
      status: "available" as const,
      source: "book",
      observedAt: "2026-10-23T10:00:00Z",
      fetchedAt: now,
      reason: null,
      data: [1],
    };
    expect(refreshPart(p, Date.parse(now), 120).status).toBe("stale");
    expect(
      refreshPart({ ...p, observedAt: null }, Date.parse(now), 120).status,
    ).toBe("available");
    expect(
      refreshPart(
        { ...p, observedAt: null, fetchedAt: "2026-10-23T10:00:00Z" },
        Date.parse(now),
        120,
      ).status,
    ).toBe("stale");
  });
});

describe("bookmaker quotes and conservative joins", () => {
  const event = {
    id: "event1",
    sport_key: "cricket_test_match",
    commence_time: "2026-10-23T11:00:00Z",
    home_team: "A",
    away_team: "B",
    bookmakers: [
      {
        key: "book",
        title: "Named Book",
        last_update: "2026-10-23T11:59:00Z",
        markets: [
          {
            key: "h2h",
            last_update: "2026-10-23T11:58:00Z",
            outcomes: [
              { name: "A", price: 1.8 },
              { name: "B", price: 2.2 },
              { name: "Draw", price: 4 },
            ],
          },
        ],
      },
    ],
  };
  it("preserves named books, decimal prices, clocks and unknown settlement/state", () => {
    const p = normalizeOdds(event, now);
    expect(p.data?.[0].title).toBe("Named Book");
    expect(p.data?.[0].markets[0]).toMatchObject({
      state: "unknown",
      settlement: null,
      updatedAt: "2026-10-23T11:58:00.000Z",
    });
    expect(p.observedAt).toBe("2026-10-23T11:58:00.000Z");
    expect(p.data?.[0].markets[0].outcomes[0].price).toBe(1.8);
  });
  it("requires an explicit competition, format, gender scope and unique exact event", () => {
    const match = {
      ...cricketDataMatch(cd, now),
      format: "TEST",
      gender: "male",
    };
    const scope = {
      sportKey: "cricket_test_match",
      competitionIds: ["series-a"],
      format: "TEST",
      gender: "male",
    };
    expect(matchMarketEvent(match, [event], scope)).toBe("event1");
    expect(
      matchMarketEvent({ ...match, gender: "unknown" }, [event], scope),
    ).toBeNull();
    expect(
      matchMarketEvent(
        { ...match, competition: { id: "other", name: "Other" } },
        [event],
        scope,
      ),
    ).toBeNull();
    expect(
      matchMarketEvent(match, [event, { ...event, id: "event2" }], scope),
    ).toBeNull();
    expect(
      matchMarketEvent(
        match,
        [{ ...event, commence_time: "2026-10-24T11:00:00Z" }],
        scope,
      ),
    ).toBeNull();
    expect(revision({ a: 1 })).toBe(revision({ a: 1 }));
  });
});
