import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

import { formatKpiValue } from '@/simulation/format'
import type { KpiFormat } from '@/types/api'

const DURATION_MS = 380

/**
 * Counts a KPI from its previous value to its next one.
 *
 * The motion is doing real work: when six cards update at once, a number that
 * travels tells you it moved and roughly how far, which a value that simply
 * swaps does not. Respects `prefers-reduced-motion` — on a screen this dense,
 * that matters.
 */
export function AnimatedValue({ value, format }: { value: number; format: KpiFormat }) {
  const reduceMotion = useReducedMotion()
  const [display, setDisplay] = useState(value)
  const fromRef = useRef(value)
  const frameRef = useRef<number>(0)

  useEffect(() => {
    if (reduceMotion) {
      fromRef.current = value
      setDisplay(value)
      return
    }

    const from = fromRef.current
    if (from === value) return

    const start = performance.now()

    function step(now: number) {
      const progress = Math.min((now - start) / DURATION_MS, 1)
      // Ease-out cubic: fast departure, gentle landing.
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(from + (value - from) * eased)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step)
      } else {
        fromRef.current = value
      }
    }

    frameRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frameRef.current)
  }, [value, reduceMotion])

  return <span className="tnum">{formatKpiValue(display, format)}</span>
}
