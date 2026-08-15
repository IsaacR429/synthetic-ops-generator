import { useParams } from 'react-router'

export function RunDetailPage() {
  const { runId } = useParams()

  return (
    <section>
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
        Run Detail
      </div>

      <h1 className="mt-2 font-mono text-[28px] font-semibold tracking-[-0.025em] text-white">
        {runId}
      </h1>

      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
        Execution metadata and operational state for this run.
      </p>
    </section>
  )
}