from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class MetricDirection(StrEnum):
    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"
    CONTEXT_DEPENDENT = "context_dependent"


class MetricClassification(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    BLOCKING = "blocking"
    UNAVAILABLE = "unavailable"


class MetricDefinition(BaseModel):
    metric_definition_id: str = Field(min_length=1)

    name: str = Field(min_length=1)
    description: str | None = None

    unit: str = Field(min_length=1)
    evaluation_statistic: str = Field(min_length=1)

    direction: MetricDirection

    aggregation_window_seconds: int | None = Field(
        default=None,
        gt=0,
    )


class MetricCatalogue(BaseModel):
    definitions: dict[str, MetricDefinition] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_definition_keys(self) -> "MetricCatalogue":
        for key, definition in self.definitions.items():
            if key != definition.metric_definition_id:
                raise ValueError(
                    "Metric catalogue key does not match "
                    f"metric_definition_id: {key}"
                )

        return self
