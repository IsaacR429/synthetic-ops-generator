import { useEffect, useState } from 'react'
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

function formatRunTime(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
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
                  className={`inline-flex rounded-md border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] ${runStatusClasses(
                    run.status,
                  )}`}
                >
                  {formatLabel(run.status)}
                </span>
              )}
            </div>
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
                  className="rounded-lg border border-red-400/15 bg-red-500/[0.06] px-4 py-2 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/[0.12] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {stoppingRun ? 'Stopping...' : 'Stop Run'}
                </button>
              )}

              <button
                type="button"
                onClick={() => navigate(`/runs/${run.run_id}/events`)}
                className="rounded-lg border border-violet-400/20 bg-violet-500/[0.07] px-4 py-2 text-xs font-medium text-violet-200 transition-colors hover:bg-violet-500/[0.12]"
              >
                Inspect Events →
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
          <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/50 backdrop-blur-md">
            <div className="grid grid-cols-1 gap-px bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-[#0b0914] p-5">
                <div className="text-[10px] uppercase tracking-[0.10em] text-slate-600">
                  Execution State
                </div>

                <dl className="mt-4 space-y-3 text-sm">
                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Scenario</dt>
                    <dd className="font-mono text-slate-200">{run.scenario_id}</dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Current State</dt>
                    <dd className="text-slate-200">
                      {formatLabel(run.current_state)}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Events</dt>
                    <dd className="font-mono text-slate-200">{run.event_count}</dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Validation</dt>
                    <dd className="text-slate-200">
                      {run.validation_passed === null
                        ? run.status === 'running'
                          ? 'Pending'
                          : 'Not reported'
                        : run.validation_passed
                          ? 'Passed'
                          : 'Failed'}
                    </dd>
                  </div>
                </dl>
              </div>

              <div className="bg-[#0b0914] p-5">
                <div className="text-[10px] uppercase tracking-[0.10em] text-slate-600">
                  Configuration
                </div>

                <dl className="mt-4 space-y-3 text-sm">
                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Execution Mode</dt>
                    <dd className="text-slate-200">
                      {formatLabel(run.execution_mode)}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Lifecycle</dt>
                    <dd className="text-slate-200">
                      {formatLabel(run.generation_lifecycle)}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Interval</dt>
                    <dd className="font-mono text-slate-200">
                      {run.event_interval_seconds}s
                    </dd>
                  </div>

                  {run.continuous_configuration && (
                    <div className="flex justify-between gap-6">
                      <dt className="text-slate-500">Stop Mode</dt>
                      <dd className="text-slate-200">
                        {formatLabel(run.continuous_configuration.stop_mode)}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>

              <div className="bg-[#0b0914] p-5">
                <div className="text-[10px] uppercase tracking-[0.10em] text-slate-600">
                  Target Scope
                </div>

                <dl className="mt-4 space-y-3 text-sm">
                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Enterprise</dt>
                    <dd className="font-mono text-slate-200">
                      {run.target?.enterprise_id ?? '—'}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Business Stream</dt>
                    <dd className="font-mono text-slate-200">
                      {run.target?.business_stream_id ?? '—'}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Service</dt>
                    <dd className="font-mono text-slate-200">
                      {run.target?.service_id ?? '—'}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Environment</dt>
                    <dd className="text-slate-200">
                      {run.target
                        ? formatLabel(run.target.environment)
                        : '—'}
                    </dd>
                  </div>
                </dl>
              </div>

              <div className="bg-[#0b0914] p-5">
                <div className="text-[10px] uppercase tracking-[0.10em] text-slate-600">
                  Timing
                </div>

                <dl className="mt-4 space-y-3 text-sm">
                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Started</dt>
                    <dd className="text-right text-slate-200">
                      {formatRunTime(run.started_at)}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Completed</dt>
                    <dd className="text-right text-slate-200">
                      {formatRunTime(run.completed_at)}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Change</dt>
                    <dd className="font-mono text-slate-200">
                      {run.change_id}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-6">
                    <dt className="text-slate-500">Seed</dt>
                    <dd className="font-mono text-slate-200">
                      {run.random_seed}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>

            {run.error_message && (
              <div className="border-t border-red-400/10 bg-red-500/[0.04] px-5 py-4 text-sm text-red-300">
                {run.error_message}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}