import type {
  EnterpriseDetail,
  EnterpriseSummary,
  HealthResponse,
  ReplayRunResponse,
  RunEventsResponse,
  RunResponse,
  ScenarioCapabilities,
  ScenarioDetail,
  ScenarioSummary,
  StartRunRequest,
  StartRunResponse,
  StopRunResponse,
} from '../types/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function encodePathSegment(segment: string): string {
  return encodeURIComponent(segment)
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `/api${path}`
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorJson = await response.json()
      if (errorJson && typeof errorJson.detail === 'string') {
        errorMessage = errorJson.detail
      }
    } catch {
      // Fallback to HTTP status message
    }
    throw new ApiError(response.status, errorMessage)
  }

  return response.json() as Promise<T>
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function listEnterprises(): Promise<EnterpriseSummary[]> {
  return request<EnterpriseSummary[]>('/enterprises')
}

export function getEnterprise(
  enterpriseId: string,
): Promise<EnterpriseDetail> {
  return request<EnterpriseDetail>(
    `/enterprises/${encodePathSegment(enterpriseId)}`,
  )
}

export function listScenarios(): Promise<ScenarioSummary[]> {
  return request<ScenarioSummary[]>('/scenarios')
}

export function getScenario(
  scenarioId: string,
): Promise<ScenarioDetail> {
  return request<ScenarioDetail>(
    `/scenarios/${encodePathSegment(scenarioId)}`,
  )
}

export function getScenarioCapabilities(
  scenarioId: string,
): Promise<ScenarioCapabilities> {
  return request<ScenarioCapabilities>(
    `/scenarios/${encodePathSegment(scenarioId)}/capabilities`,
  )
}

export function startRun(
  payload: StartRunRequest,
): Promise<StartRunResponse> {
  return request<StartRunResponse>('/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listRuns(
  status?: string,
): Promise<RunResponse[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return request<RunResponse[]>(`/runs${query}`)
}

export function getRun(
  runId: string,
): Promise<RunResponse> {
  return request<RunResponse>(
    `/runs/${encodePathSegment(runId)}`,
  )
}

export function getRunEvents(
  runId: string,
): Promise<RunEventsResponse> {
  return request<RunEventsResponse>(
    `/runs/${encodePathSegment(runId)}/events`,
  )
}

export function stopRun(
  runId: string,
): Promise<StopRunResponse> {
  return request<StopRunResponse>(
    `/runs/${encodePathSegment(runId)}/stop`,
    {
      method: 'POST',
    },
  )
}

export function replayRun(
  runId: string,
): Promise<ReplayRunResponse> {
  return request<ReplayRunResponse>(
    `/runs/${encodePathSegment(runId)}/replay`,
    {
      method: 'POST',
    },
  )
}
