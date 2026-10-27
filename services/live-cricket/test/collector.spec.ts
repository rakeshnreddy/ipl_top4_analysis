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
type Resource = "list" | "detail";
function heldResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}
function sourcePayload(
  provider: "sportscore" | "cricketdata",
  resource: Resource,
  updated: string | null,
  runs: number,
) {
  if (provider === "sportscore") {
    const row = {
      home: "Synthetic A",
      away: "Synthetic B",
      competition: "Synthetic Men T20",
      time: "2026-10-23T11:00:00Z",
      url: "/cricket/match/synthetic-a-vs-synthetic-b/",
      status: "live",
      status_text: "1st innings",
      home_score: `${runs}/3 (17.5)`,
      away_score: null,
    };
    return resource === "list"
      ? { sport: "cricket", count: 1, matches: [row], updated }
      : { sport: "cricket", match: row, updated };
  }
  const row = {
    ...match,
    updated_at: updated,
    score: [{ ...match.score[0], r: runs }],
  };
  return resource === "list"
    ? cdPayload([row])
    : { status: "success", data: row };
}
const interleavings = (["sportscore", "cricketdata"] as const).flatMap(
  (provider) =>
    (["list", "detail"] as const).flatMap((newer) =>
      ([true, false] as const).map((newerFirst) => ({
        provider,
        newer,
        newerFirst,
      })),
    ),
);

