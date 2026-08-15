import { useParams } from 'react-router'

export function RunDetailPage() {
    const { runId } = useParams()

    return (
        <section>
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-blue-400">
                Run Detail
            </div>

            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                {runId}
            </h1>

            <p className="mt-2 text-sm text-slate-400">
                Execution metadata and operational state for this run.
            </p>
        </section>
    )
}