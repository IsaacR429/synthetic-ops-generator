import { useParams } from 'react-router'

export function EventInspectionPage() {
    const { runId } = useParams()

    return (
        <section>
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-blue-400">
                Event Inspection
            </div>

            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                Retained Events
            </h1>

            <p className="mt-2 text-sm text-slate-400">
                Canonical retained event sequence for Run {runId}.
            </p>
        </section>
    )
}