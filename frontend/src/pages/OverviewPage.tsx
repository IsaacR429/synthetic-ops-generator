import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'

import {
  ApiError,
  getEventActivity,
  listEnterprises,
  listRuns,
  listScenarios,
} from '../api/client'

import type {
  EventActivityResponse,
  EventActivityWindow,
  RunResponse,
  RunStatus,
} from '../types/api'

interface OverviewMetrics {
  activeRuns: number
  totalRuns: number
  generatedEvents: number
  scenarios: number
  enterprises: number
  failedRuns: number
}

interface ScenarioCoverageItem {
  enterpriseId: string
  enterpriseName: string
  scenarioCount: number
}

function formatCount(value: number): string {
  return new Intl.NumberFormat().format(value)
}

function formatLabel(value: string): string {
  return value
    .split('_')
    .map(
      (word) =>
        word.charAt(0).toUpperCase() +
        word.slice(1),
    )
    .join(' ')
}

function formatRunDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function runStatusClasses(
  status: RunStatus,
): string {
  const classes: Record<RunStatus, string> = {
    running:
      'border-violet-400/20 bg-violet-500/10 text-violet-300',
    completed:
      'border-emerald-400/20 bg-emerald-500/10 text-emerald-300',
    failed:
      'border-red-400/20 bg-red-500/10 text-red-300',
    stopped:
      'border-amber-400/20 bg-amber-500/10 text-amber-300',
  }

  return classes[status]
}

type MetricAccent =
  | 'violet'
  | 'indigo'
  | 'cyan'
  | 'sky'
  | 'emerald'
  | 'rose'

const METRIC_ACCENTS: Record<
  MetricAccent,
  {
    glow: string
    line: string
    dot: string
    value: string
    hover: string
  }
> = {
  violet: {
    glow:
      'from-violet-500/[0.16] via-indigo-500/[0.05] to-transparent',
    line:
      'from-violet-400/80 via-indigo-400/45 to-transparent',
    dot: 'bg-violet-300',
    value: 'text-violet-100',
    hover: 'hover:border-violet-400/20',
  },

  indigo: {
    glow:
      'from-indigo-500/[0.16] via-blue-500/[0.05] to-transparent',
    line:
      'from-indigo-400/80 via-blue-400/45 to-transparent',
    dot: 'bg-indigo-300',
    value: 'text-indigo-100',
    hover: 'hover:border-indigo-400/20',
  },

  cyan: {
    glow:
      'from-cyan-500/[0.15] via-teal-500/[0.05] to-transparent',
    line:
      'from-cyan-400/80 via-teal-400/45 to-transparent',
    dot: 'bg-cyan-300',
    value: 'text-cyan-100',
    hover: 'hover:border-cyan-400/20',
  },

  sky: {
    glow:
      'from-sky-500/[0.15] via-indigo-500/[0.05] to-transparent',
    line:
      'from-sky-400/80 via-indigo-400/45 to-transparent',
    dot: 'bg-sky-300',
    value: 'text-sky-100',
    hover: 'hover:border-sky-400/20',
  },

  emerald: {
    glow:
      'from-emerald-500/[0.15] via-teal-500/[0.05] to-transparent',
    line:
      'from-emerald-400/80 via-teal-400/45 to-transparent',
    dot: 'bg-emerald-300',
    value: 'text-emerald-100',
    hover: 'hover:border-emerald-400/20',
  },

  rose: {
    glow:
      'from-rose-500/[0.14] via-orange-500/[0.04] to-transparent',
    line:
      'from-rose-400/80 via-orange-400/35 to-transparent',
    dot: 'bg-rose-300',
    value: 'text-rose-100',
    hover: 'hover:border-rose-400/20',
  },
}

interface MetricCardProps {
  label: string
  value: string
  detail: string
  accent: MetricAccent
}

