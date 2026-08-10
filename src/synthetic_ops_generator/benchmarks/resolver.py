from collections.abc import Iterable

from synthetic_ops_generator.benchmarks.models import (
    BenchmarkOverride,
    BenchmarkScope,
    MetricPolicy,
    ResolvedBenchmark,
)
from synthetic_ops_generator.metrics.models import (
    MetricDefinition,
    MetricDirection,
)

_SCOPE_PRECEDENCE = {
    BenchmarkScope.GLOBAL: 0,
    BenchmarkScope.INDUSTRY: 1,
    BenchmarkScope.ENTERPRISE: 2,
    BenchmarkScope.SERVICE: 3,
    BenchmarkScope.SCENARIO: 4,
}


class BenchmarkResolutionError(ValueError):
    pass


def validate_threshold_order(
    definition: MetricDefinition,
    policy: MetricPolicy | ResolvedBenchmark,
) -> None:
    target = policy.reference_target
    warning = policy.warning_threshold
    blocking = policy.blocking_threshold

    if definition.direction == MetricDirection.LOWER_IS_BETTER:
        if not target <= warning <= blocking:
            raise BenchmarkResolutionError(
                "Lower-is-better thresholds must follow "
                "target <= warning <= blocking."
            )

        return

    if definition.direction == MetricDirection.HIGHER_IS_BETTER:
        if not target >= warning >= blocking:
            raise BenchmarkResolutionError(
                "Higher-is-better thresholds must follow "
                "target >= warning >= blocking."
            )

        return

    raise BenchmarkResolutionError(
        f"Metric {definition.metric_definition_id} "
        "is context-dependent and cannot use the standard "
        "threshold evaluator."
    )


def resolve_benchmark(
    definition: MetricDefinition,
    base_policy: MetricPolicy,
    overrides: Iterable[BenchmarkOverride] = (),
) -> ResolvedBenchmark:
    if base_policy.metric_definition_id != definition.metric_definition_id:
        raise BenchmarkResolutionError(
            "Metric definition and benchmark policy do not match."
        )

    validate_threshold_order(
        definition,
        base_policy,
    )

    reference_target = base_policy.reference_target
    warning_threshold = base_policy.warning_threshold
    blocking_threshold = base_policy.blocking_threshold
    provenance = base_policy.provenance

    applied_overrides: list[str] = []

    relevant_overrides = [
        override
        for override in overrides
        if override.metric_definition_id
        == definition.metric_definition_id
    ]

    relevant_overrides.sort(
        key=lambda override: _SCOPE_PRECEDENCE[override.scope]
    )

    seen_scopes: set[tuple[BenchmarkScope, str]] = set()

    for override in relevant_overrides:
        identity = (
            override.scope,
            override.scope_id,
        )

        if identity in seen_scopes:
            raise BenchmarkResolutionError(
                "Duplicate benchmark override for "
                f"{override.scope}:{override.scope_id}"
            )

        seen_scopes.add(identity)

        if override.reference_target is not None:
            reference_target = override.reference_target

        if override.warning_threshold is not None:
            warning_threshold = override.warning_threshold

        if override.blocking_threshold is not None:
            blocking_threshold = override.blocking_threshold

        if override.provenance is not None:
            provenance = override.provenance

        applied_overrides.append(
            f"{override.scope}:{override.scope_id}"
        )

    resolved = ResolvedBenchmark(
        metric_definition_id=definition.metric_definition_id,
        reference_target=reference_target,
        warning_threshold=warning_threshold,
        blocking_threshold=blocking_threshold,
        provenance=provenance,
        applied_overrides=applied_overrides,
    )

    validate_threshold_order(
        definition,
        resolved,
    )

    return resolved
