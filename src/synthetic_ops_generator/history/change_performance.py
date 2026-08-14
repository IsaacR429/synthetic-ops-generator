from collections.abc import Mapping
from dataclasses import dataclass

from synthetic_ops_generator.history.change_history import (
    HistoricalChangeCase,
    HistoricalChangeHistory,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
    SourceDomain,
)


@dataclass(frozen=True)
class HistoricalChangePerformance:
    change: HistoricalChangeCase
    incident_created: bool
    validation_duration_seconds: int

    def __post_init__(self) -> None:
        if self.validation_duration_seconds <= 0:
            raise ValueError(
                "Historical validation duration "
                "must be greater than zero."
            )


@dataclass(frozen=True)
class HistoricalChangePerformanceHistory:
    history: HistoricalChangeHistory
    changes: tuple[
        HistoricalChangePerformance,
        ...,
    ]


def build_historical_change_performance(
    *,
    change: HistoricalChangeCase,
    scenario: ScenarioDefinition,
    validation_duration_seconds: int,
) -> HistoricalChangePerformance:
    if change.scenario_id != scenario.scenario_id:
        raise ValueError(
            "Historical Change scenario_id "
            "does not match Scenario definition."
        )

    incident_created = _resolve_incident_created(
        scenario=scenario,
    )

    return HistoricalChangePerformance(
        change=change,
        incident_created=incident_created,
        validation_duration_seconds=(
            validation_duration_seconds
        ),
    )


def build_historical_change_performance_history(
    *,
    history: HistoricalChangeHistory,
    scenarios: Mapping[
        str,
        ScenarioDefinition,
    ],
    validation_durations_seconds: Mapping[
        int,
        int,
    ],
) -> HistoricalChangePerformanceHistory:
    materialized: list[
        HistoricalChangePerformance
    ] = []

    for change in history.changes:
        scenario = scenarios.get(
            change.scenario_id
        )

        if scenario is None:
            raise ValueError(
                "Historical Change Scenario "
                "definition is missing: "
                f"{change.scenario_id}"
            )

        duration = (
            validation_durations_seconds.get(
                change.ordinal
            )
        )

        if duration is None:
            raise ValueError(
                "Historical validation duration "
                "is missing for Change ordinal "
                f"{change.ordinal}."
            )

        materialized.append(
            build_historical_change_performance(
                change=change,
                scenario=scenario,
                validation_duration_seconds=(
                    duration
                ),
            )
        )

    extra_ordinals = (
        set(
            validation_durations_seconds
        )
        - {
            change.ordinal
            for change in history.changes
        }
    )

    if extra_ordinals:
        raise ValueError(
            "Historical validation durations "
            "contain unknown Change ordinals."
        )

    return HistoricalChangePerformanceHistory(
        history=history,
        changes=tuple(materialized),
    )


def _resolve_incident_created(
    *,
    scenario: ScenarioDefinition,
) -> bool:
    profiles = {
        behaviour.profile_id
        for behaviour in scenario.behaviours
        if (
            behaviour.source
            == SourceDomain.INCIDENT
        )
    }

    has_created = (
        "incident_created" in profiles
    )

    has_no_incident = (
        "no_incident" in profiles
    )

    if has_created and has_no_incident:
        raise ValueError(
            "Scenario cannot declare both "
            "incident_created and no_incident."
        )

    if has_created:
        return True

    if has_no_incident:
        return False

    raise ValueError(
        "Historical performance requires "
        "an explicit incident_created or "
        "no_incident Scenario behaviour."
    )
