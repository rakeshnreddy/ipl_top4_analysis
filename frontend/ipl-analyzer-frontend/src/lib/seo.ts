import { PRIMARY_SITE_URL, primaryPageUrl } from './siteIdentity';

export function appBaseHref() {
  return PRIMARY_SITE_URL;
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
  element.href = primaryPageUrl(href, import.meta.env.BASE_URL);
}

/** Title, description, canonical and social tags for the page on screen. */
export function setPageMeta(title: string, description: string, pageHref: string) {
  pageHref = primaryPageUrl(pageHref, import.meta.env.BASE_URL);
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
  script.text = JSON.stringify(data, (key, value: unknown) => {
    if (typeof value !== 'string' || !/^https?:\/\//.test(value)) return value;
    const canonical = primaryPageUrl(value, import.meta.env.BASE_URL);
    // Page canonicals omit fragments; entity IDs require them to remain distinct.
    const fragment = key === '@id' ? new URL(value).hash : '';
    return fragment && !new URL(canonical).hash ? `${canonical}${fragment}` : canonical;
  });
}
