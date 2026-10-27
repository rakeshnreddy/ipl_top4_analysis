import { PRIMARY_SITE_URL } from './siteIdentity';

export interface CommercialContext {
  url: string;
  sourceIds: string[];
  contentReady: boolean;
  attributionVisible: boolean;
}
export interface Sponsorship {
  name: string;
  url: string;
  message: string;
  disclosure: 'Advertisement';
  rel: 'sponsored noopener noreferrer';
}
export interface MonetizationConfig {
  adsEnabled: boolean;
  publisherId: string | null;
  siteApproved: boolean;
  cmpReady: boolean;
  sponsor: Sponsorship | null;
}

/** Public account identifiers only; this does not establish account ownership or approval. */
export function normalizePublisherId(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const match = /^(?:ca-)?pub-(\d{16})$/.exec(value.trim());
  if (!match || ['0000000000000000', '1234567890123456'].includes(match[1])) return null;
  return `ca-pub-${match[1]}`;
}

const publicText = (value: unknown, max: number) => typeof value === 'string' ? value.trim().slice(0, max) : '';
function suppliedSponsor(env: Record<string, unknown>): Sponsorship | null {
  const name = publicText(env.VITE_SPONSOR_NAME, 100);
  const message = publicText(env.VITE_SPONSOR_MESSAGE, 240);
  const rawUrl = publicText(env.VITE_SPONSOR_URL, 2048);
  if (!name || !message || !rawUrl) return null;
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== 'https:' || url.username || url.password) return null;
    return { name, message, url: url.href, disclosure: 'Advertisement', rel: 'sponsored noopener noreferrer' };
  } catch { return null; }
}

export function monetizationFromEnv(env: Record<string, unknown> = {}): MonetizationConfig {
  return {
    adsEnabled: env.VITE_ADS_ENABLED === 'true',
    publisherId: normalizePublisherId(env.VITE_ADSENSE_PUBLISHER_ID),
    siteApproved: env.VITE_ADSENSE_SITE_APPROVED === 'true',
    cmpReady: env.VITE_ADSENSE_CMP_READY === 'true',
    sponsor: suppliedSponsor(env),
  };
}

/** An explicit source allowlist, not a blanket commercial licence for the whole site. */
export function commercialSurfaceAllowed(context: CommercialContext): boolean {
  if (!context.contentReady || !context.attributionVisible || !context.sourceIds.length
    || context.sourceIds.some(source => source !== 'sportscore')) return false;
  try {
    const url = new URL(context.url);
    return url.origin === new URL(PRIMARY_SITE_URL).origin
      && !url.username && !url.password
      && ['/cricket/', '/cricket/index.html'].includes(url.pathname);
  } catch { return false; }
}

/** Readiness only. No advertising script, request, impression or consent UI is loaded here. */
export function advertisingEligible(config: MonetizationConfig, context: CommercialContext): boolean {
  return config.adsEnabled && !!config.publisherId && config.siteApproved && config.cmpReady
    && commercialSurfaceAllowed(context);
}

export function sponsorshipFor(config: MonetizationConfig, context: CommercialContext): Sponsorship | null {
  return config.sponsor && commercialSurfaceAllowed(context) ? config.sponsor : null;
}
