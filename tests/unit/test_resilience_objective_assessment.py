from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
    BenchmarkSourceType,
)
from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.domain.resilience import (
    ReplicationStatus,
)
from synthetic_ops_generator.resilience.assessment import (
    RecoveryObjectiveAssessmentContext,
    RecoveryObjectiveAssessmentStatus,
    assess_rpo_objective,
    assess_rto_objective,
)
from synthetic_ops_generator.resilience.exposure import (
    ReplicationExposureMeasurement,
    ReplicationExposureMeasurementStatus,
    ReplicationExposureScope,
)
from synthetic_ops_generator.resilience.objectives import (
    RecoveryObjective,
    RecoveryObjectiveScope,
)
from synthetic_ops_generator.resilience.recovery import (
    RecoveryMeasurement,
    RecoveryMeasurementScope,
    RecoveryMeasurementStatus,
)


OUTAGE_TIME = datetime(
    2026,
    10,
    19,
    10,
    0,
    tzinfo=UTC,
)


def source() -> BenchmarkSource:
    return BenchmarkSource(
        source_id="bank_dr_standard",
        source_type=BenchmarkSourceType.ENTERPRISE_SLO,
        source_name="Bank Alpha DR Standard",
        source_reference="enterprise://bank_alpha/dr-standard",
        version="2026.1",
        rationale="Approved enterprise recovery objectives.",
    )


def context(
    *,
    enterprise_id: str = "bank_alpha",
    environment: Environment = Environment.PRODUCTION,
    evaluated_on: date = date(2026, 10, 19),
) -> RecoveryObjectiveAssessmentContext:
    return RecoveryObjectiveAssessmentContext(
        enterprise_id=enterprise_id,
        environment=environment,
        evaluated_on=evaluated_on,
    )


def objective(
    *,
    service: str = "payment_service",
    component: str | None = "payment_api",
    rto: float | None = 300.0,
    rpo: float | None = 60.0,
    effective_from: date = date(2026, 1, 1),
    effective_to: date | None = None,
) -> RecoveryObjective:
    return RecoveryObjective(
        objective_id="RO-BANK-PAYMENTS-001",
        scope=RecoveryObjectiveScope(
            enterprise_id="bank_alpha",
            service=service,
            component=component,
            environment=Environment.PRODUCTION,
        ),
        rto_target_seconds=rto,
        rpo_target_seconds=rpo,
        provenance=source(),
        effective_from=effective_from,
        effective_to=effective_to,
    )


def recovery_measurement(
    *,
    service: str = "payment_service",
    component: str | None = "payment_api",
    duration: float = 180.0,
    status: RecoveryMeasurementStatus = (
        RecoveryMeasurementStatus.MEASURED
    ),
) -> RecoveryMeasurement:
    if status == RecoveryMeasurementStatus.MEASURED:
        restored_at = OUTAGE_TIME + timedelta(
            seconds=duration
        )

        return RecoveryMeasurement(
            scope=RecoveryMeasurementScope(
                service=service,
                component=component,
                failed_site_id="bank_primary",
                failed_service_instance_id="payment_api_primary",
                restored_site_id="bank_secondary",
                restored_service_instance_id="payment_api_secondary",
            ),
            status=status,
            outage_started_at=OUTAGE_TIME,
            service_restored_at=restored_at,
            recovery_duration_seconds=duration,
            outage_start_observation_id="RSO-OUTAGE-001",
            restoration_observation_id="RSO-SERVING-001",
        )

    return RecoveryMeasurement(
        scope=RecoveryMeasurementScope(
            service=service,
            component=component,
            failed_site_id="bank_primary",
            failed_service_instance_id="payment_api_primary",
            restored_site_id="bank_secondary",
            restored_service_instance_id="payment_api_secondary",
        ),
        status=status,
        outage_started_at=OUTAGE_TIME,
        recovery_duration_seconds=None,
        outage_start_observation_id="RSO-OUTAGE-001",
    )


