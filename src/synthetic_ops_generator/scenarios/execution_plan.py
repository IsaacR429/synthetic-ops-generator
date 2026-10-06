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


@dataclass(frozen=True)
class ScenarioExecutionPlan:
    entries: tuple[ScenarioExecutionPlanEntry, ...]


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
            )
        )

    return ScenarioExecutionPlan(entries=tuple(entries))
