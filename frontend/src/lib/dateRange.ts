/** ISO date (YYYY-MM-DD) helpers for the trend range picker. */

export function shiftIsoDate(iso: string, deltaDays: number): string {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + deltaDays)
  return date.toISOString().slice(0, 10)
}

/** Clamps an ISO date into [min, max], inclusive. */
export function clampIsoDate(iso: string, min: string, max: string): string {
  if (iso < min) return min
  if (iso > max) return max
  return iso
}
