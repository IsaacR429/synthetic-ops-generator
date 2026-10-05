from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CapacityDirection(StrEnum):
    HIGHER_IS_PRESSURE = "higher_is_pressure"
    LOWER_IS_PRESSURE = "lower_is_pressure"


class CapacityClassification(StrEnum):
    NORMAL = "normal"
    PRESSURE = "pressure"
    SATURATED = "saturated"



class CapacityMetricEnvelope(BaseModel):
    metric_definition_id: str = Field(min_length=1)
    direction: CapacityDirection
    pressure_threshold: float
    saturation_threshold: float

    @model_validator(mode="after")
    def validate_threshold_order(
        self,
    ) -> "CapacityMetricEnvelope":
        if (
            self.direction
            == CapacityDirection.HIGHER_IS_PRESSURE
            and self.saturation_threshold
            <= self.pressure_threshold
        ):
            raise ValueError(
                "Saturation threshold must be greater than "
                "pressure threshold for higher-is-pressure capacity."
            )

        if (
            self.direction
            == CapacityDirection.LOWER_IS_PRESSURE
            and self.saturation_threshold
            >= self.pressure_threshold
        ):
            raise ValueError(
                "Saturation threshold must be less than "
                "pressure threshold for lower-is-pressure capacity."
            )

        return self


class CapacityProfile(BaseModel):
    profile_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None

    metrics: dict[
        str,
        CapacityMetricEnvelope,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_metric_keys(
        self,
    ) -> "CapacityProfile":
        for key, envelope in self.metrics.items():
            if key != envelope.metric_definition_id:
                raise ValueError(
                    "Capacity metric key does not match "
                    "metric_definition_id: "
                    f"{key}"
                )
        return self
