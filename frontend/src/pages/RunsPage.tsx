import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, listRuns } from '../api/client'
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
      'bg-violet-300 shadow-[0_0_10px_rgba(196,181,253,0.35)]',
    completed:
      'bg-emerald-300',
    failed:
      'bg-red-300',
    stopped:
      'bg-amber-300',
  }

  return classes[status]
}

function formatRunTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

interface RunStatusSummaryProps {
  label: string
  count: number
  tone: 'violet' | 'emerald' | 'amber' | 'red'
}

const RUN_STATUS_TONES = {
  violet: {
    dot: 'bg-violet-300',
    text: 'text-violet-100',
    glow: 'from-violet-400/60',
  },

  emerald: {
    dot: 'bg-emerald-300',
    text: 'text-emerald-100',
    glow: 'from-emerald-400/60',
  },

  amber: {
    dot: 'bg-amber-300',
    text: 'text-amber-100',
    glow: 'from-amber-400/60',
  },

  red: {
    dot: 'bg-red-300',
    text: 'text-red-100',
    glow: 'from-red-400/60',
  },
}

function RunStatusSummary({
  label,
  count,
  tone,
}: RunStatusSummaryProps) {
  const style = RUN_STATUS_TONES[tone]

  return (
    <div className="relative flex min-w-0 flex-1 items-center gap-3 px-4 py-3">
      <div
        className={`size-1.5 shrink-0 rounded-full ${style.dot}`}
      />

      <div className="min-w-0">
        <div className="text-[9px] font-semibold uppercase tracking-[0.15em] text-slate-600">
          {label}
        </div>

        <div
          className={`mt-0.5 font-mono text-sm font-semibold ${style.text}`}
        >
          {count}
        </div>
      </div>

      <div
        className={`pointer-events-none absolute bottom-0 left-4 h-px w-10 bg-gradient-to-r ${style.glow} to-transparent`}
      />
    </div>
  )
}

export function RunsPage() {
  const navigate = useNavigate()

  const [runs, setRuns] = useState<RunResponse[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const runningCount = runs.filter(
    (run) => run.status === 'running',
  ).length

  const completedCount = runs.filter(
    (run) => run.status === 'completed',
  ).length

  const stoppedCount = runs.filter(
    (run) => run.status === 'stopped',
  ).length

  const failedCount = runs.filter(
    (run) => run.status === 'failed',
  ).length

  useEffect(() => {
    let active = true

    async function loadRuns() {
      try {
        setLoading(true)
        setError(null)
        const data = await listRuns()

        if (active) {
          setRuns(data)
        }
      } catch (err) {
        if (active) {
          const message =
            err instanceof ApiError
              ? err.message
              : 'Failed to load runs catalogue.'
          setError(message)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadRuns()

    return () => {
      active = false
    }
  }, [])

  return (
    <section>
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
          Execution
        </div>

        <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.025em] text-white">
          Runs
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Inspect synthetic operational runs and their execution state.
        </p>
      </div>

      <div className="mt-8">
        {!loading && !error && runs.length > 0 && (
          <div className="mb-4 overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/65 shadow-[0_12px_35px_rgba(2,6,23,0.14)]">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
              <div>
                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/60">
                  Operational State
                </div>

                <div className="mt-1 text-xs font-medium text-slate-300">
                  Durable execution catalogue
                </div>
              </div>

              <div className="flex items-center gap-2 text-[9px] uppercase tracking-[0.12em] text-slate-600">
                <span className="size-1.5 rounded-full bg-cyan-300/70" />
                {runs.length} retained runs
              </div>
            </div>

            <div className="grid grid-cols-2 divide-x divide-y divide-white/[0.05] sm:grid-cols-4 sm:divide-y-0">
              <RunStatusSummary
                label="Running"
                count={runningCount}
                tone="violet"
              />

              <RunStatusSummary
                label="Completed"
                count={completedCount}
                tone="emerald"
              />

              <RunStatusSummary
                label="Stopped"
                count={stoppedCount}
                tone="amber"
              />

              <RunStatusSummary
                label="Failed"
                count={failedCount}
                tone="red"
              />
            </div>
          </div>
        )}

        {loading ? (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            Loading runs...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-sm text-red-300">
            {error}
          </div>
        ) : runs.length === 0 ? (
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-6 text-sm text-slate-400">
            No runs have been executed yet.
          </div>
        ) : (
          <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#111428]/70 shadow-[0_16px_45px_rgba(2,6,23,0.16)]">
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px bg-gradient-to-r from-violet-400/55 via-cyan-400/20 to-transparent" />
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/[0.07] bg-white/[0.018] text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Run</th>

                  <th className="px-4 py-3 font-medium">Scenario</th>

                  <th className="px-4 py-3 font-medium">Enterprise</th>

                  <th className="px-4 py-3 font-medium">Service</th>

                  <th className="px-4 py-3 font-medium">Lifecycle</th>

                  <th className="px-4 py-3 font-medium">Status</th>

                  <th className="px-4 py-3 font-medium">Started</th>

                  <th className="px-4 py-3 text-right font-medium">Events</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-white/[0.06]">
                {runs.map((run) => (
                  <tr
                    key={run.run_id}
                    onClick={() => navigate(`/runs/${run.run_id}`)}
                    className="group cursor-pointer text-slate-300 transition-all duration-150 hover:bg-gradient-to-r hover:from-violet-500/[0.035] hover:via-cyan-500/[0.018] hover:to-transparent"
                  >
                    <td className="whitespace-nowrap px-4 py-4">
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`size-1.5 shrink-0 rounded-full ${runStatusDotClasses(
                            run.status,
                          )}`}
                        />

                        <span className="font-mono text-[11px] font-medium text-violet-100 transition-colors group-hover:text-white">
                          {run.run_id}
                        </span>
                      </div>
                    </td>

                    <td className="whitespace-nowrap px-4 py-4">
                      {run.scenario_id}
                    </td>

                    <td className="whitespace-nowrap px-4 py-4">
                      {run.target?.enterprise_id ?? '—'}
                    </td>

                    <td className="whitespace-nowrap px-4 py-4">
                      {run.target?.service_id ?? '—'}
                    </td>

                    <td className="whitespace-nowrap px-4 py-4">
                      <span
                        className={[
                          'inline-flex rounded-md border px-2 py-1',
                          'text-[10px] font-medium',
                          run.generation_lifecycle === 'continuous'
                            ? [
                                'border-cyan-400/10',
                                'bg-cyan-500/[0.035]',
                                'text-cyan-100',
                              ].join(' ')
                            : [
                                'border-white/[0.06]',
                                'bg-white/[0.02]',
                                'text-slate-300',
                              ].join(' '),
                        ].join(' ')}
                      >
                        {formatLabel(run.generation_lifecycle)}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-4 py-4">
                      <span
                        className={`inline-flex rounded-md border px-2 py-1 text-[11px] font-medium ${runStatusClasses(
                          run.status,
                        )}`}
                      >
                        {formatLabel(run.status)}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-400">
                      {formatRunTime(run.started_at)}
                    </td>

                    <td className="whitespace-nowrap px-4 py-4 text-right">
                      <span className="font-mono text-[11px] font-semibold text-cyan-100">
                        {run.event_count ?? '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}