import { useEffect, useMemo, useState } from 'react'

import {
  getScenarioCapabilities,
  listEnterprises,
  listScenarios,
} from '../api/client'
import type {
  EnterpriseSummary,
  RunExecutionMode,
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

export function RunConfigurationPage() {
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
  const [randomSeedInput, setRandomSeedInput] = useState('42')
  const [degradationSamplesInput, setDegradationSamplesInput] = useState('')
  const [plateauSamplesInput, setPlateauSamplesInput] = useState('')
  const [recoverySamplesInput, setRecoverySamplesInput] = useState('')

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

  const configurationReady =
    selectedScenario !== undefined &&
    capabilities !== null &&
    executionModeSupported &&
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
    }
  }, [
    configurationReady,
    degradationSamples,
    executionMode,
    plateauSamples,
    randomSeed,
    recoverySamples,
    selectedScenarioId,
  ])

  const handleEnterpriseChange = (enterpriseId: string) => {
    setSelectedEnterpriseId(enterpriseId)
    setSelectedScenarioId('')
    setCapabilities(null)
  }

  const handleScenarioChange = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId)
    setCapabilities(null)
    setCapabilityError(null)
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
            <div className="rounded-xl border border-violet-400/10 bg-gradient-to-br from-violet-500/[0.04] via-white/[0.02] to-transparent p-6 shadow-[0_18px_50px_rgba(49,16,101,0.06)]">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
                1. Select Enterprise
              </label>

              <select
                value={selectedEnterpriseId}
                onChange={(e) => handleEnterpriseChange(e.target.value)}
                className="mt-3 w-full rounded-lg border border-violet-400/15 bg-[#0b0914] px-3.5 py-2.5 text-sm text-white focus:border-violet-400/40 focus:outline-none"
              >
                <option value="">-- Choose Enterprise --</option>
                {enterprises.map((enterprise) => (
                  <option
                    key={enterprise.enterprise_id}
                    value={enterprise.enterprise_id}
                  >
                    {enterprise.name} ({formatLabel(enterprise.industry)})
                  </option>
                ))}
              </select>

              {selectedEnterprise && (
                <div className="mt-3 text-xs text-slate-400">
                  Target Industry:{' '}
                  <span className="font-medium text-slate-200">
                    {formatLabel(selectedEnterprise.industry)}
                  </span>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-violet-400/10 bg-gradient-to-br from-violet-500/[0.04] via-white/[0.02] to-transparent p-6 shadow-[0_18px_50px_rgba(49,16,101,0.06)]">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-400/80">
                2. Select Scenario
              </label>

              <select
                disabled={!selectedEnterpriseId}
                value={selectedScenarioId}
                onChange={(e) => handleScenarioChange(e.target.value)}
                className="mt-3 w-full rounded-lg border border-violet-400/15 bg-[#0b0914] px-3.5 py-2.5 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50 focus:border-violet-400/40 focus:outline-none"
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
                    {scenario.scenario_id} - {scenario.name}
                  </option>
                ))}
              </select>

              {availableScenarios.length > 0 && (
                <div className="mt-3 text-xs text-slate-400">
                  {availableScenarios.length} scenario(s) available for{' '}
                  {selectedEnterprise?.name}.
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-7">
            {!selectedScenario ? (
              <div className="flex h-full min-h-[300px] items-center justify-center rounded-xl border border-dashed border-violet-400/15 bg-violet-500/[0.015] p-8 text-center text-sm text-slate-500">
                Select an enterprise and scenario to inspect details and
                execution capabilities.
              </div>
            ) : (
              <div className="relative overflow-hidden rounded-xl border border-violet-400/10 bg-gradient-to-br from-violet-500/[0.06] via-white/[0.02] to-transparent p-6 shadow-[0_18px_50px_rgba(49,16,101,0.08)]">
                <div className="pointer-events-none absolute -right-20 -top-24 size-64 rounded-full bg-violet-600/10 blur-3xl" />

                <div className="relative">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="font-mono text-xs font-semibold text-violet-400">
                        {selectedScenario.scenario_id}
                      </div>

                      <h3 className="mt-1 text-lg font-semibold text-white">
                        {selectedScenario.name}
                      </h3>
                    </div>

                    <span className="rounded-full border border-violet-400/20 bg-violet-500/10 px-3 py-1 text-xs font-medium text-violet-300">
                      {selectedEnterprise?.name}
                    </span>
                  </div>

                  <p className="mt-3 text-xs leading-relaxed text-slate-400">
                    {selectedScenario.description}
                  </p>

                  <div className="mt-4 border-t border-white/8 pt-4">
                    <div className="text-xs font-semibold text-white">
                      Target scope
                    </div>

                    <div className="mt-2 text-xs text-slate-400">
                      Enterprise:{' '}
                      <span className="font-mono font-medium text-slate-200">
                        {selectedScenario.enterprise_id}
                      </span>
                    </div>
                  </div>

                  <div className="mt-5 border-t border-white/8 pt-5">
                    <div className="text-xs font-semibold text-white">
                      Execution capabilities
                    </div>

                    {loadingCapabilities && (
                      <div className="mt-3 text-xs text-slate-500">
                        Discovering capabilities...
                      </div>
                    )}

                    {capabilityError && (
                      <div className="mt-3 text-xs text-red-300">
                        {capabilityError}
                      </div>
                    )}

                    {capabilities && (
                      <>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {capabilities.execution_modes.map((mode) => (
                            <span
                              key={mode}
                              className="rounded-full border border-violet-400/15 bg-violet-500/[0.07] px-3 py-1 text-[11px] font-medium text-violet-200"
                            >
                              {formatLabel(mode)}
                            </span>
                          ))}
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
                    <div className="mt-5 border-t border-white/8 pt-5">
                      <div className="text-xs font-semibold text-white">
                        Run parameters
                      </div>

                      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                          <label
                            htmlFor="execution-mode"
                            className="text-[11px] font-medium text-slate-400"
                          >
                            Execution mode
                          </label>

                          <select
                            id="execution-mode"
                            value={executionMode}
                            onChange={(event) =>
                              setExecutionMode(
                                event.target.value as RunExecutionMode,
                              )
                            }
                            className="mt-2 w-full rounded-lg border border-violet-400/15 bg-[#090711] px-3 py-2.5 text-sm text-white focus:border-violet-400/40 focus:outline-none"
                          >
                            {capabilities.execution_modes.map((mode) => (
                              <option key={mode} value={mode}>
                                {formatLabel(mode)}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label
                            htmlFor="random-seed"
                            className="text-[11px] font-medium text-slate-400"
                          >
                            Random seed
                          </label>

                          <input
                            id="random-seed"
                            type="number"
                            step="1"
                            value={randomSeedInput}
                            onChange={(event) =>
                              setRandomSeedInput(event.target.value)
                            }
                            className="mt-2 w-full rounded-lg border border-violet-400/15 bg-[#090711] px-3 py-2.5 text-sm text-white focus:border-violet-400/40 focus:outline-none"
                          />
                        </div>
                      </div>

                      {!randomSeedValid && (
                        <div className="mt-2 text-[11px] text-red-300">
                          Random seed must be a valid integer.
                        </div>
                      )}

                      {executionMode === 'historical' && (
                        <div className="mt-5 border-t border-white/6 pt-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-400/80">
                            Historical perturbation curve
                          </div>

                          <div className="mt-3 grid grid-cols-3 gap-3">
                            <div>
                              <label
                                htmlFor="degradation-samples"
                                className="text-[11px] font-medium text-slate-400"
                              >
                                Degradation
                              </label>

                              <input
                                id="degradation-samples"
                                type="number"
                                min="1"
                                step="1"
                                value={degradationSamplesInput}
                                onChange={(event) =>
                                  setDegradationSamplesInput(event.target.value)
                                }
                                className="mt-2 w-full rounded-lg border border-violet-400/15 bg-[#090711] px-3 py-2.5 text-sm text-white focus:border-violet-400/40 focus:outline-none"
                              />
                            </div>

                            <div>
                              <label
                                htmlFor="plateau-samples"
                                className="text-[11px] font-medium text-slate-400"
                              >
                                Plateau
                              </label>

                              <input
                                id="plateau-samples"
                                type="number"
                                min="0"
                                step="1"
                                value={plateauSamplesInput}
                                onChange={(event) =>
                                  setPlateauSamplesInput(event.target.value)
                                }
                                className="mt-2 w-full rounded-lg border border-violet-400/15 bg-[#090711] px-3 py-2.5 text-sm text-white focus:border-violet-400/40 focus:outline-none"
                              />
                            </div>

                            <div>
                              <label
                                htmlFor="recovery-samples"
                                className="text-[11px] font-medium text-slate-400"
                              >
                                Recovery
                              </label>

                              <input
                                id="recovery-samples"
                                type="number"
                                min="0"
                                step="1"
                                value={recoverySamplesInput}
                                onChange={(event) =>
                                  setRecoverySamplesInput(event.target.value)
                                }
                                className="mt-2 w-full rounded-lg border border-violet-400/15 bg-[#090711] px-3 py-2.5 text-sm text-white focus:border-violet-400/40 focus:outline-none"
                              />
                            </div>
                          </div>

                          {!historicalConfigurationValid && (
                            <div className="mt-3 text-[11px] leading-5 text-red-300">
                              Degradation must be greater than zero. Plateau and
                              recovery must be zero or greater.
                            </div>
                          )}
                        </div>
                      )}

                      <div className="mt-6 rounded-lg border border-white/8 bg-black/15 p-4">
                        <div className="flex items-center justify-between gap-4">
                          <div>
                            <div className="text-xs font-semibold text-white">
                              Configuration status
                            </div>

                            <div className="mt-1 text-[11px] text-slate-500">
                              {configurationReady
                                ? 'Run configuration is valid and ready for execution.'
                                : 'Complete the required configuration before execution.'}
                            </div>
                          </div>

                          <div
                            className={[
                              'rounded-full border px-3 py-1',
                              'text-[10px] font-semibold',
                              'uppercase tracking-[0.10em]',
                              configurationReady
                                ? [
                                    'border-emerald-400/15',
                                    'bg-emerald-400/[0.06]',
                                    'text-emerald-300',
                                  ].join(' ')
                                : [
                                    'border-slate-600/30',
                                    'bg-white/[0.025]',
                                    'text-slate-500',
                                  ].join(' '),
                            ].join(' ')}
                          >
                            {configurationReady ? 'Ready' : 'Incomplete'}
                          </div>
                        </div>
                      </div>

                      {startRunRequest && (
                        <details className="mt-4 rounded-lg border border-violet-400/10 bg-black/10">
                          <summary className="cursor-pointer px-4 py-3 text-[11px] font-medium text-violet-300">
                            Request preview
                          </summary>

                          <pre className="overflow-x-auto border-t border-white/6 px-4 py-4 font-mono text-[11px] leading-5 text-slate-400">
                            {JSON.stringify(startRunRequest, null, 2)}
                          </pre>
                        </details>
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