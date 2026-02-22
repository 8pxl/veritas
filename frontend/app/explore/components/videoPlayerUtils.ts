/** Seconds to auto-dismiss the proposition popup */
export const DISMISS_AFTER = 8

/** Parse a timestamp string ("1:23", "0:01:23", or raw seconds) into seconds */
export function parseTimestamp(verifyAt: string): number {
  const num = Number(verifyAt)
  if (!isNaN(num)) return num
  const parts = verifyAt.split(":").map(Number)
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  return 0
}

/** Format seconds into a "m:ss" label */
export function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, "0")}`
}

/** Linear interpolation between two values */
export function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t
}

/** Interpolate a chart data point value (handles null values) */
export function lerpChartValue(
  start: number | null,
  end: number | null,
  t: number
): number | null {
  if (start === null && end === null) return null
  if (start === null) return end
  if (end === null) return start
  return Math.round(lerp(start, end, t))
}
