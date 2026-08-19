import {
  type ReactNode,
  useEffect,
  useState,
} from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError, getRun, stopRun } from '../api/client'
import type { RunResponse, RunStatus } from '../types/api'

function formatLabel(value: string): string {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function runStatusClasses(status: RunStatus): string {
  const classes: Record<RunStatus, string> = {
    running: 'border-violet-400/20 bg-violet-500/10 text-violet-300',
    completed: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-300',
    failed: 'border-red-400/20 bg-red-500/10 text-red-300',
    stopped: 'border-amber-400/20 bg-amber-500/10 text-amber-300',
  }

  return classes[status]
}

function runStatusDotClasses(
  status: RunStatus,
): string {
  const classes: Record<RunStatus, string> = {
    running:
      'bg-violet-300 shadow-[0_0_14px_rgba(196,181,253,0.35)]',
    completed:
      'bg-emerald-300',
    failed:
      'bg-red-300',
    stopped:
      'bg-amber-300',
  }

  return classes[status]
}

function formatRunTime(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

interface DetailRowProps {
  label: string
  value: ReactNode
  mono?: boolean
  emphasis?: 'default' | 'cyan' | 'green'
}

function DetailRow({
  label,
  value,
  mono = false,
  emphasis = 'default',
}: DetailRowProps) {
  const valueClass =
    emphasis === 'cyan'
      ? 'text-cyan-100'
      : emphasis === 'green'
        ? 'text-emerald-300'
        : 'text-slate-200'

  return (
    <div className="flex items-center justify-between gap-6">
      <dt className="text-[11px] text-slate-500">
        {label}
      </dt>

      <dd
        className={[
          'text-right text-[12px] font-medium',
          mono ? 'font-mono' : '',
          valueClass,
        ].join(' ')}
      >
        {value}
      </dd>
    </div>
  )
}

export function RunDetailPage() {
  const { runId } = useParams()
  const navigate = useNavigate()

  const [run, setRun] = useState<RunResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [stoppingRun, setStoppingRun] = useState<boolean>(false)

  useEffect(() => {
    if (!runId) return

    const targetRunId = runId
    let active = true
    let timeoutId: number | undefined

    async function fetchRun() {
      try {
        setError(null)
        const data = await getRun(targetRunId)

        if (!active) return

        setRun(data)
        setLoading(false)

        if (data.status === 'running') {
          timeoutId = window.setTimeout(() => {
            void fetchRun()
          }, 1500)
        }
      } catch (err) {
        if (!active) return
        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load run details.'
        setError(message)
        setLoading(false)
      }
    }

    setLoading(true)
    void fetchRun()

    return () => {
      active = false
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [runId])

  async function handleStopRun() {
    if (!runId || stoppingRun) return

    try {
      setStoppingRun(true)

      try {
        await stopRun(runId)
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 409)) {
          throw err
        }
      }

      const updated = await getRun(runId)
      setRun(updated)
      setError(null)
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to stop run.'

      setError(message)
    } finally {
      setStoppingRun(false)
    }
  }

  return (
    <section>
      <div>
        <Link
          to="/runs"
          className="inline-flex items-center text-xs font-medium text-slate-400 transition-colors hover:text-slate-200"
        >
          ← Back to Runs
        </Link>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
              Run Detail
            </div>

            <div className="mt-1 flex items-center gap-3">
              <h1 className="font-mono text-[28px] font-semibold tracking-[-0.025em] text-white">
                {runId}
              </h1>

              {run && (
                <span
                  className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] ${runStatusClasses(
                    run.status,
                  )}`}
                >
                  <span
                    className={`size-1.5 rounded-full ${runStatusDotClasses(
                      run.status,
                    )}`}
                  />
                  {formatLabel(run.status)}
                </span>
              )}
            </div>

            {run && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                <span className="font-mono text-violet-200">
                  {run.scenario_id}
                </span>

                <span className="text-slate-700">
                  ·
                </span>

                <span className="text-slate-400">
                  {formatLabel(
                    run.execution_mode,
                  )}
                </span>

                <span className="text-slate-700">
                  ·
                </span>

                <span
                  className={
                    run.generation_lifecycle ===
                    'continuous'
                      ? 'text-cyan-300'
                      : 'text-slate-400'
                  }
                >
                  {formatLabel(
                    run.generation_lifecycle,
                  )}
                </span>

                {run.target && (
                  <>
                    <span className="text-slate-700">
                      ·
                    </span>

                    <span className="text-slate-500">
                      {formatLabel(
                        run.target.environment,
                      )}
                    </span>
                  </>
                )}
              </div>
            )}
          </div>

          {run && (
            <div className="flex items-center gap-3">
              {run.status === 'running' && (
                <button
                  type="button"
                  disabled={stoppingRun}
                  onClick={() => {
                    void handleStopRun()
                  }}
                  className="rounded-lg border border-red-400/15 bg-red-500/[0.04] px-4 py-2.5 text-[10px] font-medium text-red-300 transition-all hover:border-red-400/25 hover:bg-red-500/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {stoppingRun
                    ? 'Stopping...'
                    : 'Stop Run'}
                </button>
              )}

              <button
                type="button"
                onClick={() =>
                  navigate(
                    `/runs/${run.run_id}/events`,
                  )
                }
                className="group rounded-lg border border-violet-400/15 bg-gradient-to-r from-violet-500/[0.08] to-cyan-500/[0.025] px-4 py-2.5 text-[10px] font-medium text-violet-100 transition-all hover:border-violet-400/25 hover:bg-violet-500/[0.10]"
              >
                <span className="flex items-center gap-2">
                  Inspect Events

                  <span className="text-violet-300/60 transition-transform group-hover:translate-x-0.5">
                    →
                  </span>
                </span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="mt-8">
        {loading ? (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            Loading run metadata...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-sm text-red-300">
            {error}
          </div>
        ) : !run ? (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            Run not found.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {/* EXECUTION STATE */}
              <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/65 p-5">
                <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-violet-400/55 via-cyan-400/20 to-transparent" />

                <div>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/60">
                    Execution Metadata
                  </div>

                  <div className="mt-1 text-sm font-semibold text-white">
                    Execution State
                  </div>
                </div>

                <dl className="mt-5 space-y-3.5 border-t border-white/[0.06] pt-4">
                  <DetailRow
                    label="Scenario"
                    value={run.scenario_id}
                    mono
                  />

                  <DetailRow
                    label="Current State"
                    value={formatLabel(
                      run.current_state,
                    )}
                  />

                  <DetailRow
                    label="Events"
                    value={run.event_count}
                    mono
                    emphasis="cyan"
                  />

                  <DetailRow
                    label="Validation"
                    value={
                      run.validation_passed === null
                        ? run.status === 'running'
                          ? 'Pending'
                          : 'Not reported'
                        : run.validation_passed
                          ? 'Passed'
                          : 'Failed'
                    }
                    emphasis={
                      run.validation_passed
                        ? 'green'
                        : 'default'
                    }
                  />
                </dl>
              </div>

              {/* CONFIGURATION */}
              <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/65 p-5">
                <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/40 via-violet-400/20 to-transparent" />

                <div>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-cyan-300/60">
                    Execution Metadata
                  </div>

                  <div className="mt-1 text-sm font-semibold text-white">
                    Configuration
                  </div>
                </div>

                <dl className="mt-5 space-y-3.5 border-t border-white/[0.06] pt-4">
                  <DetailRow
                    label="Execution Mode"
                    value={formatLabel(
                      run.execution_mode,
                    )}
                  />

                  <DetailRow
                    label="Lifecycle"
                    value={formatLabel(
                      run.generation_lifecycle,
                    )}
                  />

                  <DetailRow
                    label="Interval"
                    value={`${run.event_interval_seconds}s`}
                    mono
                  />

                  {run.continuous_configuration && (
                    <DetailRow
                      label="Stop Mode"
                      value={formatLabel(
                        run.continuous_configuration
                          .stop_mode,
                      )}
                    />
                  )}
                </dl>
              </div>

              {/* TARGET SCOPE */}
              <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/65 p-5">
                <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-violet-400/40 via-cyan-400/20 to-transparent" />

                <div>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/60">
                    Target Discovery
                  </div>

                  <div className="mt-1 text-sm font-semibold text-white">
                    Target Scope
                  </div>
                </div>

                <dl className="mt-5 space-y-3.5 border-t border-white/[0.06] pt-4">
                  <DetailRow
                    label="Enterprise"
                    value={
                      run.target?.enterprise_id ??
                      '—'
                    }
                    mono
                  />

                  <DetailRow
                    label="Business Stream"
                    value={
                      run.target
                        ?.business_stream_id ??
                      '—'
                    }
                    mono
                  />

                  <DetailRow
                    label="Service"
                    value={
                      run.target?.service_id ??
                      '—'
                    }
                    mono
                    emphasis="cyan"
                  />

                  <DetailRow
                    label="Environment"
                    value={
                      run.target
                        ? formatLabel(
                            run.target.environment,
                          )
                        : '—'
                    }
                  />
                </dl>
              </div>

              {/* TIMING */}
              <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/65 p-5">
                <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-slate-400/35 via-violet-400/10 to-transparent" />

                <div>
                  <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Execution Metadata
                  </div>

                  <div className="mt-1 text-sm font-semibold text-white">
                    Timing
                  </div>
                </div>

                <dl className="mt-5 space-y-3.5 border-t border-white/[0.06] pt-4">
                  <DetailRow
                    label="Started"
                    value={formatRunTime(
                      run.started_at,
                    )}
                    mono
                  />

                  <DetailRow
                    label="Completed"
                    value={formatRunTime(
                      run.completed_at,
                    )}
                    mono
                  />

                  <DetailRow
                    label="Change"
                    value={run.change_id}
                    mono
                  />

                  <DetailRow
                    label="Seed"
                    value={run.random_seed}
                    mono
                  />
                </dl>
              </div>
            </div>

            {run.error_message && (
              <div className="rounded-xl border border-red-400/10 bg-red-500/[0.04] p-5 text-sm text-red-300">
                {run.error_message}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}