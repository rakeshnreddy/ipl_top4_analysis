import {
  normalizeSportScoreDetail,
  normalizeSportScoreList,
} from "../../../frontend/ipl-analyzer-frontend/src/data/freeCricketNormalize";
import { defaultConfig } from "./config";
import type { Config } from "./config";
import {
  arr,
  baseDetail,
  iso,
  obj,
  refreshPart,
  SOURCES,
  str,
  unavailable,
  validPublicId,
} from "./domain";
import type {
  MatchDetailSnapshot,
  MatchListSnapshot,
  MatchSummary,
  Part,
  Bookmaker,
} from "./domain";
import { cricketDataDetail, cricketDataMatch } from "./providers/cricketdata";
import { sportmonksDetail, sportmonksMatch } from "./providers/sportmonks";
import { matchMarketEvent, normalizeOdds } from "./providers/odds";
import type { MarketScope } from "./providers/odds";
export { defaultConfig };

export interface Store {
  get<T>(key: string): T | undefined;
  put(key: string, value: unknown): void;
  delete(key: string): void;
}
export class MemoryStore implements Store {
  private rows = new Map<string, string>();
  get<T>(key: string): T | undefined {
    const v = this.rows.get(key);
    return v === undefined ? undefined : (JSON.parse(v) as T);
  }
  put(key: string, value: unknown): void {
    this.rows.set(key, JSON.stringify(value));
  }
  delete(key: string): void {
    this.rows.delete(key);
  }
}
type Provider = "sportscore" | "cricketdata" | "sportmonks" | "odds";
interface Quota {
  hours: { at: number; credits: number }[];
  days: { at: number; credits: number }[];
  minutes: { at: number; credits: number }[];
  blockedUntil: number;
  remoteRemaining: number | null;
}
interface Job {
  nextAt: number;
  error: string | null;
}
type Fetcher = (input: string | URL, init?: RequestInit) => Promise<Response>;
interface ScoreSnapshot {
  match: MatchSummary;
  resource: "list" | "detail";
  publishedAt: string | null;
}

