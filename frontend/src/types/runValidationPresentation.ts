export const EXECUTION_VALIDATION_LABEL =
  'Execution Validation'

export function formatExecutionValidation(
  validationPassed: boolean | null,
  isRunning: boolean,
): string {
  if (validationPassed === null) {
    return isRunning
      ? 'Pending'
      : 'Not reported'
  }

  return validationPassed
    ? 'Passed'
    : 'Failed'
}
