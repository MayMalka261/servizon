import { AnimatePresence, motion } from 'framer-motion'
import { RefreshCw, X } from 'lucide-react'

import { useLeverStore } from '@/stores/leverStore'

/**
 * Shown when a background refresh moved the baseline under an open scenario.
 *
 * The lever positions are deliberately left alone — the scenario is the user's
 * work, and a data refresh is not a reason to discard it. The results are
 * simply recomputed against the new baseline and this says so, so nobody is
 * left wondering why the numbers shifted while they were reading them.
 */
export function BaselineMovedNotice() {
  const baselineMoved = useLeverStore((state) => state.baselineMoved)
  const acknowledge = useLeverStore((state) => state.acknowledgeBaselineMove)

  return (
    <AnimatePresence>
      {baselineMoved ? (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          role="status"
          className="flex items-center gap-3 rounded-lg border border-[var(--color-digital)]/30 bg-[var(--color-digital-soft)] px-4 py-2.5"
        >
          <RefreshCw className="h-4 w-4 shrink-0 text-[var(--color-digital)]" />
          <p className="text-sm text-[var(--color-ink-soft)]">
            נתוני המוקד התעדכנו. התרחיש שלך נשמר וחושב מחדש מול הנתונים החדשים.
          </p>
          <button
            type="button"
            onClick={acknowledge}
            aria-label="סגירת ההודעה"
            className="ms-auto rounded-md p-1 text-[var(--color-ink-muted)] transition-colors hover:bg-white/60"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
