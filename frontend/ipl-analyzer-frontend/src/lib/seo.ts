import { canonicalLeagueHref } from '../data/leagues';

export function appBaseHref() {
  return new URL(import.meta.env.BASE_URL, window.location.origin).href;
}

/** Normalize legacy query destinations without changing the address being viewed. */
function canonicalPageHref(href: string) {
  const url = new URL(href, window.location.origin);
  if (url.origin !== window.location.origin) return href;
  const leagueId = url.searchParams.get('league');
  if (leagueId && /^[a-z0-9-]+$/.test(leagueId)) {
    const canonical = new URL(canonicalLeagueHref(leagueId), url.origin);
    canonical.hash = url.hash;
    return canonical.href;
  }
  return url.href;
}

export function setMetaTag(attribute: 'name' | 'property', key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!element) {
    element = document.createElement('meta');
    element.setAttribute(attribute, key);
    document.head.appendChild(element);
  }
  element.content = content;
}

export function setCanonical(href: string) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!element) {
    element = document.createElement('link');
    element.rel = 'canonical';
    document.head.appendChild(element);
  }
  element.href = href;
}

/** Title, description, canonical and social tags for the page on screen. */
export function setPageMeta(title: string, description: string, pageHref: string) {
  pageHref = canonicalPageHref(pageHref);
  document.title = title;
  setCanonical(pageHref);
  setMetaTag('name', 'description', description);
  setMetaTag('property', 'og:title', title);
  setMetaTag('property', 'og:description', description);
  setMetaTag('property', 'og:type', 'website');
  setMetaTag('property', 'og:url', pageHref);
  const image = new URL(`social/og/${pageHref.match(/\/league\/([a-z0-9-]+)\//)?.[1] ?? 'playoff-pulse'}.png`, appBaseHref()).href;
  setMetaTag('property', 'og:image', image);
  setMetaTag('property', 'og:image:width', '1200');
  setMetaTag('property', 'og:image:height', '630');
  setMetaTag('property', 'og:image:alt', title);
  setMetaTag('name', 'twitter:image', image);
  setMetaTag('name', 'twitter:card', 'summary_large_image');
  setMetaTag('name', 'twitter:title', title);
  setMetaTag('name', 'twitter:description', description);
}

export function setJsonLd(data: object) {
  let script = document.head.querySelector<HTMLScriptElement>('script[data-ipl-jsonld="true"]');
  if (!script) {
    script = document.createElement('script');
    script.type = 'application/ld+json';
    script.dataset.iplJsonld = 'true';
    document.head.appendChild(script);
  }
  script.text = JSON.stringify(data, (_key, value: unknown) =>
    typeof value === 'string' && /^https?:\/\//.test(value) ? canonicalPageHref(value) : value);
}
