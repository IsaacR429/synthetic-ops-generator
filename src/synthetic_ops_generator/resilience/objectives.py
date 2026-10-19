from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
)


class RecoveryObjectiveScope(BaseModel):
    """
    Operational scope to which a recovery objective applies.

    Enterprise, service and environment are always explicit.
    Component may narrow the objective when required.

    Criticality, service class, ownership and mission criticality
    remain canonical enterprise-service properties and are not
    duplicated here.
    """

    model_config = ConfigDict(frozen=True)

    enterprise_id: str = Field(min_length=1)
    service: str = Field(min_length=1)

    component: str | None = Field(
        default=None,
        min_length=1,
    )

    environment: Environment


class RecoveryObjective(BaseModel):
    """
    Versioned, provenance-backed recovery objective.

    This model represents declared recovery targets only.

    It does not contain observed recovery measurements,
    replication exposure measurements, RTO/RPO compliance
    verdicts, DR-success conclusions, or data-loss conclusions.
    """

    model_config = ConfigDict(frozen=True)

    objective_id: str = Field(min_length=1)

    scope: RecoveryObjectiveScope

    rto_target_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    rpo_target_seconds: float | None = Field(
        default=None,
        ge=0,
    )

    provenance: BenchmarkSource

    effective_from: date
    effective_to: date | None = None

    description: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_objective(
        self,
    ) -> "RecoveryObjective":
        if (
            self.rto_target_seconds is None
            and self.rpo_target_seconds is None
        ):
            raise ValueError(
                "Recovery objective requires at least one "
                "of RTO or RPO."
            )

        if (
            self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError(
                "Recovery objective effective_to cannot "
                "precede effective_from."
            )

        return self