function MetricCard({
  label,
  value,
  detail,
  accent,
}: MetricCardProps) {
  const tone = METRIC_ACCENTS[accent]

  return (
    <div
      className={`group relative min-w-0 overflow-hidden rounded-xl border border-white/[0.08] bg-[#101326]/80 p-4 shadow-[0_12px_35px_rgba(2,6,23,0.16)] transition-all duration-200 hover:-translate-y-0.5 ${tone.hover}`}
    >
      <div
        className={`pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-br ${tone.glow}`}
      />

      <div
        className={`pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r ${tone.line}`}
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[9px] font-semibold uppercase tracking-[0.17em] text-slate-500">
            {label}
          </div>

          <div
            className={`mt-2 font-mono text-[22px] font-semibold tracking-[-0.035em] ${tone.value}`}
          >
            {value}
          </div>
        </div>

        <div className="flex h-8 w-8 shrink-0 items-end justify-center gap-[3px] rounded-lg border border-white/[0.07] bg-black/10 pb-2">
          <span
            className={`h-2 w-[3px] rounded-full ${tone.dot} opacity-40`}
          />
          <span
            className={`h-4 w-[3px] rounded-full ${tone.dot} opacity-75`}
          />
          <span
            className={`h-3 w-[3px] rounded-full ${tone.dot}`}
          />
        </div>
      </div>

      <div className="relative mt-2 truncate text-[11px] text-slate-400">
        {detail}
      </div>

      <div className="relative mt-3 h-px overflow-hidden bg-white/[0.045]">
        <div
          className={`h-full w-16 bg-gradient-to-r ${tone.line}`}
        />
      </div>
    </div>
  )
}

function formatActivityTime(value: string): string {
  const date = new Date(value)
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

interface ChartPoint {
  x: number
  y: number
}

function buildTickIndexes(
  length: number,
  targetTicks = 6,
): number[] {
  if (length <= 1) {
    return [0]
  }

  if (length <= targetTicks) {
    return Array.from({ length }, (_, index) => index)
  }

  const raw = Array.from(
    { length: targetTicks },
    (_, index) =>
      Math.round(
        (index * (length - 1)) /
          (targetTicks - 1),
      ),
  )

  return [...new Set(raw)]
}

function buildSmoothPath(
  points: ChartPoint[],
): string {
  if (points.length === 0) {
    return ''
  }

  let d = `M ${points[0].x} ${points[0].y}`

  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index]
    const next = points[index + 1]
    const midX = (current.x + next.x) / 2

    d += ` C ${midX} ${current.y}, ${midX} ${next.y}, ${next.x} ${next.y}`
  }

  return d
}

interface EventActivityChartProps {
  activity: EventActivityResponse
}

