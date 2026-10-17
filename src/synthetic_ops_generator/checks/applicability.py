from synthetic_ops_generator.checks.models import (
    CheckDefinition,
)
from synthetic_ops_generator.topology.resolver import (
    ResolvedTopologyNode,
)


def is_check_applicable(
    definition: CheckDefinition,
    target: ResolvedTopologyNode,
) -> bool:
    """
    Return whether a reusable CheckDefinition applies to a
    resolved enterprise topology target.

    OR semantics apply inside each selector dimension.
    AND semantics apply across populated dimensions.
    Empty selector dimensions are unconstrained.

    This function evaluates structural enterprise truth only.
    It does not infer health, failure, impact or execution state.
    """

    applicability = definition.applicability

    if (
        applicability.service_classes
        and target.service_class
        not in applicability.service_classes
    ):
        return False

    if (
        applicability.mission_criticalities
        and target.mission_criticality
        not in applicability.mission_criticalities
    ):
        return False

    if (
        applicability.asset_classes
        and target.asset_class
        not in applicability.asset_classes
    ):
        return False

    return True
