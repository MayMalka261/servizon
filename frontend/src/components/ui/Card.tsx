import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Draws the coloured rule along the card's top edge. */
  accent?: string
}

export function Card({ className, accent, style, ...props }: CardProps) {
  return (
    <div
      className={cn('card', accent && 'card-accent', className)}
      style={accent ? { ...style, ['--accent' as string]: accent } : style}
      {...props}
    />
  )
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-[var(--color-ink)]">{title}</h2>
        {description ? (
          <p className="mt-0.5 text-sm text-[var(--color-ink-muted)]">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  )
}
