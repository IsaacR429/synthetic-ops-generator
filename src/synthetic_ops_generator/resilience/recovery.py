from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from synthetic_ops_generator.domain.resilience import (
    ResilienceObservation,
    ResilienceObservationType,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)


class RecoveryMeasurementStatus(StrEnum):
    """
    Status of a derived service-recovery measurement.

    MEASURED means the required factual outage and restoration
    observations were compatible and chronologically usable.

    INDETERMINATE means the available evidence cannot establish
    a recovery duration.
    """

    MEASURED = "measured"
    INDETERMINATE = "indeterminate"


class RecoveryMeasurementScope(BaseModel):
    """
    Explicit operational scope for one recovery measurement.

    The failed endpoint and restored endpoint are declared rather
    than inferred from site roles or scenario identifiers.
    """

    model_config = ConfigDict(frozen=True)

    service: str = Field(min_length=1)

    component: str | None = Field(
        default=None,
        min_length=1,
    )

    failed_site_id: str = Field(min_length=1)
    failed_service_instance_id: str = Field(
        min_length=1
    )

    restored_site_id: str = Field(min_length=1)
    restored_service_instance_id: str = Field(
        min_length=1
    )


class RecoveryMeasurement(BaseModel):
    """
    Auditable derived measurement of service restoration time.

    This model compares factual resilience observations only.
    It does not contain recovery objectives, RTO/RPO verdicts,
    DR-success conclusions, or actual-data-loss conclusions.
    """

    model_config = ConfigDict(frozen=True)

    scope: RecoveryMeasurementScope

    status: RecoveryMeasurementStatus

    outage_started_at: datetime | None = None
    service_restored_at: datetime | None = None

    recovery_duration_seconds: float | None = None

    @field_validator(
        "outage_started_at",
        "service_restored_at",
    )
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Recovery measurement timestamps must be "
                "timezone-aware."
            )

        return value

    outage_start_observation_id: str | None = Field(
        default=None,
        min_length=1,
    )
    restoration_observation_id: str | None = Field(
        default=None,
        min_length=1,
    )


def _matches_component(
    *,
    expected_component: str | None,
    observed_component: str | None,
) -> bool:
    if expected_component is None:
        return True

    return observed_component == expected_component


def _valid_outage_observation(
    *,
    scope: RecoveryMeasurementScope,
    observation: ServiceAvailabilityObservation,
) -> bool:
    return (
        observation.availability_state
        == ServiceAvailabilityState.UNAVAILABLE
        and observation.service == scope.service
        and _matches_component(
            expected_component=scope.component,
            observed_component=observation.component,
        )
        and observation.site_id
        == scope.failed_site_id
        and observation.service_instance_id
        == scope.failed_service_instance_id
    )


def _valid_restoration_observation(
    *,
    scope: RecoveryMeasurementScope,
    observation: ResilienceObservation,
) -> bool:
    return (
        observation.observation_type
        == ResilienceObservationType.INSTANCE_SERVING
        and observation.service == scope.service
        and _matches_component(
            expected_component=scope.component,
            observed_component=observation.component,
        )
        and observation.to_site_id
        == scope.restored_site_id
        and observation.to_service_instance_id
        == scope.restored_service_instance_id
    )


def measure_service_recovery(
    *,
    scope: RecoveryMeasurementScope,
    outage_observation: (
        ServiceAvailabilityObservation | None
    ),
    restoration_observation: (
        ResilienceObservation | None
    ),
) -> RecoveryMeasurement:
    """
    Derive service-recovery duration from factual observations.

    Recovery begins when the declared failed Service Instance is
    observed UNAVAILABLE.

    Recovery ends only when the declared restored Service Instance
    is explicitly observed INSTANCE_SERVING.

    AVAILABLE or INSTANCE_ACTIVATED does not establish restored
    production service.

    Missing, incompatible, or chronologically invalid evidence
    produces INDETERMINATE rather than guessing another boundary.
    """

    valid_outage = (
        outage_observation is not None
        and _valid_outage_observation(
            scope=scope,
            observation=outage_observation,
        )
    )

    valid_restoration = (
        restoration_observation is not None
        and _valid_restoration_observation(
            scope=scope,
            observation=restoration_observation,
        )
    )

    outage_started_at = (
        outage_observation.observed_at
        if valid_outage
        else None
    )

    outage_start_observation_id = (
        outage_observation.observation_id
        if valid_outage
        else None
    )

    service_restored_at = (
        restoration_observation.observed_at
        if valid_restoration
        else None
    )

    restoration_observation_id = (
        restoration_observation.observation_id
        if valid_restoration
        else None
    )

    if (
        outage_started_at is None
        or service_restored_at is None
        or service_restored_at < outage_started_at
    ):
        return RecoveryMeasurement(
            scope=scope,
            status=(
                RecoveryMeasurementStatus.INDETERMINATE
            ),
            outage_started_at=outage_started_at,
            service_restored_at=service_restored_at,
            recovery_duration_seconds=None,
            outage_start_observation_id=(
                outage_start_observation_id
            ),
            restoration_observation_id=(
                restoration_observation_id
            ),
        )

    duration_seconds = (
        service_restored_at - outage_started_at
    ).total_seconds()

    return RecoveryMeasurement(
        scope=scope,
        status=RecoveryMeasurementStatus.MEASURED,
        outage_started_at=outage_started_at,
        service_restored_at=service_restored_at,
        recovery_duration_seconds=duration_seconds,
        outage_start_observation_id=(
            outage_start_observation_id
        ),
        restoration_observation_id=(
            restoration_observation_id
        ),
    )
