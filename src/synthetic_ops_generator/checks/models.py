from pydantic import BaseModel, Field

from synthetic_ops_generator.domain.enums import (
    AssetClass,
    MissionCriticality,
    ServiceClass,
)
from synthetic_ops_generator.domain.operational_test import (
    TestCategory,
)


class CheckApplicability(BaseModel):
    """
    Semantic selector for enterprise topology targets.

    Values inside one selector dimension use OR semantics.
    Populated selector dimensions are combined with AND semantics.

    Empty dimensions are unconstrained.
    """

    service_classes: set[ServiceClass] = Field(
        default_factory=set
    )

    mission_criticalities: set[
        MissionCriticality
    ] = Field(
        default_factory=set
    )

    asset_classes: set[AssetClass] = Field(
        default_factory=set
    )


class CheckDefinition(BaseModel):
    """
    Reusable definition of what can be checked.

    Execution state, requirement/mandatory semantics,
    scheduling, scenario outcome profiles and quantitative
    metric thresholds intentionally live elsewhere.
    """

    check_definition_id: str = Field(
        min_length=1
    )

    category: TestCategory

    test_type: str = Field(
        min_length=1
    )

    name: str = Field(
        min_length=1
    )

    description: str | None = None

    applicability: CheckApplicability = Field(
        default_factory=CheckApplicability
    )

class CheckExecutionSpec(BaseModel):
    """
    Binds a reusable CheckDefinition to execution-context semantics.

    `mandatory` belongs here rather than on CheckDefinition because
    whether a check is required depends on the operational/policy
    context in which it is used.

    This is intentionally a thin P1B bridge. Rich requirement,
    evidence and policy semantics belong to later P2.5-P slices.
    """

    definition: CheckDefinition

    mandatory: bool = True
