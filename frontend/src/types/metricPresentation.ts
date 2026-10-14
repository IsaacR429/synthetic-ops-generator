export interface MetricCapacityPayload {
  capacity_profile_id?: unknown
  classification?: unknown
  direction?: unknown
  pressure_threshold?: unknown
  saturation_threshold?: unknown
}

export interface MetricPayload {
  name?: unknown
  observed_value?: unknown
  unit?: unknown
  classification?: unknown
  evaluation_statistic?: unknown
  direction?: unknown
  scenario_state?: unknown

  baseline?: {
    center?: unknown
    lower_bound?: unknown
    upper_bound?: unknown
  }

  effective_benchmark?: {
    reference_target?: unknown
    warning_threshold?: unknown
    blocking_threshold?: unknown
  }

  capacity?: MetricCapacityPayload
}

export function getMetricPayload(
  data: Record<string, unknown>,
): MetricPayload | null {
  const metric = data.metric

  if (
    !metric ||
    typeof metric !== 'object' ||
    Array.isArray(metric)
  ) {
    return null
  }

  return metric as MetricPayload
}

export function getMetricClassification(
  metric: MetricPayload | null,
): string | null {
  return typeof metric?.classification === 'string'
    ? metric.classification
    : null
}

export function getCapacityClassification(
  metric: MetricPayload | null,
): string | null {
  return typeof metric?.capacity?.classification === 'string'
    ? metric.capacity.classification
    : null
}
