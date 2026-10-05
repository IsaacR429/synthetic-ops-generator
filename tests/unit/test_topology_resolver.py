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
from synthetic_ops_generator.topology.models import (
    Dependency,
    DependencyRelationship,
)
from synthetic_ops_generator.topology.resolver import (
    TopologyResolutionError,
    TopologyResolver,
)
from synthetic_ops_generator.topology.validator import (
    TopologyValidationError,
    validate_topology,
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
            BusinessStream(
                stream_id="digital_banking",
                name="Digital Banking",
            ),
        ],
        services=[
            Service(
                service_id="account_service",
                name="Account Service",
                business_stream_id="core_banking",
                owner="core_banking_operations",
                criticality=Criticality.CRITICAL,
            ),
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="payments_operations",
                criticality=Criticality.CRITICAL,
            ),
            Service(
                service_id="mobile_banking_service",
                name="Mobile Banking",
                business_stream_id="digital_banking",
                owner="digital_banking_operations",
                criticality=Criticality.HIGH,
            ),
        ],
        components=[
            Component(
                component_id="account_database",
                name="Account DB",
                component_type="database",
                service_id="account_service",
                environment=Environment.PRODUCTION,
            ),
            Component(
                component_id="account_api",
                name="Account API",
                component_type="api",
                service_id="account_service",
                environment=Environment.PRODUCTION,
            ),
            Component(
                component_id="mobile_api",
                name="Mobile API",
                component_type="api",
                service_id="mobile_banking_service",
                environment=Environment.PRODUCTION,
            ),
        ],
        dependencies=[
            Dependency(
                dependency_id="dep_1",
                source_id="account_api",
                target_id="account_database",
                relationship_type=DependencyRelationship.DEPENDS_ON,
                criticality=Criticality.HIGH,
            ),
            Dependency(
                dependency_id="dep_2",
                source_id="payment_service",
                target_id="account_database",
                relationship_type=DependencyRelationship.DEPENDS_ON,
                criticality=Criticality.HIGH,
            ),
            Dependency(
                dependency_id="dep_3",
                source_id="mobile_api",
                target_id="account_api",
                relationship_type=DependencyRelationship.DEPENDS_ON,
                criticality=Criticality.HIGH,
            ),
        ],
    )


def test_transitive_dependents_of() -> None:
    enterprise = build_enterprise()
    resolver = TopologyResolver(enterprise)

    dependents = resolver.transitive_dependents_of(
        "account_database"
    )
    ids = tuple(
        node.node_id
        for node in dependents
    )
    assert ids == (
        "account_api",
        "payment_service",
        "mobile_api",
    )
    assert "account_database" not in ids


def test_unknown_node_is_rejected() -> None:
    resolver = TopologyResolver(
        build_enterprise()
    )
    with pytest.raises(
        TopologyResolutionError,
        match="Unknown topology node",
    ):
        resolver.resolve_node(
            "unknown_node"
        )


def test_service_component_id_collision_is_rejected() -> None:
    enterprise = build_enterprise()
    enterprise.components.append(
        Component(
            component_id="payment_service",
            name="Ambiguous Component",
            component_type="api",
            service_id="payment_service",
            environment=Environment.PRODUCTION,
        )
    )
    with pytest.raises(
        TopologyValidationError,
        match="globally unique",
    ):
        validate_topology(
            enterprise
        )


def test_direct_dependencies_and_dependents() -> None:
    enterprise = build_enterprise()
    resolver = TopologyResolver(enterprise)

    direct_deps = resolver.direct_dependencies_of("account_api")
    assert tuple(node.node_id for node in direct_deps) == ("account_database",)

    direct_dependents = resolver.direct_dependents_of("account_api")
    assert tuple(node.node_id for node in direct_dependents) == ("mobile_api",)


def test_transitive_dependencies_of() -> None:
    enterprise = build_enterprise()
    resolver = TopologyResolver(enterprise)

    deps = resolver.transitive_dependencies_of("mobile_api")
    ids = tuple(node.node_id for node in deps)
    assert ids == ("account_api", "account_database")


def test_resolve_node_returns_node_details() -> None:
    enterprise = build_enterprise()
    resolver = TopologyResolver(enterprise)

    account_db = resolver.resolve_node(
        "account_database"
    )
    assert account_db.node_id == "account_database"
    assert account_db.node_type == "component"
    assert account_db.service_id == "account_service"
    assert account_db.business_stream_id == "core_banking"
    assert account_db.component_id == "account_database"
    assert account_db.environment == Environment.PRODUCTION

    payment = resolver.resolve_node(
        "payment_service"
    )
    assert payment.node_id == "payment_service"
    assert payment.node_type == "service"
    assert payment.service_id == "payment_service"
    assert payment.business_stream_id == "payments"
    assert payment.component_id is None
    assert payment.environment is None


def test_transitive_dependents_are_cycle_safe() -> None:
    enterprise = build_enterprise()
    enterprise.dependencies.append(
        Dependency(
            dependency_id="dep_cycle",
            source_id="account_database",
            target_id="mobile_api",
            relationship_type=(
                DependencyRelationship.DEPENDS_ON
            ),
            criticality=Criticality.HIGH,
        )
    )
    resolver = TopologyResolver(
        enterprise
    )
    dependents = resolver.transitive_dependents_of(
        "account_database"
    )
    ids = tuple(
        node.node_id
        for node in dependents
    )
    assert ids == (
        "account_api",
        "payment_service",
        "mobile_api",
    )
    assert "account_database" not in ids
