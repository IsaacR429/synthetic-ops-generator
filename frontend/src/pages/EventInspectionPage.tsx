import {
  Fragment,
  useEffect,
  useState,
} from 'react'
import { Link, useParams } from 'react-router'

import { ApiError, getRun, getRunEvents } from '../api/client'
import type {
  RunEventQuery,
  RunEventsResponse,
  RunResponse,
  SourceDomain,
} from '../types/api'

const EVENT_PAGE_SIZE = 100

const SOURCE_DOMAIN_OPTIONS: {
  value: SourceDomain
  label: string
}[] = [
  {
    value: 'itsm',
    label: 'ITSM',
  },
  {
    value: 'deployment',
    label: 'Deployment',
  },
  {
    value: 'application_test',
    label: 'Application Test',
  },
  {
    value: 'infrastructure_test',
    label: 'Infrastructure Test',
  },
  {
    value: 'metric',
    label: 'Metric',
  },
  {
    value: 'log',
    label: 'Log',
  },
  {
    value: 'manual_validation',
    label: 'Manual Validation',
  },
  {
    value: 'incident',
    label: 'Incident',
  },
  {
    value: 'evidence',
    label: 'Evidence',
  },
]

function formatSourceDomain(
  value: SourceDomain,
): string {
  return (
    SOURCE_DOMAIN_OPTIONS.find(
      (option) => option.value === value,
    )?.label ?? value
  )
}

function formatEventTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  }).format(new Date(value))
}

interface FilterInputProps {
  id: string
  label: string
  value: string
  placeholder: string
  onChange: (value: string) => void
}

function FilterInput({
  id,
  label,
  value,
  placeholder,
  onChange,
}: FilterInputProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-2 block text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500"
      >
        {label}
      </label>

      <input
        id={id}
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(event) =>
          onChange(event.target.value)
        }
        className="w-full rounded-lg border border-white/10 bg-[#0b0914] px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-700 focus:border-violet-400/40 focus:outline-none"
      />
    </div>
  )
}

interface MetricPayload {
  name?: unknown
  observed_value?: unknown
  unit?: unknown
  classification?: unknown
  evaluation_statistic?: unknown
  direction?: unknown
  scenario_state?: unknown

  baseline?: {
    center?: unknown
    lower_bound?: unknown
    upper_bound?: unknown
  }

  effective_benchmark?: {
    reference_target?: unknown
    warning_threshold?: unknown
    blocking_threshold?: unknown
  }
}

function getMetricPayload(
  data: Record<string, unknown>,
): MetricPayload | null {
  const metric = data.metric

  if (
    !metric ||
    typeof metric !== 'object' ||
    Array.isArray(metric)
  ) {
    return null
  }

  return metric as MetricPayload
}

interface MetricValueProps {
  label: string
  value: unknown
}

function MetricValue({
  label,
  value,
}: MetricValueProps) {
  const displayValue =
    value === null || value === undefined
      ? '—'
      : String(value)

  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.10em] text-slate-600">
        {label}
      </div>

      <div className="mt-1 break-words font-mono text-xs text-slate-200">
        {displayValue}
      </div>
    </div>
  )
}

function formatMetricObservedValue(
  metric: MetricPayload | null,
): string {
  if (
    !metric ||
    typeof metric.observed_value !== 'number'
  ) {
    return '—'
  }

  const unit =
    typeof metric.unit === 'string'
      ? ` ${metric.unit}`
      : ''

  return `${metric.observed_value.toFixed(2)}${unit}`
}

