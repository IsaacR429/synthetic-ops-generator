import { useEffect, useState } from 'react'

import { getHealth } from '../api/client'

type HealthState = 'checking' | 'healthy' | 'unavailable'

export function ApiStatus() {
  const [healthState, setHealthState] = useState<HealthState>('checking')

  useEffect(() => {
    let active = true

    async function checkHealth() {
      try {
        const health = await getHealth()

        if (!active) {
          return
        }

        setHealthState(
          health.status === 'ok' ? 'healthy' : 'unavailable',
        )
      } catch {
        if (active) {
          setHealthState('unavailable')
        }
      }
    }

    void checkHealth()

    return () => {
      active = false
    }
  }, [])

  const configuration = {
    checking: {
      dot: 'bg-violet-400',
      label: 'Checking',
      labelClass: 'text-slate-400',
    },
    healthy: {
      dot: 'bg-emerald-400',
      label: 'Healthy',
      labelClass: 'text-emerald-400',
    },
    unavailable: {
      dot: 'bg-red-400',
      label: 'Unavailable',
      labelClass: 'text-red-400',
    },
  }[healthState]

  return (
    <div className="flex items-center gap-3 rounded-full border border-violet-400/15 bg-violet-500/[0.035] px-3.5 py-1.5 shadow-[0_0_24px_rgba(139,92,246,0.04)]">
      <div
        className={[
          'size-2 rounded-full',
          configuration.dot,
        ].join(' ')}
      />

      <span className="text-xs text-slate-500">
        API status
      </span>

      <div className="h-3.5 w-px bg-white/10" />

      <span
        className={[
          'text-xs font-medium',
          configuration.labelClass,
        ].join(' ')}
      >
        {configuration.label}
      </span>
    </div>
  )
}
