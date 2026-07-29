import { Link } from 'react-router-dom'
import { ChevronLeft, Clock, Users } from 'lucide-react'

import { Badge } from '@/components/ui'
import { STATUS_STYLES } from '@/simulation/theme'
import { formatDateTime, formatNumber } from '@/simulation/format'
import { cn } from '@/lib/utils'
import type { ServiceCenter, Snapshot } from '@/types/api'

export function CenterHeader({
  center,
  snapshot,
}: {
  center: ServiceCenter
  snapshot: Snapshot | undefined
}) {
  const status = STATUS_STYLES[center.status]

  return (
    <div className="card p-4">
      <nav aria-label="ניווט" className="mb-2 flex items-center gap-1 text-xs text-[var(--color-ink-muted)]">
        <Link to="/" className="transition-colors hover:text-[var(--color-brand)]">
          מוקדי שירות
        </Link>
        <ChevronLeft className="h-3 w-3" />
        <span className="font-medium text-[var(--color-ink-soft)]">מרכז הסימולציה</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold text-[var(--color-ink)]">{center.name}</h1>
            <Badge className={status.chip}>
              <span className={cn('h-1.5 w-1.5 rounded-full', status.dot)} />
              {center.status_label}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
            <span className="ltr">{center.id}</span> · {center.center_type_label} ·{' '}
            {center.district_label} · מוקד {center.size_label}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
          <Fact
            icon={<Users className="h-3.5 w-3.5" />}
            label="מצבת"
            value={`${formatNumber(center.headcount)} נציגים`}
          />
          <Fact
            icon={<Clock className="h-3.5 w-3.5" />}
            label="שעות פעילות"
            value={
              center.working_hours_per_day === 24 ? '24/7' : `${center.working_hours_per_day} שעות`
            }
          />
          {snapshot ? (
            <div className="text-xs text-[var(--color-ink-muted)]">
              נתונים נכון ל-{formatDateTime(snapshot.captured_at)}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function Fact({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[11px] text-[var(--color-ink-muted)]">
        {icon}
        {label}
      </div>
      <p className="tnum mt-0.5 font-semibold text-[var(--color-ink)]">{value}</p>
    </div>
  )
}
