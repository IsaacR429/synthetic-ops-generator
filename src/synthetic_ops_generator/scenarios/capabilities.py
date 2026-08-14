from dataclasses import dataclass

from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
    SourceDomain,
)

_REQUIRED_HISTORICAL_PROFILES = {
    SourceDomain.METRIC: frozenset(
        {
            "healthy_baseline",
            "degraded_post_change",
            "recovered_post_rollback",
        }
    ),
    SourceDomain.INCIDENT: frozenset(
        {
            "incident_created",
            "incident_resolved",
        }
    ),
    SourceDomain.DEPLOYMENT: frozenset(
        {
            "successful_rollback",
        }
    ),
}


@dataclass(frozen=True)
class ScenarioExecutionCapabilities:
    standard_supported: bool
    historical_supported: bool


def _profiles_by_source(
    scenario: ScenarioDefinition,
) -> dict[SourceDomain, set[str]]:
    profiles: dict[
        SourceDomain,
        set[str],
    ] = {}

    for behaviour in scenario.behaviours:
        profiles.setdefault(
            behaviour.source,
            set(),
        ).add(
            behaviour.profile_id
        )

    return profiles


def resolve_scenario_execution_capabilities(
    scenario: ScenarioDefinition,
) -> ScenarioExecutionCapabilities:
    profiles = _profiles_by_source(
        scenario
    )

    historical_supported = all(
        required_profiles.issubset(
            profiles.get(
                source,
                set(),
            )
        )
        for source, required_profiles
        in _REQUIRED_HISTORICAL_PROFILES.items()
    )

    return ScenarioExecutionCapabilities(
        standard_supported=True,
        historical_supported=(
            historical_supported
        ),
    )
