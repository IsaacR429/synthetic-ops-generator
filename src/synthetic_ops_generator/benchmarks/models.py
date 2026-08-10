from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from synthetic_ops_generator.domain.enums import (
    Criticality,
    WorkloadClass,
)


class BenchmarkSourceType(StrEnum):
    EXTERNAL_REFERENCE = "external_reference"
    ENTERPRISE_SLO = "enterprise_slo"
    SYNTHETIC_REFERENCE = "synthetic_reference"


class BenchmarkSource(BaseModel):
    source_id: str = Field(min_length=1)

    source_type: BenchmarkSourceType

    source_name: str = Field(min_length=1)
    source_reference: str | None = None

    version: str = Field(min_length=1)
    retrieved_on: date | None = None

    rationale: str = Field(min_length=1)


class BenchmarkReferenceCatalogue(BaseModel):
    references: dict[str, BenchmarkSource] = Field(
        default_factory=dict
    )


class MetricPolicy(BaseModel):
    metric_definition_id: str = Field(min_length=1)

    reference_target: float
    warning_threshold: float
    blocking_threshold: float

    provenance: BenchmarkSource

    supporting_reference_ids: list[str] = Field(
        default_factory=list
    )


class BenchmarkProfile(BaseModel):
    profile_id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    workload_class: WorkloadClass
    criticality: Criticality

    description: str | None = None

    metrics: dict[str, MetricPolicy] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_metric_keys(self) -> "BenchmarkProfile":
        for key, policy in self.metrics.items():
            if key != policy.metric_definition_id:
                raise ValueError(
                    "Benchmark metric key does not match "
                    f"metric_definition_id: {key}"
                )

        return self


class BenchmarkCatalogue(BaseModel):
    profiles: dict[str, BenchmarkProfile] = Field(
        default_factory=dict
    )


class BenchmarkScope(StrEnum):
    GLOBAL = "global"
    INDUSTRY = "industry"
    ENTERPRISE = "enterprise"
    SERVICE = "service"
    SCENARIO = "scenario"


class BenchmarkOverride(BaseModel):
    scope: BenchmarkScope
    scope_id: str = Field(min_length=1)

    metric_definition_id: str = Field(min_length=1)

    reference_target: float | None = None
    warning_threshold: float | None = None
    blocking_threshold: float | None = None

    provenance: BenchmarkSource | None = None

    reason: str | None = None


class ResolvedBenchmark(BaseModel):
    metric_definition_id: str

    reference_target: float
    warning_threshold: float
    blocking_threshold: float

    provenance: BenchmarkSource

    applied_overrides: list[str] = Field(
        default_factory=list
    )
