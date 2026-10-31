import { describe, expect, it } from 'vitest';
import { validPositionChances } from './f1Data';

describe('validPositionChances', () => {
  it('accepts one finite percentage per exact position, including zero', () => {
    expect(validPositionChances([54, 31, 14, 1], 4)).toBe(true);
    expect(validPositionChances([0, 0, 0, 100], 4)).toBe(true);
    expect(validPositionChances(Array.from({ length: 23 }, () => 4.35), 23)).toBe(true);
  });

  it.each([
    undefined, null, { title: 100 }, [100], [100, 0, 0], [100, 0, 0, 0, 0],
    [101, 0, 0, -1], [null, 0, 0, 100], ['0', 0, 0, 100], [NaN, 0, 0, 100],
    [Infinity, 0, 0, 0], [54, 31, 14, 0], [0, 0, 0, 0],
  ].map((values) => ({ values })))('rejects missing, malformed or incomplete distributions: $values', ({ values }) => {
    expect(validPositionChances(values, 4)).toBe(false);
  });
});