describe("shared collector and quotas", () => {
  it("does not promote placeholder-only fixture coverage to available scores", async () => {
    const payload = sourcePayload("sportscore", "list", new Date(clock).toISOString(), 100) as { matches: Record<string, unknown>[] };
    payload.matches[0].home_score = "-";
    payload.matches[0].away_score = "—";
    const collector = new Collector(new MemoryStore(), defaultConfig(), async () => Response.json(payload), () => clock);
    const list = await collector.list();
    expect(list.matches[0].scores).toEqual([]);
    expect(list.coverage[0].scores).toBe(false);
  });
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
  it.each(["list", "detail"] as const)(
    "rejects an older SportScore %s publication but accepts an equal-time score correction",
    async (kind) => {
      let now = clock;
      const published = "2026-10-23T12:00:00Z";
      let updated = published;
      let score = "100/3 (17.5)";
      const sourceMatch = () => ({
        home: "Synthetic A",
        away: "Synthetic B",
        competition: "Synthetic Men T20",
        time: "2026-10-23T11:00:00Z",
        url: "/cricket/match/synthetic-a-vs-synthetic-b/",
        status: "live",
        status_text: "1st innings",
        home_score: score,
        away_score: null,
      });
      const fetcher = vi.fn(async (input: string | URL) =>
        Response.json(
          new URL(input).pathname.endsWith("/matches/")
            ? { sport: "cricket", count: 1, matches: [sourceMatch()], updated }
            : { sport: "cricket", match: sourceMatch(), updated },
        ),
      );
      const c = new Collector(
        new MemoryStore(),
        defaultConfig(),
        fetcher,
        () => now,
      );
      const list = await c.list();
      const id = list.matches[0].id;
      const first = kind === "list" ? list : await c.detail(id);
      const read = () => (kind === "list" ? c.list() : c.detail(id));
      const matchOf = (snapshot: Awaited<ReturnType<typeof read>>) =>
        "matches" in snapshot ? snapshot.matches[0] : snapshot.match;
      now += 61000;
      updated = "2026-10-23T11:59:00Z";
      score = "90/3 (17.5)";
      const older = await read();
      expect(matchOf(older).scores[0].runs).toBe(100);
      expect(older.generatedAt).toBe(first.generatedAt);
      expect(matchOf(older).fetchedAt).toBe(matchOf(first).fetchedAt);
      now += 61000;
      updated = published;
      score = "99/3 (17.5)";
      const correction = await read();
      expect(matchOf(correction).scores[0].runs).toBe(99);
      expect(correction.generatedAt).toBe(published);
    },
  );
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
  it.each(interleavings)(
    "reconciles overlapping $provider requests with newer $newer publication finishing first=$newerFirst",
    async ({ provider, newer, newerFirst }) => {
      let now = clock;
      let held = false;
      const pending = { list: heldResponse(), detail: heldResponse() };
      const initial = "2026-10-23T11:58:00Z";
      const oldTime = "2026-10-23T11:59:00Z";
      const newTime = "2026-10-23T12:00:00Z";
      const fetcher = vi.fn((input: string | URL) => {
        const path = new URL(input).pathname;
        const resource: Resource =
          path.endsWith("/matches/") || path.endsWith("currentMatches")
            ? "list"
            : "detail";
        return held
          ? pending[resource].promise
          : Promise.resolve(
              Response.json(sourcePayload(provider, resource, initial, 80)),
            );
      });
      const c = new Collector(
        new MemoryStore(),
        provider === "sportscore" ? defaultConfig() : keyed,
        fetcher,
        () => now,
      );
      const seed = await c.list();
      const id = seed.matches[0].id;
      await c.detail(id);
      held = true;
      now += 61000;
      const listAt = new Date(now).toISOString();
      const listPromise = c.list();
      now += 1000;
      const detailAt = new Date(now).toISOString();
      const detailPromise = c.detail(id);
      const promises = { list: listPromise, detail: detailPromise };
      const older: Resource = newer === "list" ? "detail" : "list";
      for (const resource of newerFirst ? [newer, older] : [older, newer]) {
        pending[resource].resolve(
          Response.json(
            sourcePayload(
              provider,
              resource,
              resource === newer ? newTime : oldTime,
              resource === newer ? 100 : 90,
            ),
          ),
        );
        await promises[resource];
      }
      const finalList = await c.list();
      const finalDetail = await c.detail(id);
      expect(finalList.matches[0].scores[0].runs).toBe(100);
      expect(finalDetail.match.scores[0].runs).toBe(100);
      expect(finalList.matches[0].revision).toBe(finalDetail.match.revision);
      const originalFetch = newer === "list" ? listAt : detailAt;
      expect(finalList.matches[0].fetchedAt).toBe(originalFetch);
      expect(finalDetail.match.fetchedAt).toBe(originalFetch);
      expect(finalDetail.match.observedAt).toBe(
        provider === "cricketdata" ? newTime.replace("Z", ".000Z") : null,
      );
      // Envelopes describe their own resource. Retaining a score cannot re-date
      // an older detail publication or claim its time is a ball observation.
      expect(finalList.generatedAt).toBe(
        provider === "sportscore"
          ? newer === "list"
            ? newTime
            : oldTime
          : listAt,
      );
      expect(finalDetail.generatedAt).toBe(
        provider === "sportscore"
          ? newer === "detail"
            ? newTime
            : oldTime
          : detailAt,
      );
    },
  );
  it.each(["2026-10-23T12:00:00Z", null])(
    "retains SportScore's incumbent for conflicting cross-resource publication %s across restart",
    async (detailTime) => {
      const store = new MemoryStore();
      const published = "2026-10-23T12:00:00Z";
      const fetcher = vi.fn(async (input: string | URL) => {
        const list = new URL(input).pathname.endsWith("/matches/");
        return Response.json(
          sourcePayload(
            "sportscore",
            list ? "list" : "detail",
            list ? published : detailTime,
            list ? 100 : 99,
          ),
        );
      });
      const first = new Collector(store, defaultConfig(), fetcher, () => clock);
      const list = await first.list();
      const id = list.matches[0].id;
      const detail = await first.detail(id);
      expect(detail.match.scores[0].runs).toBe(100);
      expect(detail.match.observedAt).toBeNull();
      expect(detail.generatedAt).toBe(detailTime);
      const restarted = new Collector(
        store,
        defaultConfig(),
        fetcher,
        () => clock + 1000,
      );
      expect((await restarted.detail(id)).match.scores[0].runs).toBe(100);
      expect(fetcher).toHaveBeenCalledTimes(2);
    },
  );
  it("retains a keyed provider's incumbent on an equal-observation cross-resource conflict", async () => {
    const published = "2026-10-23T12:00:00Z";
    const fetcher = vi.fn(async (input: string | URL) => {
      const list = new URL(input).pathname.endsWith("currentMatches");
      return Response.json(
        sourcePayload(
          "cricketdata",
          list ? "list" : "detail",
          published,
          list ? 100 : 99,
        ),
      );
    });
    const c = new Collector(new MemoryStore(), keyed, fetcher, () => clock);
    const list = await c.list();
    const detail = await c.detail(list.matches[0].id);
    expect(detail.match.scores[0].runs).toBe(100);
    expect(detail.match.fetchedAt).toBe(list.matches[0].fetchedAt);
  });
  it("trims score provenance with the registry and does not resurrect an evicted match after late detail I/O", async () => {
    let now = clock;
    let replaced = false;
    const pending = heldResponse();
    const original = {
      home: "Synthetic A",
      away: "Synthetic B",
      competition: "Synthetic Men T20",
      time: "2026-10-23T11:00:00Z",
      url: "/cricket/match/synthetic-a-vs-synthetic-b/",
      status: "completed",
      status_text: "Final",
      home_score: "100/3",
      away_score: null,
    };
    const replacement = {
      ...original,
      home: "Synthetic C",
      away: "Synthetic D",
      url: "/cricket/match/synthetic-c-vs-synthetic-d/",
    };
    const fetcher = vi.fn((input: string | URL) =>
      new URL(input).pathname.endsWith("/matches/")
        ? Promise.resolve(
            Response.json({
              sport: "cricket",
              count: 1,
              matches: [replaced ? replacement : original],
              updated: new Date(now).toISOString(),
            }),
          )
        : pending.promise,
    );
    const store = new MemoryStore();
    const c = new Collector(
      store,
      { ...defaultConfig(), maxMatches: 1 },
      fetcher,
      () => now,
    );
    const first = await c.list();
    const oldId = first.matches[0].id;
    expect(store.get(`sportscore:score:${oldId}`)).toBeDefined();
    const late = c.detail(oldId);
    const rejection = expect(late).rejects.toThrow("match_not_found");
    replaced = true;
    now += 61000;
    const next = await c.list();
    expect(next.matches).toHaveLength(1);
    pending.resolve(
      Response.json({
        sport: "cricket",
        match: original,
        updated: "2026-10-23T12:00:00Z",
      }),
    );
    await rejection;
    expect(store.get(`sportscore:score:${oldId}`)).toBeUndefined();
    expect(store.get(`sportscore:detail:${oldId}`)).toBeUndefined();
    expect(store.get(`job:sportscore:detail:${oldId}`)).toBeUndefined();
    expect(store.get(`sportscore:score:${next.matches[0].id}`)).toBeDefined();
  });
  it("preserves old detail/card clocks when a newer discovered score wins during detail I/O", async () => {
    let now = clock;
    let held = false;
    const pending = { list: heldResponse(), detail: heldResponse() };
    const initial = "2026-10-23T11:58:00Z",
      oldTime = "2026-10-23T11:59:00Z",
      newTime = "2026-10-23T12:00:00Z";
    const info = (at: string, runs: number) => ({
      ...match,
      updated_at: at,
      fantasyEnabled: true,
      score: [{ ...match.score[0], r: runs }],
    });
    const fetcher = vi.fn((input: string | URL) => {
      const path = new URL(input).pathname;
      if (path.endsWith("match_scorecard"))
        return Promise.resolve(
          Response.json({
            status: "success",
            data: {
              ...info(held ? oldTime : initial, held ? 90 : 80),
              scorecard: [
                {
                  inning: "A Inning 1",
                  totals: { R: held ? 90 : 80, W: 3, O: 17.5 },
                  batting: [
                    { batsman: { id: "p", name: "Synthetic Player" }, r: 20 },
                  ],
                  bowling: [],
                },
              ],
            },
          }),
        );
      const resource: Resource = path.endsWith("currentMatches")
        ? "list"
        : "detail";
      return held
        ? pending[resource].promise
        : Promise.resolve(
            Response.json(
              resource === "list"
                ? cdPayload([info(initial, 80)])
                : { status: "success", data: info(initial, 80) },
            ),
          );
    });
    const c = new Collector(
      new MemoryStore(),
      { ...keyed, cricketDataFantasy: true },
      fetcher,
      () => now,
    );
    const first = await c.list();
    const id = first.matches[0].id;
    await c.detail(id);
    held = true;
    now += 61000;
    const listPromise = c.list();
    now += 1000;
    const detailAt = new Date(now).toISOString();
    const detailPromise = c.detail(id);
    pending.list.resolve(Response.json(cdPayload([info(newTime, 100)])));
    await listPromise;
    pending.detail.resolve(
      Response.json({ status: "success", data: info(oldTime, 90) }),
    );
    const detail = await detailPromise;
    expect(detail.match.scores[0].runs).toBe(100);
    expect(detail.match.observedAt).toBe(newTime.replace("Z", ".000Z"));
    expect(detail.generatedAt).toBe(detailAt);
    expect(detail.scorecard.data?.[0].runs).toBe(90);
    expect(detail.scorecard.observedAt).toBe(oldTime.replace("Z", ".000Z"));
    expect(detail.scorecard.fetchedAt).toBe(detailAt);
    expect(detail.match.capabilities.scorecard).toBe(true);
    expect(detail.model.status).toBe("unavailable");
    expect(detail.message).toMatch(/original source clocks/);
  });
});
