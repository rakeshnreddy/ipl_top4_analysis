import { describe, expect, it, vi } from "vitest";
import { Collector, MemoryStore, defaultConfig } from "../src/collector";

const clock = Date.parse("2026-10-23T12:00:00Z");
const match = {
  id: "a1234567-1234-1234-1234-123456789012",
  name: "A vs B",
  series_id: "series-a",
  teams: ["A", "B"],
  matchType: "t20",
  status: "In progress",
  matchStarted: true,
  matchEnded: false,
  score: [{ r: 100, w: 3, o: 17.5, inning: "A Inning 1" }],
  fantasyEnabled: false,
};
const cdPayload = (rows: unknown[], total = rows.length) => ({
  status: "success",
  data: rows,
  info: { totalRows: total, hitsToday: 1, hitsLimit: 100 },
});
const keyed = {
  ...defaultConfig(),
  scoreProvider: "cricketdata" as const,
  cricketDataKey: "test-key-not-a-secret",
  cricketDataAccess: true,
  cricketDataRedisplay: true,
  discoverySeconds: 60,
  detailSeconds: 60,
};

describe("shared collector and quotas", () => {
  it("makes zero upstream requests when keyed access/redisplay is disabled", async () => {
    const fetcher = vi.fn();
    const c = new Collector(
      new MemoryStore(),
      { ...keyed, cricketDataRedisplay: false },
      fetcher,
      () => clock,
    );
    expect((await c.list()).status).toBe("unavailable");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("coalesces concurrent discovery and reuses persistent state after restart", async () => {
    const store = new MemoryStore();
    const fetcher = vi.fn(async () => Response.json(cdPayload([match])));
    const c = new Collector(store, keyed, fetcher, () => clock);
    const results = await Promise.all(
      Array.from({ length: 20 }, () => c.list()),
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(results.every((r) => r.matches.length === 1)).toBe(true);
    const reloaded = new Collector(store, keyed, fetcher, () => clock + 1000);
    expect((await reloaded.list()).matches[0].id).toBe(`cd-${match.id}`);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("keeps the last good snapshot and marks outage stale without changing its clock", async () => {
    let now = clock;
    const fetcher = vi.fn(async () => Response.json(cdPayload([match])));
    const c = new Collector(new MemoryStore(), keyed, fetcher, () => now);
    const good = await c.list();
    now += 1000 * 600;
    fetcher.mockRejectedValueOnce(
      new Error("secret upstream URL should never escape"),
    );
    const bad = await c.list();
    expect(bad.matches[0].scores[0].runs).toBe(100);
    expect(bad.matches[0].fetchedAt).toBe(good.matches[0].fetchedAt);
    expect(bad.status).toBe("partial");
    expect(JSON.stringify(bad)).not.toContain("secret upstream");
  });
  it("never queries a user-supplied unknown match ID and rejects malformed IDs", async () => {
    const f = vi.fn(async () => Response.json(cdPayload([match])));
    const c = new Collector(new MemoryStore(), keyed, f, () => clock);
    await expect(c.detail("../secret")).rejects.toThrow("invalid_match_id");
    await expect(c.detail("sm-99999")).rejects.toThrow("match_not_found");
    expect(f).not.toHaveBeenCalled();
  });
  it("bounds pagination, marks incomplete coverage and counts every page against quota", async () => {
    const fetcher = vi.fn(async () =>
      Response.json(
        cdPayload(
          Array.from({ length: 25 }, (_, i) => ({
            ...match,
            id: `match-${i}`,
          })),
          1000,
        ),
      ),
    );
    const c = new Collector(
      new MemoryStore(),
      { ...keyed, maxPages: 2, cricketDataDaily: 2 },
      fetcher,
      () => clock,
    );
    const l = await c.list();
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(l.status).toBe("partial");
    await c.detail("cd-match-0");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("reads Sportmonks current meta.current_page/last_page pagination without following upstream links", async () => {
    const f = vi.fn(async (input: string | URL) => {
      const u = new URL(input);
      const page = Number(u.searchParams.get("page"));
      const fixture = {
        id: u.pathname.endsWith("livescores") ? 1 : page + 1,
        localteam: { id: 1, name: "A" },
        visitorteam: { id: 2, name: "B" },
        status: "1st Innings",
        type: "T20",
        league: { id: 1, name: "League" },
      };
      return Response.json({
        data: [fixture],
        meta: { current_page: page, last_page: 3 },
        links: { next: "https://evil.test/should-not-be-followed" },
      });
    });
    const c = new Collector(
      new MemoryStore(),
      {
        ...defaultConfig(),
        scoreProvider: "sportmonks",
        sportmonksAccess: true,
        sportmonksRedisplay: true,
        sportmonksKey: "placeholder",
        maxPages: 3,
      },
      f,
      () => clock,
    );
    const list = await c.list();
    expect(f).toHaveBeenCalledTimes(3);
    expect(list.status).toBe("partial");
    expect(
      f.mock.calls.every(
        ([u]) => new URL(u).hostname === "cricket.sportmonks.com",
      ),
    ).toBe(true);
  });
  it("reserves budget before I/O and persists it across concurrent requests/restarts", async () => {
    const store = new MemoryStore(),
      f = vi.fn(async () => Response.json(cdPayload([match])));
    const config = { ...keyed, cricketDataDaily: 1 };
    const c = new Collector(store, config, f, () => clock);
    await c.list();
    await c.detail(`cd-${match.id}`);
    const restart = new Collector(store, config, f, () => clock + 61000);
    await restart.list();
    expect(f).toHaveBeenCalledTimes(1);
  });
  it("rejects oversized upstream data before accepting a snapshot", async () => {
    const f = vi.fn(
      async () =>
        new Response("x".repeat(200), {
          headers: { "content-length": "3000000" },
        }),
    );
    const c = new Collector(new MemoryStore(), keyed, f, () => clock);
    expect((await c.list()).status).toBe("unavailable");
  });
  it("accepts a correction but rejects an older source observation", async () => {
    let now = clock;
    let data = { ...match, updated_at: "2026-10-23T11:59:00Z" };
    const f = vi.fn(async () => Response.json(cdPayload([data])));
    const c = new Collector(new MemoryStore(), keyed, f, () => now);
    const first = await c.list();
    now += 61000;
    data = {
      ...data,
      updated_at: "2026-10-23T12:00:00Z",
      score: [{ r: 99, w: 3, o: 17.5, inning: "A Inning 1" }],
    };
    expect((await c.list()).matches[0].scores[0].runs).toBe(99);
    now += 61000;
    data = { ...match, updated_at: "2026-10-23T11:58:00Z" };
    const older = await c.list();
    expect(older.matches[0].scores[0].runs).toBe(99);
    expect(older.matches[0].revision).not.toBe(first.matches[0].revision);
  });
  it("rejects a wrong scorecard identity while preserving useful verified scores", async () => {
    const f = vi.fn(async (input: string | URL) => {
      const path = new URL(input).pathname;
      if (path.endsWith("currentMatches"))
        return Response.json(cdPayload([match]));
      if (path.endsWith("match_info"))
        return Response.json({
          status: "success",
          data: { ...match, fantasyEnabled: true },
        });
      return Response.json({
        status: "success",
        data: {
          ...match,
          id: "another-match",
          teams: ["Other", "Teams"],
          scorecard: [
            {
              inning: "Other Inning 1",
              totals: { R: 999, O: 20, W: 0 },
              batting: [],
              bowling: [],
            },
          ],
        },
      });
    });
    const c = new Collector(
      new MemoryStore(),
      { ...keyed, cricketDataFantasy: true },
      f,
      () => clock,
    );
    await c.list();
    const detail = await c.detail(`cd-${match.id}`);
    expect(detail.match.scores[0].runs).toBe(100);
    expect(detail.scorecard.status).toBe("unavailable");
    expect(JSON.stringify(detail)).not.toContain("999");
  });
  it("coalesces a cold deep link with concurrent discovery before querying detail", async () => {
    const f = vi.fn(async (input: string | URL) =>
      new URL(input).pathname.endsWith("currentMatches")
        ? Response.json(cdPayload([match]))
        : Response.json({ status: "success", data: match }),
    );
    const c = new Collector(new MemoryStore(), keyed, f, () => clock);
    const [detail, list] = await Promise.all([
      c.detail(`cd-${match.id}`),
      c.list(),
    ]);
    expect(detail.match.id).toBe(list.matches[0].id);
    expect(f).toHaveBeenCalledTimes(2);
  });
  it("retains a last good scorecard with its own old clock when optional card refresh fails", async () => {
    let now = clock,
      broken = false;
    const f = vi.fn(async (input: string | URL) => {
      const path = new URL(input).pathname;
      if (path.endsWith("currentMatches"))
        return Response.json(cdPayload([match]));
      if (path.endsWith("match_info"))
        return Response.json({
          status: "success",
          data: { ...match, fantasyEnabled: true },
        });
      if (broken) throw new Error("card_source_failed");
      return Response.json({
        status: "success",
        data: {
          ...match,
          scorecard: [
            {
              inning: "A Inning 1",
              totals: { R: 100, O: 17.5, W: 3 },
              batting: [{ batsman: { id: "p", name: "Player" }, r: 30 }],
              bowling: [],
            },
          ],
        },
      });
    });
    const c = new Collector(
      new MemoryStore(),
      { ...keyed, cricketDataFantasy: true },
      f,
      () => now,
    );
    await c.list();
    const good = await c.detail(`cd-${match.id}`);
    broken = true;
    now += 61000;
    const next = await c.detail(`cd-${match.id}`);
    expect(next.scorecard.data).toEqual(good.scorecard.data);
    expect(next.scorecard.fetchedAt).toBe(good.scorecard.fetchedAt);
    expect(next.scorecard.status).toBe("stale");
  });
  it("keeps stale bookmaker prices independent from fresh scores", async () => {
    const data = {
      ...match,
      gender: "male",
      dateTimeGMT: "2026-10-23T11:00:00Z",
    };
    const f = vi.fn(async (input: string | URL) => {
      const u = new URL(input);
      if (u.hostname === "api.the-odds-api.com")
        return Response.json([
          {
            id: "event-one",
            sport_key: "cricket_ipl",
            commence_time: "2026-10-23T11:00:00Z",
            home_team: "A",
            away_team: "B",
            bookmakers: [
              {
                key: "book",
                title: "Book",
                last_update: "2026-10-23T10:00:00Z",
                markets: [
                  {
                    key: "h2h",
                    outcomes: [
                      { name: "A", price: 1.8 },
                      { name: "B", price: 2.2 },
                    ],
                  },
                ],
              },
            ],
          },
        ]);
      return u.pathname.endsWith("currentMatches")
        ? Response.json(cdPayload([data]))
        : Response.json({ status: "success", data });
    });
    const c = new Collector(
      new MemoryStore(),
      {
        ...keyed,
        oddsKey: "placeholder",
        oddsAccess: true,
        oddsRedisplay: true,
        marketScopes: [
          {
            sportKey: "cricket_ipl",
            competitionIds: ["series-a"],
            format: "T20",
            gender: "male",
          },
        ],
      },
      f,
      () => clock,
    );
    const d = await c.detail(`cd-${match.id}`);
    expect(d.match.fetchedAt).toBe(new Date(clock).toISOString());
    expect(d.markets.status).toBe("stale");
    expect(d.markets.observedAt).toBe("2026-10-23T10:00:00.000Z");
    expect(d.model.status).toBe("unavailable");
  });
  it("does not restore rolling daily credits at midnight or a partial boundary bucket", async () => {
    const store = new MemoryStore();
    let now = Date.parse("2026-10-22T23:59:00Z");
    const f = vi.fn(async () => Response.json(cdPayload([match])));
    const c = new Collector(
      store,
      { ...keyed, cricketDataDaily: 1 },
      f,
      () => now,
    );
    await c.list();
    now = Date.parse("2026-10-23T00:01:00Z");
    await c.list();
    expect(f).toHaveBeenCalledTimes(1);
    now = Date.parse("2026-10-23T23:58:00Z");
    await c.list();
    expect(f).toHaveBeenCalledTimes(1);
    now = Date.parse("2026-10-24T00:01:00Z");
    await c.list();
    expect(f).toHaveBeenCalledTimes(2);
  });
});
