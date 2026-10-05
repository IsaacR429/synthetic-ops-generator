from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.scenarios.context import (
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.topology.resolver import (
    ResolvedTopologyNode,
    TopologyResolver,
)


class ScenarioExecutionTargetResolutionError(ValueError):
    pass


def resolve_scenario_execution_target(
    *,
    topology: TopologyResolver,
    node_id: str,
    environment: Environment,
) -> ScenarioExecutionTarget:
    """
    Resolve a topology node into a Scenario execution target.

    Topology resolution determines structural identity and ownership.
    The Scenario supplies execution environment for service-scoped
    targets because Services are not environment-specific objects.

    Component-scoped targets must already belong to the requested
    execution environment.
    """

    node = topology.resolve_node(node_id)

    return scenario_execution_target_from_node(
        node=node,
        environment=environment,
    )


def scenario_execution_target_from_node(
    *,
    node: ResolvedTopologyNode,
    environment: Environment,
) -> ScenarioExecutionTarget:
    if node.node_type == "component":
        if node.component_id is None:
            raise ScenarioExecutionTargetResolutionError(
                "Resolved component topology node is missing "
                f"component identity: {node.node_id}"
            )

        if node.environment is None:
            raise ScenarioExecutionTargetResolutionError(
                "Resolved component topology node is missing "
                f"environment: {node.node_id}"
            )

        if node.environment != environment:
            raise ScenarioExecutionTargetResolutionError(
                "Topology component environment does not match "
                "Scenario execution environment: "
                f"{node.node_id} is {node.environment.value}; "
                f"requested {environment.value}."
            )

        return ScenarioExecutionTarget(
            business_stream=node.business_stream_id,
            service=node.service_id,
            component=node.component_id,
            environment=node.environment,
        )

    if node.node_type == "service":
        return ScenarioExecutionTarget(
            business_stream=node.business_stream_id,
            service=node.service_id,
            component=None,
            environment=environment,
        )

    raise ScenarioExecutionTargetResolutionError(
        f"Unsupported topology node type: {node.node_type}"
    )
