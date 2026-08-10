import pytest

from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import Criticality, Environment, Industry
from synthetic_ops_generator.topology.models import (
    Dependency,
    DependencyRelationship,
    ServiceInstance,
    Site,
    SiteRole,
)
from synthetic_ops_generator.topology.validator import (
    TopologyValidationError,
    validate_topology,
)


def test_valid_topology() -> None:
    enterprise = Enterprise(
        enterprise_id="test_ent",
        name="Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(stream_id="payments", name="Payments")
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Processing",
                business_stream_id="payments",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            )
        ],
        components=[
            Component(
                component_id="payment_api",
                name="Payment API",
                component_type="api",
                service_id="payment_service",
                environment=Environment.PRODUCTION,
            ),
            Component(
                component_id="payment_db",
                name="Payment DB",
                component_type="database",
                service_id="payment_service",
                environment=Environment.PRODUCTION,
            ),
        ],
        dependencies=[
            Dependency(
                dependency_id="dep_1",
                source_id="payment_api",
                target_id="payment_db",
                relationship_type=DependencyRelationship.DEPENDS_ON,
                criticality=Criticality.CRITICAL,
            )
        ],
    )

    validate_topology(enterprise)


def test_invalid_service_business_stream_raises_error() -> None:
    enterprise = Enterprise(
        enterprise_id="test_ent",
        name="Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Processing",
                business_stream_id="unknown_stream",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            )
        ],
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_invalid_component_service_raises_error() -> None:
    enterprise = Enterprise(
        enterprise_id="test_ent",
        name="Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(stream_id="payments", name="Payments")
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Processing",
                business_stream_id="payments",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            )
        ],
        components=[
            Component(
                component_id="payment_api",
                name="Payment API",
                component_type="api",
                service_id="unknown_service",
                environment=Environment.PRODUCTION,
            )
        ],
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_invalid_service_instance_site_raises_error() -> None:
    enterprise = Enterprise(
        enterprise_id="test_ent",
        name="Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(stream_id="payments", name="Payments")
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Processing",
                business_stream_id="payments",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            )
        ],
        sites=[
            Site(
                site_id="primary_site",
                name="Primary Site",
                region="region_a",
                role=SiteRole.PRIMARY,
            )
        ],
        service_instances=[
            ServiceInstance(
                instance_id="payment_inst_1",
                service_id="payment_service",
                site_id="unknown_site",
                environment=Environment.PRODUCTION,
            )
        ],
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_invalid_dependency_source_raises_error() -> None:
    enterprise = Enterprise(
        enterprise_id="test_ent",
        name="Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(stream_id="payments", name="Payments")
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Processing",
                business_stream_id="payments",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            )
        ],
        dependencies=[
            Dependency(
                dependency_id="dep_1",
                source_id="non_existent_api",
                target_id="payment_service",
                relationship_type=DependencyRelationship.DEPENDS_ON,
                criticality=Criticality.CRITICAL,
            )
        ],
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_invalid_dependency_target_raises_error() -> None:
    enterprise = Enterprise(
        enterprise_id="test_ent",
        name="Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(stream_id="payments", name="Payments")
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Processing",
                business_stream_id="payments",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            )
        ],
        dependencies=[
            Dependency(
                dependency_id="dep_1",
                source_id="payment_service",
                target_id="non_existent_target",
                relationship_type=DependencyRelationship.DEPENDS_ON,
                criticality=Criticality.CRITICAL,
            )
        ],
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)
