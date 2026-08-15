import { NavLink, Outlet } from 'react-router'

import streamOpsLogo from '../assets/streamops-logo.svg'
import { ApiStatus } from '../components/ApiStatus'

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
    <div className="min-h-screen bg-transparent text-slate-200">
      <div className="flex min-h-screen">
        <aside className="flex w-64 shrink-0 flex-col border-r border-violet-400/10 bg-[#08070f]/95 shadow-[8px_0_40px_rgba(76,29,149,0.05)]">
          <div className="border-b border-white/8 px-6 py-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center">
                <img
                  src={streamOpsLogo}
                  alt=""
                  className="size-10 object-contain drop-shadow-[0_0_14px_rgba(139,92,246,0.28)]"
                />
              </div>

              <div>
                <div className="text-[16px] font-semibold tracking-[-0.02em] text-white">
                  StreamOps
                </div>

                <div className="mt-0.5 text-[11px] font-medium tracking-[0.01em] text-slate-500">
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
                    'text-[13px] font-medium tracking-[-0.01em] transition-all duration-200',
                    isActive
                      ? [
                          'border border-violet-400/15',
                          'bg-gradient-to-r from-violet-600/25 to-indigo-500/10',
                          'text-violet-100',
                          'shadow-[0_0_24px_rgba(124,58,237,0.08)]',
                        ].join(' ')
                      : [
                          'border border-transparent',
                          'text-slate-400',
                          'hover:bg-violet-500/[0.06]',
                          'hover:text-violet-100',
                        ].join(' '),
                  ].join(' ')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="border-t border-white/8 px-5 py-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.20em] text-violet-400/45">
              Control Interface
            </div>

            <div className="mt-1.5 text-[11px] font-medium text-slate-600">
              StreamOps v0.1
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b border-violet-400/10 bg-[#08070f]/75 px-7 backdrop-blur-xl">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
                Operational Control
              </div>
            </div>

            <ApiStatus />
          </header>

          <main className="min-w-0 flex-1 px-7 py-7">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}