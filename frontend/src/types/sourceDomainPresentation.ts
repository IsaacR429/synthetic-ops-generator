import type { SourceDomain } from "./api.ts"

export interface SourceDomainOption {
  value: SourceDomain
  label: string
}

export const SOURCE_DOMAIN_OPTIONS: readonly SourceDomainOption[] = [
  { value: 'itsm', label: 'ITSM' },
  { value: 'deployment', label: 'Deployment' },
  { value: 'application_test', label: 'Application Test' },
  { value: 'infrastructure_test', label: 'Infrastructure Test' },
  { value: 'metric', label: 'Metric' },
  { value: 'log', label: 'Log' },
  { value: 'manual_validation', label: 'Manual Validation' },
  { value: 'incident', label: 'Incident' },
  { value: 'evidence', label: 'Evidence' },
  { value: 'resilience', label: 'Resilience' },
]

export function formatSourceDomain(
  value: SourceDomain,
): string {
  return (
    SOURCE_DOMAIN_OPTIONS.find(
      (option) => option.value === value,
    )?.label ?? value
  )
}
