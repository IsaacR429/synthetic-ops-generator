from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.resilience import (
    ReplicationObservation,
    ReplicationStatus,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)


OBSERVED_AT = datetime(
    2026,
    10,
    19,
    10,
    10,
    tzinfo=UTC,
)

LAST_REPLICATION_AT = datetime(
    2026,
    10,
    19,
    10,
    8,
    tzinfo=UTC,
)


def _availability(
    *,
    state: ServiceAvailabilityState = (
        ServiceAvailabilityState.UNAVAILABLE
    ),
    observed_at: datetime = OBSERVED_AT,
) -> ServiceAvailabilityObservation:
    return ServiceAvailabilityObservation(
        observation_id="AVO0000001",
        availability_state=state,
        service="claims_processing",
        component="claims_api",
        site_id="insurance_primary",
        service_instance_id="claims_api_primary",
        observed_at=observed_at,
    )


def _replication(
    *,
    status: ReplicationStatus = (
        ReplicationStatus.SYNCHRONIZED
    ),
    observed_at: datetime = OBSERVED_AT,
    last_successful_replication_at: datetime | None = (
        LAST_REPLICATION_AT
    ),
) -> ReplicationObservation:
    return ReplicationObservation(
        observation_id="RPO0000001",
        service="claims_processing",
        component="claims_api",
        from_site_id="insurance_primary",
        from_service_instance_id="claims_api_primary",
        to_site_id="insurance_secondary",
        to_service_instance_id="claims_api_secondary",
        replication_status=status,
        last_successful_replication_at=(
            last_successful_replication_at
        ),
        observed_at=observed_at,
    )


def test_availability_states_are_factual() -> None:
    assert (
        ServiceAvailabilityState.UNAVAILABLE.value
        == "unavailable"
    )
    assert (
        ServiceAvailabilityState.AVAILABLE.value
        == "available"
    )


def test_unavailable_observation_identifies_endpoint() -> None:
    observation = _availability()

    assert (
        observation.availability_state
        == ServiceAvailabilityState.UNAVAILABLE
    )
    assert observation.site_id == "insurance_primary"
    assert (
        observation.service_instance_id
        == "claims_api_primary"
    )
    assert observation.observed_at == OBSERVED_AT


def test_available_observation_can_represent_later_recovery_fact() -> None:
    observation = _availability(
        state=ServiceAvailabilityState.AVAILABLE,
    )

    assert (
        observation.availability_state
        == ServiceAvailabilityState.AVAILABLE
    )


def test_availability_component_is_optional() -> None:
    observation = ServiceAvailabilityObservation(
        observation_id="AVO0000002",
        availability_state=(
            ServiceAvailabilityState.UNAVAILABLE
        ),
        service="claims_processing",
        site_id="insurance_primary",
        service_instance_id="claims_api_primary",
        observed_at=OBSERVED_AT,
    )

    assert observation.component is None


def test_availability_requires_concrete_site_and_instance() -> None:
    with pytest.raises(ValidationError):
        ServiceAvailabilityObservation(
            observation_id="AVO0000003",
            availability_state=(
                ServiceAvailabilityState.UNAVAILABLE
            ),
            service="claims_processing",
            site_id="insurance_primary",
            observed_at=OBSERVED_AT,
        )


def test_availability_rejects_naive_observation_time() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _availability(
            observed_at=datetime(
                2026,
                10,
                19,
                10,
                10,
            )
        )


def test_replication_status_vocabulary_is_factual() -> None:
    assert (
        ReplicationStatus.SYNCHRONIZED.value
        == "synchronized"
    )
    assert ReplicationStatus.LAGGING.value == "lagging"
    assert ReplicationStatus.STOPPED.value == "stopped"
    assert ReplicationStatus.UNKNOWN.value == "unknown"


def test_replication_observation_preserves_endpoints_and_timestamp() -> None:
    observation = _replication()

    assert (
        observation.from_service_instance_id
        == "claims_api_primary"
    )
    assert (
        observation.to_service_instance_id
        == "claims_api_secondary"
    )
    assert (
        observation.replication_status
        == ReplicationStatus.SYNCHRONIZED
    )
    assert (
        observation.last_successful_replication_at
        == LAST_REPLICATION_AT
    )
    assert observation.observed_at == OBSERVED_AT


def test_replication_endpoints_must_be_distinct() -> None:
    with pytest.raises(
        ValidationError,
        match="instances must differ",
    ):
        ReplicationObservation(
            observation_id="RPO0000002",
            service="claims_processing",
            from_site_id="insurance_primary",
            from_service_instance_id="claims_api_primary",
            to_site_id="insurance_primary",
            to_service_instance_id="claims_api_primary",
            replication_status=ReplicationStatus.SYNCHRONIZED,
            last_successful_replication_at=(
                LAST_REPLICATION_AT
            ),
            observed_at=OBSERVED_AT,
        )


def test_replication_allows_same_site_with_distinct_instances() -> None:
    observation = ReplicationObservation(
        observation_id="RPO0000003",
        service="claims_processing",
        from_site_id="insurance_primary",
        from_service_instance_id="claims_api_a",
        to_site_id="insurance_primary",
        to_service_instance_id="claims_api_b",
        replication_status=ReplicationStatus.SYNCHRONIZED,
        last_successful_replication_at=(
            LAST_REPLICATION_AT
        ),
        observed_at=OBSERVED_AT,
    )

    assert (
        observation.from_service_instance_id
        != observation.to_service_instance_id
    )


def test_replication_can_report_unknown_last_success() -> None:
    observation = _replication(
        status=ReplicationStatus.UNKNOWN,
        last_successful_replication_at=None,
    )

    assert observation.last_successful_replication_at is None


def test_replication_rejects_naive_last_success_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _replication(
            last_successful_replication_at=datetime(
                2026,
                10,
                19,
                10,
                8,
            )
        )


def test_replication_rejects_last_success_after_observation() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot be after",
    ):
        _replication(
            last_successful_replication_at=datetime(
                2026,
                10,
                19,
                10,
                11,
                tzinfo=UTC,
            )
        )


def test_replication_rejects_naive_observation_time() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _replication(
            observed_at=datetime(
                2026,
                10,
                19,
                10,
                10,
            )
        )


def test_dr_fact_models_do_not_claim_rto_rpo_or_success() -> None:
    availability_fields = (
        ServiceAvailabilityObservation.model_fields
    )
    replication_fields = ReplicationObservation.model_fields

    forbidden = {
        "dr_success",
        "recovery_success",
        "rto_met",
        "rpo_met",
        "compliant",
        "blocking",
        "decision",
        "residual_risk",
    }

    assert forbidden.isdisjoint(availability_fields)
    assert forbidden.isdisjoint(replication_fields)


def test_availability_fact_does_not_store_derived_recovery_duration() -> None:
    fields = ServiceAvailabilityObservation.model_fields

    assert "failure_at" not in fields
    assert "restored_at" not in fields
    assert "recovery_duration" not in fields
