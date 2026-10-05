from synthetic_ops_generator.domain.enums import (
    SourceDomain,
)


APPROVED_CHANGE = "approved_change"
MISSING_REQUIRED_APPROVAL = "missing_required_approval"

HEALTHY_BASELINE = "healthy_baseline"
HEALTHY_POST_CHANGE = "healthy_post_change"
DEGRADED_POST_CHANGE = "degraded_post_change"
RECOVERED_POST_ROLLBACK = "recovered_post_rollback"
OPERATIONAL_DEGRADATION = "operational_degradation"
OPERATIONAL_RECOVERY = "operational_recovery"
OPERATIONAL_WARNING = "operational_warning"
CAPACITY_PRESSURE = "capacity_pressure"
CAPACITY_SATURATION = "capacity_saturation"
CAPACITY_RECOVERY = "capacity_recovery"

ALL_REQUIRED_CHECKS_PASS = "all_required_checks_pass"
REQUIRED_CHECK_FAILED = "required_check_failed"

SUCCESSFUL_DEPLOYMENT = "successful_deployment"
FAILED_DEPLOYMENT = "failed_deployment"
SUCCESSFUL_ROLLBACK = "successful_rollback"

ALL_MANDATORY_TESTS_PASS = "all_mandatory_tests_pass"
MANDATORY_TEST_REGRESSION = "mandatory_test_regression"

NORMAL_OPERATIONAL_LOGS = "normal_operational_logs"
DEGRADATION_ERROR_LOGS = "degradation_error_logs"
RECOVERY_OPERATIONAL_LOGS = "recovery_operational_logs"

ALL_REQUIRED_VALIDATIONS_PASS = (
    "all_required_validations_pass"
)

NO_INCIDENT = "no_incident"
INCIDENT_CREATED = "incident_created"
INCIDENT_RESOLVED = "incident_resolved"

COMPLETE_VALIDATION_EVIDENCE = (
    "complete_validation_evidence"
)
INCOMPLETE_VALIDATION_EVIDENCE = (
    "incomplete_validation_evidence"
)
ROLLBACK_VALIDATION_EVIDENCE = (
    "rollback_validation_evidence"
)


SUPPORTED_PROFILES_BY_SOURCE: dict[
    SourceDomain,
    frozenset[str],
] = {
    SourceDomain.ITSM: frozenset(
        {
            APPROVED_CHANGE,
            MISSING_REQUIRED_APPROVAL,
        }
    ),
    SourceDomain.METRIC: frozenset(
        {
            HEALTHY_BASELINE,
            HEALTHY_POST_CHANGE,
            DEGRADED_POST_CHANGE,
            RECOVERED_POST_ROLLBACK,
            OPERATIONAL_DEGRADATION,
            OPERATIONAL_RECOVERY,
            OPERATIONAL_WARNING,
            CAPACITY_PRESSURE,
            CAPACITY_SATURATION,
            CAPACITY_RECOVERY,
        }
    ),
    SourceDomain.INFRASTRUCTURE_TEST: frozenset(
        {
            ALL_REQUIRED_CHECKS_PASS,
            REQUIRED_CHECK_FAILED,
        }
    ),
    SourceDomain.DEPLOYMENT: frozenset(
        {
            SUCCESSFUL_DEPLOYMENT,
            FAILED_DEPLOYMENT,
            SUCCESSFUL_ROLLBACK,
        }
    ),
    SourceDomain.APPLICATION_TEST: frozenset(
        {
            ALL_MANDATORY_TESTS_PASS,
            MANDATORY_TEST_REGRESSION,
        }
    ),
    SourceDomain.LOG: frozenset(
        {
            NORMAL_OPERATIONAL_LOGS,
            DEGRADATION_ERROR_LOGS,
            RECOVERY_OPERATIONAL_LOGS,
        }
    ),
    SourceDomain.MANUAL_VALIDATION: frozenset(
        {
            ALL_REQUIRED_VALIDATIONS_PASS,
        }
    ),
    SourceDomain.INCIDENT: frozenset(
        {
            NO_INCIDENT,
            INCIDENT_CREATED,
            INCIDENT_RESOLVED,
        }
    ),
    SourceDomain.EVIDENCE: frozenset(
        {
            COMPLETE_VALIDATION_EVIDENCE,
            INCOMPLETE_VALIDATION_EVIDENCE,
            ROLLBACK_VALIDATION_EVIDENCE,
        }
    ),
}