def exposure_measurement(
    *,
    service: str = "payment_service",
    component: str | None = "payment_api",
    exposure: float = 30.0,
    status: ReplicationExposureMeasurementStatus = (
        ReplicationExposureMeasurementStatus.MEASURED
    ),
) -> ReplicationExposureMeasurement:
    if (
        status
        == ReplicationExposureMeasurementStatus.MEASURED
    ):
        return ReplicationExposureMeasurement(
            scope=ReplicationExposureScope(
                service=service,
                component=component,
                source_site_id="bank_primary",
                source_service_instance_id="payment_api_primary",
                target_site_id="bank_secondary",
                target_service_instance_id="payment_api_secondary",
            ),
            status=status,
            outage_reference_at=OUTAGE_TIME,
            replication_observed_at=(
                OUTAGE_TIME + timedelta(seconds=5)
            ),
            last_successful_replication_at=(
                OUTAGE_TIME - timedelta(seconds=exposure)
            ),
            exposure_interval_seconds=exposure,
            outage_observation_id="RSO-OUTAGE-001",
            replication_observation_id="RSO-REPLICATION-001",
            replication_status=ReplicationStatus.STOPPED,
        )

    return ReplicationExposureMeasurement(
        scope=ReplicationExposureScope(
            service=service,
            component=component,
            source_site_id="bank_primary",
            source_service_instance_id="payment_api_primary",
            target_site_id="bank_secondary",
            target_service_instance_id="payment_api_secondary",
        ),
        status=status,
        outage_reference_at=OUTAGE_TIME,
        replication_observed_at=(
            OUTAGE_TIME + timedelta(seconds=5)
        ),
        exposure_interval_seconds=None,
        outage_observation_id="RSO-OUTAGE-001",
        replication_observation_id="RSO-REPLICATION-001",
        replication_status=ReplicationStatus.UNKNOWN,
    )


