import pytest

from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import (
    Criticality,
    Environment,
    Industry,
)
from synthetic_ops_generator.scenarios.execution_target import (
    ScenarioExecutionTargetResolutionError,
    resolve_scenario_execution_target,
)
from synthetic_ops_generator.topology.resolver import (
    TopologyResolutionError,
    TopologyResolver,
)


def build_enterprise() -> Enterprise:
    return Enterprise(
        enterprise_id="bank_alpha",
        name="Bank Alpha",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(
                stream_id="core_banking",
                name="Core Banking",
            ),
            BusinessStream(
                stream_id="payments",
                name="Payments",
            ),
        ],
        services=[
            Service(
                service_id="account_service",
                name="Account Service",
                business_stream_id="core_banking",
                owner="core_operations",
                criticality=Criticality.CRITICAL,
            ),
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="payment_operations",
                criticality=Criticality.CRITICAL,
            ),
        ],
        components=[
            Component(
                component_id="account_database",
                name="Account Database",
                component_type="database",
                service_id="account_service",
                environment=Environment.PRODUCTION,
            ),
        ],
    )


def test_component_node_resolves_owning_service_and_stream() -> None:
    topology = TopologyResolver(
        build_enterprise()
    )

    target = resolve_scenario_execution_target(
        topology=topology,
        node_id="account_database",
        environment=Environment.PRODUCTION,
    )

    assert target.business_stream == "core_banking"
    assert target.service == "account_service"
    assert target.component == "account_database"
    assert target.environment == Environment.PRODUCTION


def test_service_node_uses_scenario_environment() -> None:
    topology = TopologyResolver(
        build_enterprise()
    )

    target = resolve_scenario_execution_target(
        topology=topology,
        node_id="payment_service",
        environment=Environment.PRODUCTION,
    )

    assert target.business_stream == "payments"
    assert target.service == "payment_service"
    assert target.component is None
    assert target.environment == Environment.PRODUCTION


def test_component_environment_mismatch_is_rejected() -> None:
    topology = TopologyResolver(
        build_enterprise()
    )

    with pytest.raises(
        ScenarioExecutionTargetResolutionError,
        match="environment does not match",
    ):
        resolve_scenario_execution_target(
            topology=topology,
            node_id="account_database",
            environment=Environment.TEST,
        )


def test_unknown_topology_node_is_rejected() -> None:
    topology = TopologyResolver(
        build_enterprise()
    )

    with pytest.raises(
        TopologyResolutionError,
        match="Unknown topology node",
    ):
        resolve_scenario_execution_target(
            topology=topology,
            node_id="missing_component",
            environment=Environment.PRODUCTION,
        )
