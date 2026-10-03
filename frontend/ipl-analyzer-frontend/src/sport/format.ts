/** Monte Carlo odds: avoid printing 100% or 0% for outcomes that are only very likely or very unlikely. */
export function formatChance(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) {
    return '–';
  }
  if (value >= 99.95) {
    return '>99.9%';
  }
  if (value > 99) {
    return `${value.toFixed(1)}%`;
  }
  if (value >= 1) {
    return `${Math.round(value)}%`;
  }
  if (value >= 0.1) {
    return `${value.toFixed(1)}%`;
  }
  return value > 0 ? '<0.1%' : '–';
}
