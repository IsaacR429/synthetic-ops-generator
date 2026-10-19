from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.domain.resilience import (
    ReplicationObservation,
    ReplicationStatus,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)
from synthetic_ops_generator.resilience.exposure import (
    ReplicationExposureMeasurementStatus,
    ReplicationExposureScope,
    measure_replication_exposure,
)


OUTAGE_TIME = datetime(
    2026,
    10,
    19,
    10,
    0,
    tzinfo=UTC,
)

REPLICATION_OBSERVED_TIME = (
    OUTAGE_TIME + timedelta(seconds=5)
)

LAST_SUCCESSFUL_TIME = (
    OUTAGE_TIME - timedelta(seconds=60)
)


def scope() -> ReplicationExposureScope:
    return ReplicationExposureScope(
        service="payment_service",
        component="payment_api",
        source_site_id="bank_primary",
        source_service_instance_id="payment_api_primary",
        target_site_id="bank_secondary",
        target_service_instance_id="payment_api_secondary",
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


def replication_observation(
    *,
    observed_at: datetime = REPLICATION_OBSERVED_TIME,
    last_successful_at: datetime | None = LAST_SUCCESSFUL_TIME,
    status: ReplicationStatus = ReplicationStatus.STOPPED,
) -> ReplicationObservation:
    return ReplicationObservation(
        observation_id="RSO-REPLICATION-001",
        service="payment_service",
        component="payment_api",
        from_site_id="bank_primary",
        from_service_instance_id="payment_api_primary",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        replication_status=status,
        last_successful_replication_at=(
            last_successful_at
        ),
        observed_at=observed_at,
    )


def test_replication_exposure_is_measured_at_outage_boundary() -> None:
    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=(
            replication_observation()
        ),
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.MEASURED
    )

    assert (
        measurement.outage_reference_at
        == OUTAGE_TIME
    )
    assert (
        measurement.replication_observed_at
        == REPLICATION_OBSERVED_TIME
    )
    assert (
        measurement.last_successful_replication_at
        == LAST_SUCCESSFUL_TIME
    )

    assert (
        measurement.exposure_interval_seconds
        == 60.0
    )

    assert (
        measurement.outage_observation_id
        == "RSO-UNAVAILABLE-001"
    )
    assert (
        measurement.replication_observation_id
        == "RSO-REPLICATION-001"
    )

    assert (
        measurement.replication_status
        == ReplicationStatus.STOPPED
    )


def test_exposure_does_not_use_replication_observation_time() -> None:
    replication = replication_observation(
        observed_at=(
            OUTAGE_TIME + timedelta(seconds=30)
        ),
        last_successful_at=(
            OUTAGE_TIME - timedelta(seconds=60)
        ),
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=replication,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.MEASURED
    )

    # If replication_observed_at were incorrectly used,
    # this would be 90 seconds rather than 60.
    assert (
        measurement.exposure_interval_seconds
        == 60.0
    )


def test_missing_outage_is_indeterminate() -> None:
    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=None,
        replication_observation=(
            replication_observation()
        ),
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )

    assert measurement.outage_reference_at is None
    assert measurement.outage_observation_id is None

    assert (
        measurement.replication_observed_at
        == REPLICATION_OBSERVED_TIME
    )
    assert (
        measurement.last_successful_replication_at
        == LAST_SUCCESSFUL_TIME
    )
    assert (
        measurement.replication_observation_id
        == "RSO-REPLICATION-001"
    )

    assert measurement.exposure_interval_seconds is None


def test_missing_replication_observation_is_indeterminate() -> None:
    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=None,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )

    assert (
        measurement.outage_reference_at
        == OUTAGE_TIME
    )
    assert (
        measurement.outage_observation_id
        == "RSO-UNAVAILABLE-001"
    )

    assert measurement.replication_observed_at is None
    assert (
        measurement.last_successful_replication_at
        is None
    )
    assert (
        measurement.replication_observation_id
        is None
    )
    assert measurement.exposure_interval_seconds is None


