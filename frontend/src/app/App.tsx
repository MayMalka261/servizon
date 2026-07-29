import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppHeader } from '@/components/layout/AppHeader'
import { ErrorBoundary } from '@/components/layout/ErrorBoundary'
import { Skeleton } from '@/components/ui/primitives'
import { CentersPage } from '@/pages/CentersPage'

// The simulation and comparison screens pull in Recharts and Framer Motion.
// Deferring them keeps the centers list — the first thing anyone sees — light.
const SimulationCenterPage = lazy(() =>
  import('@/pages/SimulationCenterPage').then((m) => ({ default: m.SimulationCenterPage })),
)
const ComparePage = lazy(() =>
  import('@/pages/ComparePage').then((m) => ({ default: m.ComparePage })),
)

function RouteFallback() {
  return (
    <div className="mx-auto max-w-[1800px] space-y-4 p-4 sm:p-6">
      <Skeleton className="h-20 w-full" />
      <div className="grid gap-4 lg:grid-cols-[280px_1fr_340px]">
        <Skeleton className="h-[600px]" />
        <Skeleton className="h-[600px]" />
        <Skeleton className="h-[600px]" />
      </div>
    </div>
  )
}

export function App() {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<CentersPage />} />
            <Route path="/centers/:centerId" element={<SimulationCenterPage />} />
            <Route path="/centers/:centerId/compare" element={<ComparePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </div>
  )
}
