from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class ResilienceObservationType(StrEnum):
    FAILOVER_INITIATED = "failover_initiated"
    TRAFFIC_SWITCH_STARTED = "traffic_switch_started"
    TRAFFIC_SWITCH_COMPLETED = "traffic_switch_completed"
    INSTANCE_ACTIVATED = "instance_activated"
    INSTANCE_SERVING = "instance_serving"


_TRANSITION_OBSERVATION_TYPES = frozenset(
    {
        ResilienceObservationType.FAILOVER_INITIATED,
        ResilienceObservationType.TRAFFIC_SWITCH_STARTED,
        ResilienceObservationType.TRAFFIC_SWITCH_COMPLETED,
    }
)

_INSTANCE_STATE_OBSERVATION_TYPES = frozenset(
    {
        ResilienceObservationType.INSTANCE_ACTIVATED,
        ResilienceObservationType.INSTANCE_SERVING,
    }
)


class ResilienceObservation(BaseModel):
    """
    A factual resilience or traffic-transition observation.

    This model records what an operational source observed.
    It does not determine DR success, RTO compliance,
    resilience adequacy or residual risk.
    """

    observation_id: str = Field(min_length=1)
    observation_type: ResilienceObservationType

    service: str = Field(min_length=1)
    component: str | None = Field(
        default=None,
        min_length=1,
    )

    from_site_id: str | None = Field(
        default=None,
        min_length=1,
    )
    from_service_instance_id: str | None = Field(
        default=None,
        min_length=1,
    )

    to_site_id: str | None = Field(
        default=None,
        min_length=1,
    )
    to_service_instance_id: str | None = Field(
        default=None,
        min_length=1,
    )

    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Resilience observation timestamps "
                "must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_observation(
        self,
    ) -> "ResilienceObservation":
        source_has_site = (
            self.from_site_id is not None
        )
        source_has_instance = (
            self.from_service_instance_id is not None
        )

        destination_has_site = (
            self.to_site_id is not None
        )
        destination_has_instance = (
            self.to_service_instance_id is not None
        )

        if source_has_site != source_has_instance:
            raise ValueError(
                "Source resilience endpoint requires both "
                "site and service instance."
            )

        if (
            destination_has_site
            != destination_has_instance
        ):
            raise ValueError(
                "Destination resilience endpoint requires "
                "both site and service instance."
            )

        source_defined = (
            source_has_site
            and source_has_instance
        )
        destination_defined = (
            destination_has_site
            and destination_has_instance
        )

        if (
            self.observation_type
            in _TRANSITION_OBSERVATION_TYPES
        ):
            if not (
                source_defined
                and destination_defined
            ):
                raise ValueError(
                    "Resilience transition observations require "
                    "both source and destination endpoints."
                )

            if (
                self.from_service_instance_id
                == self.to_service_instance_id
            ):
                raise ValueError(
                    "Resilience transition source and "
                    "destination instances must differ."
                )

            return self

        if (
            self.observation_type
            in _INSTANCE_STATE_OBSERVATION_TYPES
        ):
            if source_defined:
                raise ValueError(
                    "Instance-state resilience observations "
                    "cannot define a source endpoint."
                )

            if not destination_defined:
                raise ValueError(
                    "Instance-state resilience observations "
                    "require a destination endpoint."
                )

        return self
