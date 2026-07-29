import { useEffect, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { MessageSquare, Phone, ServerCrash } from 'lucide-react'

import { BarComparison } from '@/components/charts/BarComparison'
import { GaugeChart } from '@/components/charts/GaugeChart'
import { ServiceRadarChart } from '@/components/charts/RadarChart'
import { TrendChart } from '@/components/charts/TrendChart'
import { WaterfallChart } from '@/components/charts/WaterfallChart'
import { KpiCard } from '@/components/kpi/KpiCard'
import { BaselineMovedNotice } from '@/components/layout/BaselineMovedNotice'
import { CenterHeader } from '@/components/layout/CenterHeader'
import { LeverPanel } from '@/components/levers/LeverPanel'
import { RecommendationList } from '@/components/recommendations/RecommendationList'
import { ScenarioBar } from '@/components/scenarios/ScenarioBar'
import { Button, Card, Skeleton, Tabs, TabsList, TabsTrigger } from '@/components/ui'
import { useCenter, useLevers } from '@/hooks/useCenters'
import { useSimulation, useSnapshot } from '@/hooks/useSimulation'
import { useHasScenario, useLeverStore } from '@/stores/leverStore'
import { ACCENTS } from '@/simulation/theme'
import type { KpiId, SimulationTab } from '@/types/api'

/** The tab drives the accent colour carried through cards, sliders and charts. */
const TAB_ACCENT: Record<SimulationTab, string> = {
  digital_channels: ACCENTS.digital.color,
  phone_center: ACCENTS.workforce.color,
}

const DIGITAL_CHANNEL_LABELS = 'אתר · וואטסאפ · אימייל · טפסים · צ׳אט'

export function SimulationCenterPage() {
  const { centerId } = useParams<{ centerId: string }>()

  const tab = useLeverStore((state) => state.tab)
  const setTab = useLeverStore((state) => state.setTab)
  const hasScenario = useHasScenario()

  const { data: center, isError: centerError, error } = useCenter(centerId)
  const { data: snapshot } = useSnapshot(centerId)
  const { data: levers } = useLevers()
  const { data: result, isPending: simulationPending } = useSimulation(centerId, tab)

  // Leaving the screen must not carry one center's scenario into the next.
  useEffect(() => {
    return () => {
      useLeverStore.setState({ centerId: null, values: {}, defaults: {}, touched: {} })
    }
  }, [])

  const accent = TAB_ACCENT[tab]

  const incomingCalls = useMemo(
    () => result?.kpis.find((kpi) => kpi.id === ('incoming_calls' satisfies KpiId)),
    [result],
  )
  const slaKpi = useMemo(() => result?.kpis.find((kpi) => kpi.id === ('sla' satisfies KpiId)), [result])

  if (centerError) {
    return (
      <main className="mx-auto max-w-2xl p-6">
        <Card className="flex flex-col items-center px-6 py-16 text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-critical-soft)]">
            <ServerCrash className="h-6 w-6 text-[var(--color-critical)]" />
          </div>
          <h1 className="font-semibold text-[var(--color-ink)]">לא ניתן לטעון את המוקד</h1>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{(error as Error).message}</p>
          <Link to="/" className="mt-5">
            <Button variant="primary" size="sm">
              חזרה לרשימת המוקדים
            </Button>
          </Link>
        </Card>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-[1800px] space-y-4 p-4 sm:p-6">
      {center ? <CenterHeader center={center} snapshot={snapshot} /> : <Skeleton className="h-28" />}

      <BaselineMovedNotice />

      <Tabs value={tab} onValueChange={(value) => setTab(value as SimulationTab)}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="digital_channels">
              <MessageSquare className="h-4 w-4" />
              ערוצים דיגיטליים
            </TabsTrigger>
            <TabsTrigger value="phone_center">
              <Phone className="h-4 w-4" />
              מוקד טלפוני
            </TabsTrigger>
          </TabsList>

          <p className="text-xs text-[var(--color-ink-muted)]">
            {tab === 'digital_channels'
              ? DIGITAL_CHANNEL_LABELS
              : 'תור טלפוני · מודל Erlang C על שעת השיא'}
          </p>
        </div>
      </Tabs>

      {centerId ? <ScenarioBar centerId={centerId} tab={tab} /> : null}

      {/* Three columns, matching the deck: levers, metrics, charts. Stacks on
          narrow screens, where the lever panel comes first because that is
          what the user came to touch. */}
      <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
        <LeverPanel levers={levers} snapshot={snapshot} tab={tab} />

        <section className="space-y-4" aria-label="מדדי השירות">
          <div>
            <h2 className="font-semibold text-[var(--color-ink)]">מדדי השירות</h2>
            <p className="text-xs text-[var(--color-ink-muted)]">
              מדד המושפע משינוי המנוף התפעולי ומגמת השינוי מול המצב הנוכחי.
            </p>
          </div>

          {simulationPending || !result ? (
            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
              {Array.from({ length: 6 }, (_, index) => (
                <Skeleton key={index} className="h-36" />
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
              {result.kpis.map((kpi) => (
                <KpiCard key={kpi.id} kpi={kpi} accent={accent} />
              ))}
            </div>
          )}

          {result ? <RecommendationList recommendations={result.recommendations} /> : null}
        </section>

        <section className="space-y-4" aria-label="גרפים">
          <GaugeChart kpi={slaKpi} />
          <TrendChart
            trend={snapshot?.trend ?? []}
            scenarioDaily={incomingCalls?.scenario}
            accent={accent}
          />
          <WaterfallChart steps={result?.waterfall ?? []} hasScenario={hasScenario} />
          <BarComparison kpis={result?.kpis ?? []} accent={accent} />
          <ServiceRadarChart kpis={result?.kpis ?? []} />
        </section>
      </div>
    </main>
  )
}
