export function OverviewPage() {
  return (
    <section>
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
          StreamOps
        </div>

        <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.025em] text-white">
          Operational Overview
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Monitor and control synthetic operational event generation across
          configured enterprises and scenarios.
        </p>
      </div>

      <div className="relative mt-8 overflow-hidden rounded-xl border border-violet-400/10 bg-gradient-to-br from-violet-500/[0.07] via-white/[0.025] to-transparent p-6 shadow-[0_18px_50px_rgba(49,16,101,0.08)]">
        <div className="pointer-events-none absolute -right-20 -top-24 size-64 rounded-full bg-violet-600/10 blur-3xl" />

        <div className="relative">
          <div className="text-[15px] font-semibold tracking-[-0.01em] text-white">
            Control plane ready
          </div>

          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
            Enterprise discovery, scenario capabilities, run execution,
            persistence, replay, and event inspection will be connected
            through the StreamOps API client.
          </p>
        </div>
      </div>
    </section>
  )
}