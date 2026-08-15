import { useParams } from 'react-router'

export function EventInspectionPage() {
  const { runId } = useParams()

  return (
    <section>
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
        Event Inspection
      </div>

      <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.025em] text-white">
        Retained Events
      </h1>

      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
        Canonical retained event sequence for Run{' '}
        <span className="font-mono font-medium text-slate-200">{runId}</span>.
      </p>
    </section>
  )
}