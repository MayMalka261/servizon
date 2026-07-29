import { AlertTriangle, CheckCircle2, Info, Lightbulb } from 'lucide-react'
import type { ComponentType } from 'react'

import { Card } from '@/components/ui'
import { SEVERITY_STYLES } from '@/simulation/theme'
import { cn } from '@/lib/utils'
import type { Recommendation, Severity } from '@/types/api'

const ICONS: Record<Severity, ComponentType<{ className?: string }>> = {
  critical: AlertTriangle,
  warning: AlertTriangle,
  positive: CheckCircle2,
  info: Info,
}

/**
 * Rule-based recommendations from the engine.
 *
 * Every sentence is assembled server-side from numbers the model actually
 * produced, so anything shown here can be traced back to the computation
 * behind it. That traceability is the point in a decision-support tool.
 */
export function RecommendationList({ recommendations }: { recommendations: Recommendation[] }) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-[var(--color-brand)]" />
        <h3 className="text-sm font-semibold text-[var(--color-ink)]">המלצות</h3>
      </div>

      <div className="space-y-2">
        {recommendations.map((recommendation) => {
          const style = SEVERITY_STYLES[recommendation.severity]
          const Icon = ICONS[recommendation.severity]

          return (
            <article
              key={recommendation.id}
              className="relative overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-muted)] p-3 ps-4"
            >
              <span
                className={cn('absolute inset-y-0 start-0 w-1', style.bar)}
                aria-hidden
              />
              <div className="flex items-start gap-2">
                <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', style.chip.split(' ')[1])} />
                <div className="min-w-0">
                  <h4 className="text-sm font-semibold text-[var(--color-ink)]">
                    {recommendation.title}
                  </h4>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-ink-soft)]">
                    {recommendation.body}
                  </p>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </Card>
  )
}