def test_available_primary_is_not_valid_outage_reference() -> None:
    available = ServiceAvailabilityObservation(
        observation_id="RSO-AVAILABLE-001",
        availability_state=(
            ServiceAvailabilityState.AVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        observed_at=OUTAGE_TIME,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=available,
        replication_observation=(
            replication_observation()
        ),
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )

    assert measurement.outage_reference_at is None
    assert measurement.outage_observation_id is None
    assert measurement.exposure_interval_seconds is None


def test_outage_reference_must_match_replication_source_scope() -> None:
    wrong_source = ServiceAvailabilityObservation(
        observation_id="RSO-WRONG-OUTAGE-001",
        availability_state=(
            ServiceAvailabilityState.UNAVAILABLE
        ),
        service="payment_service",
        component="payment_api",
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
        observed_at=OUTAGE_TIME,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=wrong_source,
        replication_observation=(
            replication_observation()
        ),
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )
    assert measurement.outage_reference_at is None


def test_replication_source_must_match_scope() -> None:
    wrong_source = ReplicationObservation(
        observation_id="RSO-WRONG-SOURCE-001",
        service="payment_service",
        component="payment_api",
        from_site_id="bank_secondary",
        from_service_instance_id="payment_api_secondary",
        to_site_id="bank_primary",
        to_service_instance_id="payment_api_primary",
        replication_status=ReplicationStatus.STOPPED,
        last_successful_replication_at=(
            LAST_SUCCESSFUL_TIME
        ),
        observed_at=REPLICATION_OBSERVED_TIME,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=wrong_source,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )

    assert measurement.replication_observed_at is None
    assert measurement.replication_observation_id is None


def test_replication_target_must_match_scope() -> None:
    wrong_target = ReplicationObservation(
        observation_id="RSO-WRONG-TARGET-001",
        service="payment_service",
        component="payment_api",
        from_site_id="bank_primary",
        from_service_instance_id="payment_api_primary",
        to_site_id="bank_other",
        to_service_instance_id="payment_api_other",
        replication_status=ReplicationStatus.STOPPED,
        last_successful_replication_at=(
            LAST_SUCCESSFUL_TIME
        ),
        observed_at=REPLICATION_OBSERVED_TIME,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=wrong_target,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )

    assert measurement.replication_observed_at is None
    assert measurement.replication_observation_id is None


def test_replication_service_must_match_scope() -> None:
    wrong_service = ReplicationObservation(
        observation_id="RSO-WRONG-SERVICE-001",
        service="another_service",
        component="payment_api",
        from_site_id="bank_primary",
        from_service_instance_id="payment_api_primary",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        replication_status=ReplicationStatus.STOPPED,
        last_successful_replication_at=(
            LAST_SUCCESSFUL_TIME
        ),
        observed_at=REPLICATION_OBSERVED_TIME,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=wrong_service,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )
    assert measurement.replication_observation_id is None


def test_component_mismatch_is_indeterminate_when_scope_declares_component() -> None:
    wrong_component = ReplicationObservation(
        observation_id="RSO-WRONG-COMPONENT-001",
        service="payment_service",
        component="payment_database",
        from_site_id="bank_primary",
        from_service_instance_id="payment_api_primary",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        replication_status=ReplicationStatus.STOPPED,
        last_successful_replication_at=(
            LAST_SUCCESSFUL_TIME
        ),
        observed_at=REPLICATION_OBSERVED_TIME,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=wrong_component,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )
    assert measurement.replication_observation_id is None


def test_service_level_scope_does_not_require_component_match() -> None:
    service_scope = ReplicationExposureScope(
        service="payment_service",
        component=None,
        source_site_id="bank_primary",
        source_service_instance_id="payment_api_primary",
        target_site_id="bank_secondary",
        target_service_instance_id="payment_api_secondary",
    )

    measurement = measure_replication_exposure(
        scope=service_scope,
        outage_observation=unavailable_primary(),
        replication_observation=(
            replication_observation()
        ),
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.MEASURED
    )
    assert (
        measurement.exposure_interval_seconds
        == 60.0
    )


def test_unknown_last_success_is_indeterminate() -> None:
    replication = replication_observation(
        last_successful_at=None,
        status=ReplicationStatus.UNKNOWN,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=replication,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )

    assert (
        measurement.replication_status
        == ReplicationStatus.UNKNOWN
    )
    assert (
        measurement.last_successful_replication_at
        is None
    )
    assert measurement.exposure_interval_seconds is None


def test_replication_snapshot_before_outage_is_indeterminate() -> None:
    replication = replication_observation(
        observed_at=(
            OUTAGE_TIME - timedelta(seconds=1)
        ),
        last_successful_at=(
            OUTAGE_TIME - timedelta(seconds=60)
        ),
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=replication,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )
    assert measurement.exposure_interval_seconds is None


def test_last_success_after_outage_is_indeterminate() -> None:
    replication = replication_observation(
        observed_at=(
            OUTAGE_TIME + timedelta(seconds=10)
        ),
        last_successful_at=(
            OUTAGE_TIME + timedelta(seconds=1)
        ),
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=replication,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.INDETERMINATE
    )
    assert measurement.exposure_interval_seconds is None


def test_last_success_at_outage_measures_zero_exposure() -> None:
    replication = replication_observation(
        observed_at=OUTAGE_TIME,
        last_successful_at=OUTAGE_TIME,
        status=ReplicationStatus.SYNCHRONIZED,
    )

    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=replication,
    )

    assert (
        measurement.status
        == ReplicationExposureMeasurementStatus.MEASURED
    )
    assert (
        measurement.exposure_interval_seconds
        == 0.0
    )


def test_measurement_does_not_claim_data_loss_or_rpo_compliance() -> None:
    measurement = measure_replication_exposure(
        scope=scope(),
        outage_observation=unavailable_primary(),
        replication_observation=(
            replication_observation()
        ),
    )

    dumped = measurement.model_dump()

    assert "actual_data_loss" not in dumped
    assert "data_loss" not in dumped
    assert "rpo_target" not in dumped
    assert "rpo_met" not in dumped
    assert "rpo_breached" not in dumped
    assert "dr_success" not in dumped