/** The sole state owner for one set of provider credentials and its shared quotas. */
export class Collector {
  private pending = new Map<string, Promise<void>>();
  private networkCount = 0;
  constructor(
    private store: Store,
    readonly config: Config = defaultConfig(),
    // A platform fetch reference stored as a method gets this=Collector, which
    // fails Workers' native receiver check. The wrapper invokes it globally.
    private fetcher: Fetcher = (input, init) => fetch(input, init),
    private now: () => number = Date.now,
  ) {}
  private key(suffix: string): string {
    return `${this.config.scoreProvider}:${suffix}`;
  }
  private configured(): boolean {
    const c = this.config;
    return (
      c.scoreProvider === "sportscore" ||
      (c.scoreProvider === "cricketdata" &&
        c.cricketDataAccess &&
        c.cricketDataRedisplay &&
        !!c.cricketDataKey) ||
      (c.scoreProvider === "sportmonks" &&
        c.sportmonksAccess &&
        c.sportmonksRedisplay &&
        !!c.sportmonksKey)
    );
  }
  private source() {
    return this.config.scoreProvider === "none"
      ? SOURCES.service
      : SOURCES[this.config.scoreProvider];
  }
  private empty(message: string): MatchListSnapshot {
    return {
      schemaVersion: 1,
      status: "unavailable",
      message,
      source: this.source(),
      generatedAt: null,
      refreshAfterSeconds: this.config.discoverySeconds,
      staleAfterSeconds: this.config.staleSeconds,
      coverage: [],
      matches: [],
    };
  }
  private async job(
    key: string,
    seconds: number,
    task: () => Promise<void>,
  ): Promise<void> {
    const pending = this.pending.get(key);
    if (pending) return pending;
    if ((this.store.get<Job>(`job:${key}`)?.nextAt ?? 0) > this.now()) return;
    // Persist the reservation before external I/O. A restart cannot bypass cadence.
    this.store.put(`job:${key}`, {
      nextAt: this.now() + seconds * 1000,
      error: null,
    } satisfies Job);
    const work = task()
      .catch((error: unknown) => {
        const known = [
          "quota_exhausted",
          "upstream_busy",
          "upstream_unavailable",
          "upstream_too_large",
          "upstream_rejected",
          "older_source_snapshot",
          "invalid_provider_match",
          "invalid_market_feed",
          "invalid_source_id",
          "source_identity_changed",
        ];
        const code =
          error instanceof Error && known.includes(error.message)
            ? error.message
            : error instanceof SyntaxError
              ? "invalid_json"
              : error instanceof TypeError
                ? "network_error"
                : "source_contract_error";
        console.error(
          JSON.stringify({
            event: "live_cricket_refresh_failed",
            source: this.config.scoreProvider,
            kind: key.includes("detail:")
              ? "detail"
              : key.startsWith("markets:")
                ? "markets"
                : "discovery",
            code,
          }),
        );
        this.store.put(`job:${key}`, {
          nextAt: this.now() + Math.max(60, seconds) * 1000,
          error:
            "The source is unavailable or its shared request budget is exhausted.",
        } satisfies Job);
      })
      .finally(() => {
        this.pending.delete(key);
      });
    this.pending.set(key, work);
    return work;
  }
  private quota(provider: Provider, cost: number): void {
    const now = this.now(),
      hour = 3_600_000,
      day = 24 * hour,
      key = `quota:${provider}`;
    const q = this.store.get<Quota>(key) ?? {
      hours: [],
      days: [],
      minutes: [],
      blockedUntil: 0,
      remoteRemaining: null,
    };
    // Retain the whole boundary bucket, conservatively over-counting up to one
    // hour/day/minute rather than resetting credits inside a rolling window.
    q.hours = q.hours.filter((b) => b.at + hour > now - day);
    q.days = q.days.filter((b) => b.at + day > now - 32 * day);
    q.minutes = q.minutes.filter((b) => b.at + 60000 > now - hour);
    const used = (b: { credits: number }[]) =>
      b.reduce((a, b) => a + b.credits, 0);
    const daily =
      provider === "sportscore"
        ? this.config.sportscoreDaily
        : provider === "cricketdata"
          ? this.config.cricketDataDaily
          : provider === "sportmonks"
            ? this.config.sportmonksDaily
            : Infinity;
    if (
      q.blockedUntil > now ||
      q.remoteRemaining === 0 ||
      used(q.hours) + cost > daily ||
      (provider === "odds" && used(q.days) + cost > this.config.oddsMonthly) ||
      (provider === "sportmonks" && used(q.minutes) + cost > 1900)
    )
      throw new Error("quota_exhausted");
    const add = (b: { at: number; credits: number }[], at: number) => {
      const v = b.find((x) => x.at === at);
      if (v) v.credits += cost;
      else b.push({ at, credits: cost });
    };
    add(q.hours, Math.floor(now / hour) * hour);
    add(q.days, Math.floor(now / day) * day);
    add(q.minutes, Math.floor(now / 60000) * 60000);
    if (q.remoteRemaining !== null)
      q.remoteRemaining = Math.max(0, q.remoteRemaining - cost);
    this.store.put(key, q);
  }
  private remoteQuota(provider: Provider, response: Response): void {
    const key = `quota:${provider}`,
      q = this.store.get<Quota>(key);
    if (!q) return;
    const raw = response.headers.get("x-requests-remaining");
    if (raw !== null && /^\d+$/.test(raw)) q.remoteRemaining = Number(raw);
    if (
      response.status === 429 ||
      response.status === 401 ||
      response.status === 403
    ) {
      const retry = Number(response.headers.get("retry-after"));
      q.blockedUntil =
        this.now() +
        Math.min(86400, Number.isFinite(retry) && retry > 0 ? retry : 3600) *
          1000;
    }
    // A zero remote quota is not reset by a guessed billing-day boundary.
    this.store.put(key, q);
  }
  private async request(
    provider: Provider,
    url: URL,
    cost = 1,
  ): Promise<unknown> {
    const allowed = {
      sportscore: "https://sportscore.com",
      cricketdata: "https://api.cricapi.com",
      sportmonks: "https://cricket.sportmonks.com",
      odds: "https://api.the-odds-api.com",
    };
    if (url.origin !== allowed[provider] || this.networkCount >= 2)
      throw new Error("upstream_busy");
    this.quota(provider, cost);
    this.networkCount++;
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), this.config.timeoutMs);
    try {
      const response = await this.fetcher(url, {
        headers: { Accept: "application/json" },
        // Workers supports manual/follow only. Manual plus the !ok check below
        // rejects redirects without forwarding a query-string provider key.
        redirect: "manual",
        signal: controller.signal,
      });
      this.remoteQuota(provider, response);
      if (
        !response.ok ||
        Number(response.headers.get("content-length") ?? 0) >
          this.config.maxBytes ||
        !response.body
      )
        throw new Error("upstream_unavailable");
      const reader = response.body.getReader(),
        chunks: Uint8Array[] = [];
      let length = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          length += value.byteLength;
          if (length > this.config.maxBytes) {
            await reader.cancel();
            throw new Error("upstream_too_large");
          }
          chunks.push(value);
        }
      } finally {
        reader.releaseLock();
      }
      const bytes = new Uint8Array(length);
      let cursor = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, cursor);
        cursor += chunk.length;
      }
      const payload: unknown = JSON.parse(new TextDecoder().decode(bytes));
      if (provider === "cricketdata" && obj(payload).status !== "success")
        throw new Error("upstream_rejected");
      return payload;
    } finally {
      clearTimeout(timer);
      this.networkCount--;
    }
  }
  private cdUrl(
    endpoint: "currentMatches" | "match_info" | "match_scorecard",
    params: Record<string, string>,
  ): URL {
    const u = new URL(`https://api.cricapi.com/v1/${endpoint}`);
    u.searchParams.set("apikey", this.config.cricketDataKey);
    for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
    return u;
  }
  private smUrl(endpoint: string, params: Record<string, string>): URL {
    const u = new URL(`https://cricket.sportmonks.com/api/v2.0/${endpoint}`);
    u.searchParams.set("api_token", this.config.sportmonksKey);
    for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
    return u;
  }
  /** Synchronous read/compare/write after I/O: both resources share one winner. */
  private acceptScore(incoming: ScoreSnapshot): ScoreSnapshot {
    const key = this.key(`score:${incoming.match.id}`);
    const current = this.store.get<ScoreSnapshot>(key);
    if (current) {
      const sameResource = current.resource === incoming.resource;
      if (this.config.scoreProvider === "sportscore") {
        // Publication is snapshot provenance, never the observation time of a ball.
        // A cross-resource tie/unknown clock cannot resolve conflicting scores.
        const before = current.publishedAt;
        const after = incoming.publishedAt;
        if (before && after) {
          const delta = Date.parse(after) - Date.parse(before);
          if (
            delta < 0 ||
            (delta === 0 &&
              !sameResource &&
              current.match.revision !== incoming.match.revision)
          )
            return current;
        } else if (
          !sameResource &&
          (!after || current.match.revision !== incoming.match.revision)
        ) {
          return current;
        }
      } else {
        const before = current.match.observedAt;
        const after = incoming.match.observedAt;
        if (before && (!after || Date.parse(after) < Date.parse(before)))
          return current;
        if (
          before &&
          after &&
          Date.parse(after) === Date.parse(before) &&
          !sameResource &&
          current.match.revision !== incoming.match.revision
        )
          return current;
        if (
          !before &&
          !after &&
          !sameResource &&
          current.match.revision !== incoming.match.revision
        )
          return current;
      }
    }
    // Equal-time corrections from the same resource may legitimately lower runs.
    this.store.put(key, incoming);
    return incoming;
  }
  private async collectList(): Promise<void> {
    const at = new Date(this.now()).toISOString(),
      c = this.config;
    let result: MatchListSnapshot;
    if (c.scoreProvider === "sportscore") {
      const p = await this.request(
        "sportscore",
        new URL(
          "https://sportscore.com/api/widget/matches/?sport=cricket&limit=50",
        ),
      );
      result = normalizeSportScoreList(p, at);
    } else {
      const matches: MatchSummary[] = [];
      let partial = false,
        more = false;
      for (let page = 0; page < c.maxPages; page++) {
        let payload: unknown;
        try {
          if (c.scoreProvider === "cricketdata")
            payload = await this.request(
              "cricketdata",
              this.cdUrl("currentMatches", { offset: String(page * 25) }),
            );
          else {
            const params: Record<string, string> = {
              include: "localteam,visitorteam,league,venue,runs",
              page: String(page + 1),
            };
            // Explicit live discovery keeps multi-day games that started earlier.
            if (page === 0)
              payload = await this.request(
                "sportmonks",
                this.smUrl("livescores", params),
              );
            else {
              params["filter[starts_between]"] =
                `${new Date(this.now() - 86400000).toISOString().slice(0, 10)},${new Date(this.now() + 86400000).toISOString().slice(0, 10)}`;
              params.page = String(page);
              payload = await this.request(
                "sportmonks",
                this.smUrl("fixtures", params),
              );
            }
          }
        } catch (error) {
          if (!matches.length) throw error;
          partial = true;
          break;
        }
        const rows = arr(obj(payload).data);
        for (const row of rows) {
          try {
            matches.push(
              c.scoreProvider === "cricketdata"
                ? cricketDataMatch(row, at)
                : sportmonksMatch(row, at),
            );
          } catch {
            partial = true;
          }
        }
        if (c.scoreProvider === "cricketdata") {
          const total = Number(obj(obj(payload).info).totalRows);
          more = Number.isFinite(total)
            ? page * 25 + rows.length < total
            : rows.length >= 25;
          if (!more) break;
        } else if (page > 0) {
          const meta = obj(obj(payload).meta);
          const current = Number(meta.current_page);
          const last = Number(meta.last_page);
          // The official v2 examples expose meta.current_page/last_page. Never
          // follow the supplied links: only our fixed-host page counter is used.
          more =
            Number.isSafeInteger(current) && Number.isSafeInteger(last)
              ? current < last
              : rows.length >= 100;
          if (!more) break;
        } else more = true;
      }
      partial ||= more;
      result = {
        ...this.empty(""),
        status: partial ? "partial" : "ok",
        message: partial
          ? "Discovery is bounded by the configured free request budget; some matches may be omitted."
          : null,
        generatedAt: at,
        matches,
        coverage: [],
      };
    }
    // No await from this current-state read through publishing and trimming.
    const previous = this.store.get<MatchListSnapshot>(this.key("list"));
    if (
      c.scoreProvider === "sportscore" &&
      previous?.generatedAt &&
      result.generatedAt &&
      Date.parse(result.generatedAt) < Date.parse(previous.generatedAt)
    )
      throw new Error("older_source_snapshot");
    const incomingIds = new Set(result.matches.map((m) => m.id));
    const byId = new Map(result.matches.map((m) => [m.id, m]));
    // Missing rows during a provider outage do not silently finish active matches.
    for (const old of previous?.matches ?? [])
      if (
        !byId.has(old.id) &&
        [
          "live",
          "toss",
          "stumps",
          "suspended",
          "delayed",
          "innings-break",
        ].includes(old.state) &&
        this.now() - Date.parse(old.fetchedAt ?? "") < 48 * 3600000
      ) {
        byId.set(old.id, old);
        result.status = "partial";
        result.message =
          "An active match is retained from an earlier source snapshot. Check its last observed/checked time.";
      }
    if (byId.size > c.maxMatches) {
      result.status = "partial";
      result.message =
        "The bounded match registry is full; some source matches were omitted.";
    }
    result.matches = [...byId.values()].slice(0, c.maxMatches).map((match) => {
      if (!incomingIds.has(match.id)) return match;
      const chosen = this.acceptScore({
        match,
        resource: "list",
        publishedAt: result.generatedAt,
      });
      if (chosen.match.revision !== match.revision) {
        result.status = "partial";
        result.message =
          "Some scores are retained from a newer or unresolved source snapshot; their original clocks are preserved.";
      }
      return chosen.match;
    });
    result.refreshAfterSeconds = c.discoverySeconds;
    result.staleAfterSeconds = c.staleSeconds;
    result.coverage = [
      ...new Set(result.matches.map((m) => m.competition.name)),
    ].map((competition) => ({
      competition,
      scores: true,
      scorecard: result.matches.some(
        (m) => m.competition.name === competition && m.capabilities.scorecard,
      ),
      commentary: result.matches.some(
        (m) => m.competition.name === competition && m.capabilities.commentary,
      ),
      markets: false,
      note: "Discovered within this source’s coverage; fields and completeness vary by match.",
    }));
    this.store.put(this.key("list"), result);
    for (const old of previous?.matches ?? [])
      if (!result.matches.some((m) => m.id === old.id)) {
        this.store.delete(this.key(`detail:${old.id}`));
        this.store.delete(`job:${this.key(`detail:${old.id}`)}`);
        this.store.delete(this.key(`market-map:${old.id}`));
        this.store.delete(this.key(`score:${old.id}`));
      }
  }
  async list(): Promise<MatchListSnapshot> {
    if (!this.configured())
      return this.empty(
        "The selected score source needs configured server credentials, access and redisplay permission.",
      );
    await this.job(this.key("discovery"), this.config.discoverySeconds, () =>
      this.collectList(),
    );
    const list = this.store.get<MatchListSnapshot>(this.key("list"));
    if (!list)
      return this.empty(
        "The cricket source is temporarily unavailable or its shared free request budget is exhausted.",
      );
    const failed = this.store.get<Job>(`job:${this.key("discovery")}`)?.error;
    const stale = list.matches.some(
      (m) =>
        !m.fetchedAt ||
        this.now() - Date.parse(m.observedAt ?? m.fetchedAt) >
          this.config.staleSeconds * 1000,
    );
    return {
      ...list,
      status: failed || stale ? "partial" : list.status,
      message:
        failed ??
        (stale
          ? "Some source snapshots are stale; the last known match state is retained."
          : list.message),
    };
  }
  private async collectDetail(summary: MatchSummary): Promise<void> {
    const c = this.config,
      at = new Date(this.now()).toISOString(),
      previous = this.store.get<MatchDetailSnapshot>(
        this.key(`detail:${summary.id}`),
      );
    let result: MatchDetailSnapshot;
    if (c.scoreProvider === "sportscore") {
      const slug = summary.providerIds.sportscoreSlug;
      if (!/^[a-z0-9-]{1,160}$/.test(slug ?? ""))
        throw new Error("invalid_source_id");
      result = normalizeSportScoreDetail(
        await this.request(
          "sportscore",
          new URL(
            `https://sportscore.com/api/widget/match/?sport=cricket&slug=${encodeURIComponent(slug)}`,
          ),
        ),
        summary,
        at,
      );
    } else if (c.scoreProvider === "cricketdata") {
      const id = summary.providerIds.cricketdata;
      if (!/^[a-zA-Z0-9-]{1,80}$/.test(id ?? ""))
        throw new Error("invalid_source_id");
      const info = obj(
        await this.request("cricketdata", this.cdUrl("match_info", { id })),
      ).data;
      if (str(obj(info).id) !== id) throw new Error("source_identity_changed");
      let card: unknown | null = null;
      let cardFailed = false;
      if (c.cricketDataFantasy && obj(info).fantasyEnabled === true) {
        try {
          const candidate = obj(
            await this.request(
              "cricketdata",
              this.cdUrl("match_scorecard", { id }),
              10,
            ),
          ).data;
          const candidateMatch = cricketDataMatch(candidate, at),
            infoMatch = cricketDataMatch(info, at);
          if (
            candidateMatch.id !== infoMatch.id ||
            candidateMatch.teams
              .map((t) => t.name)
              .sort()
              .join("|") !==
              infoMatch.teams
                .map((t) => t.name)
                .sort()
                .join("|") ||
            candidateMatch.competition.id !== infoMatch.competition.id
          )
            throw new Error("scorecard_identity_changed");
          card = candidate;
        } catch {
          cardFailed = true;
        }
      }
      result = cricketDataDetail(info, card, at);
      if (cardFailed && previous?.scorecard.data)
        result.scorecard = {
          ...previous.scorecard,
          status: "stale",
          reason:
            "The detailed scorecard source could not be verified; this is the last known good card.",
        };
    } else {
      const id = summary.providerIds.sportmonks;
      if (!/^\d{1,15}$/.test(id ?? "")) throw new Error("invalid_source_id");
      const payload = obj(
        await this.request(
          "sportmonks",
          this.smUrl(`fixtures/${id}`, {
            include:
              "localteam,visitorteam,league,venue,runs,batting,bowling,lineup,balls.score",
          }),
        ),
      ).data;
      if (str(obj(payload).id) !== id)
        throw new Error("source_identity_changed");
      result = sportmonksDetail(payload, at);
    }
    // Read current state after all I/O. A removed match cannot be resurrected by
    // a late detail response; its bounded cache/provenance rows stay removed.
    const list = this.store.get<MatchListSnapshot>(this.key("list"));
    if (!list?.matches.some((m) => m.id === summary.id)) return;
    const currentDetail = this.store.get<MatchDetailSnapshot>(
      this.key(`detail:${summary.id}`),
    );
    if (
      c.scoreProvider === "sportscore" &&
      currentDetail?.generatedAt &&
      result.generatedAt &&
      Date.parse(result.generatedAt) < Date.parse(currentDetail.generatedAt)
    )
      throw new Error("older_source_snapshot");
    if (
      currentDetail?.match.observedAt &&
      result.match.observedAt &&
      Date.parse(result.match.observedAt) <
        Date.parse(currentDetail.match.observedAt)
    )
      return;
    const chosen = this.acceptScore({
      match: result.match,
      resource: "detail",
      publishedAt: result.generatedAt,
    });
    if (currentDetail?.markets.data) result.markets = currentDetail.markets;
    // Keep this resource's sections and envelope intact even when another
    // resource supplied the winning score. Never re-date an old card or delivery.
    this.store.put(this.key(`detail:${summary.id}`), result);
    list.matches = list.matches.map((m) =>
      m.id === summary.id ? chosen.match : m,
    );
    this.store.put(this.key("list"), list);
  }
  private async collectMarkets(scope: MarketScope): Promise<void> {
    const u = new URL(
      `https://api.the-odds-api.com/v4/sports/${scope.sportKey}/odds`,
    );
    u.searchParams.set("apiKey", this.config.oddsKey);
    u.searchParams.set("regions", this.config.oddsRegions.join(","));
    u.searchParams.set("markets", "h2h");
    u.searchParams.set("oddsFormat", "decimal");
    u.searchParams.set("dateFormat", "iso");
    const payload = await this.request(
      "odds",
      u,
      this.config.oddsRegions.length,
    );
    if (!Array.isArray(payload) || payload.length > 200)
      throw new Error("invalid_market_feed");
    // Persist only normalized app transport, not bulk/raw upstream archives.
    const entries = payload.map((e) => {
      const d = obj(e);
      return {
        id: str(d.id),
        sport_key: str(d.sport_key),
        commence_time: str(d.commence_time),
        home_team: str(d.home_team),
        away_team: str(d.away_team),
        quotes: normalizeOdds(d, new Date(this.now()).toISOString()),
      };
    });
    this.store.put(`markets:${scope.sportKey}`, entries);
  }
  private async marketPart(match: MatchSummary): Promise<Part<Bookmaker[]>> {
    const c = this.config;
    if (
      !c.oddsAccess ||
      !c.oddsRedisplay ||
      !c.oddsKey ||
      !c.oddsRegions.length
    )
      return unavailable(
        SOURCES.odds.name,
        "Bookmaker prices require a free API key, enabled access and confirmed redisplay permission.",
      );
    const scope = c.marketScopes.find(
      (s) =>
        s.competitionIds.includes(match.competition.id) &&
        s.format === match.format &&
        s.gender === match.gender,
    );
    if (!scope)
      return unavailable(
        SOURCES.odds.name,
        "No verified competition/format/category mapping exists for this match.",
      );
    await this.job(`markets:${scope.sportKey}`, c.marketSeconds, () =>
      this.collectMarkets(scope),
    );
    const events =
      this.store.get<
        ({ id: string; quotes: Part<Bookmaker[]> } & Record<string, unknown>)[]
      >(`markets:${scope.sportKey}`) ?? [];
    const id = matchMarketEvent(match, events, scope);
    if (!id)
      return unavailable(
        SOURCES.odds.name,
        "No unambiguous matching bookmaker event is available.",
      );
    const mapKey = this.key(`market-map:${match.id}`),
      previous = this.store.get<{ id: string; start: string | null }>(mapKey);
    if (previous && (previous.id !== id || previous.start !== match.startTime))
      return unavailable(
        SOURCES.odds.name,
        "The event mapping changed and requires explicit review.",
      );
    this.store.put(mapKey, { id, start: match.startTime });
    const quote = events.find((e) => e.id === id)!.quotes;
    const error = this.store.get<Job>(`job:markets:${scope.sportKey}`)?.error;
    return refreshPart(
      error && quote.data
        ? { ...quote, status: "stale", reason: error }
        : quote,
      this.now(),
      Math.min(300, c.staleSeconds),
    );
  }
  async detail(id: string): Promise<MatchDetailSnapshot> {
    if (!validPublicId(id)) throw new Error("invalid_match_id");
    const prefix = {
      sportscore: "ss-",
      cricketdata: "cd-",
      sportmonks: "sm-",
      none: "",
    }[this.config.scoreProvider];
    if (!prefix || !id.startsWith(prefix) || !this.configured())
      throw new Error("match_not_found");
    let summary = this.store
      .get<MatchListSnapshot>(this.key("list"))
      ?.matches.find((m) => m.id === id);
    if (!summary) {
      await this.list();
      summary = this.store
        .get<MatchListSnapshot>(this.key("list"))
        ?.matches.find((m) => m.id === id);
    }
    // Public detail requests cannot choose arbitrary upstream paths or undiscovered IDs.
    if (!summary || !this.configured()) throw new Error("match_not_found");
    await this.job(this.key(`detail:${id}`), this.config.detailSeconds, () =>
      this.collectDetail(summary),
    );
    const listed = this.store
      .get<MatchListSnapshot>(this.key("list"))
      ?.matches.find((m) => m.id === id);
    if (!listed) throw new Error("match_not_found");
    const marketMatch =
      this.store.get<ScoreSnapshot>(this.key(`score:${id}`))?.match ?? listed;
    let markets = await this.marketPart(marketMatch);
    // Market I/O can overlap discovery too. Assemble from current storage only
    // after it finishes, keeping the detailed envelope's own publication clock.
    const currentSummary = this.store
      .get<MatchListSnapshot>(this.key("list"))
      ?.matches.find((m) => m.id === id);
    if (!currentSummary) {
      this.store.delete(this.key(`market-map:${id}`));
      throw new Error("match_not_found");
    }
    const detail = this.store.get<MatchDetailSnapshot>(
      this.key(`detail:${id}`),
    ) ?? {
      ...baseDetail(
        currentSummary,
        this.config.detailSeconds,
        this.config.staleSeconds,
      ),
      generatedAt: null,
    };
    const current =
      this.store.get<ScoreSnapshot>(this.key(`score:${id}`))?.match ??
      currentSummary;
    const identity = (match: MatchSummary) =>
      JSON.stringify([
        match.teams,
        match.competition.id,
        match.format,
        match.gender,
        match.startTime,
      ]);
    if (identity(marketMatch) !== identity(current))
      markets = unavailable(
        SOURCES.odds.name,
        "The match identity changed during the quote request; prices require a fresh verified mapping.",
      );
    const retainedScore = current.revision !== detail.match.revision;
    const failed = this.store.get<Job>(
      `job:${this.key(`detail:${id}`)}`,
    )?.error;
    const result: MatchDetailSnapshot = {
      ...detail,
      match: current,
      refreshAfterSeconds: this.config.detailSeconds,
      staleAfterSeconds: this.config.staleSeconds,
      scorecard: refreshPart(
        detail.scorecard,
        this.now(),
        this.config.staleSeconds,
      ),
      commentary: refreshPart(
        detail.commentary,
        this.now(),
        this.config.staleSeconds,
      ),
      markets,
      model: unavailable(
        "Playoff Pulse",
        "No released match-win artifact and complete verified inference state are configured.",
      ),
      status: failed || retainedScore ? ("partial" as const) : detail.status,
      message:
        failed ??
        (retainedScore
          ? "The score is retained from another accepted source snapshot; detailed sections keep their own original source clocks."
          : detail.message),
    };
    result.match = {
      ...result.match,
      capabilities: {
        ...result.match.capabilities,
        scorecard: result.scorecard.data !== null,
        commentary: result.commentary.data !== null,
        markets: markets.data !== null,
        model: false,
      },
    };
    return result;
  }
}