def test_rto_is_met_when_actual_is_below_target() -> None:
    result = assess_rto_objective(
        objective=objective(),
        measurement=recovery_measurement(
            duration=180.0
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )
    assert result.target_seconds == 300.0
    assert result.actual_seconds == 180.0
    assert result.objective_id == "RO-BANK-PAYMENTS-001"


def test_rto_equality_counts_as_met() -> None:
    result = assess_rto_objective(
        objective=objective(rto=300.0),
        measurement=recovery_measurement(
            duration=300.0
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )


def test_rto_is_breached_when_actual_exceeds_target() -> None:
    result = assess_rto_objective(
        objective=objective(rto=300.0),
        measurement=recovery_measurement(
            duration=301.0
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.BREACHED
    )
    assert result.target_seconds == 300.0
    assert result.actual_seconds == 301.0


def test_rpo_is_met_when_exposure_is_below_target() -> None:
    result = assess_rpo_objective(
        objective=objective(),
        measurement=exposure_measurement(
            exposure=30.0
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )
    assert result.target_seconds == 60.0
    assert result.actual_seconds == 30.0


def test_rpo_equality_counts_as_met() -> None:
    result = assess_rpo_objective(
        objective=objective(rpo=60.0),
        measurement=exposure_measurement(
            exposure=60.0
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )


def test_rpo_is_breached_when_exposure_exceeds_target() -> None:
    result = assess_rpo_objective(
        objective=objective(rpo=60.0),
        measurement=exposure_measurement(
            exposure=61.0
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.BREACHED
    )


def test_missing_rto_target_is_indeterminate() -> None:
    result = assess_rto_objective(
        objective=objective(
            rto=None,
            rpo=60.0,
        ),
        measurement=recovery_measurement(),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )
    assert result.target_seconds is None
    assert result.actual_seconds == 180.0


def test_missing_rpo_target_is_indeterminate() -> None:
    result = assess_rpo_objective(
        objective=objective(
            rto=300.0,
            rpo=None,
        ),
        measurement=exposure_measurement(),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )
    assert result.target_seconds is None
    assert result.actual_seconds == 30.0


def test_indeterminate_recovery_measurement_produces_indeterminate_rto() -> None:
    result = assess_rto_objective(
        objective=objective(),
        measurement=recovery_measurement(
            status=RecoveryMeasurementStatus.INDETERMINATE
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )
    assert result.actual_seconds is None


def test_indeterminate_exposure_produces_indeterminate_rpo() -> None:
    result = assess_rpo_objective(
        objective=objective(),
        measurement=exposure_measurement(
            status=(
                ReplicationExposureMeasurementStatus
                .INDETERMINATE
            )
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )
    assert result.actual_seconds is None


@pytest.mark.parametrize(
    "assessment_kind",
    ["rto", "rpo"],
)
def test_wrong_enterprise_is_indeterminate(
    assessment_kind: str,
) -> None:
    if assessment_kind == "rto":
        result = assess_rto_objective(
            objective=objective(),
            measurement=recovery_measurement(),
            context=context(
                enterprise_id="another_enterprise"
            ),
        )
    else:
        result = assess_rpo_objective(
            objective=objective(),
            measurement=exposure_measurement(),
            context=context(
                enterprise_id="another_enterprise"
            ),
        )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )


@pytest.mark.parametrize(
    "assessment_kind",
    ["rto", "rpo"],
)
def test_wrong_environment_is_indeterminate(
    assessment_kind: str,
) -> None:
    if assessment_kind == "rto":
        result = assess_rto_objective(
            objective=objective(),
            measurement=recovery_measurement(),
            context=context(
                environment=Environment.STAGING
            ),
        )
    else:
        result = assess_rpo_objective(
            objective=objective(),
            measurement=exposure_measurement(),
            context=context(
                environment=Environment.STAGING
            ),
        )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )


@pytest.mark.parametrize(
    "assessment_kind",
    ["rto", "rpo"],
)
def test_service_mismatch_is_indeterminate(
    assessment_kind: str,
) -> None:
    if assessment_kind == "rto":
        result = assess_rto_objective(
            objective=objective(),
            measurement=recovery_measurement(
                service="another_service"
            ),
            context=context(),
        )
    else:
        result = assess_rpo_objective(
            objective=objective(),
            measurement=exposure_measurement(
                service="another_service"
            ),
            context=context(),
        )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )


@pytest.mark.parametrize(
    "assessment_kind",
    ["rto", "rpo"],
)
def test_declared_component_mismatch_is_indeterminate(
    assessment_kind: str,
) -> None:
    if assessment_kind == "rto":
        result = assess_rto_objective(
            objective=objective(
                component="payment_database"
            ),
            measurement=recovery_measurement(
                component="payment_api"
            ),
            context=context(),
        )
    else:
        result = assess_rpo_objective(
            objective=objective(
                component="payment_database"
            ),
            measurement=exposure_measurement(
                component="payment_api"
            ),
            context=context(),
        )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )


def test_service_level_rto_objective_accepts_component_measurement() -> None:
    result = assess_rto_objective(
        objective=objective(component=None),
        measurement=recovery_measurement(
            component="payment_api"
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )


def test_service_level_rpo_objective_accepts_component_measurement() -> None:
    result = assess_rpo_objective(
        objective=objective(component=None),
        measurement=exposure_measurement(
            component="payment_api"
        ),
        context=context(),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )


@pytest.mark.parametrize(
    "assessment_kind",
    ["rto", "rpo"],
)
def test_not_yet_effective_objective_is_indeterminate(
    assessment_kind: str,
) -> None:
    target = objective(
        effective_from=date(2026, 10, 20),
    )

    if assessment_kind == "rto":
        result = assess_rto_objective(
            objective=target,
            measurement=recovery_measurement(),
            context=context(
                evaluated_on=date(2026, 10, 19)
            ),
        )
    else:
        result = assess_rpo_objective(
            objective=target,
            measurement=exposure_measurement(),
            context=context(
                evaluated_on=date(2026, 10, 19)
            ),
        )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )


@pytest.mark.parametrize(
    "assessment_kind",
    ["rto", "rpo"],
)
def test_expired_objective_is_indeterminate(
    assessment_kind: str,
) -> None:
    target = objective(
        effective_to=date(2026, 10, 18),
    )

    if assessment_kind == "rto":
        result = assess_rto_objective(
            objective=target,
            measurement=recovery_measurement(),
            context=context(),
        )
    else:
        result = assess_rpo_objective(
            objective=target,
            measurement=exposure_measurement(),
            context=context(),
        )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.INDETERMINATE
    )


@pytest.mark.parametrize(
    "boundary_date",
    [
        date(2026, 1, 1),
        date(2026, 10, 19),
    ],
)
def test_effective_boundaries_are_inclusive(
    boundary_date: date,
) -> None:
    target = objective(
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 10, 19),
    )

    result = assess_rto_objective(
        objective=target,
        measurement=recovery_measurement(),
        context=context(
            evaluated_on=boundary_date
        ),
    )

    assert (
        result.status
        == RecoveryObjectiveAssessmentStatus.MET
    )


def test_assessment_preserves_objective_provenance_identity() -> None:
    result = assess_rto_objective(
        objective=objective(),
        measurement=recovery_measurement(),
        context=context(),
    )

    assert result.provenance_source_id == "bank_dr_standard"
    assert result.provenance_version == "2026.1"


def test_assessment_is_immutable() -> None:
    result = assess_rto_objective(
        objective=objective(),
        measurement=recovery_measurement(),
        context=context(),
    )

    with pytest.raises(ValidationError):
        result.status = (
            RecoveryObjectiveAssessmentStatus.BREACHED
        )


def test_rto_assessment_contains_no_dr_success_or_action_fields() -> None:
    result = assess_rto_objective(
        objective=objective(),
        measurement=recovery_measurement(),
        context=context(),
    )

    forbidden = {
        "dr_success",
        "go_no_go",
        "blocking",
        "remediation",
        "recommended_action",
        "residual_risk",
        "actual_data_loss",
        "data_loss",
    }

    assert forbidden.isdisjoint(result.model_dump())


def test_rpo_assessment_contains_no_dr_success_or_action_fields() -> None:
    result = assess_rpo_objective(
        objective=objective(),
        measurement=exposure_measurement(),
        context=context(),
    )

    forbidden = {
        "dr_success",
        "go_no_go",
        "blocking",
        "remediation",
        "recommended_action",
        "residual_risk",
        "actual_data_loss",
        "data_loss",
    }

    assert forbidden.isdisjoint(result.model_dump())
