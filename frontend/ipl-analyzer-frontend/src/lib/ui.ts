import type { CSSProperties } from 'react';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Scroll a section into view, without animation when the reader asked for reduced motion. */
export function scrollToSection(sectionId: string) {
  window.setTimeout(() => {
    document
      .getElementById(sectionId)
      ?.scrollIntoView?.({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }, 0);
}

/**
 * Background tint for a probability cell. Capped at 40% of the heat colour so the
 * text token keeps at least 4.5:1 contrast in both themes.
 */
export function heatStyle(value: number, tone: 'good' | 'bad'): CSSProperties | undefined {
  if (!(value > 0)) {
    return undefined;
  }
  const strength = Math.round(Math.min(value, 100) * 0.4);
  return { backgroundColor: `color-mix(in srgb, var(--heat-${tone}) ${strength}%, transparent)` };
}

export function ordinalSuffix(value: number) {
  const suffixes = ['th', 'st', 'nd', 'rd'];
  const lastTwo = value % 100;
  return suffixes[(lastTwo - 20) % 10] || suffixes[lastTwo] || suffixes[0];
}

const channel = (value: number) => (value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);

/**
 * Black or white, whichever has more contrast on a team colour. Team colours come
 * from the data feeds; their suggested text colour sometimes misses WCAG AA.
 */
export function readableOn(background: string, fallback = '#ffffff') {
  const hex = background.trim().replace(/^#/, '');
  const full = hex.length === 3 ? [...hex].map((digit) => digit + digit).join('') : hex;
  if (!/^[0-9a-f]{6}$/i.test(full)) {
    return fallback;
  }
  const [r, g, b] = [0, 2, 4].map((start) => channel(parseInt(full.slice(start, start + 2), 16) / 255));
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return (luminance + 0.05) / 0.05 > 1.05 / (luminance + 0.05) ? '#000000' : '#ffffff';
}
