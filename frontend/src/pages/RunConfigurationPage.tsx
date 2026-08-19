import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'

import {
  ApiError,
  getRun,
  getScenarioCapabilities,
  listEnterprises,
  listRuns,
  listScenarios,
  startRun,
  stopRun,
} from '../api/client'
import type {
  EnterpriseSummary,
  GenerationLifecycle,
  RunExecutionMode,
  RunResponse,
  RunStatus,
  ScenarioCapabilities,
  ScenarioSummary,
  StartRunRequest,
} from '../types/api'

function formatLabel(value: string): string {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function parseIntegerInput(value: string): number | null {
  const trimmed = value.trim()

  if (!/^-?\d+$/.test(trimmed)) {
    return null
  }

  const parsed = Number(trimmed)

  return Number.isSafeInteger(parsed) ? parsed : null
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

export function RunConfigurationPage() {
  const navigate = useNavigate()

  const [enterprises, setEnterprises] = useState<EnterpriseSummary[]>([])
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [selectedEnterpriseId, setSelectedEnterpriseId] = useState<string>('')
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('')
  const [capabilities, setCapabilities] =
    useState<ScenarioCapabilities | null>(null)
  const [loadingDiscovery, setLoadingDiscovery] = useState<boolean>(true)
  const [loadingCapabilities, setLoadingCapabilities] =
    useState<boolean>(false)
  const [discoveryError, setDiscoveryError] = useState<string | null>(null)
  const [capabilityError, setCapabilityError] = useState<string | null>(null)

  const [executionMode, setExecutionMode] =
    useState<RunExecutionMode>('standard')
  const [generationLifecycle, setGenerationLifecycle] =
    useState<GenerationLifecycle>('bounded')
  const [randomSeedInput, setRandomSeedInput] = useState('42')
  const [degradationSamplesInput, setDegradationSamplesInput] = useState('')
  const [plateauSamplesInput, setPlateauSamplesInput] = useState('')
  const [recoverySamplesInput, setRecoverySamplesInput] = useState('')

  const [activeRun, setActiveRun] = useState<RunResponse | null>(null)
  const [startingRun, setStartingRun] = useState(false)
  const [stoppingRun, setStoppingRun] = useState(false)
  const [executionError, setExecutionError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function recoverActiveRun() {
      try {
        const runningRuns = await listRuns('running')

        if (!active || runningRuns.length === 0) {
          return
        }

        const latestRunningRun = runningRuns.reduce(
          (latest, run) =>
            new Date(run.started_at).getTime() >
            new Date(latest.started_at).getTime()
              ? run
              : latest,
        )

        setActiveRun((currentRun) =>
          currentRun ?? latestRunningRun,
        )
      } catch {
        if (active) {
          setExecutionError(
            'StreamOps could not recover the active Run.',
          )
        }
      }
    }

    void recoverActiveRun()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true

    async function loadDiscovery() {
      try {
        setLoadingDiscovery(true)
        setDiscoveryError(null)

        const [enterprisesData, scenariosData] = await Promise.all([
          listEnterprises(),
          listScenarios(),
        ])

        if (!active) {
          return
        }

        setEnterprises(enterprisesData)
        setScenarios(scenariosData)
      } catch {
        if (active) {
          setDiscoveryError('Failed to discover enterprises and scenarios.')
        }
      } finally {
        if (active) {
          setLoadingDiscovery(false)
        }
      }
    }

    void loadDiscovery()

    return () => {
      active = false
    }
  }, [])

  const availableScenarios = useMemo(() => {
    if (!selectedEnterpriseId) {
      return []
    }
    return scenarios.filter((s) => s.enterprise_id === selectedEnterpriseId)
  }, [scenarios, selectedEnterpriseId])

  useEffect(() => {
    if (!selectedScenarioId) {
      setCapabilities(null)
      setLoadingCapabilities(false)
      setCapabilityError(null)
      return
    }

    let active = true

    async function loadCapabilities() {
      try {
        setLoadingCapabilities(true)
        setCapabilityError(null)

        const caps = await getScenarioCapabilities(selectedScenarioId)

        if (!active) {
          return
        }

        setCapabilities(caps)
      } catch {
        if (active) {
          setCapabilityError('Failed to load scenario capabilities.')
        }
      } finally {
        if (active) {
          setLoadingCapabilities(false)
        }
      }
    }

    void loadCapabilities()

    return () => {
      active = false
    }
  }, [selectedScenarioId])

  useEffect(() => {
    if (!capabilities) {
      setExecutionMode('standard')
      setDegradationSamplesInput('')
      setPlateauSamplesInput('')
      setRecoverySamplesInput('')
      return
    }

    const defaultMode = capabilities.execution_modes.includes('standard')
      ? 'standard'
      : capabilities.execution_modes[0]

    if (defaultMode) {
      setExecutionMode(defaultMode)
    }

    const defaultLifecycle =
      capabilities.generation_lifecycles.includes('bounded')
        ? 'bounded'
        : capabilities.generation_lifecycles[0]

    if (defaultLifecycle) {
      setGenerationLifecycle(defaultLifecycle)
    }

    const historicalDefaults = capabilities.historical.configuration

    if (historicalDefaults) {
      setDegradationSamplesInput(
        String(historicalDefaults.degradation_samples),
      )
      setPlateauSamplesInput(String(historicalDefaults.plateau_samples))
      setRecoverySamplesInput(String(historicalDefaults.recovery_samples))
    } else {
      setDegradationSamplesInput('')
      setPlateauSamplesInput('')
      setRecoverySamplesInput('')
    }
  }, [capabilities])

  const activeRunId = activeRun?.run_id
  const activeRunStatus = activeRun?.status

  useEffect(() => {
    if (!activeRunId || activeRunStatus !== 'running') {
      return
    }

    const currentRunId = activeRunId
    let cancelled = false
    let timeoutId: number | undefined

    async function pollRun() {
      try {
        const latest = await getRun(currentRunId)

        if (cancelled) {
          return
        }

        setActiveRun(latest)
        setExecutionError(null)

        if (latest.status === 'running') {
          timeoutId = window.setTimeout(() => {
            void pollRun()
          }, 1500)
        }
      } catch {
        if (cancelled) {
          return
        }

        setExecutionError('StreamOps could not refresh the live Run state.')

        timeoutId = window.setTimeout(() => {
          void pollRun()
        }, 3000)
      }
    }

    timeoutId = window.setTimeout(() => {
      void pollRun()
    }, 1500)

    return () => {
      cancelled = true

      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [activeRunId, activeRunStatus])

  const selectedEnterprise = useMemo(
    () => enterprises.find((e) => e.enterprise_id === selectedEnterpriseId),
    [enterprises, selectedEnterpriseId],
  )

  const selectedScenario = useMemo(
    () => scenarios.find((s) => s.scenario_id === selectedScenarioId),
    [scenarios, selectedScenarioId],
  )

  const randomSeed = parseIntegerInput(randomSeedInput)
  const degradationSamples = parseIntegerInput(degradationSamplesInput)
  const plateauSamples = parseIntegerInput(plateauSamplesInput)
  const recoverySamples = parseIntegerInput(recoverySamplesInput)

  const randomSeedValid = randomSeed !== null

  const historicalConfigurationValid =
    executionMode !== 'historical' ||
    (degradationSamples !== null &&
      degradationSamples > 0 &&
      plateauSamples !== null &&
      plateauSamples >= 0 &&
      recoverySamples !== null &&
      recoverySamples >= 0)

  const executionModeSupported =
    capabilities?.execution_modes.includes(executionMode) ?? false

  const generationLifecycleSupported =
    capabilities?.generation_lifecycles.includes(
      generationLifecycle,
    ) ?? false

  const executionConfigurationCompatible =
    !(
      executionMode === 'historical' &&
      generationLifecycle === 'continuous'
    )

  const configurationReady =
    selectedScenario !== undefined &&
    capabilities !== null &&
    executionModeSupported &&
    generationLifecycleSupported &&
    executionConfigurationCompatible &&
    randomSeedValid &&
    historicalConfigurationValid

  const startRunRequest: StartRunRequest | null = useMemo(() => {
    if (!configurationReady || !selectedScenarioId || randomSeed === null) {
      return null
    }

    if (
      executionMode === 'historical' &&
      degradationSamples !== null &&
      plateauSamples !== null &&
      recoverySamples !== null
    ) {
      return {
        scenario_id: selectedScenarioId,
        random_seed: randomSeed,
        execution_mode: executionMode,
        generation_lifecycle: generationLifecycle,
        historical: {
          degradation_samples: degradationSamples,
          plateau_samples: plateauSamples,
          recovery_samples: recoverySamples,
        },
      }
    }

    return {
      scenario_id: selectedScenarioId,
      random_seed: randomSeed,
      execution_mode: executionMode,
      generation_lifecycle: generationLifecycle,
    }
  }, [
    configurationReady,
    degradationSamples,
    executionMode,
    generationLifecycle,
    plateauSamples,
    randomSeed,
    recoverySamples,
    selectedScenarioId,
  ])

  const handleEnterpriseChange = (enterpriseId: string) => {
    setSelectedEnterpriseId(enterpriseId)
    setSelectedScenarioId('')
    setCapabilities(null)

    setActiveRun(null)
    setExecutionError(null)
  }

  const handleScenarioChange = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId)
    setCapabilities(null)
    setCapabilityError(null)

    setActiveRun(null)
    setExecutionError(null)
  }

  async function handleStartRun() {
    if (!startRunRequest || startingRun || activeRun?.status === 'running') {
      return
    }

    try {
      setStartingRun(true)
      setExecutionError(null)

      const started = await startRun(startRunRequest)
      const current = await getRun(started.run_id)

      setActiveRun(current)
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : 'StreamOps could not start the Run.'

      setExecutionError(message)
    } finally {
      setStartingRun(false)
    }
  }

  async function handleStopRun() {
    if (!activeRun || activeRun.status !== 'running' || stoppingRun) {
      return
    }

    const runId = activeRun.run_id

    try {
      setStoppingRun(true)
      setExecutionError(null)

      try {
        await stopRun(runId)
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 409)) {
          throw error
        }
      }

      const latest = await getRun(runId)
      setActiveRun(latest)
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : 'StreamOps could not stop the Run.'

      setExecutionError(message)
    } finally {
      setStoppingRun(false)
    }
  }

  return (
    <section>
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
          Simulation
        </div>

        <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.025em] text-white">
          Configure Run
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Configure a synthetic operational run using discovered enterprise and
          scenario capabilities.
        </p>
      </div>

      {loadingDiscovery && (
        <div className="mt-8 rounded-xl border border-violet-400/10 bg-white/[0.02] p-8 text-center text-sm text-slate-400">
          Discovering enterprises and scenarios...
        </div>
      )}

      {discoveryError && (
        <div className="mt-8 rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-sm text-red-300">
          {discoveryError}
        </div>
      )}

      {!loadingDiscovery && !discoveryError && (
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-5">
            <div className="group relative overflow-hidden rounded-2xl border border-violet-400/10 bg-[#111428]/80 p-5 shadow-[0_14px_40px_rgba(2,6,23,0.16)]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-br from-violet-500/[0.13] via-fuchsia-500/[0.035] to-transparent" />

              <div className="pointer-events-none absolute left-0 top-0 h-px w-full bg-gradient-to-r from-violet-400/70 via-fuchsia-400/30 to-transparent" />

              <div className="relative">
                <div className="flex items-center gap-3">
                  <div className="flex size-8 items-center justify-center rounded-lg border border-violet-400/20 bg-violet-500/10 font-mono text-xs font-semibold text-violet-200">
                    01
                  </div>

                  <div>
                    <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-violet-300/70">
                      Target Discovery
                    </div>

                    <div className="mt-0.5 text-sm font-semibold text-white">
                      Select Enterprise
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <select
                    value={selectedEnterpriseId}
                    onChange={(e) =>
                      handleEnterpriseChange(e.target.value)
                    }
                    className="w-full rounded-xl border border-white/[0.08] bg-[#090b17]/85 px-4 py-3 text-sm text-slate-100 shadow-inner outline-none transition-all hover:border-violet-400/20 focus:border-violet-400/40 focus:ring-2 focus:ring-violet-500/10"
                  >
                    <option value="">
                      -- Choose Enterprise --
                    </option>

                    {enterprises.map((enterprise) => (
                      <option
                        key={enterprise.enterprise_id}
                        value={enterprise.enterprise_id}
                      >
                        {enterprise.name} (
                        {formatLabel(enterprise.industry)})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mt-4 flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-violet-300/70" />
                  <div className="h-px flex-1 bg-gradient-to-r from-violet-400/35 to-transparent" />
                </div>

                {selectedEnterprise && (
                  <div className="mt-3 flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                    <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      Industry
                    </span>

                    <span className="text-xs font-medium text-slate-200">
                      {formatLabel(
                        selectedEnterprise.industry,
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="group relative overflow-hidden rounded-2xl border border-cyan-400/10 bg-[#111428]/80 p-5 shadow-[0_14px_40px_rgba(2,6,23,0.16)]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-br from-cyan-500/[0.10] via-indigo-500/[0.035] to-transparent" />

              <div className="pointer-events-none absolute left-0 top-0 h-px w-full bg-gradient-to-r from-cyan-400/65 via-indigo-400/25 to-transparent" />

              <div className="relative">
                <div className="flex items-center gap-3">
                  <div className="flex size-8 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-500/10 font-mono text-xs font-semibold text-cyan-200">
                    02
                  </div>

                  <div>
                    <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-cyan-300/65">
                      Signal Definition
                    </div>

                    <div className="mt-0.5 text-sm font-semibold text-white">
                      Select Scenario
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <select
                    disabled={!selectedEnterpriseId}
                    value={selectedScenarioId}
                    onChange={(e) =>
                      handleScenarioChange(e.target.value)
                    }
                    className="w-full rounded-xl border border-white/[0.08] bg-[#090b17]/85 px-4 py-3 text-sm text-slate-100 shadow-inner outline-none transition-all hover:border-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-40 focus:border-cyan-400/40 focus:ring-2 focus:ring-cyan-500/10"
                  >
                    <option value="">
                      {selectedEnterpriseId
                        ? '-- Choose Scenario --'
                        : '-- Select Enterprise First --'}
                    </option>

                    {availableScenarios.map((scenario) => (
                      <option
                        key={scenario.scenario_id}
                        value={scenario.scenario_id}
                      >
                        {scenario.scenario_id} -{' '}
                        {scenario.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mt-4 flex items-center gap-2">
                  <span
                    className={[
                      'size-1.5 rounded-full',
                      selectedEnterpriseId
                        ? 'bg-cyan-300/70'
                        : 'bg-slate-600',
                    ].join(' ')}
                  />

                  <div className="h-px flex-1 bg-gradient-to-r from-cyan-400/30 to-transparent" />
                </div>

                {availableScenarios.length > 0 && (
                  <div className="mt-3 flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                    <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      Available
                    </span>

                    <span className="font-mono text-xs text-cyan-200">
                      {availableScenarios.length}{' '}
                      {availableScenarios.length === 1
                        ? 'scenario'
                        : 'scenarios'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            {!selectedScenario ? (
              <div className="relative flex h-full min-h-[300px] overflow-hidden rounded-2xl border border-white/[0.07] bg-[#101326]/55">
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-violet-500/[0.07] via-transparent to-cyan-500/[0.045]" />

                <div className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-violet-500/[0.08] blur-3xl" />

                <div className="pointer-events-none absolute -bottom-20 left-1/3 size-48 rounded-full bg-cyan-500/[0.06] blur-3xl" />

                <div className="relative flex w-full flex-col items-center justify-center px-8 py-12 text-center">
                  <div className="relative flex size-16 items-center justify-center rounded-2xl border border-white/[0.08] bg-black/10">
                    <div className="absolute size-10 rounded-full border border-violet-400/15" />

                    <div className="absolute size-6 rounded-full border border-cyan-400/20" />

                    <div className="size-2 rounded-full bg-gradient-to-br from-violet-300 to-cyan-300 shadow-[0_0_20px_rgba(103,232,249,0.28)]" />
                  </div>

                  <div className="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-300/65">
                    Scenario Intelligence
                  </div>

                  <div className="mt-2 text-base font-semibold text-slate-200">
                    Configure the operational signal
                  </div>

                  <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
                    Select an enterprise and scenario to
                    inspect its target, execution modes,
                    lifecycle capabilities, and generation
                    controls.
                  </p>

                  <div className="mt-6 flex items-center gap-2">
                    <span className="size-1.5 rounded-full bg-violet-400/70" />
                    <span className="h-px w-8 bg-gradient-to-r from-violet-400/40 to-cyan-400/30" />
                    <span className="size-1.5 rounded-full bg-cyan-400/70" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#111428]/80 p-6 shadow-[0_18px_55px_rgba(2,6,23,0.18)]">
                <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-br from-violet-500/[0.12] via-indigo-500/[0.045] to-cyan-500/[0.025]" />

                <div className="pointer-events-none absolute left-0 top-0 h-px w-full bg-gradient-to-r from-violet-400/75 via-fuchsia-400/35 to-cyan-400/30" />

                <div className="pointer-events-none absolute -right-20 -top-24 size-64 rounded-full bg-violet-500/[0.08] blur-3xl" />

                <div className="pointer-events-none absolute -bottom-32 left-1/3 size-56 rounded-full bg-cyan-500/[0.045] blur-3xl" />

                <div className="relative">
                  <div className="flex items-start justify-between gap-5">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="size-1.5 rounded-full bg-violet-300 shadow-[0_0_12px_rgba(196,181,253,0.35)]" />

                        <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-violet-300/80">
                          {selectedScenario.scenario_id}
                        </div>

                        <span className="h-px w-8 bg-gradient-to-r from-violet-400/45 to-transparent" />
                      </div>

                      <h3 className="mt-3 text-xl font-semibold tracking-[-0.025em] text-white">
                        {selectedScenario.name}
                      </h3>

                      <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
                        {selectedScenario.description}
                      </p>
                    </div>

                    <div className="shrink-0 rounded-xl border border-violet-400/15 bg-violet-500/[0.08] px-3 py-2">
                      <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-violet-300/55">
                        Enterprise
                      </div>

                      <div className="mt-1 text-xs font-medium text-violet-100">
                        {selectedEnterprise?.name}
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 grid grid-cols-1 gap-3 border-t border-white/[0.07] pt-5 sm:grid-cols-2">
                    <div className="rounded-xl border border-white/[0.06] bg-white/[0.018] px-4 py-3">
                      <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Target Enterprise
                      </div>

                      <div className="mt-2 font-mono text-xs text-violet-200">
                        {selectedScenario.enterprise_id}
                      </div>
                    </div>

                    <div className="relative overflow-hidden rounded-xl border border-cyan-400/[0.08] bg-cyan-500/[0.025] px-4 py-3">
                      <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-cyan-400/70 to-transparent" />

                      <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Operational Signal
                      </div>

                      <div className="mt-2 flex items-center gap-2 text-xs text-cyan-100">
                        <span className="size-1.5 rounded-full bg-cyan-300" />
                        Synthetic generation target
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 border-t border-white/[0.07] pt-5">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-cyan-300/60">
                          Capability Matrix
                        </div>

                        <div className="mt-1 text-sm font-semibold text-white">
                          Execution Capabilities
                        </div>
                      </div>

                      {capabilities && (
                        <div className="flex items-center gap-2 text-[10px] text-slate-500">
                          <span className="size-1.5 rounded-full bg-emerald-300" />
                          Discovered
                        </div>
                      )}
                    </div>

                    {loadingCapabilities && (
                      <div className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.018] px-4 py-3 text-xs text-slate-500">
                        Discovering capabilities...
                      </div>
                    )}

                    {capabilityError && (
                      <div className="mt-4 rounded-xl border border-red-500/15 bg-red-500/[0.06] px-4 py-3 text-xs text-red-300">
                        {capabilityError}
                      </div>
                    )}

                    {capabilities && (
                      <>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {capabilities.execution_modes.map((mode) => (
                            <span
                              key={mode}
                              className="inline-flex items-center gap-2 rounded-lg border border-violet-400/15 bg-violet-500/[0.07] px-3 py-2 text-[10px] font-medium text-violet-100"
                            >
                              <span className="size-1.5 rounded-full bg-violet-300/80" />
                              {formatLabel(mode)}
                            </span>
                          ))}

                          {capabilities.generation_lifecycles.map(
                            (lifecycle) => (
                              <span
                                key={lifecycle}
                                className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/15 bg-cyan-500/[0.055] px-3 py-2 text-[10px] font-medium text-cyan-100"
                              >
                                <span className="size-1.5 rounded-full bg-cyan-300/80" />
                                {formatLabel(lifecycle)}
                              </span>
                            ),
                          )}
                        </div>

                        {capabilities.historical.supported &&
                          capabilities.historical.configuration && (
                            <div className="mt-4 rounded-lg border border-violet-400/10 bg-violet-500/[0.035] p-4">
                              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-violet-400/75">
                                Historical defaults
                              </div>

                              <div className="mt-3 grid grid-cols-3 gap-3">
                                <div>
                                  <div className="text-sm font-semibold text-white">
                                    {
                                      capabilities.historical.configuration
                                        .degradation_samples
                                    }
                                  </div>

                                  <div className="mt-1 text-[10px] text-slate-600">
                                    Degradation
                                  </div>
                                </div>

                                <div>
                                  <div className="text-sm font-semibold text-white">
                                    {
                                      capabilities.historical.configuration
                                        .plateau_samples
                                    }
                                  </div>

                                  <div className="mt-1 text-[10px] text-slate-600">
                                    Plateau
                                  </div>
                                </div>

                                <div>
                                  <div className="text-sm font-semibold text-white">
                                    {
                                      capabilities.historical.configuration
                                        .recovery_samples
                                    }
                                  </div>

                                  <div className="mt-1 text-[10px] text-slate-600">
                                    Recovery
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                      </>
                    )}
                  </div>

                  {capabilities && (
                    <div className="mt-5 border-t border-white/[0.07] pt-5">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/60">
                            Generation Control
                          </div>

                          <div className="mt-1 text-sm font-semibold text-white">
                            Run Parameters
                          </div>
                        </div>

                        <div className="flex items-center gap-2 text-[10px] text-slate-500">
                          <span className="size-1.5 rounded-full bg-cyan-300/80" />
                          Runtime configuration
                        </div>
                      </div>

                      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border border-violet-400/[0.10] bg-violet-500/[0.025] p-3.5">
                          <label
                            htmlFor="execution-mode"
                            className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-500"
                          >
                            Execution Mode
                          </label>

                          <select
                            id="execution-mode"
                            value={executionMode}
                            onChange={(event) =>
                              setExecutionMode(
                                event.target.value as RunExecutionMode,
                              )
                            }
                            className="mt-2.5 w-full rounded-lg border border-violet-400/15 bg-[#090b17]/90 px-3.5 py-2.5 text-sm font-medium text-slate-100 outline-none transition-all hover:border-violet-400/25 focus:border-violet-400/45 focus:ring-2 focus:ring-violet-500/10"
                          >
                            {capabilities.execution_modes.map((mode) => (
                              <option
                                key={mode}
                                value={mode}
                                disabled={
                                  mode === 'historical' &&
                                  generationLifecycle === 'continuous'
                                }
                              >
                                {formatLabel(mode)}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="rounded-xl border border-cyan-400/[0.10] bg-cyan-500/[0.025] p-3.5">
                          <label
                            htmlFor="generation-lifecycle"
                            className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-500"
                          >
                            Generation Lifecycle
                          </label>

                          <select
                            id="generation-lifecycle"
                            value={generationLifecycle}
                            onChange={(event) =>
                              setGenerationLifecycle(
                                event.target.value as GenerationLifecycle,
                              )
                            }
                            disabled={!capabilities}
                            className="mt-2.5 w-full rounded-lg border border-cyan-400/15 bg-[#090b17]/90 px-3.5 py-2.5 text-sm font-medium text-slate-100 outline-none transition-all hover:border-cyan-400/25 disabled:cursor-not-allowed disabled:opacity-40 focus:border-cyan-400/45 focus:ring-2 focus:ring-cyan-500/10"
                          >
                            {capabilities?.generation_lifecycles.map(
                              (lifecycle) => (
                                <option
                                  key={lifecycle}
                                  value={lifecycle}
                                  disabled={
                                    lifecycle === 'continuous' &&
                                    executionMode === 'historical'
                                  }
                                >
                                  {formatLabel(lifecycle)}
                                </option>
                              ),
                            )}
                          </select>
                        </div>

                        <div className="rounded-xl border border-white/[0.07] bg-white/[0.018] p-3.5 sm:col-span-2">
                          <label
                            htmlFor="random-seed"
                            className="flex items-center justify-between gap-4"
                          >
                            <span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-500">
                              Random Seed
                            </span>

                            <span className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.10em] text-slate-600">
                              <span className="size-1 rounded-full bg-violet-300/70" />
                              Deterministic input
                            </span>
                          </label>

                          <input
                            id="random-seed"
                            type="number"
                            step="1"
                            value={randomSeedInput}
                            onChange={(event) =>
                              setRandomSeedInput(event.target.value)
                            }
                            className="mt-2.5 w-full rounded-lg border border-white/[0.08] bg-[#090b17]/90 px-3.5 py-2.5 font-mono text-sm font-medium text-slate-100 outline-none transition-all hover:border-white/20 focus:border-violet-400/45 focus:ring-2 focus:ring-violet-500/10"
                          />
                        </div>
                      </div>

                      {!randomSeedValid && (
                        <div className="mt-2 text-[11px] text-red-300">
                          Random seed must be a valid integer.
                        </div>
                      )}

                      {executionMode === 'historical' && (
                        <div className="mt-5 overflow-hidden rounded-xl border border-violet-400/[0.10] bg-violet-500/[0.025]">
                          <div className="border-b border-white/[0.06] px-4 py-3.5">
                            <div className="flex items-center justify-between gap-4">
                              <div>
                                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/65">
                                  Historical Simulation
                                </div>

                                <div className="mt-1 text-sm font-semibold text-white">
                                  Perturbation Curve
                                </div>
                              </div>

                              <div className="flex items-center gap-2 text-[9px] uppercase tracking-[0.10em] text-slate-600">
                                <span className="size-1.5 rounded-full bg-violet-300/70" />
                                Synthetic timeline
                              </div>
                            </div>
                          </div>

                          <div className="relative px-4 py-5">
                            <div className="pointer-events-none absolute left-[16%] right-[16%] top-[31px] h-px bg-gradient-to-r from-rose-400/25 via-amber-400/25 to-emerald-400/25" />

                            <div className="relative grid grid-cols-1 gap-3 sm:grid-cols-3">
                              <div className="rounded-xl border border-rose-400/[0.10] bg-rose-500/[0.025] p-3.5">
                                <div className="mb-3 flex items-center gap-2">
                                  <span className="size-2 rounded-full bg-rose-300/80" />

                                  <span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-rose-200/70">
                                    Degradation
                                  </span>
                                </div>

                                <input
                                  id="degradation-samples"
                                  type="number"
                                  min="1"
                                  step="1"
                                  value={degradationSamplesInput}
                                  onChange={(event) =>
                                    setDegradationSamplesInput(
                                      event.target.value,
                                    )
                                  }
                                  className="w-full rounded-lg border border-rose-400/10 bg-[#090b17]/90 px-3.5 py-2.5 font-mono text-sm text-rose-100 outline-none transition-all hover:border-rose-400/20 focus:border-rose-400/40 focus:ring-2 focus:ring-rose-500/10"
                                />
                              </div>

                              <div className="rounded-xl border border-amber-400/[0.10] bg-amber-500/[0.02] p-3.5">
                                <div className="mb-3 flex items-center gap-2">
                                  <span className="size-2 rounded-full bg-amber-300/80" />

                                  <span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-amber-200/70">
                                    Plateau
                                  </span>
                                </div>

                                <input
                                  id="plateau-samples"
                                  type="number"
                                  min="0"
                                  step="1"
                                  value={plateauSamplesInput}
                                  onChange={(event) =>
                                    setPlateauSamplesInput(
                                      event.target.value,
                                    )
                                  }
                                  className="w-full rounded-lg border border-amber-400/10 bg-[#090b17]/90 px-3.5 py-2.5 font-mono text-sm text-amber-100 outline-none transition-all hover:border-amber-400/20 focus:border-amber-400/40 focus:ring-2 focus:ring-amber-500/10"
                                />
                              </div>

                              <div className="rounded-xl border border-emerald-400/[0.10] bg-emerald-500/[0.02] p-3.5">
                                <div className="mb-3 flex items-center gap-2">
                                  <span className="size-2 rounded-full bg-emerald-300/80" />

                                  <span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-emerald-200/70">
                                    Recovery
                                  </span>
                                </div>

                                <input
                                  id="recovery-samples"
                                  type="number"
                                  min="0"
                                  step="1"
                                  value={recoverySamplesInput}
                                  onChange={(event) =>
                                    setRecoverySamplesInput(
                                      event.target.value,
                                    )
                                  }
                                  className="w-full rounded-lg border border-emerald-400/10 bg-[#090b17]/90 px-3.5 py-2.5 font-mono text-sm text-emerald-100 outline-none transition-all hover:border-emerald-400/20 focus:border-emerald-400/40 focus:ring-2 focus:ring-emerald-500/10"
                                />
                              </div>
                            </div>

                            {!historicalConfigurationValid && (
                              <div className="mt-4 rounded-lg border border-red-400/10 bg-red-500/[0.04] px-3.5 py-3 text-[11px] leading-5 text-red-300">
                                Degradation must be greater than zero.
                                Plateau and recovery must be zero or greater.
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      <div
                        className={[
                          'relative mt-6 overflow-hidden rounded-xl border p-4',
                          configurationReady
                            ? 'border-emerald-400/[0.12] bg-emerald-500/[0.025]'
                            : 'border-white/[0.07] bg-white/[0.018]',
                        ].join(' ')}
                      >
                        {configurationReady && (
                          <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-emerald-300/80 via-cyan-400/30 to-transparent" />
                        )}

                        <div className="flex items-center justify-between gap-5">
                          <div className="flex items-center gap-3">
                            <div
                              className={[
                                'flex size-9 items-center justify-center rounded-lg border',
                                configurationReady
                                  ? 'border-emerald-400/15 bg-emerald-500/[0.07]'
                                  : 'border-white/[0.07] bg-white/[0.02]',
                              ].join(' ')}
                            >
                              <span
                                className={[
                                  'size-2 rounded-full',
                                  configurationReady
                                    ? 'bg-emerald-300 shadow-[0_0_14px_rgba(110,231,183,0.30)]'
                                    : 'bg-slate-600',
                                ].join(' ')}
                              />
                            </div>

                            <div>
                              <div className="text-[9px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                                Configuration State
                              </div>

                              <div className="mt-1 text-sm font-semibold text-white">
                                {configurationReady
                                  ? 'Ready for execution'
                                  : 'Configuration incomplete'}
                              </div>

                              <div className="mt-1 text-[11px] text-slate-500">
                                {configurationReady
                                  ? 'Selected capabilities and parameters are compatible.'
                                  : 'Complete the required configuration before execution.'}
                              </div>
                            </div>
                          </div>

                          <div
                            className={[
                              'rounded-lg border px-3 py-1.5',
                              'text-[9px] font-semibold',
                              'uppercase tracking-[0.14em]',
                              configurationReady
                                ? [
                                    'border-emerald-400/15',
                                    'bg-emerald-400/[0.06]',
                                    'text-emerald-300',
                                  ].join(' ')
                                : [
                                    'border-white/[0.07]',
                                    'bg-white/[0.02]',
                                    'text-slate-500',
                                  ].join(' '),
                            ].join(' ')}
                          >
                            {configurationReady ? 'Ready' : 'Incomplete'}
                          </div>
                        </div>
                      </div>

                      {startRunRequest && (
                        <details className="group mt-3 overflow-hidden rounded-xl border border-violet-400/[0.08] bg-violet-500/[0.018]">
                          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <div className="flex size-7 items-center justify-center rounded-md border border-violet-400/10 bg-violet-500/[0.05] font-mono text-[10px] text-violet-300">
                                {'{ }'}
                              </div>

                              <div>
                                <div className="text-[10px] font-semibold text-violet-100">
                                  Request Preview
                                </div>

                                <div className="mt-0.5 text-[9px] text-slate-600">
                                  Canonical Start Run request
                                </div>
                              </div>
                            </div>

                            <span className="text-xs text-violet-300/60 transition-transform group-open:rotate-90">
                              →
                            </span>
                          </summary>

                          <pre className="max-h-72 overflow-auto border-t border-white/[0.06] bg-[#090b17]/70 px-4 py-4 font-mono text-[11px] leading-5 text-slate-400">
                            {JSON.stringify(
                              startRunRequest,
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      )}

                      <div className="relative mt-5 overflow-hidden rounded-xl border border-violet-400/[0.10] bg-gradient-to-r from-violet-500/[0.055] via-indigo-500/[0.025] to-cyan-500/[0.018] p-4">
                        <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-violet-300/80 to-cyan-400/20" />

                        <div className="flex flex-wrap items-center justify-between gap-5">
                          <div>
                            <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300/65">
                              Execution Control
                            </div>

                            <div className="mt-1.5 text-sm font-semibold text-white">
                              Start synthetic run
                            </div>

                            <p className="mt-1 text-[11px] leading-5 text-slate-500">
                              Submit the validated configuration to the
                              StreamOps control plane.
                            </p>
                          </div>

                          <button
                            type="button"
                            disabled={
                              !startRunRequest ||
                              startingRun ||
                              activeRun?.status === 'running'
                            }
                            onClick={() => {
                              void handleStartRun()
                            }}
                            className={[
                              'group relative overflow-hidden rounded-xl px-5 py-3',
                              'text-xs font-semibold transition-all duration-200',
                              !startRunRequest ||
                              startingRun ||
                              activeRun?.status === 'running'
                                ? [
                                    'cursor-not-allowed',
                                    'border border-white/[0.06]',
                                    'bg-white/[0.025]',
                                    'text-slate-600',
                                  ].join(' ')
                                : [
                                    'border border-violet-400/25',
                                    'bg-gradient-to-r',
                                    'from-violet-600/90',
                                    'via-purple-500/85',
                                    'to-indigo-500/80',
                                    'text-white',
                                    'shadow-[0_12px_35px_rgba(124,58,237,0.22)]',
                                    'hover:-translate-y-0.5',
                                    'hover:shadow-[0_16px_40px_rgba(124,58,237,0.28)]',
                                  ].join(' '),
                            ].join(' ')}
                          >
                            <span className="relative flex items-center gap-3">
                              <span>
                                {startingRun
                                  ? 'Starting...'
                                  : activeRun?.status === 'running'
                                    ? 'Run Active'
                                    : 'Start Run'}
                              </span>

                              {!startingRun &&
                                activeRun?.status !== 'running' && (
                                  <span className="text-violet-100/70">
                                    →
                                  </span>
                                )}
                            </span>
                          </button>
                        </div>
                      </div>

                      {executionError && (
                        <div className="mt-4 rounded-lg border border-red-400/15 bg-red-500/[0.05] px-4 py-3 text-[11px] leading-5 text-red-300">
                          {executionError}
                        </div>
                      )}

                      {activeRun && (
                        <div className="mt-6 overflow-hidden rounded-xl border border-violet-400/15 bg-[#0b0914] shadow-[0_14px_45px_rgba(2,6,23,0.22)]">
                          <div className="flex items-center justify-between gap-4 border-b border-white/[0.07] bg-white/[0.02] px-5 py-4">
                            <div>
                              <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300/70">
                                Live Execution
                              </div>

                              <div className="mt-1 flex flex-wrap items-center gap-2">
                                <span className="font-mono text-sm font-semibold text-white">
                                  {activeRun.run_id}
                                </span>

                                <span className="text-slate-600">·</span>

                                <span className="font-mono text-xs text-slate-400">
                                  {activeRun.scenario_id}
                                </span>

                                <span className="text-slate-600">·</span>

                                <span className="text-xs text-slate-400">
                                  {formatLabel(activeRun.execution_mode)}
                                </span>
                              </div>
                            </div>

                            <div
                              className={[
                                'rounded-full border px-3 py-1',
                                'text-[10px] font-semibold',
                                'uppercase tracking-[0.10em]',
                                runStatusClasses(activeRun.status),
                              ].join(' ')}
                            >
                              {activeRun.status}
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-px bg-white/[0.06] sm:grid-cols-4">
                            <div className="p-4">
                              <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-600">
                                Current State
                              </div>

                              <div className="mt-2 text-sm font-semibold text-white">
                                {formatLabel(activeRun.current_state)}
                              </div>
                            </div>

                            <div className="p-4">
                              <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-600">
                                Events
                              </div>

                              <div className="mt-2 font-mono text-sm font-semibold text-cyan-200">
                                {activeRun.event_count}
                              </div>
                            </div>

                            <div className="p-4">
                              <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-600">
                                Started
                              </div>

                              <div className="mt-2 font-mono text-xs font-medium text-slate-200">
                                {formatRunTime(
                                  activeRun.started_at,
                                )}
                              </div>
                            </div>

                            <div className="p-4">
                              <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-slate-600">
                                Validation
                              </div>

                              <div
                                className={[
                                  'mt-2 text-sm font-semibold',
                                  activeRun.validation_passed === true
                                    ? 'text-emerald-300'
                                    : activeRun.validation_passed === false
                                      ? 'text-red-300'
                                      : 'text-slate-300',
                                ].join(' ')}
                              >
                                {activeRun.validation_passed === null
                                  ? activeRun.status === 'running'
                                    ? 'Pending'
                                    : 'Not reported'
                                  : activeRun.validation_passed
                                    ? 'Passed'
                                    : 'Failed'}
                              </div>
                            </div>
                          </div>

                          {activeRun.error_message && (
                            <div className="border-t border-red-400/[0.10] bg-red-500/[0.04] px-5 py-3 text-[11px] leading-5 text-red-300">
                              {activeRun.error_message}
                            </div>
                          )}

                          <div className="relative flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] px-5 py-4">
                            <div className="flex items-center gap-2 text-[9px] uppercase tracking-[0.12em] text-slate-600">
                              <span
                                className={[
                                  'size-1.5 rounded-full',
                                  activeRun.status === 'running'
                                    ? 'bg-cyan-300'
                                    : 'bg-slate-600',
                                ].join(' ')}
                              />

                              {activeRun.status === 'running'
                                ? 'Telemetry active'
                                : 'Execution retained'}
                            </div>

                            <div className="flex items-center gap-3">
                              {activeRun.status === 'running' && (
                                <button
                                  type="button"
                                  disabled={stoppingRun}
                                  onClick={() => {
                                    void handleStopRun()
                                  }}
                                  className="rounded-lg border border-red-400/15 bg-red-500/[0.04] px-4 py-2.5 text-[10px] font-medium text-red-300 transition-all hover:border-red-400/25 hover:bg-red-500/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  {stoppingRun
                                    ? 'Stopping...'
                                    : 'Stop Run'}
                                </button>
                              )}

                              <button
                                type="button"
                                onClick={() =>
                                  navigate(
                                    `/runs/${activeRun.run_id}`,
                                  )
                                }
                                className="group rounded-lg border border-violet-400/15 bg-violet-500/[0.055] px-4 py-2.5 text-[10px] font-medium text-violet-100 transition-all hover:border-violet-400/25 hover:bg-violet-500/[0.10]"
                              >
                                <span className="flex items-center gap-2">
                                  Inspect Run

                                  <span className="text-violet-300/60 transition-transform group-hover:translate-x-0.5">
                                    →
                                  </span>
                                </span>
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}