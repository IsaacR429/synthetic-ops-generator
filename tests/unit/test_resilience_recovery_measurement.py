from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.resilience import (
    ResilienceObservation,
    ResilienceObservationType,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)
from synthetic_ops_generator.resilience.recovery import (
    RecoveryMeasurementScope,
    RecoveryMeasurementStatus,
    measure_service_recovery,
)


OUTAGE_TIME = datetime(
    2026,
    10,
    19,
    10,
    0,
    tzinfo=UTC,
)

RESTORED_TIME = OUTAGE_TIME + timedelta(
    seconds=180,
)


def scope() -> RecoveryMeasurementScope:
    return RecoveryMeasurementScope(
        service="payment_service",
        component="payment_api",
        failed_site_id="bank_primary",
        failed_service_instance_id="payment_api_primary",
        restored_site_id="bank_secondary",
        restored_service_instance_id="payment_api_secondary",
    )


def unavailable_primary(
    *,
    observed_at: datetime = OUTAGE_TIME,
) -> ServiceAvailabilityObservation:
    return ServiceAvailabilityObservation(
        observation_id="RSO-UNAVAILABLE-001",
        availability_state=(
            ServiceAvailabilityState.UNAVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        observed_at=observed_at,
    )


def secondary_serving(
    *,
    observed_at: datetime = RESTORED_TIME,
) -> ResilienceObservation:
    return ResilienceObservation(
        observation_id="RSO-SERVING-001",
        observation_type=(
            ResilienceObservationType.INSTANCE_SERVING
        ),
        service="payment_service",
        component="payment_api",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=observed_at,
    )


def test_recovery_measurement_uses_unavailable_to_serving_interval() -> None:
    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=secondary_serving(),
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.MEASURED
    )

    assert measurement.outage_started_at == OUTAGE_TIME
    assert measurement.service_restored_at == RESTORED_TIME

    assert (
        measurement.recovery_duration_seconds
        == 180.0
    )

    assert (
        measurement.outage_start_observation_id
        == "RSO-UNAVAILABLE-001"
    )
    assert (
        measurement.restoration_observation_id
        == "RSO-SERVING-001"
    )


def test_missing_outage_is_indeterminate() -> None:
    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=None,
        restoration_observation=secondary_serving(),
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )

    assert measurement.outage_started_at is None
    assert measurement.recovery_duration_seconds is None
    assert measurement.outage_start_observation_id is None

    assert measurement.service_restored_at == RESTORED_TIME
    assert (
        measurement.restoration_observation_id
        == "RSO-SERVING-001"
    )


def test_missing_serving_observation_is_indeterminate() -> None:
    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=None,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )

    assert measurement.outage_started_at == OUTAGE_TIME
    assert measurement.service_restored_at is None
    assert measurement.recovery_duration_seconds is None

    assert (
        measurement.outage_start_observation_id
        == "RSO-UNAVAILABLE-001"
    )
    assert measurement.restoration_observation_id is None


