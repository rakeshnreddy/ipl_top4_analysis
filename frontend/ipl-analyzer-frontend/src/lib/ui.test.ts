import { describe, expect, it } from 'vitest';
import { heatStyle, ordinalSuffix, readableOn, samePageHref } from './ui';

describe('readableOn', () => {
  it('picks the text colour with more contrast on a team colour', () => {
    // White on Bengals orange is 3.4:1; black clears AA.
    expect(readableOn('#fb4f14')).toBe('#000000');
    expect(readableOn('#034694')).toBe('#ffffff');
    expect(readableOn('#fff')).toBe('#000000');
  });

  it('falls back when the colour is not a hex value', () => {
    expect(readableOn('rebeccapurple', '#eeeeee')).toBe('#eeeeee');
  });
});

describe('heatStyle', () => {
  it('caps the tint so cell text keeps its contrast', () => {
    expect(heatStyle(100, 'good')?.backgroundColor).toBe('color-mix(in srgb, var(--heat-good) 40%, transparent)');
    expect(heatStyle(0, 'bad')).toBeUndefined();
  });
});

describe('ordinalSuffix', () => {
  it('handles the teens', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 23].map(ordinalSuffix)).toEqual(['st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'st', 'nd', 'rd']);
  });
});

describe('samePageHref', () => {
  it('keeps the current path and query, so a <base href> cannot send the link to the home page', () => {
    window.history.replaceState(null, '', '/ipl_top4_analysis/?league=mls-2026');
    expect(samePageHref('#fixtures')).toBe('/ipl_top4_analysis/?league=mls-2026#fixtures');
    expect(samePageHref('team=NSH')).toBe('/ipl_top4_analysis/?league=mls-2026#team=NSH');
    window.history.replaceState(null, '', '/');
  });
});
