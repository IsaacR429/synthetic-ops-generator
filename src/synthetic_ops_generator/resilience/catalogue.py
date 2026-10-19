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
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.resilience.objectives import (
    RecoveryObjective,
    RecoveryObjectiveScope,
)


class RecoveryObjectiveDefinition(BaseModel):
    """
    Configuration form of a recovery objective.

    Provenance is referenced by source identity so shared
    BenchmarkSource metadata is not duplicated across objectives.
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

    provenance_source_id: str = Field(min_length=1)

    effective_from: date
    effective_to: date | None = None

    description: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_definition(
        self,
    ) -> "RecoveryObjectiveDefinition":
        if (
            self.rto_target_seconds is None
            and self.rpo_target_seconds is None
        ):
            raise ValueError(
                "Recovery objective definition requires at "
                "least one of RTO or RPO."
            )

        if (
            self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError(
                "Recovery objective definition effective_to "
                "cannot precede effective_from."
            )

        return self


class RecoveryObjectiveConfiguration(BaseModel):
    """
    Shared recovery-objective configuration.

    Sources hold reusable provenance truth.
    Objectives reference those sources by identity.
    """

    model_config = ConfigDict(frozen=True)

    sources: dict[str, BenchmarkSource] = Field(
        default_factory=dict
    )

    objectives: dict[
        str,
        RecoveryObjectiveDefinition,
    ] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_catalogue_integrity(
        self,
    ) -> "RecoveryObjectiveConfiguration":
        for key, source in self.sources.items():
            if key != source.source_id:
                raise ValueError(
                    "Recovery objective source key does not "
                    f"match source_id: {key}"
                )

        for key, objective in self.objectives.items():
            if key != objective.objective_id:
                raise ValueError(
                    "Recovery objective catalogue key does "
                    f"not match objective_id: {key}"
                )

            if (
                objective.provenance_source_id
                not in self.sources
            ):
                raise ValueError(
                    "Recovery objective references unknown "
                    "provenance source: "
                    f"{objective.provenance_source_id}"
                )

        return self


def load_recovery_objective_configuration(
    path: str | Path,
) -> RecoveryObjectiveConfiguration:
    """
    Load and validate recovery-objective YAML using the
    repository's generic configuration loader.
    """

    return load_yaml_model(
        path,
        RecoveryObjectiveConfiguration,
    )


def resolve_recovery_objective(
    *,
    configuration: RecoveryObjectiveConfiguration,
    objective_id: str,
) -> RecoveryObjective:
    """
    Materialize one RecoveryObjective with resolved provenance.

    Resolution is identity-based and contains no scenario-specific
    behavior.
    """

    try:
        definition = configuration.objectives[
            objective_id
        ]
    except KeyError as exc:
        raise ValueError(
            "Unknown recovery objective: "
            f"{objective_id}"
        ) from exc

    provenance = configuration.sources[
        definition.provenance_source_id
    ]

    return RecoveryObjective(
        objective_id=definition.objective_id,
        scope=definition.scope,
        rto_target_seconds=(
            definition.rto_target_seconds
        ),
        rpo_target_seconds=(
            definition.rpo_target_seconds
        ),
        provenance=provenance,
        effective_from=definition.effective_from,
        effective_to=definition.effective_to,
        description=definition.description,
    )
