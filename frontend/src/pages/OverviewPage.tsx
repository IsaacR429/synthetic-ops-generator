export function OverviewPage() {
    return (
        <section>
            <div>
                <div className="text-xs font-medium uppercase tracking-[0.14em] text-blue-400">
                    StreamOps
                </div>

                <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                    Operational Overview
                </h1>

                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                    Monitor and control synthetic operational event generation
                    across configured enterprises and scenarios.
                </p>
            </div>

            <div className="mt-8 rounded-xl border border-white/8 bg-white/[0.025] p-6">
                <div className="text-sm font-medium text-slate-200">
                    Control plane ready
                </div>

                <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
                    Enterprise discovery, scenario capabilities, run execution,
                    persistence, replay, and event inspection will be connected
                    through the StreamOps API client.
                </p>
            </div>
        </section>
    )
}