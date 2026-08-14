from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class TemporalActivityConfig(BaseModel):
    business_start_hour: int = Field(
        ge=0,
        le=23,
    )
    business_end_hour: int = Field(
        ge=1,
        le=24,
    )

    business_days: list[int] = Field(
        min_length=1
    )

    business_hours_factor: float = Field(
        gt=0.0
    )
    off_hours_factor: float = Field(
        gt=0.0
    )
    weekend_factor: float = Field(
        gt=0.0
    )

    @field_validator("business_days")
    @classmethod
    def validate_days(
        cls,
        days: list[int],
    ) -> list[int]:
        if any(day < 0 or day > 6 for day in days):
            raise ValueError(
                "Business days must use weekday values from 0 to 6."
            )

        return days

    @model_validator(mode="after")
    def validate_hours(
        self,
    ) -> "TemporalActivityConfig":
        if (
            self.business_start_hour
            >= self.business_end_hour
        ):
            raise ValueError(
                "business_start_hour must be before "
                "business_end_hour."
            )

        return self


class TemporalPersistenceConfig(BaseModel):
    persistence: float = Field(
        ge=0.0,
        lt=1.0,
    )

    innovation_stddev: float = Field(
        ge=0.0
    )

    lower_bound: float = Field(
        default=0.0,
        ge=0.0,
    )

    upper_bound: float | None = None

    @model_validator(mode="after")
    def validate_bounds(
        self,
    ) -> "TemporalPersistenceConfig":
        if (
            self.upper_bound is not None
            and self.upper_bound
            < self.lower_bound
        ):
            raise ValueError(
                "upper_bound cannot be below "
                "lower_bound."
            )

        return self


class HistoricalMetricResponse(BaseModel):
    metric_definition_id: str = Field(
        min_length=1
    )

    slope_per_activity_unit: float


class HistoricalBehaviourProfile(BaseModel):
    profile_id: str = Field(
        min_length=1
    )

    name: str = Field(
        min_length=1
    )

    temporal: TemporalActivityConfig

    persistence: TemporalPersistenceConfig

    metric_responses: dict[
        str,
        HistoricalMetricResponse,
    ] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_metric_response_keys(
        self,
    ) -> "HistoricalBehaviourProfile":
        for (
            key,
            response,
        ) in self.metric_responses.items():
            if (
                key
                != response.metric_definition_id
            ):
                raise ValueError(
                    "Historical metric response "
                    "key does not match "
                    "metric_definition_id: "
                    f"{key}"
                )

        return self
