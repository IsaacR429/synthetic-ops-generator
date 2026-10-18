from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel, ConfigDict

from synthetic_ops_generator.domain.enums import (
    Environment,
    RiskLevel,
)
from synthetic_ops_generator.governance.models import (
    PolicyControl,
)
from synthetic_ops_generator.topology.resolver import (
    ResolvedTopologyNode,
)


class ApplicabilityDimensionStatus(StrEnum):
    """
    Resolution state for one PolicyApplicability dimension.
    """

    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    UNCONSTRAINED = "unconstrained"


class ControlApplicabilityStatus(StrEnum):
    """
    Overall contextual applicability of one PolicyControl.

    NOT_APPLICABLE means at least one populated selector definitely
    does not match.

    INDETERMINATE means no selector definitely mismatches, but at
    least one required applicability value cannot be resolved.

    APPLICABLE means every populated selector is resolved and matches.
    """

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    INDETERMINATE = "indeterminate"


class PolicyApplicabilityContext(BaseModel):
    """
    Runtime context used only to resolve static policy applicability.

    The topology target supplies structural enterprise semantics.
    Explicit environment context is useful for service-level targets,
    whose topology node may legitimately have no environment.

    Change risk is external operational context and therefore remains
    separate from topology.
    """

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )

    target: ResolvedTopologyNode

    environment: Environment | None = None
    change_risk: RiskLevel | None = None


class ControlApplicabilityResult(BaseModel):
    """
    Auditable result of resolving one PolicyControl applicability.

    This is not requirement activation, compliance, blocking,
    waiver resolution, or an operational decision.
    """

    model_config = ConfigDict(frozen=True)

    control_id: str

    status: ControlApplicabilityStatus

    evaluated_dimensions: dict[
        str,
        ApplicabilityDimensionStatus,
    ]


T = TypeVar("T")


def _evaluate_dimension(
    *,
    allowed: set[T],
    actual: T | None,
) -> ApplicabilityDimensionStatus:
    """
    Evaluate one selector dimension.

    Empty selector means the dimension places no constraint.
    """

    if not allowed:
        return ApplicabilityDimensionStatus.UNCONSTRAINED

    if actual is None:
        return ApplicabilityDimensionStatus.UNKNOWN

    if actual in allowed:
        return ApplicabilityDimensionStatus.MATCH

    return ApplicabilityDimensionStatus.MISMATCH


def _resolve_environment(
    *,
    target: ResolvedTopologyNode,
    explicit_environment: Environment | None,
) -> tuple[
    Environment | None,
    bool,
]:
    """
    Resolve environment from topology and explicit operational context.

    Returns:
        (resolved_environment, conflict)

    A conflict is intentionally represented separately because choosing
    one source over the other would silently discard contradictory
    enterprise context.
    """

    topology_environment = target.environment

    if (
        explicit_environment is not None
        and topology_environment is not None
        and explicit_environment != topology_environment
    ):
        return None, True

    if explicit_environment is not None:
        return explicit_environment, False

    return topology_environment, False


def resolve_control_applicability(
    *,
    control: PolicyControl,
    context: PolicyApplicabilityContext,
) -> ControlApplicabilityResult:
    """
    Resolve contextual applicability for one PolicyControl.

    Semantics:
      - OR within one selector dimension
      - AND across populated selector dimensions
      - empty selector -> UNCONSTRAINED
      - known mismatch -> NOT_APPLICABLE
      - unresolved required value -> INDETERMINATE
      - otherwise -> APPLICABLE

    A definitive mismatch takes precedence over unrelated unknown
    dimensions because the control is already known not to apply.
    """

    applicability = control.applicability
    target = context.target

    resolved_environment, environment_conflict = (
        _resolve_environment(
            target=target,
            explicit_environment=context.environment,
        )
    )

    if not applicability.environments:
        environment_status = (
            ApplicabilityDimensionStatus.UNCONSTRAINED
        )
    elif environment_conflict:
        environment_status = (
            ApplicabilityDimensionStatus.UNKNOWN
        )
    else:
        environment_status = _evaluate_dimension(
            allowed=applicability.environments,
            actual=resolved_environment,
        )

    evaluated_dimensions = {
        "environment": environment_status,
        "service_class": _evaluate_dimension(
            allowed=applicability.service_classes,
            actual=target.service_class,
        ),
        "mission_criticality": _evaluate_dimension(
            allowed=applicability.mission_criticalities,
            actual=target.mission_criticality,
        ),
        "asset_class": _evaluate_dimension(
            allowed=applicability.asset_classes,
            actual=target.asset_class,
        ),
        "change_risk": _evaluate_dimension(
            allowed=applicability.change_risks,
            actual=context.change_risk,
        ),
    }

    dimension_states = set(
        evaluated_dimensions.values()
    )

    if ApplicabilityDimensionStatus.MISMATCH in dimension_states:
        status = ControlApplicabilityStatus.NOT_APPLICABLE
    elif ApplicabilityDimensionStatus.UNKNOWN in dimension_states:
        status = ControlApplicabilityStatus.INDETERMINATE
    else:
        status = ControlApplicabilityStatus.APPLICABLE

    return ControlApplicabilityResult(
        control_id=control.control_id,
        status=status,
        evaluated_dimensions=evaluated_dimensions,
    )
