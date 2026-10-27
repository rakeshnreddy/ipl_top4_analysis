import { arr, obj, str } from "./domain";
import type { MarketScope } from "./providers/odds";

export interface Config {
  scoreProvider: "sportscore" | "cricketdata" | "sportmonks" | "none";
  cricketDataKey: string;
  cricketDataAccess: boolean;
  cricketDataRedisplay: boolean;
  cricketDataFantasy: boolean;
  sportmonksKey: string;
  sportmonksAccess: boolean;
  sportmonksRedisplay: boolean;
  oddsKey: string;
  oddsAccess: boolean;
  oddsRedisplay: boolean;
  oddsRegions: string[];
  marketScopes: MarketScope[];
  sportscoreDaily: number;
  cricketDataDaily: number;
  sportmonksDaily: number;
  oddsMonthly: number;
  discoverySeconds: number;
  detailSeconds: number;
  marketSeconds: number;
  staleSeconds: number;
  maxPages: number;
  maxMatches: number;
  timeoutMs: number;
  maxBytes: number;
  allowedOrigins: string[];
}
export function defaultConfig(): Config {
  return {
    scoreProvider: "sportscore",
    cricketDataKey: "",
    cricketDataAccess: false,
    cricketDataRedisplay: false,
    cricketDataFantasy: false,
    sportmonksKey: "",
    sportmonksAccess: false,
    sportmonksRedisplay: false,
    oddsKey: "",
    oddsAccess: false,
    oddsRedisplay: false,
    oddsRegions: ["uk"],
    marketScopes: [],
    sportscoreDaily: 9000,
    cricketDataDaily: 90,
    sportmonksDaily: 90,
    oddsMonthly: 450,
    discoverySeconds: 60,
    detailSeconds: 60,
    marketSeconds: 14_400,
    staleSeconds: 180,
    maxPages: 2,
    maxMatches: 200,
    timeoutMs: 8000,
    maxBytes: 2_000_000,
    allowedOrigins: [
      "https://ipl-playoff-pulse.pages.dev",
      "https://rakeshnreddy.github.io",
      "http://localhost:5173",
      "http://127.0.0.1:5173",
    ],
  };
}
const positive = (s: unknown, fallback: number, min: number, max: number) => {
  const n = Number(s);
  return Number.isSafeInteger(n) && n >= min && n <= max ? n : fallback;
};
export function readConfig(input: unknown): Config {
  const e = obj(input),
    c = defaultConfig(),
    provider = str(e.SCORE_PROVIDER, c.scoreProvider);
  c.scoreProvider = [
    "sportscore",
    "cricketdata",
    "sportmonks",
    "none",
  ].includes(provider)
    ? (provider as Config["scoreProvider"])
    : "none";
  c.cricketDataKey = str(e.CRICDATA_API_KEY);
  c.cricketDataAccess = e.CRICDATA_ACCESS_ENABLED === "true";
  c.cricketDataRedisplay = e.CRICDATA_REDISPLAY_ALLOWED === "true";
  c.cricketDataFantasy = e.CRICDATA_FANTASY_ENABLED === "true";
  c.sportmonksKey = str(e.SPORTMONKS_API_TOKEN);
  c.sportmonksAccess = e.SPORTMONKS_ACCESS_ENABLED === "true";
  c.sportmonksRedisplay = e.SPORTMONKS_REDISPLAY_ALLOWED === "true";
  c.oddsKey = str(e.ODDS_API_KEY);
  c.oddsAccess = e.ODDS_ACCESS_ENABLED === "true";
  c.oddsRedisplay = e.ODDS_REDISPLAY_ALLOWED === "true";
  c.sportscoreDaily = positive(
    e.SPORTSCORE_DAILY_CREDITS,
    c.sportscoreDaily,
    1,
    9000,
  );
  c.cricketDataDaily = positive(
    e.CRICDATA_DAILY_CREDITS,
    c.cricketDataDaily,
    1,
    90,
  );
  c.sportmonksDaily = positive(
    e.SPORTMONKS_DAILY_CREDITS,
    c.sportmonksDaily,
    1,
    90,
  );
  c.oddsMonthly = positive(e.ODDS_MONTHLY_CREDITS, c.oddsMonthly, 1, 450);
  const minimum =
    c.scoreProvider === "cricketdata"
      ? 1800
      : c.scoreProvider === "sportmonks"
        ? 3600
        : 60;
  c.discoverySeconds = positive(
    e.DISCOVERY_SECONDS,
    Math.max(minimum, c.discoverySeconds),
    minimum,
    86400,
  );
  c.detailSeconds = positive(
    e.DETAIL_SECONDS,
    Math.max(minimum, c.detailSeconds),
    minimum,
    86400,
  );
  c.marketSeconds = positive(e.MARKET_SECONDS, c.marketSeconds, 3600, 86400);
  c.staleSeconds = positive(
    e.STALE_SECONDS,
    Math.max(180, c.discoverySeconds * 3),
    180,
    172800,
  );
  c.maxPages = positive(e.MAX_DISCOVERY_PAGES, c.maxPages, 1, 4);
  const regions = str(e.ODDS_REGIONS, "uk")
    .split(",")
    .map((x) => x.trim())
    .filter((x) =>
      ["uk", "au", "eu", "us", "us2", "us_dfs", "us_ex"].includes(x),
    );
  c.oddsRegions = [...new Set(regions)].slice(0, 2);
  try {
    c.marketScopes = arr(JSON.parse(str(e.ODDS_SCOPES_JSON, "[]")))
      .slice(0, 4)
      .flatMap((v) => {
        const d = obj(v),
          sportKey = str(d.sportKey),
          competitionIds = arr(d.competitionIds)
            .map((x) => str(x))
            .filter(Boolean)
            .slice(0, 20),
          fmt = str(d.format),
          g = str(d.gender);
        return /^cricket_[a-z0-9_]{1,80}$/.test(sportKey) &&
          competitionIds.length &&
          ["T20", "T10", "ODI", "TEST", "HUNDRED"].includes(fmt) &&
          ["male", "female", "mixed"].includes(g)
          ? [{ sportKey, competitionIds, format: fmt, gender: g }]
          : [];
      });
  } catch {
    c.marketScopes = [];
  }
  const origins = str(e.ALLOWED_ORIGINS)
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  if (origins.length)
    c.allowedOrigins = origins
      .filter((x) => {
        try {
          const u = new URL(x);
          return (
            u.origin === x &&
            (u.protocol === "https:" ||
              u.hostname === "localhost" ||
              u.hostname === "127.0.0.1")
          );
        } catch {
          return false;
        }
      })
      .slice(0, 8);
  return c;
}
