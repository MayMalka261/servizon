import { useEffect, useState } from 'react'

/**
 * Settles a fast-changing value.
 *
 * Used on the lever panel so a slider drag produces one request when the
 * user stops, not sixty while they move.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])

  return settled
}
