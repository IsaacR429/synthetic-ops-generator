import { NavLink, Outlet } from 'react-router'

const navigation = [
    {
        label: 'Overview',
        to: '/',
        end: true,
    },
    {
        label: 'Configure Run',
        to: '/configure',
    },
    {
        label: 'Runs',
        to: '/runs',
    },
]

export function AppShell() {
    return (
        <div className="min-h-screen bg-[#070b12] text-slate-200">
            <div className="flex min-h-screen">
                <aside className="flex w-64 shrink-0 flex-col border-r border-white/8 bg-[#090e17]">
                    <div className="border-b border-white/8 px-6 py-6">
                        <div className="flex items-center gap-3">
                            <div className="flex size-9 items-center justify-center rounded-lg border border-blue-400/20 bg-blue-500/10">
                                <div className="size-2.5 rounded-full bg-blue-400 shadow-[0_0_14px_rgba(96,165,250,0.65)]" />
                            </div>

                            <div>
                                <div className="text-base font-semibold tracking-tight text-white">
                                    StreamOps
                                </div>

                                <div className="mt-0.5 text-[11px] tracking-wide text-slate-500">
                                    Synthetic Event Generation
                                </div>
                            </div>
                        </div>
                    </div>

                    <nav className="flex-1 space-y-1 px-3 py-5">
                        {navigation.map((item) => (
                            <NavLink
                                key={item.to}
                                to={item.to}
                                end={item.end}
                                className={({ isActive }) =>
                                    [
                                        'flex items-center rounded-lg px-3 py-2.5',
                                        'text-sm font-medium transition-colors',
                                        isActive
                                            ? 'bg-blue-500/10 text-blue-300'
                                            : 'text-slate-400 hover:bg-white/5 hover:text-slate-200',
                                    ].join(' ')
                                }
                            >
                                {item.label}
                            </NavLink>
                        ))}
                    </nav>

                    <div className="border-t border-white/8 px-5 py-4">
                        <div className="text-[11px] uppercase tracking-[0.14em] text-slate-600">
                            Control Interface
                        </div>

                        <div className="mt-1 text-xs text-slate-500">
                            StreamOps v0.1
                        </div>
                    </div>
                </aside>

                <div className="flex min-w-0 flex-1 flex-col">
                    <header className="flex h-16 items-center justify-between border-b border-white/8 bg-[#090e17]/85 px-7 backdrop-blur">
                        <div>
                            <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                                Operational Control
                            </div>
                        </div>

                        <div className="flex items-center gap-2 rounded-full border border-white/8 bg-white/[0.025] px-3 py-1.5">
                            <div className="size-2 rounded-full bg-slate-500" />

                            <span className="text-xs text-slate-400">
                                API status pending
                            </span>
                        </div>
                    </header>

                    <main className="min-w-0 flex-1 px-7 py-7">
                        <Outlet />
                    </main>
                </div>
            </div>
        </div>
    )
}