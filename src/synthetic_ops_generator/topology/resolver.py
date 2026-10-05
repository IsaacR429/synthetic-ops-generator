from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
)
from synthetic_ops_generator.topology.models import (
    Dependency,
)
from synthetic_ops_generator.topology.validator import (
    validate_topology,
)


class TopologyResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedTopologyNode:
    node_id: str
    node_type: Literal["service", "component"]
    service_id: str
    business_stream_id: str
    component_id: str | None = None
    environment: Environment | None = None


class TopologyResolver:
    """
    Resolves dependency graphs across Services and Components in an Enterprise.
    """

    def __init__(self, enterprise: Enterprise) -> None:
        validate_topology(enterprise)
        self._enterprise = enterprise

        services = {
            service.service_id: service
            for service in enterprise.services
        }

        self._nodes: dict[str, ResolvedTopologyNode] = {}
        for service in enterprise.services:
            self._nodes[service.service_id] = ResolvedTopologyNode(
                node_id=service.service_id,
                node_type="service",
                service_id=service.service_id,
                business_stream_id=service.business_stream_id,
            )

        for component in enterprise.components:
            service = services[component.service_id]
            self._nodes[component.component_id] = ResolvedTopologyNode(
                node_id=component.component_id,
                node_type="component",
                service_id=service.service_id,
                business_stream_id=service.business_stream_id,
                component_id=component.component_id,
                environment=component.environment,
            )

        self._outgoing: dict[str, list[Dependency]] = defaultdict(list)
        self._incoming: dict[str, list[Dependency]] = defaultdict(list)

        for dependency in enterprise.dependencies:
            self._outgoing[dependency.source_id].append(dependency)
            self._incoming[dependency.target_id].append(dependency)

    def resolve_node(self, node_id: str) -> ResolvedTopologyNode:
        node = self._nodes.get(node_id)
        if node is None:
            raise TopologyResolutionError(
                f"Unknown topology node: {node_id}"
            )
        return node

    def outgoing_dependencies(
        self, node_id: str
    ) -> tuple[Dependency, ...]:
        self.resolve_node(node_id)
        return tuple(self._outgoing.get(node_id, ()))

    def incoming_dependencies(
        self, node_id: str
    ) -> tuple[Dependency, ...]:
        self.resolve_node(node_id)
        return tuple(self._incoming.get(node_id, ()))

    def direct_dependencies_of(
        self, node_id: str
    ) -> tuple[ResolvedTopologyNode, ...]:
        return tuple(
            self.resolve_node(dependency.target_id)
            for dependency in self.outgoing_dependencies(node_id)
        )

    def direct_dependents_of(
        self, node_id: str
    ) -> tuple[ResolvedTopologyNode, ...]:
        return tuple(
            self.resolve_node(dependency.source_id)
            for dependency in self.incoming_dependencies(node_id)
        )

    def transitive_dependencies_of(
        self, node_id: str
    ) -> tuple[ResolvedTopologyNode, ...]:
        self.resolve_node(node_id)
        visited = {node_id}
        queue = deque([node_id])
        resolved: list[ResolvedTopologyNode] = []
        while queue:
            current = queue.popleft()
            for dependency in self._outgoing.get(current, ()):
                target_id = dependency.target_id
                if target_id in visited:
                    continue
                visited.add(target_id)
                resolved.append(self.resolve_node(target_id))
                queue.append(target_id)
        return tuple(resolved)

    def transitive_dependents_of(
        self, node_id: str
    ) -> tuple[ResolvedTopologyNode, ...]:
        self.resolve_node(node_id)
        visited = {node_id}
        queue = deque([node_id])
        resolved: list[ResolvedTopologyNode] = []
        while queue:
            current = queue.popleft()
            for dependency in self._incoming.get(current, ()):
                dependent_id = dependency.source_id
                if dependent_id in visited:
                    continue
                visited.add(dependent_id)
                resolved.append(self.resolve_node(dependent_id))
                queue.append(dependent_id)
        return tuple(resolved)
