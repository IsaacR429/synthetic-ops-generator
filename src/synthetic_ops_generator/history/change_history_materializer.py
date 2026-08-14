from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeHistory,
)
from synthetic_ops_generator.history.change_materializer import (
    HistoricalMaterializedChange,
    materialize_historical_change,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
)


@dataclass(frozen=True)
class HistoricalMaterializedHistory:
    history: HistoricalChangeHistory
    changes: tuple[
        HistoricalMaterializedChange,
        ...,
    ]

    @property
    def events(self) -> tuple[GeneratedEvent, ...]:
        return tuple(
            event
            for change in self.changes
            for event in change.events
        )


def materialize_historical_change_history(
    *,
    history: HistoricalChangeHistory,
    scenarios: Mapping[
        str,
        ScenarioDefinition,
    ],
    enterprise: Enterprise,
    config_root: str | Path,
    ids: IdFactory,
    random_seed: int,
    incident_curve_spec: (
        PerturbationCurveSpec | None
    ) = None,
    post_change_samples: int = 6,
) -> HistoricalMaterializedHistory:
    _validate_history_materialization_inputs(
        history=history,
        scenarios=scenarios,
        enterprise=enterprise,
    )

    materialized_changes: list[
        HistoricalMaterializedChange
    ] = []

    for index, change in enumerate(
        history.changes
    ):
        scenario = scenarios[change.scenario_id]

        child_seed = random_seed + index

        materialized_changes.append(
            materialize_historical_change(
                change=change,
                scenario=scenario,
                enterprise=enterprise,
                config_root=config_root,
                ids=ids,
                random_seed=child_seed,
                incident_curve_spec=(
                    incident_curve_spec
                ),
                post_change_samples=(
                    post_change_samples
                ),
            )
        )

    return HistoricalMaterializedHistory(
        history=history,
        changes=tuple(
            materialized_changes
        ),
    )


def _validate_history_materialization_inputs(
    *,
    history: HistoricalChangeHistory,
    scenarios: Mapping[
        str,
        ScenarioDefinition,
    ],
    enterprise: Enterprise,
) -> None:
    if (
        history.enterprise_id
        != enterprise.enterprise_id
    ):
        raise ValueError(
            "Historical parent Enterprise "
            "does not match supplied Enterprise."
        )

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

        if (
            scenario.scenario_id
            != change.scenario_id
        ):
            raise ValueError(
                "Historical Change Scenario "
                "mapping is inconsistent."
            )

        if (
            scenario.target.enterprise_id
            != history.enterprise_id
        ):
            raise ValueError(
                "Historical Change Scenario "
                "Enterprise does not match "
                "parent history."
            )

        if (
            scenario.target.business_stream_id
            != history.business_stream_id
        ):
            raise ValueError(
                "Historical Change Scenario "
                "Business Stream does not match "
                "parent history."
            )

        if (
            scenario.target.service_id
            != history.service_id
        ):
            raise ValueError(
                "Historical Change Scenario "
                "Service does not match "
                "parent history."
            )
