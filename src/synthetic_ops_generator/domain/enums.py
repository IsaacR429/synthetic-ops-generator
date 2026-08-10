from enum import StrEnum


class Industry(StrEnum):
    BANKING = "banking"
    INSURANCE = "insurance"


class Environment(StrEnum):
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Criticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OperationalState(StrEnum):
    INITIALISING = "initialising"
    NORMAL = "normal"
    IMPLEMENTING = "implementing"
    OBSERVING = "observing"
    WARNING = "warning"
    DEGRADED = "degraded"
    FAILURE = "failure"
    ROLLBACK = "rollback"
    REMEDIATION = "remediation"
    RECOVERY = "recovery"
    COMPLETED = "completed"


class Decision(StrEnum):
    PASS = "pass"
    CONDITIONAL_PASS = "conditional_pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class Action(StrEnum):
    PROCEED = "proceed"
    REVIEW = "review"
    REMEDIATE = "remediate"
    ROLLBACK = "rollback"
    WAIVE = "waive"


class Outcome(StrEnum):
    SUCCESSFUL = "successful"
    DEGRADED = "degraded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    INCIDENT_CREATED = "incident_created"