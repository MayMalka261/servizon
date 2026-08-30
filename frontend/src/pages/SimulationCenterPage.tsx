import { useEffect, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { MessageSquare, Phone, ServerCrash } from 'lucide-react'

import { BarComparison } from '@/components/charts/BarComparison'
import { GaugeChart } from '@/components/charts/GaugeChart'
import { MetricTrendChart } from '@/components/charts/MetricTrendChart'
import { TrendChart } from '@/components/charts/TrendChart'
import { KpiCard } from '@/components/kpi/KpiCard'
import { BaselineMovedNotice } from '@/components/layout/BaselineMovedNotice'
import { CenterHeader } from '@/components/layout/CenterHeader'
import { LeverPanel } from '@/components/levers/LeverPanel'
import { RecommendationList } from '@/components/recommendations/RecommendationList'
import { ScenarioBar } from '@/components/scenarios/ScenarioBar'
import { Button, Card, Skeleton, Tabs, TabsList, TabsTrigger } from '@/components/ui'
import { useCenter, useLevers } from '@/hooks/useCenters'
import { useSimulation, useSnapshot } from '@/hooks/useSimulation'
import { useLeverStore } from '@/stores/leverStore'
import { TAB_ACCENT } from '@/simulation/theme'
import type { KpiId, SimulatedKpi, SimulationTab } from '@/types/api'

const DIGITAL_CHANNEL_LABELS = 'אתר · וואטסאפ · אימייל · טפסים · צ׳אט'

export function SimulationCenterPage() {
  const { centerId } = useParams<{ centerId: string }>()

  const tab = useLeverStore((state) => state.tab)
  const setTab = useLeverStore((state) => state.setTab)

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
  const isPhone = tab === 'phone_center'

  // The charts each tab shows are a fixed, curated set, so the metrics they
  // need are looked up by name rather than taken from whatever happens to be
  // in the KPI list.
  const kpi = useMemo(() => {
    const find = (id: KpiId) => result?.kpis.find((item) => item.id === id)
    return {
      sla: find('sla'),
      calls: find('incoming_calls'),
      abandonment: find('abandonment_rate'),
      aht: find('aht'),
      digitalContacts: find('digital_contacts'),
      digitalAht: find('aht_digital'),
    }
  }, [result])

  const trendWindow = useLeverStore((state) => state.trendWindow)

  const series = useMemo(() => {
    const raw = snapshot?.trend?.[tab]
    if (!raw) return undefined
    return {
      volume: raw.volume.slice(-trendWindow),
      abandonment: raw.abandonment.slice(-trendWindow),
      aht: raw.aht.slice(-trendWindow),
    }
  }, [snapshot, tab, trendWindow])

  // Digital share is the filter's own value, so the gauge is built from the
  // store rather than from a KPI card. Reading it back off the server would be
  // the same number by a longer route.
  const adoptionValue = useLeverStore((state) => state.values.digital_adoption)
  const adoptionBaseline = useLeverStore((state) => state.defaults.digital_adoption)

  const digitalShare: SimulatedKpi | undefined = useMemo(() => {
    if (adoptionBaseline === undefined) return undefined
    const current = adoptionBaseline / 100
    const scenario = (adoptionValue ?? adoptionBaseline) / 100
    const difference = scenario - current
    return {
      id: 'digital_adoption',
      label: 'אחוז פניות דיגיטלי',
      format: 'percent',
      direction: 'higher_is_better',
      current,
      scenario,
      difference,
      percentage: current === 0 ? 0 : (difference / current) * 100,
      trend: difference === 0 ? 0 : difference > 0 ? 1 : -1,
      is_improvement: difference > 0,
    }
  }, [adoptionValue, adoptionBaseline])

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
    // The page itself never scrolls. It fills the viewport below the header,
    // and the three columns scroll independently — dragging a filter should not
    // move the metric you are watching off screen, which is exactly what a
    // single page-level scrollbar caused.
    <main
      className="mx-auto flex max-w-[1800px] flex-col gap-4 p-4 sm:p-6 xl:h-[calc(100dvh-4rem)] xl:overflow-hidden"
      style={{ ['--tab-accent' as string]: accent }}
    >
      <div className="shrink-0 space-y-4">
        {center ? (
          <CenterHeader center={center} snapshot={snapshot} />
        ) : (
          <Skeleton className="h-28" />
        )}

        <BaselineMovedNotice />

        <Tabs value={tab} onValueChange={(value) => setTab(value as SimulationTab)}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TabsList>
              <TabsTrigger value="digital_channels" accent={TAB_ACCENT.digital_channels}>
                <MessageSquare className="h-4 w-4" />
                ערוצים דיגיטליים
              </TabsTrigger>
              <TabsTrigger value="phone_center" accent={TAB_ACCENT.phone_center}>
                <Phone className="h-4 w-4" />
                מוקד טלפוני
              </TabsTrigger>
            </TabsList>

            <p className="text-xs text-[var(--color-ink-muted)]">
              {isPhone ? 'תור טלפוני · מודל Erlang C על שעת השיא' : DIGITAL_CHANNEL_LABELS}
            </p>
          </div>
        </Tabs>

        {centerId ? <ScenarioBar centerId={centerId} tab={tab} /> : null}
      </div>

      {/* Three columns: filters, metrics, charts. Each is its own scroll
          container. Stacks on narrow screens, where the filter panel comes
          first because that is what the user came to touch. */}
      <div
        key={tab}
        className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)_380px]"
      >
        <LeverPanel levers={levers} snapshot={snapshot} tab={tab} />

        <section
          className="flex min-h-0 flex-col gap-3 xl:overflow-y-auto xl:pe-1"
          aria-label="מדדי השירות"
        >
          <div className="shrink-0">
            <h2 className="text-sm font-semibold text-[var(--color-ink)]">מדדי השירות</h2>
            <p className="text-[11px] text-[var(--color-ink-muted)]">
              מדד המושפע משינוי הפילטרים ומגמת השינוי מול המצב הנוכחי.
            </p>
          </div>

          {simulationPending || !result ? (
            <div className="grid shrink-0 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {Array.from({ length: 6 }, (_, index) => (
                <Skeleton key={index} className="h-28" />
              ))}
            </div>
          ) : (
            <div className="grid shrink-0 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {result.kpis.map((item, index) => (
                <KpiCard key={item.id} kpi={item} accent={accent} index={index} />
              ))}
            </div>
          )}

          {result ? <RecommendationList recommendations={result.recommendations} /> : null}
        </section>

        <section
          className="min-h-0 space-y-4 xl:overflow-y-auto xl:pe-1"
          aria-label="גרפים"
        >
          {isPhone ? (
            <>
              <GaugeChart kpi={kpi.sla} title="עמידה ב-SLA" target={0.9} />
              <TrendChart
                trend={series?.volume ?? []}
                scenarioDaily={kpi.calls?.scenario}
                title="מגמת נפח שיחות"
                accent={accent}
                windowDays={trendWindow}
              />
              <BarComparison kpis={result?.kpis ?? []} tab={tab} accent={accent} />
              <MetricTrendChart
                title="מגמת נטישה"
                description="שיעור הנטישה היומי בפועל, מול הצפוי בתרחיש."
                points={series?.abandonment ?? []}
                scenario={kpi.abandonment?.scenario}
                format="percent"
                accent={accent}
              />
              <MetricTrendChart
                title="זמן טיפול ממוצע"
                description="זמן הטיפול היומי בפועל, מול הצפוי בתרחיש."
                points={series?.aht ?? []}
                scenario={kpi.aht?.scenario}
                format="duration"
                accent={accent}
              />
            </>
          ) : (
            <>
              <GaugeChart kpi={digitalShare} title="אחוז פניות דיגיטלי" target={0.6} />
              <TrendChart
                trend={series?.volume ?? []}
                scenarioDaily={kpi.digitalContacts?.scenario}
                title="כמות פניות דיגיטליות לאורך זמן"
                accent={accent}
                windowDays={trendWindow}
              />
              <BarComparison kpis={result?.kpis ?? []} tab={tab} accent={accent} />
              <MetricTrendChart
                title="מגמת זמן טיפול בפניות"
                description="זמן הטיפול היומי בפועל, מול הצפוי בתרחיש."
                points={series?.aht ?? []}
                scenario={kpi.digitalAht?.scenario}
                format="duration"
                accent={accent}
              />
            </>
          )}
        </section>
      </div>
    </main>
  )
}