export function EventInspectionPage() {
  const { runId } = useParams<{ runId: string }>()

  const [run, setRun] = useState<RunResponse | null>(null)
  const [runEvents, setRunEvents] = useState<RunEventsResponse | null>(null)
  const [
    selectedSourceDomain,
    setSelectedSourceDomain,
  ] = useState<SourceDomain | ''>('')
  const [sourceSystemInput, setSourceSystemInput] =
    useState('')
  const [eventTypeInput, setEventTypeInput] =
    useState('')
  const [serviceInput, setServiceInput] =
    useState('')
  const [componentInput, setComponentInput] =
    useState('')
  const [appliedQuery, setAppliedQuery] =
    useState<RunEventQuery | undefined>(
      undefined,
    )
  const [
    totalRetainedEventCount,
    setTotalRetainedEventCount,
  ] = useState<number | null>(null)
  const [
    expandedEventId,
    setExpandedEventId,
  ] = useState<string | null>(null)
  const [
    pageCursor,
    setPageCursor,
  ] = useState<number | undefined>(undefined)
  const [
    cursorHistory,
    setCursorHistory,
  ] = useState<Array<number | undefined>>([])
  const [loading, setLoading] = useState(true)

  const [runError, setRunError] =
    useState<string | null>(null)

  const [eventError, setEventError] =
    useState<string | null>(null)

  const error = runError ?? eventError

  const hasDraftFilters =
    Boolean(
      selectedSourceDomain ||
        sourceSystemInput.trim() ||
        eventTypeInput.trim() ||
        serviceInput.trim() ||
        componentInput.trim(),
    )

  useEffect(() => {
    setRun(null)
    setRunEvents(null)

    setSelectedSourceDomain('')
    setSourceSystemInput('')
    setEventTypeInput('')
    setServiceInput('')
    setComponentInput('')
    setAppliedQuery(undefined)

    setTotalRetainedEventCount(null)
    setExpandedEventId(null)

    setPageCursor(undefined)
    setCursorHistory([])

    setRunError(null)
    setEventError(null)
  }, [runId])

  useEffect(() => {
    if (!runId) {
      return
    }

    const targetRunId = runId
    let active = true
    let timeoutId: number | undefined

    async function loadRun() {
      try {
        setRunError(null)

        const runData = await getRun(
          targetRunId,
        )

        if (!active) {
          return
        }

        setRun(runData)
        setLoading(false)

        if (runData.status === 'running') {
          timeoutId = window.setTimeout(
            () => {
              void loadRun()
            },
            1500,
          )
        }
      } catch (err) {
        if (!active) {
          return
        }

        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load Run metadata.'

        setRunError(message)
        setLoading(false)
      }
    }

    setLoading(true)
    void loadRun()

    return () => {
      active = false

      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [runId])

  useEffect(() => {
    if (!runId) {
      return
    }

    const targetRunId = runId
    let active = true
    let timeoutId: number | undefined

    async function loadEvents() {
      try {
        setEventError(null)

        const eventsData = await getRunEvents(
          targetRunId,
          {
            ...(appliedQuery ?? {}),
            after_sequence_number: pageCursor,
            limit: EVENT_PAGE_SIZE,
          },
        )

        if (!active) {
          return
        }

        setRunEvents(eventsData)

        if (!appliedQuery) {
          setTotalRetainedEventCount(
            eventsData.retained_event_count,
          )
        }
      } catch (err) {
        if (!active) {
          return
        }

        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load retained events.'

        setEventError(message)
      } finally {
        if (
          active &&
          run?.status === 'running'
        ) {
          timeoutId = window.setTimeout(
            () => {
              void loadEvents()
            },
            1500,
          )
        }
      }
    }

    void loadEvents()

    return () => {
      active = false

      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [
    runId,
    appliedQuery,
    pageCursor,
    run?.status,
  ])

  function handleApplyFilters() {
    const query: RunEventQuery = {}

    if (selectedSourceDomain) {
      query.source_domain =
        selectedSourceDomain
    }

    const sourceSystem =
      sourceSystemInput.trim()

    if (sourceSystem) {
      query.source_system = sourceSystem
    }

    const eventType =
      eventTypeInput.trim()

    if (eventType) {
      query.event_type = eventType
    }

    const service = serviceInput.trim()

    if (service) {
      query.service = service
    }

    const component =
      componentInput.trim()

    if (component) {
      query.component = component
    }

    setPageCursor(undefined)
    setCursorHistory([])
    setExpandedEventId(null)

    setAppliedQuery(
      Object.keys(query).length > 0
        ? query
        : undefined,
    )
  }

  function handleClearFilters() {
    setSelectedSourceDomain('')
    setSourceSystemInput('')
    setEventTypeInput('')
    setServiceInput('')
    setComponentInput('')

    setPageCursor(undefined)
    setCursorHistory([])
    setExpandedEventId(null)

    setAppliedQuery(undefined)
  }

  function handleNextPage() {
    const nextCursor =
      runEvents?.next_after_sequence_number

    if (
      nextCursor === null ||
      nextCursor === undefined
    ) {
      return
    }

    setCursorHistory((current) => [
      ...current,
      pageCursor,
    ])

    setExpandedEventId(null)
    setPageCursor(nextCursor)
  }

  function handlePreviousPage() {
    if (cursorHistory.length === 0) {
      return
    }

    const previousCursor =
      cursorHistory[
        cursorHistory.length - 1
      ]

    setCursorHistory((current) =>
      current.slice(0, -1),
    )

    setExpandedEventId(null)
    setPageCursor(previousCursor)
  }

  return (
    <section>
      <Link
        to={runId ? `/runs/${runId}` : '/runs'}
        className="inline-flex items-center text-xs font-medium text-slate-400 transition-colors hover:text-slate-200"
      >
        ← Back to Run
      </Link>

      <div className="mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
        Event Inspection
      </div>

      <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.025em] text-white">
        Retained Events
      </h1>

      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
        Canonical retained event sequence for Run{' '}
        <span className="font-mono font-medium text-slate-200">
          {runId}
        </span>
        .
      </p>

      <div className="mt-8">
        {loading ? (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            Loading retained events...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-sm text-red-300">
            {error}
          </div>
        ) : run && runEvents ? (
          <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/70 shadow-[0_14px_40px_rgba(2,6,23,0.14)]">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.06] px-5 py-3.5">
              <div>
                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/60">
                  Inspection Context
                </div>

                <div className="mt-1 flex items-center gap-2 text-xs text-slate-300">
                  <span className="font-mono text-white">
                    {run.run_id}
                  </span>

                  <span className="text-slate-600">
                    ·
                  </span>

                  <span className="font-mono">
                    {run.scenario_id}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span
                  className={[
                    'size-1.5 rounded-full',
                    run.status === 'running'
                      ? 'bg-violet-300 shadow-[0_0_12px_rgba(196,181,253,0.35)]'
                      : run.status === 'completed'
                        ? 'bg-emerald-300'
                        : run.status === 'stopped'
                          ? 'bg-amber-300'
                          : 'bg-red-300',
                  ].join(' ')}
                />

                <span
                  className={[
                    'text-[9px] font-semibold uppercase tracking-[0.12em]',
                    run.status === 'running'
                      ? 'text-violet-200'
                      : run.status === 'completed'
                        ? 'text-emerald-300'
                        : run.status === 'stopped'
                          ? 'text-amber-300'
                          : 'text-red-300',
                  ].join(' ')}
                >
                  {run.status}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 divide-y divide-white/[0.05] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <div className="relative px-5 py-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                  Run Status
                </div>

                <div className="mt-1.5 text-sm font-semibold capitalize text-slate-200">
                  {run.status}
                </div>

                <div
                  className={[
                    'absolute bottom-0 left-5 h-px w-10 bg-gradient-to-r to-transparent',
                    run.status === 'running'
                      ? 'from-violet-400/70'
                      : run.status === 'completed'
                        ? 'from-emerald-400/70'
                        : run.status === 'stopped'
                          ? 'from-amber-400/70'
                          : 'from-red-400/70',
                  ].join(' ')}
                />
              </div>

              <div className="relative px-5 py-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                  Generated Events
                </div>

                <div className="mt-1.5 font-mono text-lg font-semibold text-cyan-100">
                  {run.event_count ?? '—'}
                </div>

                <div className="absolute bottom-0 left-5 h-px w-10 bg-gradient-to-r from-cyan-400/70 to-transparent" />
              </div>

              <div className="relative px-5 py-4">
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                  Retained Events
                </div>

                <div className="mt-1.5 font-mono text-lg font-semibold text-violet-100">
                  {totalRetainedEventCount ??
                    runEvents.retained_event_count}
                </div>

                <div className="absolute bottom-0 left-5 h-px w-10 bg-gradient-to-r from-violet-400/70 to-transparent" />
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            Run inspection data is unavailable.
          </div>
        )}

        {!loading && !error && runEvents && (
          <div className="mt-6 overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/65 shadow-[0_14px_40px_rgba(2,6,23,0.14)]">
            {/* CONSOLE HEADER */}
            <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <div className="flex size-6 items-center justify-center rounded-md border border-violet-400/20 bg-violet-500/10 font-mono text-xs font-medium text-violet-200">
                  Q
                </div>

                <div>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/60">
                    Event Query Console
                  </div>

                  <div className="text-xs font-semibold text-white">
                    Projection & Scope Filter
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <span className="size-1.5 rounded-full bg-cyan-300/80" />
                Live index filtering
              </div>
            </div>

            {/* INPUT GRID */}
            <div className="p-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
                <div>
                  <label
                    htmlFor="source-domain-filter"
                    className="mb-2 block text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500"
                  >
                    Source Domain
                  </label>

                  <select
                    id="source-domain-filter"
                    value={selectedSourceDomain}
                    onChange={(event) =>
                      setSelectedSourceDomain(
                        event.target.value as
                          | SourceDomain
                          | '',
                      )
                    }
                    className="w-full rounded-lg border border-white/[0.08] bg-[#090b17] px-3 py-2 text-xs text-slate-200 transition-colors focus:border-violet-400/40 focus:outline-none"
                  >
                    <option value="">
                      All Domains
                    </option>

                    {SOURCE_DOMAIN_OPTIONS.map(
                      (option) => (
                        <option
                          key={option.value}
                          value={option.value}
                        >
                          {option.label}
                        </option>
                      ),
                    )}
                  </select>
                </div>

                <FilterInput
                  id="source-system-filter"
                  label="Source System"
                  value={sourceSystemInput}
                  placeholder="e.g. synthetic_observability"
                  onChange={setSourceSystemInput}
                />

                <FilterInput
                  id="event-type-filter"
                  label="Event Type"
                  value={eventTypeInput}
                  placeholder="e.g. metric.observed"
                  onChange={setEventTypeInput}
                />

                <FilterInput
                  id="service-filter"
                  label="Service"
                  value={serviceInput}
                  placeholder="e.g. payment_service"
                  onChange={setServiceInput}
                />

                <FilterInput
                  id="component-filter"
                  label="Component"
                  value={componentInput}
                  placeholder="e.g. payment_api"
                  onChange={setComponentInput}
                />
              </div>
            </div>

            {/* QUERY FOOTER */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/[0.06] bg-[#0d1020]/35 px-5 py-3.5">
              <div className="flex items-center gap-5">
                <div>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-600">
                    Query Result
                  </div>

                  <div className="mt-1 flex items-baseline gap-1.5">
                    <span className="font-mono text-sm font-semibold text-cyan-100">
                      {runEvents.retained_event_count}
                    </span>

                    <span className="text-[10px] text-slate-500">
                      retained events
                    </span>
                  </div>
                </div>

                {appliedQuery && (
                  <div className="hidden h-8 w-px bg-white/[0.06] sm:block" />
                )}

                {appliedQuery && (
                  <div className="hidden sm:block">
                    <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-600">
                      Query Mode
                    </div>

                    <div className="mt-1 text-[10px] font-medium text-violet-200">
                      Projection filters · AND
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleClearFilters}
                  disabled={
                    !appliedQuery &&
                    !hasDraftFilters
                  }
                  className="rounded-lg border border-white/[0.07] bg-white/[0.015] px-4 py-2.5 text-[10px] font-medium text-slate-400 transition-all hover:border-white/[0.12] hover:bg-white/[0.035] hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-35"
                >
                  Clear
                </button>

                <button
                  type="button"
                  onClick={handleApplyFilters}
                  className="group rounded-lg border border-violet-400/20 bg-gradient-to-r from-violet-500/[0.12] to-cyan-500/[0.05] px-4 py-2.5 text-[10px] font-semibold text-violet-100 transition-all hover:border-violet-400/30 hover:from-violet-500/[0.17] hover:to-cyan-500/[0.08]"
                >
                  <span className="flex items-center gap-2">
                    Apply Query

                    <span className="text-cyan-300/60 transition-transform group-hover:translate-x-0.5">
                      →
                    </span>
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}

        {!loading &&
          !error &&
          runEvents &&
          runEvents.events.length === 0 && (
            <div className="mt-6 rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
              {appliedQuery
                ? 'No retained events match the current filters.'
                : 'No retained events are available for this Run.'}
            </div>
          )}

        {!loading &&
          !error &&
          runEvents &&
          runEvents.events.length > 0 && (
            <div className="mt-6 overflow-hidden rounded-xl border border-white/10 bg-slate-900/50">
              <div className="border-b border-white/10 px-5 py-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Canonical Event Sequence
                </div>

                <p className="mt-1 text-xs text-slate-500">
                  Events are shown in persisted sequence order.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[1050px] text-left text-sm">
                  <thead className="border-b border-white/10 bg-white/[0.02] text-xs text-slate-400">
                    <tr>
                      <th className="px-4 py-3 font-medium">
                        Seq
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Time
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Domain
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Source
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Event Type
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Signal
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Observed
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Status
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Service
                      </th>

                      <th className="px-4 py-3 font-medium">
                        Component
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-white/[0.06]">
                    {runEvents.events.map((event) => {
                      const isExpanded =
                        expandedEventId === event.event_id

                      const metric = getMetricPayload(
                        event.data,
                      )

                      return (
                        <Fragment key={event.event_id}>
                          <tr
                            onClick={() =>
                              setExpandedEventId((current) =>
                                current === event.event_id
                                  ? null
                                  : event.event_id,
                              )
                            }
                            className="cursor-pointer text-slate-300 transition-colors hover:bg-white/[0.025]"
                          >
                            <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-violet-300">
                              {event.sequence_number}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-400">
                              {formatEventTime(event.event_time)}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3">
                              {event.source_domain
                                ? formatSourceDomain(
                                    event.source_domain,
                                  )
                                : '—'}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-300">
                              {event.source_system}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-200">
                              {event.event_type}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-200">
                              {metric &&
                              typeof metric.name === 'string'
                                ? metric.name
                                : '—'}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-200">
                              {formatMetricObservedValue(metric)}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3 text-xs">
                              {metric &&
                              typeof metric.classification === 'string'
                                ? metric.classification
                                : '—'}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3">
                              {event.service ?? '—'}
                            </td>

                            <td className="whitespace-nowrap px-4 py-3">
                              {event.component ?? '—'}
                            </td>
                          </tr>

                          {isExpanded && (
                            <tr className="bg-white/[0.015]">
                              <td colSpan={10} className="px-6 py-5">
                                <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
                                  <div>
                                    <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                                      Event Envelope
                                    </div>

                                    <dl className="mt-3 space-y-2 text-xs">
                                      <div>
                                        <dt className="text-slate-600">
                                          Event ID
                                        </dt>
                                        <dd className="mt-0.5 font-mono text-slate-300">
                                          {event.event_id}
                                        </dd>
                                      </div>

                                      <div>
                                        <dt className="text-slate-600">
                                          Schema
                                        </dt>
                                        <dd className="mt-0.5 font-mono text-slate-300">
                                          {event.schema_version}
                                        </dd>
                                      </div>

                                      <div>
                                        <dt className="text-slate-600">
                                          Change
                                        </dt>
                                        <dd className="mt-0.5 font-mono text-slate-300">
                                          {event.chg_id ?? '—'}
                                        </dd>
                                      </div>

                                      <div>
                                        <dt className="text-slate-600">
                                          Business Stream
                                        </dt>
                                        <dd className="mt-0.5 text-slate-300">
                                          {event.business_stream ?? '—'}
                                        </dd>
                                      </div>

                                      <div>
                                        <dt className="text-slate-600">
                                          Environment
                                        </dt>
                                        <dd className="mt-0.5 text-slate-300">
                                          {event.environment ?? '—'}
                                        </dd>
                                      </div>

                                      <div>
                                        <dt className="text-slate-600">
                                          Synthetic
                                        </dt>
                                        <dd className="mt-0.5 text-slate-300">
                                          {event.synthetic
                                            ? 'Yes'
                                            : 'No'}
                                        </dd>
                                      </div>
                                    </dl>
                                  </div>

                                  <div className="min-w-0">
                                    {event.source_domain === 'metric' &&
                                      (() => {
                                        const metric = getMetricPayload(
                                          event.data,
                                        )

                                        if (!metric) {
                                          return null
                                        }

                                        return (
                                          <div className="mb-5 rounded-lg border border-violet-400/10 bg-violet-500/[0.04] p-4">
                                            <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-violet-300/70">
                                              Metric Summary
                                            </div>

                                            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
                                              <MetricValue
                                                label="Metric"
                                                value={metric.name}
                                              />

                                              <MetricValue
                                                label="Observed"
                                                value={
                                                  typeof metric.observed_value ===
                                                  'number'
                                                    ? `${metric.observed_value.toFixed(
                                                        2,
                                                      )} ${
                                                        typeof metric.unit ===
                                                        'string'
                                                          ? metric.unit
                                                          : ''
                                                      }`
                                                    : metric.observed_value
                                                }
                                              />

                                              <MetricValue
                                                label="Statistic"
                                                value={
                                                  metric.evaluation_statistic
                                                }
                                              />

                                              <MetricValue
                                                label="Classification"
                                                value={metric.classification}
                                              />

                                              <MetricValue
                                                label="Baseline"
                                                value={metric.baseline?.center}
                                              />

                                              <MetricValue
                                                label="Warning"
                                                value={
                                                  metric.effective_benchmark
                                                    ?.warning_threshold
                                                }
                                              />
                                            </div>
                                          </div>
                                        )
                                      })()}

                                    <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                                      Canonical Payload
                                    </div>

                                    <pre className="mt-3 max-h-[420px] overflow-auto rounded-lg border border-white/[0.06] bg-black/20 p-4 font-mono text-xs leading-5 text-slate-300">
                                      {JSON.stringify(
                                        event.data,
                                        null,
                                        2,
                                      )}
                                    </pre>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-4">
                <div className="text-xs text-slate-500">
                  Showing{' '}
                  <span className="font-mono text-slate-300">
                    {runEvents.returned_event_count}
                  </span>{' '}
                  of{' '}
                  <span className="font-mono text-slate-300">
                    {runEvents.retained_event_count}
                  </span>{' '}
                  retained events
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handlePreviousPage}
                    disabled={cursorHistory.length === 0}
                    className="rounded-lg border border-white/[0.08] bg-white/[0.025] px-4 py-2 text-xs font-medium text-slate-300 transition-colors hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:border-white/[0.04] disabled:bg-transparent disabled:text-slate-600"
                  >
                    ← Previous
                  </button>

                  <button
                    type="button"
                    onClick={handleNextPage}
                    disabled={
                      runEvents.next_after_sequence_number ===
                      null
                    }
                    className="rounded-lg border border-violet-400/20 bg-violet-500/[0.08] px-4 py-2 text-xs font-medium text-violet-200 transition-colors hover:bg-violet-500/[0.14] disabled:cursor-not-allowed disabled:border-white/[0.05] disabled:bg-transparent disabled:text-slate-600"
                  >
                    Next →
                  </button>
                </div>
              </div>
            </div>
          )}
      </div>
    </section>
  )
}