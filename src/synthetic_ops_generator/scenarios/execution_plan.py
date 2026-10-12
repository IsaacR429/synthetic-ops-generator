from dataclasses import dataclass

from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.scenarios.context import (
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.execution_target import (
    ScenarioExecutionTargetResolutionError,
    resolve_scenario_execution_target,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioDefinition,
)
from synthetic_ops_generator.topology.resolver import (
    TopologyResolutionError,
    TopologyResolver,
)
from synthetic_ops_generator.topology.validator import (
    TopologyValidationError,
)


class ScenarioExecutionPlanningError(ValueError):
    pass


@dataclass(frozen=True)
class ScenarioExecutionPlanEntry:
    behaviour: ScenarioBehaviour
    execution_target: ScenarioExecutionTarget | None
    resilience_transition_target: (
        ScenarioExecutionTarget | None
    ) = None


@dataclass(frozen=True)
class ScenarioExecutionPlan:
    entries: tuple[ScenarioExecutionPlanEntry, ...]


def _validate_resilience_transition_targets(
    *,
    source: ScenarioExecutionTarget,
    destination: ScenarioExecutionTarget,
) -> None:
    if (
        source.service_instance_id is None
        or source.site_id is None
    ):
        raise ScenarioExecutionPlanningError(
            "Resilience transition source must resolve to "
            "a Service Instance execution target."
        )

    if (
        destination.service_instance_id is None
        or destination.site_id is None
    ):
        raise ScenarioExecutionPlanningError(
            "Resilience transition destination must resolve to "
            "a Service Instance execution target."
        )

    if (
        source.service_instance_id
        == destination.service_instance_id
    ):
        raise ScenarioExecutionPlanningError(
            "Resilience transition source and destination "
            "instances must differ."
        )

    if source.service != destination.service:
        raise ScenarioExecutionPlanningError(
            "Resilience transition source and destination "
            "must belong to the same Service: "
            f"{source.service} != {destination.service}."
        )

    if source.component != destination.component:
        raise ScenarioExecutionPlanningError(
            "Resilience transition source and destination "
            "must reference the same Component: "
            f"{source.component} != {destination.component}."
        )


def build_scenario_execution_plan(
    *,
    scenario: ScenarioDefinition,
    enterprise: Enterprise,
) -> ScenarioExecutionPlan:
    try:
        topology = TopologyResolver(enterprise)
    except TopologyValidationError as exc:
        raise ScenarioExecutionPlanningError(
            str(exc)
        ) from exc

    entries: list[ScenarioExecutionPlanEntry] = []

    for behaviour in scenario.behaviours:
        if (
            behaviour.source == SourceDomain.ITSM
            and behaviour.execution_node_id is not None
        ):
            raise ScenarioExecutionPlanningError(
                "ITSM behaviour must remain on declared Scenario target scope."
            )

        if behaviour.execution_node_id is None:
            entries.append(
                ScenarioExecutionPlanEntry(
                    behaviour=behaviour,
                    execution_target=None,
                )
            )
            continue

        try:
            target = resolve_scenario_execution_target(
                topology=topology,
                node_id=behaviour.execution_node_id,
                environment=scenario.target.environment,
            )

            resilience_transition_target = None

            if behaviour.resilience_transition is not None:
                resilience_transition_target = (
                    resolve_scenario_execution_target(
                        topology=topology,
                        node_id=(
                            behaviour.resilience_transition
                            .to_execution_node_id
                        ),
                        environment=(
                            scenario.target.environment
                        ),
                    )
                )

                _validate_resilience_transition_targets(
                    source=target,
                    destination=resilience_transition_target,
                )

        except (
            TopologyResolutionError,
            ScenarioExecutionTargetResolutionError,
        ) as exc:
            raise ScenarioExecutionPlanningError(
                str(exc)
            ) from exc

        entries.append(
            ScenarioExecutionPlanEntry(
                behaviour=behaviour,
                execution_target=target,
                resilience_transition_target=(
                    resilience_transition_target
                ),
            )
        )

    return ScenarioExecutionPlan(entries=tuple(entries))
