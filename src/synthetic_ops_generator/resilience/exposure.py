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
    ReplicationObservation,
    ReplicationStatus,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)


class ReplicationExposureMeasurementStatus(StrEnum):
    """
    Status of a derived replication-exposure measurement.

    MEASURED means the factual outage boundary and replication
    evidence establish a usable exposure interval.

    INDETERMINATE means the available evidence cannot establish
    that interval without guessing.
    """

    MEASURED = "measured"
    INDETERMINATE = "indeterminate"


class ReplicationExposureScope(BaseModel):
    """
    Explicit source/target scope for one replication exposure
    measurement.

    Endpoints are declared rather than inferred from site roles,
    scenario IDs, or provider-specific semantics.
    """

    model_config = ConfigDict(frozen=True)

    service: str = Field(min_length=1)

    component: str | None = Field(
        default=None,
        min_length=1,
    )

    source_site_id: str = Field(min_length=1)
    source_service_instance_id: str = Field(
        min_length=1
    )

    target_site_id: str = Field(min_length=1)
    target_service_instance_id: str = Field(
        min_length=1
    )


class ReplicationExposureMeasurement(BaseModel):
    """
    Auditable derived replication exposure at an outage boundary.

    exposure_interval_seconds represents the interval from the
    most recent observed successful replication point to the
    factual source-instance outage time.

    It is not proof of actual data loss and does not determine
    RPO compliance or DR success.
    """

    model_config = ConfigDict(frozen=True)

    scope: ReplicationExposureScope

    status: ReplicationExposureMeasurementStatus

    outage_reference_at: datetime | None = None
    replication_observed_at: datetime | None = None
    last_successful_replication_at: datetime | None = None

    exposure_interval_seconds: float | None = None

    outage_observation_id: str | None = Field(
        default=None,
        min_length=1,
    )
    replication_observation_id: str | None = Field(
        default=None,
        min_length=1,
    )

    replication_status: ReplicationStatus | None = None

    @field_validator(
        "outage_reference_at",
        "replication_observed_at",
        "last_successful_replication_at",
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
                "Replication exposure timestamps must be "
                "timezone-aware."
            )

        return value


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
    scope: ReplicationExposureScope,
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
        == scope.source_site_id
        and observation.service_instance_id
        == scope.source_service_instance_id
    )


def _valid_replication_observation(
    *,
    scope: ReplicationExposureScope,
    observation: ReplicationObservation,
) -> bool:
    return (
        observation.service == scope.service
        and _matches_component(
            expected_component=scope.component,
            observed_component=observation.component,
        )
        and observation.from_site_id
        == scope.source_site_id
        and observation.from_service_instance_id
        == scope.source_service_instance_id
        and observation.to_site_id
        == scope.target_site_id
        and observation.to_service_instance_id
        == scope.target_service_instance_id
    )


def measure_replication_exposure(
    *,
    scope: ReplicationExposureScope,
    outage_observation: (
        ServiceAvailabilityObservation | None
    ),
    replication_observation: (
        ReplicationObservation | None
    ),
) -> ReplicationExposureMeasurement:
    """
    Derive replication exposure at the factual outage boundary.

    The interval is:

        outage_reference_at
        - last_successful_replication_at

    replication_observed_at is retained for audit lineage but is
    deliberately not used as the exposure endpoint.

    Evidence is measurable only when:
      - the outage is an UNAVAILABLE observation on the declared
        replication source endpoint;
      - the replication observation matches the declared source
        and target endpoints;
      - the replication snapshot was observed at or after the
        outage boundary;
      - last_successful_replication_at is known and is at or
        before the outage boundary.

    Otherwise the result is INDETERMINATE.
    """

    valid_outage = (
        outage_observation is not None
        and _valid_outage_observation(
            scope=scope,
            observation=outage_observation,
        )
    )

    valid_replication = (
        replication_observation is not None
        and _valid_replication_observation(
            scope=scope,
            observation=replication_observation,
        )
    )

    outage_reference_at = (
        outage_observation.observed_at
        if valid_outage
        else None
    )

    outage_observation_id = (
        outage_observation.observation_id
        if valid_outage
        else None
    )

    replication_observed_at = (
        replication_observation.observed_at
        if valid_replication
        else None
    )

    last_successful_replication_at = (
        replication_observation
        .last_successful_replication_at
        if valid_replication
        else None
    )

    replication_observation_id = (
        replication_observation.observation_id
        if valid_replication
        else None
    )

    replication_status = (
        replication_observation.replication_status
        if valid_replication
        else None
    )

    measurable = (
        outage_reference_at is not None
        and replication_observed_at is not None
        and last_successful_replication_at is not None
        and replication_observed_at
        >= outage_reference_at
        and last_successful_replication_at
        <= outage_reference_at
    )

    if not measurable:
        return ReplicationExposureMeasurement(
            scope=scope,
            status=(
                ReplicationExposureMeasurementStatus
                .INDETERMINATE
            ),
            outage_reference_at=outage_reference_at,
            replication_observed_at=(
                replication_observed_at
            ),
            last_successful_replication_at=(
                last_successful_replication_at
            ),
            exposure_interval_seconds=None,
            outage_observation_id=(
                outage_observation_id
            ),
            replication_observation_id=(
                replication_observation_id
            ),
            replication_status=replication_status,
        )

    exposure_interval_seconds = (
        outage_reference_at
        - last_successful_replication_at
    ).total_seconds()

    return ReplicationExposureMeasurement(
        scope=scope,
        status=(
            ReplicationExposureMeasurementStatus.MEASURED
        ),
        outage_reference_at=outage_reference_at,
        replication_observed_at=replication_observed_at,
        last_successful_replication_at=(
            last_successful_replication_at
        ),
        exposure_interval_seconds=(
            exposure_interval_seconds
        ),
        outage_observation_id=(
            outage_observation_id
        ),
        replication_observation_id=(
            replication_observation_id
        ),
        replication_status=replication_status,
    )
