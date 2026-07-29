import { Link } from 'react-router-dom'
import { ArrowLeft, Clock, PhoneCall, Users } from 'lucide-react'

import { Badge, Card } from '@/components/ui'
import { formatNumber } from '@/simulation/format'
import { STATUS_STYLES } from '@/simulation/theme'
import { cn } from '@/lib/utils'
import type { ServiceCenter } from '@/types/api'

/** Colours the headline SLA figure by how far it is from acceptable. */
function slaTone(slaPct: number): string {
  if (slaPct >= 90) return 'text-[var(--color-positive)]'
  if (slaPct >= 80) return 'text-[var(--color-warning)]'
  return 'text-[var(--color-critical)]'
}

export function CenterCard({ center }: { center: ServiceCenter }) {
  const status = STATUS_STYLES[center.status]

  return (
    <Link
      to={`/centers/${center.id}`}
      className="group block h-full focus-visible:outline-none"
      aria-label={`פתיחת מרכז סימולציה עבור ${center.name}`}
    >
      <Card className="flex h-full flex-col p-5 transition-all group-hover:-translate-y-0.5 group-hover:shadow-[var(--shadow-raised)] group-focus-visible:ring-2 group-focus-visible:ring-[var(--color-brand)]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-[var(--color-ink)]">{center.name}</h3>
            <p className="mt-0.5 text-xs text-[var(--color-ink-muted)]">
              <span className="ltr">{center.id}</span> · {center.center_type_label} ·{' '}
              {center.district_label}
            </p>
          </div>
          <Badge className={cn('shrink-0', status.chip)}>
            <span className={cn('h-1.5 w-1.5 rounded-full', status.dot)} />
            {center.status_label}
          </Badge>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-3">
          <Metric
            label="פניות ליום"
            value={formatNumber(center.daily_contacts)}
            icon={<PhoneCall className="h-3.5 w-3.5" />}
          />
          <Metric
            label="עמידה ב-SLA"
            value={`${center.sla_pct}%`}
            icon={<Clock className="h-3.5 w-3.5" />}
            valueClassName={slaTone(center.sla_pct)}
          />
          <Metric
            label="נטישה"
            value={`${center.abandonment_pct}%`}
            icon={<Users className="h-3.5 w-3.5" />}
          />
        </div>

        <div className="mt-auto flex items-center justify-between border-t border-[var(--color-line)] pt-4">
          <span className="text-xs text-[var(--color-ink-muted)]">
            {center.headcount} נציגים · מוקד {center.size_label} ·{' '}
            {center.working_hours_per_day === 24 ? '24/7' : `${center.working_hours_per_day} שעות`}
          </span>
          <span className="flex items-center gap-1 text-xs font-medium text-[var(--color-brand)]">
            סימולציה
            <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
          </span>
        </div>
      </Card>
    </Link>
  )
}

function Metric({
  label,
  value,
  icon,
  valueClassName,
}: {
  label: string
  value: string
  icon: React.ReactNode
  valueClassName?: string
}) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[var(--color-ink-muted)]">
        {icon}
        <span className="text-[11px]">{label}</span>
      </div>
      <p className={cn('tnum mt-1 text-lg font-semibold', valueClassName ?? 'text-[var(--color-ink)]')}>
        {value}
      </p>
    </div>
  )
}