def test_available_secondary_does_not_establish_restoration() -> None:
    available = ServiceAvailabilityObservation(
        observation_id="RSO-AVAILABLE-001",
        availability_state=(
            ServiceAvailabilityState.AVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
        observed_at=RESTORED_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=None,
    )

    assert available.availability_state == (
        ServiceAvailabilityState.AVAILABLE
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.service_restored_at is None


def test_instance_activated_does_not_establish_restoration() -> None:
    activated = ResilienceObservation(
        observation_id="RSO-ACTIVATED-001",
        observation_type=(
            ResilienceObservationType.INSTANCE_ACTIVATED
        ),
        service="payment_service",
        component="payment_api",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=RESTORED_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=activated,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.service_restored_at is None
    assert measurement.recovery_duration_seconds is None


def test_available_primary_is_not_valid_outage_start() -> None:
    available_primary = ServiceAvailabilityObservation(
        observation_id="RSO-PRIMARY-AVAILABLE-001",
        availability_state=(
            ServiceAvailabilityState.AVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        observed_at=OUTAGE_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=available_primary,
        restoration_observation=secondary_serving(),
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.outage_started_at is None
    assert measurement.recovery_duration_seconds is None


def test_outage_must_match_failed_instance_scope() -> None:
    wrong_instance = ServiceAvailabilityObservation(
        observation_id="RSO-WRONG-PRIMARY-001",
        availability_state=(
            ServiceAvailabilityState.UNAVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
        observed_at=OUTAGE_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=wrong_instance,
        restoration_observation=secondary_serving(),
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.outage_started_at is None
    assert measurement.outage_start_observation_id is None


def test_restoration_must_match_serving_instance_scope() -> None:
    wrong_target = ResilienceObservation(
        observation_id="RSO-WRONG-SERVING-001",
        observation_type=(
            ResilienceObservationType.INSTANCE_SERVING
        ),
        service="payment_service",
        component="payment_api",
        to_site_id="bank_primary",
        to_service_instance_id="payment_api_primary",
        observed_at=RESTORED_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=wrong_target,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.service_restored_at is None
    assert measurement.restoration_observation_id is None


def test_service_mismatch_is_indeterminate() -> None:
    wrong_service = ResilienceObservation(
        observation_id="RSO-WRONG-SERVICE-001",
        observation_type=(
            ResilienceObservationType.INSTANCE_SERVING
        ),
        service="another_service",
        component="payment_api",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=RESTORED_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=wrong_service,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.service_restored_at is None


def test_component_mismatch_is_indeterminate_when_scope_declares_component() -> None:
    wrong_component = ResilienceObservation(
        observation_id="RSO-WRONG-COMPONENT-001",
        observation_type=(
            ResilienceObservationType.INSTANCE_SERVING
        ),
        service="payment_service",
        component="payment_database",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=RESTORED_TIME,
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=wrong_component,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.service_restored_at is None


def test_service_level_scope_does_not_require_component_match() -> None:
    service_scope = RecoveryMeasurementScope(
        service="payment_service",
        component=None,
        failed_site_id="bank_primary",
        failed_service_instance_id="payment_api_primary",
        restored_site_id="bank_secondary",
        restored_service_instance_id="payment_api_secondary",
    )

    outage = ServiceAvailabilityObservation(
        observation_id="RSO-UNAVAILABLE-001",
        availability_state=(
            ServiceAvailabilityState.UNAVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        observed_at=OUTAGE_TIME,
    )

    restoration = ResilienceObservation(
        observation_id="RSO-SERVING-001",
        observation_type=(
            ResilienceObservationType.INSTANCE_SERVING
        ),
        service="payment_service",
        component="payment_api",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=RESTORED_TIME,
    )

    measurement = measure_service_recovery(
        scope=service_scope,
        outage_observation=outage,
        restoration_observation=restoration,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.MEASURED
    )
    assert measurement.recovery_duration_seconds == 180.0


def test_restoration_before_outage_is_indeterminate() -> None:
    restoration = secondary_serving(
        observed_at=OUTAGE_TIME - timedelta(seconds=1)
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=restoration,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.INDETERMINATE
    )
    assert measurement.recovery_duration_seconds is None


def test_equal_outage_and_restoration_time_measures_zero_duration() -> None:
    restoration = secondary_serving(
        observed_at=OUTAGE_TIME
    )

    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=restoration,
    )

    assert (
        measurement.status
        == RecoveryMeasurementStatus.MEASURED
    )
    assert measurement.recovery_duration_seconds == 0.0


def test_measurement_does_not_contain_recovery_objective_verdicts() -> None:
    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=secondary_serving(),
    )

    dumped = measurement.model_dump()

    assert "rto_target" not in dumped
    assert "rto_met" not in dumped
    assert "rpo_target" not in dumped
    assert "rpo_met" not in dumped
    assert "dr_success" not in dumped
    assert "data_loss" not in dumped

def test_recovery_measurement_rejects_naive_timestamp() -> None:
    from synthetic_ops_generator.resilience.recovery import (
        RecoveryMeasurement,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "Recovery measurement timestamps must be "
            "timezone-aware"
        ),
    ):
        RecoveryMeasurement(
            scope=scope(),
            status=RecoveryMeasurementStatus.MEASURED,
            outage_started_at=datetime(
                2026,
                10,
                19,
                10,
                0,
            ),
            service_restored_at=RESTORED_TIME,
            recovery_duration_seconds=180.0,
            outage_start_observation_id=(
                "RSO-UNAVAILABLE-001"
            ),
            restoration_observation_id=(
                "RSO-SERVING-001"
            ),
        )


def test_recovery_measurement_is_immutable() -> None:
    measurement = measure_service_recovery(
        scope=scope(),
        outage_observation=unavailable_primary(),
        restoration_observation=secondary_serving(),
    )

    with pytest.raises(
        ValidationError,
    ):
        measurement.recovery_duration_seconds = 999.0
