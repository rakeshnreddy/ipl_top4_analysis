/** Accept complete rows only, allowing for the producer's two-decimal rounding. */
export function validPositionChances(values: unknown, count: number): values is number[] {
  return Array.isArray(values)
    && count > 0
    && values.length === count
    && values.every((value) => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100)
    && Math.abs(values.reduce((sum, value) => sum + value, 0) - 100) <= count * 0.0051;
}