function EventActivityChart({
  activity,
}: EventActivityChartProps) {
  const totalEvents = activity.buckets.reduce(
    (total, bucket) => total + bucket.event_count,
    0,
  )

  const peakEvents = Math.max(
    ...activity.buckets.map((b) => b.event_count),
    1,
  )

  const width = 600
  const height = 220
  const paddingX = 16
  const topPadding = 24
  const bottomPadding = 30

  const plotWidth = width - paddingX * 2
  const baselineY = height - bottomPadding

  const bucketSlotWidth =
    plotWidth /
    Math.max(activity.buckets.length, 1)

  const barWidth = Math.max(
    3,
    Math.min(18, bucketSlotWidth * 0.42),
  )

  const bucketCount = activity.buckets.length

  const points: ChartPoint[] = activity.buckets.map(
    (bucket, index) => {
      const x =
        paddingX +
        (index / Math.max(bucketCount - 1, 1)) *
          plotWidth

      const scaledRatio =
        bucket.event_count <= 0
          ? 0
          : Math.sqrt(
              bucket.event_count / peakEvents,
            )

      const y =
        topPadding +
        (1 - scaledRatio) * (height - topPadding - bottomPadding)

      return { x, y }
    },
  )

  const smoothCurve = buildSmoothPath(points)

  const areaPath =
    points.length > 0
      ? `${smoothCurve} L ${points[points.length - 1].x} ${baselineY} L ${points[0].x} ${baselineY} Z`
      : ''

  const tickIndexes = buildTickIndexes(bucketCount, 6)

  const peakIndex = activity.buckets.findIndex(
    (b) => b.event_count === peakEvents && peakEvents > 0,
  )

  const nonZeroIndexes = activity.buckets
    .map((bucket, index) =>
      bucket.event_count > 0 ? index : -1,
    )
    .filter((index) => index >= 0)

  const markerIndexes = new Set<number>(
    [
      peakIndex,
      nonZeroIndexes[0],
      nonZeroIndexes[nonZeroIndexes.length - 1],
    ].filter((idx) => idx !== undefined && idx >= 0),
  )

  return (
    <div className="px-5 py-6">
      <div className="relative">
        <div className="mb-4 flex items-center justify-between text-xs">
          <div className="text-slate-400">
            <span className="font-mono text-sm font-semibold text-cyan-200">
              {formatCount(totalEvents)}
            </span>{' '}
            retained events in this window
          </div>

          <div className="flex items-center gap-3 font-mono text-[10px] text-slate-500">
            <span>
              Peak: {formatCount(peakEvents)}{' '}
              evt/bucket
            </span>
          </div>
        </div>

        {totalEvents > 0 ? (
          <div className="relative">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              className="h-56 w-full overflow-visible"
              preserveAspectRatio="none"
            >
              <defs>
                <linearGradient
                  id="activityAreaGradient"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor="rgb(34, 211, 238)"
                    stopOpacity="0.13"
                  />
                  <stop
                    offset="60%"
                    stopColor="rgb(139, 92, 246)"
                    stopOpacity="0.045"
                  />
                  <stop
                    offset="100%"
                    stopColor="rgb(139, 92, 246)"
                    stopOpacity="0.0"
                  />
                </linearGradient>

                <linearGradient
                  id="activityStrokeGradient"
                  x1="0"
                  y1="0"
                  x2="1"
                  y2="0"
                >
                  <stop
                    offset="0%"
                    stopColor="rgb(167, 139, 250)"
                  />
                  <stop
                    offset="50%"
                    stopColor="rgb(56, 189, 248)"
                  />
                  <stop
                    offset="100%"
                    stopColor="rgb(34, 211, 238)"
                  />
                </linearGradient>

                <filter
                  id="glow"
                  x="-20%"
                  y="-20%"
                  width="140%"
                  height="140%"
                >
                  <feGaussianBlur
                    stdDeviation="1.8"
                    result="blur"
                  />
                  <feComposite
                    in="SourceGraphic"
                    in2="blur"
                    operator="over"
                  />
                </filter>
              </defs>

              {activity.buckets.map((bucket, index) => {
                if (bucket.event_count === 0) {
                  return null
                }

                const point = points[index]
                const barTop = point.y
                const barHeight = baselineY - barTop
                const isPeak =
                  bucket.event_count === peakEvents

                return (
                  <rect
                    key={`bar-${index}`}
                    x={point.x - barWidth / 2}
                    y={barTop}
                    width={barWidth}
                    height={Math.max(barHeight, 2)}
                    rx={barWidth / 2}
                    fill={
                      isPeak
                        ? 'rgba(103,232,249,0.20)'
                        : 'rgba(129,140,248,0.10)'
                    }
                    stroke={
                      isPeak
                        ? 'rgba(103,232,249,0.28)'
                        : 'rgba(129,140,248,0.10)'
                    }
                    strokeWidth="1"
                    vectorEffect="non-scaling-stroke"
                  />
                )
              })}

              <path
                d={areaPath}
                fill="url(#activityAreaGradient)"
              />

              <path
                d={smoothCurve}
                fill="none"
                stroke="rgba(103,232,249,0.10)"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
                filter="url(#glow)"
              />

              <path
                d={smoothCurve}
                fill="none"
                stroke="url(#activityStrokeGradient)"
                strokeWidth="2.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {points.map((point, index) =>
                markerIndexes.has(index) ? (
                  <g key={index}>
                    <circle
                      cx={point.x}
                      cy={point.y}
                      r="4"
                      fill="rgba(8,15,32,0.92)"
                    />
                    <circle
                      cx={point.x}
                      cy={point.y}
                      r="2.25"
                      fill="#67e8f9"
                    />
                  </g>
                ) : null,
              )}

              {peakIndex >= 0 &&
                points[peakIndex] && (
                  <g>
                    <line
                      x1={points[peakIndex].x}
                      x2={points[peakIndex].x}
                      y1={topPadding}
                      y2={points[peakIndex].y - 8}
                      stroke="rgba(103,232,249,0.16)"
                      strokeDasharray="3 5"
                      vectorEffect="non-scaling-stroke"
                    />

                    <text
                      x={points[peakIndex].x}
                      y={Math.max(
                        14,
                        points[peakIndex].y - 12,
                      )}
                      textAnchor="middle"
                      fill="rgba(165,243,252,0.85)"
                      fontSize="10"
                      fontFamily="monospace"
                    >
                      {formatCount(peakEvents)}
                    </text>
                  </g>
                )}
            </svg>

            <div
              className="mt-2 grid text-[10px] font-medium text-slate-600"
              style={{
                gridTemplateColumns: `repeat(${tickIndexes.length}, minmax(0, 1fr))`,
              }}
            >
              {tickIndexes.map(
                (index, position) => (
                  <div
                    key={index}
                    className={[
                      position === 0
                        ? 'text-left'
                        : position ===
                            tickIndexes.length -
                              1
                          ? 'text-right'
                          : 'text-center',
                    ].join(' ')}
                  >
                    {formatActivityTime(
                      activity.buckets[
                        index
                      ].started_at,
                    )}
                  </div>
                ),
              )}
            </div>
          </div>
        ) : (
          <div className="relative flex h-72 flex-col items-center justify-center">
            <div className="relative flex size-14 items-center justify-center rounded-2xl border border-cyan-400/[0.08] bg-cyan-500/[0.03]">
              <div className="absolute h-px w-8 bg-gradient-to-r from-violet-400/40 to-cyan-400/40" />
              <span className="size-2 rounded-full bg-cyan-300/60" />
            </div>

            <div className="mt-4 text-sm font-semibold text-slate-300">
              No event activity
            </div>

            <div className="mt-1 text-xs text-slate-600">
              No retained events were generated
              during this window.
            </div>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3 text-[10px]">
          <div className="flex items-center gap-2 uppercase tracking-[0.14em] text-slate-600">
            <span className="size-2 rounded-full bg-gradient-to-br from-violet-300 to-cyan-300" />
            Persisted event generation
          </div>

          <div className="font-mono text-slate-600">
            {formatActivityTime(
              activity.start_time,
            )}{' '}
            →{' '}
            {formatActivityTime(
              activity.end_time,
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export function OverviewPage() {
  const navigate = useNavigate()

  const [metrics, setMetrics] =
    useState<OverviewMetrics | null>(null)
  const [recentRuns, setRecentRuns] =
    useState<RunResponse[]>([])
  const [activeRunItems, setActiveRunItems] =
    useState<RunResponse[]>([])
  const [
    scenarioCoverage,
    setScenarioCoverage,
  ] = useState<ScenarioCoverageItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [
    activityWindow,
    setActivityWindow,
  ] = useState<EventActivityWindow>('24h')

  const [
    eventActivity,
    setEventActivity,
  ] = useState<EventActivityResponse | null>(null)

  const [
    activityLoading,
    setActivityLoading,
  ] = useState(true)

  const [
    activityError,
    setActivityError,
  ] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadOverview() {
      try {
        setLoading(true)
        setError(null)

        const [
          runs,
          scenarios,
          enterprises,
        ] = await Promise.all([
          listRuns(),
          listScenarios(),
          listEnterprises(),
        ])

        if (!active) {
          return
        }

        const activeRuns = runs.filter(
          (run) => run.status === 'running',
        ).length

        const currentRuns = runs
          .filter((run) => run.status === 'running')
          .sort(
            (left, right) =>
              new Date(right.started_at).getTime() -
              new Date(left.started_at).getTime(),
          )

        setActiveRunItems(currentRuns)

        const failedRuns = runs.filter(
          (run) => run.status === 'failed',
        ).length

        const generatedEvents = runs.reduce(
          (total, run) =>
            total + (run.event_count ?? 0),
          0,
        )

        const latestRuns = [...runs]
          .sort(
            (left, right) =>
              new Date(right.started_at).getTime() -
              new Date(left.started_at).getTime(),
          )
          .slice(0, 5)

        setRecentRuns(latestRuns)

        const coverage = enterprises.map((enterprise) => ({
          enterpriseId: enterprise.enterprise_id,
          enterpriseName: enterprise.name,
          scenarioCount: scenarios.filter(
            (scenario) =>
              scenario.enterprise_id ===
              enterprise.enterprise_id,
          ).length,
        }))

        setScenarioCoverage(coverage)

        setMetrics({
          activeRuns,
          totalRuns: runs.length,
          generatedEvents,
          scenarios: scenarios.length,
          enterprises: enterprises.length,
          failedRuns,
        })
      } catch (err) {
        if (!active) {
          return
        }

        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load operational overview.'

        setError(message)
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadOverview()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true

    async function loadActivity() {
      try {
        setActivityLoading(true)
        setActivityError(null)

        const activity = await getEventActivity(
          activityWindow,
        )

        if (!active) {
          return
        }

        setEventActivity(activity)
      } catch (err) {
        if (!active) {
          return
        }

        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load event activity.'

        setActivityError(message)
      } finally {
        if (active) {
          setActivityLoading(false)
        }
      }
    }

    void loadActivity()

    return () => {
      active = false
    }
  }, [activityWindow])

  return (
    <section>
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
          StreamOps
        </div>

        <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.025em] text-white">
          Operational Overview
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Monitor and control synthetic operational event generation across
          configured enterprises, scenarios, and runs.
        </p>
      </div>

      <div className="mt-8">
        {loading ? (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            Loading operational overview...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-sm text-red-300">
            {error}
          </div>
        ) : metrics ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <MetricCard
                label="Active Runs"
                value={formatCount(metrics.activeRuns)}
                detail="Currently executing"
                accent="violet"
              />

              <MetricCard
                label="Total Runs"
                value={formatCount(metrics.totalRuns)}
                detail="Durable run catalogue"
                accent="indigo"
              />

              <MetricCard
                label="Generated Events"
                value={formatCount(
                  metrics.generatedEvents,
                )}
                detail="Across all recorded runs"
                accent="cyan"
              />

              <MetricCard
                label="Scenarios"
                value={formatCount(metrics.scenarios)}
                detail="Configured scenarios"
                accent="sky"
              />

              <MetricCard
                label="Enterprises"
                value={formatCount(
                  metrics.enterprises,
                )}
                detail="Configured enterprises"
                accent="emerald"
              />

              <MetricCard
                label="Failed Runs"
                value={formatCount(metrics.failedRuns)}
                detail="Executions requiring review"
                accent="rose"
              />
            </div>

            <div className="mt-6 rounded-xl border border-white/[0.08] bg-slate-900/45">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.07] px-5 py-4">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-300/70">
                    Stream Telemetry
                  </div>

                  <div className="mt-1 text-[15px] font-semibold text-white">
                    Event Generation Activity
                  </div>
                </div>

                <div className="flex items-center rounded-lg border border-white/[0.07] bg-black/10 p-1">
                  {(
                    [
                      '1h',
                      '6h',
                      '24h',
                      '7d',
                    ] as EventActivityWindow[]
                  ).map((window) => (
                    <button
                      key={window}
                      type="button"
                      onClick={() =>
                        setActivityWindow(window)
                      }
                      className={[
                        'rounded-md px-3 py-1.5 text-[11px] font-medium transition-all',
                        activityWindow === window
                          ? 'bg-cyan-400/10 text-cyan-200 shadow-[0_0_18px_rgba(34,211,238,0.08)]'
                          : 'text-slate-500 hover:text-slate-300',
                      ].join(' ')}
                    >
                      {window}
                    </button>
                  ))}
                </div>
              </div>

              {activityLoading ? (
                <div className="flex h-72 items-center justify-center px-5 text-sm text-slate-500">
                  Loading event activity...
                </div>
              ) : activityError ? (
                <div className="flex h-72 items-center justify-center px-5 text-sm text-red-300">
                  {activityError}
                </div>
              ) : eventActivity ? (
                <EventActivityChart
                  activity={eventActivity}
                />
              ) : null}
            </div>

            <div className="mt-6 overflow-hidden rounded-xl border border-white/10 bg-slate-900/45">
              <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300/70">
                    Run Activity
                  </div>

                  <div className="mt-1 text-[15px] font-semibold text-white">
                    Recent Runs
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => navigate('/runs')}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-white"
                >
                  View all runs →
                </button>
              </div>

              {recentRuns.length === 0 ? (
                <div className="px-5 py-8 text-sm text-slate-500">
                  No runs have been executed yet.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-left text-sm">
                    <thead className="border-b border-white/[0.06] bg-white/[0.015] text-[10px] uppercase tracking-[0.10em] text-slate-500">
                      <tr>
                        <th className="px-5 py-3 font-medium">
                          Run
                        </th>

                        <th className="px-4 py-3 font-medium">
                          Scenario
                        </th>

                        <th className="px-4 py-3 font-medium">
                          Enterprise
                        </th>

                        <th className="px-4 py-3 font-medium">
                          Status
                        </th>

                        <th className="px-4 py-3 font-medium">
                          Started
                        </th>

                        <th className="px-5 py-3 text-right font-medium">
                          Events
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-white/[0.055]">
                      {recentRuns.map((run) => (
                        <tr
                          key={run.run_id}
                          onClick={() =>
                            navigate(`/runs/${run.run_id}`)
                          }
                          className="cursor-pointer text-slate-300 transition-colors hover:bg-white/[0.025]"
                        >
                          <td className="whitespace-nowrap px-5 py-3.5 font-mono text-xs text-violet-200">
                            {run.run_id}
                          </td>

                          <td className="whitespace-nowrap px-4 py-3.5">
                            {run.scenario_id}
                          </td>

                          <td className="whitespace-nowrap px-4 py-3.5 text-slate-400">
                            {run.target?.enterprise_id ?? '—'}
                          </td>

                          <td className="whitespace-nowrap px-4 py-3.5">
                            <span
                              className={`inline-flex rounded-md border px-2 py-1 text-[10px] font-medium ${runStatusClasses(
                                run.status,
                              )}`}
                            >
                              {formatLabel(run.status)}
                            </span>
                          </td>

                          <td className="whitespace-nowrap px-4 py-3.5 text-xs text-slate-400">
                            {formatRunDate(run.started_at)}
                          </td>

                          <td className="whitespace-nowrap px-5 py-3.5 text-right font-mono text-xs text-slate-300">
                            {run.event_count ?? '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-slate-900/45">
                <div className="border-b border-white/[0.07] px-5 py-4">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300/70">
                    Execution
                  </div>

                  <div className="mt-1 text-[15px] font-semibold text-white">
                    Current Activity
                  </div>
                </div>

                {activeRunItems.length === 0 ? (
                  <div className="flex min-h-[170px] items-center justify-center px-6 py-8">
                    <div className="text-center">
                      <div className="mx-auto flex size-9 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.025]">
                        <span className="size-2 rounded-full bg-slate-600" />
                      </div>

                      <div className="mt-4 text-sm font-medium text-slate-300">
                        No runs executing
                      </div>

                      <div className="mt-1 text-xs text-slate-500">
                        Active executions will appear here.
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="divide-y divide-white/[0.055]">
                    {activeRunItems.map((run) => (
                      <button
                        key={run.run_id}
                        type="button"
                        onClick={() =>
                          navigate(`/runs/${run.run_id}`)
                        }
                        className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors hover:bg-white/[0.025]"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="size-2 rounded-full bg-violet-400" />

                            <span className="font-mono text-xs text-violet-200">
                              {run.run_id}
                            </span>
                          </div>

                          <div className="mt-2 text-sm text-slate-300">
                            {run.scenario_id}
                          </div>

                          <div className="mt-1 text-xs text-slate-500">
                            {run.target?.enterprise_id ?? '—'}
                          </div>
                        </div>

                        <div className="text-right">
                          <div className="font-mono text-sm text-white">
                            {formatCount(run.event_count ?? 0)}
                          </div>

                          <div className="mt-1 text-[10px] uppercase tracking-[0.10em] text-slate-500">
                            Events
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-white/10 bg-slate-900/45">
                <div className="border-b border-white/[0.07] px-5 py-4">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300/70">
                    Configuration
                  </div>

                  <div className="mt-1 text-[15px] font-semibold text-white">
                    Scenario Coverage
                  </div>
                </div>

                <div className="divide-y divide-white/[0.055]">
                  {scenarioCoverage.map((item) => (
                    <div
                      key={item.enterpriseId}
                      className="flex items-center justify-between px-5 py-4"
                    >
                      <div>
                        <div className="text-sm font-medium text-slate-200">
                          {item.enterpriseName}
                        </div>

                        <div className="mt-1 font-mono text-[11px] text-slate-500">
                          {item.enterpriseId}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="font-mono text-lg font-medium text-white">
                          {item.scenarioCount}
                        </div>

                        <div className="mt-0.5 text-[10px] uppercase tracking-[0.10em] text-slate-500">
                          {item.scenarioCount === 1
                            ? 'Scenario'
                            : 'Scenarios'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </section>
  )
}