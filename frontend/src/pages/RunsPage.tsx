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

function formatRunTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

export function RunsPage() {
  const navigate = useNavigate()

  const [runs, setRuns] = useState<RunResponse[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

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
          <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/50 backdrop-blur-md">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 bg-white/[0.02] text-xs font-semibold text-slate-400">
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
                    className="cursor-pointer text-slate-300 transition-colors hover:bg-white/[0.035]"
                  >
                    <td className="whitespace-nowrap px-4 py-4 font-mono text-xs text-violet-200">
                      {run.run_id}
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
                      {formatLabel(run.generation_lifecycle)}
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

                    <td className="whitespace-nowrap px-4 py-4 text-right font-mono text-xs">
                      {run.event_count}
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