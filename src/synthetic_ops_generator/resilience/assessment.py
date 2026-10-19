from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from synthetic_ops_generator.domain.enums import (
    Environment,
)
from synthetic_ops_generator.resilience.exposure import (
    ReplicationExposureMeasurement,
    ReplicationExposureMeasurementStatus,
)
from synthetic_ops_generator.resilience.objectives import (
    RecoveryObjective,
)
from synthetic_ops_generator.resilience.recovery import (
    RecoveryMeasurement,
    RecoveryMeasurementStatus,
)


class RecoveryObjectiveAssessmentStatus(StrEnum):
    """
    Outcome of comparing one measured recovery quantity
    with one applicable declared objective.
    """

    MET = "met"
    BREACHED = "breached"
    INDETERMINATE = "indeterminate"


class RecoveryObjectiveAssessmentType(StrEnum):
    RTO = "rto"
    RPO = "rpo"


class RecoveryObjectiveAssessmentContext(BaseModel):
    """
    Enterprise evaluation context not carried by factual
    recovery measurements themselves.
    """

    model_config = ConfigDict(frozen=True)

    enterprise_id: str = Field(min_length=1)
    environment: Environment
    evaluated_on: date


class RecoveryObjectiveAssessment(BaseModel):
    """
    Auditable comparison of one declared recovery target
    against one derived factual measurement.

    This is not an overall DR-success, release, blocking,
    remediation, or residual-risk decision.
    """

    model_config = ConfigDict(frozen=True)

    objective_id: str = Field(min_length=1)

    assessment_type: RecoveryObjectiveAssessmentType
    status: RecoveryObjectiveAssessmentStatus

    target_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    actual_seconds: float | None = Field(
        default=None,
        ge=0,
    )

    evaluated_on: date

    provenance_source_id: str = Field(min_length=1)
    provenance_version: str = Field(min_length=1)


def _objective_applies(
    *,
    objective: RecoveryObjective,
    context: RecoveryObjectiveAssessmentContext,
    measurement_service: str,
    measurement_component: str | None,
) -> bool:
    if (
        objective.scope.enterprise_id
        != context.enterprise_id
    ):
        return False

    if (
        objective.scope.environment
        != context.environment
    ):
        return False

    if objective.scope.service != measurement_service:
        return False

    if (
        objective.scope.component is not None
        and objective.scope.component
        != measurement_component
    ):
        return False

    if context.evaluated_on < objective.effective_from:
        return False

    if (
        objective.effective_to is not None
        and context.evaluated_on
        > objective.effective_to
    ):
        return False

    return True


def _resolve_status(
    *,
    applies: bool,
    target_seconds: float | None,
    actual_seconds: float | None,
) -> RecoveryObjectiveAssessmentStatus:
    if (
        not applies
        or target_seconds is None
        or actual_seconds is None
    ):
        return (
            RecoveryObjectiveAssessmentStatus
            .INDETERMINATE
        )

    if actual_seconds <= target_seconds:
        return RecoveryObjectiveAssessmentStatus.MET

    return RecoveryObjectiveAssessmentStatus.BREACHED


def _build_result(
    *,
    objective: RecoveryObjective,
    context: RecoveryObjectiveAssessmentContext,
    assessment_type: RecoveryObjectiveAssessmentType,
    status: RecoveryObjectiveAssessmentStatus,
    target_seconds: float | None,
    actual_seconds: float | None,
) -> RecoveryObjectiveAssessment:
    return RecoveryObjectiveAssessment(
        objective_id=objective.objective_id,
        assessment_type=assessment_type,
        status=status,
        target_seconds=target_seconds,
        actual_seconds=actual_seconds,
        evaluated_on=context.evaluated_on,
        provenance_source_id=(
            objective.provenance.source_id
        ),
        provenance_version=(
            objective.provenance.version
        ),
    )


def assess_rto_objective(
    *,
    objective: RecoveryObjective,
    measurement: RecoveryMeasurement,
    context: RecoveryObjectiveAssessmentContext,
) -> RecoveryObjectiveAssessment:
    """
    Compare measured service-recovery duration with RTO.

    Equality satisfies the objective.

    Missing or unusable evidence, absent target,
    scope mismatch, or ineffective objective yields
    INDETERMINATE rather than an inferred verdict.
    """

    actual_seconds = (
        measurement.recovery_duration_seconds
        if (
            measurement.status
            == RecoveryMeasurementStatus.MEASURED
        )
        else None
    )

    target_seconds = objective.rto_target_seconds

    applies = _objective_applies(
        objective=objective,
        context=context,
        measurement_service=measurement.scope.service,
        measurement_component=(
            measurement.scope.component
        ),
    )

    status = _resolve_status(
        applies=applies,
        target_seconds=target_seconds,
        actual_seconds=actual_seconds,
    )

    return _build_result(
        objective=objective,
        context=context,
        assessment_type=(
            RecoveryObjectiveAssessmentType.RTO
        ),
        status=status,
        target_seconds=target_seconds,
        actual_seconds=actual_seconds,
    )


def assess_rpo_objective(
    *,
    objective: RecoveryObjective,
    measurement: ReplicationExposureMeasurement,
    context: RecoveryObjectiveAssessmentContext,
) -> RecoveryObjectiveAssessment:
    """
    Compare measured replication exposure with RPO.

    Replication exposure is potential recovery-point
    exposure, not proof of actual business-data loss.

    Equality satisfies the objective.

    Missing or unusable evidence, absent target,
    scope mismatch, or ineffective objective yields
    INDETERMINATE.
    """

    actual_seconds = (
        measurement.exposure_interval_seconds
        if (
            measurement.status
            == ReplicationExposureMeasurementStatus
            .MEASURED
        )
        else None
    )

    target_seconds = objective.rpo_target_seconds

    applies = _objective_applies(
        objective=objective,
        context=context,
        measurement_service=measurement.scope.service,
        measurement_component=(
            measurement.scope.component
        ),
    )

    status = _resolve_status(
        applies=applies,
        target_seconds=target_seconds,
        actual_seconds=actual_seconds,
    )

    return _build_result(
        objective=objective,
        context=context,
        assessment_type=(
            RecoveryObjectiveAssessmentType.RPO
        ),
        status=status,
        target_seconds=target_seconds,
        actual_seconds=actual_seconds,
    )
