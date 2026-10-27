import { DurableObject } from "cloudflare:workers";
import { Collector } from "./collector";
import type { Store } from "./collector";
import { readConfig } from "./config";
import { validPublicId } from "./domain";
import type { MatchDetailSnapshot, MatchListSnapshot } from "./domain";

/** Secrets are optional locally; Wrangler generates all configured bindings. */
type RuntimeEnv = Env &
  Partial<{
    CRICDATA_API_KEY: string;
    SPORTMONKS_API_TOKEN: string;
    ODDS_API_KEY: string;
  }>;

export class SqlStore implements Store {
  constructor(private sql: SqlStorage) {
    sql.exec(
      "CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    );
  }
  get<T>(key: string): T | undefined {
    const row = this.sql
      .exec<{ value: string }>("SELECT value FROM snapshots WHERE key = ?", key)
      .toArray()[0];
    return row ? (JSON.parse(row.value) as T) : undefined;
  }
  put(key: string, value: unknown): void {
    this.sql.exec(
      "INSERT INTO snapshots (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
      key,
      JSON.stringify(value),
    );
  }
  delete(key: string): void {
    this.sql.exec("DELETE FROM snapshots WHERE key = ?", key);
  }
}

export class CricketCollector extends DurableObject<RuntimeEnv> {
  private collector: Collector;
  constructor(ctx: DurableObjectState, env: RuntimeEnv) {
    super(ctx, env);
    // SQL initialization and reservations are synchronous. Never hold a concurrency
    // gate over an upstream request; shared jobs coalesce independently.
    this.collector = new Collector(
      new SqlStore(ctx.storage.sql),
      readConfig(env),
    );
  }
  async list(): Promise<MatchListSnapshot> {
    return this.collector.list();
  }
  async detail(id: string): Promise<MatchDetailSnapshot | null> {
    try {
      return await this.collector.detail(id);
    } catch (error) {
      if (
        error instanceof Error &&
        ["match_not_found", "invalid_match_id"].includes(error.message)
      )
        return null;
      throw error;
    }
  }
}

function headers(origin: string | null): Headers {
  const h = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    Vary: "Origin",
  });
  if (origin) h.set("Access-Control-Allow-Origin", origin);
  h.set("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
  h.set("Access-Control-Allow-Headers", "If-None-Match");
  h.set("Access-Control-Expose-Headers", "ETag, Retry-After");
  return h;
}
function json(body: unknown, status: number, origin: string | null): Response {
  return Response.json(body, { status, headers: headers(origin) });
}

export default {
  async fetch(
    request: Request,
    env: RuntimeEnv,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url),
      config = readConfig(env),
      origin = request.headers.get("Origin");
    if (origin && !config.allowedOrigins.includes(origin))
      return json({ error: "origin_not_allowed" }, 403, null);
    const cors =
      origin && config.allowedOrigins.includes(origin) ? origin : null;
    if (request.method === "OPTIONS")
      return new Response(null, { status: 204, headers: headers(cors) });
    if (!["GET", "HEAD"].includes(request.method))
      return json({ error: "method_not_allowed" }, 405, cors);
    if (request.body !== null || url.search || url.pathname.length > 256)
      return json({ error: "invalid_request" }, 400, cors);
    if (url.pathname === "/health")
      return json(
        {
          status: "ok",
          schemaVersion: 1,
          service: "live-cricket",
          provider: config.scoreProvider,
          providerConnectivity: "not_checked",
        },
        200,
        cors,
      );
    const idMatch = /^\/v1\/matches\/([^/]+)$/.exec(url.pathname);
    if (url.pathname !== "/v1/matches" && !idMatch)
      return json({ error: "not_found" }, 404, cors);
    if (idMatch && !validPublicId(idMatch[1]))
      return json({ error: "invalid_match_id" }, 400, cors);
    // Regional caching is only an optimization. The single credential/quotas DO
    // remains the authority preventing worldwide refresh stampedes.
    const cacheKey = new Request(url.toString(), { method: "GET" });
    try {
      let response = await caches.default.match(cacheKey);
      if (!response) {
        const stub = env.COLLECTOR.getByName("provider-credentials-v1");
        const data = idMatch
          ? await stub.detail(idMatch[1])
          : await stub.list();
        if (data === null) return json({ error: "match_not_found" }, 404, cors);
        const body = JSON.stringify(data),
          digest = await crypto.subtle.digest(
            "SHA-256",
            new TextEncoder().encode(body),
          ),
          etag = `"${Array.from(new Uint8Array(digest))
            .map((b) => b.toString(16).padStart(2, "0"))
            .join("")}"`;
        response = new Response(body, {
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=10",
            ETag: etag,
          },
        });
        ctx.waitUntil(caches.default.put(cacheKey, response.clone()));
      }
      const h = headers(cors);
      h.set("ETag", response.headers.get("ETag") ?? "");
      if (request.headers.get("If-None-Match") === h.get("ETag"))
        return new Response(null, { status: 304, headers: h });
      return new Response(request.method === "HEAD" ? null : response.body, {
        status: 200,
        headers: h,
      });
    } catch (error) {
      // Do not serialize provider exceptions, URLs, responses, or secrets.
      const reason = error instanceof Error ? error.message : "";
      const known = reason.includes("match_not_found")
        ? "match_not_found"
        : reason.includes("invalid_match_id")
          ? "invalid_match_id"
          : "service_unavailable";
      console.error(
        JSON.stringify({ event: "live_cricket_request_failed", code: known }),
      );
      return json(
        { error: known },
        known === "match_not_found"
          ? 404
          : known === "invalid_match_id"
            ? 400
            : 503,
        cors,
      );
    }
  },
} satisfies ExportedHandler<RuntimeEnv>;
