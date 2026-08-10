from pydantic import BaseModel, Field, model_validator


class MetricBaseline(BaseModel):
    metric_definition_id: str = Field(min_length=1)

    center: float
    noise_stddev: float = Field(default=0.0, ge=0)

    lower_bound: float | None = None
    upper_bound: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "MetricBaseline":
        if (
            self.lower_bound is not None
            and self.center < self.lower_bound
        ):
            raise ValueError(
                "Baseline center cannot be below lower_bound."
            )

        if (
            self.upper_bound is not None
            and self.center > self.upper_bound
        ):
            raise ValueError(
                "Baseline center cannot exceed upper_bound."
            )

        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError(
                "lower_bound cannot exceed upper_bound."
            )

        return self


class BaselineProfile(BaseModel):
    profile_id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    historical_window_minutes: int = Field(gt=0)
    sample_interval_seconds: int = Field(gt=0)

    metrics: dict[str, MetricBaseline] = Field(
        default_factory=dict
    )
