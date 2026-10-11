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


def _e54a_enterprise(
    *,
    service_instances: list[ServiceInstance],
) -> Enterprise:
    return Enterprise(
        enterprise_id="e54a_test",
        name="E5.4a Test Enterprise",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(
                stream_id="payments",
                name="Payments",
            ),
            BusinessStream(
                stream_id="accounts",
                name="Accounts",
            ),
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="payments_team",
                criticality=Criticality.CRITICAL,
            ),
            Service(
                service_id="account_service",
                name="Account Service",
                business_stream_id="accounts",
                owner="accounts_team",
                criticality=Criticality.CRITICAL,
            ),
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
                component_id="account_api",
                name="Account API",
                component_type="api",
                service_id="account_service",
                environment=Environment.PRODUCTION,
            ),
        ],
        sites=[
            Site(
                site_id="primary_site",
                name="Primary Site",
                region="region_a",
                role=SiteRole.PRIMARY,
            ),
            Site(
                site_id="secondary_site",
                name="Secondary Site",
                region="region_b",
                role=SiteRole.SECONDARY,
            ),
        ],
        service_instances=service_instances,
    )


def test_e54a_valid_component_bound_service_instance() -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="payment_api_primary",
                service_id="payment_service",
                component_id="payment_api",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    validate_topology(enterprise)


def test_e54a_service_instance_may_be_service_scoped_without_component(
) -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="payment_service_primary",
                service_id="payment_service",
                component_id=None,
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    validate_topology(enterprise)


def test_e54a_service_instance_rejects_unknown_service() -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="unknown_service_instance",
                service_id="missing_service",
                component_id=None,
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_e54a_service_instance_rejects_unknown_component() -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="missing_component_instance",
                service_id="payment_service",
                component_id="missing_component",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_e54a_service_instance_rejects_duplicate_instance_id() -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="duplicate_instance",
                service_id="payment_service",
                component_id="payment_api",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            ),
            ServiceInstance(
                instance_id="duplicate_instance",
                service_id="payment_service",
                component_id="payment_api",
                site_id="secondary_site",
                environment=Environment.PRODUCTION,
            ),
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_e54a_service_instance_component_must_belong_to_declared_service(
) -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="invalid_component_owner",
                service_id="payment_service",
                component_id="account_api",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_e54a_service_instance_environment_must_match_component(
) -> None:
    different_environment = next(
        environment
        for environment in Environment
        if environment != Environment.PRODUCTION
    )

    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="invalid_environment",
                service_id="payment_service",
                component_id="payment_api",
                site_id="primary_site",
                environment=different_environment,
            )
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_e54c_distinct_primary_secondary_instance_ids_are_valid(
) -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="payment_api_primary",
                service_id="payment_service",
                component_id="payment_api",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            ),
            ServiceInstance(
                instance_id="payment_api_secondary",
                service_id="payment_service",
                component_id="payment_api",
                site_id="secondary_site",
                environment=Environment.PRODUCTION,
            ),
        ]
    )

    validate_topology(enterprise)


def test_e54c_service_instance_id_must_not_collide_with_service_id(
) -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="payment_service",
                service_id="payment_service",
                component_id="payment_api",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)


def test_e54c_service_instance_id_must_not_collide_with_component_id(
) -> None:
    enterprise = _e54a_enterprise(
        service_instances=[
            ServiceInstance(
                instance_id="payment_api",
                service_id="payment_service",
                component_id="payment_api",
                site_id="primary_site",
                environment=Environment.PRODUCTION,
            )
        ]
    )

    with pytest.raises(TopologyValidationError):
        validate_topology(enterprise)
