import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { setupNetwork } from "@msw/cloudflare";
import { http, HttpResponse } from "msw";
import { env, exports } from "cloudflare:workers";
import { evictDurableObject, runInDurableObject } from "cloudflare:test";
import { Collector, defaultConfig } from "../src/collector";
import { SqlStore } from "../src/index";

const network = setupNetwork();
const platformFetch = globalThis.fetch;
beforeAll(() => network.enable());
afterEach(() => {
  vi.unstubAllGlobals();
  network.resetHandlers();
});
afterAll(() => network.disable());

describe("Worker HTTP and Durable Object runtime", () => {
  it("does not call the native Worker fetch with a Collector receiver", async () => {
    vi.stubGlobal(
      "fetch",
      new Proxy(platformFetch, {
        apply(target, thisArg, args) {
          // Exercise the real platform brand check for a bad receiver. Intercept
          // correctly bound requests before network I/O, so this test is offline.
          if (thisArg !== undefined && thisArg !== globalThis)
            return Reflect.apply(target, thisArg, args);
          return Promise.resolve(
            Response.json({
              sport: "cricket",
              count: 0,
              matches: [],
              updated: "2026-10-24T08:00:00Z",
            }),
          );
        },
      }),
    );
    const stub = env.COLLECTOR.getByName("native-worker-fetch-binding");
    const list = await runInDurableObject(stub, async (_instance, state) =>
      new Collector(new SqlStore(state.storage.sql)).list(),
    );
    expect(list.status).toBe("ok");
  });
  it("uses the native Worker fetch receiver while collecting the free source", async () => {
    network.use(
      http.get("https://sportscore.com/api/widget/matches/", () =>
        HttpResponse.json({
          sport: "cricket",
          count: 1,
          updated: "2026-10-24T08:00:00Z",
          matches: [
            {
              home: "Team A",
              away: "Team B",
              home_score: "81/3",
              away_score: null,
              status: "live",
              status_text: "1st innings",
              time: "2026-10-24T07:00:00Z",
              competition: "Men T20",
              url: "/cricket/match/team-a-vs-team-b/",
            },
          ],
        }),
      ),
    );
    const stub = env.COLLECTOR.getByName("native-worker-fetch-receiver");
    const list = await runInDurableObject(stub, async (_instance, state) =>
      new Collector(new SqlStore(state.storage.sql)).list(),
    );
    expect(list.status).toBe("ok");
    expect(list.matches[0]?.scores[0]?.runs).toBe(81);
  });
  it("rejects an upstream redirect without forwarding the request to another host", async () => {
    let forwarded = false;
    network.use(
      http.get(
        "https://sportscore.com/api/widget/matches/",
        () =>
          new HttpResponse(null, {
            status: 302,
            headers: { Location: "https://different.test/data" },
          }),
      ),
      http.get("https://different.test/data", () => {
        forwarded = true;
        return HttpResponse.json({
          sport: "cricket",
          count: 0,
          matches: [],
          updated: "2026-10-24T08:00:00Z",
        });
      }),
    );
    const stub = env.COLLECTOR.getByName("native-worker-redirect-rejection");
    const list = await runInDurableObject(stub, async (_instance, state) =>
      new Collector(new SqlStore(state.storage.sql)).list(),
    );
    expect(list.status).toBe("unavailable");
    expect(forwarded).toBe(false);
  });
  it("starts without a configured paid provider or account key", async () => {
    const r = await exports.default.fetch("https://pulse.test/health");
    expect(r.status).toBe(200);
    expect(await r.json()).toMatchObject({
      status: "ok",
      provider: "none",
      providerConnectivity: "not_checked",
    });
  });
  it("uses actual Durable Object RPC and a persistent SQLite-backed namespace", async () => {
    const stub = env.COLLECTOR.getByName("no-upstream-runtime-test");
    const first = await stub.list(),
      second = await stub.list();
    expect(first.status).toBe("unavailable");
    expect(second).toEqual(first);
  });
  it("recovers actual collected snapshots and quota reservations after object eviction", async () => {
    const stub = env.COLLECTOR.getByName("sqlite-recovery-test");
    let calls = 0;
    const now = Date.parse("2026-10-23T12:00:00Z");
    const config = {
      ...defaultConfig(),
      scoreProvider: "cricketdata" as const,
      cricketDataAccess: true,
      cricketDataRedisplay: true,
      cricketDataKey: "test-placeholder",
      cricketDataDaily: 1,
      discoverySeconds: 60,
    };
    const fetcher = async () => {
      calls++;
      return Response.json({
        status: "success",
        info: { totalRows: 1 },
        data: [
          {
            id: "recovery-match",
            teams: ["A", "B"],
            matchType: "t20",
            matchStarted: true,
            status: "In progress",
            score: [{ r: 81, w: 3, o: 10, inning: "A Inning 1" }],
          },
        ],
      });
    };
    const first = await runInDurableObject(stub, async (_instance, state) =>
      new Collector(
        new SqlStore(state.storage.sql),
        config,
        fetcher,
        () => now,
      ).list(),
    );
    expect(first.matches[0].scores[0].runs).toBe(81);
    await evictDurableObject(stub);
    const restored = await runInDurableObject(stub, async (_instance, state) =>
      new Collector(
        new SqlStore(state.storage.sql),
        config,
        fetcher,
        () => now + 61000,
      ).list(),
    );
    expect(restored.matches).toEqual(first.matches);
    expect(calls).toBe(1);
  });
  it("returns the public unavailable contract rather than demo matches", async () => {
    const r = await exports.default.fetch("https://pulse.test/v1/matches");
    expect(r.status).toBe(200);
    expect(await r.json()).toMatchObject({
      schemaVersion: 1,
      status: "unavailable",
      matches: [],
    });
  });
  it("rejects methods, arbitrary parameters and malformed detail IDs", async () => {
    expect(
      (
        await exports.default.fetch("https://pulse.test/v1/matches", {
          method: "POST",
        })
      ).status,
    ).toBe(405);
    expect(
      (
        await exports.default.fetch(
          "https://pulse.test/v1/matches?upstream=https://evil.test",
        )
      ).status,
    ).toBe(400);
    expect(
      (await exports.default.fetch("https://pulse.test/v1/matches/invalid"))
        .status,
    ).toBe(400);
    expect(
      (await exports.default.fetch("https://pulse.test/v1/matches/sm-999999"))
        .status,
    ).toBe(404);
  });
  it("restricts CORS to the application origins and supports ETag/HEAD", async () => {
    const allowed = await exports.default.fetch(
      "https://pulse.test/v1/matches",
      { headers: { Origin: "https://ipl-playoff-pulse.pages.dev" } },
    );
    expect(allowed.headers.get("access-control-allow-origin")).toBe(
      "https://ipl-playoff-pulse.pages.dev",
    );
    const etag = allowed.headers.get("etag");
    expect(etag).toBeTruthy();
    expect(
      (
        await exports.default.fetch("https://pulse.test/v1/matches", {
          headers: { "If-None-Match": etag! },
        })
      ).status,
    ).toBe(304);
    const head = await exports.default.fetch("https://pulse.test/v1/matches", {
      method: "HEAD",
    });
    expect(await head.text()).toBe("");
    expect(
      (
        await exports.default.fetch("https://pulse.test/v1/matches", {
          headers: { Origin: "https://evil.test" },
        })
      ).status,
    ).toBe(403);
  });
});
