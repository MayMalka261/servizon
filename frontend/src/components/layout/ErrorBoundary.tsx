import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/Button'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Catches render errors so one broken chart cannot take the screen down.
 *
 * Errors are logged to the console only — there is nowhere off-network to send
 * them, and there must not be.
 */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[Servizon] render error', error, info.componentStack)
  }

  override render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <div className="card max-w-md p-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-critical-soft)]">
            <AlertTriangle className="h-6 w-6 text-[var(--color-critical)]" />
          </div>
          <h1 className="text-lg font-semibold text-[var(--color-ink)]">אירעה שגיאה בתצוגה</h1>
          <p className="mt-2 text-sm leading-relaxed text-[var(--color-ink-muted)]">
            המסך נתקל בבעיה בלתי צפויה. הנתונים במערכת לא נפגעו — כל הסימולציות רצות על עותק
            זמני בלבד.
          </p>
          <p className="mt-3 truncate font-mono text-xs text-[var(--color-ink-muted)]">
            {error.message}
          </p>
          <Button
            variant="primary"
            className="mt-5 w-full"
            onClick={() => window.location.reload()}
          >
            טעינה מחדש
          </Button>
        </div>
      </div>
    )
  }
}
